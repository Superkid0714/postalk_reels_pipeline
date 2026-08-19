---
name: compose-video
description: 원본 실사 영상(현장음 포함)에 SRT 자막을 번인하고 BGM을 20% 볼륨으로 믹싱하며 0.5초 페이드 인/아웃을 적용해 최종 MP4를 ffmpeg로 합성합니다. 이미지 생성이나 TTS 나레이션은 다루지 않습니다 — 입력 영상은 이미 컷 편집이 끝난 실사 소스여야 합니다. 명언/릴스 영상을 최종 출력물로 뽑아야 할 때 사용하세요.
allowed-tools:
  - Bash
  - Read
  - Write
---

# Compose Video

## Instructions

1. 입력 영상(`video_path`)은 이미 컷당 2초로 편집된 실사 촬영본이어야 한다. 이 스킬은 컷을 자르거나 이어붙이지 않는다.
2. 원본 현장음은 그대로 유지하고, BGM 트랙을 `BGM_VOLUME`(20%)로 낮춰 믹싱한다. TTS 음성은 생성하지도, 섞지도 않는다.
3. `generate-subtitle`이 만든 SRT를 자막으로 번인한다 (`KOTRA_SONGEULSSI` 손글씨체).
4. 영상 시작 0.5초, 끝 0.5초에 페이드 인/아웃을 건다. 끝 페이드 시작 시각은 `duration - FADE_DURATION`으로 계산한다.
5. 출력은 1920x1080, 30fps, H.264/AAC로 인코딩한다.
6. ffmpeg가 설치되어 있지 않으면 `compose_video`가 `FileNotFoundError`를 낸다 — 설치 여부를 먼저 확인하라고 안내한다.

## Usage

```python
from src.quote_video.video_composer import compose_video

compose_video(
    video_path="assets/videos/명품대게.mp4",
    srt_path="_build/명품대게.srt",
    bgm_path="assets/bgm/default.mp3",
    output_path="output/명품대게_final.mp4",
)
```

## Config

| 항목 | 값 |
|------|-----|
| 해상도 | 1920x1080 |
| FPS | 30 |
| 페이드 인/아웃 | 0.5초 |
| BGM 볼륨 | 20% (`config.BGM_VOLUME`) |
| 자막 폰트 | `KOTRA_SONGEULSSI` (`assets/font/KOTRA_SONGEULSSI.ttf`) |
| 원본 현장음 | 유지 (TTS로 대체하지 않음) |

## Features

1. **probe_duration**: ffprobe로 원본 영상 길이 조회 (자막 대본에서 역산한 길이와 다를 수 있어 명시적으로 넘길 수도 있음)
2. **build_ffmpeg_command**: subtitles/BGM 믹스/fade 필터그래프를 구성하는 순수 함수 (ffmpeg 미설치 환경에서도 단위 테스트 가능)
3. **compose_video**: 명령을 구성해 실제로 ffmpeg를 실행하고 출력 파일 경로를 반환
