# -*- coding: utf-8 -*-
"""show_runner 라이브 배선 스모크 — LLM(Haiku) 끄고 폴백(dummy)으로 틱 루프 한 판.
think_all 스킵·step_order 자동보행·act_summary·write_map·근접 inbox 가 크래시 없이 도는지."""
import os
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="120", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="3", DUNGEON_TRAPS="3",
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_smoke2"))  # 격리 — state/ 관전 판 truncate 방지
import brains
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 호출 무력화 → claude_brain이 dummy 폴백
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(리뷰 픽스) — 셸/tmux env 잔재가 라이브 원장을 읽고 쓰는 오염 방지
import show_runner
show_runner.STEP_DELAY = 0                                # 딜레이 제거(빨리)
show_runner.main()
print("\n=== 최종 맵 (state/gm_map.txt) ===")
print(open(os.path.join(show_runner.STATE, "gm_map.txt"), encoding="utf-8").read())
