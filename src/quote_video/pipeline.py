"""Orchestrates the quote-video pipeline end to end:

    caption script -> .ass (subtitle_sync) -> composed MP4 (video_composer)

There is no image-generation or TTS stage; `video_path` must already be
real footage edited to fixed-length cuts (see config.CUT_DURATION).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import config
from .subtitle_sync import generate_ass, parse_caption_script, total_video_duration
from .video_composer import assemble_cuts_video, compose_video


def _resolve_video_path(video_path: Path, build_dir: Path, *, deadline: float | None = None) -> Path:
    """If `video_path` is a directory of raw per-cut clips (e.g. assets/videos/
    with 1.mp4, 2.mp4, ...), normalize and concatenate them into one source
    video first. If it's already a single file, use it as-is."""
    if video_path.is_dir():
        clips = sorted(video_path.glob("*.mp4"), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
        if not clips:
            raise ValueError(f"No .mp4 clips found in {video_path}")
        return assemble_cuts_video(clips, build_dir / "assembled_source.mp4", deadline=deadline)
    return video_path


def run_pipeline(
    video_path: Path,
    caption_script_path: Path,
    bgm_path: Path,
    output_path: Path,
    *,
    build_dir: Path | None = None,
    timeout_seconds: float | None = config.PIPELINE_TIMEOUT_SECONDS,
) -> Path:
    """Run the full pipeline: preprocess/concat `video_path` if it's a
    directory of raw cuts, turn the caption script into a time-ordered
    .ass, then compose the final MP4.

    `timeout_seconds` is a wall-clock budget for the whole call (clip
    preprocessing + compose combined) — pass None to disable. It's an
    upper bound enforced via subprocess timeouts, not a performance
    guarantee: a much longer/heavier input will still fail (with
    `PipelineTimeoutError`) rather than magically finishing in time, since
    encode cost scales with total output duration."""
    video_path = Path(video_path)
    caption_script_path = Path(caption_script_path)
    bgm_path = Path(bgm_path)
    output_path = Path(output_path)
    build_dir = Path(build_dir) if build_dir else output_path.parent / "_build"
    deadline = time.monotonic() + timeout_seconds if timeout_seconds else None

    lines = parse_caption_script(caption_script_path)
    expected_duration = total_video_duration(lines)

    resolved_video_path = _resolve_video_path(video_path, build_dir, deadline=deadline)

    subtitle_path = build_dir / f"{output_path.stem}.ass"
    generate_ass(caption_script_path, subtitle_path)  # pure-Python parsing, negligible — no deadline needed

    return compose_video(
        video_path=resolved_video_path,
        subtitle_path=subtitle_path,
        bgm_path=bgm_path,
        output_path=output_path,
        duration=expected_duration,
        deadline=deadline,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the quote-video pipeline.")
    parser.add_argument("--video", type=Path, required=True, help="Source footage (already cut-edited).")
    parser.add_argument("--caption", type=Path, required=True, help="Per-cut caption script (markdown).")
    parser.add_argument("--bgm", type=Path, default=None, help="BGM file (default: config.BGM_DIR/default.mp3).")
    parser.add_argument("--output", type=Path, required=True, help="Output MP4 path.")
    parser.add_argument(
        "--timeout", type=float, default=config.PIPELINE_TIMEOUT_SECONDS,
        help=f"Wall-clock budget in seconds, 0 to disable (default: {config.PIPELINE_TIMEOUT_SECONDS}).",
    )
    args = parser.parse_args()

    bgm_path = args.bgm or (config.BGM_DIR / "default.mp3")
    output_path = run_pipeline(
        args.video, args.caption, bgm_path, args.output,
        timeout_seconds=args.timeout or None,
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
