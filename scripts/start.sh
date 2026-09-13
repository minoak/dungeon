#!/usr/bin/env bash
# 던전 관전 - tmux 분할 런처 (파티 인원에 맞춰 봇 pane 동적 = 인원 N이면 pane N+3)
# 사용법:  bash ~/dungeon/start.sh
# 빠져나오기:  Ctrl-b 누르고 d   |  다시 보기: tmux attach -t dungeon  |  끝내기: tmux kill-session -t dungeon
set -e
HERE="$HOME/dungeon"
cd "$HERE"
unset DUNGEON_STATE_DIR   # 관전 pane들은 기본 state/ 를 tail — 실험(ab_menu) 잔여 env가 남아
                          # 엔진만 딴 폴더에 쓰면 화면이 영영 '시작 대기'로 보인다(오염 방지)
mkdir -p state runs

# 지난 판 자동 보존: 새 실행이 stream.jsonl 을 truncate 하기 전에 runs/ 로 복사.
# (스트림은 관전 판의 유일한 원본 — 보고서(report.py)·소급 태깅의 입고함이기도 하다)
if [ -s state/stream.jsonl ]; then
  cp -n state/stream.jsonl "runs/stream-$(date -r state/stream.jsonl +%Y%m%d-%H%M%S).jsonl" || true
fi

# 웹 뷰어 서버(포트 8000) 보장 — 이미 떠 있으면 재사용(멱등). tmux 와 나란히 브라우저 관전 가능.
if ! curl -s -o /dev/null --max-time 1 "http://127.0.0.1:8000/viewer/tiles.json"; then
  (nohup python3 -m http.server 8000 --bind 127.0.0.1 --directory "$HERE" >/dev/null 2>&1 &)
fi
echo "관전(웹): http://localhost:8000/viewer/  (판 선택 = ⦿ 라이브)"

# 파티 char 목록 — show_runner.load_party 와 '같은 코드'로 검증(경고는 stderr, 실패=아래 "1 2" 폴백
# = show_runner 자신의 폴백과 동일 → pane 수와 실제 스폰 수가 어긋나지 않는다)
CHARS=$(python3 -c "
import show_runner as sr
print(' '.join(sorted(sr.load_party(sr.PARTY_FILE))))
" 2>/dev/null | tail -1)
[ -z "$CHARS" ] && CHARS="1 2"

rm -f state/bot*.log
for c in $CHARS; do : > "state/bot$c.log"; done
: > state/gm.log
printf '(엔진 시작 대기...)\n' > state/gm_map.txt

SES=dungeon
tmux kill-session -t "$SES" 2>/dev/null || true

# pane 0 (왼쪽 큰 패널): 전체 맵 - 깜빡임 없이 '바뀔 때만' 제자리 갱신
tmux new-session -d -s "$SES" -n show \
  "bash $HERE/watch_map.sh"

# 오른쪽 열: 봇 pane들 + 맨 아래 엔진 pane (총 M=N+1 — 연속 세로분할로 균등 높이:
#  i번째 분할 비율 = (M-i)/(M-i+1). 2인=66/50(현행 그대로), 3인=75/66/50)
set -- $CHARS
N=$#
M=$((N + 1))
i=0
for c in $CHARS; do
  if [ $i -eq 0 ]; then
    tmux split-window -h -t "$SES:show" -l 42% \
      "echo '== 봇$c  (Haiku 두뇌) =='; echo; tail -F $HERE/state/bot$c.log"
  else
    pct=$(( (M - i) * 100 / (M - i + 1) ))
    tmux split-window -v -t "$SES:show" -l ${pct}% \
      "echo '== 봇$c  (Haiku 두뇌) =='; echo; tail -F $HERE/state/bot$c.log"
  fi
  i=$((i + 1))
done

# 맨 아래: 엔진 심판/이벤트 (여기서 엔진이 실제로 돈다)
# 게임이 끝나도(정상 종료·크래시 모두) pane을 열어 둔다 — 닫히면 '알 수 없이 죽은' 것처럼 보인다.
pct=$(( (M - i) * 100 / (M - i + 1) ))
tmux split-window -v -t "$SES:show" -l ${pct}% \
  "cd $HERE; unset DUNGEON_STATE_DIR; export DUNGEON_BESTIARY_FILE=\"\${DUNGEON_BESTIARY_FILE:-$HERE/bestiary.json}\"; echo '== 엔진 심판 / 이벤트 =='; echo; python3 $HERE/show_runner.py; ec=\$?; echo; echo \"[엔진 종료 (code \$ec) - 창은 열려 있음. 나가기: Ctrl-b d / 정리: tmux kill-session -t dungeon]\"; sleep infinity"
# ↑ pane 안 unset/export 필수: pane 은 이 셸이 아니라 tmux *서버*의 env 를 상속한다 —
#   서버가 오염된 env 로 이미 떠 있으면 위(8행)의 unset 만으론 못 막는다(리뷰 실증).
#   도감 영속(bestiary.json)은 *라이브 판(여기)만* 켠다 — verify/실험은 기본 꺼짐(격리)

# pane 0(맵)을 위아래로 나눠 -> GM 연대기 (Sonnet 사관) - 맵과 분리
tmux split-window -v -t "$SES:show.0" -l 34% \
  "echo '== GM 연대기  (Sonnet 사관) =='; echo; tail -F $HERE/state/gm.log"

tmux set -t "$SES" mouse on 2>/dev/null || true
tmux select-pane -t "$SES:show.0"
tmux attach -t "$SES"
