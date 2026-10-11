# -*- coding: utf-8 -*-
"""정보 보호 공통 인프라(p0.5.4 = master_plan 0.5단계, §6) 헤들리스 검증 — LLM 0콜(모델 응답은 전부 가짜).
게이트(§6.4 ①~⑥ + 이 단계의 부품 ⑦⑧):
  ① 비간섭: 행위자가 못 보는 비공개 사건 + 숨은 굴림(rng 소비)만 앞에 넣은 두 세계 — rng 를 같은 상태로 주입한 뒤 같은 후속 공개 대화의
     사건 번호·본문·COMMON 목록·**프롬프트 전체 바이트**가 같다. 원장 번호는 실제로 갈렸다(시험이 헛돌지 않는다) · 반응도 제 사건으로 간다
  ② 행동자 프롬프트(실제 claude_brain 이 만드는 글 — verify_people 방식)에 audit·상대 굴림·비공개 사건 id 가 없다 ·
     비공개 사건을 만든 행동자의 last·궤적에 흔적이 없다 · 사람 대상 공격(CA.attack_actor)의 굴림·AC 가 last·궤적에서 빠진다(원본 결과엔 남는다)
  ③ nested audit: audit 값을 다른 칸에 옮겨 적은 것(별칭·dict 사본·중첩 audit·값 복사)이 투영 뒤 사라진다 · 원본 불변 · 다른 칸 보존 ·
     사람 대상만 굴림을 걷는다(몹 대상은 그대로)
  ④ alias 위조: 받지 않은 사람이 남의 번호·원장 번호로 반응 → 거절 · 같은 번호라도 사람마다 다른 사건 · 받은 사람에게만 통한다
  ⑤ 피클 왕복(번호표 그대로) · 옛 원장(번호표 없음) 이관 1→2: 대기 사건은 받은 순서로 번호 · v0.5.2 고정 자료와 0.5.3 꼴 스냅샷을
     새 로더가 읽고(내용 판 2) 러너가 이어간다
  ⑥ 미등록 결과·미등록 관측 키: 러너 판(마을→던전, 말·친목·건네기·반응·스킬·전투)의 모든 판단에서 0 · 프롬프트의 사건 번호 = 그 사람의 번호뿐 ·
     모르는 결과의 폴백은 {type,target,status}만 · 미등록 관측 키는 그리지 않는다 · 모르는 사건 type 은 '물약 사용'이 아니라 중립 문장
  ⑦ 판정 함수 묶음(judge): 공개 칸 하나 + audit(전부 표식) · 문턱 13+은신(steal 13 고정) · 동점 방어자 · 단계 폭 5 · rng 소비 수 고정 ·
     엔진은 아직 부르지 않는다(0.5 는 판정 rng 소비가 늘지 않는다 — §10.1)
  ⑧ 불투명 ID: 같은 재료 → 같은 ID · 숫자뿐인 꼬리 없음(옛 f12 와 안 섞임) · 겹치면 늘린다
"""
import contextlib
import copy
import io
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_infoguard_")
FIX = os.path.join(HERE, "fixtures", "snapshot_v052")
os.environ.update(DUNGEON_ACTION_MODE="compose", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_GM="0", DUNGEON_STEP_DELAY="0",
                  DUNGEON_TURNS="220", DUNGEON_TOWN="1", DUNGEON_TOWN_APART="0", DUNGEON_DEPTHS="2", DUNGEON_MONSTERS="3",
                  DUNGEON_TRAPS="3", DUNGEON_LURKERS="1", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_BOSS="0", DUNGEON_SEED="7",
                  DUNGEON_SKILLS="1", DUNGEON_TRPG_COMBAT="1", DUNGEON_RANDOM_SKILL="0", DUNGEON_NPC_BRAIN="0",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_STATE_DIR=os.path.join(TMP, "state"))
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_RESUME", "DUNGEON_START", "DUNGEON_SOLO", "DUNGEON_MENU", "DUNGEON_PARTYFORM",
          "DUNGEON_STREAM_OBS", "DUNGEON_RUNS_DIR"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import info_guard as IG                              # noqa: E402
import judge                                         # noqa: E402
import scenario                                      # noqa: E402
import show_runner                                   # noqa: E402
import snapshot                                      # noqa: E402
import social_reactions as SR                        # noqa: E402

show_runner.STEP_DELAY = 0
fails = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("ok  " if ok else "FAIL", name, (" — " + str(detail)[:400]) if (detail != "" and not ok) else ""))
    if not ok:
        fails.append(name)


def capture_prompts(d, bots, inbox, reply=None):
    """think_all 한 번 — 캐릭터마다 claude_brain 이 실제로 만든 글 전체(_call_claude 를 가로챈다, 실 콜 없음)."""
    got = {}

    def stub(prompt, model="haiku"):
        got[re.search(r"- 번호 (\d+),", prompt).group(1)] = prompt
        return json.dumps(reply or {"type": "wait", "reason": "정보 보호 검증"}, ensure_ascii=False)
    with patch.object(brains, "_call_claude", stub):
        decs = brains.think_all(d, bots, inbox)
    return got, decs


MAP = ["############", "#1.2..#...3#", "#.....#....#", "#.....#...>#", "############"]


def world(hidden):
    """같은 시드의 장면. hidden 이면 1(비교 대상)이 못 보는 일 둘: 3 의 숨은 굴림(rng 소비) + 3 → 2 비공개 사건."""
    d, bots = scenario.build({"map": MAP, "seed": 7})
    d.turn = 1
    state = d.rng.getstate()
    book = SR.book(d)
    if hidden:
        out = judge.notice(d, bots[1], bots[2], ctx="steal")                    # 2 가 3 을 알아채나 — 숨은 굴림
        res = {"char": "3", "type": "search", "target": "b2", "result": "no_effect"}
        rid = book.record("bond", "3", ["2"], d.turn, private=True, form="몰래 살핀다")
        IG.add_audit(res, "social_event_id", rid)
        IG.add_audit(res, "notice", out["audit"])
        d._note_last(bots[2], res)
    d.rng.setstate(state)                                                       # rng 주입 — 숨은 굴림의 소비를 걷는다(정보 차이만 남긴다)
    inbox, _ = show_runner.deliver_and_hail(d, bots, {"2": "같이 가자, 저쪽이 수상해"}, {"2": "1"})
    d.turn = 2
    return d, bots, inbox


print("── ① 비간섭: 못 보는 비공개 사건·숨은 굴림이 앞에 있어도 프롬프트 바이트가 같다")
dA, botsA, inboxA = world(False)
dB, botsB, inboxB = world(True)
pA, decA = capture_prompts(dA, botsA, inboxA)
pB, decB = capture_prompts(dB, botsB, inboxB)
gidA = [e["id"] for e in SR.book(dA).events.values() if e["type"] == "say"]
gidB = [e["id"] for e in SR.book(dB).events.values() if e["type"] == "say"]
check("① 원장 번호는 실제로 갈렸다(같은 말이 A 에선 %s, B 에선 %s — 시험이 헛돌지 않는다)" % (gidA, gidB), gidA == ["social_1"] and gidB == ["social_2"])
check("① 1 의 프롬프트 전체 바이트가 같다(사건 번호·본문·COMMON 목록 포함)", pA.get("1") == pB.get("1") and bool(pA.get("1")))
check("① 1 이 보는 사건 = 자기 번호 social_1 · 본문 그대로 · COMMON 줄 있음",
      "[social_1]" in pA["1"] and "잡담: 같이 가자, 저쪽이 수상해" in pA["1"] and "\nCOMMON: " in pA["1"]
      and "social_2" not in pB["1"])
check("① 비공개 사건은 받는 사람(2)에게는 간다 — 2 의 프롬프트엔 있고(자기 번호 social_1) 1 에겐 없다",
      "[social_1]" in pB["2"] and "몰래 살핀다" in pB["2"] and "몰래 살핀다" not in pB["1"] and "몰래 살핀다" not in pA["2"])
for d_, b_ in ((dA, botsA), (dB, botsB)):
    b_[0]["order"] = None
dA.turn = dB.turn = 3
rA = SR.book(dA).consume("1", {"type": "wait", "reaction": "like", "reaction_to": "social_1", "src": "haiku"}, 3)
rB = SR.book(dB).consume("1", {"type": "wait", "reaction": "like", "reaction_to": "social_1", "src": "haiku"}, 3)
check("① 받은 번호로 한 반응은 원장의 제 사건으로 간다(A social_1 · B social_2 — 둘 다 2 의 말)",
      rA and rB and rA["reaction_to"] == "social_1" and rB["reaction_to"] == "social_2"
      and rA["source"]["text"] == rB["source"]["text"] == "같이 가자, 저쪽이 수상해")
inboxA2, _ = show_runner.deliver_and_hail(dA, botsA, {"2": "그럼 내가 앞장설게"}, {"2": "1"})
inboxB2, _ = show_runner.deliver_and_hail(dB, botsB, {"2": "그럼 내가 앞장설게"}, {"2": "1"})
pA2, _ = capture_prompts(dA, botsA, inboxA2)
pB2, _ = capture_prompts(dB, botsB, inboxB2)
check("① 이어지는 공개 대화도 바이트가 같다(1 의 두 번째 사건 = social_2)", pA2.get("1") == pB2.get("1") and "[social_2]" in pA2["1"])

print("── ② 행동자 프롬프트에 audit·상대 굴림·비공개 사건 id 가 없다")
lastB3 = botsB[2]["last"]
check("② 비공개 사건을 만든 행동자(3)의 last·궤적: audit·사건 id 없음 · 공개 칸(type·target·result)은 그대로",
      "audit" not in lastB3 and "social_event_id" not in lastB3 and lastB3.get("result") == "no_effect" and lastB3.get("target") == "b2"
      and all("audit" not in e and "social_event_id" not in e for e in botsB[2].get("trail") or []))
p3 = pB.get("3", "")
check("② 3 의 프롬프트: 'audit'·사건 번호 없음 · 자기 결과(궤적 꼬리표 '[변화 없음] search b2')는 있다",
      p3 and "audit" not in p3 and "social_" not in p3.replace("`social_...`", "") and "[변화 없음] search b2" in p3, p3[:1500])
d2, bots2 = scenario.build({"map": ["########", "#12...>#", "#......#", "########"], "seed": 11})
d2.turn = 1
o2 = d2.view(bots2[0], bots2)
atk, err = CA.parse({"type": "attack", "target": "b2"}, o2)
raw = d2.act(bots2[0], atk, bots2)
hidden_keys = set(IG.PERSON_ROLL_KEYS) & set(raw)
check("② 사람 대상 공격: 원본 결과엔 굴림·AC(관전용) · last·궤적엔 없다 · 성패(hit)는 남는다",
      err is None and raw.get("result") == "attack" and {"roll", "ac"} <= hidden_keys
      and not (set(IG.PERSON_ROLL_KEYS) & set(bots2[0]["last"])) and "hit" in bots2[0]["last"]
      and all(not (set(IG.PERSON_ROLL_KEYS) & set(e)) for e in bots2[0].get("trail") or []), (sorted(raw), sorted(bots2[0]["last"])))
ms = judge.mind_save(d2, bots2[1], 15, source="감사표식-출처")
res2 = {"char": "1", "type": "search", "target": "b2", "result": "no_effect", "reason_code": ms["audit"]["source"],
        "audit": {"save": ms["audit"]}}
d2._note_last(bots2[0], res2)
p2, _ = capture_prompts(d2, bots2, {"1": [], "2": []})
check("② audit 값을 문장 칸(reason_code)에 옮겨 적어도 프롬프트엔 없다(궤적 꼬리표는 그려졌다) · 직전 결과 문장은 기본 문구 '(no_effect)'",
      "감사표식" not in p2.get("1", "x") and "audit" not in p2.get("1", "x") and "[변화 없음] search b2" in p2.get("1", "")
      and brains._last_prose(bots2[0]["last"], {}).endswith("(no_effect)"), p2.get("1", "")[:1500])
check("② 프롬프트에 결과 dict 의 굴림 칸이 JSON 으로 새지 않는다('\"roll\"'·'\"ac\"'·'\"dc\"' 없음)",
      all(t not in p2.get("1", "") for t in ('"roll"', '"ac"', '"dc"', '"total"')))

print("── ③ nested audit: 옮겨 적은 audit 값도 투영 뒤 사라진다")
nested = judge.notice(d2, bots2[1], bots2[0])
au = nested["audit"]
res3 = {"char": "1", "type": "steal", "target": "b2", "result": "failed", "audit": au,
        "alias": au, "copy": dict(au), "effects": [{"type": "x", "audit": {"k": 1}, "keep": 7}, au],
        "roll_copy": au["roll"], "ctx_copy": au["ctx"], "deep": {"inner": {"dc": au["dc"], "ok": True}}, "plain": 13,
        "note": {"audit": "표식 없는 숨은 원인", "seen": "보인 것"}}                 # 칸 이름 규칙만이 잡는 꼴(그릇도 표식도 아닌 audit 값)
before = copy.deepcopy(res3)
pub3 = IG.public(res3, bots2[0])
flat = json.dumps(pub3, ensure_ascii=False)
check("③ audit 칸·별칭(같은 객체)·dict 사본·중첩 audit·값 복사(굴림·문턱·ctx) 전부 사라진다",
      "audit" not in pub3 and "alias" not in pub3 and pub3.get("copy") == {} and pub3["effects"] == [{"type": "x", "keep": 7}]
      and "roll_copy" not in pub3 and "ctx_copy" not in pub3 and pub3["deep"] == {"inner": {"ok": True}}
      and pub3["note"] == {"seen": "보인 것"}, flat)
check("③ 다른 칸은 그대로(type·target·result·plain 13 — 같은 숫자라도 표식 없는 값은 남는다) · 원본 불변(관전 스트림은 원본)",
      pub3["type"] == "steal" and pub3["result"] == "failed" and pub3["plain"] == 13 and res3 == before and "audit" in res3)
mon = {"type": "attack", "target": "고블린", "target_id": "m3", "roll": 14, "ac": 12, "hit": True}
per = {"type": "attack", "target": "카야", "target_id": "b2", "roll": 14, "mod": 3, "total": 17, "ac": 15, "hit": True,
       "combat_roll": {"rolls": [14]}, "dmg": 4}
sk = {"type": "cleave", "target": "b2", "skill_id": "cleave", "skill_roll": {"roll": 9}, "skill_dc": 13,
      "effects": [{"type": "damage", "save": {"roll": 4}, "applied": True, "value": 3}]}
check("③ 사람 대상만 굴림·문턱을 걷는다: 몹 대상 공격은 그대로 · 사람 대상 공격·스킬(대상 내성 포함)은 성패·피해만",
      IG.public(mon) == mon and IG.public(per) == {"type": "attack", "target": "카야", "target_id": "b2", "hit": True, "dmg": 4}
      and IG.public(sk) == {"type": "cleave", "target": "b2", "skill_id": "cleave", "effects": [{"type": "damage", "applied": True, "value": 3}]})
check("③ 표식 값은 JSON·피클·깊은 복사에서 보통 값처럼(관전 스트림 그대로) · 산술 결과는 표식이 없다(머리글 ⚠️)",
      json.loads(json.dumps(au))["dc"] == au["dc"] and IG.is_secret(pickle.loads(pickle.dumps(au))["roll"])
      and IG.is_secret(copy.deepcopy(au)["roll"]) and not IG.is_secret(au["roll"] + 1))

print("── ④ alias 위조: 남의 번호·원장 번호로는 반응할 수 없다")
bk = SR.ReactionBook(1)
e1 = bk.record("give", "1", ["2"], 1, what="물약")
e2 = bk.record("bond", "1", ["3"], 1, form="손을 흔든다")
e3 = bk.record("say", "2", ["3"], 1, text="안녕")
o2_, o3_ = bk.offer("2"), bk.offer("3")
check("④ 번호는 받은 사람마다 1부터: 2 = [social_1(give)] · 3 = [social_1(bond), social_2(say)] · 원장은 social_1..3",
      [(e["id"], e["type"]) for e in o2_] == [("social_1", "give")]
      and [(e["id"], e["type"]) for e in o3_] == [("social_1", "bond"), ("social_2", "say")] and [e1, e2, e3] == ["social_1", "social_2", "social_3"])
check("④ offer 는 recipients·source_action_id·parent_action_id·private 를 싣지 않는다",
      all(not ({"recipients", "source_action_id", "parent_action_id", "private"} & set(e)) for e in o2_ + o3_))
r_forge = bk.consume("2", {"reaction": "like", "reaction_to": "social_2", "src": "haiku"}, 2)
bk.offer("2")
r_global = bk.consume("2", {"reaction": "dislike", "reaction_to": "social_3", "src": "haiku"}, 2)
d_err = {"reaction": "like", "reaction_to": "social_1", "src": "haiku"}
bk.offer("4")
r_none = bk.consume("4", d_err, 2)
check("④ 2 가 3 의 번호(social_2)·원장 번호(social_3)로 반응 → 거절 · 아무것도 안 받은 4 의 social_1 → 거절(reaction_error)",
      r_forge is None and r_global is None and r_none is None and d_err.get("reaction_error", {}).get("code") == "reaction_not_eligible")
bk2 = SR.ReactionBook(1)
bk2.record("give", "1", ["2"], 1, what="물약")
bk2.record("bond", "1", ["3"], 1, form="손을 흔든다")
bk2.offer("2"), bk2.offer("3")
r2 = bk2.consume("2", {"reaction": "like", "reaction_to": "social_1", "src": "haiku"}, 2)
r3 = bk2.consume("3", {"reaction": "dislike", "reaction_to": "social_1", "src": "haiku"}, 2)
check("④ 같은 번호(social_1)라도 사람마다 제 사건: 2 → give(원장 social_1) · 3 → bond(원장 social_2)",
      r2["reaction_to"] == "social_1" and r2["source"]["type"] == "give" and r3["reaction_to"] == "social_2" and r3["source"]["type"] == "bond")

print("── ⑤ 피클 왕복·옛 원장 이관·옛 스냅샷 이어받기")
rt = pickle.loads(pickle.dumps(bk2))
check("⑤ 피클 왕복: 번호표 그대로", rt.alias == bk2.alias and rt.alias["3"] == {"social_2": "social_1"})
old = SR.ReactionBook(1)
for t in ("첫째", "둘째"):
    old.record("say", "1", ["2"], 1, text=t)
old.record("say", "1", ["3"], 1, text="셋째")
del old.alias                                          # 옛 원장(p0.5.3 이하)에는 번호표 칸이 없다
snap_old = {"version": 2, "state_version": 1, "reaction_book": pickle.loads(pickle.dumps(old)), "d": None}
up = snapshot.upgrade(snap_old)
ob = up["reaction_book"]
offered2 = ob.offer("2")
check("⑤ 이관 1→2: 옛 원장에 번호표(원장 순서) → 대기 사건은 받은 순서대로 social_1·social_2 · 반응이 제 사건으로",
      up["state_version"] == 2 and [(e["id"], e["text"]) for e in offered2] == [("social_1", "첫째"), ("social_2", "둘째")]
      and ob.consume("2", {"reaction": "like", "reaction_to": "social_2", "src": "haiku"}, 2)["source"]["text"] == "둘째"
      and ob.offer("3")[0]["id"] == "social_1")
check("⑤ 이관 등록부 완결(0..%d) · 이관은 한 번(다시 올려도 번호표 그대로)" % (snapshot.STATE_VERSION - 1),
      sorted(snapshot.MIGRATIONS) == list(range(snapshot.STATE_VERSION)) and snapshot.upgrade(up)["reaction_book"].alias is ob.alias)
old2 = SR.ReactionBook(1)
x_old = old2.record("give", "1", ["2"], 1, what="물약")             # 이미 내보내고 지난 사건
old2.offer("2")
old2.consume("2", {"type": "wait"}, 2)
a_old = old2.record("give", "3", ["2"], 3, what="단검")             # 멈출 때 대기 중(2 는 걷는 중이었다)
old2.record("say", "3", ["1"], 3, text="남의 사건")                  # 2 가 받지 않은 사건 — 2 의 번호에 안 섞인다
del old2.alias
up2 = snapshot.upgrade({"version": 2, "state_version": 1, "reaction_book": pickle.loads(pickle.dumps(old2)), "d": None})
ob2 = up2["reaction_book"]
b_new = ob2.record("bond", "1", ["2"], 4, form="어깨를 두드린다")    # 이어간 뒤 새 사건(2 는 아직 걷는 중)
mix = ob2.offer("2")
check("⑤ 이관 → 새 사건 → offer: 번호 = 받은 순서(지난 건네기 social_1 · 옛 대기 건네기 social_2 · 새 친목 social_3) · 번호표 = 원장 순서 · 반응이 제 사건으로",
      [(e["id"], e["type"]) for e in mix] == [("social_2", "give"), ("social_3", "bond")]
      and ob2.alias["2"] == {x_old: "social_1", a_old: "social_2", b_new: "social_3"}
      and ob2.consume("2", {"reaction": "like", "reaction_to": "social_2", "src": "haiku"}, 5)["source"]["what"] == "단검",
      ([(e["id"], e["type"]) for e in mix], ob2.alias.get("2")))
S52 =os.path.join(TMP, "s52", "state")
shutil.copytree(FIX, S52)
s52, _m52 = snapshot.load(os.path.join(S52, "snapshot.pkl"))
check("⑤ v0.5.2 고정 자료: 새 로더가 내용 판 0 → 2 · 원장에 번호표",
      s52["state_version"] == 2 and isinstance(getattr(s52["reaction_book"], "alias", None), dict))
S53 = os.path.join(TMP, "s53", "state")
shutil.copytree(FIX, S53)
with open(os.path.join(S53, "snapshot.pkl"), "rb") as f:
    raw53 = pickle.load(f)                             # 리포 고정 자료(코드와 같은 신뢰 급 — fixtures README)
raw53 = snapshot.MIGRATIONS[0](raw53)                  # 0.5.3 이 쓰던 꼴 = 정신·숙련 칸 + 판형 2·내용 판 1(원장 번호표는 없다)
raw53.update(version=2, state_version=1)
with open(os.path.join(S53, "snapshot.pkl"), "wb") as f:
    pickle.dump(raw53, f, protocol=pickle.HIGHEST_PROTOCOL)
meta53 = json.load(io.open(os.path.join(S53, "snapshot.json"), encoding="utf-8"))
with io.open(os.path.join(S53, "snapshot.json"), "w", encoding="utf-8") as f:
    json.dump(dict(meta53, version=2, state_version=1), f, ensure_ascii=False, indent=1)
s53, _m53 = snapshot.load(os.path.join(S53, "snapshot.pkl"))
check("⑤ 0.5.3 꼴 스냅샷(판형 2·내용 판 1·번호표 없음): 새 로더가 내용 판 2 · 번호표 · 몸의 정신·숙련 그대로",
      not hasattr(raw53["reaction_book"], "alias") and s53["state_version"] == 2
      and isinstance(getattr(s53["reaction_book"], "alias", None), dict) and all("mind" in b for b in snapshot._bodies(s53)))
env53 = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
env53.update(json.load(io.open(os.path.join(FIX, "env.json"), encoding="utf-8")))
env53.update(PYTHONUTF8="1", DUNGEON_STATE_DIR=S53, DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"),
             DUNGEON_RESUME=os.path.join(S53, "snapshot.pkl"), DUNGEON_RUNS_DIR=os.path.join(TMP, "s53", "runs"))
DRIVER = ("import sys; sys.path.insert(0, %r); import brains; brains._call_claude = lambda p, m='haiku': ('', None); "
          "import show_runner; show_runner.STEP_DELAY = 0; show_runner.main()" % HERE)   # __main__ 을 밟지 않는다(.env 무접촉)
p53 = subprocess.run([sys.executable, "-c", DRIVER], cwd=HERE, env=env53, capture_output=True, timeout=600)
recs53 = [json.loads(x) for x in io.open(os.path.join(S53, "stream.jsonl"), encoding="utf-8") if x.strip()]
ticks53 = [r["turn"] for r in recs53 if r.get("kind") == "tick"]
check("⑤ 러너가 0.5.3 꼴 스냅샷을 이어간다: resume 줄 하나 · resume_failed 없음 · 틱 연속 · end",
      p53.returncode == 0 and len([r for r in recs53 if r.get("kind") == "resume"]) == 1 and "resume_failed" not in recs53[0]
      and ticks53 == list(range(1, int(env53["DUNGEON_TURNS"]) + 1)) and recs53[-1].get("kind") == "end",
      (p53.returncode, p53.stderr.decode("utf-8", "replace")[-400:]))

print("── ⑥ 미등록 결과·미등록 관측 키 0(러너 판) · 폴백 축소 · 중립 문장")


def runner_sweep():
    st = {"views": 0, "last": 0, "trail": 0, "wit": 0, "events": 0, "msg_ids": 0, "skill": 0, "pvp": 0}
    bad, nums, counter, cur = [], {}, {}, {}
    sheets = show_runner.load_party(os.path.join(HERE, "party.json"))   # 기본 파티 셋(내장 HEROES 는 둘뿐)
    names = {c: (sheets[c].get("name") or sheets[c]["job"]) for c in ("1", "2", "3")}
    orig_think = brains.think_all

    def think(d, bots, inbox=None, on_error=None):
        cur["d"] = d
        return orig_think(d, bots, inbox, on_error=on_error)

    def decide(obs, char, bot=None, roster=None, solo=False):
        st["views"] += 1
        txt = brains._wire(obs, names, compose=True)
        if brains.unwired_keys(obs):
            bad.append(("unwired", char, obs.get("turn"), brains.unwired_keys(obs)))
        last = obs.get("last")
        if last:
            st["last"] += 1
            st["skill"] += bool(last.get("skill_id"))
            if brains._last_prose(last, names).startswith("{") or "audit" in last or "social_event_id" in last:
                bad.append(("last", last.get("type"), last.get("result")))
            if IG.is_person_ref(last.get("target_id") or last.get("target")) and set(IG.PERSON_ROLL_KEYS) & set(last):
                bad.append(("person_roll", last.get("type"), sorted(set(IG.PERSON_ROLL_KEYS) & set(last))))
        for e in obs.get("trail") or []:
            st["trail"] += 1
            if e.get("type") != "gap" and any(str(fact).startswith("{") for _k, _l, fact in G.event_tags(e, names)):   # gap = 생략 표식(_trail_prose 가 따로 그린다)
                bad.append(("trail", e.get("type"), e.get("result")))
        for w in obs.get("witnessed") or []:
            st["wit"] += 1
            if "의 일: {" in brains._witness_prose(w):
                bad.append(("witnessed", w.get("kind")))
        evs = obs.get("social_events") or []
        for e in evs:
            st["events"] += 1
            if SR.describe(e) == "상호작용":
                bad.append(("event_type", e.get("type")))
            nums.setdefault(char, []).append(int(e["id"].split("_")[1]))
        if set(re.findall(r"\[(social_\d+)\]", txt)) != {e["id"] for e in evs}:
            bad.append(("ids", char, obs.get("turn")))
        mine = SR.book(cur["d"]).alias.get(char, {}).values() if SR.book(cur["d"]) else ()
        for m in obs.get("messages") or []:
            if "social_event_id" in m:
                st["msg_ids"] += 1
                if m["social_event_id"] not in mine:
                    bad.append(("msg_id", char, m["social_event_id"]))
        n = counter[char] = counter.get(char, 0) + 1
        p = CA.fallback(G.dummy_brain(obs, char), obs)
        ally = next((t["id"] for t in obs.get("targets") or [] if str(t["id"]).startswith("b") and t["id"] != "b" + char), None)
        if ally and n % 5 == 2:
            p = {"type": "bond", "target": ally, "form": "어깨를 두드린다"}
        elif ally and n % 9 == 4 and obs.get("potions"):
            p = {"type": "give", "target": ally, "item": "i1"}
        elif ally and n in (8, 16) and char == "3":
            p = {"type": "attack", "target": ally}                      # 사람 대상 공격 한 번(굴림이 last 에서 빠지는지 — 위 'last' 검사)
            st["pvp"] += 1
        elif obs.get("skills") and n % 6 == 3:                          # 스킬 결과(SK.summary 경로) — 보이는 몹, 없으면 동료·자신
            mon = next((t["id"] for t in obs.get("targets") or [] if str(t["id"]).startswith("m")), None)
            p = {"type": obs["skills"][0]["id"], "target": mon or ally or "self"}
        if n % 3 == 1:
            p = {**p, "say": "여기 조심하자", "to": "all", "say_kind": "잡담"}
        if evs:
            p = {**p, "reaction": "like", "reaction_to": evs[-1]["id"]}
        act, err = CA.parse(p, obs)
        if err:
            act, err = CA.parse(CA.fallback(G.dummy_brain(obs, char), obs), obs)
        return {**act, **SR.parse(p, obs), **{k: p[k] for k in ("say", "to", "say_kind") if k in p},
                "reason": "정보 보호 검증", "src": "fixture"}

    with patch.object(show_runner, "load_party", return_value={c: dict(sheets[c]) for c in ("1", "2", "3")}), \
         patch.object(brains, "think_all", think), patch.object(brains, "claude_brain", decide), \
         patch.object(brains, "_call_claude", side_effect=AssertionError("실제 모델 호출 금지")), \
         patch.object(show_runner.time, "sleep", lambda _: None), contextlib.redirect_stdout(io.StringIO()):
        show_runner.main()
    rows = [json.loads(x) for x in (Path(os.environ["DUNGEON_STATE_DIR"]) / "stream.jsonl").read_text(encoding="utf-8").splitlines()]
    return st, bad, nums, rows, SR.book(cur["d"])


st6, bad6, nums6, rows6, book6 = runner_sweep()
reacts6 = [r for row in rows6 for r in row.get("reactions") or []]
check("⑥ 러너 판 표본: 판단 %(views)d · last %(last)d · 궤적 %(trail)d · 목격 %(wit)d · 받은 사건 %(events)d · 들은 말 번호 %(msg_ids)d · 스킬 결과 %(skill)d" % st6,
      st6["views"] >= 80 and st6["last"] >= 60 and st6["trail"] >= 100 and st6["wit"] >= 20 and st6["events"] >= 20
      and st6["msg_ids"] >= 10 and st6["skill"] >= 1 and st6["pvp"] >= 1, st6)
check("⑥ 모든 판단에서 미등록 관측 키·last 폴백·궤적 폴백·목격 폴백·모르는 사건 type 0 · last 에 audit·전역 사건 번호 없음",
      not bad6, bad6[:6])
own6 = {c: [eid for eid, e in book6.events.items() if c in e["recipients"]] for c in ("1", "2", "3")}
check("⑥ 번호표 = 그 사람이 받은 사건만 원장 순서대로 social_1..n(남의 사건 수가 안 섞인다) · 내보낸 번호는 늘어나기만 한다",
      all(book6.alias.get(c) == {eid: "social_%d" % (i + 1) for i, eid in enumerate(own6[c])} for c in own6)
      and all(all(b > a for a, b in zip(v, v[1:])) for v in nums6.values()) and len(nums6) == 3 and len(book6.events) > max(map(len, own6.values())),
      {c: (len(own6[c]), len(book6.alias.get(c, {}))) for c in own6})
check("⑥ 반응 %d건: 원장 번호로 기록 · 그 사건을 실제로 받은 사람 · 결정의 번호 = 그 사람의 번호표" % len(reacts6),
      len(reacts6) >= 5 and all(r["actor"] in r["source"]["recipients"] for r in reacts6)
      and all(book6.alias[r["actor"]][r["reaction_to"]] == next(row["decisions"][r["actor"]]["reaction_to"] for row in rows6
                                                               if row.get("kind") == "tick" and row["turn"] == r["turn"]) for r in reacts6))
unk = brains._last_prose({"type": "steal", "target": "b2", "result": "failed", "resolution": {"status": "failed"},
                          "dc": 18, "noticed": True, "why": "숨은 목격자"}, {})
check("⑥ 모르는 결과의 폴백 = {type, target, status} 만(문턱·알아챔·원인 칸 없음)",
      json.loads(unk) == {"type": "steal", "target": "b2", "status": "failed"})
tags = G.event_tags({"type": "steal", "target": "b2", "result": "failed", "dc": 18, "noticed": True})
check("⑥ 궤적 꼬리표의 폴백도 같은 꼴", tags == [("misc", "기타", '{"type": "steal", "target": "b2", "status": "failed"}')], tags)
wp = brains._witness_prose({"kind": "ally_steal", "char": "2", "name": "카야", "dc": 18})
check("⑥ 목격 폴백은 종류(kind)만", wp == '카야(봇2)의 일: {"kind": "ally_steal"}', wp)
ob6 = d2.view(bots2[0], bots2)
ob6["secret_plan"] = {"hidden": "숨은계획표식"}
w6 = brains._wire(ob6, {}, compose=True)
check("⑥ 미등록 관측 키는 그리지 않는다('그 밖의 정보' 절 없음) · unwired_keys 가 잡는다",
      "숨은계획표식" not in w6 and "그 밖의 정보" not in w6 and brains.unwired_keys(ob6) == ["secret_plan"])
check("⑥ 사건 문장: use = 물약 사용 · 모르는 type = 중립 문장 '상호작용'(물약으로 지어내지 않는다)",
      SR.describe({"type": "use", "heal": 5}) == "물약 사용: HP +5" and SR.describe({"type": "steal"}) == "상호작용")
ts = io.open(os.path.join(HERE, "game", "src", "text", "reactions.ts"), encoding="utf-8").read()
vw = io.open(os.path.join(HERE, "viewer", "index.html"), encoding="utf-8").read()
check("⑥ 관전 화면 둘(GS reactions.ts · viewer/index.html)도 use 가지 + 모르는 type 중립 문장",
      "if (e.type === 'use') return `물약 사용" in ts and "상호작용 (${e.type})" in ts
      and "s.type === 'use' ? `물약 사용" in vw and "상호작용 (${s.type})" in vw)

print("── ⑦ 판정 함수 묶음(judge)")


class FakeD:
    """주사위 눈을 차례로 내는 던전 흉내 — 판정 함수가 던전의 d20 만 쓰는지·몇 번 쓰는지 센다."""
    def __init__(self, *rolls):
        self.rolls, self.n = list(rolls), 0

    def d20(self):
        self.n += 1
        return self.rolls.pop(0)


mage, rogue, war = {"job": "마법사"}, {"job": "도적", "stealth": 4}, {"job": "전사", "str": 3, "dex": 0}
fd = FakeD(12, 11, 8)
n1, n2, n3 = judge.notice(fd, mage, rogue), judge.notice(fd, mage, rogue), judge.notice(fd, war, rogue, ctx="steal")
check("⑦ notice: 마법사(정신 3 + 수색 2) vs 13 + 도적 은신 4 = 17 — 눈 12 알아챔 · 11 놓침 · steal 은 13 고정(전사 0 + 눈 8 = 8 놓침)",
      n1["noticed"] is True and n2["noticed"] is False and n3["noticed"] is False and n1["audit"]["dc"] == 17 and n3["audit"]["dc"] == 13
      and fd.n == 3)
fd = FakeD(5, 15)
na = judge.notice(fd, mage, rogue, advantage=True)
fd2 = FakeD(9)
nm = judge.notice(fd2, object(), rogue, mod=2)
check("⑦ notice: 유리면 두 번 굴려 큰 눈 · 몹 관측자는 호출자가 준 보정(mod)만", na["noticed"] is True and fd.n == 2 and nm["noticed"] is False
      and nm["audit"]["mod"] == 2)
fd = FakeD(10, 13, 11, 13)
c1, c2 = judge.contest(fd, war, {"str": 0}, "str", "str"), judge.contest(fd, war, {"str": 0}, "str", "str")
check("⑦ contest: a 먼저·b 다음(고정 순서) · 13 대 13 동점은 방어자 · 14 대 13 은 행동자",
      c1["won"] is False and c2["won"] is True and c1["audit"]["a"]["roll"] == 10 and c1["audit"]["b"]["roll"] == 13 and fd.n == 4)
fd = FakeD(3, 8, 13, 18, 18)
stages = [judge.own_check(fd, war, 2, 10, tiers=3)["stage"] for _ in range(4)] + [judge.own_check(fd, war, 2, 10)["stage"]]
check("⑦ own_check: DC 10·보정 2 — 눈 3 실패 0 · 8 겨우 1 · 13(여유 5) 2 · 18(여유 10) 3 · tiers 1 이면 1", stages == [0, 1, 2, 3, 1], stages)
fd = FakeD(12, 12)
s1, s2 = judge.mind_save(fd, mage, 15, source="b1"), judge.mind_save(fd, G.Monster.__new__(G.Monster), 15)
check("⑦ mind_save: 마법사 정신 3 + 12 = 15 버팀 · 몹 정신 0 + 12 못 버팀 · 건 사람은 audit 에",
      s1["saved"] is True and s2["saved"] is False and s1["audit"]["source"] == "b1")
outs = [n1, c1, judge.own_check(FakeD(9), war, 0, 10), s1]


def leaves(v):
    if isinstance(v, dict):
        return [y for x in v.values() for y in leaves(x)]
    if isinstance(v, list):
        return [y for x in v for y in leaves(x)]
    return [v]


check("⑦ 결과 = 공개 칸 하나(성패·단계, 표식 없음) + audit(잎 전부 표식) — 공개 투영이 audit 을 통째로 걷는다",
      all(set(o) - {"audit"} in ({"noticed"}, {"won"}, {"stage"}, {"saved"}) for o in outs)
      and all(not IG.is_secret(o[k]) for o in outs for k in o if k != "audit")
      and all(IG.is_secret(x) for o in outs for x in leaves(o["audit"]) if x is not None)
      and all("audit" not in IG.public(o) for o in outs))
eng = "".join(io.open(os.path.join(HERE, f), encoding="utf-8").read() for f in
              ("dungeon_gm.py", "composed_actions.py", "skill_core.py", "show_runner.py", "brains.py", "interactables.py"))
check("⑦ 엔진은 아직 판정 함수를 부르지 않는다 — 0.5 는 판정 rng 소비가 늘지 않는다(쓰는 곳은 그 행동의 단계)",
      not re.search(r"judge\.(notice|contest|own_check|mind_save)\(", eng))
check("⑦ SK.ability 는 judge.ability 한 규칙(봇 정신 = prof · 몹 힘 = atk · 민첩 = AC-10)",
      G.SK.ability(("bot", (0, 0), mage), "mind") == 3 and judge.ability(war, "str") == 3)

print("── ⑧ 불투명 ID")
a1 = IG.opaque_id("c", 7, 2, 10, 4, 55)
check("⑧ 같은 재료 → 같은 ID · 다른 재료 → 다른 ID · 꼬리는 숫자뿐이 아니다",
      a1 == IG.opaque_id("c", 7, 2, 10, 4, 55) and a1 != IG.opaque_id("c", 7, 2, 10, 4, 56) and not a1[1:].isdigit() and len(a1) == 5)
taken = {a1}
a2 = IG.opaque_id("c", 7, 2, 10, 4, 55, taken=taken)
digits = [IG.opaque_id("f", i) for i in range(300)]
check("⑧ 겹치면 한 자 늘린다 · 300개 중 숫자뿐인 꼬리 0(옛 순번 ID 'f12' 와 섞이지 않는다)",
      a2 != a1 and a2.startswith(a1) and len(a2) == 6 and not any(x[1:].isdigit() for x in digits))

shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAIL %d — %s" % (len(fails), "; ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_info_guard (p0.5.4 정보 보호: 비간섭·프롬프트 무누출·nested audit·수신자별 번호·이관·미등록 0·판정 함수·불투명 ID, 실 LLM 0콜)")
