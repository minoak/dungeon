# -*- coding: utf-8 -*-
"""솔로 판 물리 점검 — LLM 끄고 dummy 폴백으로 한 판 (LLM 0콜, _smoke_bigmap 의 자매).

보는 것: 크래시·교착 없이 끝까지 도는가 / 흩어져 출발하는가 / 각자 혼자 내려가는가 /
한 명이 나가도 판이 계속되는가. **판정(주관이 있나)은 실 두뇌 판의 몫** — dummy_brain 은
캐릭터가 아니라 규칙이라 여기서 행동 분포를 읽으면 안 된다.

사용: DUNGEON_SEED=<n> python3 _smoke_solo.py
읽기: python3 analyze_run.py state_solosmoke/stream.jsonl
"""
import os

seed = os.environ.get("DUNGEON_SEED", "7")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="500", DUNGEON_W="80", DUNGEON_H="30",
                  DUNGEON_SEED=seed, DUNGEON_MONSTERS="7", DUNGEON_TRAPS="4",
                  DUNGEON_LURKERS="2", DUNGEON_POTIONS="1", DUNGEON_DEPTHS="1",
                  DUNGEON_SOLO="1", DUNGEON_PARTY_FILE="party_solo.json",
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_solosmoke"))  # 격리 — state/ 관전 판 보호
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단 — 라이브 원장 오염 방지
import brains                                                          # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백
import show_runner                                                     # noqa: E402
show_runner.STEP_DELAY = 0
show_runner.main()
