# -*- coding: utf-8 -*-
"""관계 장부(D36, 2026-09-06 파트너 확정 "뼈는 기계가 세고, 살은 문턱에서만 캐릭터가 쓴다 — 매 스텝
평가 방지: 상호작용 상태값(횟수)이 일정 수치를 넘으면 몇 자 이내로 요약") 헤들리스 검증 — 36번째 게이트.
뼈 5종(스트림 어휘로 닫힘 — say 내용 해석 0): 이야기를 나눔(talk)·함께 싸움(fought)·나를 기다려 줌(waited)·
나를 구함(rescued)·죽을 때 곁에 있었음(at_death). 강한 뼈(rescued·at_death)=즉시 초대, 약한 뼈=합계가
RELATION_K 배수일 때 초대(결정당 1개). 살=결정 응답 relation_line 한 줄 겹쳐쓰기(80자, 엔진 불가침).
시트 관계 칸=살의 초기값(가정 A). 호감도 숫자 없음. 솔로 판 미노출. 판 간 영속 X.
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판 _bone·note_talk 무동작·스폰 미씨앗·obs 무노출
  ② 뼈 5종: talk(쌍당 틱당 1·대칭) / fought(FOUGHT_WINDOW 안 같은 몹·쌍당 몹당 1) / rescued(표적을 물던
     몹 처치→피구조자 장부, 시야-온리) / waited(wait_met·rest_met→도착자 장부) / at_death(목격자 장부)
  ③ 문턱: 약한 뼈 합계 10·20 → milestone 1회씩, 강한 뼈 즉시, view 는 결정당 초대 1개(큐 소진)
  ④ 살: think_all 이 relation_line 을 그 상대 항목에 겹쳐쓰기(line_src=self·turn), 초대 없는 콜은 무시,
     80자 절단 / 엔진 불가침(dungeon_gm 소스에서 line 은 판단에 안 쓰인다)
  ⑤ 시트 씨앗: relationships 문장 → line(sheet, turn 0) / _sheet 렌더 "(시트)" → 덮어쓰면 "(네가 N턴에 남긴 말)"
  ⑥ 렌더: wire "## 동료와 겪은 일" 횟수 줄 · 초대 절은 invite 때만 · 물음표 0 · 솔로 무노출
  ⑦ 이월·배선 코드 존재(러너) ⑧ 결정론 ⑨ 스냅샷 additive(뼈 있을 때만)
(기존 verify 35종은 별도 실행.)
"""
import io
import json
import os

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon

HERE = os.path.dirname(os.path.abspath(__file__))


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


NAMES = {'1': '두란', '2': '카야', '3': '피른'}


def mkbot(char, x, y, hp=14, job='전사'):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14, 'name': NAMES.get(char),
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': [], 'status': {}, 'bleed_steps': 0, 'slow_beat': 0,
            'rest': None, 'relations': {}, 'witnessed': [], 'memories': []}


ROOM = ["##############",
        "#1.2.........#",
        "#....3.......#",
        "#####>########"]


def scene(relations=True, monsters=None, rows=None):
    d, st = Dungeon.from_ascii(rows or ROOM, seed=7, monsters=monsters)
    d.relations, d.events, d.graves, d.wait_verb, d.rest_verb = relations, True, True, True, True
    b1 = mkbot('1', *st['1'])
    b2 = mkbot('2', *st['2'], job='도적')
    b3 = mkbot('3', *st['3'], job='궁수')
    return d, b1, b2, b3, [b1, b2, b3]


def bone(b, oc, kind):
    return ((b.get('relations') or {}).get(oc) or {}).get('bones', {}).get(kind, {}).get('n', 0)


# ────────────────────────────────────────────────────────────────
print("① 스위치 격리")
check("엔진 기본 relations=0", Dungeon(seed=7).relations is False)
d0, _ = Dungeon.from_ascii(["####", "#1>#", "####"])
check("from_ascii 기본 relations=0", d0.relations is False)
d, b1, b2, b3, bots = scene(relations=False)
d.turn = 1
d.note_talk(b1, b2)
d._bone(b1, '2', 'rescued')
check("꺼진 판: note_talk·_bone 무동작", b1['relations'] == {} and b2['relations'] == {})
check("꺼진 판: obs 에 relations 없음", 'relations' not in d.view(b1, bots))
sheet = {**G.HEROES['1'], 'name': '두란', 'relationships': {'2': '카야의 눈썰미를 믿는다'}}
dg = Dungeon(seed=7)
nb = G.spawn(dg, '1', [], sheet=sheet)
check("꺼진 판: 스폰 미씨앗(relations 빈 dict)", nb['relations'] == {})
dg.relations = True
nb = G.spawn(dg, '1', [], sheet=sheet)
check("켠 판: 시트 관계 칸 = 살의 초기값(line, sheet, turn 0)",
      nb['relations'].get('2', {}).get('line') == '카야의 눈썰미를 믿는다'
      and nb['relations']['2']['line_src'] == 'sheet' and nb['relations']['2']['line_turn'] == 0
      and nb['relations']['2']['bones'] == {})

# ────────────────────────────────────────────────────────────────
print("② 뼈 5종")
d, b1, b2, b3, bots = scene()
d.turn = 1
d.note_talk(b1, b2); d.note_talk(b2, b1)
check("talk: 같은 틱 양방향 = 쌍당 1(대칭)", bone(b1, '2', 'talk') == 1 and bone(b2, '1', 'talk') == 1)
d.turn = 2
d.note_talk(b2, b1)
check("talk: 다음 틱 +1·last 갱신", bone(b1, '2', 'talk') == 2
      and b1['relations']['2']['bones']['talk']['last'] == 2 and b1['relations']['2']['total'] == 2)
check("talk: 제3자 무관", bone(b3, '1', 'talk') == 0 and bone(b1, '3', 'talk') == 0)

FIGHT = ["##############",
         "#1g2.........#",
         "#....3.......#",
         "#####>########"]
d, b1, b2, b3, bots = scene(monsters={'g': {'kind': '고블린', 'hp': 30, 'ac': 1, 'state': 'HUNTING',
                                            'target': '1'}}, rows=FIGHT)
m = d.monsters[0]
m.last_seen = (b1['x'], b1['y'])
for b in bots:
    b['aware_of'].add(m.id)
d.d20 = lambda: 15
d.turn = 1; d._attack(b1, 'm0', bots)
d.turn = 3; d._attack(b2, 'm0', bots)
check("fought: 5틱 안 같은 몹 → 둘 다 ×1", bone(b1, '2', 'fought') == 1 and bone(b2, '1', 'fought') == 1)
d.turn = 4; d._attack(b1, 'm0', bots)
d.turn = 5; d._attack(b2, 'm0', bots)
check("fought: 같은 몹은 쌍당 1회(한 전투는 한 번)", bone(b1, '2', 'fought') == 1)
d.turn = 30; d._attack(b1, 'm0', bots)            # 창 밖(25틱 뒤) — 이미 적힌 쌍이라 무관
check("fought: 제3자(안 친 피른) 무관", bone(b3, '1', 'fought') == 0)

d, b1, b2, b3, bots = scene(monsters={'g': {'kind': '고블린', 'hp': 1, 'ac': 1, 'state': 'HUNTING',
                                            'target': '2'}}, rows=FIGHT)
m = d.monsters[0]
m.last_seen = (b2['x'], b2['y'])
d.d20 = lambda: 20
d.turn = 7
r = d._attack(b1, 'm0', bots)
check("rescued: 카야를 물던 몹을 두란이 처치 → 카야 장부에 '나를 구함'·즉시 초대",
      r.get('killed') and bone(b2, '1', 'rescued') == 1 and b2['relations']['1']['queue'] == ['rescued']
      and bone(b1, '2', 'rescued') == 0 and b1['relations'].get('2', {}).get('queue', []) == [])
d, b1, b2, b3, bots = scene(monsters={'g': {'kind': '고블린', 'hp': 1, 'ac': 1, 'state': 'HUNTING',
                                            'target': '2'}}, rows=FIGHT)
b2['x'], b2['y'] = 12, 2                          # 표적이 멀리(시야 밖) — 못 본 구조는 모른다
d.monsters[0].last_seen = (b2['x'], b2['y'])
d.d20 = lambda: 20
d._attack(b1, 'm0', bots)
check("rescued: 시야 밖 피구조자는 무등재(전지 주입 금지)", bone(b2, '1', 'rescued') == 0)

d, b1, b2, b3, bots = scene()
b2['x'], b2['y'] = 12, 1
d.act(b1, {'type': 'wait'}, bots)
d.step_order(b1, bots)
b2['x'] = 3
r = d.step_order(b1, bots)
check("waited(wait_met): 기다린 두란 곁에 온 카야의 장부에 '나를 기다려 줌'",
      r['result'] == 'wait_met' and bone(b2, '1', 'waited') == 1 and bone(b1, '2', 'waited') == 0)
d, b1, b2, b3, bots = scene()
b1['hp'] = 10
b2['x'], b2['y'] = 12, 1
d.act(b1, {'type': 'rest'}, bots)
d.step_order(b1, bots)
b2['x'] = 3
r = d.step_order(b1, bots)
check("waited(rest_met): 쉬는 동료 곁에 온 쪽의 장부에도", r['result'] == 'rest_met' and bone(b2, '1', 'waited') == 1)

TRAP = ["##############",
        "#1^2.........#",
        "#............#",
        "#####>#####3##"]
d, b1, b2, b3, bots = scene(rows=TRAP)
d.traps[0].dc, d.traps[0].dmg = 99, 20
d.d20 = lambda: 1
d.turn = 9
d._enter_cell(b1, 2, 1, bots)
check("at_death: 곁에서 죽음을 본 카야 장부에 '죽을 때 곁에 있었음'·즉시 초대 / 벽 너머 피른 무등재",
      not b1['alive'] and bone(b2, '1', 'at_death') == 1 and b2['relations']['1']['queue'] == ['at_death']
      and bone(b3, '1', 'at_death') == 0)

# ────────────────────────────────────────────────────────────────
print("③ 문턱")
d, b1, b2, b3, bots = scene()
for t in range(1, 21):
    d.turn = t
    d.note_talk(b1, b2)
check("약한 뼈 합계 10·20 → milestone 두 번(즉시 아님)",
      b1['relations']['2']['queue'] == ['milestone', 'milestone']
      and b1['relations']['2']['total'] == 20)
d.turn = 21
d._bone(b1, '3', 'rescued')
o = d.view(b1, bots)
inv = [(r['char'], r.get('invite')) for r in o['relations'] if r.get('invite')]
check("view: 결정당 초대 1개(번호순 첫 큐부터) — 카야 milestone", inv == [('2', 'milestone')])
o = d.view(b1, bots)
inv = [(r['char'], r.get('invite')) for r in o['relations'] if r.get('invite')]
check("다음 결정: 카야의 둘째 milestone", inv == [('2', 'milestone')])
o = d.view(b1, bots)
inv = [(r['char'], r.get('invite')) for r in o['relations'] if r.get('invite')]
check("그다음: 피른 rescued", inv == [('3', 'rescued')])
o = d.view(b1, bots)
check("큐 소진 뒤: 초대 없음(관계 칸 자체가 없다)",
      not any(r.get('invite') for r in o.get('relations', [])))

# ────────────────────────────────────────────────────────────────
print("④ 살 — think_all 이 철한다")
orig = brains._call_claude


def think_with(reply, d, bots):
    brains._call_claude = lambda p, m: (reply, None)
    try:
        return brains.think_all(d, bots)
    finally:
        brains._call_claude = orig


d, b1, b2, b3, bots = scene()
d.turn = 40
b1['relations'] = {'2': {'bones': {'talk': {'n': 10, 'last': 39}}, 'total': 10,
                         'line': '카야의 눈썰미를 믿는다', 'line_turn': 0, 'line_src': 'sheet',
                         'queue': ['milestone']}}
out = think_with('{"reason": "r", "choice": 1, "relation_line": "말은 차갑지만 등은 맡길 수 있는 사람이다"}',
                 d, bots)
check("초대 있는 결정: 응답 relation{to=2, line}·장부 겹쳐쓰기(self·turn 40)",
      out['1'].get('relation') == {'to': '2', 'line': '말은 차갑지만 등은 맡길 수 있는 사람이다'}
      and b1['relations']['2']['line'] == '말은 차갑지만 등은 맡길 수 있는 사람이다'
      and b1['relations']['2']['line_src'] == 'self' and b1['relations']['2']['line_turn'] == 40)
check("초대 없던 카야·피른의 relation_line 은 무시", 'relation' not in out['2'] and 'relation' not in out['3'])
d.turn = 41
out = think_with('{"reason": "r", "choice": 1, "relation_line": "이건 안 받는다"}', d, bots)
check("초대 없는 다음 결정: 필드 무시·줄 불변", 'relation' not in out['1']
      and b1['relations']['2']['line'] == '말은 차갑지만 등은 맡길 수 있는 사람이다')
b1['relations']['2']['queue'] = ['rescued']
out = think_with('{"reason": "r", "choice": 1, "relation_line": "%s"}' % ('가' * 120), d, bots)
check("80자 절단(NOTE_LEN 과 같은 자)", len(b1['relations']['2']['line']) == brains.NOTE_LEN)
src = io.open(os.path.join(HERE, "dungeon_gm.py"), encoding="utf-8").read()
PEEK = ('==', '!=', 'startswith', 'endswith', 'len(', '.split', '.lower', '.find', 're.', ' in e[')
bad = [ln for ln in src.splitlines() if "'line'" in ln and any(p in ln for p in PEEK)]
check("엔진 불가침: dungeon_gm 은 line 의 내용을 읽지 않는다(비교·검색·길이 0 — 있음/없음만)", not bad)

# ────────────────────────────────────────────────────────────────
print("⑤ 시트 씨앗 렌더")
roster = [{'char': '1', 'name': '두란'}, {'char': '2', 'name': '카야'}, {'char': '3', 'name': '피른'}]
b = {**mkbot('1', 1, 1), 'relationships': {'2': '카야의 눈썰미를 믿는다', '3': '피른의 수다는 귀찮다'},
     'relations': {'2': {'bones': {}, 'total': 0, 'line': '카야의 눈썰미를 믿는다', 'line_turn': 0,
                         'line_src': 'sheet', 'queue': []}}}
sh = brains._sheet(b, roster)
check("시트: 살(시트 초기값) 렌더 '(시트)'", "- 카야(봇2)와의 관계: 카야의 눈썰미를 믿는다 (시트)" in sh)
check("시트: 살이 없는 상대는 시트 문장 그대로", "- 피른(봇3)와의 관계: 피른의 수다는 귀찮다" in sh)
b['relations']['2'].update(line='말은 차갑지만 등은 맡길 수 있다', line_turn=40, line_src='self')
sh = brains._sheet(b, roster)
check("시트: 덮어쓴 살 '(네가 40턴에 남긴 말)'",
      "- 카야(봇2)와의 관계: 말은 차갑지만 등은 맡길 수 있다 (네가 40턴에 남긴 말)" in sh
      and "카야의 눈썰미를 믿는다" not in sh)
check("relations 꺼진 봇(빈 dict)은 시트 문장 그대로",
      "카야의 눈썰미를 믿는다" in brains._sheet({**b, 'relations': {}}, roster))

# ────────────────────────────────────────────────────────────────
print("⑥ 렌더")
d, b1, b2, b3, bots = scene()
for t in (1, 2):
    d.turn = t; d.note_talk(b1, b2)
d.turn = 5; d._bone(b1, '2', 'rescued')
d.turn = 6
b1['ledger'] = G.new_ledger()
o = d.view(b1, bots)
w = brains._wire(o, NAMES)
check("wire '## 동료와 겪은 일' + '이야기를 나눔 ×2' + '나를 구함 ×1 (1턴 전에)'",
      "## 동료와 겪은 일" in w and "카야(봇2): 이야기를 나눔 ×2 (4턴 전에), 나를 구함 ×1 (1턴 전에)" in w)
check("wire 초대 절 '카야(봇2)에 대해 남길 한 줄' + relation_line 안내 + 이유",
      "## 카야(봇2)에 대해 남길 한 줄 (선택)" in w and "relation_line" in w and "방금 너를 구했다" in w)
sec = w.split("## 동료와 겪은 일")[1]
check("wire 물음표 0(관찰 사실만)", "?" not in sec.split("## 카야")[0])
o = d.view(b1, bots)
w2 = brains._wire(o, NAMES)
check("초대 없는 결정: 초대 절 없음·횟수 줄은 남는다",
      "에 대해 남길 한 줄" not in w2 and "## 동료와 겪은 일" in w2)
d.solo = True
check("솔로 판: obs 무노출", 'relations' not in d.view(b1, bots))
d.solo = False

# ────────────────────────────────────────────────────────────────
print("⑦ 러너 배선 · ⑧ 결정론 · ⑨ 스냅샷")
rsrc = io.open(os.path.join(HERE, "show_runner.py"), encoding="utf-8").read()
check("러너: 스위치·메타·note_talk 배선·이월",
      'DUNGEON_RELATIONS' in rsrc and 'relations=RELATIONS_ON' in rsrc and 'd.note_talk(' in rsrc
      and 'n["relations"]' in rsrc)
pm = io.open(os.path.join(HERE, "adventurer_prompt_menu.md"), encoding="utf-8").read()
check("프롬프트: relation_line 필드 안내(절이 있을 때만)", "`relation_line`" in pm and "절이 있을 때만" in pm)


def run():
    d, b1, b2, b3, bots = scene(monsters={'g': {'kind': '고블린', 'hp': 30, 'ac': 1, 'state': 'HUNTING',
                                                'target': '1'}}, rows=FIGHT)
    d.monsters[0].last_seen = (b1['x'], b1['y'])
    d.d20 = lambda: 15
    for t in range(1, 12):
        d.turn = t
        d.note_talk(b1, b2)
        if t == 3:
            d._attack(b1, 'm0', bots)
        if t == 4:
            d._attack(b2, 'm0', bots)
    return json.dumps([b['relations'] for b in bots], sort_keys=True, ensure_ascii=False)


check("같은 장면 2회 = 같은 장부", run() == run())
b = mkbot('1', 1, 1)
check("스냅샷: 뼈 없으면 키 없음", 'relations' not in G.bot_snapshot(b))
b['relations'] = {'2': {'bones': {'talk': {'n': 2, 'last': 2}}, 'total': 2, 'line': 'x',
                        'line_turn': 0, 'line_src': 'sheet', 'queue': []}}
check("스냅샷: 뼈 횟수만(살은 안 나간다) additive",
      G.bot_snapshot(b).get('relations') == {'2': {'talk': 2}})

print()
print(("RESULT: ALL PASS" if not C.failed else "RESULT: %d FAIL" % C.failed)
      + " — verify_relations (D36 관계 장부: 뼈 5종·문턱·살·시트 씨앗·렌더·결정론)")
raise SystemExit(1 if C.failed else 0)
