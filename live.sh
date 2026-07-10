#!/usr/bin/env bash
# ⚠️ 이 스크립트는 *진짜 판*을 돌린다 (state/ 를 새로 쓴다) — 검증 스위트 아님.
#
# 라이브 관전(헤들리스) 원커맨드: 지난 판 보존 → 웹 뷰어 서버 보장 → 게임 실행.
# 관전은 브라우저에서: http://localhost:8000/viewer/  (판 선택 = ⦿ 라이브)
# tmux 5분할로 보고 싶으면 start.sh (보존·도감 동일, GM 기본 켬).
#
# 사용법:  bash ~/dungeon/live.sh
#   env 로 조절: DUNGEON_SEED / DUNGEON_TURNS / DUNGEON_W·H 등 show_runner 의 전부.
#   DUNGEON_GM 기본 0 — 뷰어에 GM 내레이션 칸이 없어(v0) 켜면 보이지 않는 Sonnet 콜만 나간다.
set -e
HERE="$HOME/dungeon"
cd "$HERE"
unset DUNGEON_STATE_DIR   # 실험(ab_menu 등) 잔여 env 오염 방지 — start.sh 와 동일
mkdir -p state runs

# 지난 판 자동 보존: 새 실행이 stream.jsonl 을 truncate 하기 전에 runs/ 로 복사 (start.sh 와 같은 규칙)
if [ -s state/stream.jsonl ]; then
  cp -n state/stream.jsonl "runs/stream-$(date -r state/stream.jsonl +%Y%m%d-%H%M%S).jsonl" || true
fi

# 웹 뷰어 서버(포트 8000) 보장 — 이미 떠 있으면 재사용(멱등).
# dungeon 루트를 서빙해야 /viewer/ 가 /runs/·/state/ 를 fetch 할 수 있다 (VIEWER_DESIGN §3).
if ! curl -s -o /dev/null --max-time 1 "http://127.0.0.1:8000/viewer/tiles.json"; then
  (nohup python3 -m http.server 8000 --bind 127.0.0.1 --directory "$HERE" >/dev/null 2>&1 &)
  sleep 0.5
fi

echo "관전: http://localhost:8000/viewer/   (판 선택 = ⦿ 라이브, 재생 위치를 끝에 두면 따라감)"
echo "중단: Ctrl-C  — 지난 판은 runs/ 에 이미 보존돼 있음"
echo

# 도감 영속은 라이브 판만 켠다 (start.sh 와 동일 — verify/실험은 기본 꺼짐=격리)
export DUNGEON_BESTIARY_FILE="${DUNGEON_BESTIARY_FILE:-$HERE/bestiary.json}"
export DUNGEON_GM="${DUNGEON_GM:-0}"
exec python3 "$HERE/show_runner.py"
