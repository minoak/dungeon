# -*- coding: utf-8 -*-
"""계정 = 키 지문(D77, 2026-09-16) 헤들리스 검증 — 65번째 게이트. LLM 0콜·네트워크 0(생존 확인은 가짜로 갈아 끼움).
게이트:
  ① 로그인: 형태 불량 400(상한 미소모) · 죽은 키 400 · 구글 불통 503(계정 안 생김) · 산 키 → 200 created · 별명 정제 ·
     열쇠 1(표식 8자) · 로그인 전 익명 세션에 저장한 캐릭터가 계정으로 옮겨짐(익명 쪽은 빔) · account.json 엔 지문만
  ② 다른 기기: 새 쿠키로 같은 키 → created=false · 같은 계정 · 같은 캐릭터 · Ctx 가 하나(같은 state_dir) · 별명 바꾸면 양쪽 다
  ③ 열쇠: 새 키 연결 → 2 · 그 키로 새 쿠키 로그인 = 같은 계정 · 남의 키 연결 409 · 해제 → 1 · 해제한 키는 새 계정 ·
     마지막 열쇠 해제 400 · 없는 표식 400 · 로그인 안 한 번호표의 연결/별명 401
  ④ 로그아웃: /api/me logged_in=false · 캐릭터 목록이 익명 것 · /api/presets.account · 다시 들어오면 계정 것
  ⑤ 실판(dummy): 로그인한 세션의 판이 accounts/<id>/state 에 · 다른 기기 쿠키의 /api/status 도 같은 판 · 익명 폴더엔 판 없음
  ⑥ 키 미기록: 데이터 폴더 전체·서버 로그·응답에 키 문자열 0회
  ⑦ 재시작: 같은 데이터 폴더로 새 서버 → 옛 쿠키가 로그인 상태 그대로 · 캐릭터 그대로 · 서버 비밀 파일이 같아 지문 동일 · 로그인 IP 상한 429
"""
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_account_")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="")   # 러너(서브프로세스)가 물려받는 짧은 판 설정
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_STATE_DIR", "DUNGEON_STREAM_OBS", "BOTPIKDUN_DATA", "BOTPIKDUN_BRAIN",
          "BOTPIKDUN_MAX_RUNS", "BOTPIKDUN_START_PER_HOUR", "BOTPIKDUN_LOGIN_PER_HOUR", "BOTPIKDUN_SECRET"):
    os.environ.pop(k, None)
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"

import server                                        # noqa: E402

K1 = "AIzaSyACCT1-0123456789abcdefghijklmnopq"        # 가짜 키(형태만) — 어디에도 남으면 안 된다
K2 = "AIzaSyACCT2-0123456789abcdefghijklmnopq"
K3 = "AIzaSyACCT3-0123456789abcdefghijklmnopq"
KD = "AIzaSyDEAD0-0123456789abcdefghijklmnopq"        # 구글이 거부하는 키
KEYS = (K1, K2, K3, KD)
BOOM = {"on": False}
LOG = io.StringIO()
fails = []


def fake_alive(key):                                 # 생존 확인 대역 — 네트워크 0
    if BOOM["on"]:
        raise server.KeyCheckUnavailable("test")
    return key != KD


server.KEY_CHECK = fake_alive


def check(name, cond, note=""):
    print(("PASS " if cond else "FAIL ") + name + ((" — " + note) if note else ""))
    if not cond:
        fails.append(name)


class Device:
    """기기 하나 = 쿠키 단지 하나."""
    def __init__(self, port, name):
        self.port, self.name, self.cookie = port, name, None

    def call(self, path, body=None, method=None, headers=None):
        h = dict(headers or {})
        if self.cookie:
            h["Cookie"] = "%s=%s" % (server.COOKIE, self.cookie)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        c.request(method or ("POST" if body is not None else "GET"), path, body=data, headers=h)
        r = c.getresponse()
        raw = r.read()
        sc = r.getheader("Set-Cookie") or ""
        if sc.startswith(server.COOKIE + "="):
            self.cookie = sc.split(";")[0].split("=", 1)[1]
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            obj = None
        c.close()
        return r.status, obj, raw

    def login(self, key, nick=""):
        return self.call("/api/login", {"key": key, "nick": nick})


def serve(data_dir, **kw):
    srv = server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=data_dir, brain="dummy", **kw)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def wait_stream(path, sec=25):
    t0 = time.time()
    while time.time() - t0 < sec:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with io.open(path, encoding="utf-8") as f:
                first = f.readline()
            try:
                if json.loads(first).get("kind") == "run_meta":
                    return json.loads(first)
            except ValueError:
                pass
        time.sleep(0.2)
    return None


def wait_done(dev, sec=40):
    t0 = time.time()
    while time.time() - t0 < sec:
        st = dev.call("/api/status")[1]
        if st and not st["running"]:
            return st
        time.sleep(0.3)
    return None


def key_hits(root):
    hits = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                with io.open(p, "rb") as f:
                    blob = f.read()
            except OSError:
                continue
            for k in KEYS:
                if k.encode() in blob:
                    hits.append(os.path.relpath(p, root))
    return hits


SLOT = {"job": "전사", "traits": [], "name": "떠돌이", "sex": "남", "persona": "말수가 적고 앞장선다"}   # 시트는 성격(키워드 또는 문장)이 필수
base = {"mode": "classic", "map": "normal", "town": False, "party": "default", "brain": "claude_cli"}

old_err = sys.stderr
sys.stderr = LOG
try:
    srv, port = serve(TMP, max_runs=3, starts_per_hour=20, login_per_hour=40)
    ACC = srv.sessions.accounts
    A, B, C, D, E, F = (Device(port, n) for n in "ABCDEF")

    print("── ① 로그인")
    A.call("/launcher/")
    st, obj, _ = A.call("/api/characters", {"slot": SLOT, "label": "떠돌이"})
    check("① 로그인 전 익명 세션에 캐릭터 저장 200", st == 200 and obj and obj.get("preset"), str(obj))
    st, obj, _ = A.login("short")
    check("① 형태 불량 400 · 상한 미소모", st == 400 and "키" in obj["error"] and not srv.sessions.logins, str(obj))
    st, obj, _ = A.login(KD)
    check("① 죽은 키 400(구글이 거부)", st == 400 and "거부" in obj["error"], str(obj))
    BOOM["on"] = True
    st, obj, _ = A.login(K1)
    BOOM["on"] = False
    check("① 구글 불통 503 · 계정 안 생김", st == 503 and not os.listdir(ACC.dir), str(obj))
    st, obj, _ = A.login(K1, "두란의 신\n**굵게**")
    acct = (obj or {}).get("account") or {}
    check("① 산 키 → 200 created · 별명 정제(개행 없음·20자 안) · 열쇠 1(표식 8자) · 계정 표식 8자 · 옮긴 캐릭터 1",
          st == 200 and obj["created"] is True and obj["moved"] == 1 and acct.get("nick", "").startswith("두란의 신")
          and "\n" not in acct["nick"] and len(acct["nick"]) <= 20 and len(acct["keys"]) == 1
          and len(acct["keys"][0]["tag"]) == 8 and len(acct["id"]) == 8, str(obj))
    fp1 = ACC.fingerprint(K1)
    aid = fp1
    st, obj, _ = A.call("/api/me")
    check("① /api/me logged_in · public", st == 200 and obj["logged_in"] is True and obj["public"] is True and obj["account"]["id"] == fp1[:8])
    st, obj, _ = A.call("/api/characters")
    anon_file = os.path.join(TMP, "sessions", A.cookie, "character_presets.json")
    anon_left = json.load(io.open(anon_file, encoding="utf-8"))["presets"] if os.path.exists(anon_file) else []
    check("① 계정 캐릭터 목록에 옮겨진 '떠돌이' 1 · 익명 저장소는 빔", st == 200 and len(obj["presets"]) == 1
          and obj["presets"][0]["label"] == "떠돌이" and anon_left == [], str(obj))
    data = json.load(io.open(os.path.join(ACC.dir, aid, "account.json"), encoding="utf-8"))
    check("① account.json 엔 지문·표식·별명만(키 문자열 없음) · keyindex/<지문> → 계정 · logins/<번호표> → 계정",
          data["keys"][0]["fp"] == fp1 and data["keys"][0]["tag"] == fp1[:8]
          and io.open(os.path.join(ACC.keys_dir, fp1)).read().strip() == aid
          and io.open(os.path.join(ACC.logins_dir, A.cookie)).read().strip() == aid)

    print("── ② 다른 기기")
    st, obj, _ = B.login(K1, "다른 별명")
    check("② 새 쿠키 + 같은 키 → created=false · 같은 계정 · 별명은 처음 것 유지", st == 200 and obj["created"] is False
          and obj["account"]["id"] == fp1[:8] and obj["account"]["nick"].startswith("두란의 신"), str(obj))
    check("② 캐릭터도 같은 것", B.call("/api/characters")[1]["presets"][0]["label"] == "떠돌이")
    check("② Ctx 가 하나(state_dir 동일 · 객체 동일)", srv.sessions.get(A.cookie) is srv.sessions.get(B.cookie)
          and srv.sessions.get(A.cookie).state_dir == os.path.join(ACC.dir, aid, "state"))
    st, obj, _ = A.call("/api/nick", {"nick": "카야의 신"})
    check("② 별명 바꾸면 양쪽 다", st == 200 and obj["account"]["nick"] == "카야의 신" and B.call("/api/me")[1]["account"]["nick"] == "카야의 신")

    print("── ③ 열쇠")
    st, obj, _ = C.login(K3)
    check("③ 다른 사람(K3) 로그인 = 새 계정", st == 200 and obj["created"] is True and obj["account"]["id"] != fp1[:8])
    st, obj, _ = A.call("/api/keys/link", {"key": K2})
    check("③ 새 키 연결 → 열쇠 2 · 표식이 다르다", st == 200 and len(obj["account"]["keys"]) == 2
          and obj["account"]["keys"][1]["tag"] == ACC.fingerprint(K2)[:8], str(obj))
    st, obj, _ = D.login(K2)
    check("③ 연결한 키로 새 쿠키 로그인 = 같은 계정(created=false)", st == 200 and obj["created"] is False and obj["account"]["id"] == fp1[:8])
    st, obj, _ = A.call("/api/keys/link", {"key": K3})
    check("③ 남의 계정에 묶인 키 연결 → 409", st == 409 and "다른 계정" in obj["error"], str(obj))
    st, obj, _ = A.call("/api/keys/link", {"key": K1})
    check("③ 이미 내 열쇠인 키 연결 = 그대로(멱등, 열쇠 2)", st == 200 and len(obj["account"]["keys"]) == 2)
    st, obj, _ = A.call("/api/keys/unlink", {"tag": ACC.fingerprint(K2)[:8]})
    check("③ 해제 → 열쇠 1 · keyindex 에서 사라짐", st == 200 and len(obj["account"]["keys"]) == 1
          and not os.path.exists(os.path.join(ACC.keys_dir, ACC.fingerprint(K2))))
    st, obj, _ = E.login(K2)
    check("③ 해제한 키로 로그인 = 새 계정(id=그 키의 지문)", st == 200 and obj["created"] is True and obj["account"]["id"] == ACC.fingerprint(K2)[:8])
    st, obj, _ = A.call("/api/keys/unlink", {"tag": fp1[:8]})
    check("③ 마지막 열쇠 해제 → 400", st == 400 and "마지막" in obj["error"], str(obj))
    check("③ 없는 표식 해제 → 400", A.call("/api/keys/unlink", {"tag": "deadbeef"})[0] == 400)
    F.call("/launcher/")
    check("③ 로그인 안 한 번호표의 연결/별명 → 401", F.call("/api/keys/link", {"key": K2})[0] == 401 and F.call("/api/nick", {"nick": "x"})[0] == 401)

    print("── ④ 로그아웃")
    st, obj, _ = B.call("/api/logout", {})
    check("④ 로그아웃 200 · /api/me logged_in=false", st == 200 and B.call("/api/me")[1]["logged_in"] is False)
    check("④ 캐릭터 목록이 익명 것(0) · /api/presets.account 없음", B.call("/api/characters")[1]["presets"] == []
          and B.call("/api/presets")[1].get("account") is None)
    check("④ A 는 그대로 로그인 · /api/presets.account 에 별명", A.call("/api/presets")[1]["account"]["nick"] == "카야의 신")
    st, obj, _ = B.login(K1)
    check("④ 다시 들어오면 계정 것(캐릭터 1)", st == 200 and len(B.call("/api/characters")[1]["presets"]) == 1)

    print("── ⑤ 실판(dummy) — 로그인한 세션")
    st, obj, _ = A.call("/api/start", dict(base, key=K1, seed=7))
    check("⑤ 시작 200(두뇌 dummy)", st == 200 and obj["brain"] == "dummy", str(obj))
    meta = wait_stream(os.path.join(ACC.dir, aid, "state", "stream.jsonl"))
    check("⑤ 판 기록이 accounts/<id>/state/stream.jsonl 에(seed 7)", meta is not None and meta["seed"] == 7)
    done = wait_done(A)
    check("⑤ 러너 끝남 · 다른 기기(B)의 /api/status 도 같은 판(seed 7)", done is not None and B.call("/api/status")[1]["seed"] == 7)
    check("⑤ 익명 세션 폴더엔 판 없음", not os.path.exists(os.path.join(TMP, "sessions", A.cookie, "state", "stream.jsonl")))
    st, obj, raw = A.call("/state/stream.jsonl")
    check("⑤ /state/stream.jsonl 이 계정의 판", st == 200 and json.loads(raw.decode("utf-8").splitlines()[0])["seed"] == 7)

    print("── ⑥ 키 미기록")
    time.sleep(0.5)
    hits = key_hits(TMP)
    check("⑥ 데이터 폴더 어디에도 키 없음(accounts·keyindex·logins·sessions)", not hits, str(hits))
    check("⑥ 서버 로그에 키 없음", not any(k in LOG.getvalue() for k in KEYS))

    print("── ⑦ 재시작")
    srv.shutdown()
    srv.server_close()
    srv2, port2 = serve(TMP, max_runs=3, starts_per_hour=20, login_per_hour=2)
    for dev in (A, B, C, D, E, F):
        dev.port = port2
    st, obj, _ = A.call("/api/me")
    check("⑦ 새 서버 + 옛 쿠키 = 로그인 그대로 · 별명 · 캐릭터 1", st == 200 and obj["logged_in"] is True and obj["account"]["nick"] == "카야의 신"
          and len(A.call("/api/characters")[1]["presets"]) == 1)
    check("⑦ 서버 비밀 파일이 같아 지문 동일", srv2.sessions.accounts.fingerprint(K1) == fp1
          and os.path.exists(os.path.join(TMP, "secret")))
    Z1, Z2, Z3 = (Device(port2, n) for n in ("Z1", "Z2", "Z3"))
    codes = [Z1.login(K1)[0], Z2.login(K1)[0], Z3.login(K1)[0]]
    check("⑦ 로그인 IP 시간당 상한 2 → 세 번째 429", codes == [200, 200, 429], str(codes))
    srv2.sessions.stop_all()
    srv2.shutdown()
    srv2.server_close()
finally:
    sys.stderr = old_err

print()
if fails:
    print("FAIL %d — %s" % (len(fails), "; ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_account (D77 계정 = 키 지문: 생존 확인·지문·계정 폴더·열쇠 연결·다른 기기 같은 Ctx·키 미기록)")
