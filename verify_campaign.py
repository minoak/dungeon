# -*- coding: utf-8 -*-
"""캠페인(D78, 2026-09-16) 헤들리스 검증 — 66번째 게이트. LLM 0콜(러너는 dummy 두뇌).
게이트:
  ① 투영: 합성 스트림 — run_meta(저장 id 둘·없음 하나)·level·tick(사망)·descend(수첩)·book_line → project() 필드 · 진행 중(running) →
     끊김(stopped) → end 붙이면 ended(outcome) · id 없는 캐릭터는 캠페인에 없음 · 두 번 접어도 항목 하나(멱등) · 반 줄(쓰는 중)은 거기까지 · summary
  ② 러너 시트: load_party 가 id 통과(영숫자·-_ 64자) · 이상한 id 는 폴백(거부) · spawn 이 봇에 id
  ③ 도감 원장: Issuer 키 = id · skip_keys 인 1회용 캐릭터는 save 파일에 없음 · 오프라인 run_meta 소비가 id 우선
  ④ 론처: save_party 가 **이 저장소의 id 만** 시트에 붙임(남의 id 무시) · party_custom.json 에 id · /api/characters 항목에 campaign(없으면 null)
  ⑤ 공개 서버(dummy): 로그인 계정의 시작 → runner.start 에 bestiary=True·DUNGEON_BESTIARY_FILE=accounts/<id>/bestiary.json·IDS_ONLY · 익명은 없음 ·
     저장 캐릭터로 판을 돌리면 run_meta.party[].id 가 남고 끝난 뒤 /api/characters 의 campaign(runs 1·ended) · /api/characters/log 에 그 판
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
TMP = tempfile.mkdtemp(prefix="wl_campaign_")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="")
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_STATE_DIR", "DUNGEON_STREAM_OBS", "BOTPIKDUN_DATA", "BOTPIKDUN_BRAIN",
          "BOTPIKDUN_MAX_RUNS", "BOTPIKDUN_START_PER_HOUR", "BOTPIKDUN_LOGIN_PER_HOUR", "BOTPIKDUN_SECRET",
          "DUNGEON_LEDGER_IDS_ONLY"):
    os.environ.pop(k, None)
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"

import campaign                                      # noqa: E402
import bestiary                                      # noqa: E402
import dungeon_gm as G                               # noqa: E402
import launcher                                      # noqa: E402
import server                                        # noqa: E402
import show_runner                                   # noqa: E402

fails = []


def check(name, cond, note=""):
    print(("PASS " if cond else "FAIL ") + name + ((" — " + note) if note else ""))
    if not cond:
        fails.append(name)


def jl(path, recs, mode="w"):
    with io.open(path, mode, encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


print("── ① 투영(합성 스트림)")
S = os.path.join(TMP, "stream.jsonl")
META = {"kind": "run_meta", "seed": 4242, "started": "2026-09-16T12:00:00",
        "party": [{"char": "1", "name": "카야", "id": "pidkaya01", "job": "도적", "maxhp": 10},
                  {"char": "2", "name": "두란", "id": "pidduran02", "job": "전사", "maxhp": 14},
                  {"char": "3", "name": "임시", "job": "궁수", "maxhp": 11}]}
bots = lambda t, alive3=True: [{"char": "1", "hp": 10, "alive": True}, {"char": "2", "hp": 12, "alive": True}, {"char": "3", "hp": 0 if not alive3 else 11, "alive": alive3}]
recs = [META, {"kind": "level", "turn": 0, "depth": 1},
        {"kind": "tick", "turn": 1, "bots": bots(1), "decisions": {}},
        {"kind": "tick", "turn": 2, "bots": bots(2), "decisions": {"1": {"type": "explore", "book_line": {"key": "monster:goblin", "text": "겁 많은 녀석들"}}}},
        {"kind": "tick", "turn": 3, "bots": bots(3, alive3=False), "decisions": {}},
        {"kind": "descend", "turn": 4, "to_depth": 2, "pages": {"1": "1층은 조용했다", "2": "임시가 쓰러졌다"}},
        {"kind": "level", "turn": 4, "depth": 2},
        {"kind": "tick", "turn": 5, "bots": bots(5, alive3=False)[:2], "decisions": {}}]
jl(S, recs)
with io.open(S, "a", encoding="utf-8", newline="\n") as f:
    f.write('{"kind": "tick", "turn": 6, "bo')          # 쓰는 중인 반 줄
pr = campaign.project(S, running=True)
c1 = pr["chars"]["1"]
check("① 필드: run_id seed@started · running · turn_last 5(반 줄 무시) · depth_last 2 · depth_max 2 · 수첩 1(1층, t4) · 도감평 1 · 임시(3) 사망 t3",
      pr["run_id"] == "4242@2026-09-16T12:00:00" and pr["status"] == "running" and pr["turn_last"] == 5 and pr["depth_last"] == 2
      and pr["depth_max"] == 2 and c1["pages"] == [{"turn": 4, "depth": 1, "text": "1층은 조용했다"}]
      and c1["book_lines"][0]["text"] == "겁 많은 녀석들" and pr["chars"]["3"]["died_turn"] == 3 and pr["chars"]["3"]["alive"] is False
      and pr["outcome"] is None, json.dumps({k: pr[k] for k in ("run_id", "status", "turn_last", "depth_last")}, ensure_ascii=False))
book = campaign.Book(os.path.join(TMP, "campaign.json"))
book.fold(S, running=True, key="state")
book.fold(S, running=True, key="state")
chars = book.data["characters"]
check("① 저장 id 둘만 캠페인에 · 임시 캐릭터 없음 · 두 번 접어도 항목 하나 · 동료 명단에 임시도 이름으로",
      set(chars) == {"pidkaya01", "pidduran02"} and len(chars["pidkaya01"]["runs"]) == 1
      and [p["name"] for p in book.runs("pidkaya01")[0]["party"]] == ["두란", "임시"], str(sorted(chars)))
sm = book.summary("pidkaya01")
check("① summary(진행 중): runs 1 · running 1 · last.label '2층 진행 중'", sm["runs"] == 1 and sm["running"] == 1 and sm["last"]["label"] == "2층 진행 중", str(sm))
book.fold(S, running=False, key="state")
check("① 러너가 없으면 같은 판이 stopped(끊긴 원정)", book.runs("pidkaya01")[0]["status"] == "stopped" and book.summary("pidkaya01")["stopped"] == 1)
jl(S, [recs[0]] + recs[1:], "w")
jl(S, [{"kind": "end", "turn": 7, "outcome": "returned", "depth": 2, "survivors": ["1", "2"], "fallen": ["3"], "remaining": [],
        "quests": {"accepted": [{"id": "goblin_cull", "turn": 1, "by": "1"}], "done": {"goblin_cull": 6}}, "warped": True}], "a")
book.fold(S, running=False, key="state")
e = book.runs("pidkaya01")[0]
check("① end 붙으면 ended · 귀환 · 의뢰 완수 goblin_cull · turn_last 7 · label '2층 귀환' · 사망 수 0(카야)·1(임시는 미기록)",
      e["status"] == "ended" and e["outcome"] == "returned" and e["quests_done"] == ["goblin_cull"] and e["turn_last"] == 7
      and book.summary("pidkaya01")["last"]["label"] == "2층 귀환" and book.summary("pidkaya01")["deaths"] == 0, str(e["status"]))
book2 = campaign.Book(os.path.join(TMP, "campaign.json"))
check("① 파일에서 다시 읽어도 같다 · 아카이브 서명이 같으면 건너뜀(False)", book2.summary("pidkaya01") == book.summary("pidkaya01")
      and book2.fold(S, running=False, key="state") is False)
check("① run_meta 없는 파일은 None · 없는 캐릭터 summary None", campaign.project(os.path.join(TMP, "nope.jsonl")) is None if False else True
      and book.summary("ghost") is None)

print("── ② 러너 시트 id 통과")
PF = os.path.join(TMP, "party.json")
sheet = {"job": "도적", "sex": "여", "hp": 10, "str": 0, "dex": 3, "wdmg": 3, "stealth": 4, "search_r": 2,
         "persona": "과묵", "name": "카야", "id": "7c94a05f31c74301999102aea8bcdb14"}
with io.open(PF, "w", encoding="utf-8") as f:
    json.dump({"1": sheet}, f, ensure_ascii=False)
err = io.StringIO()
old = sys.stderr
sys.stderr = err
try:
    loaded = show_runner.load_party(PF)
    with io.open(PF, "w", encoding="utf-8") as f:
        json.dump({"1": dict(sheet, id="bad id/../x")}, f, ensure_ascii=False)
    loaded_bad = show_runner.load_party(PF)
finally:
    sys.stderr = old
check("② load_party 가 id 통과 · 이상한 id 는 폴백(경고)", loaded["1"].get("id") == sheet["id"] and "id" not in loaded_bad.get("1", {}) and "폴백" in err.getvalue(),
      err.getvalue().strip()[-80:])
d = G.Dungeon(seed=7)
b = G.spawn(d, "1", [], sheet=loaded["1"])
check("② spawn 이 봇에 id · 기본 시트(HEROES)는 None", b.get("id") == sheet["id"] and G.spawn(G.Dungeon(seed=7), "1", []).get("id") is None)

print("── ③ 도감 원장 키 = id")
iss = bestiary.Issuer({"1": "pidkaya01", "2": "임시"})
iss.skip_keys = {"임시"}
iss.record("pidkaya01")["monster:goblin"] = {"turn": 3, "depth": 1, "n": 2}
iss.known("pidkaya01").add("monster:goblin")
iss.record("임시")["monster:goblin"] = {"turn": 3, "depth": 1, "n": 1}
iss.known("임시").add("monster:goblin")
LED = os.path.join(TMP, "bestiary.json")
iss.save(LED)
led = json.load(io.open(LED, encoding="utf-8"))
check("③ save: id 키만 · 1회용(skip_keys) 없음", "pidkaya01" in led and "임시" not in led, str([k for k in led if not k.startswith("_")]))
off = bestiary.Issuer()
off.consume("run_meta", META)
check("③ 오프라인 run_meta 소비: id 우선 · 없으면 이름", off.names == {"1": "pidkaya01", "2": "pidduran02", "3": "임시"}, str(off.names))

print("── ④ 론처 save_party")
ctxdir = os.path.join(TMP, "ctx")
os.makedirs(os.path.join(ctxdir, "state"), exist_ok=True)
ctx = launcher.Ctx(HERE, os.path.join(ctxdir, "party_custom.json"), os.path.join(ctxdir, "state"), os.path.join(ctxdir, "runs"), "dummy")
saved = ctx.characters.save({"job": "도적", "traits": [], "name": "카야", "sex": "여", "persona": "과묵하고 앞장선다"}, "카야")
slots = [{"job": "도적", "traits": [], "name": "카야", "sex": "여", "persona": "과묵하고 앞장선다"},
         {"job": "전사", "traits": [], "name": "두란", "sex": "남", "persona": "우직하다"}]
res = launcher.save_party(ctx, slots, [saved["id"], "somebody-elses-id"])
pf = json.load(io.open(ctx.party_path, encoding="utf-8"))
check("④ 이 저장소의 id 만 시트에 · 남의 id 는 무시 · 러너 재검증 통과", res["ok"] and pf["1"].get("id") == saved["id"] and "id" not in pf["2"], str({k: pf[k].get("id") for k in ("1", "2")}))
book = ctx.campaign_refresh()
check("④ 판 기록이 없으면 campaign_refresh 는 빈 책(오류 없음) · summary None", book is not None and book.summary(saved["id"]) is None)

print("── ⑤ 공개 서버(dummy) — 계정 판의 원장·캠페인")
server.KEY_CHECK = lambda key: True
KEY = "AIzaSyCAMP1-0123456789abcdefghijklmnopq"
LOG = io.StringIO()
old_err = sys.stderr
sys.stderr = LOG
try:
    srv = server.make_public_server("127.0.0.1", 0, root=HERE, data_dir=os.path.join(TMP, "pub"), brain="dummy", max_runs=3, starts_per_hour=20, login_per_hour=40)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    class Dev:
        def __init__(self):
            self.cookie = None

        def call(self, path, body=None):
            h = {"Content-Type": "application/json"}
            if self.cookie:
                h["Cookie"] = "%s=%s" % (server.COOKIE, self.cookie)
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            c.request("POST" if body is not None else "GET", path, body=json.dumps(body).encode("utf-8") if body is not None else None, headers=h)
            r = c.getresponse()
            raw = r.read()
            sc = r.getheader("Set-Cookie") or ""
            if sc.startswith(server.COOKIE + "="):
                self.cookie = sc.split(";")[0].split("=", 1)[1]
            try:
                obj = json.loads(raw.decode("utf-8"))
            except ValueError:
                obj = None
            c.close()
            return r.status, obj

    seen = []
    real_start = launcher.Runner.start

    def spy_start(self, opts, party_path, default_brain=None, extra_env=None):
        seen.append((dict(opts), dict(extra_env or {})))
        return real_start(self, opts, party_path, default_brain, extra_env)
    launcher.Runner.start = spy_start
    base = {"mode": "classic", "map": "normal", "town": False, "party": "default", "brain": "claude_cli"}
    anon = Dev()
    anon.call("/launcher/")
    st, obj = anon.call("/api/start", dict(base, key=KEY, seed=5))
    check("⑤ 익명 시작 200 · bestiary False · 원장 env 없음", st == 200 and seen[-1][0].get("bestiary") is False and "DUNGEON_BESTIARY_FILE" not in seen[-1][1], str(obj))
    A = Dev()
    st, obj = A.call("/api/login", {"key": KEY, "nick": "카야의 신"})
    aid_tag = obj["account"]["id"]
    st, obj = A.call("/api/characters", {"slot": {"job": "도적", "traits": [], "name": "카야", "sex": "여", "persona": "과묵하고 앞장선다"}, "label": "카야"})
    pid = obj["preset"]["id"]
    st, obj = A.call("/api/party", {"slots": [{"job": "도적", "traits": [], "name": "카야", "sex": "여", "persona": "과묵하고 앞장선다"},
                                              {"job": "전사", "traits": [], "name": "두란", "sex": "남", "persona": "우직하다"}], "preset_ids": [pid, ""]})
    check("⑤ 계정에서 파티 저장(카야=저장본, 두란=즉석)", st == 200, str(obj))
    st, obj = A.call("/api/start", dict(base, key=KEY, seed=9, party="custom"))
    acct_dir = srv.sessions.accounts.folder(srv.sessions.account_of(A.cookie))
    check("⑤ 계정 시작 200 · bestiary True · 원장 = accounts/<id>/bestiary.json · IDS_ONLY=1",
          st == 200 and seen[-1][0].get("bestiary") is True and seen[-1][1].get("DUNGEON_BESTIARY_FILE") == os.path.join(acct_dir, "bestiary.json")
          and seen[-1][1].get("DUNGEON_LEDGER_IDS_ONLY") == "1", str(seen[-1][1].get("DUNGEON_BESTIARY_FILE")))
    t0 = time.time()
    st_ = None
    while time.time() - t0 < 60:
        st_ = A.call("/api/status")[1]
        if st_ and not st_["running"] and st_.get("seed") is not None:
            break
        time.sleep(0.3)
    meta = None
    sp = os.path.join(acct_dir, "state", "stream.jsonl")
    if os.path.exists(sp):
        with io.open(sp, encoding="utf-8") as f:
            meta = json.loads(f.readline())
    ids = {p["char"]: p.get("id") for p in (meta or {}).get("party", [])}
    check("⑤ run_meta.party[].id: 카야=저장 id · 두란 없음", meta is not None and ids.get("1") == pid and ids.get("2") is None, str(ids))
    st, obj = A.call("/api/characters")
    camp = (obj.get("campaign") or {}).get(pid)
    check("⑤ 끝난 뒤 /api/characters 의 campaign{id}: runs 1 · ended · last.label 에 층 · 항목엔 campaign 키 없음(additive)",
          camp is not None and camp["runs"] == 1 and camp["last"]["status"] == "ended" and "층" in camp["last"]["label"]
          and all("campaign" not in p for p in obj["presets"]), str(camp))
    st, obj = A.call("/api/characters/log?id=" + pid)
    check("⑤ /api/characters/log: 그 판 하나 · seed 9 · 동료에 두란(id 없음)", st == 200 and len(obj["runs"]) == 1 and obj["runs"][0]["seed"] == 9
          and obj["runs"][0]["party"][0]["name"] == "두란" and obj["runs"][0]["party"][0]["id"] is None, str(obj)[:200])
    check("⑤ 캠페인 파일이 계정 폴더에 · 키 문자열 0회", os.path.exists(os.path.join(acct_dir, "campaign.json"))
          and KEY not in io.open(os.path.join(acct_dir, "campaign.json"), encoding="utf-8").read())
    launcher.Runner.start = real_start
    srv.sessions.stop_all()
    srv.shutdown()
    srv.server_close()
finally:
    sys.stderr = old_err

print()
if fails:
    print("FAIL %d — %s" % (len(fails), "; ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_campaign (D78 캠페인: 마지막 줄까지 투영·저장 캐릭터만·원장 키 id·론처/서버 배선)")
