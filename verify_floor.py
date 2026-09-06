# -*- coding: utf-8 -*-
"""층 집계·결산(D40 ②, 2026-09-06 파트너 확정 "층이 끝나면 결산 — 시스템이 집계하고 캐릭터에게 추가") 검증 — 39번째 게이트. LLM 0콜.
사건 사전(dungeon_gm.EVENT_KINDS·event_tags) 하나로 자기 사건·목격 사건을 층 단위로 세고(bot['floor']), 층을 떠날 때
얼린다(floor_freeze → bot['floors']). 살(캐릭터 한 줄)은 다음 층 첫 결정에 `floor_line` 피기백(D26/D36 선례, 추가 콜 0).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판 = 집계 안 쌓임·obs 에 floor/floors 키 없음
  ② 자기 집계: 집계 여부 True 인 키만(걸음·이동 시작·도착 제외) · 조우 한 건 = 발견·함정·상태 각 +1 · 위급 +1(궤적 꺼도)
  ③ 목격 집계: _witness 를 지난 사실은 WITNESS_LABELS 로 w 에(당사자 제외)
  ④ obs.floor 형태 {since, turns, n, w, rooms} · 렌더 "## 이 층에서 지금까지" 꼬리표 ×N 내림차순 · 목격 줄
  ⑤ 결산: floor_freeze → {depth, t0, t1, n, w, line None, invite True} · 순수 함수(봇 무변경) · 이월 형태(러너 규칙 미러)
  ⑥ 초대: 첫 결정 렌더에 `floor_line` 안내 · 응답 floor_line → floors[-1].line(엔진 불가침 — 내용 안 읽음) · 초대 1회
     (다음 결정엔 안내 없음, 답이 없어도 닫힘) · 마을(0층)은 '마을'로 표기
  ⑦ 결정론: 같은 수순 두 번 = 같은 집계
(기존 verify 38종은 별도 실행.)
"""
import copy
import brains
import dungeon_gm as G
from dungeon_gm import Dungeon


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, hp=14):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': hp,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': [], 'last': None}


ROWS = ["############",
        "#1.2......>#",
        "############"]
NAMES = {'1': '두란', '2': '카야'}
ENC = {'char': '1', 'type': 'walk', 'target': '@3,3', 'result': 'encounter',
       'monsters': [{'kind': '고블린', 'id': 'm1'}, {'kind': '고블린', 'id': 'm2'}],
       'trap': {'name': '가시 함정', 'dmg': 2, 'status': '출혈'}, 'treasure': True}


def scene(floor=True, trail=False):
    d, st = Dungeon.from_ascii(ROWS, seed=7)
    d.floor_on, d.trail_on, d.events = floor, trail, True
    b = mkbot('1', *st['1'])
    o = mkbot('2', *st['2'])
    return d, b, o, [b, o]


def feed(d, b):
    d.turn = 10
    d._note_last(b, {'char': '1', 'type': 'goto', 'target': 'exit', 'result': 'pathed', 'len': 5})
    d._note_last(b, {'char': '1', 'type': 'walk', 'target': 'exit', 'result': 'walking'})
    d.turn = 12
    d._note_last(b, ENC)
    d.turn = 13
    d._note_last(b, {'char': '1', 'type': 'attack', 'result': 'attack', 'target': '고블린', 'target_id': 'm1',
                     'hit': True, 'dmg': 4, 'killed': True})
    b['hp'] = 3
    d.turn = 14
    d._note_last(b, {'char': '1', 'type': 'hurt', 'by': '고블린', 'by_id': 'm2', 'dmg': 9, 'hp': 3})


print("── ① 스위치")
check("① 엔진 기본 floor_on=False · from_ascii 기본 False",
      Dungeon(seed=7).floor_on is False and Dungeon.from_ascii(["####", "#1>#", "####"])[0].floor_on is False)
d0, b0, o0, bots0 = scene(floor=False)
feed(d0, b0)
ob0 = d0.view(b0, bots0)
check("① 꺼진 판: 집계 안 쌓임 · obs 에 floor/floors 없음", not (b0.get('floor') or {}).get('n')
      and 'floor' not in ob0 and 'floors' not in ob0)

print("── ② 자기 집계")
d, b, o, bots = scene()
feed(d, b)
n = b['floor']['n']
check("② 걸음·이동 시작 제외 / 조우 = [발견] ×2·[함정] ×1·[출혈] ×1·[획득] ×1 / [처치] ×1 / [피격] ×1 / [위급] ×1(궤적 꺼도)",
      n == {'발견': 2, '함정': 1, '출혈': 1, '획득': 1, '처치': 1, '피격': 1, '위급': 1}
      and b['critical'] is True and not b.get('trail'))

print("── ③ 목격 집계")
d._witness(bots, b['x'], b['y'], {'kind': 'ally_hurt', 'char': '1', 'by': '고블린', 'by_id': 'm2'}, exclude=('1',))
d._witness(bots, b['x'], b['y'], {'kind': 'ally_kill', 'char': '1', 'mon': '고블린'}, exclude=('1',))
check("③ 동료(카야)의 w 에 [동료 피격] ×1·[동료 처치] ×1 · 당사자(두란) w 는 비어 있음",
      o['floor']['w'] == {'동료 피격': 1, '동료 처치': 1} and not b['floor']['w'])

print("── ④ obs·렌더")
d.turn = 20
ob = d.view(b, bots)
fl = ob.get('floor')
check("④ obs.floor = {since 10, turns 10, n, w, rooms}", fl and fl['since'] == 10 and fl['turns'] == 10
      and fl['n'] == n and fl['w'] == {} and 'rooms' in fl)
txt = brains._wire(ob, NAMES)
sec = [ln for ln in txt.splitlines() if ln.startswith("- [") or ln.startswith("## 이 층")]
check("④ 렌더: '## 이 층에서 지금까지 (t10 진입, 10틱째' · 꼬리표 ×N 내림차순([발견] ×2 먼저) · 목격 줄 없음(w 비면)",
      any(ln.startswith("## 이 층에서 지금까지 (t10 진입, 10틱째") for ln in txt.splitlines())
      and any(ln.startswith("- [발견] ×2 · ") for ln in sec) and "- 목격:" not in txt)
obo = d.view(o, bots)
check("④ 목격만 있는 동료 렌더: '- 목격: [동료 처치] ×1 · [동료 피격] ×1'(같은 횟수는 라벨순)",
      "- 목격: [동료 처치] ×1 · [동료 피격] ×1" in brains._wire(obo, NAMES))

print("── ⑤ 결산(얼리기)")
before = copy.deepcopy(b)
fz = G.floor_freeze(b, 1, 25)
check("⑤ floor_freeze → [{depth 1, t0 10, t1 25, n, w, line None, invite True}] · 봇 무변경(순수)",
      fz == [{'depth': 1, 't0': 10, 't1': 25, 'n': n, 'w': {}, 'line': None, 'invite': True}]
      and b == before)
fz2 = G.floor_freeze({**b, 'floors': fz, 'floor': {'since': 25, 'n': {'대화': 1}, 'w': {}}}, 0, 40)
check("⑤ 두 번째 얼리기는 뒤에 붙는다(마을 왕복 포함) · 앞 항목 보존",
      len(fz2) == 2 and fz2[0]['depth'] == 1 and fz2[1] == {'depth': 0, 't0': 25, 't1': 40, 'n': {'대화': 1}, 'w': {},
                                                              'line': None, 'invite': True})

print("── ⑥ 초대·살")
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "", "floor_line": "1층은 고블린 둘로 험했다"}'
dn, bn, on_, botsn = scene()
bn['floors'] = G.floor_freeze(b, 1, 25)          # 새 층 첫 결정 직전 상태(러너 이월 미러)
bn['floor'] = {'since': 26, 'n': {}, 'w': {}}
dn.turn = 26
obn = dn.view(bn, botsn)
txt1 = brains._wire(obn, NAMES)
check("⑥ 첫 결정 렌더: '## 지난 층' · '- 1층 (t10~t25, 15틱): [발견] ×2 …' · floor_line 안내",
      "## 지난 층" in txt1 and "- 1층 (t10~t25, 15틱): [발견] ×2" in txt1 and "`floor_line`" in txt1)
out = brains.think_all(dn, botsn)
check("⑥ 응답 floor_line → decisions 에 실리고 floors[-1].line 저장 · invite 닫힘",
      out['1'].get('floor_line') == '1층은 고블린 둘로 험했다'
      and bn['floors'][-1]['line'] == '1층은 고블린 둘로 험했다' and bn['floors'][-1]['invite'] is False)
txt2 = brains._wire(dn.view(bn, botsn), NAMES)
check("⑥ 다음 결정: 안내 없음 · 한 줄이 결산 뒤에 붙음 — '… — \"1층은 고블린 둘로 험했다\"'",
      "`floor_line`" not in txt2 and '— "1층은 고블린 둘로 험했다"' in txt2)
out2 = brains.think_all(dn, botsn)
check("⑥ 초대 없는 결정의 floor_line 은 무시(엔진 불가침 유지)", 'floor_line' not in out2['1']
      and bn['floors'][-1]['line'] == '1층은 고블린 둘로 험했다')
dm, bm, om, botsm = scene()
bm['floors'] = [{'depth': 0, 't0': 1, 't1': 18, 'n': {'대화': 2}, 'w': {}, 'line': None, 'invite': True}]
check("⑥ 마을(0층)은 '마을'로 표기", "- 마을 (t1~t18, 17틱): [대화] ×2" in brains._wire(dm.view(bm, botsm), NAMES))

print("── ⑦ 결정론")
da, ba, oa, botsa = scene()
feed(da, ba)
db, bb, ob_, botsb = scene()
feed(db, bb)
check("⑦ 같은 수순 두 번 = 같은 집계", ba['floor'] == bb['floor'])

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_floor (D40 ② 층 집계·결산: 사전 하나·자기/목격 집계·렌더·얼리기·초대 1회·floor_line 불가침·결정론)")
