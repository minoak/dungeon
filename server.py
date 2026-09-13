# -*- coding: utf-8 -*-
"""봇픽던 공개(심사용) 서버 — launcher.py 를 심사위원(세션)별로 감싼다. 2026-09-13, 챔피언십 심사(9/21~10/5)용. D68.

launcher.py 는 로컬 도구다: 리포 루트 전체를 정적으로 내주고(.env 포함), 판 시작에 인증이 없고, 판이 하나뿐이다.
이 서버는 그 위에 네 가지만 더한다 — 엔진·러너·관전 클라이언트·론처 화면은 무변경(경로가 같다, 쿠키가 폴더를 고른다).
  1. 세션 — 쿠키 번호표(botpikdun_sid) 하나에 Ctx 하나: state/·runs/·파티 파일·저장 캐릭터가 전부
     <BOTPIKDUN_DATA>/sessions/<id>/ 아래. 24시간 안 오면 메모리에서 내린다(판 기록이 있는 폴더는 남기고, 쿠키가 오면 되살린다).
  2. 정적 허용 목록 — /game/(빌드)·/viewer/·/launcher/·/art/ 와 자기 세션의 /state/·/runs/ 만. 나머지는 404.
     디렉터리 목록은 자기 세션의 /runs/ 만. 점으로 시작하는 파일과 .py 는 어디서도 안 내준다.
  3. BYOK — 판 시작 요청의 key 가 그 판 러너의 GEMINI_API_KEY 환경변수로만 들어간다(보관 없는 세션형, D10 서랍).
     디스크·로그·응답에 남기지 않는다. 서버 자체의 키·대체 두뇌는 러너에 물려주지 않는다.
  4. 상한 — 서버 전체 동시 max_runs(기본 3)판 · 세션당 1판(Runner 그대로) · IP 당 시간당 시작 starts_per_hour(기본 12).

실행:  python server.py --host 127.0.0.1 --port 8000     (외부는 Caddy 가 HTTPS 로 받아 넘긴다 — scripts/vm/)
환경:  BOTPIKDUN_DATA(세션 폴더 뿌리, 기본 <리포>/state/public) · BOTPIKDUN_MAX_RUNS · BOTPIKDUN_START_PER_HOUR ·
       BOTPIKDUN_BRAIN(기본 gemini_api — 게이트 verify_public 만 dummy)
"""
import argparse
import os
import secrets
import shutil
import sys
import threading
import time
from functools import partial
from http import cookies
from http.server import SimpleHTTPRequestHandler
from urllib.parse import unquote, urlparse

import launcher                                   # noqa: E402
from launcher import BadRequest, Conflict, Ctx, Handler, LauncherServer   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE = "botpikdun_sid"
STATIC_OK = ("/game/", "/viewer/", "/launcher/", "/art/")   # 리포에서 그대로 내주는 접두(공개 리포의 정적 자산)
SESSION_OK = ("/state/", "/runs/")                           # 세션 폴더에서 내주는 접두
ENTRY = ("/", "/launcher/", "/launcher/index.html", "/game/", "/game/index.html")   # 여기서만 새 번호표를 준다
SESSION_TTL = 24 * 3600
MAX_SESSIONS = 500                                           # 메모리에 두는 세션 상한(크롤러 방어) — 넘으면 새 번호표 거부
KEY_MIN, KEY_MAX = 20, 200


def _env_int(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class Sessions:
    """번호표(sid) → Ctx. 폴더 = <data>/sessions/<sid>/{state,runs,party_custom.json,character_presets.json}."""

    def __init__(self, root, data_dir, brain="gemini_api", max_runs=3, starts_per_hour=12, ttl=SESSION_TTL):
        self.root, self.brain = root, brain
        self.max_runs, self.starts_per_hour, self.ttl = int(max_runs), int(starts_per_hour), ttl
        self.dir = os.path.join(data_dir, "sessions")
        os.makedirs(self.dir, exist_ok=True)
        self.lock = threading.Lock()            # ctx/seen/starts 보호
        self.start_lock = threading.Lock()      # 전체 동시 판 상한 검사 + 시작을 한 덩어리로
        self.ctx = {}                           # sid → Ctx
        self.seen = {}                          # sid → 마지막 요청 시각
        self.starts = {}                        # ip → [시작 시각]

    @staticmethod
    def valid(sid):
        return isinstance(sid, str) and len(sid) == 32 and all(c in "0123456789abcdef" for c in sid)

    def get(self, sid):
        """있는 세션만. 서버 재시작 뒤 폴더만 남은 번호표는 되살린다(러너는 없음)."""
        if not self.valid(sid):
            return None
        with self.lock:
            ctx = self.ctx.get(sid)
            if ctx is None and os.path.isdir(os.path.join(self.dir, sid)):
                ctx = self._make(sid)
            if ctx is not None:
                self.seen[sid] = time.time()
            return ctx

    def new(self):
        with self.lock:
            if len(self.ctx) >= MAX_SESSIONS:
                self.sweep_locked(time.time())
                if len(self.ctx) >= MAX_SESSIONS:
                    raise Conflict("자리가 없다 — 잠시 뒤에 다시")
            sid = secrets.token_hex(16)
            return sid, self._make(sid)

    def _make(self, sid):
        d = os.path.join(self.dir, sid)
        os.makedirs(os.path.join(d, "state"), exist_ok=True)
        os.makedirs(os.path.join(d, "runs"), exist_ok=True)
        ctx = Ctx(self.root, os.path.join(d, "party_custom.json"), os.path.join(d, "state"), os.path.join(d, "runs"),
                  self.brain)
        ctx.sid, ctx.dir = sid, d
        self.ctx[sid] = ctx
        self.seen[sid] = time.time()
        return ctx

    def running_count(self):
        with self.lock:
            return sum(1 for c in self.ctx.values() if c.runner.running())

    def allow_start(self, ip):
        now = time.time()
        with self.lock:
            ts = [t for t in self.starts.get(ip, []) if now - t < 3600]
            if len(ts) >= self.starts_per_hour:
                self.starts[ip] = ts
                return False
            ts.append(now)
            self.starts[ip] = ts
            return True

    def sweep_locked(self, now):
        """TTL 지난 세션(러너 없음)을 메모리에서 내린다. 판 기록(runs/)이 없는 폴더는 지우고, 있는 폴더는 남긴다."""
        for sid, ctx in list(self.ctx.items()):
            if now - self.seen.get(sid, now) > self.ttl and not ctx.runner.running():
                self.ctx.pop(sid, None)
                self.seen.pop(sid, None)
                try:
                    if not os.listdir(ctx.runs_dir):
                        shutil.rmtree(ctx.dir, ignore_errors=True)
                except OSError:
                    pass

    def sweep(self):
        with self.lock:
            self.sweep_locked(time.time())

    def stop_all(self):
        with self.lock:
            for ctx in self.ctx.values():
                ctx.runner.stop()


class PublicHandler(Handler):
    """Handler(론처)의 라우팅·API 를 그대로 쓰되, 세션(쿠키)이 Ctx 를 고르고, 정적 서빙은 허용 목록으로 좁힌다."""
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map,
                          **{".jsonl": "text/plain; charset=utf-8"})   # 판 파일을 text/* 로 — Caddy 압축 매치(scripts/vm/Caddyfile)

    def __init__(self, *args, sessions=None, **kwargs):
        self.sessions = sessions
        self.ctx = None
        self._cookie_out = None
        SimpleHTTPRequestHandler.__init__(self, *args, directory=sessions.root, **kwargs)   # Handler.__init__ 는 ctx 필수라 건너뜀

    # ── 세션 ──
    def _sid_in(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw)
        except cookies.CookieError:
            return None
        m = jar.get(COOKIE)
        return m.value if m else None

    def _session(self, create):
        """쿠키의 세션. 없으면 create 일 때만 새로 만들어 응답에 쿠키를 싣는다."""
        ctx = self.sessions.get(self._sid_in())
        if ctx is None and create:
            sid, ctx = self.sessions.new()
            self._cookie_out = sid
        self.ctx = ctx
        return ctx

    def _ip(self):
        xff = self.headers.get("X-Forwarded-For", "")
        return (xff.split(",")[0].strip() if xff else "") or self.client_address[0]

    def end_headers(self):
        if self._cookie_out:
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
            self.send_header("Set-Cookie", "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax%s"
                             % (COOKIE, self._cookie_out, 30 * 86400, secure))
            self._cookie_out = None
        super().end_headers()

    # ── 정적: 허용 목록 ──
    def _denied(self):
        return os.path.join(self.sessions.root, "__denied__")      # 없는 경로 → 부모가 404

    def translate_path(self, path):
        p = unquote(urlparse(path).path)
        parts = [w for w in p.split("/") if w]
        if any(w.startswith(".") or w.endswith(".py") for w in parts):
            return self._denied()
        for pre, attr in (("/state/", "state_dir"), ("/runs/", "runs_dir")):
            if p.startswith(pre):
                if self.ctx is None:
                    return self._denied()
                rel = [w for w in p[len(pre):].split("/") if w and w not in (".", "..") and os.path.dirname(w) == ""]
                return os.path.join(getattr(self.ctx, attr), *rel)
        if p.startswith(STATIC_OK):
            return super().translate_path(path)                       # /game/ → game/dist, 나머지는 리포 루트 기준
        return self._denied()

    def list_directory(self, path):
        if self.ctx is not None and os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(self.ctx.runs_dir)):
            return super().list_directory(path)                       # 자기 세션의 판 목록(관전 클라이언트 드롭다운)
        self.send_error(404)                                          # 상태 줄은 latin-1 만 — 한글 메시지 금지(응답이 끊긴다)
        return None

    # ── 라우팅 ──
    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/healthz":
            return self._json(200, {"ok": True, "running": self.sessions.running_count(), "max_runs": self.sessions.max_runs})
        if p == "/favicon.ico":                                        # 브라우저가 알아서 찾는 것 — 콘솔 404 소음 없이 빈 응답
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not (p.startswith("/api/") or p.startswith(SESSION_OK) or p.startswith(STATIC_OK) or p in ("/", "/game")):
            return self._json(404, {"error": "없는 경로"})
        try:
            self._session(create=p.startswith("/api/") or p.startswith(SESSION_OK) or p in ENTRY or p == "/game")
        except Conflict as e:
            return self._json(429, {"error": str(e)})
        if (p.startswith("/api/") or p.startswith(SESSION_OK)) and self.ctx is None:
            return self._json(404, {"error": "세션 없음"})
        if p == "/api/presets":
            obj = launcher.presets_payload(self.ctx)
            obj.update(byok=True, public=True, max_runs=self.sessions.max_runs, running=self.sessions.running_count())
            return self._json(200, obj)
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path
        if not p.startswith("/api/"):
            return self._json(404, {"error": "없는 경로"})
        try:
            self._session(create=True)
        except Conflict as e:
            return self._json(429, {"error": str(e)})
        if p != "/api/start":
            return super().do_POST()                                  # party·characters·retry·oracle·stop — 세션의 Ctx 로
        try:
            body = self._body()
            key = body.pop("key", None)
            key = key.strip() if isinstance(key, str) else ""
            if not (KEY_MIN <= len(key) <= KEY_MAX) or any(c.isspace() for c in key):
                raise BadRequest("Gemini API 키를 넣어야 한다 — 이 판에만 쓰이고 서버에 남지 않는다")
            with self.sessions.start_lock:
                if self.ctx.runner.running():
                    raise Conflict("이미 판이 진행 중이다 — 중지하거나 끝나길 기다려라")
                if self.sessions.running_count() >= self.sessions.max_runs:
                    return self._json(429, {"error": "지금 동시에 도는 판이 %d개라 자리가 없다 — 몇 분 뒤 다시"
                                            % self.sessions.max_runs})
                if not self.sessions.allow_start(self._ip()):
                    return self._json(429, {"error": "이 주소에서 시작한 판이 너무 많다 — 한 시간에 %d판까지"
                                            % self.sessions.starts_per_hour})
                body["brain"] = self.sessions.brain      # 공개 서버의 두뇌는 하나(BYOK Gemini) — 화면의 선택은 무시
                body["bestiary"] = False                 # D64 — 원장 이월 없음(판 안 학습만)
                extra = {"GEMINI_API_KEY": key, "ANTHROPIC_API_KEY": "", "DUNGEON_BRAIN_FALLBACK": ""}
                return self._json(200, self.ctx.runner.start(body, self.ctx.party_path, self.sessions.brain,
                                                             extra_env=extra))
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        except Conflict as e:
            return self._json(409, {"error": str(e)})
        except Exception as e:                            # 이유는 예외 이름만 — 본문(키)이 섞이지 않게
            return self._json(500, {"error": type(e).__name__})


def make_public_server(host, port, root=HERE, data_dir=None, brain=None, max_runs=None, starts_per_hour=None):
    sessions = Sessions(root,
                        data_dir or os.environ.get("BOTPIKDUN_DATA") or os.path.join(root, "state", "public"),
                        brain or os.environ.get("BOTPIKDUN_BRAIN") or "gemini_api",
                        max_runs if max_runs is not None else _env_int("BOTPIKDUN_MAX_RUNS", 3),
                        starts_per_hour if starts_per_hour is not None else _env_int("BOTPIKDUN_START_PER_HOUR", 12))
    srv = LauncherServer((host, port), partial(PublicHandler, sessions=sessions))
    srv.daemon_threads = True
    srv.sessions = sessions
    return srv


def main():
    ap = argparse.ArgumentParser(description="봇픽던 공개(심사용) 서버 — 세션별 러너, BYOK(키는 판마다 심사위원이 가져온다)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    try:
        srv = make_public_server(a.host, a.port)
    except OSError as e:
        print("[server] %s:%d 를 열 수 없다(%s)" % (a.host, a.port, e), file=sys.stderr)
        return 1
    s = srv.sessions
    print("[server] http://%s:%d/  세션 폴더=%s  동시 판 상한=%d  IP 시간당 시작=%d  두뇌=%s"
          % (a.host, a.port, s.dir, s.max_runs, s.starts_per_hour, s.brain))

    def sweeper():
        while True:
            time.sleep(600)
            try:
                s.sweep()
            except Exception as e:                    # 청소 실패로 서버가 죽지 않게
                print("[server] sweep: %s" % type(e).__name__, file=sys.stderr)
    threading.Thread(target=sweeper, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        s.stop_all()
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
