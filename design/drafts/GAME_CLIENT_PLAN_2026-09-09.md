# 게임 클라이언트(초점 캐릭터 카메라 뷰어) 계획 — 2026-09-09 (파트너 결정 · 다음 세션 인계 · 울트라코드 분할안)

> **상태: 파트너 확정 방향, 구현 전.** 파트너 결정(원문 요지)과 세션 제안(파트너 "네 제안에 동의해")을 합친 인계 문서.
> 다음 세션이 이 문서만 읽고 착수할 수 있게 쓴다. LLM 콜 0(리플레이 데이터만 쓴다). 엔진·프롬프트·기존 HTML 뷰어는 무접촉.

## 0. 결정(파트너, 2026-09-09 밤)

- "이제 html 뷰어를 벗어나야 한다. 맵 전체를 보여줄 필요도 없다. 도트 캐릭터 구현이 어려워 크기를 키우는 대신 **LLM 으로 만든** 캐릭터를 쓴다(만든 게 파일에 있다). 중요한 건 **이 캐릭터를 유의미하게 보여주기 위한 화면 재구성**."
- "게임 화면에 가깝게 **주인공 캐릭터 하나만 정해서 그걸 위주로** 보여주자. 다른 캐릭터를 보고 싶으면 **옆의 캐릭터 아이콘을 클릭하면 카메라가 그걸 따라가게**."
- "런타임은 **이번엔 배포까지 하니까 조금 더 본격적으로**." → 세션 제안 **Phaser 3 + TypeScript(웹 게임 클라이언트)** 에 "네 제안에 동의해". 배포 = 웹 서비스(론처 서버 + 브라우저). 초점 밖 칩 = 초점 캐릭터의 시야 밖이면 흐리게(제안 동의).
- 범위 = 아래 M1·M2·M3 전부("1,2,3 을 작업하고 싶다"). 다음 세션에서 **울트라코드**(멀티에이전트 병렬)로 착수 예정 — §6 분할안.

## 1. 왜 이 화면인가(근거)

- 09-09 판(seed 257573, 유나 전사·수나 도적·미나 궁수)에서 **관계의 창발**이 목격됐다: 수나가 180틱을 겉돌다 t179 갑옷 건네기 → t181 유나가 옆의 고블린 처치 → t182 유나가 수나 머리를 쓰다듬음(친목 `form`) → 이후 70틱 중 59틱 유나 동행(1%→84%), 관계 한 줄 "무섭지만 의지가 되는 언니". 이 드라마는 16px 점의 이동으로는 안 보인다. 화면은 **캐릭터의 말·몸짓·관계·속내**를 보여줘야 한다.
- SD 도트(96px, 4방향, 정지 1+걷기 4, 헤어 11종)는 지도 위 점이 아니라 **무대 위 인물** 크기다. `art/sprites-v4/README.md` 가 "HTML 뷰어는 교체 예정인 임시 뷰어, 다음 뷰어는 PNG+atlas.json 만 읽으면 된다"고 규격을 적어 뒀다.

## 2. 계약(바꾸지 않는 것)

**스트림(`STREAM_FORMAT.md`)** — 클라이언트는 스트림 소비자 하나가 더 생기는 것. 쓰는 것:
- `run_meta`: seed, w/h, sight, town, party[](char, name, job, sex, maxhp, look{sprite?, hairstyle?, head, body, colors}), give/bond/say_kind 등 스위치, backend.
- `level`: depth, w, h, grid[](행 문자열 '#'/'.'/'+'), exit, rooms[], features[], traps[], monsters[]. `descend`/`ascend` 직후엔 반드시 `level`.
- `tick`: turn, bots[](char, x, y, hp, maxhp, alive, won, order, potions, weapon, armor, status[], relations{other:{kind:n}}), monsters[], features[], traps[], events[](type/result — `viewer/index.html` `evLine` 이 문장 사전), decisions{char:{type, target?, item?, form?, say, to?, say_kind?, reason, src, relation{to,line}?, note?, skipped?}}, inbox, hails?, answers?, replies?[{from,to,kind,how}].
- `end`: outcome, survivors, fallen.
- 파생: 걷기 방향 = 틱 간 좌표 델타(현재 뷰어와 같은 규칙), 가 본 곳 = 봇 좌표 누적, 시야 = 격자 LOS(반경 `run_meta.sight`, '#'와 '+'가 빛을 막음, 동료는 `ally_sight` 면제) — **관전 근사 허용**(엔진과 픽셀 일치 요구 없음), 마을(`town`)은 전체 시야.

**에셋(`viewer/assets/sprites/sd/atlas.json`, v2)** — cell 96, directions [front,right,back,left]=행, columns 5(열 0 정지·1~4 걷기), frame_ms 160, 발 바닥 y=91(origin (0.5, 91/96)), presets[id].hairstyles[hid].sheet(전체 캐릭터 프레임 — 가발 레이어 아님). 선택값 = `look.sprite` + `look.hairstyle`(없으면 default). `look.sprite` 가 없는 옛 판 = 파츠 합성(`sprites.json`) — **M1 에서는 SD 없는 캐릭터를 직업별 기본 SD 로 폴백**(파츠 합성 이식은 후속, 결정 §8).
타일 = `viewer/tiles.json`(Kenney Tiny Dungeon, CC0 — 기존 글리프→타일 매핑 재사용). 표시 타일 48px(SD 96px = 2타일 높이 = RPG 만들기 비율).

**론처(`launcher.py`, 8000)** — 정적 `/state/`·`/runs/`·`/viewer/`·`/art/`, `/api/status`(running, seed, turn, outcome). 라이브 = 현재 뷰어와 같이 `state/stream.jsonl` 을 1.5초마다 재요청(전체 재파싱; SSE/증분은 M3 선택). 새 클라이언트는 `/game/`(빌드 산출물 정적 서빙) — M3 에서 라우트 추가(론처는 그때만 손댄다).

## 3. 화면 사양

- **무대(캔버스).** 타일맵 + 피처·함정(드러난 것만)·몹 + SD 캐릭터. 카메라는 **초점 캐릭터를 부드럽게 추적**(lerp 0.1 안팎), 뷰포트 ≈ 17×11 타일(반응형·줌 1×/1.5×). 지도 전체는 안 보여준다(미니맵 없음 — 후속 결정).
- **밝기(fog).** 가 본 곳 = 보통, 지금 초점 캐릭터의 시야 = 밝게, 미지 = 어둡게. 마을은 전부 밝게. 몹·피처는 시야 안이거나 가 본 자리의 정지물만 표시(관전자 등급 정보 — 숨은 함정·매복 몹은 **드러나기 전엔 안 그린다**: 스트림은 관전자 진실이지만 화면은 캐릭터 편에 선다).
- **초점 전환.** 우측(또는 상단) **캐릭터 칩** 3개: SD 정면 정지 프레임 크롭 초상 + 이름·직업 + HP 바 + 상태 태그. 클릭(또는 키 1·2·3)하면 카메라가 그 캐릭터로 이동(≤300ms 트윈), 초점 카드·말풍선 강조가 바뀐다. 초점 캐릭터의 시야 밖이면 칩을 흐리게(파트너 동의). 죽은 캐릭터 = 회색 칩(카메라는 묘 자리로 갈 수 있다), 먼저 내려간 캐릭터 = 별도 표식.
- **재생.** 틱 클록(1×/4×/16×), 슬라이더, 처음/끝, 라이브 따라가기(LIVE 배지). 틱 사이 이동은 트윈(한 틱 = 한 칸), 방향 = 델타, `order` 가 있으면 걷기 애니 — 없으면 정지. 층 전이(`descend`/`ascend`)는 새 level 로 무대를 갈아끼운다.
- **말풍선·지문.** `decisions[].say` 를 화자 머리 위 말풍선(제안이면 표식), `to` 가 있으면 화자가 **상대 쪽으로 몸을 돌린다**(4방향: 상대의 상대 위치). 친목 `form` 은 지문 줄("유나: *겁먹은 수나의 머리를 거칠게 쓰다듬으며 씩 웃어준다*"), 건네기 `give` 이벤트는 물건 아이콘이 둘 사이를 건너가는 트윈(+로그 "수나 → 유나: 가죽 갑옷"). 하단 로그 = 대사·지문·사건(`evLine` 이식) 시간순, 초점 캐릭터 관련 줄 강조.
- **초점 카드.** HP/최대·상태 태그·소지(물약 n·무기·방어구)·지금의 속내(`reason`)·최근 말·관계(뼈 라벨 사전 `BONES` 복사: 이야기를 나눔/함께 싸움/…/친목행위/물건을 건넴 — 횟수)·본인이 쓴 관계 한 줄(`decisions[].relation` 누적, 시트 초기값은 run_meta 에 없으므로 '아직 없음').
- **레이아웃.** 가로: 무대(좌·넓게) | 칩 열 + 초점 카드(우). 세로: 무대 아래 로그(접기 가능). 모바일은 비범위.

## 4. 프로젝트 구조(제안)

```
game/                      # Phaser 3 + TypeScript + Vite (Node 22.16 / npm 10.9 확인됨)
  package.json  vite.config.ts  tsconfig.json  index.html
  src/main.ts              # Phaser.Game 부트 · 씬 등록
  src/stream/types.ts      # 스트림 타입(STREAM_FORMAT 미러) · 파생 타입(Run, Level, Tick)
  src/stream/parse.ts      # JSONL 파서(불완전 마지막 줄 무시 — tail 규칙) · 층 조인(파일 순서)
  src/stream/live.ts       # 라이브 폴링(1.5s 재요청) · /api/status
  src/play/Playback.ts     # 틱 클록·속도·슬라이더·라이브 따라가기 · 이벤트 버스(onLevel/onTick(prev, cur, t))
  src/play/Focus.ts        # 초점 캐릭터 스토어(char) · 전환 이벤트
  src/world/Sight.ts       # 격자 LOS·가 본 곳 누적(관전 근사)
  src/scene/DungeonScene.ts# 타일맵·스프라이트·카메라 추적·이동 트윈·방향/걷기 애니
  src/scene/Fog.ts         # 밝기 레이어
  src/scene/Bubbles.ts     # 말풍선·몸 돌리기
  src/fx/Handoff.ts        # 건네기 트윈
  src/ui/Chips.ts  src/ui/FocusCard.ts  src/ui/Log.ts   # DOM 오버레이(Phaser 밖 HTML 로 두어도 됨)
  src/assets/sd.ts         # atlas.json → Phaser spritesheet/animation 등록(방향 행·걷기 열)
  src/assets/tiles.ts      # tiles.json 매핑
  verify/smoke.mjs         # Playwright 스모크(아래 §7)
```
개발: `npm run dev`(Vite, `/state`·`/runs`·`/api` 는 8000 으로 프록시). 빌드: `npm run build` → `game/dist/`. M3 에서 `launcher.py` 가 `/game/` 로 `game/dist/` 를 정적 서빙.

## 5. 마일스톤(파트너 합의)

- **M1 골격**: 판 파일(runs/) 하나를 읽어 타일·SD 캐릭터를 그리고, 카메라가 초점을 따라가고, 칩 클릭으로 초점을 바꾸고, 재생 컨트롤이 돈다(트윈·걷기 애니·층 전이 포함).
- **M2 연출·HUD**: 초점 카드, 말풍선·지문·사건 로그, 건네기 트윈, 몸 돌리기, 밝기.
- **M3 라이브·배포**: 론처 라이브 폴링, `/game/` 라우트, 빌드 스크립트, 스모크 검증, 기존 뷰어와 동등해지면 론처 기본 링크 교체(파트너 결정 후).

## 6. 울트라코드(멀티에이전트) 분할안 — 어디를 나누고 어디를 안 나누나

병렬은 **인터페이스가 고정된 뒤**에만 이득이다. 게임 클라이언트는 상태(재생 클록·초점·씬)를 공유하므로 골격을 먼저 한 손으로 세운다.

**Phase A — 솔로(선행, 병렬 금지)**: 스캐폴드 + `stream/*` + `play/*` + `assets/sd.ts` + `DungeonScene`(카메라·스프라이트·트윈·칩 전환) = **M1 전체**. 산출 = 돌아가는 M1 + 아래 인터페이스 문서(주석) — 이것이 Phase B 의 입력.

**Phase B — 병렬(각 카드 = 에이전트 1, 서로 파일 겹침 0)**:
| 카드 | 입력(고정 인터페이스) | 산출 | 수용 기준 |
|---|---|---|---|
| B1 초점 카드 | Focus·Playback 이벤트, tick.bots, decisions | `ui/FocusCard.ts` | 초점 전환 시 HP·상태·소지·속내·관계 뼈·관계 한 줄이 그 캐릭터로 바뀐다 |
| B2 말풍선·로그 | decisions(say/to/say_kind/form), events, `evLine` 사전 | `scene/Bubbles.ts`, `ui/Log.ts` | 제안 표식·지문 줄·사건 줄이 시간순, 초점 관련 줄 강조, 몸 돌리기 |
| B3 건네기 트윈 | events give(char,to,what), 스프라이트 위치 | `fx/Handoff.ts` | give 틱에 아이콘이 둘 사이를 건너간다(0.4s) |
| B4 밝기 | `world/Sight.ts`, level.grid, tick.bots | `scene/Fog.ts` | 가 본 곳/시야/미지 3단, 마을 전체 밝음, 16× 재생에 프레임 드롭 없음 |
| B5 라이브·배포 | live.ts, launcher.py | `stream/live.ts` 완성, `launcher.py` `/game/` 라우트, `npm run build` | 더미 두뇌 판 라이브 재생, 빌드 산출물이 8000 에서 열린다 |
| B6 스모크 | 전부 | `game/verify/smoke.mjs`(Playwright) | seed 257573 판 t176~t184 를 초점=수나로 재생·캡처, JS 오류 0 |

**Phase C — 솔로(통합)**: 병합·리뷰·`smoke.mjs` 통과·커밋. 각 카드의 금지 사항: `dungeon_gm.py`·`brains.py`·`show_runner.py`·`adventurer_prompt_menu.md`·`viewer/` 무수정(diff 검사로 확인), 새 에셋 제작 금지(있는 것만).

비용 메모: 울트라코드는 에이전트 수만큼 토큰을 쓴다. Phase B 6장이면 6에이전트 + 통합 1. [[feedback-token-frugality]] 대로 조사·리뷰엔 안 쓰고 **구현 카드에만** 쓴다.

## 7. 수용 기준(전체) · 검증

- **장면 재현**: 20:37 판(seed 257573, `runs/stream-20260909-203709.jsonl` 로 보존)에서 초점=수나(봇2)로 t176→t184 를 재생하면 순서대로 보인다: 고블린 m0 등장 → 유나 공격 → **가죽 갑옷 건네기 트윈**(t179) → 처치(t181) → **지문 "겁먹은 수나의 머리를 거칠게 쓰다듬으며 씩 웃어준다"**(t182) → 수나 동행(t184~). 칩 클릭 ≤300ms 전환, 250틱 16× 재생 프레임 드롭 없음, 콘솔 오류 0.
- 게이트: 기존 verify 43종은 무관(엔진 무접촉 — diff 로 증명). 새 게이트 = `game/verify/smoke.mjs`(Playwright, 헤드리스 Edge/Chromium — `art/sprites-v4/verify-browser.mjs` 선례). 커밋은 빌드+스모크 통과 조건부.
- 0콜 원칙: 리플레이 파일과 더미 두뇌 판만 쓴다. 실 LLM 판은 파트너가 [L] 로.

## 8. 열린 결정(파트너)

- 초점 기본값: 파티 1번 vs 론처에서 지정(제안: 1번, 론처 지정은 후속).
- 옛 판(`look.sprite` 없음)의 캐릭터: 직업별 기본 SD 로 폴백(제안) vs 파츠 합성 이식.
- 미니맵 유무(제안: 없음 — "맵 전체를 보여줄 필요 없다"), 사운드(없음), 모바일(비범위).
- 기존 HTML 뷰어 은퇴 시점(동등 기능 뒤, 파트너 결정).

## 9. 참고

- `STREAM_FORMAT.md` · `viewer/index.html`(evLine 사전·방향/걷기 규칙·라이브 폴링) · `viewer/assets/sprites/sprites.js`(SD 로딩 예) · `viewer/assets/sprites/sd/atlas.json` · `art/sprites-v4/README.md`(연동 규격·검토 서버) · `launcher.py`(라우트·보존 규칙) · `design/HARNESS_DESIGN.md` D37(외형)·D47 ②(건네기·친목 — `tick.replies`, `decisions.form/item`).
- 판: `runs/stream-20260909-203709.jsonl`(seed 257573, 250틱) · `runs/stream-20260909-202333.jsonl`(seed 857635, 107틱 미완).


## 10. 진행 기록 — 2026-09-09 밤(다음 세션): M1·M2·M3 구현 완료

- **Phase A(솔로, 커밋 13e05a8)** = M1 골격. Phaser **3.90.0** + TypeScript 5.9 + Vite 7 (레지스트리 최신은 Phaser 4.2·Vite 8·TS 7 이지만 §0 의 "Phaser 3" 을 따라 고정). 스트림 파서(증분·tail·파일 순서 조인·방향/이동·관전 근사 LOS·캐릭터별 본 칸·발자국)·재생 클록·초점·SD 스프라이트시트(직업별 기본 SD 폴백 = §8 제안대로)·타일(tiles.json 재사용 + 문·출구·물약·장비·NPC·묘 보충)·무대 씬·칩·컨트롤·스모크. 인터페이스 계약 = `game/README.md`.
- **Phase B(울트라코드 6카드 병렬, wf_0f75bf37 — 에이전트 6·오류 0·약 21분·서브에이전트 토큰 1.03M)** = M2·M3. 파일 겹침 0, 각 카드 자체 검증(dev 서버+헤드리스 Edge 스크린샷) 뒤 보고서.
  B1 초점 카드(`ui/FocusCard.ts`, 결정 색인 이진 탐색, BONES 복사) · B2 말풍선·지문·로그(`scene/Bubbles.ts` `ui/Log.ts` `text/evline.ts` — 뷰어 evLine 이식 + follow/rest/give/bond/NPC 어휘, 지문 "유나: *…*", 건네기 "수나 → 유나: 가죽 갑옷") · B3 건네기 트윈(`fx/Handoff.ts`, 0.4s 포물선+팝) · B4 밝기(`scene/Fog.ts`, 미지 α.88·본 곳 α.45, 서명 더티체크, 틱당 ≤1회) · B5 라이브·배포(`stream/live.ts` 백오프·`installLive` 배지·새 판 자동 재접속, `launcher.py` `/game/`→`game/dist/` 라우트·503 안내·status.game) · B6 스모크(`verify/smoke.mjs` — 실패 수집 구조, M1+M2 검사 26종).
- **Phase C(솔로 통합)**: main.ts 에 `installLive` + 오류 span 분리 · 씬 판 교체 결함 수선(B4 적발: 같은 levelIdx 면 재구축 안 됨) · style.css 중복 제거 · `WL_NOHMR` 스위치 · README 갱신 · 론처 페이지에 "게임 화면으로" 버튼(기본 링크는 그대로 — §8 파트너 결정 대기). 검증: `npm run build` OK · `npm run smoke` **25 통과·0 실패·1 생략**(라이브 배지는 론처 판에서만) · `python verify_launcher.py` ALL PASS · 엔진·프롬프트·viewer/ diff 0.
- **§7 수용 기준 실측**: 초점=수나 t176→t184 — 고블린 m0 시야 안 · t179 건네기 아이콘 0ms 등장·600ms 소멸 + 로그 "수나 → 유나: 가죽 갑옷" + 말풍선 "이거 입고" + 관계 뼈 "물건을 건넴 1" · t181 "처치" · t182 지문 overlay+log · t184 "동행" · t1 제안 말풍선 · 칩 클릭 전환 37~90ms · 16× 전체 재생 최악 프레임 간격 35ms(헤드리스) · 브라우저 오류 0.
- **임시 가정(파트너 "전부 추천으로", 09-09)**: 초점 기본=파티 1번 · 옛 판=직업별 기본 SD · `dist/` 는 ignore(론처에서 열려면 `cd game && npm run build`) · 몹 표시=초점 캐릭터 시야 · 피처 '가 본 자리'=시야에 든 적 있는 칸 · 카드들의 문구(시트/목표/아직 없음/모두/동행 줄 등)는 세션 문장 — 파트너 문장이 오면 `evline.ts`·`FocusCard.ts` 한 곳씩.
- **환경 메모**: `~/.npmrc` 의 `os=linux` 잔재(tmux 시절)를 제거(파트너 승인) — 그 전엔 rollup/esbuild 리눅스 바이너리가 깔려 빌드 실패. SD 에셋 묶음(1a97f8a)·판 파일 8개(ce7c23b)는 파트너 위임으로 이 세션이 커밋.
- **남은 것(서비스 단계로 미룸 — 파트너 "당장은 할 필요 없다")**: 다듬기(안개 α·아이콘 존재감·말풍선 배치) · 기존 HTML 뷰어 은퇴·론처 기본 링크 교체(§8) · 라이브 배지 실판 육안 · 층 2 판에서 ▼ 표식·층 전이 육안 · 미니맵 없음 유지. **서비스 골격(계정·다중 판·비용·호스팅)은 별도 토론 세션**(파트너 09-09 "라이브 서비스를 생각하고 있지 않아 우리?").

- **§8 결정(2026-09-09 밤, 파트너 "계속 새 뷰어로 보려면 그렇게 해야 하는 거야? 좀 불편한 것 같은데")**: 론처 기본 링크 = 게임 클라이언트. "관전으로"·"지난 판 보기"·시작 뒤 자동 이동이 `/game/` 으로 가고, 옛 HTML 뷰어는 타이틀의 "옛 뷰어로" 보조 버튼으로 남는다(은퇴 시점은 아직 미정). `launcher/index.html` 만 변경(정적 파일 — 론처 재시작 불필요).
