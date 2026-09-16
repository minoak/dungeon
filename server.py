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
  5. 계정(D77, 2026-09-16 파트너 "api키 자체를 아이디로 쓸 수는 없어?") — **키의 지문이 계정**이다(accounts.py).
     POST /api/login {key, nick?} 이 키의 생존을 구글에 묻고(key_alive — 폐기된 키는 문이 안 열린다 = 킬 스위치), 지문(HMAC)으로
     계정을 찾거나 만들고 번호표를 묶는다. 그 뒤 이 번호표의 Ctx 는 <data>/accounts/<id>/ (state·runs·파티·캐릭터) — 기기가
     달라도 같은 키면 같은 계정, 같은 Ctx(러너 하나). 로그인 전 익명 세션의 저장 캐릭터는 들어올 때 계정으로 옮긴다.
     /api/me · /api/logout · /api/keys/link · /api/keys/unlink · /api/nick. 키는 여기서도 저장·기록되지 않는다(지문·별명만).
     로그인(=생존 확인) IP 시간당 상한 — 우리 서버를 남의 키 검사기로 못 쓰게.

실행:  python server.py --host 127.0.0.1 --port 8000     (외부는 Caddy 가 HTTPS 로 받아 넘긴다 — scripts/vm/)
환경:  BOTPIKDUN_DATA(세션·계정 폴더 뿌리, 기본 <리포>/state/public) · BOTPIKDUN_MAX_RUNS · BOTPIKDUN_START_PER_HOUR ·
       BOTPIKDUN_LOGIN_PER_HOUR(기본 30) · BOTPIKDUN_SECRET(지문 비밀 — 없으면 <data>/secret 을 첫 기동 때 만든다, 백업 대상) ·
       BOTPIKDUN_BRAIN(기본 gemini_api — 게이트 verify_public·verify_account 만 dummy)
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
import accounts as ACC                            # noqa: E402  # D77 계정 = 키 지문(파일 저장소)
from launcher import BadRequest, Conflict, Ctx, Handler, LauncherServer   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE = "botpikdun_sid"
STATIC_OK = ("/game/", "/viewer/", "/launcher/", "/art/")   # 리포에서 그대로 내주는 접두(공개 리포의 정적 자산)
SESSION_OK = ("/state/", "/runs/")                           # 세션 폴더에서 내주는 접두
ENTRY = ("/", "/launcher/", "/launcher/index.html", "/game/", "/game/index.html")   # 여기서만 새 번호표를 준다
SESSION_TTL = 24 * 3600
MAX_SESSIONS = 500                                           # 메모리에 두는 세션 상한(크롤러 방어) — 넘으면 새 번호표 거부
KEY_MIN, KEY_MAX = 20, 200
LOGIN_PER_HOUR = 30                                          # D77 로그인(=구글 생존 확인) IP 시간당 상한
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
ACCOUNT_POSTS = ("/api/login", "/api/logout", "/api/keys/link", "/api/keys/unlink", "/api/nick")


class KeyCheckUnavailable(Exception):
    """구글에 닿지 못했다(네트워크·5xx) — 키의 생사를 모른다. 계정을 만들지도 열지도 않는다."""


def key_alive(key, timeout=8):
    """키 생존 확인(D77) — 모델 목록 한 번(생성 콜 아님·과금 없음). 200=살아 있음 · 400/401/403=폐기됐거나 잘못된 키 · 그 외=모른다.
    키는 헤더(x-goog-api-key)로만 보낸다 — URL 에 실으면 예외 문구·로그에 남는다."""
    import requests                       # 지연 import — 러너와 같은 이유(미설치 환경에서 import server 가 죽지 않게)
    try:
        r = requests.get(MODELS_URL, headers={"x-goog-api-key": key}, timeout=timeout)
    except requests.RequestException as e:
        raise KeyCheckUnavailable(type(e).__name__)
    if r.status_code == 200:
        return True
    if r.status_code in (400, 401, 403):
        return False
    raise KeyCheckUnavailable("HTTP %d" % r.status_code)


KEY_CHECK = key_alive                     # 게이트(verify_account)가 바꿔 끼운다 — 실 네트워크 없이


def _env_int(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class Sessions:
    """번호표(sid) → Ctx. 폴더 = <data>/sessions/<sid>/{state,runs,party_custom.json,character_presets.json}."""

    def __init__(self, root, data_dir, brain="gemini_api", max_runs=3, starts_per_hour=12, ttl=SESSION_TTL,
                 login_per_hour=LOGIN_PER_HOUR, key_check=None):
        self.root, self.brain = root, brain
        self.max_runs, self.starts_per_hour, self.ttl = int(max_runs), int(starts_per_hour), ttl
        self.login_per_hour, self.key_check = int(login_per_hour), key_check
        self.dir = os.path.join(data_dir, "sessions")
        os.makedirs(self.dir, exist_ok=True)
        self.accounts = ACC.Accounts(data_dir)   # D77 계정 저장소(<data>/accounts·keyindex·logins·secret)
        self.lock = threading.Lock()            # ctx/seen/starts 보호
        self.start_lock = threading.Lock()      # 전체 동시 판 상한 검사 + 시작을 한 덩어리로
        self.ctx = {}                           # sid → Ctx(익명)
        self.seen = {}                          # sid → 마지막 요청 시각
        self.starts = {}                        # ip → [시작 시각]
        self.actx = {}                          # 계정 id → Ctx(계정 폴더 위, 계정당 하나)
        self.aseen = {}                         # 계정 id → 마지막 요청 시각
        self.logins = {}                        # ip → [로그인 시도 시각]

    @staticmethod
    def valid(sid):
        return isinstance(sid, str) and len(sid) == 32 and all(c in "0123456789abcdef" for c in sid)

    def get(self, sid):
        """있는 세션만. 로그인한 번호표(D77)는 계정의 Ctx — 기기가 달라도 계정 하나에 Ctx 하나(러너 하나).
        익명 번호표는 서버 재시작 뒤 폴더만 남았어도 되살린다(러너는 없음)."""
        if not self.valid(sid):
            return None
        with self.lock:
            aid = self.accounts.bound(sid)
            if aid:
                self.seen[sid] = time.time()
                return self._account_ctx(aid)
            ctx = self._anon_locked(sid)
            if ctx is not None:
                self.seen[sid] = time.time()
            return ctx

    def _anon_locked(self, sid):
        ctx = self.ctx.get(sid)
        if ctx is None and os.path.isdir(os.path.join(self.dir, sid)):
            ctx = self._make(sid)
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
            return sum(1 for c in list(self.ctx.values()) + list(self.actx.values()) if c.runner.running())

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
        for aid, ctx in list(self.actx.items()):   # D77 계정 Ctx 는 메모리에서만 내린다 — 폴더는 계정의 것이라 안 지운다
            if now - self.aseen.get(aid, now) > self.ttl and not ctx.runner.running():
                self.actx.pop(aid, None)
                self.aseen.pop(aid, None)
        self.accounts.sweep(now)                   # 30일 지난 로그인 묶음

    def sweep(self):
        with self.lock:
            self.sweep_locked(time.time())

    def stop_all(self):
        with self.lock:
            for ctx in list(self.ctx.values()) + list(self.actx.values()):
                ctx.runner.stop()

    # ── D77 계정 = 키 지문 ──
    def allow_login(self, ip):
        """로그인(=구글 생존 확인) IP 시간당 상한 — 우리 서버를 남의 키 검사기로 못 쓰게."""
        now = time.time()
        with self.lock:
            ts = [t for t in self.logins.get(ip, []) if now - t < 3600]
            if len(ts) >= self.login_per_hour:
                self.logins[ip] = ts
                return False
            ts.append(now)
            self.logins[ip] = ts
            return True

    def _account_ctx(self, aid):
        """계정 폴더 위의 Ctx(state/·runs/·파티 파일·캐릭터) — 계정당 하나(기기·번호표가 달라도 같은 러너)."""
        ctx = self.actx.get(aid)
        if ctx is None:
            d = self.accounts.folder(aid)
            os.makedirs(os.path.join(d, "state"), exist_ok=True)
            os.makedirs(os.path.join(d, "runs"), exist_ok=True)
            ctx = Ctx(self.root, os.path.join(d, "party_custom.json"), os.path.join(d, "state"), os.path.join(d, "runs"),
                      self.brain)
            ctx.sid, ctx.aid, ctx.dir = None, aid, d
            self.actx[aid] = ctx
        self.aseen[aid] = time.time()
        return ctx

    @staticmethod
    def key_shape(key):
        """키 형태만(네트워크 없음) — 문자열·길이·공백. 정제된 키를 돌려주고 아니면 BadRequest."""
        key = key.strip() if isinstance(key, str) else ""
        if not (KEY_MIN <= len(key) <= KEY_MAX) or any(c.isspace() for c in key):
            raise BadRequest("Gemini API 키를 넣어야 한다 — 키는 저장되지 않고 지문만 남는다")
        return key

    def _check_alive(self, key):
        """구글 생존 확인. 죽은 키는 BadRequest, 구글 불통은 KeyCheckUnavailable(503) — 키는 예외 문구에 안 실린다."""
        if not (self.key_check or KEY_CHECK)(key):
            raise BadRequest("키가 유효하지 않다 — 구글이 거부했다(폐기됐거나 잘못 적은 키)")

    def login(self, sid, key, nick=""):
        """키 → 생존 확인 → 지문 → 계정(없으면 생성) → 번호표 묶기 → 익명 세션의 저장 캐릭터를 계정으로 옮긴다.
        반환 (공개 모양, 새로 만들었나, 옮긴 캐릭터 수). 네트워크는 lock 밖에서."""
        self._check_alive(key)
        fp = self.accounts.fingerprint(key)
        with self.lock:
            aid = self.accounts.lookup(fp)
            created = aid is None
            if created:
                data = self.accounts.create(fp, nick)
                aid = data["id"]
            else:
                data = self.accounts.load(aid)
                if nick and not data.get("nick"):
                    data = self.accounts.set_nick(aid, nick)
            anon = self._anon_locked(sid)
            actx = self._account_ctx(aid)
            self.accounts.bind(sid, aid)
            self.seen[sid] = time.time()
            moved = self._migrate(anon, actx) if anon is not None else 0
        return self.accounts.public(data), created, moved

    @staticmethod
    def _migrate(anon, actx):
        """로그인 전 이 번호표로 저장한 캐릭터를 계정 저장소로(새 id) 옮기고 익명 쪽에서 지운다. 판 기록(runs/)은 안 옮긴다."""
        n = 0
        try:
            for p in anon.characters.list():
                actx.characters.save(p["slot"], p.get("label"))
                anon.characters.delete(p["id"])
                n += 1
        except (OSError, ValueError):
            pass                                  # 옮기다 실패해도 로그인은 성사 — 남은 것은 다음 로그인에 다시
        return n

    def logout(self, sid):
        with self.lock:
            self.accounts.unbind(sid)

    def account_of(self, sid):
        return self.accounts.bound(sid) if sid else None

    def link_key(self, aid, key):
        self._check_alive(key)
        fp = self.accounts.fingerprint(key)
        try:
            return self.accounts.public(self.accounts.link(aid, fp))
        except ACC.KeyTaken:
            raise Conflict("이 키는 이미 다른 계정에 연결돼 있다 — 그 키로 들어가 거기서 빼야 한다")

    def unlink_key(self, aid, tag):
        try:
            return self.accounts.public(self.accounts.unlink(aid, tag))
        except ValueError as e:
            raise BadRequest(str(e))

    def set_nick(self, aid, nick):
        try:
            return self.accounts.public(self.accounts.set_nick(aid, nick))
        except ValueError as e:
            raise BadRequest(str(e))


class PublicHandler(Handler):
    """Handler(론처)의 라우팅·API 를 그대로 쓰되, 세션(쿠키)이 Ctx 를 고르고, 정적 서빙은 허용 목록으로 좁힌다."""
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map,
                          **{".jsonl": "text/plain; charset=utf-8"})   # 판 파일을 text/* 로 — Caddy 압축 매치(scripts/vm/Caddyfile)

    def __init__(self, *args, sessions=None, **kwargs):
        self.sessions = sessions
        self.ctx = None
        self.sid = None                          # 이 요청의 번호표(D77 로그인 묶음에 쓴다)
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
        """쿠키의 세션. 없으면 create 일 때만 새로 만들어 응답에 쿠키를 싣는다. 로그인한 번호표면 Ctx 는 계정의 것(D77)."""
        sid = self._sid_in()
        ctx = self.sessions.get(sid)
        if ctx is None and create:
            sid, ctx = self.sessions.new()
            self._cookie_out = sid
        self.sid = sid if ctx is not None else None
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

    # ── D77 계정 ──
    def _me(self):
        aid = self.sessions.account_of(self.sid)
        data = self.sessions.accounts.load(aid) if aid else None
        return {"public": True, "logged_in": data is not None,
                "account": self.sessions.accounts.public(data) if data else None}

    def _account_post(self, p):
        """계정 API — 키는 이 함수와 Sessions.login/link_key 안에서만 살고 어디에도 안 남는다(예외 문구에도 키 없음).
        순서: 형태(네트워크 없음) → IP 상한 → 구글 생존 확인 → 지문."""
        try:
            body = self._body()
            if p == "/api/logout":
                self.sessions.logout(self.sid)
                return self._json(200, {"ok": True, "logged_in": False})
            if p == "/api/login":
                key = Sessions.key_shape(body.get("key"))
                if not self.sessions.allow_login(self._ip()):
                    return self._json(429, {"error": "이 주소에서 시도한 로그인이 너무 많다 — 한 시간에 %d번까지"
                                            % self.sessions.login_per_hour})
                acct, created, moved = self.sessions.login(self.sid, key, body.get("nick") or "")
                return self._json(200, {"ok": True, "logged_in": True, "created": created, "moved": moved, "account": acct})
            aid = self.sessions.account_of(self.sid)
            if not aid:
                return self._json(401, {"error": "먼저 키로 들어와야 한다"})
            if p == "/api/keys/link":
                key = Sessions.key_shape(body.get("key"))
                if not self.sessions.allow_login(self._ip()):
                    return self._json(429, {"error": "이 주소에서 시도한 로그인이 너무 많다 — 한 시간에 %d번까지"
                                            % self.sessions.login_per_hour})
                return self._json(200, {"ok": True, "account": self.sessions.link_key(aid, key)})
            if p == "/api/keys/unlink":
                return self._json(200, {"ok": True, "account": self.sessions.unlink_key(aid, str(body.get("tag") or ""))})
            return self._json(200, {"ok": True, "account": self.sessions.set_nick(aid, body.get("nick") or "")})
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        except Conflict as e:
            return self._json(409, {"error": str(e)})
        except KeyCheckUnavailable:
            return self._json(503, {"error": "구글에 닿지 못해 키를 확인할 수 없다 — 잠시 뒤 다시"})
        except Exception as e:                            # 이유는 예외 이름만 — 본문(키)이 섞이지 않게
            return self._json(500, {"error": type(e).__name__})

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
            obj.update(byok=True, public=True, max_runs=self.sessions.max_runs, running=self.sessions.running_count(),
                       account=self._me()["account"])                      # D77 화면이 계정 상태를 같이 읽는다
            return self._json(200, obj)
        if p == "/api/me":                                            # D77 계정 상태 — 론처 화면의 계정 카드
            return self._json(200, self._me())
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path
        if not p.startswith("/api/"):
            return self._json(404, {"error": "없는 경로"})
        try:
            self._session(create=True)
        except Conflict as e:
            return self._json(429, {"error": str(e)})
        if p in ACCOUNT_POSTS:
            return self._account_post(p)                              # D77 계정 — 키는 함수 안에서만 산다
        if p != "/api/start":
            return super().do_POST()                                  # party·characters·retry·oracle·stop — 세션(또는 계정)의 Ctx 로
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
                extra = {"GEMINI_API_KEY": key, "ANTHROPIC_API_KEY": "", "DUNGEON_BRAIN_FALLBACK": ""}
                if getattr(self.ctx, "aid", None):        # D78(09-16) 계정 판: 도감 원장은 계정 폴더에, 저장한 캐릭터(id)만 남는다
                    body["bestiary"] = True
                    extra["DUNGEON_BESTIARY_FILE"] = os.path.join(self.ctx.dir, "bestiary.json")
                    extra["DUNGEON_LEDGER_IDS_ONLY"] = "1"
                else:
                    body["bestiary"] = False             # D64 — 익명 세션은 원장 이월 없음(판 안 학습만)
                return self._json(200, self.ctx.runner.start(body, self.ctx.party_path, self.sessions.brain,
                                                             extra_env=extra))
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        except Conflict as e:
            return self._json(409, {"error": str(e)})
        except Exception as e:                            # 이유는 예외 이름만 — 본문(키)이 섞이지 않게
            return self._json(500, {"error": type(e).__name__})


def make_public_server(host, port, root=HERE, data_dir=None, brain=None, max_runs=None, starts_per_hour=None,
                       login_per_hour=None, key_check=None):
    sessions = Sessions(root,
                        data_dir or os.environ.get("BOTPIKDUN_DATA") or os.path.join(root, "state", "public"),
                        brain or os.environ.get("BOTPIKDUN_BRAIN") or "gemini_api",
                        max_runs if max_runs is not None else _env_int("BOTPIKDUN_MAX_RUNS", 3),
                        starts_per_hour if starts_per_hour is not None else _env_int("BOTPIKDUN_START_PER_HOUR", 12),
                        login_per_hour=login_per_hour if login_per_hour is not None else _env_int("BOTPIKDUN_LOGIN_PER_HOUR", LOGIN_PER_HOUR),
                        key_check=key_check)
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
    print("[server] http://%s:%d/  세션 폴더=%s  계정 폴더=%s  동시 판 상한=%d  IP 시간당 시작=%d  로그인=%d  두뇌=%s"
          % (a.host, a.port, s.dir, s.accounts.dir, s.max_runs, s.starts_per_hour, s.login_per_hour, s.brain))

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
