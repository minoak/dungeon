#!/usr/bin/env bash
# 봇픽던 서버 갱신 — 리포를 최신으로, 관전 클라이언트 다시 빌드, 서비스 재시작. sudo 로 실행한다.
#   sudo bash /opt/botpikdun/scripts/vm/deploy.sh
# 재시작이라 진행 중인 판은 끊긴다 — 심사 기간엔 한산한 시간에.
set -euo pipefail
APP_DIR="${BOTPIKDUN_DIR:-/opt/botpikdun}"
REF="${BOTPIKDUN_REF:-main}"
[ "$(id -u)" -eq 0 ] || { echo "sudo 로 실행해야 한다"; exit 1; }
# 초기 초안으로 설치한 VM도 실제 Gemini 호출에 필요한 패키지를 갖추도록 한다.
if ! python3 -c 'import requests' >/dev/null 2>&1; then
  apt-get update -q
  apt-get install -y -q python3-requests
fi
git -C "$APP_DIR" fetch --depth 1 origin "$REF"
git -C "$APP_DIR" reset -q --hard FETCH_HEAD
rm -f "$APP_DIR/.env"                                                  # 공개 서버엔 키 파일 없음(BYOK)
(cd "$APP_DIR/game" && npm ci --no-audit --no-fund && npm run build)
if [ -f "$APP_DIR/server.py" ]; then
  systemctl restart botpikdun
  systemctl --no-pager --lines=5 status botpikdun || true
else
  echo "!! $APP_DIR/server.py 가 없다 — 서비스는 시작하지 않는다."
fi
echo "리포: $(git -C "$APP_DIR" log --oneline -1)"
