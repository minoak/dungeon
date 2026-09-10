#!/bin/bash
# [일회용] verify_*.py 게이트 개별 실행 — verify.sh(진짜 판) 아님
# WSL 은퇴(08-09): 스크립트 위치 기준 cd + python/python3 자동 — Git Bash(Windows)에서도 돈다
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
export PYTHONUTF8=1
# 과거 동작의 회귀 검사는 명시적으로 메뉴형. 조합형 게이트는 파일 안에서 compose를 설정한다.
export DUNGEON_ACTION_MODE=menu
FAILED=0
for v in verify_stage1 verify_stage2 verify_stage2b verify_stage3 verify_stream \
         verify_party verify_intent verify_bestiary verify_ledger verify_menu \
         verify_plan verify_fellow verify_tags verify_interrupt verify_wire verify_scan \
         verify_potion verify_builder verify_selfstop verify_events verify_dry verify_hail \
         verify_wait verify_notes verify_motion verify_brain verify_ally verify_archer verify_social \
         verify_solo verify_gear verify_town verify_launcher verify_character_presets verify_status verify_rest verify_relations \
         verify_trail verify_objtags verify_floor verify_sayto verify_saykind verify_give verify_bond verify_compose verify_approach verify_action_system verify_reactions; do
  r=$("$PY" "$v.py" 2>&1 | tail -1)
  echo "$v: $r"
  case "$r" in *"ALL PASS"*) ;; *) FAILED=1 ;; esac
done
exit $FAILED
