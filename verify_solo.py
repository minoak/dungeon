# -*- coding: utf-8 -*-
"""솔로 판(2026-07-29 파트너 발제) 검증 — 30번째 게이트.

왜: 파티 판에서 follow 가 결정의 36~39%를 먹었고 궁수 피른은 **51결정 중 34가 follow**
(explore 0·search 0)였다. 시트에 "아직 안 본 게 너무 많다 — 다 보고 나간다"고 저작된
캐릭터가 51번 중 34번 남의 뒤를 따라간 것. 원인은 프롬프트가 아니라 규칙에 있었다 —
승리 조건이 '전원이 계단 반경에 모이기'라 **뭉치는 게 규칙상 최적해**였다.

그래서 이 판은 파티라는 전제 자체를 뺀다: 셋은 서로 모르는 별개의 인물로 흩어져 출발하고,
각자 계단에 닿으면 혼자 내려간다. 마주친 뒤는 자유 — 동행하든 갈라서든 엔진이 규정하지
않는다(말·hail 은 그대로 열려 있다). 공유 던전(월드 러너)에서 남의 에이전트와 마주치는
상황과 같은 모양이라, 여기서 잰 것이 그대로 쓰인다.

⚠️ 왜 게이트인가 — 이건 물리다. 배치·명단·승리 조건은 판을 돌려 관찰할 게 아니라 0콜로
직접 찌른다(2026-07-26 합의: 물리=게이트, 판단=프로브 소수).

게이트:
  ① 스위치 기본 꺼짐 — 켜지 않은 판의 비트가 종전과 동일(기존 29종의 전제)
  ② 흩어져 출발 — 솔로는 서로 SOLO_APART 이상, 파티는 cluster 이내
  ③ obs 에 party 명단이 없다 — 남남은 서로 몇이고 누가 살았는지 모른다
  ④ 안 보이는 사람은 핑 불가 = D18 '파티 감각' 무효. **보이는 사람은 여전히 핑 가능**
     (눈에 보이면 지칭할 수 있어야 한다 — 시야-온리 원칙 그대로)
  ⑤ 혼자 하강 — 솔로는 exit, 파티는 wait_allies. 그리고 **남은 사람은 안 끌려간다**
  ⑥ 프롬프트 누출 차단 — 시트의 '- 동료:' 줄과 로스터 이름이 안 나간다.
     ⚠️ relationships 만 지우면 로스터가 이름을 되살린다(구현 중 실제로 났던 누출)
  ⑦ 시야에 든 남은 '낯선 사람' — 도감의 '낯선 짐승'과 같은 문법(모르는 건 모른다고 쓴다).
     파티 판은 '동료 카야'로 종전과 동일
  ⑧ 리모컨 메뉴에 '안 보이는 동료 찾아가기' 항목이 없다(선택지=행동의 전수 열거라 여기 남으면
     메뉴엔 떴는데 엔진이 거부하는 거짓말이 된다)
  ⑨ party_solo.json = party.json 과 relationships 만 다르다(그 외가 다르면 판 비교가 깨진다)
(기존 verify 29종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""            # 도감 영속 차단(게이트 격리 원칙)

import json                                          # noqa: E402
import itertools                                     # noqa: E402
import dungeon_gm as G                               # noqa: E402
import brains                                        # noqa: E402
import show_runner as R                              # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


SHEETS = R.load_party("party.json")
CHARS = sorted(SHEETS)


def stage(solo, sheets=None, w=80, h=30):
    """같은 시드·같은 맵에서 solo 만 갈아 끼운 판 — 차이가 스위치 하나로 좁혀진다."""
    sheets = sheets or SHEETS
    d = G.Dungeon(seed=7, w=w, h=h, n_monsters=7, n_traps=4, n_lurkers=2,
                  n_potions=1, scan=True, loops=True, solo=solo)
    bots = []
    for c in sorted(sheets):
        bots.append(G.spawn(d, c, bots, sheet=sheets[c], apart=solo))
    return d, bots


def pairs(bots):
    return [abs(a['x'] - b['x']) + abs(a['y'] - b['y'])
            for a, b in itertools.combinations(bots, 2)]


print("=== 솔로 판(DUNGEON_SOLO) 검증 — 30번째 게이트 ===\n")

# ── ① 기본 꺼짐 ────────────────────────────────────────────────────────────
print("① 스위치 기본 꺼짐")
d0 = G.Dungeon(seed=7, w=40, h=16)
check("① Dungeon(solo=) 기본 False", d0.solo is False)
check("① spawn(apart=) 기본 꺼짐 — 인자 없이 부르면 종전 배치",
      G.spawn.__defaults__[-1] is False)
check("① 러너 DUNGEON_SOLO 기본 0", R.SOLO_ON is False)

# ── ② 흩어져 출발 ─────────────────────────────────────────────────────────
print("\n② 흩어져 출발")
d_s, b_s = stage(True)
d_p, b_p = stage(False)
gap = max(G.SOLO_APART, (80 + 30) // 5)
check("② 솔로: 서로 SOLO_APART 이상 (실측 %s, 요구 %d)" % (pairs(b_s), gap),
      all(g >= gap for g in pairs(b_s)))
check("② 파티: 종전대로 곁에 (실측 %s)" % (pairs(b_p),),
      all(g <= 4 for g in pairs(b_p)))
check("② 솔로도 출구에서는 멀다(즉시 탈출 방지는 유지)",
      all(abs(b['x'] - d_s.exit[0]) + abs(b['y'] - d_s.exit[1]) >= 8 for b in b_s))
# 좁은 맵에서 간격을 못 벌리면 base 로 추락하지 않고 단계적으로 완화되어야 한다
d_n, b_n = stage(True, w=30, h=12)
check("② 좁은 맵도 배치가 성립한다(완화 사다리 — 빈 후보로 죽지 않는다)", len(b_n) == 3)

# ── ③④ 명단과 핑 ─────────────────────────────────────────────────────────
print("\n③④ 서로를 모른다")
o_s = d_s.view(b_s[0], b_s)
o_p = d_p.view(b_p[0], b_p)
check("③ 솔로 obs 에 party 명단 없음", o_s['party'] == [])
check("③ 파티 obs 는 종전대로 명단 있음", len(o_p['party']) == 2)
check("④ 솔로: 안 보이는 사람 핑 불가(D18 파티 감각 무효)",
      not any(str(t).startswith('b') for t in brains._valid_targets(o_s)))
check("④ 파티: 보이는 동료만 핑 가능(D18 개정 09-06 — 시야 밖 동료는 사라진 것, 파티 감각 폐지)",
      brains._valid_targets(o_p) & {'b2', 'b3'} == {'b%s' % a['char'] for a in o_p['sights']['bots']})

# 보이는 사람은 솔로에서도 핑이 돼야 한다 — 눈에 보이는 걸 못 부르면 그건 다른 버그다
d_m, b_m = stage(True)
b_m[1]['x'], b_m[1]['y'] = b_m[0]['x'] + 1, b_m[0]['y']
o_m = d_m.view(b_m[0], b_m)
check("④ 솔로라도 **보이는** 사람은 핑 가능(시야-온리 원칙 그대로)",
      'b2' in brains._valid_targets(o_m))

# ── ⑤ 혼자 하강 ──────────────────────────────────────────────────────────
print("\n⑤ 혼자 하강")
for solo, want in ((True, 'exit'), (False, 'wait_allies')):
    d, bots = stage(solo)
    bots[0]['x'], bots[0]['y'] = d.exit
    res = d.act(bots[0], {'type': 'interact', 'target': 'exit'}, bots)
    check("⑤ solo=%-5s → %s" % (solo, want), res.get('result') == want)
    if solo:
        check("⑤ 혼자 내려간 판에서 남은 둘은 안 끌려간다(전부 관찰의 전제)",
              [b['won'] for b in bots] == [True, False, False])
        check("⑤ 하강 보고의 party 는 자기 하나", res.get('party') == [bots[0]['char']])
        # ⚠️ 결과 보고 오역 회귀 그물 — 이 판의 오랜 병(D19 문 핑·lost 정직화와 같은 계보).
        #    첫 스모크에서 실제로 "다 모였다 — 함께 하강!!"이 혼자 나가는 장면에 찍혔다.
        import show_runner as _R                      # noqa: E402  (지연 import — 게이트 격리)
        spec = _R.act_summary({'type': 'interact', **res}) if hasattr(_R, 'act_summary') else ''
        prose = brains._last_prose({'type': 'interact', **res})
        check("⑤ 관전 문구가 없던 일행을 지어내지 않는다",
              '모였다' not in str(spec) and '함께' not in str(spec))
        check("⑤ 캐릭터가 읽는 문장도 마찬가지(더 중요 — 두뇌 입력이다)",
              '모여서' not in prose and '함께' not in prose)

# ── ⑥⑦ 프롬프트 누출 ─────────────────────────────────────────────────────
print("\n⑥⑦ 프롬프트 누출 차단")
SOLO_SHEETS = R.load_party("party_solo.json")
sheet_solo = brains._sheet(b_s[0], [])                 # 솔로 = 로스터 없음
sheet_party = brains._sheet(b_p[0], b_p)
check("⑥ 솔로 시트에 '- 동료:' 줄 없음", "- 동료:" not in sheet_solo)
check("⑥ 솔로 시트에 다른 인물 이름이 안 나감",
      not any(n in sheet_solo for n in ("카야", "피른")))
check("⑥ 파티 시트는 종전대로 동료 줄이 있다", "- 동료:" in sheet_party)
check("⑥ 솔로 시트에도 자기 정체성은 온전하다(목표·말투)",
      "목표:" in sheet_solo and "말투:" in sheet_solo)

wire_solo = brains._wire(o_m, {})                       # names 빈 것 = 솔로 경로
nms = {x['char']: x.get('name') for x in b_p}
d_pv, b_pv = stage(False)
b_pv[1]['x'], b_pv[1]['y'] = b_pv[0]['x'] + 1, b_pv[0]['y']
wire_party = brains._wire(d_pv.view(b_pv[0], b_pv), nms)
check("⑦ 솔로: 시야에 든 남은 '낯선 사람'", "낯선 사람(봇2)" in wire_solo)
check("⑦ 솔로: 이름이 안 샌다", "카야" not in wire_solo)
check("⑦ 솔로: '동료 동료' 같은 깨진 표기 없음", "동료 동료" not in wire_solo)
check("⑦ 파티: 종전대로 '동료 카야'", "동료 카야(봇2)" in wire_party)

# ── ⑧ 리모컨 메뉴 ────────────────────────────────────────────────────────
print("\n⑧ 리모컨 메뉴 전수성")
unseen_solo = [t for t in (o_s.get('options') or [])
               if str(t.get('target', '')).startswith('b')]
unseen_party = [t for t in (o_p.get('options') or [])
                if str(t.get('target', '')).startswith('b')]
check("⑧ 솔로 메뉴에 동료 항목 없음(엔진이 거부할 선택지를 띄우지 않는다)",
      unseen_solo == [])
check("⑧ 파티 메뉴에는 종전대로 있다", len(unseen_party) > 0)

# 계단 라벨이 규칙을 말한다 — 그리고 '고르라고 열거된 선택지 본문'이라 프롬프트 설명문보다
# 무겁게 읽힌다. 프롬프트만 고치고 여기를 놓치면 엔진은 혼자 내려보내면서 메뉴는 모이라고
# 한다(07-29 실측이 딱 이 모순이었다).
_lab = {}
for solo in (True, False):
    d, bots = stage(solo)
    bots[0]['x'], bots[0]['y'] = d.exit
    o = d.view(bots[0], bots)
    _lab[solo] = next((t['label'] for t in (o.get('options') or [])
                       if t.get('target') == 'exit' and t.get('type') == 'interact'), '')
check("⑧ 솔로 계단 라벨이 파티 규칙을 말하지 않는다 (%r)" % _lab[True][:40],
      _lab[True] and '전원' not in _lab[True] and '모여야' not in _lab[True])
check("⑧ 솔로 계단 라벨이 혼자임을 말한다", '혼자' in _lab[True])
check("⑧ 파티 계단 라벨은 파티 규칙을 말한다(모임+의사 — 08-09 개정)",
      '모이고' in _lab[False] and '하던 일이 없어야' in _lab[False])

# 이름 누출 — brains 의 wire 는 '낯선 사람'이라 쓰는데 엔진 메뉴만 '카야(봇2)'라고 부르면
# 두 층이 서로 다른 말을 한다. 선택지 라벨이 더 무겁게 읽히므로 그쪽이 이긴다.
_meet = {}
for solo in (True, False):
    d, bots = stage(solo)
    bots[1]['x'], bots[1]['y'] = bots[0]['x'] + 1, bots[0]['y']
    o = d.view(bots[0], bots)
    _meet[solo] = " | ".join(t['label'] for t in (o.get('options') or [])
                             if str(t.get('target', '')).startswith('b'))
check("⑧ 마주친 남의 메뉴 라벨에 이름이 안 샌다 (%r)" % _meet[True][:46],
      _meet[True] and '카야' not in _meet[True] and '낯선 사람' in _meet[True])
check("⑧ 파티 판은 종전대로 이름으로 부른다", '카야' in _meet[False])
check("⑧ 그래도 id 는 남는다 — 보이면 지칭할 수 있어야 핑을 건다",
      '봇2' in _meet[True])

# ── ⑨ 시트 파일 대조 ─────────────────────────────────────────────────────
print("\n⑨ party_solo.json = party.json - relationships")
raw_p = json.load(open("party.json", encoding="utf-8"))
raw_s = json.load(open("party_solo.json", encoding="utf-8"))
keys_p = {k for k in raw_p if not k.startswith('_')}
keys_s = {k for k in raw_s if not k.startswith('_')}
check("⑨ 같은 인물 구성", keys_p == keys_s)
diffs = []
for k in sorted(keys_p):
    a = {kk: vv for kk, vv in raw_p[k].items() if kk != 'relationships'}
    b = {kk: vv for kk, vv in raw_s[k].items() if kk != 'relationships'}
    if a != b:
        diffs.append(k)
check("⑨ relationships 말고는 한 글자도 안 다르다(저작물 무수정 — 다르면 판 비교가 깨진다)",
      not diffs)
check("⑨ 솔로 시트엔 relationships 가 아예 없다",
      all('relationships' not in raw_s[k] for k in keys_s))
check("⑨ 파티 시트엔 그대로 있다",
      all('relationships' in raw_p[k] for k in keys_p))

# ── ⑪ 프롬프트 갈림 ──────────────────────────────────────────────────────
# 첫 솔로 판이 가르쳐 준 것: 엔진에서 파티를 없애도 **프롬프트가 규칙을 거짓으로 말하면**
# 캐릭터는 그 거짓을 따른다. 두란은 계단을 t156 에 확보하고도 "전원이 모여야 하강"이라는
# 프롬프트 문장 때문에 t210 까지 54틱을 없는 동료를 찾아다녔다. 역할극이 아니라 규칙 준수였다.
# 세계가 바뀌면 세계 설명서도 바뀌어야 한다 — 그걸 사람이 기억하는 대신 여기서 지킨다.
print("\n⑪ 프롬프트 갈림(PARTY/SOLO 마커)")
FALSE_IN_SOLO = ("모여야", "함께 내려간다", "파티가 함께", "동료와 의논",
                 "파티 안에서", "파티 감각", "데리러 가라")
#            ↑ 낱말이 아니라 **규칙 진술**이어야 한다 — '데리러' 만 보면 솔로의 정당한 문장
#              "데리러 갈 사람도 없다" 가 걸려 헛경보가 난다(초안이 실제로 그랬다)
PAIRS = (("메뉴", brains.MENU_PROMPT, brains.MENU_PROMPT_SOLO),
         ("자유서술", brains.ADV_PROMPT, brains.ADV_PROMPT_SOLO),
         ("사교", brains.SOCIAL_PROMPT, brains.SOCIAL_PROMPT_SOLO))
for _nm, _party, _solo in PAIRS:
    check("⑪ %s: 두 판본 다 마커 잔재 없음" % _nm,
          not any(m in t for t in (_party, _solo)
                  for m in ("<!--PARTY", "<!--SOLO", "<!--/")))
    check("⑪ %s: 솔로 판본에 파티 규칙 진술이 없다" % _nm,
          not [w for w in FALSE_IN_SOLO if w in _solo])
    check("⑪ %s: 두 판본이 실제로 다르다(갈림이 살아 있다)" % _nm,
          bool(_party) and _party != _solo)
check("⑪ 파티 판본 무손상 — 계단 규칙·동료 절이 그대로 있다",
      "파티가 함께" in brains.MENU_PROMPT and "## 동료" in brains.MENU_PROMPT)
check("⑪ 솔로 판본이 혼자임을 명시한다",
      "혼자" in brains.MENU_PROMPT_SOLO and "## 혼자다" in brains.MENU_PROMPT_SOLO)
# 상수만 비교하면 헛돈다(자기 자신과의 비교) — 실제로 조립돼 나가는 프롬프트를 붙잡는다.
_cap = {}
_orig_call = brains._call_claude
brains._call_claude = lambda p, m="haiku": (_cap.update(p=p), ("", "stub"))[1]
try:
    brains.claude_brain(o_s, '1', b_s[0], [], True)
    _solo_prompt = _cap.get('p', '')
    brains.claude_brain(o_p, '1', b_p[0], b_p, False)
    _party_prompt = _cap.get('p', '')
finally:
    brains._call_claude = _orig_call            # 스텁 원복 — 안 되돌리면 뒤 체크가 오염된다
check("⑪ 실제로 나가는 솔로 프롬프트에 '## 혼자다' 가 있고 파티 규칙은 없다",
      "## 혼자다" in _solo_prompt and "모여야" not in _solo_prompt)
check("⑪ 실제로 나가는 파티 프롬프트는 종전 그대로",
      "## 동료" in _party_prompt and "파티가 함께" in _party_prompt)

# ── 결정론 ───────────────────────────────────────────────────────────────
print("\n⑩ 결정론")
a1, a2 = stage(True)[1], stage(True)[1]
check("⑩ 같은 시드 → 같은 배치(리플레이 성립)",
      [(b['char'], b['x'], b['y']) for b in a1] == [(b['char'], b['x'], b['y']) for b in a2])

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_solo (솔로 판: 흩어져 출발·서로 모름·혼자 하강)")
