# 리포 지도 (2026-09-13 정리 1단계)

> 파트너 "지금 깃허브 파일이 꽤 지저분하거든 … 지금이 한번 정리할 때" → "뭘 버려야 할지 감이 안 잡혀" → 기준을 정해 한 커밋으로 만들고
> 눈으로 보고 정하기로 함. **지운 파일은 git 이력에 그대로 남는다** — 아래 '이력에서 꺼내는 법' 참고.

## 기준 넷

1. **실행에 필요한가** → 남긴다. 엔진·러너·론처·데이터·프롬프트·엔티티 정의·클라이언트.
2. **지금도 쓰는 검증·도구인가** → 남기되 폴더로 모은다. 게이트 61종(`verify_*.py`, 2단계에서 `verify/` 로), 부검·리플레이 도구(`tools/`).
3. **끝난 실험의 산출물인가** → 지운다(이력에 있음). 7월 메뉴·페르소나 A/B 산출과 보고서, 죽은 스크립트, 보류한 스파이크.
4. **판 기록(runs/)과 그림 원본(art/)** → 이번엔 안 건드린다(3단계 — 파트너 결정).

## 지금 구조

```
README.md · LICENSE(MIT) · .env.example · wonderland.bat · live.bat · _run_gates.sh · STREAM_FORMAT.md
엔진·러너·론처(루트, import 이름 그대로):
  dungeon_gm.py brains.py show_runner.py launcher.py entities.py bestiary.py sheetkit.py scenario.py
  run_control.py run_summary.py movement_summary.py composed_actions.py skill_core.py skill_combat.py skill_schema.py
  social_reactions.py town_layout.py town_spaces.py stream.py tags.py gm.py envload.py character_presets.py
데이터(루트, 참조 60곳이라 유지): party.json party_solo.json party_crossed.json traits.json looks.json town.json town-v0.json
prompts/     adventurer_prompt.md(조합형 지침) context_prompt.md(D54 앞머리) gm_prompt.md social_prompt.md
             legacy/2026-09-10/(메뉴형·자유서술형 — 게이트가 메뉴형으로 돈다: 삭제 금지) legacy/2026-09-11/
tools/       analyze_run.py analyze_skills.py analyze_social.py report.py make_replay_viewer.py replay_viewer.html
             maze_metrics.py check_town.py run_skill_alpha.py ab_menu.py(verify_plan 이 파서로 import) ab_persona.py run_notes.py
scripts/     start.sh live.sh verify.sh watch_map.sh (Linux/WSL 시대 — 전부 `~/dungeon` 을 가정, VPS 서빙 때 손볼 것)
verify_*.py  게이트 61종(루트 — 2단계에서 verify/ 로 이동 예정)
entities/    몬스터·함정·오브젝트·NPC·맵·건물·의뢰 정의(D50)
design/      HARNESS_DESIGN.md(D1~D67) · drafts/
docs/        문서·연대기·데브로그·스크린샷 · PIXEL_DUNGEON_REFERENCE.md(참고 게임 메모)
game/        관전 클라이언트(Phaser+Vite) · verify/smoke.mjs
viewer/      옛 HTML 뷰어 + 공용 에셋(타일·스프라이트)
launcher/    론처 화면(index.html)
scenarios/   프로브 장면
runs/        판 기록(스트림 jsonl, 원본 데이터)   art/  그림 원본·습작(82MB)
state/       실행 폴더(.gitkeep 만 추적 — 로그·스트림은 실행 흔적이라 미추적)
```

## 이번 커밋에서 옮긴 것

| 전 | 후 | 손댄 참조 |
|---|---|---|
| `adventurer_prompt.md` `context_prompt.md` `gm_prompt.md` `social_prompt.md` | `prompts/` | brains `_load_prompt`·`_load_context`, gm.py |
| `backups/prompts/` | `prompts/legacy/` | brains `LEGACY_PROMPT_DIR`(verify_relations·verify_rest 는 이 상수를 따라간다), README, STREAM_FORMAT |
| 분석·부검·리플레이 도구 12개 | `tools/` | 각 파일 첫 import 앞에 리포 루트 sys.path 부트스트랩, `HERE`/`root` 는 리포 루트로 재정의(의미 보존) · verify_plan·verify_skill_stream 은 `tools/` 를 sys.path 에 · wonderland.bat 안내 문구 · README·game/README 명령 |
| `start.sh` `live.sh` `verify.sh` `watch_map.sh` | `scripts/` | show_runner 안내 문구, live.bat 주석 |
| `PIXEL_DUNGEON_REFERENCE.md` | `docs/` | 없음 |

## 이번 커밋에서 지운 것(이력에 있음)

| 대상 | 무엇이었나 | 왜 |
|---|---|---|
| `ab_runs/`(209) · `reports/`(15) | 7월 메뉴형/페르소나 A/B 실험의 판 로그·HTML 보고서(8.5MB) | 결론은 HARNESS_DESIGN 에 있고 재현은 `tools/ab_menu.py`·`ab_persona.py` 로 가능. 앞으로 생기면 .gitignore |
| `_smoke_bigmap.py` `_smoke_solo.py` `_smoke_stage2.py` `_test_fallback_labels.py` `_check_key.py` `measure_concurrency.py` | 초기 스모크·측정 스크립트 | 어디서도 부르지 않음(참조 0) — 게이트 61종이 대신함 |
| `risu/` | RisuAI 플러그인 스파이크(07-29 보류) | 보류 상태 그대로, 필요하면 이력에서 |
| `state/*` 추적 | 실행 로그·스트림 | 판을 돌릴 때마다 커밋 잡음 — 폴더만 `.gitkeep` |

## 이력에서 꺼내는 법

```bash
git log --oneline --all -- ab_runs | head -3          # 언제까지 있었나
git show <해시>:reports/free_s1.html > /tmp/free_s1.html   # 파일 하나 꺼내기
git checkout <해시>^ -- risu/                            # 폴더 통째로 되살리기(그 커밋의 부모 시점)
```

## 다음 단계(파트너 결정)

- **2단계**: `verify_*.py` 61개 + `verify_character_presets_browser.mjs` → `verify/`, `_run_gates.sh` 도 함께. 각 게이트의 `HERE` 를 리포 루트로 재정의하고 sys.path 를 넣는 일괄 치환 — 게이트 61종 통과가 곧 검증.
- **3단계**: `art/` 82MB(그림 원본·습작 — 런타임은 `viewer/assets`·`game/src/assets` 만 읽는다) → Git LFS 또는 릴리스 첨부 · `runs/` 48MB(판 107개) → 대표 판 유지, 스모크·중단 판 정리 여부.
- README 첫 화면 재편(외부 이름 확정 뒤).
