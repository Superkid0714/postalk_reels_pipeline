---
name: generate-subtitle
description: 손으로 작성한 컷별 자막 대본(assets/caption/*.md)을 읽어 타임스탬프가 찍힌 SRT 파일을 자동 생성합니다. 음성 인식(STT)은 쓰지 않고, "영상 한 컷 = 2초, 자막 한 줄 = 1초" 규칙으로 순서대로 시간을 배분합니다. 원본 실사 영상에 자막을 입힐 준비가 필요할 때 사용하세요.
allowed-tools:
  - Bash
  - Read
  - Write
---

# Generate Subtitle

## Instructions

1. 대본 파일은 `## [제N문장]` 아래에 `* **M컷:** 텍스트` 형식의 줄들로 구성되어야 하며, 컷 번호는 1부터 끊김 없이 이어져야 한다.
2. 컷 번호가 순서대로가 아니거나 파일에 자막 줄이 하나도 없으면 에러를 낸다 — 자동으로 보정하지 않는다.
3. 각 자막 줄에는 `CAPTION_DURATION`(1초)씩 순서대로 시간을 배분한다. Whisper나 다른 STT를 호출하지 않는다.
4. 총 자막 줄 수는 `CAPTIONS_PER_CUT`(2)로 나누어떨어져야 한다 — 그래야 실제 영상 컷 수와 맞아떨어진다. 나누어떨어지지 않으면 대본을 먼저 고치라고 알려준다.

## Usage

```python
from src.quote_video.subtitle_sync import generate_srt

generate_srt(
    caption_script_path="assets/caption/명품대게_릴스_자막.md",
    output_srt_path="_build/명품대게.srt",
)
```

## Config

| 항목 | 값 |
|------|-----|
| 자막 한 줄 길이 | `config.CAPTION_DURATION` = 1.0초 |
| 영상 한 컷 길이 | `config.CUT_DURATION` = 2.0초 |
| 컷당 자막 줄 수 | `config.CAPTIONS_PER_CUT` = 2 |
| STT 엔진 | 없음 (수동 타임스탬프 규칙만 사용) |

## Features

1. **parse_caption_script**: 대본 마크다운에서 컷 번호+텍스트를 순서대로 추출, 누락/순서 오류 검증
2. **compute_timings**: 규칙 기반으로 각 줄의 start/end 시각 계산
3. **total_video_duration**: 자막 줄 수로부터 기대되는 원본 영상 길이 역산 (컷 수 검증용)
4. **generate_srt**: 위 과정을 묶어 SRT 파일로 저장
