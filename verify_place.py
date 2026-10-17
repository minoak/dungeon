# -*- coding: utf-8 -*-
"""p0.5.23 현재 위치 줄 + 마을 규칙은 지침으로(DECISIONS 2026-10-17 '현재 위치 줄 정리') — 헤들리스 검증. LLM 0콜.
게이트:
  ① 낱말: prompts/world/place.md = {head 현재 위치 · town 마을 · dungeon 던전 · floor 지하 {n}층 · zone 구역} · 검증기가 칸 빠짐·남는 칸·floor 의 {n} 없음·다른 중괄호를 한 번에 거절 ·
     _place_lines·_town_kind·_town_guide 의 코드엔 한글 글자가 없다(문장은 말 파일·지침 파일에)
  ② 위치 줄('네 상태' 절 맨 앞): 실제 마을(구역 있음 — '현재 위치: 마을 > <구역>' + '구역: <특징>') · 옛 손그림 마을(구역 없음 — '현재 위치: 마을') · 던전 1·3층
     ('현재 위치: 던전 > 지하 N층') · HP 줄에 층 없음 · 옛 마을 줄('여기는 마을이다'·'지금 있는 곳')·'— 지금 N층' 없음 · 메뉴형도 같은 줄 · 관측 dict 는 그대로(새 칸 없음)
  ③ 지침 갈래: 마을 규칙 세 갈래(구역 시야 · 구역 청각 · 전체 가시)가 옛 마을 줄의 뜻을 그대로 든다 · 마을에 있는 판단에만 그 갈래 하나가 '네가 아는 세계' 절 끝에 한 번 ·
     다른 갈래·던전·마을 없는 판의 지침은 v0.5.22 바이트 그대로(블록만 걷은 파일) · 옛 메뉴형·자유서술 지침(바이트 보존 백업)도 세계 절 끝에 · 혼자 판도 ·
     완성 프롬프트(claude_brain — 조합형·메뉴형·자유서술)에 규칙은 한 번, 관측엔 없다 · 바꿔 끼운 지침(patch)에도 붙는다 ·
     p0523b 세계 절이 없는 사교 지침엔 세계 절(조합형 지침의 머리 + 그 갈래 한 줄)을 첫 절 앞에 — 사교 콜(social_all) 완성 프롬프트도
  ④ 옛 판 이어가기: 실제 옛 스냅샷(fixtures/snapshot_v052 — v0.5.2 코드가 쓴 마을 판)을 지금 로더로 올려 그린 관측 = 새 위치 줄 · 지침은 구역 시야 갈래
  ⑤ 배선: _run_gates.sh · VERSION 0.5.23 이상 · PATCH_NOTES · STREAM_FORMAT · check_words
"""
import ast
import inspect
import io
import json
import os
import re
import shutil
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_place_")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_SEED="7", DUNGEON_MONSTERS="1",
                  DUNGEON_TRAPS="0", DUNGEON_LURKERS="0", DUNGEON_BESTIARY_FILE="", DUNGEON_STEP_DELAY="0",
                  DUNGEON_PARTY_FILE="/nonexistent", DUNGEON_STATE_DIR=os.path.join(TMP, "state"), DUNGEON_BRAIN_BACKEND="dummy",
                  DUNGEON_ACTION_MODE="compose")
for k in ("DUNGEON_RESUME", "DUNGEON_RUNS_DIR", "DUNGEON_TOWN", "DUNGEON_SOLO", "DUNGEON_DEPTHS"):
    os.environ.pop(k, None)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import brains                                        # noqa: E402
SENT = []
brains._call_claude = lambda prompt, model="haiku": (SENT.append(prompt), ("", None))[1]   # 0콜 — 빈 응답이면 dummy 폴백(사교 콜은 (글, 이유) 를 푼다)
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import show_runner as R                              # noqa: E402
import snapshot                                      # noqa: E402
import words as WD                                   # noqa: E402
R.STEP_DELAY = 0


class C:
    failed = 0
    n = 0


def check(name, ok, detail=""):
    C.n += 1
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:400]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with io.open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


def status(w):
    """완성 관측 글 → '네 상태' 절의 줄들(빈 줄 앞까지)."""
    return w.split("## 네 상태\n")[1].split("\n\n")[0].split("\n")


def mkbot(char, x, y):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14, 'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0, 'search_r': 1,
            'job': '전사', 'sex': '남', 'persona': '', 'bag': 0, 'potions': 0, 'weapon': None, 'armor': None,
            'alive': True, 'won': False, 'order': None, 'path': [], 'aware_of': set()}


OLD_TOWN_BITS = ("여기는 마을이다", "지금 있는 곳", "위험한 것이 없", "한눈에", "구역 안뿐", "같은 구역 안에서만")

# ─────────────────────────────────────────────────────────────────────────────
print("── ① 낱말")
PW = ENT.place_words()
check("① prompts/world/place.md = 현재 위치 · 마을 · 던전 · 지하 {n}층 · 구역(entities.PLACE_WORD_KEYS 다섯)",
      PW == {"head": "현재 위치", "town": "마을", "dungeon": "던전", "floor": "지하 {n}층", "zone": "구역"} and tuple(PW) == ENT.PLACE_WORD_KEYS, PW)
WR = os.path.join(TMP, "words")
shutil.copytree(WD.WORDS_ROOT, WR)
with io.open(os.path.join(WR, "place.md"), encoding="utf-8") as f:
    good_md = f.read()
bad_md = (good_md.replace("## `zone` — 구역 특징 줄의 머리\n구역\n", "## `where` — 모르는 칸\n어디\n")
          .replace("지하 {n}층", "지하 층").replace("## `head` — 줄 머리\n현재 위치", "## `head` — 줄 머리\n현재 {pos}"))
with io.open(os.path.join(WR, "place.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write(bad_md)
try:
    ENT.read(words_root=WR)
    msg = ""
except ENT.EntityError as e:
    msg = str(e)
WANT1 = ("prompts/world/place.md: 칸 `zone` 가 없다", "prompts/world/place.md: 칸 `where` 는 위치 낱말이 아니다",
         "prompts/world/place.md: `floor` 칸에 {n} 자리가 있어야 한다", "prompts/world/place.md: `head` 칸에 쓸 수 있는 중괄호 자리는 없다")
check("① 검증기: 칸 빠짐 · 남는 칸 · floor 의 {n} 없음 · 다른 칸의 중괄호를 한 번에 거절(정의 읽기가 막힌다 — 게임이 안 뜬다)",
      all(w in msg for w in WANT1), [w for w in WANT1 if w not in msg] or msg[:300])
check("① 정본 폴더는 그대로 읽힌다", bool(ENT.reload()) and ENT.place_words() == PW)


def hangul_literals(fn):
    """함수 본문의 문자열 상수 중 한글이 든 것(독스트링 제외) — 문장은 말 파일·지침 파일에 있어야 한다."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    body = tree.body[0].body
    doc = body[0] if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) else None
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and re.search(r"[가-힣]", n.value) and (doc is None or n is not doc.value)]


hard = {f.__name__: hangul_literals(f) for f in (brains._place_lines, brains._town_kind, brains._town_guide)}
check("① 하드코딩 없음: _place_lines·_town_kind·_town_guide 의 코드에 한글 문자열이 없다(낱말 = place.md · 규칙 = 지침 TOWN 블록 · 절 머리 = _WORLD_HEAD)",
      not any(hard.values()), hard)

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 위치 줄")
dT, sT = R.build_town(apart=True)
aT = mkbot("1", *sT["1"])
oT = dT.view(aT, [aT])
wT = brains._wire(oT, {"1": "두란"}, compose=True)
stT = status(wT)
check("② 실제 마을(구역 있음): 절 맨 앞 '- 현재 위치: 마을 > <구역>' · 다음 줄 '- 구역: <특징>'(정의 문장 그대로) · 그다음 HP 줄(층 없음)",
      oT.get("town_zone") and oT.get("town_zone_about")
      and stT[:2] == ["- 현재 위치: 마을 > %s" % oT["town_zone"], "- 구역: %s" % oT["town_zone_about"]]
      and stT[2].startswith("- HP ") and "층" not in stT[2], stT[:3])
check("② 옛 마을 줄·문장이 관측에 없다(여기는 마을이다 · 지금 있는 곳 · 마을 규칙 문장) · '— 지금 N층' 없음",
      not any(t in wT for t in OLD_TOWN_BITS) and not re.search(r"— 지금 \d+층", wT), [t for t in OLD_TOWN_BITS if t in wT])
dV, sV = R.build_town(os.path.join(R.HERE, "town-v0.json"))
aV = mkbot("1", *sV["1"])
oV = dV.view(aV, [aV])
stV = status(brains._wire(oV, {"1": "두란"}, compose=True))
check("② 옛 손그림 마을(구역 이름 없음): '- 현재 위치: 마을' 한 줄 · 구역 줄 없음",
      oV.get("town") and not oV.get("town_zone") and stV[0] == "- 현재 위치: 마을" and not stV[1].startswith("- 구역") and stV[1].startswith("- HP "), stV[:2])
dD = G.Dungeon(seed=7, w=40, h=16)
aD = G.spawn(dD, "1", [])
rows = {}
for dep in (1, 3):
    dD.depth = dep
    oD = dD.view(aD, [aD])
    for compose in (True, False):
        rows[(dep, compose)] = status(brains._wire(oD, {"1": "두란"}, compose=compose))[:2]
check("② 던전: '- 현재 위치: 던전 > 지하 1층' · 3층이면 '지하 3층' · 바로 다음이 HP 줄(층 없음) · 메뉴형도 같은 줄",
      all(r[0] == "- 현재 위치: 던전 > 지하 %d층" % dep and r[1].startswith("- HP ") and "층" not in r[1] for (dep, _c), r in rows.items()), rows)
wM = brains._wire(oT, {"1": "두란"}, compose=False)
check("② 메뉴형 마을도 같은 위치 줄 · 옛 마을 줄 없음", status(wM)[:2] == stT[:2] and not any(t in wM for t in OLD_TOWN_BITS), status(wM)[:2])
DUN_RULE = "- 여기는 던전이다 — 원정에는 제한 시간이 있다. HP가 0이 되면 이번 원정에서 죽는다."
check("② 원정의 규칙 줄('여기는 던전이다 …')은 옛 그대로 — 조합형 던전에만 · 마을(조합형·메뉴형)·메뉴형 던전엔 없다",
      DUN_RULE in status(brains._wire(oD, {"1": "두란"}, compose=True)) and DUN_RULE not in brains._wire(oD, {"1": "두란"}, compose=False)
      and "여기는 던전이다" not in wT and "여기는 던전이다" not in wM)
check("② 관측 dict 는 그대로 — 위치 줄의 재료는 옛 칸(town·town_zone·town_zone_about·depth)뿐 · 새 칸 없음 · 미등록 키 없음",
      not ({"place", "location", "town_rule"} & set(oT)) and not brains.unwired_keys(oT) and not brains.unwired_keys(oV)
      and "## 그 밖의 정보" not in wT)

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ 지침 갈래")
TR = brains.TOWN_RULES
MEAN = {"zone": ("위험한 것이 없다", "어디에 어떤 건물이 있는지는 안다", "보이고 들리는 것은 지금 서 있는 구역 안뿐", "다른 구역에 누가 있고 무슨 일이 있는지는 가 봐야 안다"),
        "hear": ("위험한 것이 없다", "길과 건물이 어디 있는지는 다 안다", "사람과 목소리는 같은 구역 안에서만 보이고 들린다"),
        "all": ("위험한 것이 없다", "마을 전체가 한눈에 보인다")}
check("③ 마을 규칙 세 갈래(구역 시야 zone · 구역 청각 hear · 전체 가시 all) — 옛 마을 줄의 뜻 그대로(갈래별 구절) · 한 줄 '- ' 항목 · 지시·권유 꼴 없음",
      set(TR) == set(brains.TOWN_KINDS) == set(MEAN) and all(all(p in TR[k] for p in MEAN[k]) for k in MEAN)
      and all(TR[k].startswith("- ") and "\n" not in TR[k] and not G.NE.order_problems(TR[k][2:]) for k in TR), TR)
base = {"hp": 10, "maxhp": 14, "inventory": 0, "depth": 1}
OBS = {"zone": dict(base, depth=0, town=True, town_sight="zone", town_hear="zone"), "hear": dict(base, depth=0, town=True, town_hear="zone"),
       "all": dict(base, depth=0, town=True)}
check("③ 갈래 고르기 = 옛 마을 줄과 같은 순서(구역 시야 → 구역 청각 → 전체 가시) · 마을 밖은 없음",
      {k: brains._town_kind(o) for k, o in OBS.items()} == {"zone": "zone", "hear": "hear", "all": "all"}
      and brains._town_kind(base) is None and brains._town_kind(dict(base, town_sight="zone", town_hear="zone")) is None)
raw_adv = src("prompts", "adventurer_prompt.md")
stripped = brains._TOWN_BLOCK.sub("", raw_adv)
check("③ 지침 본문(brains.COMPOSE_PROMPT)엔 규칙·표식이 없다 = 파일에서 TOWN 블록만 걷은 것(파티·혼자) · 블록은 세 갈래 하나씩",
      brains.COMPOSE_PROMPT == brains._strip_comments(brains._variant(stripped, False))
      and brains.COMPOSE_PROMPT_SOLO == brains._strip_comments(brains._variant(stripped, True))
      and not any(TR[k] in brains.COMPOSE_PROMPT + brains.COMPOSE_PROMPT_SOLO for k in TR) and "TOWN" not in brains.COMPOSE_PROMPT
      and sorted(m.group(1) for m in brains._TOWN_BLOCK.finditer(raw_adv)) == sorted(brains.TOWN_KINDS))
sec_end = lambda g: g.index("\n\n## 행동 사전")   # noqa: E731
placed = {}
for k, o in OBS.items():
    for solo in (False, True):
        base_g = brains.COMPOSE_PROMPT_SOLO if solo else brains.COMPOSE_PROMPT
        g = brains._town_guide(base_g, o)
        others = [x for x in TR if x != k]
        placed[(k, solo)] = (g.count(TR[k]) == 1 and not any(TR[x] in g for x in others)
                             and g[:sec_end(g)].endswith("\n" + TR[k]) and g.index("## 네가 아는 세계") < g.index(TR[k])
                             and g.replace("\n" + TR[k], "", 1) == base_g)
check("③ 마을에 있는 판단: 그 갈래 한 줄만 '네가 아는 세계' 절 끝(행동 사전 앞)에 한 번 — 다른 갈래 없음 · 그 줄을 빼면 지침 본문 그대로 · 혼자 판도",
      all(placed.values()), placed)
check("③ 던전(마을 밖)의 지침은 지침 본문 그대로(같은 문자열)",
      brains._town_guide(brains.COMPOSE_PROMPT, base) == brains.COMPOSE_PROMPT and brains._town_guide(brains.MENU_PROMPT, base) == brains.MENU_PROMPT)
leg = {}
for nm_, txt, head, nxt in (("메뉴형", brains.MENU_PROMPT, "## 네가 아는 것과 모르는 것", "\n\n## 동료"),
                            ("메뉴형 혼자", brains.MENU_PROMPT_SOLO, "## 네가 아는 것과 모르는 것", "\n\n## 혼자다"),
                            ("자유서술", brains.ADV_PROMPT, "## 세계의 물리", "\n\n## 할 수 있는 행동")):
    g = brains._town_guide(txt, OBS["hear"])
    i = g.find(head)
    e = g.find(nxt, i) if i >= 0 else -1
    leg[nm_] = g.count(TR["hear"]) == 1 and 0 <= i < e and g[i:e].endswith("\n" + TR["hear"])
check("③ 옛 메뉴형·자유서술 지침(바이트 보존 백업 — 파일은 그대로)도 세계 절 끝(다음 절 앞)에 한 번", all(leg.values()), leg)
check("③ 옛 지침 백업 파일은 손대지 않았다(SHA256.json 그대로)",
      all(__import__("hashlib").sha256(open(os.path.join(HERE, "prompts", "legacy", "2026-09-10", fn), "rb").read()).hexdigest() == h
          for fn, h in json.loads(src("prompts", "legacy", "2026-09-10", "SHA256.json")).items()))
soc = brains.SOCIAL_PROMPT
check("③ p0523b 세계 절이 없는 지침(사교 콜): 조합형 지침의 세계 절 머리로 절 하나를 지어 첫 '## ' 절 앞에 — 그 갈래 한 줄 · 마을 밖은 그대로 · 혼자 판도",
      brains.WORLD_HEAD_LINE == "## 네가 아는 세계" and soc and "## 네가 아는 세계" not in soc
      and all(brains._town_guide(s_, OBS[k]) == s_[:s_.index("\n## ") + 1] + brains.WORLD_HEAD_LINE + "\n\n" + TR[k] + "\n\n" + s_[s_.index("\n## ") + 1:]
              for s_ in (soc, brains.SOCIAL_PROMPT_SOLO) for k in TR)
      and brains._town_guide(soc, base) == soc)
# 완성 프롬프트(claude_brain) — 조합형·메뉴형 · 마을·던전
kT = brains._town_kind(oT)
full = {}
for mode in ("compose", "menu", "free"):
    c0, m0 = brains.COMPOSE, brains.MENU
    brains.COMPOSE, brains.MENU = mode == "compose", mode == "menu"
    try:
        for label, o, b in (("town", oT, aT), ("dungeon", dD.view(aD, [aD]), aD)):
            del SENT[:]
            brains.claude_brain(o, "1", bot=b, roster=[b])
            full[(mode, label)] = SENT[-1] if SENT else ""
    finally:
        brains.COMPOSE, brains.MENU = c0, m0
fp = {k: (v.count(TR[kT]), sum(v.count(TR[x]) for x in TR if x != kT), v.count("- 현재 위치: "),
          any(t in v[v.index("## 네 상태"):] for t in OLD_TOWN_BITS) if "## 네 상태" in v else None) for k, v in full.items()}
check("③ 완성 프롬프트: 마을이면 그 갈래 규칙 한 번(%s) · 다른 갈래 0 · 위치 줄 한 번 · '네 상태' 절부터 끝까지 마을 규칙 없음 · 던전이면 규칙 0 — 조합형·메뉴형·자유서술" % kT,
      kT in brains.TOWN_KINDS and all(fp[(m_, "town")] == (1, 0, 1, False) and fp[(m_, "dungeon")] == (0, 0, 1, False) for m_ in ("compose", "menu", "free")), fp)
# p0523b 사교 콜(social_all — 기본 꺼짐) 완성 프롬프트: 옛 관측 마을 줄이 들던 규칙을 지침 쪽에서 받는다
soc_full = {}
for label, d_, b_ in (("town", dT, aT), ("dungeon", dD, aD)):
    s0, o0_, h0 = getattr(d_, "social", False), b_.get("order"), b_.get("hailed")
    d_.social, b_["order"], b_["hailed"] = True, "explore", True
    try:
        del SENT[:]
        brains.social_all(d_, [b_], {})
        soc_full[label] = SENT[-1] if SENT else ""
    finally:
        d_.social, b_["order"], b_["hailed"] = s0, o0_, h0
st_ = soc_full.get("town", "")
check("③ p0523b 사교 콜 완성 프롬프트: 마을이면 세계 절(머리 + 그 갈래 한 줄)이 사교 지침의 첫 절 앞에 한 번 · '네 상태'엔 위치 줄 · 던전이면 사교 지침 그대로(규칙 0)",
      st_.count(TR[kT]) == 1 and (brains.WORLD_HEAD_LINE + "\n\n" + TR[kT] + "\n\n## ") in st_ and st_.index(TR[kT]) < st_.index("## 네 상태")
      and "- 현재 위치: 마을 > " in st_ and brains.SOCIAL_PROMPT in soc_full.get("dungeon", "")
      and not any(TR[x] in soc_full.get("dungeon", "") for x in TR), {k: len(v) for k, v in soc_full.items()})
patched = "## 네가 아는 세계\n\n- 시험 지침.\n\n## 끝\n"
check("③ 바꿔 끼운 지침(게이트·벤치의 patch)에도 같은 자리에 붙는다(지침 문자열을 부를 때 읽는다)",
      brains._town_guide(patched, OBS["all"]) == "## 네가 아는 세계\n\n- 시험 지침.\n" + TR["all"] + "\n\n## 끝\n")

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ 옛 판 이어가기")
S4 = os.path.join(TMP, "s4")
shutil.copytree(os.path.join(HERE, "fixtures", "snapshot_v052"), S4)
snap4, _m4 = snapshot.load(os.path.join(S4, "snapshot.pkl"))   # 리포 고정 자료(코드와 같은 신뢰 급 — fixtures README)
d4, bots4 = snap4["d"], snap4["bots"]
rows4 = []
for b in bots4:
    o = d4.view(b, bots4)
    st = status(brains._wire(o, {}, compose=True))
    rows4.append((st[:2], brains._town_kind(o), any(t in "\n".join(st) for t in OLD_TOWN_BITS)))
check("④ v0.5.2 마을 판 스냅샷을 지금 로더로 올려 그린 관측: 세 사람 모두 '현재 위치: 마을 > 번화가' + '구역: <특징>' · 옛 줄 없음 · 지침은 구역 시야 갈래",
      snap4["state_version"] == snapshot.STATE_VERSION and len(rows4) == 3
      and all(r[0][0] == "- 현재 위치: 마을 > 번화가" and r[0][1].startswith("- 구역: ") and r[1] == "zone" and not r[2] for r in rows4), rows4)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ 배선")
gates = src("_run_gates.sh")
check("⑤ _run_gates.sh 에 등록(낱말 경계) · VERSION 0.5.23 이상 · PATCH_NOTES 0.5.23 · STREAM_FORMAT(현재 위치·TOWN 블록) · check_words 가 위치 낱말을 센다",
      re.search(r"(?<![\w])verify_place(?![\w])", gates) is not None
      and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 23) and "## 0.5.23" in src("docs", "PATCH_NOTES.md")
      and "현재 위치" in src("STREAM_FORMAT.md") and "<!--TOWN:" in src("STREAM_FORMAT.md") and "PLACE_WORDS" in src("tools", "check_words.py"))

shutil.rmtree(TMP, ignore_errors=True)
print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    sys.exit(1)
print("ALL PASS — verify_place (p0.5.23 현재 위치 줄 + 마을 규칙은 지침으로: %d checks · 낱말·검증기·하드코딩 · 위치 줄(마을 구역 있음·없음·던전 층·메뉴형) · 지침 갈래(뜻·자리·한 번·옛 지침·완성 프롬프트) · 옛 판 이어가기 · 배선, 실 LLM 0콜)" % C.n)
