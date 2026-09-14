# -*- coding: utf-8 -*-
"""D69 길드 척추 — 의뢰 맡기 → 던전(엔진 완료 판정) → 워프 귀환 → 마을에서 접수원 보고 = 원정의 끝 — 64번째 게이트. LLM 0콜.
(2026-09-14 파트너 "마을의 디테일을 살리는 길 … 마을에서의 상호작용이 많이 부족했거든" · "이 세상이 던전만 있는 건 아니라는 걸 보여주고
 싶고 … 던전과 마을을 이어주는 연결점이 바로 길드" · "그렇지" (원정의 끝을 게이트에서 길드 보고로) · "좋아 작업 부탁할게")
게이트:
  ① 정의: 의뢰 3편의 req(kill/reach/loot) · 검증기가 잘못된 req 를 잡는다 · NPC 정의의 role/report/보고 대사 · 건물 role
  ② 엔진(마을): quest_ids q1~q3 게시판 순 · 피처 역할(role) 관측 · 게시판 notice 에 tid · 조합형 대상 q1 · 메뉴 '의뢰 맡기' ·
     맡기: 멀면 too_far / 곁이면 quest_accepted(장부·목격) / 다시 quest_already · obs.quests 진행 줄 · 프롬프트 줄
  ③ 엔진(진행): reach(층 도달) · kill(_damage_monster 공용 지점 — 정의 id 대조·층 조건) · loot(보물 줍기·상자) — 결과 dict 의 quest
  ④ 엔진(보고): 귀환 전엔 접수원=선물/대화 · 귀환 뒤 접수원 = npc_report(완수/미완 갈림·장부 reported) · 보고 뒤엔 다시 평소 대사
  ⑤ 흩어진 출발: apart=True 면 셋이 서로 다른 건물 문턱 곁, 바닥 칸, 광장 자리와 다르다 · apart=False 는 옛 자리 그대로
  ⑥ NPC 두뇌(npc_reply): 스텁 _call_claude 로 JSON/문장/실패 세 갈래 · 프롬프트에 시트 없음·역할·사실·장면 있음 · 120자 상한
  ⑦ 러너 풀런(더미+각본, 마을 시작·2층·약한 보스): 맡기 3 → 2층 도달 완수 → 보스 처치 → 워프 → 마을 계속 → 접수원 보고 → end.returned ·
     end.quests(reported·done) · end.warped · level(2층).quests · events.log 줄 · run_summary 결산 일치 · run_meta 스위치 3
  ⑧ 배선(소스·문서): STREAM_FORMAT · HARNESS D69·D70 · README · 론처 체크박스·env · 클라이언트(evline·Bubbles·types) · 결산
  ⑨ D70 마을 사람 지각=구역(09-14 파트너 "구역 단위로 가자"): 다른 구역의 동료는 안 보이고(sights.bots·party.visible·goto b<char>) 말도 안 들리고
     목격도 없다 · 같은 구역·곁이면 전부 됨 · 관측 문장 · 장부 주소=구역 이름 · town_hear None 이면 옛 규칙
  ⑩ D71 NPC 가 먼저 말을 건다(09-14 파트너 "npc 가 먼저 말을 걸게 하면 어때?"): 상황별 인사 6종·한 번만·구역/범위/이미 말한 NPC 제외 ·
     러너 풀런에서 tick.npc_hails·inbox 'npc:'·귀환 뒤 hail_return · npc_reply 의 npc_hail 장면(두뇌 옵션)
(기존 verify 63종은 별도 실행.)
"""
import contextlib
import io
import json
import os
import tempfile

STATE = os.path.join(tempfile.mkdtemp(prefix="wl_guild_"), "state")
os.makedirs(STATE, exist_ok=True)
os.environ.update(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="420", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE="/nonexistent", DUNGEON_STATE_DIR=STATE, DUNGEON_BOSS="1",
                  DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy",
                  DUNGEON_ACTION_MODE="compose")   # 조합형 게이트 — _run_gates.sh 의 menu 기본을 파일 안에서 덮는다(use q<n>·targets 검사)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import run_summary                                   # noqa: E402
import show_runner                                   # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
show_runner.STEP_DELAY = 0

HERE = os.path.dirname(os.path.abspath(__file__))


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def src(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as f:
        return f.read()


def mkbot(char, x, y, job="전사"):
    return {"char": char, "x": x, "y": y, "hp": 14, "maxhp": 14, "str": 3, "dex": 0, "wdmg": 4, "stealth": 0,
            "search_r": 1, "job": job, "sex": "남", "persona": "", "bag": 0, "potions": 0, "weapon": None, "armor": None,
            "alive": True, "won": False, "order": None, "path": [], "aware_of": set(), "name": "두란" if char == "1" else "카야"}


def by_name(d, ftype, name):
    return next(f for f in d.features.values() if f.type == ftype and f.name == name)


print("── ① 정의(entities): 의뢰 req · NPC 역할·보고 · 건물 역할")
qd = {q: G.quest_def(q) for q in ("goblin_cull", "reach_floor_2", "lost_trinket")}
check("① 의뢰 3편의 req — kill(goblin, 1층, 3) / reach(2층) / loot(treasure, 1)",
      qd["goblin_cull"]["req"] == {"kind": "kill", "monster": "goblin", "depth": 1, "n": 3}
      and qd["reach_floor_2"]["req"] == {"kind": "reach", "depth": 2}
      and qd["lost_trinket"]["req"] == {"kind": "loot", "object": "treasure", "n": 1})
bad = [("q/x.json", {"id": "x", "kind": "quest", "name": "x", "comps": {"quest": {"goal": "g", "req": {"kind": "dance"}}}}),
       ("q/y.json", {"id": "y", "kind": "quest", "name": "y", "comps": {"quest": {"goal": "g", "req": {"kind": "kill", "monster": "dragon"}}}}),
       ("q/z.json", {"id": "z", "kind": "quest", "name": "z", "comps": {"quest": {"goal": "g", "req": {"kind": "reach"}}}})]
probs = ENT._problems([(os.path.join("q", os.path.basename(p)), d) for p, d in bad], "q")
check("① 검증기: 모르는 req.kind · 없는 monster · depth 없는 reach 를 전부 잡는다",
      any("req.kind" in p for p in probs) and any("monster 정의가 아니다" in p for p in probs) and any("depth" in p for p in probs))
npc_rec = ENT.npc("guild_receptionist")
check("① 접수원 정의: role·report·line_report 3종 · 주점 주인 role 에 '소문' · 성직자 role 에 '신'",
      npc_rec["report"] is True and npc_rec["role"] and npc_rec["line_report"] and npc_rec["line_report_failed"] and npc_rec["line_report_empty"]
      and "소문" in (ENT.npc("tavern_keeper")["role"] or "") and "신" in (ENT.npc("temple_attendant")["role"] or ""))
check("① 건물 정의 role — 길드·주점·신전 셋 다 한 줄, 던전 입구는 없음",
      all(ENT.get(b)["comps"]["building"].get("role") for b in ("guild_hall", "tavern", "temple"))
      and not ENT.get("dungeon_gate")["comps"]["building"].get("role"))

print("── ② 엔진(마을): 관측 id·역할·맡기")
Q = G.new_quests()
d2, s2 = show_runner.build_town(quests=Q)
check("② quest_ids = 게시판 순 q1~q3 · quest_boards = 길드 문턱(range 2)",
      d2.quest_ids == {"q1": "goblin_cull", "q2": "reach_floor_2", "q3": "lost_trinket"}
      and all(d2.quest_boards[q][0] == by_name(d2, "building", "모험가 길드").id and d2.quest_boards[q][1] == 2 for q in d2.quest_ids.values()))
gd = by_name(d2, "building", "모험가 길드")
rec = by_name(d2, "npc", "길드 접수원")
check("② feature_roles — 길드·주점·신전·접수원·주점 주인·성직자(6) · npc_defs 3", len(d2.feature_roles) == 6 and gd.id in d2.feature_roles
      and rec.id in d2.feature_roles and set(d2.npc_defs) == {"길드 접수원", "주점 주인", "성직자"})
far = mkbot("1", *s2["1"])
o_far = d2.view(far, [far])
fl = next(f for f in o_far["sights"]["features"] if f["id"] == "f%d" % gd.id)
check("② 관측 피처에 role — '모험가 길드' 항목에 role 문자열 · 프롬프트 줄 '모험가 길드 f<n> (…)' 역할", fl.get("role") == d2.feature_roles[gd.id]
      and ("모험가 길드 f%d (%s)" % (gd.id, fl["role"])) in brains._wire(o_far, {"1": "두란"}, compose=True))
check("② 멀리서: notices 없음 · 대상에 q 없음 · obs.quests 없음", not o_far.get("notices") and not any(t["id"].startswith("q") for t in o_far.get("targets", []))
      and not o_far.get("quests"))
near = mkbot("2", gd.x, gd.y + 1)                                # far(1번)와 다른 사람이어야 목격이 성립한다
o_near = d2.view(near, [near])
bd = next(n for n in o_near["notices"] if n["kind"] == "board")
check("② 길드 문턱 곁: 게시판 의뢰에 tid q1~q3 · accepted 없음 · 조합형 대상 q1~q3(tags object·quest) · 메뉴 '의뢰 맡기' 3줄",
      [q.get("tid") for q in bd["quests"]] == ["q1", "q2", "q3"] and not any(q.get("accepted") for q in bd["quests"])
      and {t["id"] for t in o_near["targets"] if t["kind"] == "quest"} == {"q1", "q2", "q3"}
      and all("quest" in t["tags"] for t in o_near["targets"] if t["kind"] == "quest")
      and sum(1 for o in o_near["options"] if o["type"] == "interact" and str(o.get("target", "")).startswith("q")) == 3)
w_near = brains._wire(o_near, {"1": "두란"}, compose=True)
check("② 프롬프트: '[q1] 고블린 소탕' · 'ID 를 use' 어휘", "[q1] 고블린 소탕" in w_near and "ID 를 use" in w_near)
gz = d2._town_zone(gd.x, gd.y + 1)                                  # 길드 지구 — 같은 구역이되 곁(1칸)은 아닌 자리에 목격자(3)를 세운다
wit_cell = next((x, y) for y in range(d2.h) for x in range(d2.w)
                if d2.grid[y][x] == G.FLOOR and d2._town_zone(x, y) == gz and 2 <= max(abs(x - gd.x), abs(y - gd.y - 1)) <= 4
                and d2.feature_at(x, y) is None)
wit = mkbot("3", *wit_cell, job="궁수")
r_far = d2._interact(far, "q1", [far, near, wit])
r_ok = d2._interact(near, "q1", [far, near, wit])
r_again = d2._interact(near, "q1", [far, near, wit])
check("② 맡기: 멀면 too_far · 곁이면 quest_accepted(quest·title·goal·board) · 장부 accepted(turn·by) · 다시 quest_already",
      r_far["result"] == "too_far" and r_ok["result"] == "quest_accepted" and r_ok["quest"] == "goblin_cull" and r_ok["title"] == "고블린 소탕"
      and r_ok.get("goal") and r_ok.get("board") == "f%d" % gd.id and Q["accepted"]["goblin_cull"]["by"] == "2"
      and r_again["result"] == "quest_already" and r_again.get("by") == "2")
check("② 목격: 같은 구역(길드 지구)의 동료 3 은 ally_quest 를 봤고, 다른 구역의 동료 1 은 못 봤다(D70) · 프롬프트 문장",
      any(w.get("kind") == "ally_quest" and w.get("what") == "고블린 소탕" for w in wit.get("witnessed", []))
      and not any(w.get("kind") == "ally_quest" for w in far.get("witnessed", []))
      and "의뢰 「고블린 소탕」를 맡는 것을" in brains._witness_prose({"kind": "ally_quest", "char": "1", "name": "두란", "what": "고블린 소탕"}))
o_acc = d2.view(near, [near])
bd2 = next(n for n in o_acc["notices"] if n["kind"] == "board")
check("② 맡은 뒤 관측: notice accepted · obs.quests[0]={id,n 0,need 3,done False} · 프롬프트 '맡은 의뢰: 고블린 소탕(0/3)' · 메뉴에서 빠짐",
      bd2["quests"][0].get("accepted") is True and o_acc["quests"][0]["id"] == "goblin_cull" and o_acc["quests"][0]["n"] == 0
      and o_acc["quests"][0]["need"] == 3 and o_acc["quests"][0]["done"] is False
      and "맡은 의뢰: 고블린 소탕(0/3)" in brains._wire(o_acc, {"2": "카야"}, compose=True)
      and sum(1 for o in o_acc["options"] if str(o.get("target", "")).startswith("q")) == 2)
b2c = mkbot("3", gd.x - 1, gd.y + 1)
d2.view(b2c, [near, b2c])                                          # 조합형 참조(_target_refs)는 관측이 만든다
r2c = d2.act(b2c, {"type": "use", "target": "q2"}, [near, b2c])
check("② 조합형 use q2 = 맡기(effect_type interact) · goto q3 = 게시판 칸으로",
      r2c.get("result") == "quest_accepted" and r2c.get("effect_type") == "interact" and r2c.get("type") == "use"
      and d2._resolve_target("q3") == ("feature", (gd.x, gd.y)))
check("② 옛 판 비트: quests 없는 마을 — tid·대상·메뉴 없음(정보만)",
      (lambda dd: (lambda oo: not any(q.get("tid") for n in oo["notices"] for q in n.get("quests", []))
                   and not any(t["kind"] == "quest" for t in oo["targets"])
                   and not any(str(o.get("target", "")).startswith("q") for o in oo["options"]))
       (dd.view(mkbot("1", gd.x, gd.y + 1), [])))(show_runner.build_town()[0]))

print("── ③ 엔진(진행): reach · kill · loot")
Q3 = G.new_quests()
for q in ("goblin_cull", "reach_floor_2", "lost_trinket"):
    Q3["accepted"][q] = {"turn": 1, "by": "1"}
rows = ["##########",
        "#1..g.g..#",
        "#..g...$.#",
        "#.......>#",
        "##########"]
d3, s3 = G.Dungeon.from_ascii(rows, seed=7, depth=1, monsters={"g": {"kind": "고블린", "hp": 1, "state": "SLEEPING"}})
d3.quests = Q3
b3 = mkbot("1", *s3["1"])
check("③ reach: 1층에선 안 찬다 · 2층 도달 = 완수(n=need=1)", d3._quest_event("reach", depth=1) == [] and Q3["progress"].get("reach_floor_2") is None
      and (lambda ev: ev and ev[0]["id"] == "reach_floor_2" and ev[0]["done"] is True)(G.Dungeon.from_ascii(rows, seed=7, depth=2, monsters={"g": {"kind": "고블린"}})[0].__class__._quest_event(
          (lambda dd: (setattr(dd, "quests", Q3), dd)[1])(G.Dungeon.from_ascii(rows, seed=7, depth=2, monsters={"g": {"kind": "고블린"}})[0]), "reach", depth=2))
      and "reach_floor_2" in Q3["done"])
kills = []
for m in list(d3.monsters):
    kills.append(d3._damage_monster(b3, m, 99, [b3]))
check("③ kill: _damage_monster 공용 지점 — 처치마다 quest [{n 1..3, need 3}] · 셋째에 done · 장부 done",
      [k.get("quest", [{}])[0].get("n") for k in kills] == [1, 2, 3] and kills[2]["quest"][0]["done"] is True
      and kills[0]["quest"][0]["done"] is False and "goblin_cull" in Q3["done"] and all(k["quest"][0]["need"] == 3 for k in kills))
Q3b = G.new_quests(); Q3b["accepted"]["goblin_cull"] = {"turn": 1, "by": "1"}
d3b, s3b = G.Dungeon.from_ascii(rows, seed=7, depth=2, monsters={"g": {"kind": "고블린", "hp": 1}})
d3b.quests = Q3b
r3b = d3b._damage_monster(mkbot("1", *s3b["1"]), d3b.monsters[0], 99, [])
check("③ kill 층 조건: 2층의 고블린은 1층 의뢰에 안 센다(quest 없음) · 모르는 종도 안 센다",
      "quest" not in r3b and d3._quest_event("kill", monster="용") == [])
tr = next(f for f in d3.features.values() if f.type == "treasure")
b3.update(x=tr.x - 1, y=tr.y)
r_loot = d3._interact(b3, "f%d" % tr.id, [b3])
check("③ loot: 보물 줍기 = lost_trinket 완수(quest 동봉) · 직전 결과 문장에 의뢰 접미 · 궤적 꼬리표 '의뢰'",
      r_loot["result"] == "treasure" and r_loot["quest"][0]["id"] == "lost_trinket" and r_loot["quest"][0]["done"] is True
      and "의뢰 「잃어버린 장신구」 완수" in brains._last_prose({**r_loot}, {"1": "두란"})
      and "의뢰 「고블린 소탕」 완수" in brains._last_prose({**kills[2], "type": "attack", "result": "attack", "hit": True, "target": "고블린"}, {"1": "두란"})
      and any(t[0] == "quest" for t in G.event_tags({**kills[2], "type": "attack", "result": "attack", "hit": True, "target": "고블린"})))

print("── ④ 엔진(보고): 귀환 전/후 접수원")
Q4 = G.new_quests()
d4, s4 = show_runner.build_town(quests=Q4)
rec4 = by_name(d4, "npc", "길드 접수원")
b4 = mkbot("1", rec4.x, rec4.y + 1)
r_before = d4._interact(b4, "f%d" % rec4.id, [b4])
check("④ 귀환 전: 접수원은 선물/대화(npc_gift) — 보고 아님", r_before["result"] == "npc_gift")
Q4["accepted"].update(goblin_cull={"turn": 3, "by": "1"}, reach_floor_2={"turn": 3, "by": "2"})
Q4["done"]["reach_floor_2"] = 40
Q4["returned"] = 80
d4.expedition_returned = True
o4 = d4.view(b4, [b4])
check("④ 귀환 뒤 관측: expedition_returned · 프롬프트 '보고해야 끝난다'", o4.get("expedition_returned") is True
      and "접수원에게 보고해야 끝난다" in brains._wire(o4, {"1": "두란"}, compose=True))
r_rep = d4._interact(b4, "f%d" % rec4.id, [b4])
check("④ 보고: npc_report — done [reach_floor_2] · undone [goblin_cull] · titles · line 에 완수 제목 · 장부 reported=turn",
      r_rep["result"] == "npc_report" and r_rep["done"] == ["reach_floor_2"] and r_rep["undone"] == ["goblin_cull"]
      and r_rep["titles"]["reach_floor_2"] == "2층 답사" and "2층 답사" in r_rep["line"] and Q4["reported"] == d4.turn)
r_after = d4._interact(b4, "f%d" % rec4.id, [b4])
check("④ 보고 뒤: 다시 평소(선물 없이 대화 — 이미 만났다) · 직전 결과 문장·러너 요약 줄",
      r_after["result"] == "npc_talk" and r_after.get("again") is True
      and "원정을 보고했다 (완수: 2층 답사 / 미완: 고블린 소탕)" in brains._last_prose(r_rep, {"1": "두란"})
      and "원정 보고 — 완수 2층 답사 / 미완 고블린 소탕" in show_runner.act_summary(r_rep))
Q4e = G.new_quests(); Q4e["returned"] = 5
d4e, _ = show_runner.build_town(quests=Q4e); d4e.expedition_returned = True
r_e = d4e._interact(b4, "f%d" % by_name(d4e, "npc", "길드 접수원").id, [b4])
check("④ 맡은 의뢰 없이 돌아와도 보고는 된다(빈 보고 대사)", r_e["result"] == "npc_report" and r_e["done"] == [] and r_e["undone"] == []
      and r_e["line"] == ENT.npc("guild_receptionist")["line_report_empty"])

print("── ⑤ 흩어진 출발")
d5a, s5a = show_runner.build_town(apart=False)
d5b, s5b = show_runner.build_town(apart=True)
ents = {f.name: (f.x, f.y) for f in d5b.features.values() if f.type == "building"}
def near_building(p):
    return any(max(abs(p[0] - x), abs(p[1] - y)) <= 2 for x, y in ents.values())
check("⑤ apart=True: 셋이 서로 다른 칸 · 전부 바닥 · 각자 건물 문턱 2칸 안 · 광장 자리와 다르다 · apart=False 는 옛 자리",
      len({tuple(v) for v in s5b.values()}) == 3 and all(d5b.grid[y][x] == G.FLOOR for x, y in s5b.values())
      and all(near_building(p) for p in s5b.values()) and all(tuple(s5b[c]) != tuple(s5a[c]) for c in s5a)
      and s5a == show_runner.build_town()[1])
check("⑤ 결정론: 두 번 지어도 같은 자리", s5b == show_runner.build_town(apart=True)[1])

print("── ⑥ NPC 두뇌(npc_reply)")
seen = {}
def stub_json(prompt, model="haiku"):
    seen["prompt"] = prompt
    return json.dumps({"line": "어서 와요, 두란 씨. 물약은 챙기셨죠?"}), None
brains._call_claude = stub_json
b6 = mkbot("1", 0, 0)
res6 = {"result": "npc_gift", "npc": "길드 접수원", "item": "물약·단검", "line": "모험가 길드예요."}
line6 = brains.npc_reply(b6, res6, "안녕하세요, 물품 좀 주세요", ["게시판 의뢰: 고블린 소탕 — 게시 중"], npc=ENT.npc("guild_receptionist"))
check("⑥ JSON 응답 → line · 프롬프트에 이름·역할·성격·사실·장면(말·판정) 있고 캐릭터 시트('# 시트') 없음",
      line6 == "어서 와요, 두란 씨. 물약은 챙기셨죠?" and "너는 길드 접수원이다" in seen["prompt"] and "원정 물품" in seen["prompt"]
      and "게시판 의뢰: 고블린 소탕" in seen["prompt"] and "물품 좀 주세요" in seen["prompt"] and "물약·단검을(를) 건넸다" in seen["prompt"]
      and "# 시트" not in seen["prompt"] and "성격:" in seen["prompt"])
brains._call_claude = lambda p, m="haiku": ("그냥 문장으로 답했다. " + "가" * 200, None)
check("⑥ JSON 없이 문장만 와도 받는다 · 120자 상한", (lambda ln: ln and ln.startswith("그냥 문장으로") and len(ln) <= brains.NPC_LINE_LEN)(
      brains.npc_reply(b6, res6, None, [], npc={})))
brains._call_claude = lambda p, m="haiku": ("", "호출 실패 NoAPIKey")
check("⑥ 실패 → None(고정 대사가 남는다) · 예외도 None", brains.npc_reply(b6, res6, None, [], npc={}) is None
      and (lambda: (setattr(brains, "_call_claude", lambda p, m="haiku": (_ for _ in ()).throw(RuntimeError("x"))), brains.npc_reply(b6, res6, None, [], npc={}))[1])() is None)
brains._call_claude = lambda prompt, model="haiku": ""   # 되돌림(더미 폴백)
facts6 = show_runner.npc_facts(d4, "주점 주인", [b4], [], Q4)
d4.rumor = show_runner.floor_rumor(G.Dungeon.from_ascii(rows, seed=7, depth=1, monsters={"g": {"kind": "고블린"}})[0])   # 손 안 댄 장면
facts6b = show_runner.npc_facts(d4, "주점 주인", [b4], ["2"], Q4)
check("⑥ npc_facts: 파티 줄·귀환 여부 · 주점 주인은 소문(실측 수)·자기 의뢰 · 접수원은 게시판 상태 · 성직자는 신의 요청 없음 줄",
      any(s.startswith("파티:") for s in facts6) and any("돌아온 뒤" in s for s in facts6)
      and any("소문" in s and "고블린 3마리" in s and "보물 1" in s for s in facts6b) and any("쓰러진 사람" in s for s in facts6b)
      and any("게시판 의뢰:" in s and "2층 답사" in s and "완수" in s for s in show_runner.npc_facts(d4, "길드 접수원", [b4], [], Q4))
      and any("신의 요청은 없다" in s for s in show_runner.npc_facts(d4, "성직자", [b4], [], Q4)))

print("── ⑦ 러너 풀런(더미+각본, 마을 시작·2층·약한 보스·워프·보고)")
_real_dummy = G.dummy_brain
orig_stats = G.ENT.monster_stats
def weak(kind):
    s = dict(orig_stats(kind))
    if kind == G.BOSS_KIND:
        s.update(hp=1, atk=0, dmg=0, ac=5)
    return s
G.ENT.monster_stats = weak
SEQ = {"guild_seen": False, "talked": False}
def scripted(obs, char="?"):
    if obs.get("town"):
        s = obs["sights"]
        rec_ = next((f for f in s["features"] if f["type"] == "npc" and f["name"] == "길드 접수원"), None)
        if obs.get("expedition_returned"):
            if rec_:
                return {"type": "interact" if rec_["adj"] else "goto", "target": rec_["id"]}
        else:
            board = next((n for n in (obs.get("notices") or []) if n["kind"] == "board"), None)
            if board:
                SEQ["guild_seen"] = True
                q = next((q for q in board["quests"] if q.get("tid") and not q.get("accepted")), None)
                if q:
                    return {"type": "interact", "target": q["tid"]}
            elif not SEQ["guild_seen"] and char == "1":
                guild = next((f for f in s["features"] if f["type"] == "building" and f["name"] == "모험가 길드"), None)
                if guild:
                    return {"type": "goto", "target": guild["id"]}
            if SEQ["guild_seen"] and not SEQ["talked"] and char == "1" and rec_:   # 떠나기 전 접수원에게 말 걸기(선물 틱 → NPC 대사가 잡담으로 들린다)
                if rec_["adj"]:
                    SEQ["talked"] = True
                return {"type": "interact" if rec_["adj"] else "goto", "target": rec_["id"]}
    return _real_dummy(obs, char)
G.dummy_brain = scripted
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    try:
        show_runner.main()
    except SystemExit:
        pass
G.dummy_brain = _real_dummy
G.ENT.monster_stats = orig_stats
with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
    rows7 = [json.loads(ln) for ln in f if ln.strip()]
meta, end = rows7[0], rows7[-1]
levels = [r for r in rows7 if r.get("kind") == "level"]
ticks = [r for r in rows7 if r.get("kind") == "tick"]
ev = [(r["turn"], e) for r in ticks for e in (r.get("events") or [])]
acc = [(t, e) for t, e in ev if e.get("result") == "quest_accepted"]
rep = [(t, e) for t, e in ev if e.get("result") == "npc_report"]
asc = [r for r in rows7 if r.get("kind") == "ascend"]
check("⑦ run_meta: quests·town_apart True · npc_brain False(더미) · town_hear zone(D70) · 첫 마을 level 에 두 봇이 서로 다른 건물 곁",
      meta.get("quests") is True and meta.get("town_apart") is True and meta.get("npc_brain") is False and meta.get("town_hear") == "zone"
      and len({(b["x"], b["y"]) for b in levels[0]["party"]}) == 2)
check("⑦ 맡기 사건 3(q1·q2·q3, 마을 층) → 각본이 길드 앞에서 맡았다", len(acc) == 3 and sorted(e.get("quest") for _, e in acc) == ["goblin_cull", "lost_trinket", "reach_floor_2"]
      and all(e.get("type") in ("interact", "use") for _, e in acc))
lv2 = next((l for l in levels if l.get("depth") == 2), None)
check("⑦ 2층 level.quests — reach_floor_2 완수", lv2 is not None and lv2.get("quests") and lv2["quests"][0]["id"] == "reach_floor_2" and lv2["quests"][0]["done"] is True)
check("⑦ 워프(ascend gate) → 마을 level(depth 0) 이 '뒤에' 하나 더 → 이어서 tick → npc_report 1회(접수원)",
      len(asc) == 1 and asc[0].get("gate") is True and [l["depth"] for l in levels] == [0, 1, 2, 0]
      and len(rep) == 1 and rep[0][1].get("npc") == "길드 접수원" and rep[0][0] > asc[0]["turn"])
check("⑦ 보고: done 에 reach_floor_2 · undone 에 goblin_cull(몹 0) · end.outcome returned · end.turn == 보고 틱 · end.warped · end.quests.reported",
      "reach_floor_2" in rep[0][1].get("done", []) and "goblin_cull" in rep[0][1].get("undone", [])
      and end.get("outcome") == "returned" and end.get("turn") == rep[0][0] and end.get("warped") is True
      and (end.get("quests") or {}).get("reported") == rep[0][0] and set((end["quests"].get("done") or {})) >= {"reach_floor_2"}
      and sorted(a["id"] for a in end["quests"]["accepted"]) == ["goblin_cull", "lost_trinket", "reach_floor_2"])
with open(os.path.join(STATE, "events.log"), encoding="utf-8") as f:
    log = f.read()
check("⑦ events.log — 맡음 줄·귀환 줄·보고 줄·종료 줄", "의뢰 맡음: 고블린 소탕" in log and "길드 접수원에게 보고하면 원정이 끝난다" in log
      and "길드에 보고했다" in log and "길드에 보고 (원정 완료)" in log)
col, end_off = run_summary.replay(os.path.join(STATE, "stream.jsonl"))
s_off = col.result()
check("⑦ 결산: quests{accepted 3, done ≥1, reported 1} · npc.talks ≥1, brain_lines 0 · 라이브 end.summary 와 같다",
      s_off["quests"]["accepted"] == 3 and s_off["quests"]["done"] >= 1 and s_off["quests"]["reported"] == 1
      and s_off["npc"]["talks"] >= 1 and s_off["npc"]["brain_lines"] == 0
      and all(k in s_off and s_off[k] == v for k, v in (end.get("summary") or {}).items()))
check("⑦ 인박스: 보고 틱 다음 인박스 없음(판 종료) · 마을에서 접수원 대사가 'npc:길드 접수원' 잡담으로 들렸다(선물 틱)",
      any(m.get("from") == "npc:길드 접수원" for r in ticks for ms in (r.get("inbox") or {}).values() for m in ms))

print("── ⑨ 마을 사람 지각=구역(D70, 09-14 파트너 '구역 단위로 가자')")
d9, s9 = show_runner.build_town(apart=True)
check("⑨ layout 마을은 town_hear='zone' · 옛 규칙 스위치(all)면 None",
      d9.town_hear == "zone" and (lambda: (setattr(show_runner, "TOWN_HEAR", "all"), show_runner.build_town()[0].town_hear, setattr(show_runner, "TOWN_HEAR", "zone"))[1])() is None)
a9, b9 = mkbot("1", *s9["1"]), mkbot("2", *s9["2"], job="도적")
za, zb = d9._town_zone(a9["x"], a9["y"]), d9._town_zone(b9["x"], b9["y"])
o9a = d9.view(a9, [a9, b9])
check("⑨ 흩어진 출발 = 서로 다른 구역 · 지형은 전부 보이지만(visible_cells 전체) 동료는 sights.bots 에 없고 party.visible False · goto b2 해석 None",
      za and zb and za != zb and len(d9.visible_cells(a9["x"], a9["y"])) > 500 and not o9a["sights"]["bots"]
      and o9a["party"][0]["visible"] is False and d9._resolve_target("b2", [a9, b9], a9) is None)
w9 = brains._wire(o9a, {"1": "두란", "2": "카야"}, compose=True)
check("⑨ 관측 문장: '같은 구역 안에서만 보이고 들린다' + '지금 있는 곳' · 옛 문장('한눈에') 없음",
      "같은 구역 안에서만 보이고 들린다" in w9 and "지금 있는 곳:" in w9 and "한눈에" not in w9)
inbox9, _ = show_runner.deliver_and_hail(d9, [a9, b9], {"1": "카야, 어디 있어?"}, {"1": "2"}, {"1": "잡담"}, {})
check("⑨ 다른 구역의 말은 배달되지 않는다 · 목격도 안 된다", inbox9["2"] == [] and not d9.hears(b9, a9["x"], a9["y"]))
b9["x"], b9["y"] = a9["x"] + 1, a9["y"]                        # 곁으로
o9a2 = d9.view(a9, [a9, b9])
inbox9b, _ = show_runner.deliver_and_hail(d9, [a9, b9], {"1": "여기 있었네"}, {"1": "2"}, {"1": "잡담"}, {})
check("⑨ 같은 구역(곁)이면 보이고 들린다 · goto b2 해석됨", [x["char"] for x in o9a2["sights"]["bots"]] == ["2"]
      and inbox9b["2"] and inbox9b["2"][0]["text"] == "여기 있었네" and d9._resolve_target("b2", [a9, b9], a9) is not None)
gd9 = by_name(d9, "building", "모험가 길드")
a9["x"], a9["y"] = gd9.x, gd9.y + 1
b9["x"], b9["y"] = s9["2"]
d9.quests = G.new_quests(); d9.index_quests()
d9._interact(a9, "q1", [a9, b9])
check("⑨ 게시판 앞에서 맡는 걸 다른 구역의 동료는 못 본다(witnessed 없음) · 장부 주소는 구역 이름",
      not b9.get("witnessed") and d9._zone_label(a9["x"], a9["y"]) == za)
d9.town_hear = None
o9c = d9.view(a9, [a9, b9])
check("⑨ 옛 규칙(town_hear None): 다른 구역도 보인다 · 옛 문장", [x["char"] for x in o9c["sights"]["bots"]] == ["2"]
      and "한눈에" in brains._wire(o9c, {"1": "두란", "2": "카야"}, compose=True))

print("── ⑩ NPC 가 먼저 말을 건다(D71, 09-14 파트너 'npc 가 먼저 말을 걸게 하면 어때?')")
Q10 = G.new_quests()
d10, s10 = show_runner.build_town(quests=Q10)
rec10 = by_name(d10, "npc", "길드 접수원")
tav10 = by_name(d10, "npc", "주점 주인")
tem10 = by_name(d10, "npc", "성직자")
d10.rumor = {"depth": 1, "monsters": {"고블린": 2, "그림자거미": 1}, "traps": 3, "features": {"treasure": 4}}
a10 = mkbot("1", rec10.x + 2, rec10.y + 2)                       # 접수원 근처(같은 구역, 곁 아님), 물약 0
g1 = d10.npc_greetings([a10])
check("⑩ 물약 0 이면 hail_no_potion — 이름 채움 · 한 번만(두 번째 호출 빈 목록)",
      len(g1) == 1 and g1[0][0] == "길드 접수원" and g1[0][1] == "1" and g1[0][5] == "hail_no_potion" and "두란 님" in g1[0][2] and "물약" in g1[0][2]
      and d10.npc_greetings([a10]) == [])
b10 = mkbot("2", rec10.x + 2, rec10.y + 2, job="도적"); b10["potions"] = 1
g2 = d10.npc_greetings([b10])
check("⑩ 물약 있고 안 맡은 의뢰 3 → hail_board(수 채움)", len(g2) == 1 and g2[0][5] == "hail_board" and "3개" in g2[0][2])
for qid in d10.quest_ids.values():
    Q10["accepted"][qid] = {"turn": 1, "by": "1"}
c10 = mkbot("3", rec10.x + 2, rec10.y + 2, job="궁수"); c10["potions"] = 1
check("⑩ 전부 맡았고 물약 있으면 기본 hail", (lambda g: len(g) == 1 and g[0][5] == "hail")(d10.npc_greetings([c10])))
Q10["returned"] = 50; d10.expedition_returned = True
r10 = mkbot("4", rec10.x + 3, rec10.y + 1); r10["potions"] = 0
check("⑩ 돌아온 파티(보고 전)면 물약보다 hail_return 이 먼저", (lambda g: len(g) == 1 and g[0][5] == "hail_return" and "보고" in g[0][2])(d10.npc_greetings([r10])))
t10 = mkbot("5", tav10.x + 1, tav10.y + 2); e10 = mkbot("6", tem10.x + 2, tem10.y + 1)
d10.oracle = {"id": "x", "text": "조심해라", "turn": 1}
g3 = {g[0]: g for g in d10.npc_greetings([t10, e10])}
check("⑩ 주점 주인 hail_rumor(고블린 2마리·함정 3) · 성직자 hail_oracle(신의 요청)",
      g3.get("주점 주인", [None] * 6)[5] == "hail_rumor" and "고블린 2마리" in g3["주점 주인"][2] and "함정도 3개" in g3["주점 주인"][2]
      and g3.get("성직자", [None] * 6)[5] == "hail_oracle")
far10 = mkbot("7", *s10["1"])                                    # 광장(번화가) — 접수원과 다른 구역
d10.oracle = None
n10 = mkbot("8", tem10.x + 2, tem10.y + 1); n10["npc_met"] = {"성직자"}
check("⑩ 다른 구역·범위 밖은 인사 없음 · 이미 말한 NPC 는 없음 · 신의 요청 없으면 성직자 기본 hail",
      d10.npc_greetings([far10]) == [] and d10.npc_greetings([n10]) == []
      and (lambda g: len(g) == 1 and g[0][5] == "hail")(d10.npc_greetings([mkbot("9", tem10.x + 2, tem10.y + 1)])))
hails7 = [(r["turn"], h) for r in ticks for h in (r.get("npc_hails") or [])]
first = next(((t, h) for t, h in hails7 if h["npc"] == "길드 접수원" and h["char"] == "1"), None)
check("⑦+⑩ 러너: 길드 곁에서 출발한 봇1 에게 접수원 인사가 tick.npc_hails 와 그 틱 inbox('npc:길드 접수원')로 · run_meta.npc_hail · 귀환 뒤 hail_return",
      meta.get("npc_hail") is True and first is not None and first[0] <= 3
      and any(m.get("from") == "npc:길드 접수원" for m in (next(r for r in ticks if r["turn"] == first[0]).get("inbox") or {}).get("1", []))
      and any(h.get("key") == "hail_return" and t > asc[0]["turn"] for t, h in hails7))
seen10 = {}
brains._call_claude = lambda p, m="haiku": (seen10.__setitem__("p", p), ('{"line": "어서 오세요!"}', None))[1]
line10 = brains.npc_reply(a10, {"result": "npc_hail", "npc": "길드 접수원", "line": "정해진 인사", "key": "hail_no_potion"}, None, [], npc=ENT.npc("guild_receptionist"))
brains._call_claude = lambda prompt, model="haiku": ""
check("⑩ 두뇌 옵션: npc_reply 의 npc_hail 장면('먼저 한마디') · 정해진 인사 동봉", line10 == "어서 오세요!" and "네가 먼저 한마디" in seen10["p"] and "정해진 인사" in seen10["p"])

print("── ⑧ 배선(소스·문서)")
check("⑧ STREAM_FORMAT: run_meta quests/town_apart/town_hear/npc_brain/npc_hail · tick.npc_hails · end.quests/warped · 이벤트 quest_accepted/npc_report · level.quests",
      all(s_ in src("STREAM_FORMAT.md") for s_ in ("| `quests` |", "| `town_apart` |", "| `town_hear` |", "| `npc_brain` |", "| `npc_hail` |", "| `npc_hails` |",
                                                    "`warped`", "quest_accepted", "npc_report", "line_src")))
check("⑧ HARNESS D69·D70·D71 · CHANGELOG · README(길드 보고·구역·먼저 말) · docs/entities.md(req·hail) · 클라이언트 npc_hails",
      all(k in src(os.path.join("design", "HARNESS_DESIGN.md")) for k in ("D69", "D70", "D71"))
      and "D70" in src(os.path.join("docs", "CHANGELOG.md")) and "D71" in src(os.path.join("docs", "CHANGELOG.md"))
      and "접수원" in src("README.md") and "같은 구역" in src("README.md") and "먼저 말" in src("README.md")
      and "req" in src(os.path.join("docs", "entities.md")) and "hail_rumor" in src(os.path.join("docs", "entities.md"))
      and "npc_hails" in src(os.path.join("game", "src", "stream", "parse.ts")) and "npc_hails" in src(os.path.join("game", "src", "scene", "Bubbles.ts"))
      and "npc_hails" in src(os.path.join("game", "src", "text", "evline.ts")))
check("⑧ 러너 스위치 3 · 론처 체크박스 2 + env 2",
      all(s_ in src("show_runner.py") for s_ in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "npc_reply(", "npc_report"))
      and all(s_ in src(os.path.join("launcher", "index.html")) for s_ in ('id="townApart" checked', 'id="npcBrain" checked', "town_apart:", "npc_brain:"))
      and all(s_ in src("launcher.py") for s_ in ("DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN")))
check("⑧ 클라이언트: evline(quest_accepted·npc_report·questSfx·returned) · Bubbles(npc) · types(quests·warped) · 씬 npcHeadOf",
      all(s_ in src(os.path.join("game", "src", "text", "evline.ts")) for s_ in ("quest_accepted", "npc_report", "questSfx", "returned:"))
      and "showNpcBubble" in src(os.path.join("game", "src", "scene", "Bubbles.ts")) and "npcHeadOf" in src(os.path.join("game", "src", "scene", "DungeonScene.ts"))
      and "warped?" in src(os.path.join("game", "src", "stream", "types.ts")))
check("⑧ 프롬프트 파일 prompts/npc_prompt.md 존재 · 자리 6개", all(k in src(os.path.join("prompts", "npc_prompt.md")) for k in ("{name}", "{role}", "{persona}", "{facts}", "{scene}", "{maxlen}")))

print("ALL PASS — verify_guild (D69 길드 척추: 의뢰 맡기·완료 판정·워프 귀환 뒤 보고=원정의 끝 · 흩어진 출발 · NPC 두뇌)" if C.failed == 0 else "FAIL %d" % C.failed)
raise SystemExit(1 if C.failed else 0)
