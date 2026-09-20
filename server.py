# -*- coding: utf-8 -*-
"""봇픽던 공개(심사용) 서버 — launcher.py 를 심사위원(세션)별로 감싼다. 2026-09-13, 챔피언십 심사(9/21~10/5)용. D68.

launcher.py 는 로컬 도구다: 리포 루트 전체를 정적으로 내주고(.env 포함), 판 시작에 인증이 없고, 판이 하나뿐이다.
이 서버는 그 위에 네 가지만 더한다 — 엔진·러너·관전 클라이언트·론처 화면은 무변경(경로가 같다, 쿠키가 폴더를 고른다).
  1. 세션 — 쿠키 번호표(botpikdun_sid) 하나에 Ctx 하나: state/·runs/·파티 파일·저장 캐릭터가 전부
     <BOTPIKDUN_DATA>/sessions/<id>/ 아래. 24시간 안 오면 메모리에서 내린다(판 기록이 있는 폴더는 남기고, 쿠키가 오면 되살린다).
  2. 정적 허용 목록 — /game/(빌드)·/viewer/·/launcher/·/art/ 와 자기 세션의 /state/·/runs/ 만. 나머지는 404.
     디렉터리 목록은 자기 세션의 /runs/ 만. 점으로 시작하는 파일과 .py 는 어디서도 안 내준다.
  3. BYOK — 판 시작 요청의 provider 에 맞는 회사 키 환경변수 하나에만 key 가 들어간다(보관 없는 세션형, D10 서랍, D80).
     디스크·로그·응답에 남기지 않는다. 서버 자체의 키·대체 두뇌는 러너에 물려주지 않는다.
  4. 상한 — 서버 전체 동시 max_runs(기본 3)판 · 세션당 1판(Runner 그대로) · IP 당 시간당 시작 starts_per_hour(기본 12) ·
     한 판이 쓰는 LLM 호출 API_CALL_LIMIT(기본 500 — 러너에 DUNGEON_API_CALL_LIMIT 로 넘긴다). 값은 /api/presets 로 화면에도 내려가고,
     D96(2026-09-20 파트너 "500콜 한도로 맞추고 안내를 하자 … 서버의 처음 화면에서 api 키로 이어서 플레이 할 수 있게"): 한도에 닿은 판은
     재시도를 권하지 않고 곧바로 곱게 멈춘다(사유 'budget') — 이어가기(D79)로 계속되고, 이어간 판은 새 러너라 한도를 다시 0부터 센다.
     자리 관리(D91, 2026-09-20 파트너 확정 — 둘 다 10분, "실사용을 보며 수정이 필요할 수도 있다"): 판단 정지가 PAUSE_LIMIT_SEC 이어지면
     러너가 스스로 닫고, 관전 요청(/api/status·/state/…)이 UNWATCHED_LIMIT_SEC 동안 없는 판은 서버가 곱게 멈춘다(수첩 없음 · 사유
     'unwatched'). 둘 다 이어가기(D79) 가능한 길 — 돌아온 방문자의 론처 화면에 '멈춘 원정 … 이어가기'가 뜬다. 로컬 론처(launcher.py)에는 없다.
  5. 계정(D77, 2026-09-16 파트너 "api키 자체를 아이디로 쓸 수는 없어?") — **키의 지문이 계정**이다(accounts.py).
     POST /api/login {provider, key, nick?} 이 키의 생존을 해당 회사에 묻고(key_alive — 폐기된 키는 문이 안 열린다 = 킬 스위치), 지문(HMAC)으로
     계정을 찾거나 만들고 번호표를 묶는다. 그 뒤 이 번호표의 Ctx 는 <data>/accounts/<id>/ (state·runs·파티·캐릭터) — 기기가
     달라도 같은 키면 같은 계정, 같은 Ctx(러너 하나). 로그인 전 익명 세션의 저장 캐릭터는 들어올 때 계정으로 옮긴다.
     /api/me · /api/logout · /api/keys/link · /api/keys/unlink · /api/nick. 키는 여기서도 저장·기록되지 않는다(지문·별명만).
     로그인(=생존 확인) IP 시간당 상한 — 우리 서버를 남의 키 검사기로 못 쓰게.

실행:  python server.py --host 127.0.0.1 --port 8000     (외부는 Caddy 가 HTTPS 로 받아 넘긴다 — scripts/vm/)
환경:  BOTPIKDUN_DATA(세션·계정 폴더 뿌리, 기본 <리포>/state/public) · BOTPIKDUN_MAX_RUNS · BOTPIKDUN_START_PER_HOUR ·
       BOTPIKDUN_LOGIN_PER_HOUR(기본 30) · BOTPIKDUN_SECRET(지문 비밀 — 없으면 <data>/secret 을 첫 기동 때 만든다, 백업 대상) ·
       BOTPIKDUN_PAUSE_LIMIT_SEC(판단 정지를 기다려 주는 초, 기본 600 · 0 = 끝없이) ·
       BOTPIKDUN_UNWATCHED_LIMIT_SEC(관전 요청이 없는 판을 멈추기까지의 초, 기본 600 · 0 = 끔) ·
       BOTPIKDUN_API_CALL_LIMIT(한 판이 쓰는 LLM 호출 수, 기본 500 · 0 = 끝없이 — 없으면 DUNGEON_API_CALL_LIMIT 를 따른다) ·
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
from brain_config import HTTP_BACKENDS, KEY_ENV, MODEL_ENV, LEGACY_MODEL_ENV, MODEL_IDS, openai_base_url, clean_model

HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE = "botpikdun_sid"
STATIC_OK = ("/game/", "/viewer/", "/launcher/", "/art/")   # 리포에서 그대로 내주는 접두(공개 리포의 정적 자산)
SESSION_OK = ("/state/", "/runs/")                           # 세션 폴더에서 내주는 접두
ENTRY = ("/", "/launcher/", "/launcher/index.html", "/game/", "/game/index.html")   # 여기서만 새 번호표를 준다
SESSION_TTL = 24 * 3600
MAX_SESSIONS = 500                                           # 메모리에 두는 세션 상한(크롤러 방어) — 넘으면 새 번호표 거부
KEY_MIN, KEY_MAX = 20, 4096
KEY_LIMITS = {"gemini_api": (20, 512), "anthropic_api": (20, 4096), "openai_api": (1, 4096)}
LOGIN_PER_HOUR = 30                                          # D77 로그인(=구글 생존 확인) IP 시간당 상한
PAUSE_LIMIT_SEC = 600                                        # F1(09-18) 판단 정지를 기다려 주는 초 — 넘으면 러너가 스스로 닫는다(이어가기 가능). 값 확정(D91, 09-20 파트너: 10분)
API_CALL_LIMIT = 500                                         # D96(09-20 파트너 "그럼 어쩔 수 없지 500콜 한도로 맞추고 안내를 하자") 한 판(러너 프로세스)이 쓰는 LLM 호출 수 · 0 = 끝없이.
                                                             #   실측 ~0.5콜/틱이라 600틱 판은 여유가 있고, 긴 판은 여기 닿아 곱게 멈춘다(사유 'budget' → 이어가기는 새 러너 = 다시 0부터).
UNWATCHED_LIMIT_SEC = 600                                    # D91(09-20 파트너: 10분) 관전 요청(/api/status·/state/…)이 이만큼 없는 판은 곱게 멈춘다(이어가기 가능) · 0 = 끔.
                                                             #   근거(실측): 숨긴 탭도 폴링은 이어지고 탭을 닫으면 바로 끊긴다 — '요청 없음 = 아무도 안 봄'. "실사용을 보며 수정이 필요할 수도 있다"(파트너) — 값은 여기 한 곳
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
ACCOUNT_POSTS = ("/api/login", "/api/logout", "/api/keys/link", "/api/keys/unlink", "/api/nick")


class KeyCheckUnavailable(Exception):
    """해당 회사에 닿지 못했다(네트워크·5xx) — 키의 생사를 모른다. 계정을 만들지도 열지도 않는다."""


def key_alive(key, provider="gemini_api", timeout=8):
    """키 생존 확인(D77) — 모델 목록 한 번(생성 콜 아님·과금 없음). 200=살아 있음 · 400/401/403=폐기됐거나 잘못된 키 · 그 외=모른다.
    키는 회사별 인증 헤더로만 보낸다 — URL 에 실으면 예외 문구·로그에 남는다."""
    import requests                       # 지연 import — 러너와 같은 이유(미설치 환경에서 import server 가 죽지 않게)
    if provider == "gemini_api":
        url, headers = MODELS_URL, {"x-goog-api-key": key}
    elif provider == "anthropic_api":
        url, headers = "https://api.anthropic.com/v1/models", {"x-api-key": key, "anthropic-version": "2023-06-01"}
    elif provider == "openai_api":
        try:
            url = openai_base_url() + "/models"
        except ValueError:
            raise KeyCheckUnavailable("InvalidBaseURL")
        headers = {"Authorization": "Bearer " + key}
    else:
        raise BadRequest("지원하지 않는 API 회사")
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
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
                 login_per_hour=LOGIN_PER_HOUR, key_check=None, pause_limit=PAUSE_LIMIT_SEC,
                 unwatched_limit=UNWATCHED_LIMIT_SEC, api_call_limit=API_CALL_LIMIT):
        self.root, self.brain = root, brain
        self.max_runs, self.starts_per_hour, self.ttl = int(max_runs), int(starts_per_hour), ttl
        self.login_per_hour, self.key_check = int(login_per_hour), key_check
        self.pause_limit = max(0, int(pause_limit))   # F1 러너에 DUNGEON_PAUSE_LIMIT_SEC 로 넘긴다(0 = 끝없이)
        self.unwatched_limit = max(0, int(unwatched_limit))   # D91 관전 요청이 이만큼 없는 판은 곱게 멈춘다(0 = 끔)
        self.api_call_limit = max(0, int(api_call_limit))     # D96 러너에 DUNGEON_API_CALL_LIMIT 로 넘긴다(0 = 끝없이) — 화면이 말하는 수와 러너가 세는 수가 같아야 해서 서버가 명시한다
        self.watcher = None                     # D91 자동 멈춤을 살피는 데몬 스레드(start_watcher — 끔이면 None 그대로)
        self.closed = threading.Event()         # 서버가 닫힌다(stop_all) — 살피기 스레드를 내린다
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
        ctx.watched = time.monotonic()          # D91 마지막 관전 요청 시각(touch)
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
        self.closed.set()                       # D91 살피기 스레드도 내린다
        with self.lock:
            for ctx in list(self.ctx.values()) + list(self.actx.values()):
                ctx.runner.stop()

    # ── D91(09-20) 관전자 없는 판 자동 멈춤 — 공개 서버만(로컬 론처에는 없다) ──
    @staticmethod
    def touch(ctx):
        """이 Ctx 의 판을 누가 보고 있다 — 상태(/api/status)·판 파일(/state/…) 요청이 올 때마다, 그리고 판을 시작할 때 시계를 다시 잰다.
        계정 Ctx 는 기기가 여럿이어도 하나라 어느 기기의 요청이든 같은 시계를 만진다."""
        ctx.watched = time.monotonic()

    def stop_unwatched(self, now=None):
        """돌고 있는데 unwatched_limit 초 동안 관전 요청이 없던 판을 곱게 멈춘다 → 멈춘 수.
        사람이 누르는 멈춤과 같은 길(Runner.stop graceful — 다음 틱 머리에서 stopped 줄·스냅샷을 남기고 스스로 닫는다 = 이어가기 가능)이고,
        수첩은 쓰지 않는다(pages=False — 읽을 사람 없는 자리에서 두뇌 콜을 쓰지 않는다). 사유 'unwatched' 는 러너가 기록에 그대로 적는다."""
        if not self.unwatched_limit:
            return 0
        with self.lock:
            ctxs = list(self.ctx.values()) + list(self.actx.values())
        n = 0
        for ctx in ctxs:                          # 멈춤은 lock 밖에서(러너가 닫히길 기다린다) — 앞 판을 기다리는 사이 돌아온 방문자가 있을 수 있어 판마다 다시 잰다
            t = time.monotonic() if now is None else now
            if not hasattr(ctx, "watched"):       # 시계가 없는 Ctx 는 지금부터 잰다(바로 멈추지 않는다)
                ctx.watched = t
            if ctx.runner.running() and t - ctx.watched >= self.unwatched_limit:
                res = ctx.runner.stop(graceful=True, pages=False, reason="unwatched")
                if res.get("stopped"):
                    n += 1
                    print("[server] 관전 요청이 %d초 없던 판을 멈췄다(%s) — 이어가기 가능"
                          % (self.unwatched_limit, "곱게" if res.get("graceful") else "끊음"), file=sys.stderr)
        return n

    def start_watcher(self):
        """자동 멈춤을 살피는 데몬 스레드 하나 — 간격은 제한 시간의 1/4(상한 15초). 끔(0)이면 안 띄운다. 두 번 불러도 하나."""
        if not self.unwatched_limit or self.watcher is not None:
            return self.watcher
        every = min(15.0, max(0.2, self.unwatched_limit / 4.0))

        def loop():
            while not self.closed.wait(every):
                try:
                    self.stop_unwatched()
                except Exception as e:            # 살피기 실패로 서버가 죽지 않게(sweeper 와 같은 규칙)
                    print("[server] unwatched: %s" % type(e).__name__, file=sys.stderr)
        self.watcher = threading.Thread(target=loop, daemon=True)
        self.watcher.start()
        return self.watcher

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
            ctx.watched = time.monotonic()      # D91 마지막 관전 요청 시각(touch)
            self.actx[aid] = ctx
        self.aseen[aid] = time.time()
        return ctx

    @staticmethod
    def provider_name(provider):
        if not isinstance(provider, str) or provider not in HTTP_BACKENDS:
            raise BadRequest("회사는 Gemini / Anthropic / OpenAI 호환 중 하나여야 한다")
        return provider

    @staticmethod
    def key_shape(key, provider="gemini_api"):
        """키 형태만(네트워크 없음) — 문자열·길이·공백. 정제된 키를 돌려주고 아니면 BadRequest."""
        key = key.strip() if isinstance(key, str) else ""
        Sessions.provider_name(provider)
        lo, hi = KEY_LIMITS[provider]
        if not (lo <= len(key) <= hi) or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise BadRequest("선택한 회사의 API 키를 넣어야 한다 — 키는 저장되지 않고 지문만 남는다")
        return key

    def _check_alive(self, key, provider="gemini_api"):
        """회사별 생존 확인. 죽은 키는 BadRequest, 불통은 KeyCheckUnavailable(503) — 키는 예외 문구에 안 실린다."""
        if not (self.key_check or KEY_CHECK)(key, provider):
            raise BadRequest("키가 유효하지 않다 — 선택한 회사가 거부했다(폐기됐거나 잘못 적은 키)")

    def check_start_key(self, key, provider="gemini_api"):
        """F1(09-18) 판을 시작할 때도 키 생존 확인 — 형태만 맞는 가짜 키로 동시 판 자리를 차지하지 못하게(로그인과 같은 확인).
        두뇌가 dummy 인 서버(0콜 게이트·다중 접속 연습)는 키를 아예 안 쓰니 확인도 없다 — 단 key_check 를 끼운 게이트는 확인한다."""
        if self.brain == "dummy" and self.key_check is None:
            return
        self._check_alive(key, provider)

    def login(self, sid, key, nick="", provider="gemini_api"):
        """키 → 생존 확인 → 지문 → 계정(없으면 생성) → 번호표 묶기 → 익명 세션의 저장 캐릭터를 계정으로 옮긴다.
        반환 (공개 모양, 새로 만들었나, 옮긴 캐릭터 수). 네트워크는 lock 밖에서."""
        self._check_alive(key, provider)
        fp = self.accounts.fingerprint(key)
        with self.lock:
            aid = self.accounts.lookup(fp)
            created = aid is None
            if created:
                data = self.accounts.create(fp, nick, provider)
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

    def link_key(self, aid, key, provider="gemini_api"):
        self._check_alive(key, provider)
        fp = self.accounts.fingerprint(key)
        try:
            return self.accounts.public(self.accounts.link(aid, fp, provider))
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
                provider = Sessions.provider_name(body.get("provider", "gemini_api"))
                key = Sessions.key_shape(body.get("key"), provider)
                if not self.sessions.allow_login(self._ip()):
                    return self._json(429, {"error": "이 주소에서 시도한 로그인이 너무 많다 — 한 시간에 %d번까지"
                                            % self.sessions.login_per_hour})
                acct, created, moved = self.sessions.login(self.sid, key, body.get("nick") or "", provider)
                return self._json(200, {"ok": True, "logged_in": True, "created": created, "moved": moved, "account": acct, "provider": provider})
            aid = self.sessions.account_of(self.sid)
            if not aid:
                return self._json(401, {"error": "먼저 키로 들어와야 한다"})
            if p == "/api/keys/link":
                provider = Sessions.provider_name(body.get("provider", "gemini_api"))
                key = Sessions.key_shape(body.get("key"), provider)
                if not self.sessions.allow_login(self._ip()):
                    return self._json(429, {"error": "이 주소에서 시도한 로그인이 너무 많다 — 한 시간에 %d번까지"
                                            % self.sessions.login_per_hour})
                return self._json(200, {"ok": True, "account": self.sessions.link_key(aid, key, provider)})
            if p == "/api/keys/unlink":
                return self._json(200, {"ok": True, "account": self.sessions.unlink_key(aid, str(body.get("tag") or ""))})
            return self._json(200, {"ok": True, "account": self.sessions.set_nick(aid, body.get("nick") or "")})
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        except Conflict as e:
            return self._json(409, {"error": str(e)})
        except KeyCheckUnavailable:
            return self._json(503, {"error": "선택한 회사에 닿지 못해 키를 확인할 수 없다 — 잠시 뒤 다시"})
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
        if p == "/api/status" or p.startswith("/state/"):              # D91 관전 폴링(론처 화면·관전 클라이언트가 1.5~3초마다) = 이 판을 누가 보고 있다
            self.sessions.touch(self.ctx)
        if p == "/api/presets":
            obj = launcher.presets_payload(self.ctx)
            obj["model_defaults"] = {p: MODEL_IDS[p]["haiku"] for p in HTTP_BACKENDS}
            obj["openai_base_url"] = openai_base_url()
            obj.update(byok=True, public=True, max_runs=self.sessions.max_runs, running=self.sessions.running_count(),
                       account=self._me()["account"],                      # D77 화면이 계정 상태를 같이 읽는다
                       pause_limit=self.sessions.pause_limit,              # D91 additive — 화면이 '얼마 뒤 멈추는지'를 말할 수 있게(초 · 0 = 없음)
                       unwatched_limit=self.sessions.unwatched_limit,
                       api_call_limit=self.sessions.api_call_limit)        # D96 additive — 시작 화면이 '한 판에 몇 콜까지'를 말할 수 있게(0 = 없음). 화면은 이 값을 그대로 쓴다
            return self._json(200, obj)
        if p == "/api/me":                                            # D77 계정 상태 — 론처 화면의 계정 카드
            return self._json(200, self._me())
        return super().do_GET()

    def _drain(self):
        """몸을 읽기 전에 거절하는 POST 는 응답 전에 몸을 비운다(상한 256KB = _body 와 같다) — 안 읽은 몸을 둔 채 닫으면 Windows 에서 응답보다
        끊김이 먼저 닿는다(09-20 실측: 600번에 26번 ConnectionAbortedError = verify_public ① '상한 밖 POST → 404' 의 일시 실패 원인)."""
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 256 * 1024)
        except ValueError:
            n = 0
        if n > 0:
            self.rfile.read(n)

    def do_POST(self):
        p = urlparse(self.path).path
        if not p.startswith("/api/"):
            self._drain()
            return self._json(404, {"error": "없는 경로"})
        try:
            self._session(create=True)
        except Conflict as e:
            self._drain()
            return self._json(429, {"error": str(e)})
        if p in ACCOUNT_POSTS:
            return self._account_post(p)                              # D77 계정 — 키는 함수 안에서만 산다
        if p != "/api/start":
            return super().do_POST()                                  # party·characters·retry·oracle·stop — 세션(또는 계정)의 Ctx 로
        try:
            body = self._body()
            default_provider = self.sessions.brain if self.sessions.brain in HTTP_BACKENDS else "gemini_api"
            if body.get("resume") and "provider" not in body:
                saved = self.ctx.runner._read_run_opts() or {}
                default_provider = saved.get("opts", {}).get("provider", default_provider)
            provider = Sessions.provider_name(body.get("provider", default_provider))
            key = Sessions.key_shape(body.pop("key", None), provider)
            if "base_url" in body or "OPENAI_BASE_URL" in body:
                raise BadRequest("호환 API 주소는 서버 운영자 설정으로만 바꿀 수 있다")
            if "model" in body:
                try:
                    body["model"] = clean_model(body["model"])
                except ValueError as e:
                    raise BadRequest(str(e))
            def no_room():                                # 이미 도는 판 = 409(예외) · 동시 판 상한 = 429 를 보내고 True · 자리 있으면 False
                if self.ctx.runner.running():
                    raise Conflict("이미 판이 진행 중이다 — 중지하거나 끝나길 기다려라")
                if self.sessions.running_count() >= self.sessions.max_runs:
                    self._json(429, {"error": "지금 동시에 도는 판이 %d개라 자리가 없다 — 몇 분 뒤 다시"
                                     % self.sessions.max_runs})
                    return True
                return False
            # F1(09-18) 순서: 자리(네트워크 없음) → IP 시간당 상한 → 키 생존 확인(네트워크라 start_lock 밖) → 잠그고 자리를 다시 보고 시작.
            # 생존 확인이 IP 상한 뒤인 까닭 = 로그인과 같다: 이 경로를 남의 키 검사기로 못 쓰게. 죽은 키의 시도도 시작 횟수 한 번을 쓴다.
            if no_room():
                return
            if not self.sessions.allow_start(self._ip()):
                return self._json(429, {"error": "이 주소에서 시작한 판이 너무 많다 — 한 시간에 %d판까지"
                                        % self.sessions.starts_per_hour})
            self.sessions.check_start_key(key, provider)
            with self.sessions.start_lock:
                if no_room():                             # 생존 확인(수 초)을 기다리는 사이 자리가 찼을 수 있다
                    return
                body["provider"] = provider
                body["brain"] = "dummy" if self.sessions.brain == "dummy" else provider   # 서버 쪽 0콜 게이트만 예외
                extra = {k: "" for k in (*KEY_ENV.values(), *MODEL_ENV, *LEGACY_MODEL_ENV.values())}
                extra.update({KEY_ENV[provider]: key, "DUNGEON_BRAIN_BACKEND": body["brain"], "DUNGEON_BRAIN_FALLBACK": ""})
                # 러너 __main__의 .env 로더도 목적지를 바꾸지 못하게 서버 설정을 명시한다.
                extra["OPENAI_BASE_URL"] = openai_base_url()
                extra["DUNGEON_PAUSE_LIMIT_SEC"] = self.sessions.pause_limit   # F1 재시도를 아무도 안 누르는 판이 자리를 쥐고 있지 못하게
                extra["DUNGEON_API_CALL_LIMIT"] = self.sessions.api_call_limit   # D96 한 판이 쓰는 LLM 호출 수 — /api/presets 로 화면이 예고한 그 값이 러너로 간다(이어가는 판도 새 프로세스라 여기서 다시 0부터)
                if getattr(self.ctx, "aid", None):        # D78(09-16) 계정 판: 도감 원장은 계정 폴더에, 저장한 캐릭터(id)만 남는다
                    body["bestiary"] = True
                    extra["DUNGEON_BESTIARY_FILE"] = os.path.join(self.ctx.dir, "bestiary.json")
                    extra["DUNGEON_LEDGER_IDS_ONLY"] = "1"
                else:
                    body["bestiary"] = False             # D64 — 익명 세션은 원장 이월 없음(판 안 학습만)
                self.sessions.touch(self.ctx)            # D91 관전 시계는 판을 시작할 때부터 잰다(이어가기도 같다)
                return self._json(200, self.ctx.runner.start(body, self.ctx.party_path, self.sessions.brain,
                                                             extra_env=extra))
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        except Conflict as e:
            return self._json(409, {"error": str(e)})
        except KeyCheckUnavailable:                       # F1: 회사에 못 닿으면 판단도 못 한다 — 자리를 주지 않는다
            return self._json(503, {"error": "선택한 회사에 닿지 못해 키를 확인할 수 없다 — 잠시 뒤 다시"})
        except Exception as e:                            # 이유는 예외 이름만 — 본문(키)이 섞이지 않게
            return self._json(500, {"error": type(e).__name__})


def make_public_server(host, port, root=HERE, data_dir=None, brain=None, max_runs=None, starts_per_hour=None,
                       login_per_hour=None, key_check=None, pause_limit=None, unwatched_limit=None,
                       api_call_limit=None):
    sessions = Sessions(root,
                        data_dir or os.environ.get("BOTPIKDUN_DATA") or os.path.join(root, "state", "public"),
                        brain or os.environ.get("BOTPIKDUN_BRAIN") or "gemini_api",
                        max_runs if max_runs is not None else _env_int("BOTPIKDUN_MAX_RUNS", 3),
                        starts_per_hour if starts_per_hour is not None else _env_int("BOTPIKDUN_START_PER_HOUR", 12),
                        login_per_hour=login_per_hour if login_per_hour is not None else _env_int("BOTPIKDUN_LOGIN_PER_HOUR", LOGIN_PER_HOUR),
                        key_check=key_check,
                        pause_limit=pause_limit if pause_limit is not None else _env_int("BOTPIKDUN_PAUSE_LIMIT_SEC", PAUSE_LIMIT_SEC),
                        unwatched_limit=(unwatched_limit if unwatched_limit is not None
                                         else _env_int("BOTPIKDUN_UNWATCHED_LIMIT_SEC", UNWATCHED_LIMIT_SEC)),
                        # D96: 서비스 환경값에 이미 DUNGEON_API_CALL_LIMIT 가 있으면 그 값을 따른다 — 운영에 걸린 수와 화면이 말하는 수를 하나로
                        api_call_limit=(api_call_limit if api_call_limit is not None
                                        else _env_int("BOTPIKDUN_API_CALL_LIMIT", _env_int("DUNGEON_API_CALL_LIMIT", API_CALL_LIMIT))))
    srv = LauncherServer((host, port), partial(PublicHandler, sessions=sessions))
    srv.daemon_threads = True
    srv.sessions = sessions
    sessions.start_watcher()                      # D91 관전자 없는 판 자동 멈춤(끔이면 스레드 없음)
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
    print("[server] 자리 관리(D91): 판단 정지 %d초 · 관전 요청 없는 판 %d초 뒤 멈춤(0 = 끔) / 둘 다 이어가기 가능"   # stdout 은 cp949 콘솔일 수 있다 - em dash 금지(기동 직후 UnicodeEncodeError)
          % (s.pause_limit, s.unwatched_limit))
    print("[server] 호출 한도(D96): 한 판에 LLM 호출 %d회(0 = 끝없이) / 닿으면 곱게 멈추고 이어가기로 계속"
          % s.api_call_limit)

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
