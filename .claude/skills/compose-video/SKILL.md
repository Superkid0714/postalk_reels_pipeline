---
name: compose-video
description: 원본 실사 영상(현장음 포함)에 .ass 자막을 번인하고, 현장음 대비 상대 음량으로 BGM을 믹싱하며, 0.5초 페이드 인/아웃을 적용해 최종 MP4를 ffmpeg로 합성합니다. 이미지 생성이나 TTS 나레이션은 다루지 않습니다 — 입력 영상은 이미 컷 편집이 끝난 실사 소스여야 합니다. 명언/릴스 영상을 최종 출력물로 뽑아야 할 때 사용하세요.
allowed-tools:
  - Bash
  - Read
  - Write
---

# Compose Video

## Instructions

1. 입력 영상(`video_path`)은 이미 컷당 2초로 편집된 실사 촬영본이어야 한다. 이 스킬은 컷을 자르거나 이어붙이지 않는다.
2. 원본 현장음은 `ORIGINAL_VOLUME`(70%)로 살짝 낮추고, BGM 트랙을 믹싱한다. TTS 음성은 생성하지도, 섞지도 않는다.
3. **BGM 볼륨은 BGM 자체 음량이 아니라 현장음 대비 상대 음량으로 계산한다.** `compose_video()`가 `probe_mean_volume_db()`로 두 트랙의 실측 음량을 잰 뒤 `compute_bgm_gain_db()`로 "BGM이 (낮춰진) 현장음 대비 `BGM_VOLUME`(20%) 수준"이 되도록 실제 dB 게인을 역산한다. 그냥 `volume=0.2`만 걸면 시끄러운 현장음(예: 시장 소음)에 묻혀 BGM이 사실상 안 들릴 수 있다 — 실제로 겪은 문제였다.
4. `amix`는 `normalize=0`으로 실행한다 (기본 정규화가 위에서 계산한 상대 음량 비율을 다시 깨뜨리기 때문). 대신 `alimiter`로 클리핑을 방지한다.
5. `generate-subtitle`이 만든 .ass를 자막으로 번인한다 (`Jayeon Sans Medium`, 하단 마진 `SUBTITLE_MARGIN_V`=220px — 인스타그램 릴스 하단 UI를 피하기 위해 조정됨). **.srt가 아니라 .ass여야 한다** — .srt는 libass가 스크립트 해상도를 잘못 가정해서 자막이 화면 위쪽에 렌더링되는 버그가 있었다.
6. 영상 시작 0.5초, 끝 0.5초에 페이드 인/아웃을 건다. 끝 페이드 시작 시각은 `duration - FADE_DURATION`으로 계산한다.
7. 출력은 1080x1920(세로, 릴스/쇼츠), 30fps, H.264/AAC로 인코딩한다.
8. ffmpeg가 설치되어 있지 않으면 관련 함수가 실패한다 — 설치 여부를 먼저 확인하라고 안내한다.

## Usage

```python
from src.quote_video.video_composer import compose_video

compose_video(
    video_path="output/_build/assembled_source.mp4",
    subtitle_path="_build/명품대게.ass",
    bgm_path="assets/bgm/default.mp3",
    output_path="output/명품대게_final.mp4",
)
```

## Config

| 항목 | 값 |
|------|-----|
| 해상도 | 1080x1920 (세로) |
| FPS | 30 |
| 페이드 인/아웃 | 0.5초 |
| 원본 현장음 볼륨 | 70% (`config.ORIGINAL_VOLUME`) |
| BGM 볼륨 | 현장음(감쇠 후) 대비 20% (`config.BGM_VOLUME`) — BGM 자체 음량 기준 아님 |
| 자막 폰트 | `Jayeon Sans Medium` (`assets/font/JayeonSans-Medium.ttf`) |
| 자막 하단 마진 | `config.SUBTITLE_MARGIN_V` = 220px |
| 원본 현장음 | 유지 (TTS로 대체하지 않음) |

## Features

1. **probe_duration**: ffprobe로 원본 영상 길이 조회 (자막 대본에서 역산한 길이와 다를 수 있어 명시적으로 넘길 수도 있음)
2. **probe_mean_volume_db** / **compute_bgm_gain_db**: 현장음·BGM 실측 음량을 재서 BGM이 현장음 대비 원하는 상대 음량이 되도록 실제 dB 게인을 계산
3. **build_ffmpeg_command**: subtitles(.ass)/BGM 믹스(normalize=0 + alimiter)/fade 필터그래프를 구성하는 순수 함수 (ffmpeg 미설치 환경에서도 단위 테스트 가능)
4. **compose_video**: 음량 계산 + 명령 구성까지 묶어 실제로 ffmpeg를 실행하고 출력 파일 경로를 반환
