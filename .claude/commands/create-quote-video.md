---
description: 원본 실사 영상 + 컷별 자막 대본 + BGM으로 최종 명언/릴스 영상을 만든다.
---

# /createvideo

## 사용법

```
/createvideo --video <원본영상경로> --caption <자막대본.md> [--bgm <BGM경로>] --output <출력경로.mp4>
```

- `--bgm` 생략 시 `assets/bgm/default.mp3` 사용.
- 자막 대본이 아직 없다면 먼저 `quote-writer-agent`로 작성한다.

## 파이프라인 흐름

```
원본 실사 영상(현장음 포함, 컷당 2초)
        +
컷별 자막 대본(assets/caption/*.md, 컷 1개=자막 1줄=1초)
        │
        ▼
  generate-subtitle 스킬 → SRT (타임스탬프는 규칙 기반 자동 계산, STT 없음)
        │
        ▼
  compose-video 스킬 → 자막 번인 + BGM 20% 믹싱 + 0.5초 페이드 인/아웃
        │
        ▼
   최종 MP4 (1920x1080, 30fps)
```

이미지 생성(Gemini)이나 TTS 나레이션 단계는 없다 — 영상 소스는 처음부터 실사 촬영본이다.

## 실행 절차

1. `quote-video-agent`를 호출해 `--video`, `--caption`, `--bgm`, `--output`을 그대로 전달한다.
2. 에이전트가 `generate-subtitle` → `compose-video` 순으로 스킬을 실행한다.
3. 완료되면 출력 MP4 경로와 러닝타임을 보고한다. 실패하면 어느 스킬에서 실패했는지와 원인을 보고한다.

## 옵션

| 옵션 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `--video` | O | - | 컷당 2초로 편집된 원본 실사 영상 |
| `--caption` | O | - | 컷별 자막 대본 (`assets/caption/*.md`) |
| `--bgm` | X | `assets/bgm/default.mp3` | 20% 볼륨으로 믹싱할 BGM |
| `--output` | O | - | 최종 MP4 저장 경로 |

## CLI로 직접 실행하기 (에이전트 없이)

```bash
python -m src.quote_video.pipeline \
  --video assets/videos/명품대게.mp4 \
  --caption assets/caption/자막.md \
  --bgm assets/bgm/default.mp3 \
  --output output/result.mp4
```
