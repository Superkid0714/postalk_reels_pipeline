"""Composes the final MP4 with ffmpeg: burns in captions, mixes BGM under
the original on-site audio, and applies fade in/out. No image or TTS
generation happens here — `video_path` is already-edited real footage.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import config


def _escape_filter_path(path: Path) -> str:
    """Escape a filesystem path for use inside an ffmpeg filtergraph value.

    ffmpeg's filter parser treats ':' as an option separator, which collides
    with Windows drive letters (C:\\...), so it must be backslash-escaped.
    """
    posix_path = str(Path(path).resolve()).replace("\\", "/")
    return posix_path.replace(":", "\\:")


def probe_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def build_ffmpeg_command(
    video_path: Path,
    srt_path: Path,
    bgm_path: Path,
    output_path: Path,
    duration: float,
    *,
    bgm_volume: float = config.BGM_VOLUME,
    fade_duration: float = config.FADE_DURATION,
    font_dir: Path = config.FONT_DIR,
    font_name: str = config.SUBTITLE_FONT_NAME,
    width: int = config.VIDEO_WIDTH,
    height: int = config.VIDEO_HEIGHT,
    fps: int = config.FPS,
) -> list[str]:
    """Build the ffmpeg argv for the compose step. Pure/testable: does not
    touch the filesystem or require ffmpeg to be installed."""
    fade_out_start = max(duration - fade_duration, 0.0)
    srt_arg = _escape_filter_path(srt_path)
    fontsdir_arg = _escape_filter_path(font_dir)

    filter_complex = (
        f"[0:a]volume=1.0[a_orig];"
        f"[1:a]volume={bgm_volume},aloop=loop=-1:size=2147483647[a_bgm];"
        f"[a_orig][a_bgm]amix=inputs=2:duration=first:dropout_transition=0[aout];"
        f"[0:v]subtitles='{srt_arg}':fontsdir='{fontsdir_arg}':"
        f"force_style='FontName={font_name}',"
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
        "-r", str(fps),
        "-s", f"{width}x{height}",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]


def compose_video(
    video_path: Path,
    srt_path: Path,
    bgm_path: Path,
    output_path: Path,
    *,
    duration: float | None = None,
    **kwargs,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if duration is None:
        duration = probe_duration(video_path)
    command = build_ffmpeg_command(video_path, srt_path, bgm_path, output_path, duration, **kwargs)
    subprocess.run(command, check=True)
    return output_path
