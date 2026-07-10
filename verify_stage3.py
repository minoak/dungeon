# -*- coding: utf-8 -*-
"""Stage 3+4 헤들리스 검증 — 직업 인지·함정 패밀리·매복(concealed)·FLEEING·방콘텐츠·하강 조율.
게이트:
  ① 직업 인지: 도적(반경2·DEX+3) ≫ 전사(반경1) — 수동(걸으며 굴림)·능동(search=확정) 분리
  ② 함정 패밀리: 가시/독침/경보 — 경보=층의 비은닉 몹 justAlerted(굴림 우회), 매복몹은 제외
  ③ 매복몹(concealed): 봇 obs·시야에 안 나감 / 자동보행 안 멈춤 / 인접 일격=they-ambush 발화(from_hiding)
  ④ FLEEING: 저HP 도주 → 협공=궁지(진동 없음) → 탈진=필사 반전(desperate) — livelock 근절
  ⑤ 방콘텐츠: 상자/샘 도박, 숨은 보물(인지로만)
  ⑥ 하강 조율: 계단=interact, 파티 전원 반경 내 모여야(wait_allies/동반 하강) — 솔로탈출 방지
  ⑦ 러너 통합: 2층 강하 스모크(LLM 무력화) — '지하 2층' 전이 + 종료
  ⑧ [300시드] 전 콘텐츠 ON 풀게임 항상 종료 + 신규 메커니즘 실발화 + 결정론
"""
import io
import os
import contextlib
from dungeon_gm import (Dungeon, Monster, Trap, spawn, dummy_brain,
                        PASSIVE_DC, LURK_DC, CAREFUL_BONUS, FLEE_STAMINA, EXIT_GATHER)


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, str_=3, dex=0, wdmg=4, stealth=0, search_r=1, job='전사'):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
            'str': str_, 'dex': dex, 'wdmg': wdmg, 'stealth': stealth,
            'search_r': search_r, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set()}


def arena(seed=1, w=20, h=12):
    """가장자리만 벽, 콘텐츠 없는 빈 방. 출구 피처만 구석에 치워 둔다."""
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


# ── ① 직업 인지: 능동 search = 반경 내 확정 / 수동 = 굴림(도적 우위) ──
d = arena()
d.traps = [Trap(7, 5, kind='spike')]                     # 봇 (5,5) 기준 dist 2
war = mkbot('1', 5, 5, dex=0, search_r=1)
rog = mkbot('2', 5, 5, dex=3, search_r=2, job='도적')
r_w = d._search(war)
check("능동 search: 전사(반경1)는 dist2 함정을 못 본다", d.traps[0].hidden and r_w['found'] == [])
r_r = d._search(rog)
check("능동 search: 도적(반경2)은 dist2 함정 확정 발견", not d.traps[0].hidden
      and len(r_r['found']) == 1 and r_r['found'][0]['kind'] == 'trap')
d.traps[0].hidden = True
d.traps[0].x, d.traps[0].y = 6, 5                        # dist 1 — 전사도 능동은 확정
check("능동 search: 전사도 반경 내(dist1)는 확정 발견(굴림 없음)",
      len(d._search(war)['found']) == 1 and not d.traps[0].hidden)

dp = arena(seed=3)
dp.traps = [Trap(6, 5, kind='spike')]                    # dist 1(둘 다 반경 내)
w_hits = r_hits = 0
for _ in range(100):
    dp.traps[0].hidden = True
    if dp._passive_search(mkbot('1', 5, 5, dex=0, search_r=1)):
        w_hits += 1
    dp.traps[0].hidden = True
    if dp._passive_search(mkbot('2', 5, 5, dex=3, search_r=2, job='도적')):
        r_hits += 1
check("수동 search-on-move: 굴림(전사도 가끔, 확정 아님) — 0 < 전사 < 100", 0 < w_hits < 100)
check("수동 search-on-move: 도적 > 전사 (DEX 보정 우위)", r_hits > w_hits)
dp.traps[0].x, dp.traps[0].y = 7, 5                      # dist 2 — 전사 반경 밖
w2 = r2 = 0
for _ in range(100):
    dp.traps[0].hidden = True
    if dp._passive_search(mkbot('1', 5, 5, dex=0, search_r=1)):
        w2 += 1
    dp.traps[0].hidden = True
    if dp._passive_search(mkbot('2', 5, 5, dex=3, search_r=2, job='도적')):
        r2 += 1
check("수동: dist2 는 전사 구조적 0 (반경 밖)", w2 == 0)
check("수동: dist2 도적은 발견 가능 (반경 우위)", r2 > 0)
print("        (dist1 전사 %d/100 · 도적 %d/100, dist2 전사 %d · 도적 %d)" % (w_hits, r_hits, w2, r2))

# ── ② 함정 패밀리: 종류 순환 + 경보 + 조심 보너스 + 경로 우회 ──
dk = Dungeon(seed=5)
check("기본 던전 함정 = 가시·경보·독침 순환(경보 포함)",
      sorted(t.kind for t in dk.traps) == ['alarm', 'dart', 'spike'])

da = arena(seed=7)
da.traps = [Trap(6, 5, dc=99, kind='alarm')]             # dc99 = 무조건 발동
da.monsters = [Monster(15, 8, mid=0), Monster(3, 9, mid=1)]
lurk = Monster(10, 3, mid=2)
lurk.concealed = True
da.monsters.append(lurk)
ba = mkbot('1', 5, 5)
out = da._enter_cell(ba, 6, 5)
tr = out.get('trap', {})
check("경보 함정: 발동 시 alarm=깨운 몹 수(비은닉만)", tr.get('alarm') == 2 and tr.get('kind') == 'alarm')
check("경보: 비은닉 몹 전부 HUNTING(justAlerted, 발원지로)",
      all(m.state == 'HUNTING' and m.target == '1' for m in da.monsters if not m.concealed))
check("경보: 매복몹(concealed)은 안 깬다(도사린 채)", lurk.state == 'SLEEPING' and lurk.concealed)
check("경보: 피해 0(dmg 필드 없음)", 'dmg' not in tr and ba['hp'] == 14)

dc = arena(seed=9)
dc.traps = [Trap(7, 5, kind='spike')]
dc.traps[0].hidden = False                               # 드러난 함정
bc = mkbot('1', 5, 5, dex=0)
p = dc.path_to(5, 5, 9, 5, [bc])                         # 열린 방 — 우회 가능
check("드러난 함정: 우회로 있으면 경로가 함정 칸을 피한다", p and (7, 5) not in p)
dcor = arena(seed=11)
for y in range(dcor.h):                                  # 1폭 외길로 좁힌다
    for x in range(dcor.w):
        dcor.grid[y][x] = '.' if (y == 5 and 1 <= x < dcor.w - 1) else '#'
dcor.traps = [Trap(7, 5, kind='spike')]
dcor.traps[0].hidden = False
bcor = mkbot('1', 5, 5, dex=0)
p2 = dcor.path_to(5, 5, 10, 5, [bcor])
check("드러난 함정: 외길이면 경유 허용(봉쇄 방지)", p2 and (7, 5) in p2)
outc = dcor._enter_cell(bcor, 7, 5)
check("알고 밟는 함정 = 조심 보너스(mod=DEX+%d)" % CAREFUL_BONUS,
      outc['trap']['mod'] == 0 + CAREFUL_BONUS)

# ── ③ 매복몹(concealed): 은폐 → 자동보행 무정지 → 일격 = they-ambush ──
dl = arena(seed=13)
sp = Monster(6, 5, kind='그림자거미', hp=5, atk=3, dmg=3, ac=13, mid=0)
sp.concealed = True
dl.monsters = [sp]
bl = mkbot('1', 5, 5, dex=-30)                           # dex-30 = 수동 인지 절대 실패(은폐 유지)
ob = dl.view(bl, [bl])
check("concealed 몹: sights.monsters 에 안 나감", ob['sights']['monsters'] == [])
check("concealed 몹: 봇 ascii_view 에 'M' 없음", all('M' not in row for row in ob['ascii_view']))
check("concealed 몹: 관전자 렌더에는 'm'(극적 아이러니)", dl.tile(6, 5, spectator=True) == 'm'
      and dl.tile(6, 5) == '.')
bl['order'], bl['path'] = '@5,3', [(5, 4), (5, 3)]       # 거미 곁을 지나가는 자동보행
r1 = dl.step_order(bl, [bl])
check("concealed 몹: 인접이어도 자동보행 안 멈춤(pre_adj 제외)",
      r1['result'] in ('walking', 'arrived') and 'monsters' not in r1)
sp.x, sp.y = bl['x'] + 1, bl['y']                        # 다시 직교 인접시켜 매복 일격
ev = dl.monster_turn([bl])
atk = [e for e in ev if e['type'] == 'monster_attack']
check("매복 일격 = they-ambush 발화(surprise+from_hiding)",
      len(atk) == 1 and atk[0].get('surprise') and atk[0].get('from_hiding'))
check("일격 후 정체 드러남(concealed 해제 + HUNTING + 봇 인지)",
      not sp.concealed and sp.state == 'HUNTING' and sp.id in bl['aware_of'])

dl2 = arena(seed=15)
sp2 = Monster(7, 5, kind='그림자거미', hp=5, mid=0)
sp2.concealed = True
dl2.monsters = [sp2]
rg = mkbot('2', 5, 5, dex=3, search_r=2, job='도적')
f = dl2._search(rg)
check("도적 능동 search 로 매복몹 사전 발각(kind=monster)",
      any(x['kind'] == 'monster' for x in f['found']) and not sp2.concealed
      and sp2.id in rg['aware_of'])
rg['x'] = 6                                              # 인접 → 발각된 거미(잠든 채)를 급습
ra = dl2._attack(rg, 'm0', [rg])
check("발각된 매복몹 급습 = we-ambush(surprise)", ra.get('surprise') is True)

# ── ④ FLEEING: 저HP 도주 → 협공=궁지(무진동) → 탈진=필사 반전 ──
df = arena(seed=17)
gb = Monster(8, 5, mid=0)
gb.hp, gb.state, gb.target = 2, 'HUNTING', '1'
gb.last_seen = (5, 5)
df.monsters = [gb]
bf = mkbot('1', 5, 5)
ev = df.monster_turn([bf])
check("저HP HUNTING → FLEEING 전환(monster_flee 이벤트)",
      gb.state == 'FLEEING' and any(e['type'] == 'monster_flee' for e in ev))

dsw = arena(seed=19)
for y in range(dsw.h):                                   # 1폭 외길 협공
    for x in range(dsw.w):
        dsw.grid[y][x] = '.' if (y == 5 and 1 <= x < dsw.w - 1) else '#'
gs = Monster(7, 5, mid=0)
gs.hp, gs.state = 2, 'FLEEING'
dsw.monsters = [gs]
p1, p2b = mkbot('1', 5, 5), mkbot('2', 9, 5)
for _ in range(3):
    dsw.monster_turn([p1, p2b])
check("협공 사이 FLEEING = 궁지 판정(제자리, 좌우 진동 없음)", (gs.x, gs.y) == (7, 5))
dd2 = arena(seed=21)
gd = Monster(8, 5, mid=0)
gd.hp, gd.state = 2, 'FLEEING'
dd2.monsters = [gd]
bd = mkbot('1', 7, 5)                                    # 계속 시야에 두고 몰아붙인다
desp = False
for _ in range(FLEE_STAMINA + 3):
    bd['x'], bd['y'] = max(2, gd.x - 1), gd.y            # 봇이 계속 붙는다(시야 유지)
    for e in dd2.monster_turn([bd]):
        if e['type'] == 'monster_desperate':
            desp = True
check("도주 탈진(%d턴) → 필사 반전(monster_desperate → HUNTING)" % FLEE_STAMINA,
      desp and gd.state == 'HUNTING' and gd.desperate)
ev2 = dd2.monster_turn([bd])
check("필사 반전 후엔 다시 도주하지 않는다", gd.state != 'FLEEING')

dw = arena(seed=23)
mw = Monster(6, 5, mid=0)
mw.state, mw.waking = 'HUNTING', 1
dw.monsters = [mw]
bw = mkbot('1', 5, 5)
check("막 깬 몹(waking=1) 공격 = 아직 기습(취약창)", dw._attack(bw, 'm0', [bw]).get('surprise') is True)
mw.waking, mw.hp = 0, 6
check("완전히 깬 HUNTING 몹 = 기습 아님", dw._attack(bw, 'm0', [bw]).get('surprise') is None)

# ── ⑤ 방콘텐츠: 상자/샘 도박 + 숨은 보물 ──
dch = Dungeon(seed=25)
chf = next(f for f in dch.features.values() if f.type == 'chest')
bch = mkbot('1', chf.x + 1, chf.y, dex=3)
rch = dch._interact(bch, 'f%d' % chf.id, [bch])
check("상자: 열면 chest_loot(보물2) 또는 chest_trap(독침2)",
      (rch['result'] == 'chest_loot' and bch['bag'] == 2)
      or (rch['result'] == 'chest_trap' and bch['hp'] == 12))
check("상자: 1회용(피처 소멸)", chf.id not in dch.features)
fnf = next(f for f in dch.features.values() if f.type == 'fountain')
bfn = mkbot('1', fnf.x, fnf.y - 1)
bfn['hp'] = 7
rfn = dch._interact(bfn, 'f%d' % fnf.id, [bfn])
check("샘: fountain_heal(+3) 또는 fountain_harm(-1)",
      (rfn['result'] == 'fountain_heal' and bfn['hp'] == 10)
      or (rfn['result'] == 'fountain_harm' and bfn['hp'] == 6))
hid = next(f for f in dch.features.values() if f.type == 'treasure' and f.concealed)
bht = mkbot('1', hid.x - 1, hid.y, dex=-30)
ob2 = dch.view(bht, [bht])
check("숨은 보물: obs sights 에 안 나감", all(x['id'] != 'f%d' % hid.id for x in ob2['sights']['features']))
dch._enter_cell(bht, hid.x, hid.y)
check("숨은 보물: 밟아도 못 줍는다(모르니까)", bht['bag'] == 0 and hid.id in dch.features)
hid.concealed = False
dch._enter_cell(bht, hid.x, hid.y)
check("드러난 보물: 밟으면 줍는다", bht['bag'] == 1 and hid.id not in dch.features)

# ── ⑥ 하강 조율: 파티 전원 모여야 내려간다(솔로탈출 방지) ──
de = arena(seed=27)
ex, ey = de.exit
e1 = mkbot('1', ex, ey)                                  # 계단 위
e2 = mkbot('2', 2, 2, job='도적')                        # 멀리
far = de._cheb(e2['x'], e2['y'], ex, ey)
assert far > EXIT_GATHER
rw = de._interact(e1, 'exit', [e1, e2])
check("동료가 멀면 wait_allies(missing 명단) — 혼자 안 내려간다",
      rw['result'] == 'wait_allies' and rw['missing'] == ['2']
      and not e1['won'] and not e2['won'])
e2['x'], e2['y'] = ex - EXIT_GATHER, ey                  # 반경 안으로
rg2 = de._interact(e1, 'exit', [e1, e2])
check("모이면 파티 동반 하강(전원 won)", rg2['result'] == 'exit'
      and rg2['party'] == ['1', '2'] and e1['won'] and e2['won'])
de2 = arena(seed=29)
ex2, ey2 = de2.exit
s1 = mkbot('1', ex2, ey2)
s2 = mkbot('2', 2, 2)
s2['alive'] = False                                      # 동료 전사(戰死) → 남은 자끼리
rs = de2._interact(s1, 'exit', [s1, s2])
check("죽은 동료는 기다리지 않는다(생존자만 모이면 하강)", rs['result'] == 'exit' and s1['won'])

# ── ⑦ 러너 통합: 2층 강하 스모크(LLM 무력화, GM 끔) ──
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="400", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="2", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2",
                  DUNGEON_PARTY_FILE="/nonexistent",   # 시트 외부화(Part B) 무시 → 내장 2인 고정(회귀 그물)
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_s3verify"))  # 격리 — state/ 관전 판 truncate 방지
import brains
brains._call_claude = lambda prompt, model="haiku": ""   # → dummy 폴백
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(리뷰 픽스) — 셸/tmux env 잔재가 라이브 원장을 읽고 쓰는 오염 방지
import show_runner
show_runner.STEP_DELAY = 0
with contextlib.redirect_stdout(io.StringIO()):
    show_runner.main()
evlog = open(os.path.join(show_runner.STATE, "events.log"), encoding="utf-8").read()
check("러너: 지하 2층 강하 전이 발생", "지하 2층" in evlog)
check("러너: 게임 종료 도달", "=== 종료" in evlog)
check("러너: 맵 헤더에 층 표기", "지하" in open(os.path.join(show_runner.STATE, "gm_map.txt"),
                                              encoding="utf-8").read())

# ── ⑧ [300시드] 전 콘텐츠 풀게임: 항상 종료 + 신규 메커니즘 실발화 + 결정론 ──
def play(seed, ticks=600, sig=False):
    dd = Dungeon(seed=seed)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    n = {'from_hiding': 0, 'alarm': 0, 'flee': 0, 'desperate': 0, 'notice': 0,
         'we_ambush': 0, 'found': 0, 'chest': 0, 'fountain': 0, 'wait': 0}
    done = False
    for t in range(ticks):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                r = dd.step_order(b, bb)
                if r.get('trap', {}).get('alarm') is not None:
                    n['alarm'] += 1
                n['found'] += len(r.get('found', []))
            else:
                r = dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
                if r.get('surprise'):
                    n['we_ambush'] += 1
                if str(r.get('result', '')).startswith('chest'):
                    n['chest'] += 1
                if str(r.get('result', '')).startswith('fountain'):
                    n['fountain'] += 1
                if r.get('result') == 'wait_allies':
                    n['wait'] += 1
        for e in dd.monster_turn(bb):
            if e['type'] == 'monster_attack' and e.get('from_hiding'):
                n['from_hiding'] += 1
            if e['type'] == 'monster_flee':
                n['flee'] += 1
            if e['type'] == 'monster_desperate':
                n['desperate'] += 1
            if e['type'] == 'monster_notice':
                n['notice'] += 1
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag']) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive, m.state, m.concealed) for m in dd.monsters),
                tuple(sorted((f.type, f.x, f.y, f.concealed) for f in dd.features.values())))
    return done, n


tot = {}
done_n = 0
for s in range(300):
    ok, n = play(s)
    done_n += ok
    for k, v in n.items():
        tot[k] = tot.get(k, 0) + v
check("[300시드] 전 콘텐츠(매복·경보·상자·샘·FLEEING) 풀게임 항상 종료", done_n == 300)
check("[300시드] they-ambush 발화(from_hiding > 0) — 2b의 예언 실현", tot['from_hiding'] > 0)
check("[300시드] 경보 함정 실발동", tot['alarm'] > 0)
check("[300시드] 도주(flee)·수동인지(found)·발각(notice)·we-ambush 실발화",
      tot['flee'] > 0 and tot['found'] > 0 and tot['notice'] > 0 and tot['we_ambush'] > 0)
check("[300시드] 상자·샘 상호작용 실발생", tot['chest'] > 0 and tot['fountain'] > 0)
check("[300시드] 하강 조율(wait_allies) 실발생", tot['wait'] > 0)
print("        (종료 %d/300 · 매복일격 %d · 경보 %d · 도주 %d · 필사 %d · 발각 %d\n"
      "         · we-ambush %d · 수동발견 %d · 상자 %d · 샘 %d · 대기 %d)"
      % (done_n, tot['from_hiding'], tot['alarm'], tot['flee'], tot['desperate'],
         tot['notice'], tot['we_ambush'], tot['found'], tot['chest'], tot['fountain'], tot['wait']))
bad_det = sum(1 for s in range(0, 20) if play(s, sig=True) != play(s, sig=True))
check("[20시드] 결정론 — 같은 시드 = 같은 판(신규 굴림 전부 시드 스트림)", bad_det == 0)

# ── ⑨ 어드버서리얼 3렌즈 리뷰 픽스 회귀 (2026-07-02) ──────────
# (a) waking 스턴락: 기습이 skip_turns를 재설정해도 waking은 공격 1회로 소비되어야
dwk = arena(seed=31)
big = Monster(6, 5, hp=60, mid=0)
big.state, big.waking = 'HUNTING', 1
dwk.monsters = [big]
bwk = mkbot('1', 5, 5)
r1 = dwk._attack(bwk, 'm0', [bwk])
r2 = dwk._attack(bwk, 'm0', [bwk])
check("(a) 발각 직후 1타=기습, 2타=기습 아님(waking 소비 — 무한 스턴락 차단)",
      r1.get('surprise') is True and r2.get('surprise') is None and big.waking == 0)
# (b) FLEEING 몹 공격 = 기습 아님(빤히 보며 도망중) + 피격해도 도주 지속(시계 안 되감김)
dfl = arena(seed=33)
run_m = Monster(6, 5, hp=60, mid=0)
run_m.state, run_m.flee_turns = 'FLEEING', 5
dfl.monsters = [run_m]
bfl = mkbot('1', 5, 5)
rfl = dfl._attack(bfl, 'm0', [bfl])
check("(b) 도주몹 공격 = 기습 아님 + 피격 후에도 FLEEING 유지(flee 시계 보존)",
      rfl.get('surprise') is None and run_m.state == 'FLEEING' and run_m.flee_turns == 5)
# (c) 경보: 자던/배회만 각성 카운트 — 도주몹은 안 뒤집는다
dal = arena(seed=35)
slp = Monster(15, 8, mid=0)
fle = Monster(3, 9, mid=1)
fle.state, fle.flee_turns = 'FLEEING', 6
dal.monsters = [slp, fle]
dal.traps = [Trap(6, 5, dc=99, kind='alarm')]
bal = mkbot('1', 5, 5)
oal = dal._enter_cell(bal, 6, 5)
check("(c) 경보=자던 놈만 각성(woken=1), 도주몹 상태·시계 불변",
      oal['trap']['alarm'] == 1 and slp.state == 'HUNTING'
      and fle.state == 'FLEEING' and fle.flee_turns == 6)
# (d) at_exit 도 지각한다 — 계단 위에서 뻔히 보이는 적이 '매복' 판정되지 않게
dax = arena(seed=37)
exf = dax.features[dax._exit_fid]
exf.x, exf.y = 6, 5
mx = Monster(8, 5, mid=0)
dax.monsters = [mx]
bax = mkbot('1', 5, 5)
bax['order'], bax['path'] = 'exit', [(6, 5)]
rax = dax.step_order(bax, [bax])
check("(d) 계단 도착(at_exit) 스텝에도 _perceive 수행(시야 내 몹 인지)",
      rax['result'] == 'at_exit' and mx.id in bax['aware_of'])
# (e) 함정 즉사 = 사후 인지 굴림 금지(시체가 숨은 것을 드러내지 않는다)
ddb = arena(seed=39)
ddb.traps = [Trap(6, 5, dc=99, dmg=99, kind='spike'), Trap(7, 5, kind='dart')]
bdb = mkbot('1', 5, 5, dex=3, search_r=2)
bdb['order'], bdb['path'] = '@8,5', [(6, 5), (7, 5), (8, 5)]
rdb = ddb.step_order(bdb, [bdb])
check("(e) 함정 즉사 스텝 = encounter(trap)로 즉시 종료, 옆 숨은 함정은 그대로 숨음",
      not bdb['alive'] and rdb['result'] == 'encounter' and rdb['trap'].get('down')
      and ddb.traps[1].hidden)
# (f) 발밑(dist 0) 피처 adj=true — 계단/상자 위에서 그대로 interact 가능
dfz = arena(seed=41)
exf2 = dfz.features[dfz._exit_fid]
exf2.x, exf2.y = 5, 5
bfz = mkbot('1', 5, 5)
vex = dfz.view(bfz, [bfz])['sights']['exit']
check("(f) 계단 위(dist 0) exit.adj=true (발밑 상호작용 계약)",
      vex and vex['dist'] == 0 and vex['adj'] is True)
check("(f) 솔로봇이 계단 위에서 dummy=interact exit (2틱 댄스 소멸)",
      dummy_brain(dfz.view(bfz, [bfz]), '1') == {'type': 'interact', 'target': 'exit'})
# (g) 강하(2층) 포함 종결·결정론 — show_runner 전이 미러(회귀 그물)
def play_depths(seed, depths=2, ticks=900, sig=False):
    depth, total = 1, 0
    dd = Dungeon(seed=seed, depth=1)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    while total < ticks:
        total += 1
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        dd.monster_turn(bb)
        if all(b['won'] or not b['alive'] for b in bb):
            surv = [b for b in bb if b['won']]
            if not surv or depth >= depths:
                return ((depth, tuple((b['char'], b['hp'], b['won'], b['bag']) for b in bb))
                        if sig else True)
            depth += 1
            dd = Dungeon(seed=seed, depth=depth, n_monsters=2 + depth - 1)
            nb = []
            for b in sorted(surv, key=lambda b: b['char']):
                n = spawn(dd, b['char'], nb)
                n['hp'], n['bag'] = b['hp'], b['bag']
                nb.append(n)
            bb = nb
    return (None, None) if sig else False
done2 = sum(1 for s in range(40) if play_depths(s))
check("(g) [40시드] 지하 2층 관통(강하 전이 포함) 항상 종결", done2 == 40)
bad2 = sum(1 for s in range(8) if play_depths(s, sig=True) != play_depths(s, sig=True))
check("(g) [8시드] 강하 포함 결정론(층별 파생시드·이월 재스폰 순서)", bad2 == 0)

print("\n" + "=" * 44)
print("RESULT: " + ("ALL PASS" if C.failed == 0 else "%d FAILED" % C.failed))
