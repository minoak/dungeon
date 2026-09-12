# -*- coding: utf-8 -*-
"""엔티티 저장소(D50) 게이트 — 로드·검증기 / 엔진 유도값 = 이관 전 리터럴 / 지식·NPC 본문의 이관 전후 해시 일치 /
검증기의 거절(모르는 부품·id≠파일명·없는 텍스처·없는 해금 사건·중복). 실 LLM 0콜, 라이브 데이터 무접촉."""
import hashlib
import json
import os
import shutil
import tempfile

os.environ.setdefault('DUNGEON_BRAIN_BACKEND', 'dummy')
import entities as ENT
import dungeon_gm as G
import show_runner

checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


def canon(o):
    return hashlib.sha256(json.dumps(o, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


# 이관 전(커밋 d38669f) lore.json 7건·town.json NPC 3인의 정본 해시 — 본문·대사·선물·배치가 한 글자라도 바뀌면 여기서 선다.
LORE_SHA = 'f332d3e7968a963733024834d85b7bad01feac27819a19b446ea86b09247e069'
NPC_SHA = 'b6c1e5f26edb42b1e7ad09a6f0db05b8f62d30df43dd846cf67d649f9e8fd1b7'

# ① 로드
defs = ENT.load()
check('① 정의 로드 — kind 4종·정의 20개(몬스터 2·함정 3·오브젝트 9·NPC 6 = 상점 v0 3 + 마을 v1 3)',
      {d['kind'] for d in defs.values()} == set(ENT.KINDS) and len(defs) == 20
      and len(ENT.by_kind('monster')) == 2 and len(ENT.by_kind('trap')) == 3 and len(ENT.by_kind('object')) == 9 and len(ENT.by_kind('npc')) == 6)

# ② 엔진 유도값 == 이관 전 리터럴(동작 그대로)
check('② TRAP_KINDS 가 정의에서 유도되어 옛 리터럴과 같다',
      G.TRAP_KINDS == {'spike': {'name': '가시 함정', 'dc': 13, 'dmg': 3, 'status': '출혈'},
                       'dart': {'name': '독침 함정', 'dc': 14, 'dmg': 2, 'status': '중독'},
                       'alarm': {'name': '경보 함정', 'dc': 13, 'dmg': 0}})
check('② GEAR_KINDS 유도 · GEAR_CYCLE 의 이름은 전부 정의에 있다',
      G.GEAR_KINDS == {'단검': 1, '장검': 2, '가죽 갑옷': 1, '사슬 갑옷': 2} and {n for _, n in G.GEAR_CYCLE} <= set(G.GEAR_KINDS))
check('② MON_STATUS 유도(그림자거미 명중=둔화, 고블린 무태그)', G.MON_STATUS == {'그림자거미': '둔화'})
g = G.Monster(0, 0, mid=0)
s = G.Monster(0, 0, kind='그림자거미', mid=1)
u = G.Monster(0, 0, kind='낯선 것', mid=2)
check('② 몬스터 수치·도주 파라미터 — 고블린(6/2/2/12, 도주 3·8) · 그림자거미(5/3/3/13, 도주 없음=파트너 결정 09-11) · 모르는 종=기준선 몹',
      (g.hp, g.maxhp, g.atk, g.dmg, g.ac, g.flee_frac, g.flee_stamina) == (6, 6, 2, 2, 12, 3, 8)
      and (s.hp, s.atk, s.dmg, s.ac, s.flee_frac, s.flee_stamina) == (5, 3, 3, 13, None, None)
      and (u.hp, u.atk, u.dmg, u.ac) == (6, 2, 2, 12)
      and (G.FLEE_FRAC, G.FLEE_STAMINA) == (3, 8))
check('② D51 도주 방향 — 고블린 ally(합류 범위 10) · 그림자거미 flee 없음=away 0', G.Monster(0, 0, mid=5).flee_to == 'ally' and G.Monster(0, 0, mid=5).flee_join_range == 10
      and ENT.monster_flee_mode('그림자거미') == ('away', 0))
check('② 명시 수치가 정의보다 우선(장면 저작·게이트 호환)',
      G.Monster(0, 0, kind='그림자거미', atk=100, mid=3).atk == 100 and G.Monster(0, 0, hp=1, mid=4).hp == 1)

# ③ 지식 본문 이관 — 옛 lore.json 과 키·본문이 같다(D53 뒤 lore() 항목에 brief·unlock 이 얹히므로 name·lore 투영으로 잰다)
lo = ENT.lore()
check('③ 지식 본문(옛 lore.json 7건) — 키·이름·본문(deep) 해시 일치',
      canon({k: {'name': v['name'], 'lore': v['lore']} for k, v in lo.items()}) == LORE_SHA
      and set(lo) == {'monster:고블린', 'monster:그림자거미', 'trap:spike', 'trap:dart', 'trap:alarm',
                      'feature:chest', 'feature:fountain'})

# ⑧ D53 지식 3층 프리셋(파트너 09-12 "5번 조우하면 심층 — 공통 프리셋, 일단 몬스터만")
check('⑧ 몬스터 2종 = brief 한 줄 + unlock{encounter, 5} · 함정·오브젝트는 해금 조건 없음(옛 2층 그대로)',
      all(lo[k].get('brief') and lo[k].get('unlock') == {'event': 'encounter', 'count': 5} for k in ('monster:고블린', 'monster:그림자거미'))
      and not any(lo[k].get('unlock') or lo[k].get('brief') for k in lo if not k.startswith('monster:'))
      and ENT.unlock_rules() == {'monster:고블린': {'event': 'encounter', 'count': 5}, 'monster:그림자거미': {'event': 'encounter', 'count': 5}}
      and 'encounter' in ENT.UNLOCK_EVENTS
      and lo['monster:고블린']['brief'] == '겁 많은 소형 마물')   # 메모 §2-2 [제안]의 예시 문구 그대로

# ④ 마을 NPC 이관 — build_town 의 대사·선물·배치가 그대로
d, _ = show_runner.build_town(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'town-v0.json'))   # 이관 기준=옛 마을(마을 v1 채택 뒤 보존본)
npc = {'lines': d.npc_lines, 'gifts': d.npc_gifts, 'again': d.npc_lines_again,
       'features': sorted((f.type, f.name, f.x, f.y) for f in d.features.values())}
check('④ 옛 마을 NPC(대사·재방문 대사·선물·배치) 해시 일치 — town-v0.json 은 배치만, 본문은 정의', canon(npc) == NPC_SHA)
d1, _ = show_runner.build_town()
check('④ 마을 v1(layout 참조) — NPC 3(성직자·길드 접수원·주점 주인) 정의에서 합쳐짐, 접수원 선물 물약+단검',
      sorted(f.name for f in d1.features.values() if f.type == 'npc') == ['길드 접수원', '성직자', '주점 주인']
      and d1.npc_gifts.get('길드 접수원') == {'potions': 1, 'weapon': '단검'} and all(d1.npc_lines_again.get(n) for n in ('성직자', '길드 접수원', '주점 주인')))

# ⑤ 생성 층의 피처 이름 = 정의 이름
dg = G.Dungeon(seed=7, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1)
names = {(f.type, f.name) for f in dg.features.values()}
allowed = {(o['type'], o['name']) for o in ENT.by_kind('object')} | {('treasure', '숨은 보물')}
check('⑤ 생성 층 피처(type, name)가 전부 정의(+숨은 보물 변형)에 있다 — %d종' % len(names), names <= allowed and ('exit', '출구') in names)
check('⑤ 몬스터 kind 가 전부 정의에 있다', {m.kind for m in dg.monsters} <= {o['name'] for o in ENT.by_kind('monster')})

# ⑥ 조합형 관측 태그 = 정의 tags(옛 리터럴과 같다)
check('⑥ 관측 태그 — 장비·물약=object+item, 상자·계단=object, 모르는 type(마을 npc)=object',
      ENT.feature_tags('weapon') == ['object', 'item'] and ENT.feature_tags('potion') == ['object', 'item']
      and ENT.feature_tags('chest') == ['object'] and ENT.feature_tags('exit') == ['object'] and ENT.feature_tags('npc') == ['object'])

# ⑦ 검증기의 거절 — 임시 사본에 나쁜 정의를 넣으면 전부 나열하며 죽는다
with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, 'entities')
    shutil.copytree(ENT.ROOT, root)
    bad = {
        os.path.join(root, 'monster', 'orc.json'): {'id': 'orc', 'name': '오크', 'kind': 'monster', 'sprite': 'wl-orc',
                                                     'comps': {'health': {'max': 9}, 'combat': {'atk': 3, 'dmg': 3, 'ac': 12}, 'mana': {}}},
        os.path.join(root, 'trap', 'pit.json'): {'id': 'hole', 'name': '구덩이', 'kind': 'trap', 'comps': {'trap': {'dc': 12, 'dmg': 2},
                                                  'knowledge': {'deep': 'x', 'unlock': {'event': 'dance', 'count': 1}}}},
        os.path.join(root, 'object', 'goblin.json'): {'id': 'goblin', 'name': '중복', 'kind': 'object', 'type': 'x', 'comps': {}},
        os.path.join(root, 'object', 'relic.json'): {'id': 'relic', 'name': '유물', 'kind': 'object', 'type': 'relic',
                                                     'comps': {'knowledge': {'unlock': {'event': 'encounter'}}}},   # count·deep 결손(D53)
        os.path.join(root, 'monster', 'imp.json'): {'id': 'imp', 'name': '임프', 'kind': 'monster', 'sprite': 'wl-goblin',
                                                    'comps': {'health': {'max': 4}, 'combat': {'atk': 1, 'dmg': 1, 'ac': 10},
                                                              'knowledge': {'deep': 'x', 'unlock': {'event': 'encounter', 'count': 2},
                                                                            'review': {'event': 'encounter'}}}},   # review count 결손(D55)
    }
    for p, d in bad.items():
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False)
    try:
        ENT.read(root)
        rejected, msg = False, ''
    except ENT.EntityError as e:
        rejected, msg = True, str(e)
    check('⑦ 검증기 거절 — 모르는 부품·없는 텍스처·id≠파일명·없는 해금 사건·중복 id·해금 count/deep 결손·review 결손(D55)을 한 번에 나열',
          rejected and '모르는 부품' in msg and '스프라이트' in msg and '파일명' in msg and '해금 사건' in msg and '중복' in msg
          and 'count(정수≥1)' in msg and '해금할 본문' in msg and 'knowledge.review' in msg)
check('⑦ 정본 폴더는 재로드해도 같은 정의', ENT.reload() == defs)

print('ALL PASS — verify_entities (%d checks, 실 LLM 0콜)' % checks)
