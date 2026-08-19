"""Turns a hand-written per-cut caption script into a timed SRT file.

No speech recognition involved: timestamps are derived purely from line
order using the fixed rule in `config` (CAPTION_DURATION per line) —
*not* from any timestamps that happen to be written in the script itself
(see `_CAPTION_LINE_RE` below). Two script formats are accepted:

    ## [제1문장]                                  (older format)
    * **1컷:** some text
    * **2컷:** more text

    ## [비디오 컷 1] (00:00 ~ 00:02)                (current format)
    * **[00:00 ~ 00:01] 자막 1:** some text
    * **[00:01 ~ 00:02] 자막 2:** more text

In both, only the number immediately before the final `:**` is read (as
the caption's 1-based sequence number); any `[bracketed timestamp]` or
`자막`/`컷` label text around it is decorative and ignored — if it
disagrees with the CAPTION_DURATION-per-line rule, the rule wins, since
that's what actually drives the burned-in .ass timing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config

# Matches "**1컷:** text" and "**[00:00 ~ 00:01] 자막 1:** text" alike:
# `[^*]*?` lazily eats any label/bracket text so the digits captured are
# always the ones immediately before the closing `:**`.
_CAPTION_LINE_RE = re.compile(r"\*\*[^*]*?(\d+)(?:컷)?:\*\*\s*(.+?)\s*$")

# Caption text itself can carry inline emphasis (e.g. "상호명 **명품대게**를
# 꼭 방문해 보세요!") that isn't meant to reach the rendered subtitle.
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_UNDERSCORE_BOLD_RE = re.compile(r"__(.+?)__")
_MD_BACKTICK_RE = re.compile(r"`(.+?)`")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_LEFTOVER_RE = re.compile(r"[*_`]")


def _strip_markdown(text: str) -> str:
    """Drop markdown emphasis markup, keeping only the plain caption text."""
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_UNDERSCORE_BOLD_RE.sub(r"\1", text)
    text = _MD_BACKTICK_RE.sub(r"\1", text)
    text = _MD_ITALIC_RE.sub(r"\1", text)
    text = _MD_LEFTOVER_RE.sub("", text)
    return text.strip()


@dataclass(frozen=True)
class CaptionLine:
    sequence_number: int  # 1-based caption order, e.g. "자막 N" / "N컷" — not the video cut number
    text: str


@dataclass(frozen=True)
class CaptionTiming:
    line: CaptionLine
    start: float  # seconds
    end: float  # seconds


def parse_caption_script(path: Path) -> list[CaptionLine]:
    """Extract ordered caption lines from a `**...N...:** text` markdown
    script (see module docstring for the two accepted label formats)."""
    lines: list[CaptionLine] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        match = _CAPTION_LINE_RE.search(raw_line)
        if not match:
            continue
        sequence_number, text = match.groups()
        lines.append(CaptionLine(sequence_number=int(sequence_number), text=_strip_markdown(text)))

    if not lines:
        raise ValueError(f"No caption lines found in {path}")

    expected = list(range(1, len(lines) + 1))
    actual = [line.sequence_number for line in lines]
    if actual != expected:
        raise ValueError(
            f"Caption sequence numbers are not sequential from 1 in {path}: got {actual}"
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


def _format_ass_timestamp(seconds: float) -> str:
    total_cs = round(seconds * 100)
    hours, remainder_cs = divmod(total_cs, 360_000)
    minutes, remainder_cs = divmod(remainder_cs, 6_000)
    secs, centis = divmod(remainder_cs, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _escape_ass_text(text: str) -> str:
    # `{`/`}` open/close ASS override tags; a stray one in caption text
    # would otherwise be interpreted as (broken) styling markup.
    return text.replace("{", "(").replace("}", ")")


def build_ass(
    timings: list[CaptionTiming],
    *,
    width: int = config.VIDEO_WIDTH,
    height: int = config.VIDEO_HEIGHT,
    font_name: str = config.SUBTITLE_FONT_NAME,
    margin_v: int = config.SUBTITLE_MARGIN_V,
) -> str:
    """Render timed captions as a minimal .ass script with an explicit
    PlayResX/PlayResY matching the real output canvas.

    Burning in a plain .srt via ffmpeg's `subtitles` filter has libass
    silently assume the legacy 384x288 default script resolution and scale
    MarginV (and other numeric style values) against *that* instead of the
    actual frame size — on a 1080x1920 canvas that inflates a MarginV of
    220 to ~1467px, pushing captions almost to the top of the frame. An
    .ass file with a correct PlayResX/PlayResY header sidesteps the
    guesswork entirely, so positions/margins apply at the intended pixel
    scale."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"0,0,0,0,100,100,0,0,1,2,0,2,40,40,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = "\n".join(
        f"Dialogue: 0,{_format_ass_timestamp(t.start)},{_format_ass_timestamp(t.end)},"
        f"Default,,0,0,0,,{_escape_ass_text(t.line.text)}"
        for t in timings
    )
    return header + events + "\n"


def generate_ass(
    caption_script_path: Path,
    output_ass_path: Path,
    *,
    caption_duration: float = config.CAPTION_DURATION,
    **kwargs,
) -> Path:
    lines = parse_caption_script(caption_script_path)
    timings = compute_timings(lines, caption_duration=caption_duration)
    ass_content = build_ass(timings, **kwargs)
    output_ass_path = Path(output_ass_path)
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    output_ass_path.write_text(ass_content, encoding="utf-8")
    return output_ass_path


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
