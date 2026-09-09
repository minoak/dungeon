# 원더랜드 게임 클라이언트 — 초점 캐릭터 카메라 뷰어

`stream.jsonl`(STREAM_FORMAT.md)의 순수 소비자. LLM 0콜. 엔진·프롬프트·기존 HTML 뷰어(`viewer/`)는 무접촉.
계획·결정·수용 기준 = `design/drafts/GAME_CLIENT_PLAN_2026-09-09.md`.

Phaser **3.90.0** + TypeScript 5.9 + Vite 7 (레지스트리 최신은 Phaser 4·Vite 8·TS 7 이지만 계획의 "Phaser 3" 을 따라 고정).
Node 22.16 / npm 10.9 확인.

## 실행

```bash
cd game
npm install                      # ⚠️ vite build 가 "Cannot find module @rollup/rollup-win32-x64-msvc" 로 터지면 ~/.npmrc 의 os=linux 류
                                 #    잔재가 원인(09-09 이 PC 에서 제거함). 남아 있으면 그 줄을 지우고 node_modules·package-lock.json 을 지운 뒤 다시 npm install
npm run dev                      # http://127.0.0.1:5173/game/?run=runs/stream-20260909-203709.jsonl&focus=2&t=176
npm run build                    # tsc --noEmit && vite build → dist/  (론처가 /game/ 으로 서빙 — M3/B5)
npm run smoke                    # 빌드 산출물을 vite preview 로 띄우고 헤드리스 Edge 로 대표 판 재생(verify/smoke.mjs, 스냅샷 verify/out/)
WL_GAME_URL=http://127.0.0.1:8000/game/ npm run smoke   # 론처 상대로
```

개발·프리뷰 서버는 `vite.config.ts` 의 `wlStatic` 플러그인이 리포 루트의 `/viewer /runs /state /art` 를 대신 서빙한다(론처 불필요).
`/api/status` 는 더미 — 라이브(`?run=state/stream.jsonl`)는 론처(8000)에서만 실제로 돈다.

URL 파라미터: `run=`(판 경로, 기본 `state/stream.jsonl`) · `focus=`(초점 봇 번호, 기본 파티 1번) · `t=`(시작 틱).
단축키: Space 재생/정지 · ←/→ 한 틱(Shift 10틱) · Home/End · 숫자 1~9 초점 전환.

## 구조(Phase A = M1 골격, 2026-09-09)

```
src/main.ts              부트: atlas·tiles 사전 → Phaser → 씬 준비 → UI 설치 → 판 로드
src/app.ts               App = { bus, playback, focus, run, scene, dom, loadRun(), frameOfTurn() }  — window.__wl
src/stream/types.ts      스트림 타입(STREAM_FORMAT 미러) + 파생 Frame/Run/LevelState
src/stream/parse.ts      StreamParser.feed(text) — 증분·tail 규칙·파일 순서 조인·방향/이동·시야/본 곳·발자국
src/stream/live.ts       fetchText · RunSource(load, startPolling 1.5s) · fetchStatus   ← B5 가 완성
src/play/Playback.ts     틱 클록(1×/4×/16×, BASE_MS 700) · setIdx/step/play · live 따라가기 · 'frame' 이벤트
src/play/Focus.ts        초점 캐릭터 · 'change' 이벤트
src/world/Sight.ts       격자 LOS(브레젠험, '#'/'+' 가 막음, 목표 칸은 보임) · allCells(마을)
src/assets/sd.ts         atlas.json → spritesheet 등록 · resolveLook(직업 폴백) · frameIndex · 걷기 애니 · 초상 크롭
src/assets/tiles.ts      tiles.json 매핑 재사용 + EXTRA(문·출구·물약·무기·방어구·NPC·묘) · TILE=48
src/scene/DungeonScene.ts 무대: 타일맵·문·출구·피처·함정·몹·SD 캐릭터·이름표·초점 링·카메라·트윈·걷기 애니 · 공개 API
src/scene/Fog.ts         밝기(B4): 미지 α.88·본 곳 α.45·시야 0, 마을 없음, 서명 더티체크 · window.__wlFog
src/scene/Bubbles.ts     말풍선·지문·몸 돌리기(B2): #overlay DOM, rAF 재배치, 화자당 1개, 제안 .proposal
src/fx/Handoff.ts        건네기 트윈(B3): give 틱에 물건 아이콘이 둘 사이를 0.4s 건너간다(name 'handoff')
src/text/evline.ts       사건 문장 사전(B2): viewer evLine 이식 + follow/rest/give/bond/NPC 어휘 — 순수 함수
src/ui/Chips.ts          캐릭터 칩(초상·이름·직업·HP·상태·시야 밖 흐림·전사·하강) · 클릭/숫자키
src/ui/Controls.ts       판 선택·재생 버튼·속도·슬라이더·틱 라벨·LIVE 배지·줌·로그 접기·단축키
src/ui/FocusCard.ts      초점 카드(B1): HP·상태·소지·속내·최근 말·관계 뼈(BONES)·관계 한 줄 — 결정 색인 이진 탐색
src/ui/Log.ts            로그(B2): 프레임 그룹 .grp[data-turn], 창 90, 증분 append, 초점 줄 .focus
src/ui/dom.ts            $, esc, el, typing
verify/smoke.mjs         Playwright(msedge 채널) 스모크 — M1 + M2 장면 재현(초점=수나 t176~t184·안개·말풍선·로그·건네기·B5 status) · 실패는 모아서 마지막에 한꺼번에
```

## 계약(바뀌지 않는 것 — Phase B 카드의 입력)

### 이벤트

| 원천 | 이벤트 | payload | 뜻 |
|---|---|---|---|
| `app.bus` | `run` | `Run` | 새 판이 열림(프레임 교체). UI 는 다시 만든다 |
| `app.bus` | `grow` | `{added}` | 라이브: 프레임이 붙음 |
| `app.bus` | `live` | `boolean` | 라이브 판 여부 |
| `app.bus` | `scene` | `DungeonScene` | 씬 create 끝 |
| `app.bus` | `error` | `string` | 로드 실패 등(HUD 에 표시) |
| `app.playback` | `frame` | `{prev, cur, idx, mode}` | 현재 프레임 변경. **mode='seek' 면 prev=null(스냅으로 그려라), 'step'/'play' 면 prev=직전 프레임(트윈 가능)** |
| `app.playback` | `play` / `speed` / `frames` / `live` | bool / idx / n / bool | 재생 상태 |
| `app.focus` | `change` | `{char, prev}` | 초점 전환(카메라 팬 300ms 는 씬이 한다) |

### Frame(파생, `src/stream/types.ts`)

`kind('level'|'tick') idx turn levelIdx level bots monsters features traps events decisions inbox hails? answers? replies? descend?`
+ `facing{char:Dir}` `moved{char:bool}` `vis{char:Set<"x,y">}`(그 봇이 지금 보는 칸, 마을=전부, 죽음/하강=빈 집합)
`seen{char:n}`(= `run.levels[levelIdx].seenList[char]` 의 이 프레임까지 길이) `visited`(= `visitedList` 길이).
`run`: `meta end party frames levels names jobs colors looks deathTurn sight town`.

### 씬 공개 API(`app.scene`)

| 메서드 | 뜻 |
|---|---|
| `feetOf(char)` / `headOf(char)` | 월드 px(발 / 머리 위 = 말풍선 앵커). 트윈 중이면 지금 자리. 없으면 null |
| `project(wx, wy)` | 월드 px → `#stage` 안 화면 px(DOM 오버레이용). 카메라가 움직이니 매 rAF 재계산 |
| `worldOf(x,y)` / `centerOf(x,y)` | 칸 → 월드 px(발 / 칸 중앙) |
| `actorOf(char)` | `{sprite, label, key, dir, cell, alive, won}` |
| `turnToward(char, other)` | 몸 돌리기(정지 프레임). 다음 걸음이 방향을 되돌린다 |
| `tileFrame(key)` | Kenney 시트 프레임 번호 — `'item:potion' 'item:weapon' 'item:armor' 'feat:chest' 'mob:고블린' …` |
| `visibleSet(char)` / `seenSet(char)` | 현재 프레임 시야 / 이 층 누적 본 칸(캐시). 초점 없으면 null(=전부) |
| `setZoom(z)` · `zoom` · `ZOOMS` | 1 / 1.5 / 2 |
| `DEPTH` | `ground 0 · footprint 5 · feature 10 · trap 12 · corpse 15 · focusRing 19 · stand 20(+y·0.01) · fx 50 · fog 60 · label 70` |
| `TILE` (`assets/tiles.ts`) | 48px |

### DOM 자리(`app.dom`)

`stage`(Phaser 캔버스 부모) · `overlay`(무대 위 절대 배치, pointer-events:none — Bubbles) · `hud` · `side` · `chips` · `focusCard` · `bottom` · `controls` · `log`.
텍스트는 반드시 `esc()` 를 거친다(대사·이름은 LLM/사용자 입력).

### 정보 등급(씬이 이미 지킨다)

숨은 함정(`hidden`)·매복 몹(`concealed`)·숨은 피처(`concealed`)는 안 그린다. 산 몹은 초점 캐릭터 시야 안만, 피처·시체는
시야 안이거나 본 적 있는 칸만. 마을(`levels[i].town`)은 전부. 초점이 없으면 전부(관전자).

## Phase B 카드(각 카드 = 자기 파일만, 겹침 0 — 계획 §6) — 2026-09-09 6장 전부 통합됨

| 카드 | 파일 | 입력 | 수용 |
|---|---|---|---|
| B1 초점 카드 | `src/ui/FocusCard.ts` | focus/frame 이벤트 · bots · decisions(reason/say/relation) · BONES 라벨(엔진 `dungeon_gm.py` BONES 복사) | 초점 전환 시 HP·상태·소지·속내·관계 뼈·관계 한 줄이 바뀐다 |
| B2 말풍선·로그 | `src/scene/Bubbles.ts` `src/ui/Log.ts` `src/text/evline.ts` | decisions(say/to/say_kind/form) · events(evLine 사전 = `viewer/index.html` 이식) · headOf/project/turnToward | 제안 표식·지문 줄·사건 줄 시간순, 초점 줄 강조, 몸 돌리기 — 훅 `#overlay .bubble[data-char](.proposal/.focus/.who/.to)` · `.stage-dir[data-char]` · `#log .grp[data-turn]` 안 `.say/.rsn/.ev.{give|dir|…}/.focus(data-c)` |
| B3 건네기 트윈 | `src/fx/Handoff.ts` | events give(char,to,item,what) · feetOf · tileFrame('item:…') | give 틱에 아이콘이 둘 사이를 0.4s 건너간다(seek 는 생략) |
| B4 밝기 | `src/scene/Fog.ts` | visibleSet/seenSet · level.grid · town · TILE · DEPTH.fog | 가 본 곳/시야/미지 3단, 마을 전체 밝음, 16× 프레임 드롭 없음 |
| B5 라이브·배포 | `src/stream/live.ts` · `launcher.py`(`/game/` 라우트만) · `package.json` scripts | RunSource/fetchStatus · 론처 `do_GET` | 더미 두뇌 판 라이브 재생, `npm run build` 산출물이 8000 의 `/game/` 에서 열린다, `python verify_launcher.py` 통과 |
| B6 스모크 | `verify/smoke.mjs` | 전부 | seed 257573 판 t176~t184 초점=수나 재생·캡처, JS 오류 0 |

금지: `dungeon_gm.py` `brains.py` `show_runner.py` `adventurer_prompt_menu.md` `viewer/` 무수정 · 새 에셋 제작 금지 · 다른 카드의 파일·`main.ts`·`app.ts`·`types.ts` 무수정(필요하면 자기 파일 안에서 해결하고 통합자에게 요청).

## 론처 배포(B5, 2026-09-09)

`launcher.py`(8000)가 `npm run build` 산출물 `game/dist/` 를 **`/game/`** 으로 서빙한다(vite `base: '/game/'` 과 같다). 뷰어·runs·state 서빙은 그대로.

| 요청 | 응답 |
|---|---|
| `GET /game` | 302 → `/game/`(쿼리 보존) |
| `GET /game/` · `/game/index.html` | `game/dist/index.html`, `Cache-Control: no-store`(새 빌드가 바로 보이게) |
| `GET /game/assets/…` | 해시 자산, 캐시 헤더 기본(SimpleHTTPRequestHandler) |
| `game/dist/index.html` 없음 | 503 + 한글 안내 한 장(`cd game && npm install && npm run build`) — 어느 `/game/…` 경로든 같은 답 |
| `GET /api/status` | 기존 키 + `game: "/game/?run=state/stream.jsonl"`(추가만 — `viewer` 유지) |

구현 = `Handler.translate_path` 오버라이드(`/game/` 접두 → `/game/dist/`; 따옴표 풀기·`..` 걸러내기·index.html 선택은 부모 그대로) + `do_GET` 의 302/503 두 분기 + `end_headers` 의 no-store 한 줄. `python verify_launcher.py` 무변경 통과.

```bash
cd game && npm run build && npm run launch        # = python ../launcher.py --no-browser → http://127.0.0.1:8000/game/?run=state/stream.jsonl
npm run smoke:launcher                             # = WL_GAME_URL=http://127.0.0.1:8000/game/ 로 smoke.mjs (WL_LAUNCHER=http://127.0.0.1:8765 로 다른 포트)
```

### 라이브(`src/stream/live.ts`)

- `RunSource` 폴링은 setTimeout 사슬 — 실패하면 **1.5 → 3 → 6s(상한)** 백오프, 성공하면 1.5s 로 복귀(`delay`·`failures` 필드로 관찰).
- `installLive(app)`(main.ts 가 한 줄로 설치) — 라이브 판(`app.live`)일 때 `/api/status` 를 1.5s 마다 읽어 `#hud .badge.live-hud` 를 갱신한다. 문자열이 같으면 DOM 무접촉.

| 배지 | 뜻 |
|---|---|
| `LIVE · t{turn}` | 러너가 돌고 있다(turn = 론처가 읽은 틱과 붙은 프레임 중 큰 것) |
| `LIVE · t{turn} · 론처 응답 없음` | `/api/status` 실패 — 상태 폴링도 같은 백오프 |
| `중단됨 · t{turn}` | 러너는 죽었는데 `end` 라인이 없다(`/api/stop`·강제 종료) |
| `론처 없음 — 라이브 아님` | vite 개발·프리뷰의 더미 `{dev:true}` — 더는 묻지 않는다 |
| (숨김) | 라이브가 아니다(리플레이·`end` 뒤) |

새 판이 시작돼 파일이 줄어들면(파서 reset → bus `run`) 배지도 초기화된다. 덤: `state/` 경로를 보고 있는데 라이브가 아니면(끝남·빈 판·404) 3s 마다 상태를 살펴, 론처에서 새 판이 돌기 시작했으면(running·틱 있음·end 없음) 같은 경로를 다시 연다 — 론처에서 시작 → 이 창이 알아서 붙는다. 스타일은 `<style id="style-live">` 주입(style.css 무수정).

⚠️ 론처의 정적 서빙은 **리포 root** 기준이라 `make_server(state_dir=임시)` 로 격리해도 `/state/stream.jsonl` 은 실제 `state/` 를 준다(러너 쓰기만 격리). 라이브 검증은 임시 폴더·더미 두뇌로 하되 이 점을 알고 할 것.

## 검증 규율

커밋은 `npm run build`(tsc + vite) + `npm run smoke` 통과 조건부. 엔진 게이트 43종은 무관(엔진 무접촉 — `git diff --stat` 로 증명).
실 LLM 판은 파트너가 론처 [L] 로. 여기서는 리플레이 파일(`runs/`)과 더미 두뇌 판만 쓴다.

## 열린 결정(파트너)

- `dist/` 커밋 여부(지금은 .gitignore — 론처에서 열려면 `npm run build` 가 먼저 필요).
- 초점 기본값(파티 1번 — 임시 가정) · 옛 판 캐릭터(직업별 기본 SD 폴백 — 임시 가정) · 미니맵 없음 · 기존 HTML 뷰어 은퇴 시점.
