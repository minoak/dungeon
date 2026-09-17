# D80 모델 배선 — 2026-09-17

범위: 사용자가 회사·모델·자기 API 키를 선택해 로그인하고 새 판/이어가기를 실행한다.
모델의 역할극 품질 비교는 이번 배선 검증과 별개다. 화면·오류 문구는 ⚠️ 임시(검토표 131~148).

## 기본 모델 표

확인일: 2026-09-17. 기본값은 `brain_config.MODEL_IDS` 한 곳이고 `brains._MODEL_ID`가 같은 표를 참조한다.
`haiku`는 기존 결정·수첩·NPC 호출의 별칭, `sonnet`은 상위 슬롯의 별칭이다.

| 회사 | haiku | sonnet | 공식 출처 |
|---|---|---|---|
| Anthropic | `claude-haiku-4-5-20251001` | `claude-sonnet-5` | [모델 표](https://platform.claude.com/docs/en/models/overview) |
| Google | `gemini-3.8-flash` | `gemini-3.1-pro-preview` | [모델 목록](https://ai.google.dev/gemini-api/docs/models), [3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) |
| OpenAI | `gpt-5.6-terra` | `gpt-5.6-sol` | [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |

최상위 모델을 자동 선택하는 표가 아니다. OpenAI의 [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)도 선택 목록에 있지만, 기본값은 짧은 행동 응답용 Terra/Sol로 두고 Astra 실측은 하지 않았다. Claude Fable 5.1·Opus 5도 선택 목록에서 고를 수 있다.
OpenAI 기본 모델은 공식 문서에서 Chat Completions와 `none` 사고 설정을 지원하는 모델로 골랐다.
Gemini 신형 Flash·Pro 기본 사고는 `low`; 기존 3 Flash는 `minimal`이다. [사고 설정 문서](https://ai.google.dev/gemini-api/docs/thinking).
3.5/3.6은 작업 지시서와 공식 문서의 minimal 설명이 달라 지원되는 `low`를 보수적으로 사용한다. 명시한 `DUNGEON_GEMINI_THINK`는 보존한다.

Sonnet 5는 사고가 기본으로 켜진다. 기존 1,024 토큰 출력 예산에서 답변을 보존하도록 `thinking.type=disabled`를 명시한다. 후속 확장에서는 Opus 5에도 같은 설정을 적용했다. [Sonnet 5 변경점](https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5), [Opus 5](https://platform.claude.com/docs/en/models/opus-5/overview).

## 사람이 고르는 모델 목록 (09-17 후속 요청)

`brain_config.MODEL_CHOICES`를 `/api/presets`의 `providers[회사].choices`로 전달한다. 새 원정과 이어가기 모두 **회사 → 모델 선택 → 키 입력** 순서이며, 기존 기본값은 그대로다.

| 회사 | 선택 목록 | 공식 출처 |
|---|---|---|
| Gemini (9종) | 3.8 Flash, 3.7 Flash, 3.6 Flash, 3.5 Flash, 3.5 Flash-Lite, 3.1 Flash-Lite, 3.1 Pro Preview, 3 Flash Preview, 2.5 Flash | [모델 ID 목록](https://ai.google.dev/gemini-api/docs/models) |
| Claude (4종) | Haiku 4.5, Sonnet 5, Opus 5, Fable 5.1 | [모델 표](https://platform.claude.com/docs/en/models/overview) |
| OpenAI (4종) | GPT-5.6 Terra, GPT-5.6 Luna, GPT-5.6 Sol, GPT-6 Astra | [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra), 기본 표의 Terra/Sol 출처 |

- `직접 입력…`을 고르면 모델 ID 칸이 열린다. 목록에 없는 로컬 기본값·저장 모델도 이 칸으로 정확히 복원한다. 빈 직접 입력으로 시작/이어가기는 막는다. 상태 갱신이 사용자의 선택을 덮지 않는다.
- 목록은 공식 문서의 정적 목록이며 계정별 권한 조회 결과가 아니다. 키마다 사용 가능 모델이 다를 수 있다. Preview를 표시하며, 목록 밖 모델도 기존 검증을 거쳐 지정할 수 있다.
- `OPENAI_BASE_URL`이 공식 주소와 다르면 OpenAI 목록을 비우고 직접 입력을 사용한다. 운영자 설정 모델은 로컬 론처에서 보존한다. 호환 서버에 OpenAI 전용 사고 파라미터를 보내지 않는다.
- Luna도 `reasoning_effort=none`. Astra는 `none`을 지원하지 않아 `low`, 기본 출력 상한 4,096을 사용한다. [모델별 지원값](https://developers.openai.com/api/docs/models/gpt-6-astra).
- Fable 5.1은 사고가 항상 켜져 `thinking.type=adaptive`, `output_config.effort=low`, 기본 출력 상한 4,096을 사용한다. [Fable](https://platform.claude.com/docs/en/models/fable-5-1/overview), [effort](https://platform.claude.com/docs/en/build-with-claude/effort).
- `DUNGEON_BRAIN_MAXTOK`을 명시하면 모든 모델에서 그 값을 우선한다. 4,096은 짧은 행동 응답을 위한 초기 설정이며 출력 완결성·속도·비용을 실측한 값은 아니다. 새 모델 실호출은 이번 확장에서 하지 않았다.
- 문구 ⚠️ 임시: 검토표 139~142.

## 설정과 계약

- 공통 슬롯 설정 `DUNGEON_MODEL_HAIKU` / `DUNGEON_MODEL_SONNET` > 이전 `DUNGEON_GEMINI_MODEL` / `DUNGEON_ANTHROPIC_MODEL` > 기본 표.
- 로컬 론처는 화면에 입력한 API 키를 우선 사용하고, 빈 칸이면 `.env` 키를 사용한다. 화면 모델 칸에는 회사별 기본값(로컬 환경 덮어쓰기 포함)을 채우며, 입력 모델은 두 슬롯에 적용한다.
- 공개 서버는 `POST /api/start {provider, key, model?}`; provider는 `gemini_api`, `anthropic_api`, `openai_api`만 허용한다. 서버를 `dummy`로 기동한 검증 환경만 실제 러너가 dummy다.
- 키는 선택 회사의 러너 환경변수 하나에만 들어간다. 다른 회사 키·모델 상속·자동 폴백을 비운다. 부모 환경, 파일, 응답, 로그에는 키를 남기지 않는다.
- 로그인/연결은 `POST /api/login {provider, key, nick?}`, `/api/keys/link {provider, key}`. 해당 회사 모델 목록 GET으로 생존 확인한다. 400/401/403은 무효, 연결 실패·3xx·429·5xx는 확인 불가(503). 리다이렉트를 따라가지 않는다.
- 계정 지문 계산은 그대로다. `keys[].provider`만 추가하며 예전 항목은 Gemini로 읽는다. `/api/me`의 계정 열쇠에도 회사가 포함된다.
- 이어가기는 모델·회사를 생략하면 직전 설정을 보존하고, 회사를 바꾸며 모델을 생략하면 새 회사 기본값으로 간다. 바꾼 설정도 다음 이어가기를 위해 보관한다(키 제외).
- `OPENAI_BASE_URL`은 `.env`/서버 운영자 환경으로만 설정한다. 공개 요청의 `base_url`은 거부한다. 주소에 인증값·쿼리·fragment를 허용하지 않는다. 화면에는 공개 서버의 목적지를 알려 준다. 자식 러너에도 같은 주소를 명시해 자식의 `.env`가 목적지를 덮지 못하게 한다.
- 호환 서비스(OpenRouter/Groq/DeepSeek/vLLM/Ollama)는 서비스 주소와 그 서비스의 모델 ID를 함께 지정한다. 키 없는 로컬 서버는 `OPENAI_API_KEY=local` 같은 자리표시자를 명시한다.
- 호환 서비스의 `/models`가 인증을 실제 검사해야 계정 로그인에도 쓸 수 있다. 인증 없는 로컬 서버는 단독 로컬 실행용이다.
- `_call_claude(prompt, model="haiku")`와 실패 라벨·`_http_post` 전송 상한·타임아웃을 보존한다. `run_meta.backend`에 `openai_api`만 additive, `decisions.src`는 그대로다.
- OpenAI 공식 추론 모델에는 `max_completion_tokens`, 일반 호환 서비스에는 `max_tokens`를 쓴다. 기본 Terra/Sol은 짧은 행동 JSON 예산을 위해 `reasoning_effort=none`. 다른 모델의 사고·출력 예산은 모델별 실측이 필요하다.

## 검증

- `verify_model_wiring`: 세 HTTP 요청/응답, 빈 응답·4xx·타임아웃·불량 JSON 모양·리다이렉트 차단·호출 상한, 회사별 키 생존 확인, 키 길이·모델 검증, 구형 계정 호환, 로컬/공개 로그인·연결·새 판·이어가기, 부모 env/디스크 키 미기록. 실 API 0콜.
- 헤들리스 Edge `verify_model_wiring_browser.mjs`: 회사별 모델 기본값, 로그인 키 자동 채움, 회사 변경 시 키 비움, 키 연결, 새 판/이어가기 요청, 브라우저 저장소 미사용, 페이지 오류 0. 시작 요청은 가로채므로 생성 API 0콜.
- 기존 `verify_character_presets_browser.mjs`: 저장·재접속·다른 칸 복원·헤어/성격 유지·수정·복사·삭제·파티 저장·모바일 표시 통과.
- **최종 68/68 ALL PASS, 모든 프로세스 exit 0.** `_run_gates.sh`의 동일한 68개 목록·환경을 사용하되 4개 독립 임시 복사본에 나눠 실행했다. `.env`·실판 상태 폴더는 복사하지 않았다. 실행 소스의 SHA-256을 남겨 최종 코드와 일치함을 확인했다.
- 첫 전체 실행에서 캠페인 게이트의 옛 `KEY_CHECK(key)` 대역을 발견했다. `KEY_CHECK(key, provider)`로 고친 뒤, 마지막 수정까지 포함한 코드로 68종 전체를 다시 실행해 통과했다.
- `git diff --check` 통과.

### 실키 프로브

`scenario.py scenarios/작정.json --probe 1 --jobs 1`, compose 모드. 임시 상태 폴더, `DUNGEON_API_CALL_LIMIT=1`, 자동 폴백 없음.
호출 전에 최대 Gemini 1 + Anthropic 1 = 2콜을 고지했고, 실제 전송은 총 **1회**였다.

| 회사·모델 | 실제 전송 | 응답/지연/거부 | 판정 |
|---|---:|---|---|
| Gemini `gemini-3.8-flash` | 1 | 텍스트 116자 → 행동 JSON 파싱 정상(`src: haiku 1`), HTTP 호출 2,417ms, 입력 2,381/출력 52토큰, `STOP`, 거부·재시도 없음 | 기본 슬롯 단일 장면 실호출 확인 |
| Anthropic | 0 | `.env`에 키 없음 | 배선만, 실호출 미검증 |
| OpenAI | 0 | `.env`에 키 없음 | 배선만, 실호출 미검증 |

미검증: Anthropic/OpenAI 실호출, 세 회사 로그인 모델 목록의 실제 계정 권한, Gemini Pro와 상위 슬롯 실호출, 호환 서비스별 endpoint/모델 동작, 장기 원정의 역할극 질감·비용·거부율. 공식 ID 확인과 단일 프로브는 이 항목들의 품질 보증이 아니다.
검토표 추가 번호: **131~138**. 키·프로브 원문·판 기록은 커밋하지 않는다.

### 모델 선택 확장 검증 (후속 작업)

- 17종 모두 요청 모델 ID·사고 옵션·출력 상한·명시한 상한 우선 처리를 대역으로 검사. 호환 주소에서는 공식 목록과 OpenAI 전용 사고 옵션이 빠지는 것을 확인했다.
- 헤들리스 Edge: 목록에서 고른 새 판/이어가기 모델 전달, 직접 입력 전달, 목록 밖 저장 모델 복원, 빈 직접 입력 차단, 상태 갱신 후 선택 보존, 회사 변경 시 키 비움, 모바일 390px 가로 넘침 없음, 페이지 오류 0. 기존 캐릭터 저장 브라우저 검사도 통과했다.
- 변경된 최종 코드로 **68/68 ALL PASS, 모든 프로세스 exit 0**. 4개 독립 임시 복사본, 기존 게이트 목록·환경 그대로. 실행 소스 SHA-256이 현재 코드와 일치함을 확인했다. `git diff --check` 통과.
- 이 확장의 실 API 호출은 **0회**. 앞 절 Gemini 1회는 이전 배선 작업의 결과이며 새 모델의 실호출 검증으로 취급하지 않는다. 실행 중인 사용자 판과 서버는 재시작하지 않았다.
- 코드 변경 후 켜져 있던 론처/공개 서버는 다음 재시작 때 새 모델 카탈로그를 읽는다. 모델별 계정 권한·응답 품질·속도·비용은 실호출 미검증이다.

## 판단 가격표·로컬 키 입력 (09-17 추가 요청)

### 가격과 계산 범위

`model_pricing.py`에 17종 일반 텍스트 API의 USD/100만 토큰 단가, 확인일, 공식 출처를 둔다. 카탈로그의 `choices[].price`로 전달하며 원격 조회나 생성 호출은 하지 않는다.
출처: [Google 가격](https://ai.google.dev/gemini-api/docs/pricing), [Anthropic 가격](https://platform.claude.com/docs/en/about-claude/pricing), [OpenAI 가격](https://developers.openai.com/api/docs/pricing). 확인 2026-09-17. Google 구형 3 Flash/2.5 Flash는 같은 공식 가격 페이지의 해당 모델 항목을 검색해서 확인했다.

- 입력 토큰 가정 = ceil((캐릭터 설정 글자 + 규칙·장면·기억 글자) × 글자당 토큰 가정).
- 판단 1회 USD = (가정 입력 토큰 × 입력 단가 + 가정 출력 토큰 × 출력 단가) / 1,000,000. 전체 판단 횟수를 곱해 비교한다. 횟수는 한 캐릭터의 요청을 합산한 수이며 게임 턴 수가 아니다.
- 기본 예시: 설정 10,000자 + 기타 문맥 4,000자, 글자당 1토큰, 출력 500토큰, 전체 100회. 모든 값을 바꿀 수 있다. 1글자=1토큰은 **계산 가정**으로, 실제 토큰화나 보장된 범위가 아니다. 모델·한국어·사고 토큰 양에 따라 달라진다.
- 현재 파티의 설정 글자 수를 보여 주고 가장 긴 설정을 계산기에 적용할 수 있다. 커스텀은 성격(키워드 포함)+배경, 기본 파티는 성격+배경+말투+목표를 센다. 엔진의 완성 프롬프트를 생성하거나 토큰을 실측한 값은 아니다. 기존 자유 입력 상한(성격 2,000자·배경 4,000자)은 변경하지 않는다.
- 무료 할당, 캐시 할인, 세금, NPC/수첩/재시도 호출은 계산에서 제외한다. 사고 토큰은 출력 가정에 포함한다. **실제 누적 청구액·한 판 총액·예산 제한 기능이 아니다.**
- Gemini 3.6~3.8 Flash 할인은 2026-12-31까지 적용하며 2027-01-01에 문서상 후속 단가로 전환한다. Sol은 2026-11-21 이후 후속 가격을 추측하지 않고 미확인으로 표시한다. Gemini Pro 200k 초과와 OpenAI 272k 초과 입력은 별도 단가를 적용한다. 이외 변동은 확인일과 공식 링크로 알린다.
- 목록 밖 모델·OpenAI 호환 주소의 단가는 미확인으로 표시하며, 0원으로 간주하지 않는다. 동일 가정의 17종 비교표와 현재 선택 모델의 공식 가격 링크를 제공한다.

### 로컬 키

키 칸이 공개 서버에서만 표시되던 조건을 수정했다. 로컬에서도 HTTP 모델의 새 판·이어가기에 키를 입력할 수 있다. 빈 칸은 기존 환경 키, 입력한 키는 해당 판에만 우선한다. CLI/dummy는 키·가격표를 숨긴다.
`Runner.start`에서 키를 시작 옵션과 분리한 뒤 형식 검사하고, 재개 옵션을 합친 다음 확정된 회사의 환경변수에만 넣는다. 입력 키를 쓸 때 다른 회사 키와 자동 폴백은 비운다. 부모 환경·저장 옵션·파일·브라우저 저장소에 쓰지 않는다. `model_ui_version=2`를 확인해 구 서버에는 새 판/이어가기 키를 전송하지 않고 재시작 안내를 보여 준다. 기존 실행 중인 서버/판은 자동으로 재시작하지 않는다.

### 검증

- Python 68종 ALL PASS, 전부 exit 0. 4개 독립 임시 복사본에 기존 목록·환경 그대로 실행, 최종 Python 소스 SHA-256 일치 확인. 실 API 0콜.
- 확장 배선 게이트: 17종 가격, 할인 경계일·후속 가격 미확인, 로컬 3회사 입력 키·빈 키 환경 보존·이어가기·잘못된 키·다른 회사 키 비움·부모 환경/파일 미기록.
- 최종 HTML/JS로 Edge 브라우저 재검증: 로컬/공개 새 판·이어가기 키 전달, 회사 변경 시 키 비움, 구 서버 전송 차단, 17행 가격 비교, 글자 수 증가 시 계산 증가, Fable $0.165/100회 $16.50 예시, 미확인 단가, 실제 파티 설정 길이 적용, 모바일 390px 비교표 펼침·가로 넘침 없음, 페이지 오류 0. CSS 링크 대비 수정과 구 서버 보호도 포함한다.
- 기존 캐릭터 저장·복원·수정·복사·삭제·파티 저장·모바일 브라우저 검사 통과. 문구 ⚠️ 임시 143~148.
