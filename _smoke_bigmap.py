# -*- coding: utf-8 -*-
"""큰 판 1층 물리 점검 — LLM 끄고 dummy 폴백으로 PD급 판 한 판 (LLM 0콜).
크래시·교착·완주 틱수만 본다. 판정(육안)은 민옥 라이브 몫.
사용: DUNGEON_SEED=<n> python3 _smoke_bigmap.py"""
import os
seed = os.environ.get("DUNGEON_SEED", "7")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="500", DUNGEON_W="80", DUNGEON_H="30",
                  DUNGEON_SEED=seed, DUNGEON_MONSTERS="7", DUNGEON_TRAPS="4",
                  DUNGEON_LURKERS="2", DUNGEON_POTIONS="1", DUNGEON_DEPTHS="1",
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_bigsmoke"))  # 격리 — state/ 관전 판 보호
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단 — 라이브 원장 오염 방지
import brains
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백
import show_runner
show_runner.STEP_DELAY = 0
show_runner.main()
