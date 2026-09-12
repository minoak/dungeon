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
  ⑩ D53 지식 3층(09-12 파트너 "5번 조우하면 심층 — 공통 프리셋, 일단 몬스터만"): book(원장 기록) 배선 시
     등재~해금 전 = brief 한 줄 + deep_progress{encounter n/need}, 조건을 채우는 조우에 'deep' 발급 → 다음 obs 본문 전체.
     book 미배선(옛 하네스) = 옛 2층(등재 즉시 본문). 조건 없는 종(함정)은 book 있어도 즉시 본문. 프롬프트 접미 '(심층: 조우 n/5)'.
  ⑪ 옛 원장(n 없음) 로드 = 조우 1 / 저장 왕복에 n·deep 보존 / 층이 바뀌면 같은 id 도 새 개체(다시 1)
  ⑫ 라이브·소급 일치는 진행도(n·deep)까지 — run_meta.bestiary_progress 시드
  ⑬ D55 캐릭터 인식 한 줄(09-12, 메모 §2-5 [결정] "해금 순간에 첫 인식 한 줄 … N번이 차면 고칠 기회"): 해금 조우에 'invite'
     (원장 due='deep'·asked_n) → obs book_invite → 프롬프트 "## 도감" 절 → 응답 book_line → decisions.book_line{key, text} →
     발급기가 원장 note 로(내용 안 읽음) · 작정 수는 초대를 못 닫음 · 초대 없는 결정의 book_line 무시 · asked_n+review 에
     'review' 초대(기존 생각 노출) · 답 없어도 닫힘(되풀이 없음) · 저장 왕복·progress·run_meta 시드까지 같은 문턱
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
check("④ aware_of 증분 = 캐릭터 귀속 획득(첫 시선) — 등재 사건 'brief'", acq_a[0] == ('두란', 'monster:고블린', 'brief'))
check("④ 재획득 없음 + 함정 밟음/간파 + 샘 경험 획득",
      acq_a.count(('두란', 'monster:고블린', 'brief')) == 1 and not any(t == 'deep' for _, _, t in acq_a)
      and ('카야', 'monster:고블린', 'brief') in acq_a and ('카야', 'monster:그림자거미', 'brief') in acq_a
      and ('두란', 'trap:alarm', 'brief') in acq_a and ('카야', 'trap:spike', 'brief') in acq_a
      and ('카야', 'feature:fountain', 'brief') in acq_a)
iss_b, acq_b = issue_seq()
check("⑤ 결정론: 같은 시퀀스 2회 = 같은 획득 순서", acq_a == acq_b)

# ── ⑥ 원장 save/load 왕복 ──
os.makedirs(STATE, exist_ok=True)
rt = os.path.join(STATE, "roundtrip.json")
iss_a.save(rt)
iss_rt = bestiary.Issuer().load(rt)
check("⑥ 원장 save/load 왕복(원자적 저장) — 진행도(n)까지",
      {n: sorted(s) for n, s in iss_rt.book.items() if s}
      == {n: sorted(s) for n, s in iss_a.book.items() if s}
      and iss_rt.progress() == iss_a.progress() and iss_rt.record('두란')['monster:고블린']['n'] == 1)


def led_prog(led):
    """원장 파일 → 진행도 투영(Issuer.progress 와 같은 꼴 — D55 뒤 note·asked_n·due·deep_n 까지)."""
    return {n: {k: bestiary._prog_entry(r) for k, r in sorted(v.items())}
            for n, v in sorted(led.items()) if not n.startswith('_') and v}


# ── ⑩ D53 지식 3층 — book 배선 시 brief+진행도 → 조건 채우면 deep ──
d10 = arena(seed=10)
d10.monsters = [Monster(6, 5, mid=i) for i in range(5)] + [Monster(7, 6, kind='그림자거미', mid=5)]
d10.lore = {'monster:고블린': {'name': '고블린', 'lore': 'LORE_G', 'brief': 'BRIEF_G', 'unlock': {'event': 'encounter', 'count': 3}},
            'trap:spike': {'name': '가시 함정', 'lore': 'LORE_S'}}
iss10 = bestiary.Issuer({'1': '두란'}, rules={'monster:고블린': {'event': 'encounter', 'count': 3}})
b10 = mkbot('1', 5, 5)
b10['known'] = iss10.known('두란')
b10['book'] = iss10.record('두란')
iss10.consume('level', {'kind': 'level', 'depth': 1, 'monsters': [{'id': i, 'kind': '고블린'} for i in range(5)] + [{'id': 5, 'kind': '그림자거미'}]})
seen10 = []
for n in range(1, 5):
    ev = iss10.consume('tick', {'kind': 'tick', 'turn': n, 'monsters': [], 'events': [],
                                'bots': [{'char': '1', 'aware_of': list(range(n))}]})
    m = next(x for x in d10.view(b10, [b10])['sights']['monsters'] if x['id'] == 'm0')
    seen10.append((ev, m.get('lore'), m.get('deep_progress')))
check("⑩ 등재(조우 1) = 원명 + brief 한 줄 + 진행도 1/3 — 본문(lore) 비노출",
      seen10[0] == ([('두란', 'monster:고블린', 'brief')], 'BRIEF_G', {'event': 'encounter', 'n': 1, 'need': 3}))
check("⑩ 조우 2 = 사건 없음(dirty 만) · 진행도 2/3", seen10[1] == ([], 'BRIEF_G', {'event': 'encounter', 'n': 2, 'need': 3}) and iss10.dirty)
check("⑩ 조우 3 = 'deep' 발급(+D55 인식 초대) → 다음 obs 본문 전체·진행도 없음",
      seen10[2] == ([('두란', 'monster:고블린', 'deep'), ('두란', 'monster:고블린', 'invite')], 'LORE_G', None))
check("⑩ 해금 뒤 조우는 n 만 오르고 재발급 없음", seen10[3] == ([], 'LORE_G', None) and iss10.record('두란')['monster:고블린']['n'] == 4
      and iss10.record('두란')['monster:고블린']['deep'] == {'turn': 3, 'depth': 1, 'n': 3})
m10s = next(x for x in d10.view(b10, [b10])['sights']['monsters'] if x['id'] == 'm5')
check("⑩ 미등재 종(그림자거미)은 그대로 '낯선 짐승'·진행도 없음", m10s['kind'] == UNKNOWN_BEAST and 'deep_progress' not in m10s and 'lore' not in m10s)
b10b = mkbot('1', 5, 5)
b10b['known'] = {'monster:고블린', 'trap:spike'}          # book 미배선 = 옛 2층
m10b = next(x for x in d10.view(b10b, [b10b])['sights']['monsters'] if x['id'] == 'm0')
check("⑩ book 미배선(옛 하네스) = 등재 즉시 본문 전체(하위호환 솔기)", m10b.get('lore') == 'LORE_G' and 'deep_progress' not in m10b)
import brains as _brains  # noqa: E402
b10d = mkbot('1', 5, 5)
b10d['known'] = iss10.known('두란')
b10d['book'] = {'monster:고블린': {'turn': 1, 'depth': 1, 'n': 2}}     # 해금 전 기록을 직접 꽂아 접미 렌더 확인
wire10 = _brains._wire(d10.view(b10d, [b10d]), {'1': '두란'})
check("⑩ 프롬프트 접미 — '… 습성: BRIEF_G (심층: 조우 2/3)'",
      any('BRIEF_G (심층: 조우 2/3)' in ln for ln in wire10.split('\n')) and 'LORE_G' not in wire10)

# ── ⑪ 옛 원장 로드·저장 왕복·층 전환 ──
old_led = os.path.join(STATE, "old_format.json")
with open(old_led, 'w', encoding='utf-8') as f:
    json.dump({'_readme': 'x', '두란': {'monster:고블린': {'turn': 44, 'depth': 1}}}, f, ensure_ascii=False)
iss11 = bestiary.Issuer({'1': '두란'}, rules={'monster:고블린': {'event': 'encounter', 'count': 3}}).load(old_led)
check("⑪ 옛 원장(n 없음) = 조우 1 로 읽고 known 에 등재", iss11.record('두란')['monster:고블린']['n'] == 1 and 'monster:고블린' in iss11.known('두란')
      and iss11.progress() == {'두란': {'monster:고블린': {'n': 1}}})
iss11.consume('level', {'kind': 'level', 'depth': 1, 'monsters': [{'id': 0, 'kind': '고블린'}]})
ev1 = iss11.consume('tick', {'kind': 'tick', 'turn': 1, 'monsters': [], 'events': [], 'bots': [{'char': '1', 'aware_of': [0]}]})
iss11.consume('level', {'kind': 'level', 'depth': 2, 'monsters': [{'id': 0, 'kind': '고블린'}]})   # 새 층 = 같은 id 라도 새 개체
ev2 = iss11.consume('tick', {'kind': 'tick', 'turn': 9, 'monsters': [], 'events': [], 'bots': [{'char': '1', 'aware_of': [0]}]})
check("⑪ 층이 바뀌면 같은 id 도 새 개체로 센다(1→2→3=해금, depth 2 에서)",
      ev1 == [] and ev2 == [('두란', 'monster:고블린', 'deep'), ('두란', 'monster:고블린', 'invite')]
      and iss11.record('두란')['monster:고블린']['deep'] == {'turn': 9, 'depth': 2, 'n': 3})
iss11.save(old_led)
iss11b = bestiary.Issuer().load(old_led)
check("⑪ 저장 왕복에 n·deep(·D55 due·asked_n) 보존 + save 가 dirty 를 내린다", not iss11.dirty
      and iss11b.record('두란')['monster:고블린'] == {'turn': 44, 'depth': 1, 'n': 3, 'deep': {'turn': 9, 'depth': 2, 'n': 3},
                                                     'asked_n': 3, 'due': 'deep'})

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

# ── ⑬ D55 캐릭터 인식 한 줄 — 해금 초대 → 응답 book_line → 원장 note → 갱신 초대(메모 §2-5) ──
d13 = arena(seed=13)
d13.monsters = [Monster(6, 5, mid=i) for i in range(9)]
d13.lore = {'monster:고블린': {'name': '고블린', 'lore': 'LORE_G', 'brief': 'BRIEF_G', 'unlock': {'event': 'encounter', 'count': 3}}}
R13 = {'monster:고블린': {'event': 'encounter', 'count': 3}}
iss13 = bestiary.Issuer({'1': '두란'}, rules=R13)          # review 미지정 = 명시 규칙과 같은 문턱(3)
b13 = mkbot('1', 5, 5)
b13['known'] = iss13.known('두란')
b13['book'] = iss13.record('두란')
iss13.consume('level', {'kind': 'level', 'depth': 1, 'monsters': [{'id': i, 'kind': '고블린'} for i in range(9)]})


def enc13(n, turn, decisions=None):
    return iss13.consume('tick', {'kind': 'tick', 'turn': turn, 'monsters': [], 'events': [], 'decisions': decisions or {},
                                  'bots': [{'char': '1', 'aware_of': list(range(n))}]})


ev_a = enc13(2, 1)
check("⑬ 해금 전엔 초대 없음(obs 에 book_invite 없음)",
      ev_a == [('두란', 'monster:고블린', 'brief')] and 'book_invite' not in d13.view(b13, [b13]))
ev_b = enc13(3, 2)
rec13 = iss13.record('두란')['monster:고블린']
inv13 = d13.view(b13, [b13]).get('book_invite')
check("⑬ 해금 조우 = 'deep' + 'invite' · 원장 due='deep'·asked_n=3 · obs book_invite{key, name, why deep, n 3}",
      ev_b == [('두란', 'monster:고블린', 'deep'), ('두란', 'monster:고블린', 'invite')]
      and rec13.get('due') == 'deep' and rec13.get('asked_n') == 3
      and inv13 == {'key': 'monster:고블린', 'name': '고블린', 'why': 'deep', 'n': 3})
txt13 = _brains._wire(d13.view(b13, [b13]), {'1': '두란'})
check("⑬ 렌더: '## 도감 — 네 생각 한 줄 (선택)' · '고블린의 심층 정보가 열렸다(지금까지 3번 겪음)' · `book_line` 안내",
      "## 도감 — 네 생각 한 줄 (선택)" in txt13 and "고블린의 심층 정보가 열렸다(지금까지 3번 겪음)" in txt13 and "`book_line`" in txt13)
ev_c = enc13(3, 3, {'1': {'type': 'goto', 'src': 'plan', 'book_line': {'key': 'monster:고블린', 'text': '무시돼야 한다'}}})
check("⑬ 작정 수(src=plan)는 초대를 닫지도 note 를 남기지도 않는다(프롬프트가 안 나갔다)",
      ev_c == [] and rec13.get('due') == 'deep' and 'note' not in rec13)
_brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "", "book_line": "겁쟁이지만 셋이면 문다"}'
dec13 = _brains.think_all(d13, [b13])['1']
check("⑬ 응답 book_line → decisions.book_line{key, text}(초대가 있는 결정에서만)",
      dec13.get('book_line') == {'key': 'monster:고블린', 'text': '겁쟁이지만 셋이면 문다'})
ev_d = enc13(3, 4, {'1': dec13})
check("⑬ 실 결정 → 원장 note{text, turn 4, depth 1, n 3} · due 닫힘 · 사건 'note'",
      ev_d == [('두란', 'monster:고블린', 'note')] and 'due' not in rec13
      and rec13.get('note') == {'text': '겁쟁이지만 셋이면 문다', 'turn': 4, 'depth': 1, 'n': 3})
ob13 = d13.view(b13, [b13])
m13 = ob13['sights']['monsters'][0]
txt13b = _brains._wire(ob13, {'1': '두란'})
check("⑬ obs: 몹 항목 note=생각(사실 lore 와 다른 칸) · book_invite 없음 · 렌더 '네 생각(네가 적어 둔 것): …'",
      m13.get('note') == '겁쟁이지만 셋이면 문다' and m13.get('lore') == 'LORE_G' and 'book_invite' not in ob13
      and "네 생각(네가 적어 둔 것): 겁쟁이지만 셋이면 문다" in txt13b and "## 도감" not in txt13b)
check("⑬ 초대 없는 결정의 book_line 은 무시(엔진 불가침)", 'book_line' not in _brains.think_all(d13, [b13])['1'])
ev_e = enc13(5, 5)
ev_f = enc13(6, 6)
inv13b = d13.view(b13, [b13]).get('book_invite')
txt13c = _brains._wire(d13.view(b13, [b13]), {'1': '두란'})
check("⑬ 조우 5 는 조용 · 조우 6(=asked_n 3 + review 3) 에 'invite' review · due='review'·asked_n 6 · obs line=기존 생각",
      ev_e == [] and ev_f == [('두란', 'monster:고블린', 'invite')] and rec13.get('due') == 'review' and rec13.get('asked_n') == 6
      and inv13b == {'key': 'monster:고블린', 'name': '고블린', 'why': 'review', 'n': 6, 'line': '겁쟁이지만 셋이면 문다'})
check("⑬ 갱신 렌더: '적어 둔 생각: \"겁쟁이지만 셋이면 문다\"' · '그대로 두려면 비워 둔다'",
      '적어 둔 생각: "겁쟁이지만 셋이면 문다"' in txt13c and "그대로 두려면 비워 둔다" in txt13c)
ev_g = enc13(6, 7, {'1': {'type': 'wait', 'src': 'haiku'}})
ev_h = enc13(7, 8)
check("⑬ 답 없는 실 결정도 초대를 닫는다(note 그대로·asked_n 6) · 다음 조우(7)엔 초대 없음(다음 문턱 9)",
      ev_g == [] and ev_h == [] and 'due' not in rec13 and rec13['note']['text'] == '겁쟁이지만 셋이면 문다' and rec13['asked_n'] == 6)
p13 = os.path.join(STATE, "d55_roundtrip.json")
iss13.save(p13)
check("⑬ 저장 왕복: note·asked_n·deep.n 보존", bestiary.Issuer().load(p13).record('두란')['monster:고블린'] == rec13)
pr13 = iss13.progress()['두란']['monster:고블린']
check("⑬ progress(run_meta 시드) = {n 7, deep, deep_n 3, asked_n 6, note{text, n 3}}",
      pr13 == {'n': 7, 'deep': True, 'deep_n': 3, 'asked_n': 6, 'note': {'text': '겁쟁이지만 셋이면 문다', 'n': 3}})
iss13c = bestiary.Issuer({'1': '두란'}, rules=R13)
iss13c.consume('run_meta', {'kind': 'run_meta', 'party': [{'char': '1', 'name': '두란'}],
                            'bestiary': {'두란': ['monster:고블린']}, 'bestiary_progress': iss13.progress()})
r13c = iss13c.record('두란')['monster:고블린']
iss13c.consume('level', {'kind': 'level', 'depth': 1, 'monsters': [{'id': i, 'kind': '고블린'} for i in range(3)]})
ev_i = iss13c.consume('tick', {'kind': 'tick', 'turn': 1, 'monsters': [], 'events': [], 'bots': [{'char': '1', 'aware_of': [0, 1]}]})
check("⑬ 소급(run_meta 시드)도 같은 문턱: n 7·deep n 3·asked_n 6·note 이월 → 조우 9 에 review 초대",
      r13c['n'] == 9 and r13c['deep']['n'] == 3 and r13c['note']['text'] == '겁쟁이지만 셋이면 문다'
      and ev_i == [('두란', 'monster:고블린', 'invite')] and r13c.get('due') == 'review' and r13c['asked_n'] == 9)

# ── ⑦⑥ 라이브 통합(show_runner 헤들리스 2판 — 격리 STATE·격리 원장) ──
shutil.rmtree(STATE, ignore_errors=True)
os.makedirs(STATE, exist_ok=True)
import brains  # noqa: E402
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"  # 빈 응답 스텁은 명시적인 엔진 테스트로 실행
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
check("⑦ 라이브 원장 = 스트림 오프라인 소급(결정론 투영 일치 — D5) — 진행도(n·deep)까지(⑫)",
      book_off == book_led and iss_off.progress() == led_prog(led))
check("⑫ 1판 run_meta.bestiary_progress = {}(첫 원정) · 원장 n 은 전부 ≥1", meta1.get("bestiary_progress") == {}
      and all(int(r.get('n', 0)) >= 1 for n, v in led.items() if not n.startswith('_') for r in v.values()))

recs2 = run_once()
meta2 = recs2[0]
check("⑥ 2판째 run_meta.bestiary = 1판 종료 원장(지식 이월 — 죽어도 남는 재산 D4) · bestiary_progress 도 1판 종료 진행도",
      meta2.get("bestiary") == book_led and meta2.get("bestiary_progress") == led_prog(led))

# ── ⑨ 이월 판 투영: 2판 스트림 소급(run_meta.bestiary 시드) == 2판 종료 원장 ──
iss_off2, _acq2 = bestiary.replay(os.path.join(STATE, "stream.jsonl"))
book_off2 = {n: sorted(s) for n, s in iss_off2.book.items() if s}
with open(BFILE, encoding="utf-8") as f:
    led2 = json.load(f)
book_led2 = {n: sorted(v) for n, v in led2.items() if not n.startswith('_')}
check("⑨ 이월 판(2판째) 오프라인 소급 = 2판 종료 원장(순수 투영 — 리뷰 픽스) — 진행도까지",
      book_off2 == book_led2 and iss_off2.progress() == led_prog(led2))

print("=" * 44)
print("RESULT: " + ("ALL PASS — 도감(D11③ obs 되먹임) 건전"
                    if C.failed == 0 else "%d FAILED" % C.failed))
raise SystemExit(1 if C.failed else 0)
