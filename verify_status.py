# -*- coding: utf-8 -*-
"""상태 태그(D34, 2026-09-06 파트너 확정 "HP 는 그대로, 몹·함정이 특수공격으로 태그를 붙인다") 헤들리스
검증 — 34번째 게이트.
태그 = 몸에 붙는 상태(출혈·둔화·중독). 효과는 몸(걸음·굴림)에만, 판단 강제 없음(D14), 지우기는
휴식(D35)뿐. 라벨=사실만(효과를 그대로 말한다). 동료도 같은 단어를 본다(겉보기 옆 한 단어).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판=함정·몹 명중에도 무태그, _apply_status=None
  ② 원천 5경로: 가시 함정→출혈 / 독침 함정→중독 / 그림자거미 명중→둔화(고블린=무태그) /
     상자 독침→중독 / 오염된 샘→중독 — 이벤트에 status 부기
  ③ 출혈: BLEED_STEPS 걸음마다 HP 1(걸음 결과에 bleed 병기) · 제자리는 안 남 · 사망 경로=묘·encounter
  ④ 둔화: SLOW_EVERY 틱에 한 칸(제자리 틱=walking+slowed, to 없음) · 쉬는 틱에도 새 몹이면 encounter
  ⑤ 중독: 명중 mod −POISON_MOD · 회피 ac −POISON_MOD (굴림 고정 — 수식만 잰다)
  ⑥ 목격: 시야 안 동료 ally_status 1회(당사자·시야 밖 제외) · ×N 은 n 만 는다
  ⑦ 렌더: 자기 obs status → "## 네 몸 상태"(효과 문장·원천·경과) · 동료 겉보기 옆 단어 ·
     목격 문장 "…으로 출혈 상태가 되는 것을" · 출혈사 "출혈로 쓰러지는 것을" · 물음표 0
  ⑧ 결정론: 같은 장면 2회 = 같은 status·witnessed
  ⑨ 스냅샷 additive(있을 때만 status) · 러너 이월 코드 존재 · 헤들리스 2층 판 결정론(더미 두뇌)
(기존 verify 33종은 별도 실행.)
"""
import os
import io
import json
import shutil
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state_statusverify")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="200", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="2", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2", DUNGEON_STEP_DELAY="0",
                  DUNGEON_PARTY_FILE="/nonexistent", DUNGEON_STATE_DIR=STATE_DIR)
os.environ.pop("DUNGEON_STREAM_OBS", None)
os.environ.pop("DUNGEON_STATUS", None)      # 러너 기본(1)을 잰다

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon

brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
os.environ["DUNGEON_BESTIARY_FILE"] = ""
import show_runner
show_runner.STEP_DELAY = 0
import time as _time
_time.sleep = lambda s: None


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, hp=14, dex=0, job='전사'):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14,
            'str': 3, 'dex': dex, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': [], 'status': {}, 'bleed_steps': 0, 'slow_beat': 0,
            'witnessed': [], 'memories': []}


def tag(b, name, by='가시 함정'):
    b['status'][name] = {'n': 1, 'by': by, 'since': 0}


def tick(d, b, bots):
    """한 틱 걷기 — 탐색 핑은 시야 끝(트인 길)까지만 깔리므로 소진되면 같은 틱에 다시 핑(act 는
    걸음이 아니다). 반환 = step_order 결과."""
    if b['alive'] and not b.get('order'):
        d.act(b, {'type': 'explore'}, bots)
    return d.step_order(b, bots)


# ────────────────────────────────────────────────────────────────
print("① 스위치 격리")
d0 = Dungeon(seed=7)
check("엔진 기본 status=0", d0.status is False)
d0a, _ = Dungeon.from_ascii(["####", "#1>#", "####"])
check("from_ascii 기본 status=0", d0a.status is False)

CORR = ["############",
        "#1........>#",
        "############"]


def corridor(status=True, hp=14, graves=False, events=False):
    d, st = Dungeon.from_ascii(CORR, seed=7)
    d.status, d.graves, d.events = status, graves, events
    b = mkbot('1', *st['1'], hp=hp)
    return d, b, [b]


d, b, bots = corridor(status=False)
check("꺼진 판 _apply_status=None·무태그",
      d._apply_status(b, '출혈', '가시 함정', bots) is None and not b['status'])

# ────────────────────────────────────────────────────────────────
print("③ 출혈 — 걸음이 피를 낸다")
d, b, bots = corridor()
tag(b, '출혈')
r0 = d.act(b, {'type': 'explore'}, bots)
check("탐색 핑 개시", r0.get('result') == 'pathed')
hps, bleeds = [], 0
for i in range(9):
    r = tick(d, b, bots)
    hps.append(b['hp'])
    if r.get('bleed'):
        bleeds += 1
        check("걸음 %d: bleed 병기 hp=%d" % (i + 1, r['bleed']['hp']), r['bleed']['hp'] == b['hp'])
check("9걸음 = HP −3 (BLEED_STEPS=%d)" % G.BLEED_STEPS, b['hp'] == 14 - 9 // G.BLEED_STEPS)
check("bleed 이벤트 3회", bleeds == 3)
check("걸음 없는 상태 유지엔 피 안 남(bleed_steps 그대로)",
      b['bleed_steps'] == 9 and b['hp'] == 11)

d, b, bots = corridor(status=False)
tag(b, '출혈')
moves = sum(1 for _ in range(9) if 'to' in tick(d, b, bots))
check("꺼진 판: 출혈 태그가 있어도 피 안 남(9걸음)", b['hp'] == 14 and moves == 9)

d, b, bots = corridor(hp=1, graves=True, events=True)
tag(b, '출혈')
last = None
for _ in range(3):
    last = tick(d, b, bots)
check("출혈사: 3걸음째 HP 0 → 사망·encounter·bleed.down·묘",
      not b['alive'] and last.get('result') == 'encounter'
      and last.get('bleed', {}).get('down') is True
      and last['bleed'].get('grave', {}).get('name') == '전사의 묘'
      and b['order'] is None)

# ────────────────────────────────────────────────────────────────
print("④ 둔화 — 두 틱에 한 칸")
d, b, bots = corridor()
tag(b, '둔화', by='그림자거미')
slowed = moves = 0
for _ in range(6):
    r = tick(d, b, bots)
    if 'to' in r:
        moves += 1
    if r.get('slowed'):
        slowed += 1
        check("제자리 틱=walking+slowed, to 없음", r['result'] == 'walking' and 'to' not in r)
check("6틱 = %d걸음 (SLOW_EVERY=%d)" % (6 // G.SLOW_EVERY, G.SLOW_EVERY),
      moves == 6 // G.SLOW_EVERY and slowed == 3)
d, b, bots = corridor(status=False)
tag(b, '둔화', by='그림자거미')
moves = sum(1 for _ in range(6) if 'to' in tick(d, b, bots))
check("꺼진 판: 둔화 태그가 있어도 6틱=6걸음", moves == 6)

SPIDER = ["#######",
          "#1..s>#",
          "#######"]
d, st = Dungeon.from_ascii(SPIDER, seed=7,
                           monsters={'s': {'kind': '그림자거미', 'state': 'SLEEPING'}})
d.status = True
b = mkbot('1', *st['1'])
tag(b, '둔화', by='그림자거미')
bots = [b]
d.act(b, {'type': 'explore'}, bots)
r = d.step_order(b, bots)          # 첫 틱 = 쉬는 틱(박자 1) — 그 자리에서 몹이 시야에 든다
check("쉬는 틱에도 눈은 뜨고 — 새 몹이면 encounter", r.get('result') == 'encounter'
      and r.get('monsters', [{}])[0].get('kind') == '그림자거미')

# ────────────────────────────────────────────────────────────────
print("⑤ 중독 — 명중·회피 감산")
FIGHT = ["######",
         "#1g.>#",
         "######"]
d, st = Dungeon.from_ascii(FIGHT, seed=7,
                           monsters={'g': {'kind': '고블린', 'state': 'HUNTING', 'target': '1'}})
d.status = True
b = mkbot('1', *st['1'])
bots = [b]
m = d.monsters[0]
m.last_seen = (b['x'], b['y'])
b['aware_of'].add(m.id)
d.d20 = lambda: 10
r = d.act(b, {'type': 'attack', 'target': 'm0'}, bots)
check("맨몸: mod=STR 3 → 13≥12 명중", r.get('mod') == 3 and r.get('hit') is True)
m.hp = 6
tag(b, '중독', by='독침 함정')
r = d.act(b, {'type': 'attack', 'target': 'm0'}, bots)
check("중독: mod=1 → 11<12 빗나감 (스트림 mod 에 그대로)", r.get('mod') == 1 and r.get('hit') is False)
d.d20 = lambda: 7
ev = d._monster_attack(m, b, bots)
check("중독: ac 10→8, 9≥8 명중 (스트림 ac 에 그대로)", ev.get('ac') == 8 and ev.get('hit') is True)
b['status'] = {}
ev = d._monster_attack(m, b, bots)
check("맨몸: ac 10, 9<10 빗나감", ev.get('ac') == 10 and ev.get('hit') is False)

# ────────────────────────────────────────────────────────────────
print("② 원천 5경로 + ⑥ 목격")
TRAP = ["###########",
        "#1.^...>2##",
        "#########3#",
        "###########"]


def trap_scene(kind='spike', status=True):
    d, st = Dungeon.from_ascii(TRAP, seed=7)
    d.status, d.events, d.graves = status, True, True
    t = d.traps[0]
    d.traps[0] = G.Trap(t.x, t.y, kind=kind)
    d.traps[0].dc = 99                     # 확정 실패
    b1 = mkbot('1', *st['1'])
    b2 = mkbot('2', *st['2'], job='도적')
    b3 = mkbot('3', *st['3'], job='궁수')
    bots = [b1, b2, b3]
    d.d20 = lambda: 1                      # 수동 인지 실패(함정을 못 보고 밟는다)
    d.act(b1, {'type': 'explore'}, bots)
    last = None
    for _ in range(3):
        last = d.step_order(b1, bots)
        if last.get('trap'):
            break
    return d, b1, b2, b3, bots, last


d, b1, b2, b3, bots, last = trap_scene('spike')
tr = last.get('trap') or {}
check("가시 함정 → 출혈(이벤트 trap.status·봇 status)",
      tr.get('status') == '출혈' and '출혈' in b1['status']
      and b1['status']['출혈']['by'] == '가시 함정' and b1['status']['출혈']['n'] == 1)
w2 = [w for w in b2['witnessed'] if w.get('kind') == 'ally_status']
w3 = [w for w in b3['witnessed'] if w.get('kind') == 'ally_status']
check("목격: 시야 안 동료 ally_status 1회 · 벽 너머 동료 0 · 당사자 0",
      len(w2) == 1 and w2[0]['tag'] == '출혈' and w2[0]['by_kind'] == 'trap'
      and not w3 and not [w for w in b1['witnessed'] if w.get('kind') == 'ally_status'])
d._apply_status(b1, '출혈', '가시 함정', bots, by_kind='trap')
check("×N: 같은 태그 재발 = n 만 는다", b1['status']['출혈']['n'] == 2 and len(b1['status']) == 1)

d, b1, b2, b3, bots, last = trap_scene('dart')
tr = last.get('trap') or {}
check("독침 함정 → 중독", tr.get('status') == '중독' and '중독' in b1['status'])

d, b1, b2, b3, bots, last = trap_scene('spike', status=False)
check("꺼진 판: 함정 실패해도 무태그·이벤트 무부기",
      not b1['status'] and 'status' not in (last.get('trap') or {}) and b1['hp'] == 11)

d, st = Dungeon.from_ascii(SPIDER.copy(), seed=7,
                           monsters={'s': {'kind': '그림자거미', 'state': 'HUNTING', 'target': '1'}})
d.status = True
b = mkbot('1', *st['1'])
b['x'] = d.monsters[0].x - 1              # 몹 곁으로(직교 인접)
bots = [b]
d.monsters[0].last_seen = (b['x'], b['y'])
b['aware_of'].add(d.monsters[0].id)
d.d20 = lambda: 20
evs = d.monster_turn(bots)
hit = [e for e in evs if e.get('type') == 'monster_attack']
check("그림자거미 명중 → 둔화(이벤트 status·봇 status·last.status)",
      hit and hit[0].get('status') == '둔화' and '둔화' in b['status']
      and b['last'].get('status') == '둔화')
d, st = Dungeon.from_ascii(FIGHT, seed=7,
                           monsters={'g': {'kind': '고블린', 'state': 'HUNTING', 'target': '1'}})
d.status = True
b = mkbot('1', *st['1'])
bots = [b]
d.monsters[0].last_seen = (b['x'], b['y'])
b['aware_of'].add(d.monsters[0].id)
d.d20 = lambda: 20
evs = d.monster_turn(bots)
hit = [e for e in evs if e.get('type') == 'monster_attack']
check("고블린 명중 → 무태그(기준선 몹)", hit and 'status' not in hit[0] and not b['status'])

OBJ = ["#######",
       "#1=~.>#",
       "#######"]
d, st = Dungeon.from_ascii(OBJ, seed=7)
d.status = True
b = mkbot('1', *st['1'])
bots = [b]
obs = d.view(b, bots)
cid = next(f['id'] for f in obs['sights']['features'] if f['type'] == 'chest')
fid = next(f['id'] for f in obs['sights']['features'] if f['type'] == 'fountain')
d.d20 = lambda: 1
r = d.act(b, {'type': 'interact', 'target': cid}, bots)
check("상자 독침 → 중독(result chest_trap·status)", r.get('result') == 'chest_trap'
      and r.get('status') == '중독' and b['status']['중독']['by'] == '함정 상자')
b['status'] = {}
b['x'] += 1
r = d.act(b, {'type': 'interact', 'target': fid}, bots)
check("오염된 샘 → 중독", r.get('result') == 'fountain_harm' and r.get('status') == '중독'
      and b['status']['중독']['by'] == '오염된 샘')

# ────────────────────────────────────────────────────────────────
print("⑦ 렌더")
d, b1, b2, b3, bots, last = trap_scene('spike')
d.turn = 5
b1['ledger'] = G.new_ledger()             # 'N턴 전에'는 장부 판의 turn 스탬프가 재료(D17-3)
obs = d.view(b1, bots)
check("자기 obs status=[{tag,n,by,since}]",
      obs.get('status') == [{'tag': '출혈', 'n': 1, 'by': '가시 함정', 'since': 0}])
txt = brains._wire(obs)
check("wire '## 네 몸 상태' + 효과 문장 + 원천 + 경과",
      "## 네 몸 상태" in txt and "[출혈]" in txt
      and G.status_prose('출혈') in txt and "가시 함정, 5턴 전에" in txt)
check("wire 물음표 0(관찰 사실만)", "?" not in txt.split("## 네 몸 상태")[1].split("\n\n")[0])
b1['status']['출혈']['n'] = 2
txt = brains._wire(d.view(b1, bots))
check("×2 표시", "[출혈 ×2]" in txt)
obs2 = d.view(b2, bots)
ally = next(a for a in obs2['sights']['bots'] if a['char'] == '1')
check("동료 항목 status=['출혈'] (겉으로 드러난다)", ally.get('status') == ['출혈'])
names = {'1': '두란', '2': '카야', '3': '피른'}
txt2 = brains._wire(obs2, names)
check("동료 줄 '겉보기 … · 출혈'", "겉보기 다침 · 출혈" in txt2 or "겉보기 가벼운 상처 · 출혈" in txt2)
check("목격 문장", brains._witness_prose(
    {'kind': 'ally_status', 'name': '두란', 'char': '1', 'tag': '출혈',
     'by': '가시 함정', 'by_kind': 'trap'}) == "두란(봇1)가 가시 함정으로 출혈 상태가 되는 것을")
check("목격 문장(몹 원천 — 조사 '로')", brains._witness_prose(
    {'kind': 'ally_status', 'name': '카야', 'char': '2', 'tag': '둔화',
     'by': '그림자거미'}) == "카야(봇2)가 그림자거미로 둔화 상태가 되는 것을")
check("출혈사 목격 문장", brains._witness_prose(
    {'kind': 'ally_down', 'name': '두란', 'char': '1', 'by': '출혈', 'by_kind': 'status'})
      == "두란(봇1)가 출혈로 쓰러지는 것을")
check("몹 사인 목격 문장 불변", brains._witness_prose(
    {'kind': 'ally_down', 'name': '두란', 'char': '1', 'by': '고블린'})
      == "두란(봇1)가 고블린에게 쓰러지는 것을")
check("자기 관측: 피격+태그", "[둔화]이(가) 붙었다" in brains._last_prose(
    {'type': 'hurt', 'by': '그림자거미', 'by_id': 'm0', 'dmg': 3, 'hp': 9, 'status': '둔화'}))
check("자기 관측: 함정+태그", "[출혈]이(가) 붙었다" in brains._last_prose(
    {'type': 'walk', 'result': 'encounter',
     'trap': {'name': '가시 함정', 'dmg': 3, 'status': '출혈'}}))
lab = next((o['label'] for o in obs.get('options', []) if o['type'] == 'attack'), None)
check("리모컨 라벨은 무변경(태그는 '네 몸 상태' 절이 말한다)", lab is None)

# ────────────────────────────────────────────────────────────────
print("⑧ 결정론")


def snap(run):
    d, b1, b2, b3, bots, last = run
    return json.dumps([b1['status'], b2['witnessed'], b1['hp'], last], sort_keys=True,
                      ensure_ascii=False, default=sorted)


check("같은 장면 2회 = 같은 status·witnessed·hp", snap(trap_scene('spike')) == snap(trap_scene('spike')))

# ────────────────────────────────────────────────────────────────
print("⑨ 스냅샷·이월·헤들리스")
b = mkbot('1', 1, 1)
check("스냅샷: 태그 없으면 키 없음(꺼진 판 바이트 동일)", 'status' not in G.bot_snapshot(b))
tag(b, '출혈')
check("스냅샷: 태그 있으면 status=['출혈'] (additive)", G.bot_snapshot(b).get('status') == ['출혈'])
src = io.open(os.path.join(HERE, "show_runner.py"), encoding="utf-8").read()
check("러너 이월 코드 존재(status·bleed_steps)",
      'n["status"]' in src and 'n["bleed_steps"]' in src and "status=STATUS_ON" in src)
check("러너 run_meta status 키", "status=STATUS_ON,          #" in src)


def run_once():
    if os.path.isdir(STATE_DIR):
        shutil.rmtree(STATE_DIR)
    os.makedirs(STATE_DIR, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
    return io.open(os.path.join(STATE_DIR, "stream.jsonl"), encoding="utf-8").read()


def norm(s):
    lines = s.splitlines()
    head = json.loads(lines[0])
    head.pop("started", None)             # 벽시계만 제외(verify_stream ⑤ 문법)
    return [json.dumps(head, sort_keys=True)] + lines[1:]


s1 = run_once()
s2 = run_once()
check("헤들리스 2층 판(더미 두뇌·status 켬) 결정론 — started 제외 라인 동일",
      norm(s1) == norm(s2) and len(s1) > 0)
recs = [json.loads(l) for l in s1.splitlines() if l.strip()]
meta = recs[0]
check("run_meta.status=true", meta.get("status") is True)
tagged = [b for r in recs if r.get("kind") == "tick" for b in r.get("bots", []) if "status" in b]
check("스냅샷 status 는 리스트(있을 때만) — 발화 %d회" % len(tagged),
      all(isinstance(b["status"], list) and b["status"] for b in tagged))
if os.path.isdir(STATE_DIR):
    shutil.rmtree(STATE_DIR)

print()
print(("RESULT: ALL PASS" if not C.failed else "RESULT: %d FAIL" % C.failed)
      + " — verify_status (D34 상태 태그: 원천·효과·목격·렌더·결정론)")
raise SystemExit(1 if C.failed else 0)
