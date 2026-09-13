# -*- coding: utf-8 -*-
"""마을(D29, 2026-07-30) 헤들리스 검증 — 32번째 게이트.
마을(0층)↔던전(1층) 왕복: 손그림 고정 마을 + NPC 3 + 전체 시야 + 계단 대칭('<') +
층 보존(재입장=같은 1층) + 1층 아래 계단=관측 클리어(파트너 확정).
게이트:
  ① build_town: 맵·NPC 3(장비·아이템·여관주인)·인사·'던전 입구' 개명 / 좌표-그림 어긋남=즉사
     / **D29 개정(09-06)**: 러너 스위치 미러링(hail·wait·motion·events·graves·ally_sight·social·trail·objtags) — selfstop·dry 는 마을 제외
  ② 전체 시야: visible_cells=전맵 / obs.town / 수색·탐색 옵션 부재(거짓 라벨 방지) / 마을 라벨
  ③ NPC: 몸이 막는다(walkable) / 기존 판(obs)에 town 키 없음 / **D32 상점 v0(09-05)**: 장비 상인=빈손이면
     단검 1회(npc_gift)·무장한 채 첫 방문=인사 / 아이템 상인=물약 1개 / **두 번째부터(09-06 개정, npc_met)=
     '아까 왔잖아' line_again + again:true — 선물 여부와 무관, 여관주인 포함** / 동료 목격 ally_loot /
     방문 단위 리셋(재스폰 dict: shop_served·npc_met 없음)
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
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"  # 빈 응답 스텁은 명시적인 엔진 테스트로 실행
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
check("① D29 개정(09-06): build_town 이 러너 스위치를 미러링(hail·wait·motion·events·graves·ally_sight·social·trail·objtags) · selfstop·dry 는 마을 제외",
      (d.hail, d.wait_verb, d.motion, d.events, d.graves, d.ally_sight, d.social, d.trail_on, d.objtags)
      == (show_runner.HAIL_ON, show_runner.WAIT_ON, show_runner.MOTION_ON, show_runner.EVENTS_ON,
          show_runner.GRAVES_ON, show_runner.ALLY_SIGHT_ON, show_runner.SOCIAL_ON, show_runner.TRAIL_ON,
          show_runner.OBJTAGS_ON)
      and d.hail and d.wait_verb and d.events and d.trail_on and d.objtags
      and d.selfstop is False and d.dry_signal is False)
npcs = sorted(f.name for f in d.features.values() if f.type == 'npc')
check("① 마을 전체 맵 — 공간 엔티티에서 만든 53×39 격자·출발 3·정식 던전 입구",
      d.town and d.w == 53 and d.h == 39 and len(starts) == 3 and d.exit == (41, 30)
      and len(d.layout_result['spaces']['regions']) == 6)
check("① NPC 3 — 성직자·길드 접수원·주점 주인(entities/npc, 대사는 임시 초안), 전원 인사 보유",
      npcs == ['길드 접수원', '성직자', '주점 주인']
      and all(d.npc_lines.get(n) for n in npcs))
check("① 같은 '>'라도 마을에선 '던전 입구'다(개명)",
      d.features[d._exit_fid].name == '던전 입구')
gr = next(f for f in d.features.values() if f.type == 'npc' and f.name == '길드 접수원')
b_g = mkbot('1', gr.x, gr.y + 1)
r_g = d._interact(b_g, 'f%d' % gr.id, [b_g])
check("① 길드 접수원 = 기본 물품(메모 §4-4): 빈손이면 물약 1 + 단검 함께(npc_gift item '물약·단검')",
      r_g['result'] == 'npc_gift' and r_g['item'] == '물약·단검' and b_g['potions'] == 1 and b_g['weapon']['name'] == '단검')
r_g2 = d._interact(b_g, 'f%d' % gr.id, [b_g])
check("① 접수원 두 번째 = 재방문 대사·중복 지급 없음",
      r_g2['result'] == 'npc_talk' and r_g2.get('again') is True and b_g['potions'] == 1)
# ②③ 상점 v0 물리(장비·아이템 상인·여관주인)는 옛 손그림 마을(town-v0.json)에서 계속 검증한다 — 정의·선물 규칙은 그대로 살아 있다
d, starts = show_runner.build_town(os.path.join(show_runner.HERE, 'town-v0.json'))
npcs = sorted(f.name for f in d.features.values() if f.type == 'npc')
check("① 옛 마을(town-v0.json) — 31×12·상점 NPC 3 보존",
      d.town and d.w == 31 and d.h == 12 and npcs == ['아이템 상인', '여관주인', '장비 상인'])

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
      and {k: b_adj.get('weapon', {}).get(k) for k in ('name', 'bonus')} == {'name': '단검', 'bonus': 1}   # D57: 선물 장비도 개체(id·worn 추가)
      and isinstance(b_adj['weapon'].get('id'), int) and b_adj['weapon'].get('worn') == [b_adj['char']] and '단검' in r['line'])
r2 = d._interact(b_adj, 'f%d' % nf.id, [b_adj])
check("③ 두 번째 말 걸기 = '아까 왔잖아' 고정 대사(line_again)·again 표식 — 무기 중복 지급 없음",
      r2['result'] == 'npc_talk' and '무장' in r2['line'] and '아까 왔잖아' in r2['line']
      and r2.get('again') is True and b_adj['weapon']['name'] == '단검')
b_armed = mkbot('9', nf.x, nf.y + 1)
b_armed['weapon'] = {'name': '장검', 'bonus': 2}
r2b = d._interact(b_armed, 'f%d' % nf.id, [b_armed])
check("③ 무장한 채 첫 방문 = 인사(line)·선물 없음·again 없음 — 방문 여부와 선물 여부는 다른 사실(09-06 개정)",
      r2b['result'] == 'npc_talk' and '아까' not in r2b['line'] and 'again' not in r2b
      and b_armed['weapon']['name'] == '장검')
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
r6 = d._interact(b_i, 'f%d' % nf_inn.id, [b_i])
check("③ 여관주인 두 번째 = '아까 왔잖아'(선물 없는 NPC 도 방문 대사) · npc_met 방문 장부는 재스폰에 없다",
      r6['result'] == 'npc_talk' and '아까 왔잖아' in r6['line'] and r6.get('again') is True
      and 'npc_met' not in G.spawn(d, '6', [], sheet=G.HEROES['1']))
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
check("⑤ 마을 v1 level 에 시각 레이어(visual: town-visual-v1 — 바닥 사각형·건물·소품·NPC 행) 실림, 던전 층엔 없음",
      levels[0].get('visual', {}).get('schema') == 'town-visual-v1' and {b['texture'] for b in levels[0]['visual']['buildings']} == {'guild','temple','tavern','gate'}
      and len(levels[0]['visual']['npcs']) == 3 and 'visual' not in levels[1])
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

# ── ⑧ layout 원본(town-layout-v1) → from_layout · town.json 의 layout 참조 — 09-11 파트너 결정 "아스키를 손으로 그릴 필요는 없다" ──
import json as _json, os as _os, tempfile as _tempfile, town_layout as _TL
lay8 = {"schema": "town-layout-v1", "size": [7, 5], "tileSize": 48, "border": 1,
        "blocked_rects": [{"id": "hut", "rect": [1, 0, 3, 2]}],
        "entrances": [{"id": "hut_door", "cell": [2, 1], "kind": "threshold"}],
        "starts": {"1": [0, 3], "2": [1, 3], "3": [2, 3]},
        "dungeon_entry": {"cell": [6, 4], "placeholder": True},
        "npcs": [{"id": "innkeeper", "cell": [5, 2], "row": 0}]}
res8 = _TL.compile_layout(lay8)
d8, st8 = G.Dungeon.from_layout(lay8, seed=1, depth=0)
check("⑧ from_layout: 다섯 필드 → 격자 = from_ascii 판정(벽·출발·입구 좌표 일치, border 적용), layout_result 보존",
      {k: list(v) for k, v in st8.items()} == res8["starts"] and list(d8.exit) == res8["dungeon_entry"]
      and d8.grid[1][2] == G.WALL and d8.grid[2][3] != G.WALL and d8.layout_result["npcs"] == [{"id": "innkeeper", "x": 6, "y": 3}])
with _tempfile.TemporaryDirectory() as tmp8:
    with open(_os.path.join(tmp8, "lay.json"), "w", encoding="utf-8") as f:
        _json.dump(lay8, f, ensure_ascii=False)
    with open(_os.path.join(tmp8, "town.json"), "w", encoding="utf-8") as f:
        _json.dump({"layout": "lay.json"}, f)
    d8b, st8b = show_runner.build_town(_os.path.join(tmp8, "town.json"))
check("⑧ town.json {layout: 상대경로} → build_town: layout 격자·NPC 정의(innkeeper) 합침·'던전 입구' 개명·출발 3",
      d8b.town and d8b.npc_lines.get("여관주인") and len(st8b) == 3 and d8b.features[d8b._exit_fid].name == "던전 입구"
      and any(f.type == "npc" and f.name == "여관주인" and (f.x, f.y) == (6, 3) for f in d8b.features.values()))

# ───────────────────── ⑨ 마을 관측(D60) ─────────────────────
print("── ⑨ 마을 관측(D60, 09-12 파트너 '마을에서는 관측 정보를 느슨하게') — 건물 피처·구역 이름")
import brains as _brains
import dungeon_gm as _G
d8, starts8 = show_runner.build_town()
blds = {f.name: f for f in d8.features.values() if f.type == 'building'}
ent_cells = {tuple(e['cell']) for e in d8.layout_result['entrances']}
check("⑨ 건물 피처 3 = 신전·모험가 길드·주점(던전 입구 건물은 문턱이 '>' 곁이라 제외) · 자리 = 문턱 칸(바닥)",
      set(blds) == {'신전', '모험가 길드', '주점'}
      and all((f.x, f.y) in ent_cells and d8.grid[f.y][f.x] == _G.FLOOR for f in blds.values())
      and d8.exit not in {(f.x, f.y) for f in blds.values()})
sx, sy = starts8['1']
b8 = mkbot('1', sx, sy)
o8 = d8.view(b8, [b8])
bf = [f for f in o8['sights']['features'] if f['type'] == 'building']
check("⑨ 출발 자리 관측: 건물 셋이 방위·거리와 함께 보이고 town_zone='번화가'",
      {f['name'] for f in bf} == {'신전', '모험가 길드', '주점'} and o8.get('town_zone') == '번화가'
      and all(f.get('bearing') and isinstance(f.get('dist'), int) and f['dist'] > 0 for f in bf))
w8 = _brains._wire(o8, {'1': '두란'})
check("⑨ 렌더: '지금 있는 곳: 번화가' + '신전 f<n>' 줄",
      '지금 있는 곳: 번화가' in w8 and any('신전 f' in ln for ln in w8.splitlines()))
tid = 'f%d' % blds['신전'].id
r8 = d8.act(b8, {'type': 'goto', 'target': tid}, [b8])
check("⑨ goto 건물 = 문턱까지 경로(pathed) · 동료 관측 doing 이름 '신전'",
      r8.get('result') == 'pathed' and d8._ally_doing(b8) == {'act': 'goto', 'target': tid, 'name': '신전'})
t8 = blds['신전']
b8b = mkbot('2', t8.x, t8.y)
o8b = d8.view(b8b, [b8b])
opts8 = [(o.get('type'), o.get('target')) for o in (o8b.get('options') or o8b.get('menu') or [])]
check("⑨ 문턱에 서면 town_zone='신전 지구' · 건물엔 상호작용 옵션 없음(goto 뿐) · use 는 nothing",
      o8b.get('town_zone') == '신전 지구' and ('interact', tid) not in opts8
      and d8._interact(b8b, tid, [b8b]).get('result') == 'nothing')
show_runner.TOWN_BUILDINGS_ON = False
d8x, _ = show_runner.build_town()
show_runner.TOWN_BUILDINGS_ON = True
check("⑨ 스위치 끄면 건물 피처 없음(NPC 3·입구 그대로) · town_zone 은 그대로(구역은 layout 의 사실)",
      not any(f.type == 'building' for f in d8x.features.values())
      and sum(1 for f in d8x.features.values() if f.type == 'npc') == 3
      and d8x.view(mkbot('1', sx, sy), [mkbot('1', sx, sy)]).get('town_zone') == '번화가')

# ───────────────────── ⑩ 건물 역할 부품(D61) ─────────────────────
print("── ⑩ 건물 역할 부품(D61, 09-12 파트너 '신탁 소켓·퀘스트 게시판') — 정보만")
d10, s10 = show_runner.build_town()
gd = next(f for f in d10.features.values() if f.type == 'building' and f.name == '모험가 길드')
tp = next(f for f in d10.features.values() if f.type == 'building' and f.name == '신전')
far = mkbot('1', *s10['1'])
check("⑩ 출발 자리(문턱에서 멀다)엔 notices 없음", not d10.view(far, [far]).get('notices'))
nb = mkbot('1', gd.x, gd.y + 1)                                  # 길드 문턱 앞 1칸
o_nb = d10.view(nb, [nb])
bd = [n for n in (o_nb.get('notices') or []) if n['kind'] == 'board']
check("⑩ 길드 문턱 곁: 게시판 notice 하나 — 의뢰 3(제목·목표·보상), 신탁 없음",
      len(bd) == 1 and [q['id'] for q in bd[0]['quests']] == ['goblin_cull', 'reach_floor_2', 'lost_trinket']
      and all(q.get('title') and q.get('goal') and q.get('reward') for q in bd[0]['quests'])
      and not any(n['kind'] == 'oracle' for n in o_nb['notices']))
w10 = _brains._wire(o_nb, {'1': '두란'})
check("⑩ 렌더: 게시판 줄에 의뢰 제목·목표(맡으라는 말 없음)", '게시판' in w10 and '고블린 소탕' in w10 and '셋 처치' in w10 and '맡아라' not in w10)
d10.oracle = None
ot = mkbot('2', tp.x, tp.y + 1)
check("⑩ 신전 문턱 곁, 신탁 없음 → oracle notice 없음", not any(n['kind'] == 'oracle' for n in (d10.view(ot, [ot]).get('notices') or [])))
d10.oracle = {'id': 'o1', 'text': '오늘은 2층까지만 가거라', 'turn': 3}
o_t1 = d10.view(ot, [ot])
orn = [n for n in o_t1['notices'] if n['kind'] == 'oracle']
w_t1 = _brains._wire(o_t1, {'2': '카야'})
check("⑩ 신탁 있음 → oracle notice{id,text} · 렌더 '신의 요청' + oracle_reply 안내 + '명령이 아니다'",
      len(orn) == 1 and orn[0]['id'] == 'o1' and orn[0]['text'] == '오늘은 2층까지만 가거라'
      and '신의 요청' in w_t1 and 'oracle_reply' in w_t1 and '명령이 아니다' in w_t1)
roster10 = [{'char': '2', 'name': '카야'}]
dec10 = _brains._parse_decision('{"reason":"r","type":"wait","oracle_reply":"알겠습니다, 신이시여"}', '', o_t1, '2', roster10)   # 반환 = 결정 dict(오류면 type 없음)
check("⑩ 응답 oracle_reply → decision.oracle_reply{id,text}",
      isinstance(dec10, dict) and dec10.get('oracle_reply') == {'id': 'o1', 'text': '알겠습니다, 신이시여'})
ot['oracle_replies'] = {'o1': '알겠습니다, 신이시여'}
o_t2 = d10.view(ot, [ot])
dec10b = _brains._parse_decision('{"reason":"r","type":"wait","oracle_reply":"또 답"}', '', o_t2, '2', roster10)
check("⑩ 답한 뒤: notice 에 replied 동봉·렌더 '이미 답했다' · 같은 신탁에 두 번째 답은 안 받는다",
      [n for n in o_t2['notices'] if n['kind'] == 'oracle'][0].get('replied') == '알겠습니다, 신이시여'
      and '이미 답했다' in _brains._wire(o_t2, {'2': '카야'}) and not (dec10b or {}).get('oracle_reply'))
show_runner.NOTICES_ON = False
d10x, _ = show_runner.build_town()
show_runner.NOTICES_ON = True
d10x.oracle = None                     # 스위치 끄면 러너가 신탁을 읽지 않는다(d.oracle=None, ⑪ 소스 검사) — 09-13 개정: 신탁은 건물과 무관하게 들린다
check("⑩ 스위치 끄면(NOTICES_ON=0) 게시판 없음(건물 정의 안 실림)·신탁은 러너가 안 읽음(건물 피처는 그대로)",
      not d10x.view(mkbot('1', gd.x, gd.y + 1), []).get('notices') and any(f.type == 'building' for f in d10x.features.values()))

print("── ⑪ 신탁은 어디서나(D61 개정, 09-13 파트너 '플레이 중에 신탁을 내릴 수 있게')")
d11, st11 = show_runner.G.Dungeon.from_ascii(["############", "#1........>#", "############"], seed=7)
b11 = mkbot('1', *st11['1'])
d11.oracle = None
check("⑪ 던전 층, 신탁 없음 → notices 없음", not d11.view(b11, [b11]).get('notices'))
d11.oracle = {'id': 'o9', 'text': '보물보다 목숨을 아껴라', 'turn': 5}
o11 = d11.view(b11, [b11])
n11 = [n for n in (o11.get('notices') or []) if n['kind'] == 'oracle']
w11 = _brains._wire(o11, {'1': '두란'})
check("⑪ 던전 층에서도 oracle notice{where sky, id, text} · 건물 없음", len(n11) == 1 and n11[0].get('where') == 'sky' and 'building' not in n11[0]
      and n11[0]['id'] == 'o9' and n11[0]['text'] == '보물보다 목숨을 아껴라')
check("⑪ 렌더: '신의 요청이 들려온다' + '명령이 아니다' + oracle_reply 안내, 자리 말('앞') 없음",
      '신의 요청이 들려온다: 「보물보다 목숨을 아껴라」' in w11 and '명령이 아니다' in w11 and 'oracle_reply' in w11 and '신전 앞' not in w11)
dec11 = _brains._parse_decision('{"reason":"r","type":"search","target":"self","oracle_reply":"목숨이 먼저지"}', '', o11, '1', [{'char': '1', 'name': '두란'}])
check("⑪ 던전 층에서 답 → decision.oracle_reply{id,text}", isinstance(dec11, dict) and dec11.get('oracle_reply') == {'id': 'o9', 'text': '목숨이 먼저지'})
b11['oracle_replies'] = {'o9': '목숨이 먼저지'}
w11b = _brains._wire(d11.view(b11, [b11]), {'1': '두란'})
check("⑪ 답한 뒤 '이미 답했다'", '이미 답했다: 「목숨이 먼저지」' in w11b)
src_r = open(os.path.join(HERE, 'show_runner.py'), encoding='utf-8').read()
check("⑪ 러너: 어느 층에서나 읽는다 · tick.oracle(새 요청) · 🔮 줄", 'd.oracle = read_oracle() if NOTICES_ON else None' in src_r
      and '"oracle": oracle_new' in src_r and '신의 요청이 들려온다(전원에게)' in src_r)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_town (D29 마을: 전체 시야·NPC·계단 대칭·층 보존·관측 클리어 · ⑨ D60 마을 관측 · ⑩ D61 게시판·신탁)")
