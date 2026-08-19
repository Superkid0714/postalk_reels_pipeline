# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repo (`youtube_longform_agent`) contains the actual application code, built from the plan in `quote-video-prompt/`. `quote-video-prompt/` is **its own separate git repository** (remote: `github.com/uxjoseph/quote-video-prompt`), not a submodule — it shows up as untracked in the outer repo's git status. Do not try to commit inside it as part of the outer repo's history, and do not assume `git log`/`git diff` at the top level will show its history.

**`quote-video-prompt/prompt.md` and `README.md` describe an earlier plan that no longer matches what's built here** — the user explicitly dropped the image-generation and TTS/STT stages (2026-08-20) in favor of using real footage directly. Treat those two files as historical/superseded context, not as the current spec. The real spec is this file plus the code itself.

## Actual pipeline (as built, superseding the original prompt.md plan)

```
real footage (already cut-edited, on-site audio kept) + hand-written per-cut caption script
        → generate-subtitle (rule-based timestamps, no STT) → SRT
        → compose-video (ffmpeg: burn SRT, mix in BGM, fade in/out) → final MP4
```

There is **no image generation and no TTS/STT** in this system — `video_path` is always real, already-edited footage; Gemini image gen, Gemini TTS, and Whisper were all cut from the original plan. Do not reintroduce them without asking the user first.

### The caption/cut timing rule

This is the load-bearing design decision (confirmed with the user, not guessed):
- Source video cuts are a fixed `CUT_DURATION` = 2.0s each.
- Each caption line in the script is shown for a fixed `CAPTION_DURATION` = 1.0s.
- So every video cut carries exactly `CAPTIONS_PER_CUT` = 2 caption lines in sequence.
- Timestamps are computed purely from line order (line *i* → `[i·1s, (i+1)·1s)`) — no speech recognition, no manual per-line timestamp entry. `subtitle_sync.total_video_duration()` raises if the caption count doesn't divide evenly by 2, since that means it can't line up with real 2s cuts.

All three constants live in `src/quote_video/config.py` — change them there, not inline, if the rule ever changes.

### Caption script format

Parsed by `subtitle_sync.parse_caption_script()`. Cut numbers must be sequential starting at 1 across the whole file (sentence groupings under `## [제N문장]` headers are for human readability only and aren't parsed):

```markdown
## [제1문장]
* **1컷:** text
* **2컷:** text
```

`tests/fixtures/sample_caption.md` (copied from `quote-video-prompt/assets/caption/명품대게_릴스_자막.md`) is a real 16-line example used by the test suite.

## Layout

- `src/quote_video/` — `config.py` (all tunables), `subtitle_sync.py` (parse script → SRT), `video_composer.py` (ffmpeg compose), `pipeline.py` (orchestrates the two + CLI entry point). No `image_generator.py` / `tts_generator.py` — intentionally absent.
- `.claude/skills/{generate-subtitle,compose-video}/SKILL.md` — one skill per pipeline stage.
- `.claude/agents/quote-video-agent.md` (orchestrator) and `quote-writer-agent.md` (writes new caption scripts into `assets/caption/`).
- `.claude/commands/create-quote-video.md` — the `/createvideo` command.
- `assets/font/`, `assets/bgm/`, `assets/videos/`, `assets/caption/` — currently empty placeholders (`.gitkeep`) except the test fixture; real assets need to be supplied before an end-to-end render will work.

## Commands

```bash
python -m unittest discover -s tests -v   # run tests (stdlib unittest, no pytest installed)
python -m src.quote_video.pipeline --video <path> --caption <path.md> [--bgm <path>] --output <path.mp4>
```

`video_composer` shells out to `ffmpeg`/`ffprobe`; neither is installed in this dev environment, so `compose_video()` / `probe_duration()` can't be exercised end-to-end here — only `build_ffmpeg_command()` (pure, no subprocess) is covered by tests. Verify actual rendering on a machine with ffmpeg installed before considering the compose step done.

## Fixed config values (current, in `config.py`)

- Video: 1920x1080, 30fps, 0.5s fade in/out.
- Subtitle font: `KOTRA_SONGEULSSI` (handwriting-style) — font file itself is not yet present in `assets/font/`.
- BGM volume: 20% (`BGM_VOLUME`), mixed under the original on-site audio via `amix`, not replacing it.
- Image style (`Notion-style minimal illustration`) and TTS voice values from the original plan are now moot — no image-gen or TTS stage exists to consume them.
