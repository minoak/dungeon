# D80 모델 배선 — 2026-09-17

범위: 사용자가 회사·모델·자기 API 키를 선택해 로그인하고 새 판/이어가기를 실행한다.
모델의 역할극 품질 비교는 이번 배선 검증과 별개다. 화면·오류 문구는 ⚠️ 임시(검토표 131~138).

## 기본 모델 표

확인일: 2026-09-17. 기본값은 `brain_config.MODEL_IDS` 한 곳이고 `brains._MODEL_ID`가 같은 표를 참조한다.
`haiku`는 기존 결정·수첩·NPC 호출의 별칭, `sonnet`은 상위 슬롯의 별칭이다.

| 회사 | haiku | sonnet | 공식 출처 |
|---|---|---|---|
| Anthropic | `claude-haiku-4-5-20251001` | `claude-sonnet-5` | [모델 표](https://platform.claude.com/docs/en/models/overview) |
| Google | `gemini-3.8-flash` | `gemini-3.1-pro-preview` | [모델 목록](https://ai.google.dev/gemini-api/docs/models), [3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) |
| OpenAI | `gpt-5.6-terra` | `gpt-5.6-sol` | [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |

최상위 모델을 자동 선택하는 표가 아니다. OpenAI의 [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)도 공식 문서에 있지만, 이번 기본값은 짧은 행동 응답용 Terra/Sol로 두고 Astra 실측은 하지 않았다. 공식 목록의 Claude Fable 5.1·Opus 5 등은 모델 칸에서 직접 지정할 수 있다.
OpenAI 기본 모델은 공식 문서에서 Chat Completions와 `none` 사고 설정을 지원하는 모델로 골랐다.
Gemini 신형 Flash·Pro 기본 사고는 `low`; 기존 3 Flash는 `minimal`이다. [사고 설정 문서](https://ai.google.dev/gemini-api/docs/thinking).
3.5/3.6은 작업 지시서와 공식 문서의 minimal 설명이 달라 지원되는 `low`를 보수적으로 사용한다. 명시한 `DUNGEON_GEMINI_THINK`는 보존한다.

Sonnet 5는 사고가 기본으로 켜진다. 기존 1,024 토큰 출력 예산에서 답변을 보존하도록 이 모델에만 `thinking.type=disabled`를 명시한다. [Sonnet 5 변경점](https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5).

## 설정과 계약

- 공통 슬롯 설정 `DUNGEON_MODEL_HAIKU` / `DUNGEON_MODEL_SONNET` > 이전 `DUNGEON_GEMINI_MODEL` / `DUNGEON_ANTHROPIC_MODEL` > 기본 표.
- 로컬 론처는 `.env` 키를 사용한다. 화면 모델 칸에는 회사별 기본값(로컬 환경 덮어쓰기 포함)을 채우며, 입력 모델은 두 슬롯에 적용한다.
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
