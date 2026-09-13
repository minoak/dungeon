#!/usr/bin/env bash
# 봇픽던 심사용 서버 — Ubuntu 24.04 VM 첫 설치(한 번). sudo 로 실행한다.
#   sudo BOTPIKDUN_DOMAIN=botpikdun.duckdns.org bash scripts/vm/setup.sh
# 하는 일: 패키지(git·python3·Node 22·Caddy) → 리포 클론(/opt/botpikdun, 읽기 전용) → 관전 클라이언트 빌드
#          → systemd 서비스(server.py, 127.0.0.1:8000, 전용 사용자, 쓰기는 /var/lib/botpikdun 만)
#          → Caddy(HTTPS 자동 인증서·압축·역프록시) → 시작.
# 다시 실행해도 안전하다(있는 건 건너뛰고, 리포·빌드·설정은 갱신).
# 환경변수: BOTPIKDUN_DOMAIN(필수) BOTPIKDUN_REPO BOTPIKDUN_REF BOTPIKDUN_DIR BOTPIKDUN_DATA BOTPIKDUN_PORT
set -euo pipefail

DOMAIN="${BOTPIKDUN_DOMAIN:?BOTPIKDUN_DOMAIN=<도메인> 이 필요하다 (예: botpikdun.duckdns.org)}"
REPO="${BOTPIKDUN_REPO:-https://github.com/minoak/dungeon.git}"
REF="${BOTPIKDUN_REF:-main}"
APP_DIR="${BOTPIKDUN_DIR:-/opt/botpikdun}"
DATA_DIR="${BOTPIKDUN_DATA:-/var/lib/botpikdun}"
PORT="${BOTPIKDUN_PORT:-8000}"
SVC_USER=botpikdun

[ "$(id -u)" -eq 0 ] || { echo "sudo 로 실행해야 한다"; exit 1; }
export DEBIAN_FRONTEND=noninteractive

echo "== 1/6 패키지"
apt-get update -q
apt-get install -y -q git curl ca-certificates gnupg debian-keyring debian-archive-keyring apt-transport-https python3
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | sed 's/^v//' | cut -d. -f1)" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -          # Node 22 (관전 클라이언트 빌드 전용)
  apt-get install -y -q nodejs
fi
if ! command -v caddy >/dev/null 2>&1; then                            # Caddy 공식 저장소(https://caddyserver.com/docs/install)
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi
python3 --version; node --version; caddy version

echo "== 2/6 사용자·데이터 폴더 $DATA_DIR"
id -u "$SVC_USER" >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SVC_USER"
mkdir -p "$DATA_DIR/sessions"
chown -R "$SVC_USER:$SVC_USER" "$DATA_DIR"
chmod 750 "$DATA_DIR"

echo "== 3/6 리포 $REPO ($REF) → $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$REF" && git -C "$APP_DIR" reset -q --hard FETCH_HEAD
else
  git clone -q --depth 1 --branch "$REF" "$REPO" "$APP_DIR"
fi
# 서버는 리포를 읽기만 한다(쓰기는 DATA_DIR). 키 파일은 두지 않는다 — 키는 심사위원이 판마다 가져온다(BYOK).
if [ -f "$APP_DIR/.env" ]; then echo "!! $APP_DIR/.env 가 있다 — 공개 서버엔 키 파일을 두지 않는다. 지운다."; rm -f "$APP_DIR/.env"; fi

echo "== 4/6 관전 클라이언트 빌드 (game/dist)"
(cd "$APP_DIR/game" && npm ci --no-audit --no-fund && npm run build)

echo "== 5/6 systemd 서비스 botpikdun"
sed -e "s|@APP_DIR@|$APP_DIR|g" -e "s|@DATA_DIR@|$DATA_DIR|g" -e "s|@PORT@|$PORT|g" -e "s|@USER@|$SVC_USER|g" \
  "$APP_DIR/scripts/vm/botpikdun.service" > /etc/systemd/system/botpikdun.service
systemctl daemon-reload
systemctl enable botpikdun >/dev/null 2>&1
if [ -f "$APP_DIR/server.py" ]; then
  systemctl restart botpikdun
else
  echo "!! $APP_DIR/server.py 가 아직 없다 — 서비스는 등록만 했다. 공개용 서버 코드가 리포에 들어오면 scripts/vm/deploy.sh 로 올린다."
fi

echo "== 6/6 Caddy ($DOMAIN → 127.0.0.1:$PORT)"
sed -e "s|@DOMAIN@|$DOMAIN|g" -e "s|@PORT@|$PORT|g" "$APP_DIR/scripts/vm/Caddyfile" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
systemctl enable caddy >/dev/null 2>&1
systemctl reload caddy 2>/dev/null || systemctl restart caddy

echo
echo "설치 끝."
systemctl --no-pager --lines=0 status caddy botpikdun || true
echo "주소: https://$DOMAIN/  — DNS 가 이 VM 의 외부 IP 를 가리키고 80·443 이 열려 있어야 인증서가 발급된다."
echo "확인: curl -sI https://$DOMAIN/ | head -1   (server.py 가 있으면 200, 없으면 Caddy 502)"
