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

# Video spec. Portrait 1080x1920 (reels/shorts) — the actual source clips in
# assets/videos/ are all portrait, not the 1920x1080 landscape the original
# prompt.md plan assumed; confirm with the user before reverting to landscape.
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
FADE_DURATION = 0.5  # seconds, in and out

# Caption/cut timing rule (confirmed with user 2026-08-20):
# each source video cut is a fixed 2s, each caption line is shown for 1s,
# so every cut carries exactly two caption lines in sequence.
CUT_DURATION = 2.0  # seconds per source video cut
CAPTION_DURATION = 1.0  # seconds per caption line
CAPTIONS_PER_CUT = int(CUT_DURATION / CAPTION_DURATION)

# SUBTITLE_FONT_NAME must be the font's internal family name (what
# libass/fontconfig actually matches against), not its filename — checked
# via fontTools: `TTFont("assets/font/Griun_Fromsol-Rg.ttf")["name"]`
# reports the family name as "Griun Fromsol" (nameID 1/16), not
# "Griun_Fromsol-Rg". Getting this wrong doesn't error, it just silently
# falls back to a default system font — always verify with fontTools
# before setting this, don't guess from the filename.
SUBTITLE_FONT_NAME = "Griun Fromsol"
SUBTITLE_FONT_FILE = FONT_DIR / "Griun_Fromsol-Rg.ttf"

# BGM is mixed under the original on-site audio, not replacing it.
BGM_VOLUME = 0.70

# On-site audio was drowning out BGM even after BGM was calibrated relative
# to it (2026-08-20 feedback); turn the on-site track down a bit so BGM has
# room. Linear multiplier applied directly to the source audio.
ORIGINAL_VOLUME = 0

# Vertical margin (px) libass keeps between the caption baseline and the
# bottom edge, on the 1080x1920 canvas. Raised from libass's default (~small)
# so captions clear Instagram Reels' own bottom UI (caption/username/music
# sticker strip). Tune this if it still overlaps or sits too high.
SUBTITLE_MARGIN_V = 440

# libx264 encoding speed/quality tradeoff. "medium" (libx264's own default)
# is noticeably slower than "veryfast" for barely-perceptible quality gain
# at these short reels durations/bitrates — needed headroom to keep the
# whole pipeline under PIPELINE_TIMEOUT_SECONDS regardless of input
# (2026-08-20 feedback: "20초 안에 끝나도록").
FFMPEG_PRESET = "veryfast"

# Wall-clock budget (seconds) for one run_pipeline() call — clip
# preprocessing/concat + subtitle generation + compose, combined. This is
# enforced as a hard subprocess timeout, not a performance promise: encode
# time still scales with total output duration (more/longer cuts = more
# work), so this can't guarantee every possible input finishes in time —
# what it guarantees is that the pipeline fails fast with a clear
# PipelineTimeoutError instead of silently running past the deadline.
PIPELINE_TIMEOUT_SECONDS = 20.0
