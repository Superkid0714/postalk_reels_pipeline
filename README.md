# POSTALK Reels Pipeline

POSTALK 백엔드가 전달한 영상 4·6·8개를 세로형 릴스로 합성하는 내부 서비스입니다. 메뉴 수는 1~3개이며, 각 메뉴에 클로즈업과 상세 장면을 배정합니다. 원본 영상의 소리는 제거하고, AI 자막·전환·배경음악을 적용해 MP4와 썸네일을 만듭니다. 프론트엔드는 이 서비스에 직접 요청하지 않습니다.

현재 백엔드 연동은 `simple`, `christmas` 두 콘셉트를 사용합니다. 릴스 결과는 1080×1920 MP4이며, 메뉴 1·2·3개에 따라 각각 16·20·24초입니다. Supabase Storage 서명 URL로 입력과 출력을 주고받습니다.

가로 원본은 전체를 중앙에 배치하고 위아래에 흐린 배경을 채우며, 세로 원본은 화면을 채웁니다. 배경음악은 콘셉트별 목록에서 작업마다 무작위로 선택합니다. 곡별 출처는 [배경음악 출처](assets/bgm/CREDITS.md)에 정리했습니다.

## 기존 프론트 미리보기 호환

새로 생성하는 릴스는 검은 시작 페이드 없이 실제 첫 장면으로 시작합니다. 기존 프론트가 사용하는 `video src="...mp4#t=0.1"`·`preload="metadata"` 방식에 맞춘 출력입니다. JPG 썸네일은 기존 경로로 계속 제공하며, 장면 전환·종료 페이드·BGM과 재생 길이는 유지합니다. 요청·응답 필드를 추가하지 않습니다. 이미 저장된 MP4 파일에는 소급 적용되지 않습니다.

## 표지와 입력 의미 보존

썸네일은 첫 메뉴 클로즈업 중간 프레임을 우선 선택한 1080×1920 JPEG입니다. 중앙 영역의 평균 밝기가 35/255 미만이면 영상 25%·50%·70% 지점도 확인해 가장 밝은 후보를 고릅니다. 기본 시작 지점은 1초이며 영상 길이에 맞춰 제한합니다. 원본 전체가 어두운 경우 밝기를 보장할 수는 없습니다. 백엔드는 완료된 같은 작업의 썸네일을 Instagram 표지(`cover_url`)로 전달합니다. 기존 결과 필드와 요청 형식은 변하지 않습니다.

설명에 부정·제한 조건, 가상·검증·테스트 콘텐츠 안내가 있으면 LLM의 광고식 바꿔쓰기를 건너뛰고 원문 기반 캡션을 사용합니다(`is_fallback=true`). 캡션은 기존 2200자 제한을 적용합니다. 자막은 글자 수 제한에 맞춘 가게·메뉴 이름이며 방문·시식 유도 문구는 추가하지 않습니다. 일반 입력은 기존 AI 생성 흐름을 사용합니다.

## 실행 환경

| 항목 | 용도 |
| --- | --- |
| `PORT` | FastAPI 포트. 기본 예시는 `8000` |
| `SUPABASE_URL` | 서명 URL의 프로젝트 검증에 사용 |
| `REELS_INTERNAL_API_KEY` | 백엔드와 공유하는 내부 호출 키 |
| `OPENAI_API_KEY` | AI가 장면 자막·게시글 캡션·해시태그를 생성할 때 필요 |
| `OPENAI_MODEL` | 선택한 대본 생성 모델. 기본값은 `gpt-4.1-mini` |
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL` | 선택. 대체 제공자와 모델 설정. 기본 선택 순서는 OpenAI → Anthropic → Gemini이며, `LLM_PROVIDER`로 지정 가능 |

Railway에서는 공개 도메인 대신 내부 주소를 사용합니다. 백엔드의 `REELS_API_URL`은 `http://<service>.railway.internal:8000` 형식이며, 두 서비스의 `REELS_INTERNAL_API_KEY` 값은 같아야 합니다. `OPENAI_API_KEY`가 없거나 AI 응답이 형식에 맞지 않으면, 서비스는 빈 해시태그를 반환하지 않고 기본 캡션·해시태그로 안전하게 대체합니다.

## 내부 API

`GET /healthz`를 제외한 모든 경로는 `x-reels-api-key` 헤더가 필요합니다. 상태 확인 응답에는 서비스 이름과 현재 미디어 저장소(`supabase`)도 포함됩니다.

| 메서드·경로 | 설명 |
| --- | --- |
| `GET /healthz` | 서비스 상태 확인 |
| `GET /reels/templates` | 사용할 수 있는 콘셉트와 장면 규칙 조회 |
| `POST /reels/scripts` | 운영 백엔드가 렌더링 전에 장면 자막·캡션·해시태그 생성 요청 |
| `GET /reels/scripts/:scriptId` | 대본 작업 상태 조회 |
| `POST /reels/renders` | 릴스 렌더링 시작 |
| `GET /reels/renders/:renderId` | 렌더링 상태와 결과 조회 |

### 렌더링 요청

```json
{
  "user_id": 1,
  "ad_id": "백엔드 생성 작업 ID",
  "concept": "christmas",
  "store": { "name": "가게 이름", "description": "가게 소개" },
  "menus": [{ "menu_index": 0, "name": "대표 메뉴" }],
  "media": [
    { "scene_index": 0, "menu_index": null, "key": "stores/example/video_clip/sign.mp4", "storage": "supabase", "download_url": "간판 서명 다운로드 URL" },
    { "scene_index": 1, "menu_index": 0, "key": "stores/example/video_clip/closeup.mp4", "storage": "supabase", "download_url": "메뉴 클로즈업 서명 다운로드 URL" },
    { "scene_index": 2, "menu_index": 0, "key": "stores/example/video_clip/detail.mp4", "storage": "supabase", "download_url": "메뉴 상세 서명 다운로드 URL" },
    { "scene_index": 3, "menu_index": null, "key": "stores/example/video_clip/entrance.mp4", "storage": "supabase", "download_url": "가게 입구 서명 다운로드 URL" }
  ],
  "scenes": [
    { "scene_index": 0, "text": "가게 소개" },
    { "scene_index": 1, "text": "대표 메뉴" },
    { "scene_index": 2, "text": "한 입의 즐거움" },
    { "scene_index": 3, "text": "가게 입구" }
  ],
  "caption": "게시물 본문",
  "hashtags": ["#시장맛집"],
  "uploads": {
    "video_url": "MP4 서명 업로드 URL",
    "thumbnail_url": "JPG 서명 업로드 URL"
  }
}
```

백엔드 연동에서는 간판, 메뉴별 클로즈업·상세, 가게 입구 순서로 영상을 보냅니다. 메뉴 1개는 4개, 2개는 6개, 3개는 8개 영상입니다. 같은 `ad_id`가 처리 중이면 새 작업을 만들지 않고 `409 ALREADY_RENDERING`과 기존 `render_id`를 반환합니다.

상태는 `queued`, `rendering`, `done`, `failed`입니다. 진행 단계는 `preparing`, `composing`, `uploading`이며, 완료 응답에는 MP4·썸네일 Storage 경로와 길이가 포함됩니다. 입력 URL, 업로드 URL, 내부 API 키는 서버 간 통신에만 사용합니다.

자세한 필드와 오류 코드는 [릴스 API 명세](docs/reels-api-spec.md), Railway 연결 방식은 [배포 문서](docs/deployment.md)를 참고하세요.

POSTALK 백엔드가 릴스 생성 요청을 만들고 결과를 저장하는 실제 연결 흐름은 [백엔드 연동 안내](docs/backend-integration.md)에 정리했습니다.

## 로컬 확인

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m uvicorn src.quote_video.api:app --reload
```

## 운영 검증 기록

실제 Instagram 게시, 표지와 캡션 대조, 중복 게시 방지 결과는 [백엔드의 게시 검증 기록](https://github.com/Superkid0714/Postalk_backend/blob/main/docs/incidents/20261118-instagram-publication.md)에 정리했습니다. 사용자용 API 명세와 게시 완료 판단은 POSTALK 백엔드를 기준으로 확인합니다.
