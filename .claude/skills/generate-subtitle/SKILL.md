---
name: generate-subtitle
description: 손으로 작성한 컷별 자막 대본(assets/caption/*.md)을 읽어 타임스탬프가 찍힌 .ass 파일을 자동 생성합니다. 음성 인식(STT)은 쓰지 않고, "영상 한 컷 = 2초, 자막 한 줄 = 1초" 규칙으로 순서대로 시간을 배분하며, 대본 텍스트에 섞인 마크다운(**, *, `, __)은 렌더링 전에 제거합니다. 원본 실사 영상에 자막을 입힐 준비가 필요할 때 사용하세요.
allowed-tools:
  - Bash
  - Read
  - Write
---

# Generate Subtitle

## Instructions

1. 대본 파일은 `* **M컷:** 텍스트` 또는 `* **[00:00 ~ 00:01] 자막 M:** 텍스트` 형식의 줄들로 구성되어야 하며 (둘 다 지원, 실제 `assets/caption/*.md`는 현재 후자 형식 사용), 각 줄의 번호(M)는 1부터 끊김 없이 이어져야 한다. `**...:**` 안에 대괄호 타임스탬프나 `자막`/`컷` 라벨이 섞여 있어도 되고, 마지막 `:**` 바로 앞 숫자만 읽는다.
2. **대본에 적힌 `[00:00 ~ 00:01]` 같은 타임스탬프는 파싱만 될 뿐 실제로 쓰이지 않는다.** 실제 타이밍은 항상 `sequence_number × CAPTION_DURATION` 규칙으로 계산된다. 지금 대본은 이 규칙과 일치하게 적혀있지만, 나중에 누가 특정 줄만 다르게 타임스탬프를 고쳐도 조용히 무시된다 — 줄 단위로 직접 타이밍을 반영해야 한다면 이건 별도 설계 변경이 필요하니 먼저 확인해야 한다.
3. 번호가 순서대로가 아니거나 파일에 자막 줄이 하나도 없으면 에러를 낸다 — 자동으로 보정하지 않는다.
4. 각 자막 줄 텍스트에서 마크다운 강조 기호(`**bold**`, `__bold__`, `` `code` ``, `*italic*`, 잔여 `*`/`_`/`` ` ``)를 제거한 뒤 저장한다 — `**N컷:**` 라벨뿐 아니라 텍스트 본문 안에 섞인 마크다운도 대상이다 (예: `상호명 **명품대게**를 꼭 방문해 보세요!` → `상호명 명품대게를 꼭 방문해 보세요!`).
5. 각 자막 줄에는 `CAPTION_DURATION`(1초)씩 순서대로 시간을 배분한다. Whisper나 다른 STT를 호출하지 않는다.
6. 총 자막 줄 수는 `CAPTIONS_PER_CUT`(2)로 나누어떨어져야 한다 — 그래야 실제 영상 컷 수와 맞아떨어진다. 나누어떨어지지 않으면 대본을 먼저 고치라고 알려준다.
7. **.srt가 아니라 .ass로 생성한다.** ffmpeg의 `subtitles` 필터에 순수 .srt를 넘기면 libass가 스크립트 해상도를 384x288(레거시 기본값)로 가정해 `MarginV`를 실제 프레임보다 훨씬 크게(1080x1920 기준 약 6.67배) 스케일링해버려서, 자막이 하단이 아니라 화면 위쪽 근처에 렌더링되는 문제가 있었다. `.ass`에 `PlayResX`/`PlayResY`를 실제 해상도로 명시하면 이 문제가 사라진다.

## Usage

```python
from src.quote_video.subtitle_sync import generate_ass

generate_ass(
    caption_script_path="assets/caption/자막.md",
    output_ass_path="_build/명품대게.ass",
)
```

## Config

| 항목 | 값 |
|------|-----|
| 자막 한 줄 길이 | `config.CAPTION_DURATION` = 1.0초 |
| 영상 한 컷 길이 | `config.CUT_DURATION` = 2.0초 |
| 컷당 자막 줄 수 | `config.CAPTIONS_PER_CUT` = 2 |
| 하단 마진 | `config.SUBTITLE_MARGIN_V` = 220px |
| STT 엔진 | 없음 (수동 타임스탬프 규칙만 사용) |

## Features

1. **parse_caption_script**: 대본 마크다운에서 컷 번호+텍스트를 순서대로 추출, 마크다운 제거, 누락/순서 오류 검증
2. **compute_timings**: 규칙 기반으로 각 줄의 start/end 시각 계산
3. **total_video_duration**: 자막 줄 수로부터 기대되는 원본 영상 길이 역산 (컷 수 검증용)
4. **generate_ass**: 위 과정을 묶어 `PlayResX`/`PlayResY`가 실제 해상도로 명시된 .ass 파일로 저장
