# -*- coding: utf-8 -*-
"""계정 = 키의 지문(D77, 2026-09-16 파트너 "애초에 api키 자체를 아이디로 쓸 수는 없어?") — 공개 서버(server.py)의 소유 층.

사용자가 원정을 보내려면 어차피 자기 Gemini 키(BYOK, D68)를 넣는다. 그 키를 신원으로 쓴다 — 가입 없음, 비밀번호 없음.
  · 저장하는 것 = 키의 **지문**(서버 비밀을 섞은 HMAC-SHA256 앞 32자)과 별명뿐. 키 문자열은 디스크·로그·응답 어디에도
    남지 않는다(D68 규율 그대로). 지문은 키로 되돌릴 수 없고, 서버 비밀 없이는 유출된 지문으로 키를 대조하지도 못한다.
  · 계정 폴더 <data>/accounts/<계정id>/ 에 state/·runs/·party_custom.json·character_presets.json·account.json —
    세션(쿠키)이 아니라 계정이 캐릭터·판 기록의 주인이다. 기기가 달라도 같은 키면 같은 계정, 같은 Ctx(러너 하나).
  · 열쇠 여러 개: 한 계정에 지문 여럿(키 교체 = 로그인 상태에서 새 키 연결). 계정 id = 첫 열쇠의 지문.
    keyindex/<지문> 파일 한 줄 → 계정 id. 마지막 열쇠는 뺄 수 없다(빼면 들어올 길이 없다).
  · 로그인 = 번호표(sid) → 계정 id 묶음(logins/<sid>, 쿠키 수명과 같은 30일). 로그아웃 = 그 파일 삭제.
  · 킬 스위치: 로그인 때 키의 생존을 구글에 묻는다(server.key_alive) — 키를 폐기하면 그 키를 쥔 누구도 못 들어온다.
    그래서 열쇠를 전부 잃으면 복구 불가(패스키 = ①-b, 다음 조각).
  · 서버 비밀 = 환경변수 BOTPIKDUN_SECRET, 없으면 <data>/secret 파일(첫 기동 때 생성, 0600). 비밀이 바뀌면 지문이
    전부 바뀐다 = 모든 계정이 고아가 된다 — 데이터 폴더와 함께 백업할 것.
순수 파일 저장소·네트워크 없음. 생존 확인·상한·라우팅은 server.py 가 맡는다.
"""
import hashlib
import hmac
import io
import json
import os
import secrets
import tempfile
import threading
import time

FP_LEN = 32              # 지문 길이(hex) — 128비트면 충돌 걱정 없이 폴더 이름으로 충분
TAG_LEN = 8              # 화면에 보이는 열쇠 표식 = 지문 앞 8자(키 문자열의 일부가 아니다)
NICK_MAX = 20
LOGIN_TTL = 30 * 86400   # 쿠키 Max-Age(server.py 의 30일)와 같다
SECRET_FILE = "secret"


class KeyTaken(Exception):
    """이 지문은 다른 계정에 묶여 있다."""


def _hex(s, n):
    return isinstance(s, str) and len(s) == n and all(c in "0123456789abcdef" for c in s)


def _atomic_write(path, text):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        for i in range(20):                           # Windows: 방금 쓴 파일을 색인기·백신이 잠깐 잡으면 replace 가 WinError 5 — 재시도(bestiary.save 선례)
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if i == 19:
                    raise
                time.sleep(0.05 * (i + 1))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def clean_nick(nick):
    """별명 정제 — 시트 자유 입력과 같은 격리(개행·마크다운 표식 제거·한 줄·상한). 빈 값은 빈 문자열."""
    import sheetkit
    return sheetkit.sanitize_freetext(nick if isinstance(nick, str) else "", NICK_MAX) or ""


class Accounts:
    def __init__(self, data_dir, secret=None):
        self.data_dir = data_dir
        self.dir = os.path.join(data_dir, "accounts")
        self.keys_dir = os.path.join(data_dir, "keyindex")
        self.logins_dir = os.path.join(data_dir, "logins")
        for d in (self.dir, self.keys_dir, self.logins_dir):
            os.makedirs(d, exist_ok=True)
        env = secret or os.environ.get("BOTPIKDUN_SECRET") or ""
        self.secret = env.encode("utf-8") if env else self._secret_file()
        self.lock = threading.RLock()

    def _secret_file(self):
        """<data>/secret — 없으면 처음 한 번 만든다(0600). 동시 기동이면 한쪽이 지고 다시 읽는다."""
        p = os.path.join(self.data_dir, SECRET_FILE)
        try:
            with io.open(p, "rb") as f:
                s = f.read().strip()
            if s:
                return s
        except OSError:
            pass
        s = secrets.token_hex(32).encode("ascii")
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            with io.open(p, "rb") as f:
                return f.read().strip()
        with os.fdopen(fd, "wb") as f:
            f.write(s)
        return s

    # ── 지문 ──
    def fingerprint(self, key):
        return hmac.new(self.secret, key.encode("utf-8"), hashlib.sha256).hexdigest()[:FP_LEN]

    # ── 저장소 ──
    def folder(self, aid):
        return os.path.join(self.dir, aid)

    def _path(self, aid):
        return os.path.join(self.folder(aid), "account.json")

    def load(self, aid):
        if not _hex(aid, FP_LEN):
            return None
        try:
            with io.open(self._path(aid), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _save(self, data):
        _atomic_write(self._path(data["id"]), json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return data

    def lookup(self, fp):
        """지문 → 계정 id(없으면 None). keyindex/<fp> 한 줄."""
        if not _hex(fp, FP_LEN):
            return None
        try:
            with io.open(os.path.join(self.keys_dir, fp), encoding="utf-8") as f:
                aid = f.read().strip()
        except OSError:
            return None
        return aid if _hex(aid, FP_LEN) and os.path.isfile(self._path(aid)) else None

    def _index(self, fp, aid):
        _atomic_write(os.path.join(self.keys_dir, fp), aid + "\n")

    def _unindex(self, fp):
        try:
            os.unlink(os.path.join(self.keys_dir, fp))
        except OSError:
            pass

    def create(self, fp, nick=""):
        """첫 열쇠의 지문이 곧 계정 id. 이미 묶인 지문이면 KeyTaken."""
        with self.lock:
            if self.lookup(fp):
                raise KeyTaken(fp)
            now = int(time.time())
            data = {"id": fp, "nick": clean_nick(nick), "created": now,
                    "keys": [{"fp": fp, "tag": fp[:TAG_LEN], "added": now}]}
            self._save(data)
            self._index(fp, fp)
            return data

    def link(self, aid, fp):
        """로그인한 계정에 새 열쇠. 같은 계정이면 그대로(멱등), 다른 계정 것이면 KeyTaken."""
        with self.lock:
            owner = self.lookup(fp)
            data = self.load(aid)
            if data is None:
                raise ValueError("계정이 없다")
            if owner == aid:
                return data
            if owner:
                raise KeyTaken(fp)
            data["keys"].append({"fp": fp, "tag": fp[:TAG_LEN], "added": int(time.time())})
            self._save(data)
            self._index(fp, aid)
            return data

    def unlink(self, aid, tag):
        with self.lock:
            data = self.load(aid)
            if data is None:
                raise ValueError("계정이 없다")
            hit = [k for k in data["keys"] if k["tag"] == tag]
            if not hit:
                raise ValueError("그런 열쇠가 없다")
            if len(data["keys"]) == 1:
                raise ValueError("마지막 열쇠는 뺄 수 없다 — 빼면 이 계정에 들어올 길이 없다")
            data["keys"] = [k for k in data["keys"] if k["tag"] != tag]
            self._save(data)
            for k in hit:
                self._unindex(k["fp"])
            return data

    def set_nick(self, aid, nick):
        with self.lock:
            data = self.load(aid)
            if data is None:
                raise ValueError("계정이 없다")
            data["nick"] = clean_nick(nick)
            return self._save(data)

    @staticmethod
    def public(data):
        """화면에 주는 모양 — 지문 전체도 안 준다(계정 표식 8자·열쇠 표식 8자·날짜)."""
        return {"id": data["id"][:TAG_LEN], "nick": data.get("nick", ""), "created": data.get("created"),
                "keys": [{"tag": k["tag"], "added": k.get("added")} for k in data.get("keys", [])]}

    # ── 로그인(번호표 ↔ 계정) ──
    def bind(self, sid, aid):
        _atomic_write(os.path.join(self.logins_dir, sid), aid + "\n")

    def unbind(self, sid):
        try:
            os.unlink(os.path.join(self.logins_dir, sid))
        except OSError:
            pass

    def bound(self, sid):
        """번호표의 계정 id — 30일 지났거나 계정이 없으면 None(파일도 지운다)."""
        if not _hex(sid, 32):
            return None
        p = os.path.join(self.logins_dir, sid)
        try:
            with io.open(p, encoding="utf-8") as f:
                aid = f.read().strip()
            fresh = time.time() - os.path.getmtime(p) < LOGIN_TTL
        except OSError:
            return None
        if fresh and _hex(aid, FP_LEN) and os.path.isfile(self._path(aid)):
            return aid
        self.unbind(sid)
        return None

    def sweep(self, now=None):
        now = now or time.time()
        try:
            names = os.listdir(self.logins_dir)
        except OSError:
            return
        for n in names:
            p = os.path.join(self.logins_dir, n)
            try:
                if now - os.path.getmtime(p) > LOGIN_TTL:
                    os.unlink(p)
            except OSError:
                pass
