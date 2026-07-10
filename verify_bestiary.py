# -*- coding: utf-8 -*-
"""도감(D9 지식 2층 구조 — D11③ obs 되먹임) 헤들리스 검증 — 10번째 게이트.
게이트:
  ① 주입 하위호환: bot['known']=None(기본) → obs 무변경(원명·lore 없음) — 기존 게이트 불침 솔기
  ② 언노운: known=set() → 보이는 몹 kind='낯선 짐승'(id·state·hp 는 유지 — 시야-온리 불변),
     리모컨 라벨에도 원명 비누설
  ③ 로어 조인: 등재 몹 = 원명+lore / 등재 피처 = lore / 미등재 피처 = lore 없음(이름은 그대로)
  ④ 발급기 규칙(스트림 어휘로 닫힘): aware_of 증분=몬스터 획득(캐릭터 귀속·재획득 없음) /
     함정 밟음·간파 / 상자·샘 상호작용
  ⑤ 결정론: 같은 레코드 시퀀스 2회 = 같은 획득 순서
  ⑥ 원장 영속: save/load 왕복 + 2판째 run_meta.bestiary = 1판 종료 원장(지식 이월 — D4)
  ⑦ 라이브 통합(show_runner 헤들리스·격리 STATE): 판 중 라이브 발급 = 같은 스트림 오프라인
     소급(replay)과 일치 — "발급은 스트림의 결정론 투영"(D5 규율)의 실측
  ⑧ 언노운→기명 전이: 발급기 set 과 bot['known']이 같은 객체 — 획득 즉시 다음 obs 에 원명+lore
  ⑨ 이월 판 투영(리뷰 3렌즈 합치 픽스): 2판째 스트림의 오프라인 소급이 run_meta.bestiary 를
     시작 지식으로 시드해 라이브 원장과 정확히 일치 — 이월 판에서도 '같은 스트림→같은 원장'
"""
import contextlib
import io
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state_bestiaryverify")
BFILE = os.path.join(STATE, "bestiary_test.json")
# ⚠️ STATE·원장 격리 — 기본 state/ 나 라이브 bestiary.json 을 건드리면 관전 판·지식이 오염된다
#    (2026-07-05 아침판 소실 사고와 같은 계열의 경로. verify 는 언제나 자기 폴더에서 논다)
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="400", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="2", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2",
                  DUNGEON_PARTY_FILE="/nonexistent",   # 내장 2인 고정(회귀 그물)
                  DUNGEON_STATE_DIR=STATE,
                  DUNGEON_BESTIARY_FILE=BFILE)
os.environ.pop("DUNGEON_STREAM_OBS", None)

from dungeon_gm import Dungeon, Monster, UNKNOWN_BEAST, spawn  # noqa: E402
import bestiary  # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, hp=14, dex=0):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14,
            'str': 3, 'dex': dex, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'last': None, 'searched': set()}


def arena(seed=1, w=20, h=12):
    d = Dungeon(seed=seed, w=w, h=h, n_monsters=0, n_traps=0, n_lurkers=0)
    for y in range(h):
        for x in range(w):
            d.grid[y][x] = '.' if (1 <= x < w - 1 and 1 <= y < h - 1) else '#'
    ef = d.features[d._exit_fid]
    ef.x, ef.y = w - 2, h - 2
    d.features = {d._exit_fid: ef}
    d.monsters, d.traps = [], []
    d.visited = set()
    return d


# ── ①②③ 주입(view 조인) 단위 검증 ──
d = arena()
gob = Monster(6, 5, mid=0)
d.monsters = [gob]
b1 = mkbot('1', 5, 5)                                   # mkbot 에 'known' 없음 = None(기본)
o1 = d.view(b1, [b1])
m1 = o1['sights']['monsters'][0]
check("① known 미배선(None) = 원명 그대로·lore 없음(하위호환 솔기)",
      m1['kind'] == '고블린' and 'lore' not in m1)

b2 = mkbot('1', 5, 5)
b2['known'] = set()
o2 = d.view(b2, [b2])
m2 = o2['sights']['monsters'][0]
lbl2 = [o['label'] for o in o2['options'] if o.get('target') == 'm0']
check("② 미등재 몹 = '낯선 짐승'(id·state·hp 유지 — 시야-온리 불변)",
      m2['kind'] == UNKNOWN_BEAST and m2['id'] == 'm0'
      and m2['state'] == gob.state and m2['hp'] == gob.hp)
check("② 리모컨 라벨에도 원명 비누설", bool(lbl2)
      and all('고블린' not in s for s in lbl2) and UNKNOWN_BEAST in lbl2[0])

d.lore = {'monster:고블린': {'name': '고블린', 'lore': 'LORE_G'},
          'feature:chest': {'name': '상자', 'lore': 'LORE_C'}}
cid = d._add_feature('chest', '상자', 7, 5)
b3 = mkbot('1', 5, 5)
b3['known'] = {'monster:고블린', 'feature:chest'}
o3 = d.view(b3, [b3])
m3 = o3['sights']['monsters'][0]
c3 = next(f for f in o3['sights']['features'] if f['type'] == 'chest')
check("③ 등재 몹 = 원명 + lore 주입", m3['kind'] == '고블린' and m3.get('lore') == 'LORE_G')
check("③ 등재 피처 = lore 조인", c3.get('lore') == 'LORE_C')
b3b = mkbot('1', 5, 5)
b3b['known'] = set()
c3b = next(f for f in d.view(b3b, [b3b])['sights']['features'] if f['type'] == 'chest')
check("③ 미등재 피처 = lore 없음(이름은 그대로 — 겉모습은 보인다)",
      'lore' not in c3b and c3b['name'] == '상자')

# ── ④⑤ 발급기 규칙 + 결정론 ──
LVL = {'kind': 'level', 'depth': 1,
       'monsters': [{'id': 0, 'kind': '고블린'}, {'id': 1, 'kind': '그림자거미'}]}
T1 = {'kind': 'tick', 'turn': 1, 'monsters': [], 'events': [],
      'bots': [{'char': '1', 'aware_of': [0]}, {'char': '2', 'aware_of': []}]}
T2 = {'kind': 'tick', 'turn': 2, 'monsters': [],
      'bots': [{'char': '1', 'aware_of': [0]}, {'char': '2', 'aware_of': [0, 1]}],
      'events': [{'type': 'walk', 'char': '1', 'trap': {'kind': 'alarm', 'name': '경보 함정'}},
                 {'type': 'search', 'char': '2', 'found': [{'kind': 'trap', 'name': '가시 함정'}]},
                 {'type': 'interact', 'char': '2', 'result': 'fountain_heal'}]}


def issue_seq():
    iss = bestiary.Issuer({'1': '두란', '2': '카야'})
    acq = []
    for kind, rec in (('level', LVL), ('tick', T1), ('tick', T2)):
        acq += iss.consume(kind, rec)
    return iss, acq


iss_a, acq_a = issue_seq()
check("④ aware_of 증분 = 캐릭터 귀속 획득(첫 시선)", acq_a[0] == ('두란', 'monster:고블린'))
check("④ 재획득 없음 + 함정 밟음/간파 + 샘 경험 획득",
      acq_a.count(('두란', 'monster:고블린')) == 1
      and ('카야', 'monster:고블린') in acq_a and ('카야', 'monster:그림자거미') in acq_a
      and ('두란', 'trap:alarm') in acq_a and ('카야', 'trap:spike') in acq_a
      and ('카야', 'feature:fountain') in acq_a)
iss_b, acq_b = issue_seq()
check("⑤ 결정론: 같은 시퀀스 2회 = 같은 획득 순서", acq_a == acq_b)

# ── ⑥ 원장 save/load 왕복 ──
os.makedirs(STATE, exist_ok=True)
rt = os.path.join(STATE, "roundtrip.json")
iss_a.save(rt)
iss_rt = bestiary.Issuer().load(rt)
check("⑥ 원장 save/load 왕복(원자적 저장)",
      {n: sorted(s) for n, s in iss_rt.book.items() if s}
      == {n: sorted(s) for n, s in iss_a.book.items() if s})

# ── ⑧ 언노운→기명 전이: 발급기 set == bot['known'] (공유 객체 — 러너 배선 시맨틱) ──
iss8 = bestiary.Issuer({'1': '두란'})
d8 = arena(seed=8)
g8 = Monster(6, 5, mid=0)
d8.monsters = [g8]
d8.lore = {'monster:고블린': {'name': '고블린', 'lore': 'LORE'}}
b8 = mkbot('1', 5, 5)
b8['known'] = iss8.known('두란')
v1 = d8.view(b8, [b8])                                  # 첫 시선(_perceive가 aware_of 등록)
iss8.consume('level', {'kind': 'level', 'depth': 1,
                       'monsters': [{'id': 0, 'kind': '고블린'}]})
iss8.consume('tick', {'kind': 'tick', 'turn': 1, 'monsters': [], 'events': [],
                      'bots': [{'char': '1', 'aware_of': sorted(b8['aware_of'])}]})
v2 = d8.view(b8, [b8])
check("⑧ 첫 시선='낯선 짐승' → 발급 직후 같은 봇 obs 즉시 원명+lore(공유 set)",
      v1['sights']['monsters'][0]['kind'] == UNKNOWN_BEAST
      and v2['sights']['monsters'][0]['kind'] == '고블린'
      and v2['sights']['monsters'][0].get('lore') == 'LORE')

# ── ⑦⑥ 라이브 통합(show_runner 헤들리스 2판 — 격리 STATE·격리 원장) ──
shutil.rmtree(STATE, ignore_errors=True)
os.makedirs(STATE, exist_ok=True)
import brains  # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
import show_runner  # noqa: E402
show_runner.STEP_DELAY = 0
import time as _time  # noqa: E402
_time.sleep = lambda s: None


def run_once():
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
    with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


recs1 = run_once()
meta1 = recs1[0]
check("⑦ 1판: run_meta.bestiary={}(첫 원정) + bestiary_file=true",
      meta1.get("bestiary") == {} and meta1.get("bestiary_file") is True)
with open(BFILE, encoding="utf-8") as f:
    led = json.load(f)
book_led = {n: sorted(v) for n, v in led.items() if not n.startswith('_')}
check("⑦ 판에서 몬스터 지식 획득 발생(원장 파일 생성)",
      any(k.startswith('monster:') for ks in book_led.values() for k in ks))
iss_off, _acq = bestiary.replay(os.path.join(STATE, "stream.jsonl"))
book_off = {n: sorted(s) for n, s in iss_off.book.items() if s}
check("⑦ 라이브 원장 = 스트림 오프라인 소급(결정론 투영 일치 — D5)", book_off == book_led)

recs2 = run_once()
meta2 = recs2[0]
check("⑥ 2판째 run_meta.bestiary = 1판 종료 원장(지식 이월 — 죽어도 남는 재산 D4)",
      meta2.get("bestiary") == book_led)

# ── ⑨ 이월 판 투영: 2판 스트림 소급(run_meta.bestiary 시드) == 2판 종료 원장 ──
iss_off2, _acq2 = bestiary.replay(os.path.join(STATE, "stream.jsonl"))
book_off2 = {n: sorted(s) for n, s in iss_off2.book.items() if s}
with open(BFILE, encoding="utf-8") as f:
    led2 = json.load(f)
book_led2 = {n: sorted(v) for n, v in led2.items() if not n.startswith('_')}
check("⑨ 이월 판(2판째) 오프라인 소급 = 2판 종료 원장(순수 투영 — 리뷰 픽스)",
      book_off2 == book_led2)

print("=" * 44)
print("RESULT: " + ("ALL PASS — 도감(D11③ obs 되먹임) 건전"
                    if C.failed == 0 else "%d FAILED" % C.failed))
raise SystemExit(1 if C.failed else 0)
