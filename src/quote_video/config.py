"""Shared configuration for the quote-video pipeline.

Pipeline: real footage (with on-site audio) + a hand-written per-cut caption
script -> auto-timed SRT -> ffmpeg compose (burn captions, mix in BGM, fade
in/out) -> final MP4. There is no image-generation or TTS/STT stage: the
source video is already real footage edited to fixed-length cuts, and its
own audio is kept.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ASSETS_DIR = REPO_ROOT / "assets"
FONT_DIR = ASSETS_DIR / "font"
BGM_DIR = ASSETS_DIR / "bgm"
VIDEO_DIR = ASSETS_DIR / "videos"
CAPTION_DIR = ASSETS_DIR / "caption"

# Video spec
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30
FADE_DURATION = 0.5  # seconds, in and out

# Caption/cut timing rule (confirmed with user 2026-08-20):
# each source video cut is a fixed 2s, each caption line is shown for 1s,
# so every cut carries exactly two caption lines in sequence.
CUT_DURATION = 2.0  # seconds per source video cut
CAPTION_DURATION = 1.0  # seconds per caption line
CAPTIONS_PER_CUT = int(CUT_DURATION / CAPTION_DURATION)

SUBTITLE_FONT_NAME = "KOTRA_SONGEULSSI"
SUBTITLE_FONT_FILE = FONT_DIR / "KOTRA_SONGEULSSI.ttf"

# BGM is mixed under the original on-site audio, not replacing it.
BGM_VOLUME = 0.20
