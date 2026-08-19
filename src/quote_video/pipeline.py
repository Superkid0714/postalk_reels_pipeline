"""Orchestrates the quote-video pipeline end to end:

    caption script -> SRT (subtitle_sync) -> composed MP4 (video_composer)

There is no image-generation or TTS stage; `video_path` must already be
real footage edited to fixed-length cuts (see config.CUT_DURATION).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .subtitle_sync import generate_srt, parse_caption_script, total_video_duration
from .video_composer import compose_video


def run_pipeline(
    video_path: Path,
    caption_script_path: Path,
    bgm_path: Path,
    output_path: Path,
    *,
    build_dir: Path | None = None,
) -> Path:
    video_path = Path(video_path)
    caption_script_path = Path(caption_script_path)
    bgm_path = Path(bgm_path)
    output_path = Path(output_path)
    build_dir = Path(build_dir) if build_dir else output_path.parent / "_build"

    lines = parse_caption_script(caption_script_path)
    expected_duration = total_video_duration(lines)

    srt_path = build_dir / f"{output_path.stem}.srt"
    generate_srt(caption_script_path, srt_path)

    return compose_video(
        video_path=video_path,
        srt_path=srt_path,
        bgm_path=bgm_path,
        output_path=output_path,
        duration=expected_duration,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the quote-video pipeline.")
    parser.add_argument("--video", type=Path, required=True, help="Source footage (already cut-edited).")
    parser.add_argument("--caption", type=Path, required=True, help="Per-cut caption script (markdown).")
    parser.add_argument("--bgm", type=Path, default=None, help="BGM file (default: config.BGM_DIR/default.mp3).")
    parser.add_argument("--output", type=Path, required=True, help="Output MP4 path.")
    args = parser.parse_args()

    bgm_path = args.bgm or (config.BGM_DIR / "default.mp3")
    output_path = run_pipeline(args.video, args.caption, bgm_path, args.output)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
