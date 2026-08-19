"""Composes the final MP4 with ffmpeg: burns in captions, mixes BGM under
the original on-site audio, and applies fade in/out. No image or TTS
generation happens here — `video_path` is already-edited real footage.
"""

from __future__ import annotations

import math
import re
import subprocess
import time
from pathlib import Path

from . import config

_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(-?[\d.]+)\s*dB")


class PipelineTimeoutError(TimeoutError):
    """Raised when a step would run past the pipeline's wall-clock budget.

    This does not make ffmpeg itself faster — it converts "ran silently
    past the deadline" into a clear, fast failure, since encode time
    scales with input (more/longer cuts = more work) and can't be bounded
    for arbitrary input in the general case."""


def _remaining_seconds(deadline: float | None) -> float | None:
    """Seconds left before `deadline` (a time.monotonic() timestamp), or
    None if there's no deadline. Raises immediately if already expired,
    so a doomed subprocess is never even started."""
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PipelineTimeoutError(
            f"Exceeded the {config.PIPELINE_TIMEOUT_SECONDS}s pipeline budget before this step could run."
        )
    return remaining


def _run(command: list[str], *, deadline: float | None = None, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run wrapper that turns a timeout into PipelineTimeoutError
    with the offending command attached, instead of a bare TimeoutExpired."""
    try:
        return subprocess.run(command, timeout=_remaining_seconds(deadline), **kwargs)
    except subprocess.TimeoutExpired as e:
        raise PipelineTimeoutError(
            f"Exceeded the {config.PIPELINE_TIMEOUT_SECONDS}s pipeline budget running: {' '.join(command[:4])} ..."
        ) from e


def _escape_filter_path(path: Path) -> str:
    """Escape a filesystem path for use inside an ffmpeg filtergraph value.

    ffmpeg's filter parser treats ':' as an option separator, which collides
    with Windows drive letters (C:\\...), so it must be backslash-escaped.
    """
    posix_path = str(Path(path).resolve()).replace("\\", "/")
    return posix_path.replace(":", "\\:")


def probe_duration(video_path: Path, *, deadline: float | None = None) -> float:
    result = _run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(video_path),
        ],
        deadline=deadline,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return float(result.stdout.strip())


def probe_mean_volume_db(audio_path: Path, *, deadline: float | None = None) -> float:
    """Mean loudness (dBFS) of a media file's audio track, via ffmpeg's
    volumedetect filter."""
    result = _run(
        ["ffmpeg", "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"],
        deadline=deadline,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    match = _MEAN_VOLUME_RE.search(result.stderr)
    if not match:
        raise RuntimeError(f"Could not determine mean_volume for {audio_path}")
    return float(match.group(1))


def compute_bgm_gain_db(orig_mean_db: float, bgm_mean_db: float, bgm_volume: float) -> float:
    """Gain (dB) to apply to the raw BGM track so its measured loudness sits
    at `bgm_volume` (linear ratio, e.g. 0.2 = 20%) relative to the on-site
    audio's measured loudness — not relative to the BGM file's own raw
    level, which is what a flat `volume=bgm_volume` would do and can leave
    BGM effectively inaudible under louder on-site audio."""
    target_db = orig_mean_db + 20 * math.log10(bgm_volume)
    return target_db - bgm_mean_db


def build_ffmpeg_command(
    video_path: Path,
    subtitle_path: Path,
    bgm_path: Path,
    output_path: Path,
    duration: float,
    *,
    bgm_volume: float = config.BGM_VOLUME,
    bgm_gain_db: float | None = None,
    orig_volume: float = config.ORIGINAL_VOLUME,
    fade_duration: float = config.FADE_DURATION,
    font_dir: Path = config.FONT_DIR,
    font_name: str = config.SUBTITLE_FONT_NAME,
    margin_v: int = config.SUBTITLE_MARGIN_V,
    width: int = config.VIDEO_WIDTH,
    height: int = config.VIDEO_HEIGHT,
    fps: int = config.FPS,
    preset: str = config.FFMPEG_PRESET,
) -> list[str]:
    """Build the ffmpeg argv for the compose step. Pure/testable: does not
    touch the filesystem or require ffmpeg to be installed.

    `bgm_gain_db`, when given (normally computed by compose_video() via
    compute_bgm_gain_db()), is the actual dB gain applied to the raw BGM
    track. If omitted, falls back to treating `bgm_volume` as a flat linear
    multiplier of the BGM's own raw level (the old, naive behaviour)."""
    fade_out_start = max(duration - fade_duration, 0.0)
    subtitle_arg = _escape_filter_path(subtitle_path)
    fontsdir_arg = _escape_filter_path(font_dir)
    if bgm_gain_db is None:
        bgm_gain_db = 20 * math.log10(bgm_volume)

    filter_complex = (
        f"[0:a]volume={orig_volume}[a_orig];"
        f"[1:a]volume={bgm_gain_db}dB,aloop=loop=-1:size=2147483647[a_bgm];"
        f"[a_orig][a_bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a_mixed];"
        f"[a_mixed]alimiter=limit=0.97[aout];"
        f"[0:v]subtitles='{subtitle_arg}':fontsdir='{fontsdir_arg}':"
        f"force_style='FontName={font_name},MarginV={margin_v}',"
        f"fade=t=in:st=0:d={fade_duration},"
        f"fade=t=out:st={fade_out_start}:d={fade_duration}[vout]"
    )

    return [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(bgm_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", preset,
        "-r", str(fps),
        "-s", f"{width}x{height}",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]


def build_concat_command(
    clip_paths: list[Path],
    clip_durations: list[float],
    output_path: Path,
    *,
    cut_duration: float = config.CUT_DURATION,
    width: int = config.VIDEO_WIDTH,
    height: int = config.VIDEO_HEIGHT,
    fps: int = config.FPS,
    preset: str = config.FFMPEG_PRESET,
) -> list[str]:
    """Build the ffmpeg argv that normalizes raw per-cut clips (varying
    resolution/duration, e.g. assets/videos/1.mp4, 2.mp4, ...) and
    concatenates them into one source video: each clip is trimmed/padded to
    exactly `cut_duration` and letterboxed to a common resolution. Pure/
    testable: does not touch the filesystem or require ffmpeg installed."""
    if len(clip_paths) != len(clip_durations):
        raise ValueError("clip_paths and clip_durations must be the same length")
    if not clip_paths:
        raise ValueError("clip_paths must not be empty")

    filters = []
    concat_refs = []
    for i, duration in enumerate(clip_durations):
        trim_dur = min(duration, cut_duration)
        pad_dur = max(0.0, cut_duration - duration)
        video_chain = (
            f"[{i}:v]trim=start=0:duration={trim_dur},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
        )
        if pad_dur > 0:
            video_chain += f",tpad=stop_mode=clone:stop_duration={pad_dur}"
        video_chain += f"[v{i}]"
        filters.append(video_chain)
        filters.append(
            f"[{i}:a]atrim=start=0:duration={trim_dur},asetpts=PTS-STARTPTS,"
            f"apad=whole_dur={cut_duration}[a{i}]"
        )
        concat_refs.append(f"[v{i}][a{i}]")

    filters.append(f"{''.join(concat_refs)}concat=n={len(clip_paths)}:v=1:a=1[vout][aout]")

    command = ["ffmpeg", "-y"]
    for clip in clip_paths:
        command += ["-i", str(clip)]
    command += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", preset,
        "-r", str(fps),
        "-c:a", "aac",
        str(output_path),
    ]
    return command


def assemble_cuts_video(
    clip_paths: list[Path],
    output_path: Path,
    *,
    cut_duration: float = config.CUT_DURATION,
    deadline: float | None = None,
    **kwargs,
) -> Path:
    """Normalize and concatenate raw per-cut clips into a single
    already-edited source video, ready to hand to compose_video().

    `deadline` (a time.monotonic() timestamp) is an optional wall-clock
    budget shared across every ffprobe/ffmpeg call in this function — pass
    it down from run_pipeline() rather than a fresh duration per call, so
    time already spent on earlier clips counts against later ones."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    durations = [probe_duration(clip, deadline=deadline) for clip in clip_paths]
    command = build_concat_command(clip_paths, durations, output_path, cut_duration=cut_duration, **kwargs)
    _run(command, deadline=deadline, check=True)
    return output_path


def compose_video(
    video_path: Path,
    subtitle_path: Path,
    bgm_path: Path,
    output_path: Path,
    *,
    duration: float | None = None,
    bgm_volume: float = config.BGM_VOLUME,
    orig_volume: float = config.ORIGINAL_VOLUME,
    deadline: float | None = None,
    **kwargs,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if duration is None:
        duration = probe_duration(video_path, deadline=deadline)

    if orig_volume > 0:
        # BGM is calibrated against the on-site audio's level *after* its
        # own volume reduction, so the two stay balanced regardless of
        # orig_volume.
        orig_mean_db = probe_mean_volume_db(video_path, deadline=deadline) + 20 * math.log10(orig_volume)
        bgm_mean_db = probe_mean_volume_db(bgm_path, deadline=deadline)
        bgm_gain_db = compute_bgm_gain_db(orig_mean_db, bgm_mean_db, bgm_volume)
    else:
        # On-site audio is muted entirely — there's nothing left to be
        # "relative to" (and `math.log10(0)` would raise anyway). BGM
        # becomes the sole audio track, so build_ffmpeg_command()'s
        # fallback (bgm_gain_db=None -> flat 20*log10(bgm_volume) of BGM's
        # own raw level) is the sensible interpretation here.
        bgm_gain_db = None

    command = build_ffmpeg_command(
        video_path,
        subtitle_path,
        bgm_path,
        output_path,
        duration,
        bgm_gain_db=bgm_gain_db,
        orig_volume=orig_volume,
        **kwargs,
    )
    _run(command, deadline=deadline, check=True)
    return output_path
