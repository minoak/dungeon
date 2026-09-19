# -*- coding: utf-8 -*-
"""공개(심사용) 서버 server.py 헤들리스 검증 — 62번째 게이트. LLM 0콜(러너는 dummy 두뇌).
게이트:
  ① 허용 목록: / → /launcher/ 302 · /launcher/ 200+쿠키(HttpOnly·SameSite=Lax, X-Forwarded-Proto=https 일 때만 Secure) ·
     /.env /launcher.py /design/… /viewer/*.py /state/(목록) /state/../.. → 404 · /viewer/tiles.json 200 · 자산 요청은 번호표를 안 만든다
  ② 세션: 번호표가 다르면 Ctx(state/·runs/·파티 파일)가 다르다 · /api/presets 에 byok·public 표식
  ③ 시작 거부: 키 없음/짧음/공백 → 400 · 상한 밖 경로 POST → 404
  ④ 실판(dummy): 두 심사위원이 각자 시드로 동시에 → 각자의 /state/stream.jsonl 에 각자의 run_meta.seed · /api/status 도 각자 ·
     화면이 고른 두뇌는 무시되고 서버 두뇌로 · .jsonl 은 text/plain · /runs/ 목록은 자기 것만
  ⑤ 상한: 동시 판 max_runs 넘으면 429 · 같은 세션 두 번째 시작 409 · IP 시간당 시작 상한 429
  ⑥ 키 미기록: 세션 폴더 전체(runner.out·state·runs)와 서버 로그에 키 문자열 0회
  ⑦ 서버 재시작: 같은 데이터 폴더로 새 서버 → 옛 쿠키로 /api/status·/state/stream.jsonl 이 그대로 읽힌다
  ⑧ F1 시작 때 키 생존 확인 · ⑨ F5 쓰는 중인 판 파일을 읽어도 죽지 않는다
  ⑩ D91 자리 관리(2026-09-20): 기본 10분 둘·환경변수(0 = 끔)·로컬 론처엔 없음 · 관전 폴링(/api/status·/state/…)이 이어지면 계속 돌고,
     끊기면 제한 시간 뒤 러너가 곱게 닫힌다(stopped 줄 reason unwatched·수첩 없음·end 없음) · 돌아온 방문자의 /api/status.resume.stopped =
     unwatched → 이어가기 200·resume 줄도 같은 사유 · 끊은 판(terminate)에도 사유가 요약에 남는다 · 서버를 닫으면 살피기 스레드도 내려간다
"""
import http.client
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_public_")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="")   # 러너(서브프로세스)가 물려받는 짧은 판 설정
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_STATE_DIR", "DUNGEON_STREAM_OBS", "BOTPIKDUN_DATA", "BOTPIKDUN_BRAIN",
          "BOTPIKDUN_MAX_RUNS", "BOTPIKDUN_START_PER_HOUR", "BOTPIKDUN_PAUSE_LIMIT_SEC", "BOTPIKDUN_UNWATCHED_LIMIT_SEC",
          "DUNGEON_STEP_DELAY", "DUNGEON_RESUME"):
    os.environ.pop(k, None)
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"

import server                                        # noqa: E402

KEY = "AIzaSyTESTKEY-0123456789abcdefghijklmnop"      # 가짜 키(형태만) — 어디에도 남으면 안 된다
UNWATCHED = 4                                        # ⑩ 관전자 없는 판의 제한 시간(초)을 줄여서 본다 — 서버 기본은 600(살피기 간격 = 1/4 = 1초)
LOG = io.StringIO()                                  # 서버 로그(Handler.log_message → sys.stderr) 채집
fails = []


def check(name, cond, note=""):
    print(("PASS " if cond else "FAIL ") + name + ((" — " + note) if note else ""))
    if not cond:
        fails.append(name)


class Judge:
    """심사위원 한 명 = 쿠키 단지 하나."""
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
        out = (r.status, {k.lower(): v for k, v in r.getheaders()}, raw, obj, sc)   # 헤더 이름은 소문자로(http.server 는 Content-type)
        c.close()
        return out


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


def wait_done(judge, sec=40):
    t0 = time.time()
    while time.time() - t0 < sec:
        st = judge.call("/api/status")[3]
        if st and not st["running"]:
            return st
        time.sleep(0.3)
    return None


old_err = sys.stderr
sys.stderr = LOG
try:
    srv, port = serve(TMP, max_runs=3, starts_per_hour=5)
    A, B, C, D = (Judge(port, n) for n in "ABCD")
    print("── ① 허용 목록")
    st, h, _, _, sc = A.call("/")
    check("① / → 302 /launcher/ + 첫 방문 쿠키(HttpOnly·SameSite=Lax·Secure 없음)", st == 302 and h.get("location") == "/launcher/"
          and "HttpOnly" in sc and "SameSite=Lax" in sc and "Secure" not in sc and A.cookie and len(A.cookie) == 32, sc[:60])
    st, h, raw, _, sc = A.call("/launcher/")
    check("① /launcher/ 200 · 번호표 있으면 새로 안 줌", st == 200 and b"<html" in raw[:200].lower() and not sc)
    st, h, raw, _, sc = B.call("/launcher/", headers={"X-Forwarded-Proto": "https"})
    check("① X-Forwarded-Proto=https 면 Secure 쿠키", st == 200 and "; Secure" in sc)
    for bad in ("/.env", "/launcher.py", "/server.py", "/design/HARNESS_DESIGN.md", "/viewer/_shot_server.py",
                "/state/", "/state/../../party.json", "/runs/../party.json", "/party.json", "/prompts/", "/scripts/vm/setup.sh"):
        st = A.call(bad)[0]
        check("① %s → 404" % bad, st == 404, "got %s" % st)
    st, h, raw, _, _ = A.call("/viewer/tiles.json")
    check("① /viewer/tiles.json 200", st == 200 and raw[:1] == b"{")
    st = A.call("/api/nope")[0]
    check("① /api/nope → 404", st == 404)
    st, h, raw, obj, _ = A.call("/api/party", {"slots": []}, method="POST")
    check("① 상한 밖 POST /notapi → 404", A.call("/notapi", {"x": 1}, method="POST")[0] == 404)
    fresh = Judge(port, "asset")
    st, h, raw, _, sc = fresh.call("/viewer/tiles.json")
    check("① 자산 요청은 번호표를 안 만든다", st == 200 and not sc and fresh.cookie is None)
    st, _, _, _, sc = fresh.call("/game/assets/__missing_public_probe__.js")
    check("① 쿠키 없는 게임 자산 요청도 연결을 끊지 않음 · 번호표 없음",
          st in (404, 503) and not sc and fresh.cookie is None, str(st))
    st, _, _, obj, sc = fresh.call("/healthz")
    check("① GET /healthz 200 · 상태 확인은 세션을 만들지 않음",
          st == 200 and obj.get("ok") is True and not sc and fresh.cookie is None)
    n_dirs = len(os.listdir(os.path.join(TMP, "sessions")))
    check("① 세션 폴더 = 번호표 받은 수(2)", n_dirs == 2, str(n_dirs))

    print("── ② 세션")
    pa, pb = A.call("/api/presets")[3], B.call("/api/presets")[3]
    check("② /api/presets byok·public 표식 + status", pa and pa.get("byok") is True and pa.get("public") is True
          and pa["status"]["running"] is False and pa["max_runs"] == 3)
    check("② 번호표가 다르다", A.cookie != B.cookie)
    ctxA, ctxB = srv.sessions.get(A.cookie), srv.sessions.get(B.cookie)
    check("② Ctx 가 다르다(state·runs·파티 파일)", ctxA is not ctxB and ctxA.state_dir != ctxB.state_dir
          and ctxA.runs_dir != ctxB.runs_dir and ctxA.party_path != ctxB.party_path
          and ctxA.state_dir.startswith(os.path.join(TMP, "sessions", A.cookie)))

    print("── ③ 시작 거부")
    base = {"mode": "classic", "map": "normal", "town": False, "party": "default", "brain": "claude_cli"}
    for label, body in (("키 없음", dict(base)), ("키 짧음", dict(base, key="short")),
                        ("키에 공백", dict(base, key="AIza 0123456789 0123456789")), ("키가 문자열 아님", dict(base, key=123))):
        st, _, _, obj, _ = A.call("/api/start", body)
        check("③ %s → 400" % label, st == 400 and "키" in (obj or {}).get("error", ""), str(obj))
    check("③ 거부된 시작은 러너를 안 띄운다", A.call("/api/status")[3]["running"] is False)

    print("── ④ 실판(dummy) 두 세션 동시")
    captured = {}
    real_popen = server.launcher.subprocess.Popen
    def spy(args, **kw):                                              # 러너에 준 환경변수만 엿본다(한 번)
        captured.update(kw.get("env") or {})
        server.launcher.subprocess.Popen = real_popen
        return real_popen(args, **kw)
    server.launcher.subprocess.Popen = spy
    stA, _, _, oA, _ = A.call("/api/start", dict(base, key=KEY, seed=7))
    server.launcher.subprocess.Popen = real_popen
    check("④ 러너 환경변수: GEMINI_API_KEY=키 · ANTHROPIC_API_KEY 비움 · 대체 두뇌 비움 · 두뇌 dummy · 원장 없음",
          captured.get("GEMINI_API_KEY") == KEY and captured.get("ANTHROPIC_API_KEY") == "" and captured.get("OPENAI_API_KEY") == "" and captured.get("DUNGEON_BRAIN_FALLBACK") == ""
          and captured.get("DUNGEON_BRAIN_BACKEND") == "dummy" and captured.get("DUNGEON_BESTIARY_FILE") == "",
          str({k: captured.get(k) for k in ("DUNGEON_BRAIN_BACKEND", "DUNGEON_BESTIARY_FILE")}))
    check("④ F1 러너에 판단 정지 제한 시간을 넘긴다(서버 기본값)", captured.get("DUNGEON_PAUSE_LIMIT_SEC") == str(server.PAUSE_LIMIT_SEC)
          and server.PAUSE_LIMIT_SEC > 0, str(captured.get("DUNGEON_PAUSE_LIMIT_SEC")))
    stB, _, _, oB, _ = B.call("/api/start", dict(base, key=KEY, seed=11))
    check("④ 두 세션 시작 200 · 두뇌는 서버 것(dummy, 화면의 claude_cli 무시)", stA == 200 and stB == 200
          and oA["brain"] == "dummy" and oB["brain"] == "dummy", "%s %s" % (oA, oB))
    check("④ 응답에 키 없음", KEY not in json.dumps(oA) + json.dumps(oB))
    mA = wait_stream(os.path.join(ctxA.state_dir, "stream.jsonl"))
    mB = wait_stream(os.path.join(ctxB.state_dir, "stream.jsonl"))
    check("④ 각자의 state/stream.jsonl 에 각자의 run_meta.seed", mA and mB and mA["seed"] == 7 and mB["seed"] == 11,
          "%s %s" % (mA and mA.get("seed"), mB and mB.get("seed")))
    eA, eB = wait_done(A), wait_done(B)
    check("④ 러너 둘 다 끝남(dummy·6틱)", eA is not None and eB is not None)
    sA, sB = A.call("/api/status")[3], B.call("/api/status")[3]
    check("④ /api/status 도 각자(seed 7 / 11)", sA["seed"] == 7 and sB["seed"] == 11, "%s %s" % (sA["seed"], sB["seed"]))
    def first_seed(raw):
        try:
            return json.loads(raw.split(b"\n", 1)[0].decode("utf-8")).get("seed")
        except (ValueError, UnicodeDecodeError, IndexError):
            return None
    st, h, raw, _, _ = A.call("/state/stream.jsonl")
    check("④ /state/stream.jsonl 200 · text/plain · 세션 A 의 것(seed 7)", st == 200 and h.get("content-type", "").startswith("text/plain")
          and first_seed(raw) == 7, "%s %s" % (h.get("content-type"), first_seed(raw)))
    st, h, raw, _, _ = B.call("/state/stream.jsonl")
    check("④ 세션 B 의 것은 seed 11", st == 200 and first_seed(raw) == 11, str(first_seed(raw)))
    st, _, _, oA2, _ = A.call("/api/start", dict(base, key=KEY, seed=8))          # 두 번째 판 → 첫 판이 runs/ 로 보존
    eA2 = wait_done(A)
    st, h, raw, _, _ = A.call("/runs/")
    names = [n for n in os.listdir(ctxA.runs_dir)]
    check("④ /runs/ 목록은 자기 세션 것(보존된 판 1)", st == 200 and len(names) == 1 and names[0].encode() in raw
          and b"stream-" in raw, str(names))
    st = B.call("/runs/" + names[0])[0]
    check("④ 남의 세션 판은 404", st == 404)
    st = A.call("/runs/" + names[0])[0]
    check("④ 자기 세션 판은 200", st == 200)

    print("── ⑤ 상한")
    sleepers = []
    for j in (A, B, C):
        j.call("/api/presets")                                          # C 도 번호표
        ctx = srv.sessions.get(j.cookie)
        ctx.runner.proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])   # 오래 도는 판 흉내
        sleepers.append(ctx.runner.proc)
    st, _, _, obj, _ = D.call("/api/start", dict(base, key=KEY, seed=9))
    check("⑤ 동시 판 3 = 상한 → 네 번째 심사위원 429", st == 429 and "자리" in obj.get("error", ""), str(obj))
    st, _, _, obj, _ = A.call("/api/start", dict(base, key=KEY, seed=9))
    check("⑤ 같은 세션 두 번째 시작 → 409", st == 409, str(obj))
    check("⑤ /healthz running=3", A.call("/healthz")[3].get("running") == 3)
    for p in sleepers:
        p.kill(); p.wait()
    srv2, port2 = serve(os.path.join(TMP, "rate"), max_runs=3, starts_per_hour=2)
    E = Judge(port2, "E")
    E.call("/api/presets")
    codes = []
    for seed in (7, 8, 9):
        st, _, _, obj, _ = E.call("/api/start", dict(base, key=KEY, seed=seed))
        codes.append(st)
        if st == 200:
            wait_done(E)
    check("⑤ IP 시간당 시작 2 → 세 번째 429", codes == [200, 200, 429], str(codes))
    srv2.shutdown()

    print("── ⑥ 키 미기록")
    hits = []
    for root, _, files in os.walk(TMP):
        for fn in files:
            with open(os.path.join(root, fn), "rb") as f:
                if KEY.encode() in f.read():
                    hits.append(os.path.relpath(os.path.join(root, fn), TMP))
    check("⑥ 세션 폴더 어디에도 키 없음(runner.out·state·runs)", not hits, str(hits))
    check("⑥ 서버 로그에 키 없음", KEY not in LOG.getvalue())

    print("── ⑦ 서버 재시작 뒤 세션 되살림")
    srv.shutdown()
    srv3, port3 = serve(TMP, max_runs=3, starts_per_hour=5)
    A3 = Judge(port3, "A3"); A3.cookie = A.cookie
    st3 = A3.call("/api/status")[3]
    st, h, raw, _, sc = A3.call("/state/stream.jsonl")
    check("⑦ 옛 쿠키로 /api/status(seed 8)·/state/stream.jsonl 그대로, 새 쿠키 안 줌",
          st3 and st3["seed"] == 8 and st == 200 and not sc, "%s %s %r" % (st3 and st3["seed"], st, sc))
    Z = Judge(port3, "Z")
    Z.cookie = "zz" * 16
    stz = Z.call("/launcher/")[0]
    check("⑦ 엉터리 쿠키는 새 번호표", stz == 200 and Z.cookie != "zz" * 16 and len(Z.cookie) == 32)
    srv3.shutdown()

    print("── ⑧ F1 시작 때 키 생존 확인(생존 확인 대역 — 네트워크 0)")
    DEAD = "AIzaSyDEADKEY-0123456789abcdefghijklmnop"      # 형태는 맞지만 회사가 거부하는 키
    asked, boom = [], {"on": False}
    def fake_alive(key, provider="gemini_api"):
        asked.append(key)
        if boom["on"]:
            raise server.KeyCheckUnavailable("test")
        return key != DEAD
    srv4, port4 = serve(os.path.join(TMP, "alive"), max_runs=3, starts_per_hour=3, key_check=fake_alive, pause_limit=77)
    F = Judge(port4, "F")
    F.call("/api/presets")
    st, _, _, obj, _ = F.call("/api/start", dict(base, key=DEAD, seed=7))
    check("⑧ 죽은 키 → 400 · 러너 안 뜸 · 응답에 키 없음", st == 400 and "유효" in (obj or {}).get("error", "")
          and F.call("/api/status")[3]["running"] is False and DEAD not in json.dumps(obj), str(obj))
    boom["on"] = True
    st, _, _, obj, _ = F.call("/api/start", dict(base, key=KEY, seed=7))
    check("⑧ 회사에 못 닿음 → 503 · 러너 안 뜸", st == 503 and F.call("/api/status")[3]["running"] is False, str(obj))
    boom["on"] = False
    captured4 = {}
    def spy4(args, **kw):
        captured4.update(kw.get("env") or {})
        server.launcher.subprocess.Popen = real_popen
        return real_popen(args, **kw)
    server.launcher.subprocess.Popen = spy4
    st, _, _, obj, _ = F.call("/api/start", dict(base, key=KEY, seed=7))
    server.launcher.subprocess.Popen = real_popen
    check("⑧ 산 키 → 200 · 확인은 시도마다 한 번(3) · 제한 시간은 서버 설정값(77)", st == 200 and asked == [DEAD, KEY, KEY]
          and captured4.get("DUNGEON_PAUSE_LIMIT_SEC") == "77", "%s %s %s" % (st, len(asked), captured4.get("DUNGEON_PAUSE_LIMIT_SEC")))
    wait_done(F)
    st, _, _, obj, _ = F.call("/api/start", dict(base, key=DEAD, seed=8))
    check("⑧ 죽은 키의 시도도 시작 횟수를 쓴다 — 네 번째는 확인 없이 429(키 검사기로 못 쓴다)", st == 429 and len(asked) == 3,
          "%s %s" % (st, len(asked)))
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    srv4.sessions.get(F.cookie).runner.proc = sleeper
    st, _, _, obj, _ = F.call("/api/start", dict(base, key=DEAD, seed=9))
    check("⑧ 이미 도는 판이면 확인 전에 409(횟수·확인 안 씀)", st == 409 and len(asked) == 3, "%s %s" % (st, len(asked)))
    sleeper.kill(); sleeper.wait()

    print("── ⑨ F5 쓰는 중인 판 파일(반 토막 한글)을 읽어도 죽지 않는다")
    import campaign                                                      # noqa: E402
    ctxF = srv4.sessions.get(F.cookie)
    spath = os.path.join(ctxF.state_dir, "stream.jsonl")
    with open(spath, "rb") as f:
        whole = f.read()
    n_whole = sum(1 for _ in campaign._iter(spath))
    with open(spath, "ab") as f:
        f.write('{"kind":"tick","turn":99,"say":"'.encode("utf-8") + "한".encode("utf-8")[:1])   # 러너가 긴 줄을 쓰는 도중의 모습
    st, _, _, obj, _ = F.call("/api/status")
    check("⑨ /api/status 200 · 온전한 줄까지의 사실(seed 7)", st == 200 and obj and obj.get("seed") == 7 and obj.get("turn") != 99, str(obj)[:120])
    check("⑨ campaign._iter 도 온전한 줄까지만", sum(1 for _ in campaign._iter(spath)) == n_whole, str(n_whole))
    with open(spath, "wb") as f:
        f.write(whole)
    srv4.shutdown()

    print("── ⑩ D91 자리 관리: 관전자 없는 판 자동 멈춤(제한 시간을 %d초로 줄여서)" % UNWATCHED)
    check("⑩ 기본값 = 파트너 확정 10분 둘(상수 한 곳씩) · 기본 서버엔 살피기 스레드가 있다",
          server.PAUSE_LIMIT_SEC == 600 and server.UNWATCHED_LIMIT_SEC == 600 and srv.sessions.unwatched_limit == 600
          and srv.sessions.watcher is not None, "%s %s" % (server.UNWATCHED_LIMIT_SEC, srv.sessions.unwatched_limit))
    os.environ["BOTPIKDUN_UNWATCHED_LIMIT_SEC"] = "0"
    srv_off = server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=os.path.join(TMP, "off"), brain="dummy")
    os.environ["BOTPIKDUN_UNWATCHED_LIMIT_SEC"] = "77"
    srv_env = server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=os.path.join(TMP, "env"), brain="dummy")
    os.environ.pop("BOTPIKDUN_UNWATCHED_LIMIT_SEC", None)
    check("⑩ 환경변수 BOTPIKDUN_UNWATCHED_LIMIT_SEC: 0 = 끔(스레드 없음) · 77 = 77초",
          srv_off.sessions.unwatched_limit == 0 and srv_off.sessions.watcher is None and srv_off.sessions.stop_unwatched() == 0
          and srv_env.sessions.unwatched_limit == 77, "%s %s" % (srv_off.sessions.unwatched_limit, srv_env.sessions.unwatched_limit))
    for s_ in (srv_off, srv_env):
        s_.sessions.stop_all()
        s_.server_close()
    with io.open(os.path.join(HERE, "launcher.py"), encoding="utf-8") as f:
        lsrc = f.read()
    check("⑩ 로컬 론처에는 자동 멈춤이 없다(시계·살피기 없음 — 사유를 받아 적는 길만)",
          "unwatched_limit" not in lsrc and "stop_unwatched" not in lsrc and "start_watcher" not in lsrc and "reason=None" in lsrc)
    os.environ.update(DUNGEON_TURNS="400", DUNGEON_STEP_DELAY="0.5")     # 자식 러너가 물려받는다 — 멈출 때까지 끝나지 않는 긴 판(seed 11 = 102틱, 0콜 실측)
    srv5, port5 = serve(os.path.join(TMP, "unwatched"), max_runs=3, starts_per_hour=5, unwatched_limit=UNWATCHED)
    G = Judge(port5, "G")
    pg = G.call("/api/presets")[3]
    check("⑩ /api/presets 에 두 제한 시간(additive)", pg.get("unwatched_limit") == UNWATCHED and pg.get("pause_limit") == server.PAUSE_LIMIT_SEC,
          "%s %s" % (pg.get("unwatched_limit"), pg.get("pause_limit")))
    st, _, _, obj, _ = G.call("/api/start", dict(base, key=KEY, seed=11))
    ctxG = srv5.sessions.get(G.cookie)
    sG = os.path.join(ctxG.state_dir, "stream.jsonl")
    check("⑩ 판 시작 200 · 판 파일이 생긴다", st == 200 and wait_stream(sG) is not None, str(obj))
    t0, n_poll, t_last = time.time(), 0, time.time()
    while time.time() - t0 < UNWATCHED * 2 + 1:                         # 보는 동안 — 론처 화면(상태)과 관전 클라이언트(판 파일)의 폴링을 번갈아 흉내
        t_last = time.time()                                             # 마지막 관전 요청을 보내기 직전(서버의 시계는 이 뒤에 다시 잰다)
        G.call("/api/status" if n_poll % 2 else "/state/stream.jsonl")
        n_poll += 1
        time.sleep(0.4)
    check("⑩ 관전 폴링이 이어지는 동안은 제한 시간의 두 배가 지나도 돈다", ctxG.runner.running(), "polls %d" % n_poll)
    while ctxG.runner.running() and time.time() - t_last < 90:          # 이제 아무도 안 본다 — 서버 안에서만 지켜본다(HTTP 로 물으면 그게 관전이다)
        time.sleep(0.2)
    gone = time.time() - t_last
    check("⑩ 폴링이 끊기면 제한 시간 뒤 러너가 닫힌다(그 전에는 아니다)", not ctxG.runner.running() and gone >= UNWATCHED,
          "%.1fs" % gone)
    check("⑩ 러너가 스스로 닫혔다(곱게 — 종료 코드 0) · stop.json 은 지워짐", ctxG.runner.proc.returncode == 0
          and not os.path.exists(os.path.join(ctxG.state_dir, "stop.json")), str(ctxG.runner.proc.returncode))
    with io.open(sG, encoding="utf-8") as f:
        recsG = [json.loads(ln) for ln in f if ln.strip()]
    lastG = recsG[-1] if recsG else {}
    check("⑩ 기록: 마지막 줄 = stopped(reason unwatched · 수첩 없음) · end 없음",
          lastG.get("kind") == "stopped" and lastG.get("reason") == "unwatched" and "pages" not in lastG
          and not any(r.get("kind") == "end" for r in recsG), str(lastG)[:120])
    stG = G.call("/api/status")[3]
    rsG = (stG or {}).get("resume") or {}
    check("⑩ 돌아온 방문자의 /api/status: running false · outcome 없음 · resume(이어갈 몸).stopped = unwatched",
          stG and stG["running"] is False and stG.get("outcome") is None and rsG.get("stopped") == "unwatched"
          and rsG.get("turn_last") == lastG.get("turn") and rsG.get("pages") == [], str(rsG)[:160])
    st, _, _, obj, _ = G.call("/api/start", {"resume": True, "key": KEY})
    check("⑩ 이어가기 200(같은 판 · 멈춘 틱에서)", st == 200 and obj.get("resumed") is True and obj.get("from_turn") == lastG.get("turn"), str(obj))
    t2, resumeG = time.time(), []
    while time.time() - t2 < 30 and not resumeG:                         # 폴링하며 기다린다(= 보고 있다)
        G.call("/api/status")
        with io.open(sG, encoding="utf-8", errors="replace") as f:
            for ln in f:
                try:
                    r_ = json.loads(ln)
                except ValueError:
                    continue
                if r_.get("kind") == "resume":
                    resumeG.append(r_)
        time.sleep(0.3)
    check("⑩ resume 줄이 앞 조각의 사유를 말한다(stopped unwatched)", len(resumeG) == 1 and resumeG[0].get("stopped") == "unwatched"
          and ctxG.runner.running(), str(resumeG)[:160])
    t3, meta_mid = time.time(), None
    while time.time() - t3 < 30:                                         # 이어간 러너가 틱을 돌아 요약의 stop 이 다시 비워질 때까지(루프 머리 스냅샷 = stop None)
        G.call("/api/status")
        meta_mid = server.launcher.snapshot.read_meta(ctxG.state_dir)
        if meta_mid and meta_mid.get("stop") is None and (meta_mid.get("turn_last") or 0) > lastG.get("turn", 0):
            break
        time.sleep(0.3)
    check("⑩ 이어간 판이 돈다 — 요약의 stop 은 다시 비었다", bool(meta_mid) and meta_mid.get("stop") is None, str(meta_mid)[:120])
    res = ctxG.runner.stop(graceful=False, reason="unwatched")           # 곱게 닫힐 틈 없이 끊은 판에도 사유가 남는다(요약만 — 몸은 루프 머리 그대로)
    rsG2 =(G.call("/api/status")[3] or {}).get("resume") or {}
    n_stopped = 0
    with io.open(sG, encoding="utf-8", errors="replace") as f:
        for ln in f:                                                     # 끊긴 판의 마지막 줄은 반 토막일 수 있다 — 온전한 줄만 센다
            try:
                n_stopped += json.loads(ln).get("kind") == "stopped"
            except ValueError:
                pass
    check("⑩ 끊은 판(terminate)도 resume.stopped = unwatched · stopped 줄은 늘지 않는다(러너가 쓴 것만 기록)",
          res.get("stopped") and not res.get("graceful") and rsG2.get("stopped") == "unwatched" and n_stopped == 1,
          "%s %s %d" % (res, rsG2.get("stopped"), n_stopped))
    ctxG.watched -= 10000                                                # 안 도는 판은 아무리 오래 안 봐도 건드리지 않는다
    check("⑩ 도는 판이 없으면 멈출 것도 없다", srv5.sessions.stop_unwatched() == 0)
    srv5.sessions.stop_all()
    check("⑩ 서버를 닫으면 살피기 스레드도 내려간다", (srv5.sessions.watcher.join(5) or True) and not srv5.sessions.watcher.is_alive())
    srv5.shutdown()
    os.environ.update(DUNGEON_TURNS="6")
    os.environ.pop("DUNGEON_STEP_DELAY", None)
finally:
    sys.stderr = old_err

if fails:
    print("FAILED %d: %s" % (len(fails), fails))
    sys.exit(1)
print("ALL PASS — verify_public (D68 공개 서버: 허용 목록·세션·BYOK 키 미기록·상한·재시작)")
