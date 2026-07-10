#!/usr/bin/env bash
# ⚠️ tmux 레이아웃 스냅샷 도구 — 코드 검증 스위트가 아니다(그건 verify_*.py 8종+verify_tags.py).
#    이 스크립트는 *실제 판을 8초 실행*하므로 state/ 를 덮어쓴다.
# 헤드리스 검증: 분할(파티 인원 동적) 띄우고 8초 돌린 뒤 각 패널 텍스트 스냅샷
HERE="$HOME/dungeon"
cd "$HERE"
unset DUNGEON_STATE_DIR   # 스냅샷 pane들은 기본 state/ 고정(start.sh와 동일한 오염 방지)
mkdir -p state runs

# 지난 판 자동 보존(start.sh 와 동일) — 2026-07-05 아침판 소실 사고 재발 방지
if [ -s state/stream.jsonl ]; then
  cp -n state/stream.jsonl "runs/stream-$(date -r state/stream.jsonl +%Y%m%d-%H%M%S).jsonl" || true
fi

CHARS=$(python3 -c "
import show_runner as sr
print(' '.join(sorted(sr.load_party(sr.PARTY_FILE))))
" 2>/dev/null | tail -1)
[ -z "$CHARS" ] && CHARS="1 2"

rm -f state/bot*.log
for c in $CHARS; do : > "state/bot$c.log"; done
printf '(엔진 시작 대기...)\n' > state/gm_map.txt

SES=dverify
tmux kill-session -t "$SES" 2>/dev/null || true

# 검증용으로 큰 가상 화면(200x50)에 띄워야 스냅샷이 안 잘림
tmux new-session -d -s "$SES" -n show -x 200 -y 50 \
  "while :; do clear; cat $HERE/state/gm_map.txt 2>/dev/null; sleep 0.3; done"
set -- $CHARS
N=$#
M=$((N + 1))
i=0
for c in $CHARS; do
  if [ $i -eq 0 ]; then
    tmux split-window -h -t "$SES:show" -l 42% \
      "echo '== 봇$c =='; echo; tail -F $HERE/state/bot$c.log"
  else
    pct=$(( (M - i) * 100 / (M - i + 1) ))
    tmux split-window -v -t "$SES:show" -l ${pct}% \
      "echo '== 봇$c =='; echo; tail -F $HERE/state/bot$c.log"
  fi
  i=$((i + 1))
done
pct=$(( (M - i) * 100 / (M - i + 1) ))
tmux split-window -v -t "$SES:show" -l ${pct}% \
  "cd $HERE; unset DUNGEON_STATE_DIR DUNGEON_BESTIARY_FILE; echo '== 엔진 이벤트 =='; echo; python3 $HERE/show_runner.py"
# ↑ DUNGEON_BESTIARY_FILE 도 unset — 이 스냅샷 판(더미 8초)이 라이브 도감 원장을 읽거나
#   더미 획득을 영구 기록하면 캐릭터의 '죽어도 남는 재산'이 오염된다(도감 격리, 리뷰 픽스)

sleep 8

echo "########## LAYOUT ##########"
tmux list-panes -t "$SES" -F 'pane #{pane_index}:  #{pane_width} x #{pane_height}'
for p in $(tmux list-panes -t "$SES" -F '#{pane_index}'); do
  echo "########## PANE $p ##########"
  tmux capture-pane -p -t "$SES:show.$p"
done
tmux kill-session -t "$SES"
echo "########## DONE ##########"
