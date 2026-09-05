# -*- coding: utf-8 -*-
"""마을(D29, 2026-07-30) 헤들리스 검증 — 32번째 게이트.
마을(0층)↔던전(1층) 왕복: 손그림 고정 마을 + NPC 3 + 전체 시야 + 계단 대칭('<') +
층 보존(재입장=같은 1층) + 1층 아래 계단=관측 클리어(파트너 확정).
게이트:
  ① build_town: 맵·NPC 3(장비·아이템·여관주인)·인사·'던전 입구' 개명 / 좌표-그림 어긋남=즉사
  ② 전체 시야: visible_cells=전맵 / obs.town / 수색·탐색 옵션 부재(거짓 라벨 방지) / 마을 라벨
  ③ NPC: 몸이 막는다(walkable) / 기존 판(obs)에 town 키 없음 / **D32 상점 v0(09-05)**: 장비 상인=빈손이면
     단검 1회(npc_gift)·무장했으면 대사만 / 아이템 상인=물약 1개·같은 방문 두 번째는 대사만 / 동료 목격
     ally_loot / 방문 단위 리셋(재스폰 dict) / 여관주인=인사만
  ④ 계단 대칭(엔진 장면): stairs_up 모임 규칙(wait_allies→ascend·went=up) / 솔로 혼자 상행
     + 모임 동의=의사(08-09 셔틀 부검): 곁이어도 딴 작정=busy(안 끌려감) / 계단 목표·동행=동의
  ⑤ [러너 풀런] 왕복: 마을→1층→마을→1층→클리어 — ascend 레코드·depth 열·같은 1층(시드·격자·
     '<' 보존)·run_meta.town·outcome
  ⑥ 결정론: 러너 2회 = started 제외 라인 동일
  ⑦ 솔로+마을 v0 거부(행선 분기 미지원 — 정직한 즉사)
(기존 verify 31종은 별도 실행.)
"""
import io
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="400", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="1", DUNGEON_TRAPS="0",
                  DUNGEON_LURKERS="0",
                  DUNGEON_TOWN="1",                    # 마을 판 — DEPTHS 기본 1(1층 계단=클리어)
                  DUNGEON_PARTY_FILE="/nonexistent",   # 내장 2인 고정(회귀 그물)
                  DUNGEON_STATE_DIR=os.path.join(HERE, "state_townverify"))
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)
os.environ.pop("DUNGEON_DEPTHS", None)
os.environ.pop("DUNGEON_SOLO", None)

import brains
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
import dungeon_gm as G
import show_runner
show_runner.STEP_DELAY = 0
import time as _time
_time.sleep = lambda s: None

SPATH = os.path.join(show_runner.STATE, "stream.jsonl")


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'potions': 0, 'weapon': None, 'armor': None,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set()}


# ───────────────────── ① build_town ─────────────────────
print("── ① build_town")
d, starts = show_runner.build_town()
npcs = sorted(f.name for f in d.features.values() if f.type == 'npc')
check("① 마을 로드 — town 스위치·손그림 격자·출발 표기",
      d.town and d.w == 31 and d.h == 12 and starts.get('1') is not None)
check("① NPC 3 — 장비·아이템·여관주인(파트너 확정), 전원 인사 보유",
      npcs == ['아이템 상인', '여관주인', '장비 상인']
      and all(d.npc_lines.get(n) for n in npcs))
check("① 같은 '>'라도 마을에선 '던전 입구'다(개명)",
      d.features[d._exit_fid].name == '던전 입구')

# ───────────────────── ② 전체 시야 ─────────────────────
print("── ② 전체 시야")
b1 = mkbot('1', *starts['1'])
check("② 고향은 다 아는 곳 — visible_cells = 맵 전부",
      len(d.visible_cells(*starts['1'])) == d.w * d.h)
obs = d.view(b1, [b1])
check("② obs.town 사실 + NPC 전원이 첫 obs 에 등장(전체 가시)",
      obs.get('town') is True
      and sorted(f['name'] for f in obs['sights']['features'] if f['type'] == 'npc') == npcs)
labels = [o['label'] for o in obs['options']]
check("② 수색·탐색 동사 부재 — 전부 보이는 곳에서 '벽 뒤·시야 밖' 라벨은 거짓",
      not any(o['type'] in ('search', 'explore') for o in obs['options']))
check("② 던전 입구 라벨(이동) + NPC 이동 라벨",
      any('던전 입구' in l for l in labels)
      and any('장비 상인' in l for l in labels))
nf = next(f for f in d.features.values() if f.type == 'npc' and f.name == '장비 상인')
b_adj = mkbot('1', nf.x, nf.y + 1)
obs_adj = d.view(b_adj, [b_adj])
check("② 곁의 NPC = '말 걸기' 라벨",
      any(o['type'] == 'interact' and '말 걸기' in o['label'] and nf.name in o['label']
          for o in obs_adj['options']))

# ───────────────────── ③ NPC 물리·기존 판 불변 ─────────────────────
print("── ③ NPC")
check("③ NPC 몸이 막는다 — walkable 불가(밟고 지나갈 수 없다)",
      not d.walkable(nf.x, nf.y, []))
r = d._interact(b_adj, 'f%d' % nf.id, [b_adj])
check("③ 장비 상인(D32 상점 v0): 빈손이면 첫 말 걸기에 단검 — npc_gift·item·정해진 대사·바로 걸침",
      r['result'] == 'npc_gift' and r['npc'] == '장비 상인' and r['item'] == '단검'
      and b_adj.get('weapon') == {'name': '단검', 'bonus': 1} and '단검' in r['line'])
r2 = d._interact(b_adj, 'f%d' % nf.id, [b_adj])
check("③ 이미 무장했으면 다시 말 걸어도 대사만(line_again) — 무기 중복 지급 없음",
      r2['result'] == 'npc_talk' and '무장' in r2['line'] and b_adj['weapon']['name'] == '단검')
pf = next(ff for ff in d.features.values() if ff.type == 'npc' and ff.name == '아이템 상인')
b_p = mkbot('2', pf.x, pf.y + 1)
b_w = mkbot('3', pf.x + 3, pf.y + 1)
d.events = True                                   # 마을=전체 시야 — 받는 장면은 동료가 본다
r3 = d._interact(b_p, 'f%d' % pf.id, [b_p, b_w])
check("③ 아이템 상인: 물약 1개 — npc_gift·potions 1·정해진 대사",
      r3['result'] == 'npc_gift' and r3['item'] == '물약' and b_p.get('potions') == 1 and '물약' in r3['line'])
r4 = d._interact(b_p, 'f%d' % pf.id, [b_p, b_w])
check("③ 같은 방문의 두 번째 말 걸기 = 대사만(line_again), 물약은 그대로 1",
      r4['result'] == 'npc_talk' and b_p.get('potions') == 1 and '몫' in r4['line'])
check("③ 동료가 받는 걸 본다 — ally_loot{what=물약} 1건, 당사자 제외",
      len([w for w in (b_w.get('witnessed') or []) if w.get('kind') == 'ally_loot' and w.get('what') == '물약']) == 1
      and not b_p.get('witnessed'))
check("③ 방문 단위 리셋 — 층 전이의 재스폰(새 봇 dict)엔 shop_served 가 없다(살아 돌아오면 또 하나)",
      'shop_served' not in G.spawn(d, '4', [], sheet=G.HEROES['1']))
nf_inn = next(ff for ff in d.features.values() if ff.type == 'npc' and ff.name == '여관주인')
b_i = mkbot('5', nf_inn.x, nf_inn.y + 1)
r5 = d._interact(b_i, 'f%d' % nf_inn.id, [b_i])
check("③ 여관주인: 선물 없음 — npc_talk 인사만(회복은 다음 단계)",
      r5['result'] == 'npc_talk' and '방' in r5['line'] and 'shop_served' in b_i and not b_i['shop_served'])
d0 = G.Dungeon(seed=7)
b0 = mkbot('1', 1, 1)
b0['x'], b0['y'] = next((x, y) for y in range(d0.h) for x in range(d0.w)
                        if d0.grid[y][x] == G.FLOOR and not d0.feature_at(x, y)
                        and not d0.monster_at(x, y))
obs0 = d0.view(b0, [b0])
check("③ 기존 판 불변 — town 끈 obs 엔 town 키 자체가 없다",
      'town' not in obs0)

# ───────────────────── ④ 계단 대칭(엔진 장면) ─────────────────────
print("── ④ 계단 대칭")
rows2 = ['##########',
         '#1.<.....#',
         '#......2.#',
         '#....>...#',
         '##########']
da, sta = G.Dungeon.from_ascii(rows2, seed=7)
ba, bb = mkbot('1', 2, 1), mkbot('2', 7, 2)
uid = next('f%d' % f.id for f in da.features.values() if f.type == 'stairs_up')
r = da._interact(ba, uid, [ba, bb])
check("④ 상행도 모임 규칙 — 안 모이면 wait_allies(빠진 동료 명단)",
      r['result'] == 'wait_allies' and r['missing'] == ['2'])
bb['x'], bb['y'] = 4, 1
r = da._interact(ba, uid, [ba, bb])
check("④ 모이면 함께 상행 — ascend·전원 won·went=up",
      r['result'] == 'ascend' and r['party'] == ['1', '2']
      and ba['won'] and bb['won']
      and ba['went'] == 'up' and bb['went'] == 'up')
ds, sts = G.Dungeon.from_ascii(rows2, seed=7)
ds.solo = True
bs = mkbot('1', 2, 1)
uid = next('f%d' % f.id for f in ds.features.values() if f.type == 'stairs_up')
r = ds._interact(bs, uid, [bs, mkbot('2', 7, 2)])
check("④ 솔로 판 — 혼자 올라간다(모임 조건 없음)",
      r['result'] == 'ascend' and r['party'] == ['1'] and bs['went'] == 'up')
dv, _ = G.Dungeon.from_ascii(rows2, seed=7)
uid = next('f%d' % f.id for f in dv.features.values() if f.type == 'stairs_up')
bv, bw = mkbot('1', 2, 1), mkbot('2', 4, 1)
bw['order'], bw['path'] = '@7,2', [(5, 1)]        # 곁이지만 탐색 작정이 살아 있다
r = dv._interact(bv, uid, [bv, bw])
check("④ 동의는 위치가 아니라 의사(08-09) — 곁이어도 딴 작정이면 busy(안 끌려감)",
      r['result'] == 'wait_allies' and r['missing'] == [] and r['busy'] == ['2']
      and r['dir'] == 'up' and not bw['won'])
bw['order'], bw['path'] = uid, []                  # 작정이 이 계단 자체 = 동의
r = dv._interact(bv, uid, [bv, bw])
check("④ 이 계단이 목표인 작정 = 동의 — 함께 상행",
      r['result'] == 'ascend' and r['party'] == ['1', '2'])
df, _ = G.Dungeon.from_ascii(rows2, seed=7)
uid = next('f%d' % f.id for f in df.features.values() if f.type == 'stairs_up')
bf, bg = mkbot('1', 2, 1), mkbot('2', 4, 1)
bg['order'] = 'follow:b1'                          # 동행 — 따라가는 상대가 동의 무리 안
r = df._interact(bf, uid, [bf, bg])
check("④ 동행은 함께 간다 — follow:리더 = 동의(연쇄)",
      r['result'] == 'ascend' and r['party'] == ['1', '2'])
de, _ = G.Dungeon.from_ascii(rows2, seed=7)
be, bh = mkbot('1', 5, 3), mkbot('2', 4, 1)       # '>' 위 + 반경 안 동료
bh['order'] = '@7,2'
r = de._interact(be, 'exit', [be, bh])
check("④ 하강도 같은 문법 — 딴 작정 동료는 busy(dir=down)",
      r['result'] == 'wait_allies' and r['busy'] == ['2'] and r['dir'] == 'down')

# ───────────────────── ⑤ 러너 풀런 — 왕복 + 클리어 ─────────────────────
print("── ⑤ 러너 왕복 풀런(LLM 0콜 — 각본 두뇌)")
SEQ = {'up_done': False}
_real_dummy = G.dummy_brain


def scripted(obs, char='?'):
    """왕복 각본: 마을=입구로(기본 더미가 그렇게 한다) → 1층 첫 방문='<'로 올라가 마을 →
    다시 입장 → '>'로 클리어. 마을로 돌아온 순간 up_done 이 선다."""
    if obs.get('town') and SEQ['up_done'] is None:
        SEQ['up_done'] = True                  # 1층을 봤다가 마을로 돌아왔다 — 다음 1층행은 클리어행
    if obs.get('depth') == 1 and not obs.get('town'):
        if not SEQ['up_done']:
            SEQ['up_done'] = None              # 1층 목격 표시(마을 복귀 때 True 로)
        if SEQ['up_done'] is not True:
            up = next((f for f in obs['sights']['features'] if f['type'] == 'stairs_up'), None)
            if up:
                return {'type': 'interact' if up['adj'] else 'goto', 'target': up['id']}
            if char != '1':                    # '<'가 벽에 가려 안 보이면 1번 곁으로(각본 수렴 —
                return {'type': 'goto', 'target': 'b1'}   # 실측: 봇2가 '>'로 새서 두 계단 교착)
    return _real_dummy(obs, char)


def run_once():
    SEQ['up_done'] = False
    G.dummy_brain = scripted
    try:
        show_runner.main()
    finally:
        G.dummy_brain = _real_dummy
    with io.open(SPATH, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


recs = run_once()
kinds = [r['kind'] for r in recs]
levels = [r for r in recs if r['kind'] == 'level']
end = recs[-1]
check("⑤ 왕복 열 — 마을(0)→1층→마을(0)→1층 (level depth 열)",
      [l['depth'] for l in levels] == [0, 1, 0, 1])
check("⑤ ascend 레코드(additive) — to_depth 0", any(
      r['kind'] == 'ascend' and r['to_depth'] == 0 for r in recs))
check("⑤ run_meta.town + descend 2회(입장·재입장)",
      recs[0]['kind'] == 'run_meta' and recs[0].get('town') is True
      and kinds.count('descend') == 2)
d1a, d1b = levels[1], levels[3]
check("⑤ 재입장 = 같은 1층 — 층 시드·격자 동일 + '<' 보존(세계가 이어진다)",
      d1a['level_seed'] == d1b['level_seed'] and d1a['grid'] == d1b['grid']
      and all(any(f['type'] == 'stairs_up' for f in lv['features']) for lv in (d1a, d1b)))
check("⑤ 마을 level — NPC 3 실림(관전자 등급 진실)",
      sum(1 for f in levels[0]['features'] if f['type'] == 'npc') == 3)
check("⑤ 클리어 — 아래 계단으로 전원 하강(outcome=escaped, depth 1)",
      end['kind'] == 'end' and end['outcome'] == 'escaped' and end['depth'] == 1)

# ───────────────────── ⑥ 결정론 ─────────────────────
print("── ⑥ 결정론")


def lines_once():
    run_once()
    with io.open(SPATH, encoding='utf-8') as f:
        return [l for l in f if l.strip() and '"run_meta"' not in l]


check("⑥ 러너 2회 = started 제외 라인 동일", lines_once() == lines_once())

# ───────────────────── ⑦ 솔로+마을 거부 ─────────────────────
print("── ⑦ 솔로+마을")
show_runner.SOLO_ON = True
try:
    show_runner.main()
    rejected = False
except SystemExit as e:
    rejected = '솔로+마을' in str(e)
finally:
    show_runner.SOLO_ON = False
check("⑦ 솔로+마을 v0 = 시작 전 정직한 거부(행선 분기 미지원)", rejected)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_town (D29 마을: 전체 시야·NPC·계단 대칭·층 보존·관측 클리어)")
