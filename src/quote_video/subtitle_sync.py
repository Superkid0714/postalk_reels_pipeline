"""Turns a hand-written per-cut caption script into a timed SRT file.

No speech recognition involved: timestamps are derived purely from cut
order using the fixed rule in `config` (CAPTION_DURATION per line). The
script format is the one used in assets/caption/*.md:

    ## [제1문장]
    * **1컷:** some text
    * **2컷:** more text
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config

_CUT_LINE_RE = re.compile(r"\*\*(\d+)컷:\*\*\s*(.+?)\s*$")


@dataclass(frozen=True)
class CaptionLine:
    cut_number: int
    text: str


@dataclass(frozen=True)
class CaptionTiming:
    line: CaptionLine
    start: float  # seconds
    end: float  # seconds


def parse_caption_script(path: Path) -> list[CaptionLine]:
    """Extract ordered caption lines from a `N컷: text` markdown script."""
    lines: list[CaptionLine] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        match = _CUT_LINE_RE.search(raw_line)
        if not match:
            continue
        cut_number, text = match.groups()
        lines.append(CaptionLine(cut_number=int(cut_number), text=text))

    if not lines:
        raise ValueError(f"No caption lines found in {path}")

    expected = list(range(1, len(lines) + 1))
    actual = [line.cut_number for line in lines]
    if actual != expected:
        raise ValueError(
            f"Caption cut numbers are not sequential from 1 in {path}: got {actual}"
        )
    return lines


def compute_timings(
    lines: list[CaptionLine], caption_duration: float = config.CAPTION_DURATION
) -> list[CaptionTiming]:
    """Assign each caption line a [start, end) window, in file order."""
    return [
        CaptionTiming(line=line, start=i * caption_duration, end=(i + 1) * caption_duration)
        for i, line in enumerate(lines)
    ]


def total_video_duration(lines: list[CaptionLine]) -> float:
    """Expected source-video length implied by the caption/cut timing rule."""
    if len(lines) % config.CAPTIONS_PER_CUT != 0:
        raise ValueError(
            f"{len(lines)} caption lines does not divide evenly into "
            f"{config.CAPTIONS_PER_CUT} lines/cut"
        )
    num_cuts = len(lines) // config.CAPTIONS_PER_CUT
    return num_cuts * config.CUT_DURATION


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder_ms = divmod(total_ms, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    secs, millis = divmod(remainder_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_srt(timings: list[CaptionTiming]) -> str:
    blocks = []
    for i, timing in enumerate(timings, start=1):
        blocks.append(
            f"{i}\n"
            f"{_format_srt_timestamp(timing.start)} --> {_format_srt_timestamp(timing.end)}\n"
            f"{timing.line.text}\n"
        )
    return "\n".join(blocks) + "\n"


def generate_srt(caption_script_path: Path, output_srt_path: Path) -> Path:
    lines = parse_caption_script(caption_script_path)
    timings = compute_timings(lines)
    srt_content = build_srt(timings)
    output_srt_path = Path(output_srt_path)
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    output_srt_path.write_text(srt_content, encoding="utf-8")
    return output_srt_path
