# -*- coding: utf-8 -*-
"""obs wire 직렬화(D17-3 문장형 + D17-4 스위치) 헤들리스 검증 — 15번째 게이트.
게이트:
  ① 순수성: _wire 는 obs 를 변형하지 않는다(딥카피 대조) + 같은 obs → 같은 문자열(결정론)
  ② 전수성: 실측 스윕에서 sights 의 모든 지칭(계단·피처 id·몹 id·동료·트인 길)과 장부
     (known statics id·last_seen)가 문장에 등장 — 표현 층의 조용한 누락은 조향이다
  ③ 실전 폴백 0: 스윕 전체에서 '그 밖의 정보'(미지 키)·last JSON 폴백 미발동
     — 실전 어휘 전부가 문장 어휘로 커버된다는 증명
  ④ 스위치(D17-4): OBS_ASCII=0 → 그림 섹션 부재 / OBS_POS=0 → 좌표 줄 부재 / 켬(기본) → 존재
  ⑤ 시야-온리 보존: concealed 몹 id 가 문장 어디에도 없음(회귀 그물)
  ⑥ last·주입 어휘 합성: 대표 last 형태 전수(피격/조우/함정/길막힘/허탕/동행접음/작정깨짐/
     상자/샘/공격/수색/핑)와 intent·witnessed·messages 주입이 전부 문장으로 렌더 + 미지
     형태는 JSON 폴백으로 정직하게 노출
  ⑦ 프롬프트 조립: 메뉴·자유서술 모두 obs JSON 덤프(```json) 부재(다이어트 실증) +
     메뉴판에만 번호 목록 존재
(스윕 = dummy 결정론 — LLM 0콜, 초 단위.)
"""
import os
import re
import copy
import json

os.environ.update(DUNGEON_MENU="1", DUNGEON_STEP_DELAY="0",
                  DUNGEON_PARTY_FILE="/nonexistent")
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)
os.environ.pop("DUNGEON_OBS_ASCII", None)  # 스위치 기본값(켬) 고정 — 셸 잔재 오염 방지
os.environ.pop("DUNGEON_OBS_POS", None)

import dungeon_gm as G
import brains


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


NAMES = {"1": "두란", "2": "카야", "3": "피른"}


def _has(txt, tok):
    """id 토큰은 숫자 경계로(m1 이 m10 에 오탐 방지), 그 외는 부분 문자열."""
    if re.match(r"^([mf]\d+|exit|b.)$", tok):
        return re.search(r"(?<![0-9A-Za-z])%s(?![0-9])" % re.escape(tok), txt) is not None
    return tok in txt


def census_ok(obs, txt):
    """② 전수성: obs 의 모든 지칭 대상이 문장에 있다 — sights 와 장부를 오라클로."""
    s = obs.get("sights") or {}
    need = []
    if s.get("exit"):
        need.append("계단(exit)")
    for m in s.get("monsters", []):
        need.append(m["id"])
    for f in s.get("features", []):
        need.append(f["id"])
    for b in s.get("bots", []):
        need.append("봇%s" % b["char"])
    for w in s.get("ways", []):
        need.append("%s쪽으로 트인 길" % w["bearing"])
    k = obs.get("known") or {}
    for e in k.get("statics", []):
        if e.get("id"):
            need.append(e["id"])
    for e in k.get("last_seen", []):
        need.append(("봇%s" % e["char"]) if e.get("char") else e["id"])
    return all(_has(txt, n) for n in need)


# ───────────────────── ①②③⑤ 실측 스윕 (12시드 × 3인 × 80틱) ─────────────────────
def sweep():
    st = {"views": 0, "mutate": 0, "det": 0, "census": 0, "fallback": 0,
          "hidden": 0, "wit": 0, "last_n": 0, "known_n": 0}
    for seed in range(1, 13):
        d = G.Dungeon(seed=seed, w=40, h=16, n_monsters=3, n_traps=3, n_lurkers=1)
        bots = []
        for c in "12":                     # 내장 HEROES 2인(시트 외부화와 독립 — 게이트 격리)
            b = G.spawn(d, c, bots)
            b["ledger"] = G.new_ledger()   # 장부 켬(D17) — known/zone/turn 어휘까지 스윕
            b["known"] = set()             # 도감 켬 — '낯선 짐승' 마스킹 경로
            bots.append(b)
        for tick in range(1, 81):
            d.turn = tick                  # 러너 미러(show_runner 가 스탬프하는 구조)
            for b in bots:
                if not b["alive"] or b["won"]:
                    continue
                if b.get("order"):
                    d.step_order(b, bots)
                    continue
                obs = d.view(b, bots)
                if b.get("intent"):
                    obs["intent"] = b["intent"]     # think_all 주입 미러(렌더 경로 검사)
                snap = copy.deepcopy(obs)
                txt = brains._wire(obs, NAMES)
                st["views"] += 1
                st["mutate"] += (obs != snap)
                st["det"] += (txt == brains._wire(obs, NAMES))
                st["census"] += (0 if census_ok(obs, txt) else 1)
                if "## 그 밖의 정보" in txt or "- 그 결과: {" in txt:
                    st["fallback"] += 1
                if any(_has(txt, "m%d" % m.id) for m in d.monsters
                       if m.alive and m.concealed):
                    st["hidden"] += 1
                st["wit"] += bool(snap.get("witnessed"))
                st["last_n"] += bool(snap.get("last"))
                st["known_n"] += bool((snap.get("known") or {}).get("statics"))
                dec = G.dummy_brain(obs, b["char"])
                d.act(b, dec, bots)
                b["intent"] = {"type": dec.get("type", ""),
                               **({"target": dec["target"]} if dec.get("target") else {})}
            d.monster_turn(bots)
            if all(b["won"] or not b["alive"] for b in bots):
                break
    return st


# ───────────────────── ⑥ last·주입 어휘 합성 ─────────────────────
LASTS = [
    ({"type": "hurt", "by": "고블린", "by_id": "m1", "dmg": 3, "hp": 5}, "맞았다"),
    ({"type": "hurt", "by": "그림자거미", "by_id": "m9", "dmg": 5, "hp": 2,
      "surprise": True}, "기습"),
    ({"type": "plan_broken", "why": "대상 소멸",
      "step": {"type": "interact", "target": "f3"}}, "작정이 깨졌다"),
    ({"type": "walk", "result": "encounter", "target": "f1",
      "monsters": [{"kind": "고블린"}]}, "처음 보는 적"),
    ({"type": "walk", "result": "encounter", "target": "f1",
      "trap": {"name": "가시함정", "dmg": 2}}, "당했다"),
    ({"type": "walk", "result": "encounter", "target": "f1",
      "trap": {"name": "경보함정", "alarm": 2}}, "울렸다"),
    ({"type": "walk", "result": "encounter", "target": "f1",
      "trap": {"name": "가시함정", "safe": True}}, "피했다"),
    ({"type": "walk", "result": "encounter", "target": "f1", "treasure": True}, "보물"),
    ({"type": "walk", "result": "encounter", "target": "f1",
      "found": [{"name": "숨은 보물"}]}, "발견"),
    ({"type": "walk", "result": "blocked", "target": "exit",
      "monsters": [{"kind": "고블린"}]}, "점거"),
    ({"type": "walk", "result": "blocked", "target": "exit",
      "allies": [{"name": "카야"}]}, "크게 돌아야"),
    ({"type": "walk", "result": "blocked", "target": "exit"}, "막혔다"),
    ({"type": "walk", "result": "lost", "target": "b2"}, "곁에 없다"),
    ({"type": "walk", "result": "idle", "target": "follow:b2"}, "동행을 접었다"),
    ({"type": "walk", "result": "arrived", "target": "f2"}, "도착"),
    ({"type": "walk", "result": "at_exit", "target": "exit"}, "계단 앞"),
    ({"type": "walk", "result": "treasure", "target": "f2"}, "보물"),
    ({"type": "attack", "result": "attack", "target": "고블린", "hit": True,
      "dmg": 4, "killed": True}, "쓰러뜨렸다"),
    ({"type": "attack", "result": "attack", "target": "고블린", "hit": False}, "빗나갔다"),
    ({"type": "attack", "result": "attack", "target": "고블린", "hit": True,
      "dmg": 6, "surprise": True}, "기습"),
    ({"type": "attack", "result": "no_target"}, "대상"),
    ({"type": "attack", "result": "too_far"}, "멀었다"),
    ({"type": "interact", "result": "exit", "party": ["1", "2"]}, "함께 내려갔다"),
    ({"type": "interact", "result": "wait_allies", "missing": ["3"]}, "안 모였다"),
    ({"type": "interact", "result": "chest_loot", "target": "f1", "loot": 2}, "보물 2개"),
    ({"type": "interact", "result": "chest_trap", "target": "f1", "dmg": 2}, "독침"),
    ({"type": "interact", "result": "fountain_heal", "target": "f2", "heal": 3}, "회복"),
    ({"type": "interact", "result": "fountain_harm", "target": "f2", "dmg": 1}, "오염"),
    ({"type": "interact", "result": "treasure", "target": "f5"}, "주웠다"),
    ({"type": "interact", "result": "nothing", "target": "f5"}, "아무것도"),
    ({"type": "interact", "result": "too_far", "target": "f5"}, "멀었다"),
    ({"type": "interact", "result": "no_target", "target": "f5"}, "없었다"),
    ({"type": "search", "found": [{"name": "가시함정", "bearing": "N"}]}, "드러냈다"),
    ({"type": "search", "found": []}, "숨은 건 없었다"),
    ({"type": "goto", "result": "pathed", "target": "f3", "len": 5}, "걷기 시작"),
    ({"type": "goto", "result": "arrived", "target": "f3"}, "이미 곁"),
    ({"type": "goto", "result": "blocked", "target": "exit",
      "allies": [{"name": "카야"}]}, "크게 돌아야"),
    ({"type": "explore", "result": "no_path", "target": "auto"}, "새 길이 없다"),
    ({"type": "explore", "result": "pathed", "target": "auto"}, "걷기 시작"),
    ({"type": "follow", "result": "following", "target": "b2"}, "동행"),
    ({"type": "follow", "result": "pathed", "target": "b2"}, "걷기 시작"),
]


def synth_checks():
    bad = [str(l) for l, want in LASTS
           if want not in brains._last_prose(l, NAMES)
           or brains._last_prose(l, NAMES).startswith("{")]
    check("⑥ last 대표 형태 %d종 전부 문장 렌더" % len(LASTS), not bad)
    for b in bad:
        print("         폴백/누락: %s" % b)
    unk = brains._last_prose({"type": "teleport", "result": "zap"}, NAMES)
    check("⑥ 미지 형태 → JSON 폴백(정직 노출)", unk.startswith("{"))

    obs = {"job": "전사", "sex": "남", "hp": 9, "maxhp": 14, "str": 3, "dex": 1,
           "inventory": 1, "depth": 1, "pos": [5, 5],
           "sights": {"exit": None, "features": [], "monsters": [], "ways": [], "bots": []},
           "party": [], "options": [], "ascii_view": ["@"], "legend": {},
           "intent": {"type": "goto", "target": "f3", "reason": "보물부터", "say": "간다"},
           "witnessed": [{"kind": "ally_hurt", "char": "2", "by": "고블린",
                          "by_id": "m1", "name": "카야"}],
           "messages": [{"from": "1", "text": "모여"}],
           "last": {"type": "walk", "result": "lost", "target": "b2"}}
    txt = brains._wire(obs, NAMES)
    check("⑥ intent 렌더(판단·이유·말)",
          "직전 판단: goto f3" in txt and "보물부터" in txt and '"간다"' in txt)
    check("⑥ witnessed 렌더(목격 문장)", "카야(봇2)가 고블린에게 맞는 것을" in txt)
    check("⑥ messages 렌더(들은 말)", '두란(봇1): "모여"' in txt)
    check("⑥ 빈 시야 자리표시", "(아무것도 안 보인다)" in txt)


# ───────────────────── ④ 스위치 / ⑦ 프롬프트 조립 ─────────────────────
def fresh_obs():
    d = G.Dungeon(seed=7, w=40, h=16, n_monsters=3, n_traps=3)
    bots = [G.spawn(d, "1", [])]
    return d.view(bots[0], bots), bots[0]


def switch_checks():
    obs, _ = fresh_obs()
    on = brains._wire(obs, NAMES)
    check("④ 기본(켬): 그림 섹션+좌표 줄 존재",
          "## 주변 그림" in on and "- 좌표:" in on)
    sa, sp = brains.OBS_ASCII, brains.OBS_POS
    try:
        brains.OBS_ASCII = False
        no_a = brains._wire(obs, NAMES)
        check("④ OBS_ASCII=0: 그림 섹션 부재(좌표는 유지)",
              "## 주변 그림" not in no_a and "```" not in no_a and "- 좌표:" in no_a)
        brains.OBS_ASCII = True
        brains.OBS_POS = False
        no_p = brains._wire(obs, NAMES)
        check("④ OBS_POS=0: 좌표 줄 부재(그림은 유지)",
              "- 좌표:" not in no_p and "## 주변 그림" in no_p)
    finally:
        brains.OBS_ASCII, brains.OBS_POS = sa, sp


def prompt_checks():
    obs, bot = fresh_obs()
    roster = [dict(bot, name="두란")]
    got = {}

    def cap_menu(prompt, model="haiku"):
        got["m"] = prompt
        return '{"choice": 1, "reason": "x", "say": ""}'

    def cap_free(prompt, model="haiku"):
        got["f"] = prompt
        return '{"type": "search", "reason": "x", "say": ""}'

    save_menu = brains.MENU
    try:
        brains.MENU = True
        brains._call_claude = cap_menu
        brains.claude_brain(obs, "1", bot, roster)
        brains.MENU = False
        brains._call_claude = cap_free
        brains.claude_brain(obs, "1", bot, roster)
    finally:
        brains.MENU = save_menu
    m, f = got["m"], got["f"]
    check("⑦ 메뉴판: obs JSON 덤프 부재(```json 없음)", "```json" not in m)
    check("⑦ 메뉴판: 번호 목록 존재", "## 이번 턴 선택지" in m
          and re.search(r"^1\. ", m, re.M) is not None)
    check("⑦ 메뉴판: 문장 obs 존재(상태·시야 섹션)",
          "## 네 상태" in m and "## 지금 보이는 것" in m)
    check("⑦ 자유서술판: obs JSON 덤프 부재 + 선택지 섹션 부재",
          "```json" not in f and "## 이번 턴 선택지" not in f)


def main():
    print("== obs wire 직렬화(D17-3·D17-4) 검증 ==")
    st = sweep()
    v = st["views"]
    check("① 순수성: obs 무변형 (%d뷰)" % v, st["mutate"] == 0)
    check("① 결정론: 같은 obs → 같은 문장", st["det"] == v)
    check("② 전수성: 지칭 대상 전부 문장에 등장(불일치 %d)" % st["census"],
          st["census"] == 0)
    check("③ 실전 폴백 0 (last %d회·장부 %d회 표본 포함)" % (st["last_n"], st["known_n"]),
          st["fallback"] == 0 and st["last_n"] >= 100 and st["known_n"] >= 100)
    check("⑤ 시야-온리: concealed 몹 id 문장 부재(위반 %d)" % st["hidden"],
          st["hidden"] == 0)
    print("   (표본: %d뷰, 목격 렌더 %d회)" % (v, st["wit"]))
    synth_checks()
    switch_checks()
    prompt_checks()
    print("=" * 44)
    if C.failed:
        print("RESULT: %d FAIL" % C.failed)
        raise SystemExit(1)
    print("RESULT: ALL PASS — wire 직렬화(문장형 obs·스위치) 계약 건전")


if __name__ == "__main__":
    main()
