# -*- coding: utf-8 -*-
"""D98 운영자 키 판(공개 서버 server.py) 헤들리스 검증 — LLM 0콜(러너는 dummy 두뇌 · 대부분은 러너 대신 곧 끝나는 프로세스).
2026-09-21 파트너 "우리쪽에서 재미나이3.8 플래시 모델을 제공" · "서버 하루 한도나 한판당 제한량은 필요" · "600턴으로 다시 롤백" ·
"이 판은 이어가기 금지".
게이트:
  ① 꺼짐: 운영자 키가 없으면 presets.house.on false · 키 없는 시작은 옛날처럼 400 · 환경변수로 켜고 끈다(하루 판 수 0 = 끔)
  ② 켜짐: 키 없이 시작 → 러너 환경 = 운영자 키 · 다른 회사 키 비움 · 모델 고정(화면이 보낸 회사·모델 무시) ·
     틱 상한 = 서버 값(표준 원정 1800 과 맵 값보다 앞선다) · 판당 호출 = 운영자 키 판 값 · 생존 확인 없음 · run_opts 에 house 표식(키 없음)
  ③ 자기 키 판은 그대로: 키를 넣으면 그 키 · 표준 원정 1800틱 · 서버 호출 한도 · 생존 확인 · 운영자 키 판 수를 안 쓴다
  ④ 하루 한도: 주소당 → 429(이 주소) · 서버 전체 → 429(다 찼다) · 거절은 수를 안 쓴다 · presets.left 가 주소마다 맞다
  ⑤ 러너가 못 뜬 시작은 한 판으로 치지 않는다(돌려받기)
  ⑥ 사용량 파일: 서버를 다시 띄워도 오늘 쓴 수가 남는다 · 날이 바뀌면 새로 · 주소 문자열은 파일에 없다(지문만)
  ⑦ 이어가기 금지(실제 dummy 판을 곱게 멈춰서): 멈춘 몸(스냅샷)은 있다 · 그래도 status.resume 은 없다 · 대신 status.house_end(사유·틱) ·
     이어가기 400(키를 넣어도) · 론처 Runner.start 도 거절 · 표식만 걷으면 이어갈 몸이 보인다(= 거절의 이유가 표식이다)
  ⑧ 키 미기록: 데이터 폴더 전체·서버 로그·presets 응답에 운영자 키·자기 키 문자열 0회
  ⑨ 화면(정적): 키를 비우고 출발하면 key 를 싣지 않는다 · 관전 정지 패널이 house_end 를 읽는다 · 첫 화면 안내 자리 · 조건 문장은 서버 값에서
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
TMP = tempfile.mkdtemp(prefix="wl_house_")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="")   # 러너(서브프로세스)가 물려받는 짧은 판 설정
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_STATE_DIR", "DUNGEON_STREAM_OBS", "BOTPIKDUN_DATA", "BOTPIKDUN_BRAIN",
          "BOTPIKDUN_MAX_RUNS", "BOTPIKDUN_START_PER_HOUR", "BOTPIKDUN_PAUSE_LIMIT_SEC", "BOTPIKDUN_UNWATCHED_LIMIT_SEC",
          "BOTPIKDUN_API_CALL_LIMIT", "DUNGEON_API_CALL_LIMIT", "DUNGEON_STEP_DELAY", "DUNGEON_RESUME",
          "BOTPIKDUN_HOUSE_KEY", "BOTPIKDUN_HOUSE_MODEL", "BOTPIKDUN_HOUSE_TURNS", "BOTPIKDUN_HOUSE_CALL_LIMIT",
          "BOTPIKDUN_HOUSE_PER_DAY", "BOTPIKDUN_HOUSE_PER_IP_DAY"):
    os.environ.pop(k, None)
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"

import server                                        # noqa: E402
import launcher                                      # noqa: E402

HKEY = "AIzaSyHOUSEKEY-0123456789abcdefghijklmn"      # 가짜 운영자 키(형태만) — 어디에도 남으면 안 된다
OWN = "AIzaSyOWNKEY-0123456789abcdefghijklmnopqr"     # 가짜 자기 키
LOG = io.StringIO()
fails = []


def check(name, cond, note=""):
    print(("PASS " if cond else "FAIL ") + name + ((" — " + note) if note else ""))
    if not cond:
        fails.append(name)


class Judge:
    """심사위원 한 명 = 쿠키 단지 하나 + 자기 주소(X-Forwarded-For — 서버의 _ip 가 먼저 본다)."""
    def __init__(self, port, ip):
        self.port, self.ip, self.cookie = port, ip, None

    def call(self, path, body=None):
        h = {"X-Forwarded-For": self.ip}
        if self.cookie:
            h["Cookie"] = "%s=%s" % (server.COOKIE, self.cookie)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        c.request("POST" if body is not None else "GET", path, body=data, headers=h)
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
        return r.status, raw, obj


def serve(data_dir, **kw):
    srv = server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=data_dir, brain="dummy", **kw)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def judge(port, ip):
    j = Judge(port, ip)
    j.call("/api/presets")                                            # 번호표
    return j


real_popen = launcher.subprocess.Popen
captured = []


def quick_spy(args, **kw):
    """러너 대신 곧 끝나는 프로세스 — 러너에 준 환경변수만 남긴다(판은 안 돈다)."""
    captured.append(dict(kw.get("env") or {}))
    return real_popen([sys.executable, "-c", "pass"], **kw)


def start_spied(j, body):
    launcher.subprocess.Popen = quick_spy
    try:
        st, raw, obj = j.call("/api/start", body)
    finally:
        launcher.subprocess.Popen = real_popen
    ctx = srv_ctx(j)
    if st == 200 and ctx is not None and ctx.runner.proc is not None:
        ctx.runner.proc.wait(10)                                      # 다음 시작이 409 를 받지 않게
    return st, raw, obj


def usage(data_dir):
    try:
        with io.open(os.path.join(data_dir, "house_usage.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


CUR = {}


def srv_ctx(j):
    return CUR["srv"].sessions.get(j.cookie)


asked = []


def fake_alive(key, provider="gemini_api"):
    asked.append(key)
    return True


STD = {"mode": "standard", "action_mode": "compose", "town": False, "party": "default", "seed": 7}   # 화면이 보내는 표준 원정 모양
OLD = {"mode": "classic", "map": "normal", "town": False, "party": "default"}                         # 짧은 판(40x16)

old_err = sys.stderr
sys.stderr = LOG
try:
    print("── ① 꺼짐")
    d_off = os.path.join(TMP, "off")
    srv_off, p_off = serve(d_off)
    CUR["srv"] = srv_off
    A0 = judge(p_off, "10.9.0.1")
    pa = A0.call("/api/presets")[2]
    h0 = (pa or {}).get("house") or {}
    check("① 운영자 키 없음 → presets.house.on false · left 0 · 조건 값은 내려간다(600틱·%s)" % server.HOUSE_MODEL,
          h0.get("on") is False and h0.get("left") == 0 and h0.get("turns") == server.HOUSE_TURNS == 600
          and h0.get("model") == server.HOUSE_MODEL and h0.get("resume") is False, str(h0))
    st, _, obj = A0.call("/api/start", dict(OLD))
    check("① 키 없는 시작 → 400(옛날 그대로 '키')", st == 400 and "키" in (obj or {}).get("error", ""), str(obj))
    check("① 사용량 파일도 안 생긴다", not os.path.exists(os.path.join(d_off, "house_usage.json")))
    srv_off.shutdown(); srv_off.server_close()
    os.environ.update(BOTPIKDUN_HOUSE_KEY=HKEY, BOTPIKDUN_HOUSE_PER_DAY="5", BOTPIKDUN_HOUSE_TURNS="321",
                      BOTPIKDUN_HOUSE_CALL_LIMIT="123", BOTPIKDUN_HOUSE_PER_IP_DAY="4")
    s_env = server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=os.path.join(TMP, "env"), brain="dummy")
    os.environ["BOTPIKDUN_HOUSE_PER_DAY"] = "0"
    s_zero = server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=os.path.join(TMP, "env0"), brain="dummy")
    for k in ("BOTPIKDUN_HOUSE_KEY", "BOTPIKDUN_HOUSE_PER_DAY", "BOTPIKDUN_HOUSE_TURNS", "BOTPIKDUN_HOUSE_CALL_LIMIT",
              "BOTPIKDUN_HOUSE_PER_IP_DAY"):
        os.environ.pop(k, None)
    se = s_env.sessions
    check("① 환경변수로 켠다(키·하루 5·주소 4·321틱·123콜) · 하루 판 수 0 = 끔",
          se.house_on() and se.house_key == HKEY and se.house_per_day == 5 and se.house_per_ip_day == 4
          and se.house_turns == 321 and se.house_call_limit == 123 and not s_zero.sessions.house_on(),
          "%s %s %s %s" % (se.house_per_day, se.house_turns, se.house_call_limit, s_zero.sessions.house_on()))
    for s_ in (s_env, s_zero):
        s_.sessions.stop_all(); s_.server_close()
    try:
        server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=os.path.join(TMP, "bad"), brain="dummy", house_keyy="x")
        bad = False
    except TypeError:
        bad = True
    check("① 모르는 운영자 키 인자는 TypeError(오타가 조용히 기본값이 되지 않게)", bad)

    print("── ② 켜짐 — 키 없이 시작")
    d_on = os.path.join(TMP, "on")
    srv, port = serve(d_on, house_key=HKEY, house_per_day=3, house_per_ip_day=2, key_check=fake_alive)
    CUR["srv"] = srv
    A = judge(port, "10.0.0.1")
    pa = A.call("/api/presets")
    ha = (pa[2] or {}).get("house") or {}
    check("② presets.house = 켜짐 · 이 주소 남은 2 · 하루 3 · 모델·600틱·400콜 · 이어가기 없음",
          ha == {"on": True, "left": 2, "per_day": 3, "per_ip_day": 2, "model": "gemini-3.8-flash", "turns": 600,
                 "call_limit": 400, "resume": False}, str(ha))
    check("② presets 응답에 운영자 키 없음", HKEY.encode() not in pa[1])
    st, raw, obj = start_spied(A, dict(STD, provider="anthropic_api", brain="anthropic_api", model="claude-x", house=False))
    env = captured[-1] if captured else {}
    check("② 시작 200 · 응답에 키 없음", st == 200 and HKEY.encode() not in raw, str(obj))
    check("② 러너 환경: GEMINI_API_KEY = 운영자 키 · 다른 회사 키 비움 · 대체 두뇌 비움",
          env.get("GEMINI_API_KEY") == HKEY and env.get("ANTHROPIC_API_KEY") == "" and env.get("OPENAI_API_KEY") == ""
          and env.get("DUNGEON_BRAIN_FALLBACK") == "", str({k: bool(env.get(k)) for k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY")}))
    check("② 모델 고정(화면의 회사·모델 무시): 두 슬롯 모두 gemini-3.8-flash",
          env.get("DUNGEON_MODEL_HAIKU") == "gemini-3.8-flash" and env.get("DUNGEON_MODEL_SONNET") == "gemini-3.8-flash",
          "%s %s" % (env.get("DUNGEON_MODEL_HAIKU"), env.get("DUNGEON_MODEL_SONNET")))
    check("② 틱 상한 600 — 표준 원정(STANDARD_RUN %s)보다 앞선다" % launcher.STANDARD_RUN["DUNGEON_TURNS"],
          env.get("DUNGEON_TURNS") == "600" and launcher.STANDARD_RUN["DUNGEON_TURNS"] != "600"
          and env.get("DUNGEON_DEPTHS") == launcher.STANDARD_RUN["DUNGEON_DEPTHS"], str(env.get("DUNGEON_TURNS")))
    check("② 판당 호출 = 운영자 키 판 값(400 — 자기 키 판 값 %d 아님)" % srv.sessions.api_call_limit,
          env.get("DUNGEON_API_CALL_LIMIT") == "400" and srv.sessions.api_call_limit != 400, str(env.get("DUNGEON_API_CALL_LIMIT")))
    check("② 운영자 키는 생존 확인을 안 한다", asked == [], str(len(asked)))
    ro = launcher.run_control.read_json(os.path.join(srv_ctx(A).state_dir, launcher.Runner.RUN_OPTS)).get("opts", {})
    check("② run_opts: house 표식 · 키 없음 · 회사 gemini_api", ro.get("house") is True and "key" not in ro
          and ro.get("provider") == "gemini_api" and HKEY not in json.dumps(ro), str({k: ro.get(k) for k in ("house", "provider", "model")}))
    u = usage(d_on)
    check("② 한 판을 썼다(서버 1 · 이 주소 1)", u.get("total") == 1 and sorted(u.get("ip", {}).values()) == [1], str(u))

    print("── ③ 자기 키 판은 그대로")
    B = judge(port, "10.0.0.2")
    st, raw, obj = start_spied(B, dict(STD, key=OWN, provider="gemini_api", seed=8))
    env = captured[-1]
    ro = launcher.run_control.read_json(os.path.join(srv_ctx(B).state_dir, launcher.Runner.RUN_OPTS)).get("opts", {})
    check("③ 200 · 자기 키 · 표준 원정 틱(1800) · 서버 호출 한도 · 생존 확인 1번 · house 표식 없음",
          st == 200 and env.get("GEMINI_API_KEY") == OWN and env.get("DUNGEON_TURNS") == launcher.STANDARD_RUN["DUNGEON_TURNS"]
          and env.get("DUNGEON_API_CALL_LIMIT") == str(srv.sessions.api_call_limit) and asked == [OWN] and "house" not in ro,
          "%s %s %s %s" % (st, env.get("DUNGEON_TURNS"), env.get("DUNGEON_API_CALL_LIMIT"), len(asked)))
    check("③ 운영자 키 판 수를 안 쓴다(그대로 1)", usage(d_on).get("total") == 1, str(usage(d_on)))
    stB = B.call("/api/status")[2] or {}
    check("③ 자기 키 판의 status 에는 house_end 가 없다(키는 additive · 값 null)", "house_end" in stB and stB["house_end"] is None, str(stB.get("house_end")))
    st, _, obj = B.call("/api/start", dict(STD, key="short"))
    check("③ 형태가 틀린 키는 운영자 키로 넘어가지 않고 400", st == 400 and usage(d_on).get("total") == 1, str(obj))

    print("── ④ 하루 한도")
    st2 = start_spied(A, dict(STD, seed=9))[0]
    st3, _, o3 = start_spied(A, dict(STD, seed=10))
    check("④ 같은 주소 두 번째 200 · 세 번째 429(이 주소)", st2 == 200 and st3 == 429 and "이 주소" in (o3 or {}).get("error", ""),
          "%s %s %s" % (st2, st3, o3))
    check("④ 거절은 수를 안 쓴다(서버 2)", usage(d_on).get("total") == 2, str(usage(d_on)))
    C = judge(port, "10.0.0.3")
    stc = start_spied(C, dict(STD, seed=11))[0]
    D = judge(port, "10.0.0.4")
    std_, _, od = start_spied(D, dict(STD, seed=12))
    check("④ 다른 주소 200(서버 3 = 하루 몫) · 그다음 주소는 429(다 찼다 · 자정 · 자기 키 안내)",
          stc == 200 and std_ == 429 and "다 찼다" in (od or {}).get("error", "") and "자기 API 키" in (od or {}).get("error", ""),
          "%s %s %s" % (stc, std_, od))
    left = {j.ip: (j.call("/api/presets")[2] or {}).get("house", {}).get("left") for j in (A, B, C, D)}
    check("④ presets.left: 서버 몫이 다 찼으니 모두 0", set(left.values()) == {0}, str(left))
    st, _, obj = start_spied(D, dict(STD, key=OWN, seed=13))
    check("④ 운영자 키 판이 다 찬 날에도 자기 키 판은 열린다", st == 200, str(obj))

    print("── ⑤ 돌려받기")
    d_back = os.path.join(TMP, "back")
    srv_b, port_b = serve(d_back, house_key=HKEY, house_per_day=1, house_per_ip_day=1)
    CUR["srv"] = srv_b
    E = judge(port_b, "10.1.0.1")
    st, _, obj = start_spied(E, dict(STD, action_mode="xx"))
    check("⑤ 러너가 못 뜬 시작(400)은 한 판으로 치지 않는다", st == 400 and usage(d_back).get("total") == 0, "%s %s" % (st, usage(d_back)))
    st = start_spied(E, dict(STD))[0]
    check("⑤ 그 뒤 제대로 된 시작 200(하루 1 을 그대로 쓴다)", st == 200 and usage(d_back).get("total") == 1, str(usage(d_back)))
    try:                                                              # 동시 시작 경합: 둘 다 엿보기(house_check)를 통과한 뒤 잠금 안에서 쓰는 쪽이 스스로 막아야 한다
        srv_b.sessions.take_house("10.1.0.9")
        raced = False
    except server.HouseSpent:
        raced = True
    check("⑤ take_house 는 엿보기 없이도 스스로 막는다(동시 시작이 하루 수를 넘지 못한다)", raced and usage(d_back).get("total") == 1,
          str(usage(d_back)))
    srv_b.shutdown(); srv_b.server_close()

    print("── ⑥ 사용량 파일")
    srv.shutdown(); srv.server_close()
    srv2, port2 = serve(d_on, house_key=HKEY, house_per_day=3, house_per_ip_day=2)
    CUR["srv"] = srv2
    D2 = judge(port2, "10.0.0.4")
    l_restart = (D2.call("/api/presets")[2] or {}).get("house", {}).get("left")
    check("⑥ 서버를 다시 띄워도 오늘 쓴 수가 남는다(left 0)", l_restart == 0, str(l_restart))
    with open(os.path.join(d_on, "house_usage.json"), "rb") as f:
        rawu = f.read()
    check("⑥ 파일에 주소 문자열이 없다(지문만) · 날짜 = 한국 날짜",
          b"10.0.0." not in rawu and json.loads(rawu.decode("utf-8")).get("day") == server.Sessions.house_today(), rawu[:80].decode("utf-8", "replace"))
    doc = json.loads(rawu.decode("utf-8"))
    doc["day"] = "2000-01-01"
    with open(os.path.join(d_on, "house_usage.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f)
    l_new = (D2.call("/api/presets")[2] or {}).get("house", {}).get("left")
    check("⑥ 날이 바뀌면 새로(left 2)", l_new == 2, str(l_new))
    srv2.shutdown(); srv2.server_close()

    print("── ⑦ 이어가기 금지(실제 dummy 판)")
    os.environ.update(DUNGEON_STEP_DELAY="0.5")                     # 멈출 때까지 끝나지 않는 판(운영자 키 판 틱 상한 400)
    d_res = os.path.join(TMP, "resume")
    srv3, port3 = serve(d_res, house_key=HKEY, house_per_day=3, house_per_ip_day=3, house_turns=400)
    CUR["srv"] = srv3
    G = judge(port3, "10.2.0.1")
    st, _, obj = G.call("/api/start", dict(OLD, seed=11))
    ctxG = srv3.sessions.get(G.cookie)
    sG = os.path.join(ctxG.state_dir, "stream.jsonl")
    meta0, t0 = None, time.time()
    while time.time() - t0 < 30 and meta0 is None:
        G.call("/api/status")                                         # 보고 있다(자동 멈춤 방지)
        try:
            with io.open(sG, encoding="utf-8") as f:
                first = json.loads(f.readline())
            meta0 = first if first.get("kind") == "run_meta" else None
        except (OSError, ValueError):
            pass
        time.sleep(0.3)
    snap, t1 = None, time.time()
    while time.time() - t1 < 30 and snap is None:                    # 루프 머리 스냅샷이 한 번은 찍힐 때까지
        G.call("/api/status")
        snap = launcher.snapshot.read_meta(ctxG.state_dir)
        time.sleep(0.3)
    check("⑦ 운영자 키 판 시작 200 · 판 파일 · 스냅샷(이어갈 몸의 재료)이 생긴다", st == 200 and meta0 is not None and snap is not None,
          "%s %s %s" % (st, bool(meta0), bool(snap)))
    res = ctxG.runner.stop(graceful=True)
    stG = G.call("/api/status")[2] or {}
    body_left = launcher.snapshot.read_meta(ctxG.state_dir)
    check("⑦ 곱게 멈춘 뒤: 몸은 남아 있다(스냅샷) · 그래도 status.resume 은 없다",
          res.get("stopped") and body_left is not None and stG.get("running") is False and stG.get("resume") is None,
          "%s %s %s" % (res.get("stopped"), bool(body_left), stG.get("resume")))
    he = stG.get("house_end") or {}
    check("⑦ 대신 status.house_end = 멈춘 자리(사유·틱) — 화면이 '여기서 끝났다'를 말할 재료",
          bool(he.get("stopped")) and he.get("turn_last") == (body_left or {}).get("turn_last"), str(he))
    st, _, obj = G.call("/api/start", {"resume": True})
    st_k, _, obj_k = G.call("/api/start", {"resume": True, "key": OWN})
    check("⑦ 이어가기 400(키 없이도, 자기 키를 넣어도) · 같은 문장", st == 400 and st_k == 400
          and (obj or {}).get("error") == launcher.HOUSE_NO_RESUME == (obj_k or {}).get("error"), "%s %s" % (obj, obj_k))
    try:
        ctxG.runner.start({"resume": True}, ctxG.party_path)
        direct = False
    except launcher.BadRequest as e:
        direct = str(e) == launcher.HOUSE_NO_RESUME
    check("⑦ 론처 Runner.start 도 거절(서버를 거치지 않아도)", direct)
    ro_path = os.path.join(ctxG.state_dir, launcher.Runner.RUN_OPTS)
    ro_doc = launcher.run_control.read_json(ro_path)
    launcher.run_control.write_json(ro_path, {**ro_doc, "opts": {k: v for k, v in ro_doc["opts"].items() if k != "house"}})
    with_flag_gone = ctxG.runner.resumable(ctxG.runner.status())
    launcher.run_control.write_json(ro_path, ro_doc)
    check("⑦ 표식만 걷으면 이어갈 몸이 보인다 = 거절의 이유가 표식이다", bool(with_flag_gone)
          and ctxG.runner.resumable(ctxG.runner.status()) is None, str(with_flag_gone)[:100])
    check("⑦ 그 판의 run_meta.max_turns = 400(서버 값 — 부모 환경의 6 이 아니다)", meta0 is not None and meta0.get("max_turns") == 400,
          str(meta0.get("max_turns") if meta0 else None))
    srv3.sessions.stop_all()
    srv3.shutdown(); srv3.server_close()
    os.environ.pop("DUNGEON_STEP_DELAY", None)

    print("── ⑧ 키 미기록")
    hits = []
    for root, _, files in os.walk(TMP):
        for fn in files:
            with open(os.path.join(root, fn), "rb") as f:
                b = f.read()
            for label, k in (("운영자", HKEY), ("자기", OWN)):
                if k.encode() in b:
                    hits.append((label, os.path.relpath(os.path.join(root, fn), TMP)))
    n_files = sum(len(fs) for _, _, fs in os.walk(TMP))
    check("⑧ 데이터 폴더 전체(%d파일)에 운영자 키·자기 키 없음" % n_files, not hits and n_files > 10, str(hits))
    check("⑧ 서버 로그(%d자)에 키 없음" % len(LOG.getvalue()), HKEY not in LOG.getvalue() and OWN not in LOG.getvalue()
          and len(LOG.getvalue()) > 0)

    print("── ⑨ 화면(정적)")
    with io.open(os.path.join(HERE, "launcher", "index.html"), encoding="utf-8") as f:
        html = f.read()
    i = html.find("if (houseOpen())")
    branch = html[i:i + 400] if i >= 0 else ""
    check("⑨ 키를 비우고 출발하면 key 를 싣지 않는다(서버가 운영자 키 판으로 판단)", "delete body.key" in branch)
    with io.open(os.path.join(HERE, "viewer", "assets", "brain-pause.js"), encoding="utf-8") as f:
        bp = f.read()
    check("⑨ 관전 화면 정지 패널이 status.house_end 를 읽고 시작 화면으로 보낸다(이어가기 버튼 없음)",
          "status?.house_end" in bp and "(budget || houseEnd)" in bp and "시작 화면으로" in bp)
    check("⑨ 첫 화면 안내 자리(tHouseNote) · 조건 문장은 서버 값(house.turns·house.model·house.left)에서",
          'id="tHouseNote"' in html and "${house.turns}" in html and "${house.model}" in html and "${house.left}" in html)
finally:
    sys.stderr = old_err
    launcher.subprocess.Popen = real_popen

if fails:
    print("FAILED %d: %s" % (len(fails), fails))
    sys.exit(1)
print("ALL PASS — verify_house (D98 운영자 키 판: 모델 고정·600틱·판당 호출·하루 판 수·이어가기 없음·키 미기록)")
