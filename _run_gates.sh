#!/bin/bash
# [일회용] verify_*.py 게이트 개별 실행 — verify.sh(진짜 판) 아님
cd ~/dungeon
FAILED=0
for v in verify_stage1 verify_stage2 verify_stage2b verify_stage3 verify_stream \
         verify_party verify_intent verify_bestiary verify_ledger verify_menu \
         verify_plan verify_fellow verify_tags verify_interrupt verify_wire verify_scan \
         verify_potion verify_builder verify_selfstop verify_events verify_dry verify_hail \
         verify_wait verify_notes; do
  r=$(python3 "$v.py" 2>&1 | tail -1)
  echo "$v: $r"
  case "$r" in *"ALL PASS"*) ;; *) FAILED=1 ;; esac
done
exit $FAILED
