# -*- coding: utf-8 -*-
"""리모컨(options 메뉴) 헤들리스 검증 — 7번째 게이트.
게이트:
  ① 옵션 불변식 스윕(시드 20 × 전 재결정 시점): n 연속(1..K) / search 정확 1개 / explore ≥1
  ② 전수성: sights ↔ options 1:1 — 인접 몹=attack·비인접 몹=goto / 피처 adj=interact·비adj=goto /
     출구 보임(adj=interact, 비adj=goto)·안 보임=옵션 없음 / 보이는 비인접 동료=합류·인접 동료=없음 /
     안 보이는 생존 동료=장부에 마지막 본 자리가 있을 때만 그 칸 핑(D18 개정 09-06), 없으면 항목 없음
  ③ 시야-온리: concealed 몹·피처 id 가 어떤 option target 에도 없음
  ④ 순수성: view() 가 rng 상태를 안 건드림 + 2회 호출 options 동일
  ⑤ _pick 왕복: 모든 n 에 대해 type/target == options[n] + 관용("3.0"/"옵션 3")·기각(3.5/0/999)
  ⑥ explore 방위 존중: 메뉴가 준 정확 방위가 도달가능하면 _set_explore 가 그 방위로 간다(정확일치 우선)
  ⑦ 러너 통합(고정 스텁 LLM): decisions 에 choice:int·src=haiku / run_meta.menu=true /
     2회 실행 결정론(started 제외 라인 동일)
  ⑧ 방향 탐색 열거(D19 개정 4, 09-07 — scan 판 + explore_dirs, 시드 20 스윕): 열거 집합 = 독립 오라클
     (방위별 unvisited 대표칸·너머 안 본·경로 있음 − 막다른 곳 − 보이는 문 방위 − 문 칸 종점)·칸 수=라벨 /
     열거 방위 집행=라벨(방위·칸) / (type,target) 중복 0 / 열거 방위의 wire 줄이 '트여 있다' /
     열거 시 '엔진에 맡긴다' 0 / 스위치 끄면 구판 메뉴(탐색 줄 외 동일·'트여 있다' 0)
(기존 verify 6종은 별도 실행 — 게이트 명령이 연쇄한다.)
"""
import io
import os
import re
import json
import contextlib

os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="120", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="3", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2",
                  DUNGEON_MENU="1", DUNGEON_STEP_DELAY="0",
                  DUNGEON_PARTY_FILE="/nonexistent",     # 내장 2인 고정(회귀 그물)
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_menuverify"))
os.environ.pop("DUNGEON_STREAM_OBS", None)
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(리뷰 픽스) — 셸/tmux env 잔재가 라이브 원장을 읽고 쓰는 오염 방지

import dungeon_gm as G
import brains


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


# ───────────────────────── ①~⑥ 옵션 불변식 스윕 ─────────────────────────
def sweep():
    stats = {"views": 0, "ncont": 0, "search1": 0, "explore1": 0, "census": 0,
             "sight_only": 0, "pure": 0, "pick": 0, "exp_dir_ok": 0, "exp_dir_n": 0}
    for seed in range(1, 21):
        d = G.Dungeon(seed=seed, w=40, h=16, n_monsters=3, n_traps=3, n_lurkers=1)
        bots = []
        bots.append(G.spawn(d, '1', bots))
        bots.append(G.spawn(d, '2', bots))
        for tick in range(1, 121):
            for b in bots:
                if not b['alive'] or b['won']:
                    continue
                if b.get('order'):
                    d.step_order(b, bots)
                    continue
                st = d.rng.getstate()
                obs = d.view(b, bots)
                obs2 = d.view(b, bots)                      # ④ 재호출 동일(+rng 무변화)
                stats["views"] += 1
                stats["pure"] += (d.rng.getstate() == st
                                  and obs['options'] == obs2['options'])
                opts = obs['options']
                ns = [o['n'] for o in opts]
                stats["ncont"] += (ns == list(range(1, len(opts) + 1)))
                stats["search1"] += (sum(1 for o in opts if o['type'] == 'search') == 1)
                stats["explore1"] += (sum(1 for o in opts if o['type'] == 'explore') >= 1)
                stats["census"] += census_ok(obs, bots, b)
                stats["sight_only"] += sight_only_ok(d, opts)
                stats["pick"] += pick_ok(opts, obs)
                n_dir, n_ok = explore_dir_ok(d, b, bots, obs)
                stats["exp_dir_n"] += n_dir
                stats["exp_dir_ok"] += n_ok
                d.act(b, G.dummy_brain(obs, b['char']), bots)
            d.monster_turn(bots)
            if all(b['won'] or not b['alive'] for b in bots):
                break
    return stats


def census_ok(obs, bots, me):
    """② 전수성: sights 를 오라클로 options 재구성 — 집합이 정확히 일치해야 한다."""
    s = obs['sights']
    want = set()
    for m in s['monsters']:
        want.add(('attack' if m['adj'] else 'goto', m['id']))
    ex = s.get('exit')
    if ex:
        want.add(('interact' if ex['adj'] else 'goto', 'exit'))
    for f in s['features']:
        want.add(('interact' if f['adj'] else 'goto', f['id']))
    for a in s['bots']:
        if not a['adj']:
            want.add(('goto', a['id']))                    # 인접 동료 합류는 no-op → 미노출
    vis = {a['char'] for a in s['bots']}
    led_mv = (me.get('ledger') or {}).get('moving') or {}
    for p in obs['party']:
        if p['alive'] and not p['won'] and p['char'] not in vis:
            e = led_mv.get('b%s' % p['char'])         # D18 개정(09-06): 파티 감각 폐지 — 장부의
            if e:                                     #   마지막 본 자리(칸 핑)만, 본 적 없으면 없음
                want.add(('goto', '@%d,%d' % (e['x'], e['y'])))
    got = {(o['type'], o.get('target')) for o in obs['options']
           if o['type'] in ('attack', 'goto', 'interact')}
    return got == want


def sight_only_ok(d, opts):
    """③ 시야-온리: concealed 몹/피처 id 가 옵션 target 에 절대 없음."""
    hidden = {'m%d' % m.id for m in d.monsters if m.alive and m.concealed}
    hidden |= {'f%d' % f.id for f in d.features.values() if f.concealed}
    return not any(o.get('target') in hidden for o in opts)


def pick_ok(opts, obs):
    """⑤ _pick 왕복 + 관용/기각."""
    for o in opts:
        r = brains._pick({'choice': o['n']}, obs)
        if not r or r['type'] != o['type'] or r.get('target') != o.get('target'):
            return False
    o1 = opts[0]
    lenient = (brains._pick({'choice': '%d.0' % o1['n']}, obs),
               brains._pick({'choice': '옵션 %d' % o1['n']}, obs))
    if any(r is None or r['type'] != o1['type'] for r in lenient):
        return False
    bad = (brains._pick({'choice': 3.5}, obs) if len(opts) >= 3 else None,
           brains._pick({'choice': 0}, obs),
           brains._pick({'choice': len(opts) + 1}, obs),
           brains._pick({}, obs))
    return all(r is None for r in bad)


def explore_dir_ok(d, bot, bots, obs):
    """⑥ 메뉴 explore 방위가 '도달가능한 fresh way'면 _set_explore 는 정확히 그 방위로.
    (도달불가면 best-effort 대안 — 문서화된 동작이라 검사 제외.)
    _set_explore 는 bot order/path 만 만지고 세계·rng 무변화 → 저장/복원으로 무해."""
    seen = d.visible_cells(bot['x'], bot['y'])
    reachable = {w['bearing'] for w in d._ways(bot['x'], bot['y'], seen)
                 if not w['visited'] and d.path_to(bot['x'], bot['y'],
                                                   w['cell'][0], w['cell'][1], bots)}
    n = ok = 0
    save = (bot.get('order'), list(bot.get('path') or []))
    for o in obs['options']:
        if o['type'] != 'explore' or o.get('target') not in reachable:
            continue
        n += 1
        r = d._set_explore(bot, o['target'], bots)
        if r.get('result') == 'pathed' and r.get('bearing') == o['target']:
            ok += 1
    bot['order'], bot['path'] = save
    return n, ok


# ───────────────────────── ⑧ 방향 탐색 열거(D19 개정 4, 09-07) — 문장↔메뉴 1:1 ─────────────────────────
def fresh_oracle(d, b, bots):
    """독립 오라클: 계획기(_explore_ways)를 안 부르고 같은 사실을 다시 센다 — 방위별 (unvisited 대표칸·너머 안 본·
    경로 있음) → 경로. 종점 = 그 방위의 보이는 가장 먼 안 밟은·너머 안 본 프런티어(3개 시도) → 대표칸."""
    seen = d.visible_cells(b['x'], b['y'])
    sc = b.get('seen_cells') or set()
    bx, by = b['x'], b['y']

    def unseen_edge(c):
        x, y = c
        return any(0 <= x + dx < d.w and 0 <= y + dy < d.h and (x + dx, y + dy) not in sc
                   for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)))
    fr = d._frontier_cells(bx, by, seen)
    out = {}
    for w in d._ways(bx, by, seen):
        if w['visited'] or not unseen_edge(w['cell']):
            continue
        far = [c for c in fr if d._bearing(c[0] - bx, c[1] - by) == w['bearing']
               and c not in d.visited and unseen_edge(c)]
        far.sort(key=lambda c: (-max(abs(c[0] - bx), abs(c[1] - by)), c))
        for c in far[:3] + [w['cell']]:
            p = d.path_to(bx, by, c[0], c[1], bots)
            if p:
                out[w['bearing']] = p
                break
    return out


def sweep_dirs():
    st = {"views": 0, "listed": 0, "set_ok": 0, "exec_ok": 0, "exec_n": 0, "dup_ok": 0,
          "wire_ok": 0, "wire_n": 0, "generic_ok": 0, "off_ok": 0}
    for seed in range(1, 21):
        d = G.Dungeon(seed=seed, w=40, h=16, n_monsters=3, n_traps=3, n_lurkers=1,
                      scan=True, explore_dirs=True)
        bots = []
        bots.append(G.spawn(d, '1', bots))
        bots.append(G.spawn(d, '2', bots))
        for tick in range(1, 121):
            for b in bots:
                if not b['alive'] or b['won']:
                    continue
                if b.get('order'):
                    d.step_order(b, bots)
                    continue
                obs = d.view(b, bots)
                opts = obs['options']
                st["views"] += 1
                dirs = [o for o in opts if o['type'] == 'explore' and '트여 있다' in o['label']]
                generic = [o for o in opts if o['type'] == 'explore' and not o.get('target')]
                # ⓐ 열거 집합 = 오라클 − 막다른 곳 − 보이는 문 방위 − 문 칸 종점, 칸 수 = 라벨
                covered = {o['target'] for o in opts if o['type'] == 'explore' and '막다른 곳' in o['label']}
                covered |= {dr['bearing'] for dr in ((obs.get('zone') or {}).get('doors') or [])
                            if dr.get('seen') and dr.get('dist', 0) > 0}
                doorc = {dr.cell for dr in d.doors.values() if dr.cell}
                doorc |= {c for dr in d.doors.values() for c in dr.sides.values()}
                orc = fresh_oracle(d, b, bots)
                want = {bb: p for bb, p in orc.items() if bb not in covered and p[-1] not in doorc}
                got = {o['target']: o for o in dirs}
                st["set_ok"] += (set(got) == set(want)
                                 and all(('약 %d칸' % len(want[bb])) in got[bb]['label'] for bb in want))
                st["listed"] += bool(dirs)
                keys = [(o['type'], o.get('target')) for o in opts]
                st["dup_ok"] += (len(keys) == len(set(keys)))
                st["generic_ok"] += (not generic) if dirs else 1
                # ⓓ 열거 방위의 문장 줄 = '트여 있다'(wire 와 메뉴가 같은 말)
                wire = brains._wire(obs, {})
                for o in dirs:
                    st["wire_n"] += 1
                    line = next((l for l in wire.splitlines()
                                 if l.startswith('- %s: ' % G.BEAR_KR[o['target']])), '')
                    st["wire_ok"] += ('트여 있다' in line)
                # ⓑ 집행 = 라벨(방위·칸 수) — order/path/plan 복원(세계 무변경)
                save = (b.get('order'), list(b.get('path') or []), list(b.get('plan') or []))
                for o in dirs:
                    st["exec_n"] += 1
                    r = d._set_explore(b, o['target'], bots)
                    st["exec_ok"] += (r.get('result') == 'pathed' and r.get('bearing') == o['target']
                                      and ('약 %d칸' % r.get('len', -1)) in o['label'])
                b['order'], b['path'], b['plan'] = save
                # ⓔ 스위치 끄면 구판: 탐색 줄 외 동일 + '트여 있다' 줄 0
                d.explore_dirs = False
                off = d.view(b, bots)['options']
                d.explore_dirs = True
                nonx = lambda os_: [(o['type'], o.get('target'), o['label']) for o in os_ if o['type'] != 'explore']
                st["off_ok"] += (nonx(off) == nonx(opts)
                                 and all('트여 있다' not in o['label'] for o in off if o['type'] == 'explore'))
                d.act(b, G.dummy_brain(obs, b['char']), bots)
            d.monster_turn(bots)
            if all(b['won'] or not b['alive'] for b in bots):
                break
    return st


# ───────────────────────── ⑦ 러너 통합(고정 스텁) ─────────────────────────
def stub(prompt, model="haiku"):
    """결정론 스텁 LLM: 1번이 즉시행동(공격/계단/상호작용)이면 1번, 아니면 마지막(explore)."""
    ns = re.findall(r"^(\d+)\. ", prompt, re.M)
    if not ns:
        return ""
    n = 1 if re.search(r"^1\. (공격|계단|상호작용)", prompt, re.M) else int(ns[-1])
    return '{"choice": %d, "say": "간다", "reason": "검증 스텁"}' % n


def run_stub_game():
    import show_runner
    show_runner.STEP_DELAY = 0
    import time as _t
    _t.sleep = lambda s: None
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
    p = os.path.join(show_runner.STATE, "stream.jsonl")
    return open(p, encoding="utf-8").read()


def normalized(raw):
    out = []
    for line in raw.splitlines():
        r = json.loads(line)
        r.pop("started", None)
        out.append(json.dumps(r, ensure_ascii=False, sort_keys=True))
    return out


def main():
    print("== 리모컨(options) 검증 ==")
    st = sweep()
    v = st["views"]
    check("① n 연속 1..K (%d뷰)" % v, st["ncont"] == v)
    check("① search 정확 1개", st["search1"] == v)
    check("① explore ≥1", st["explore1"] == v)
    check("② 전수성(sights↔options 1:1)", st["census"] == v)
    check("③ 시야-온리(concealed 미노출)", st["sight_only"] == v)
    check("④ 순수성(rng 무변화·재호출 동일)", st["pure"] == v)
    check("⑤ _pick 왕복+관용+기각", st["pick"] == v)
    check("⑥ explore 방위 존중 %d/%d" % (st["exp_dir_ok"], st["exp_dir_n"]),
          st["exp_dir_n"] > 0 and st["exp_dir_ok"] == st["exp_dir_n"])

    st8 = sweep_dirs()
    v8 = st8["views"]
    check("⑧ 방향 탐색 열거(scan+explore_dirs) 집합=오라클·칸 수=라벨 (%d뷰, 열거 %d뷰)" % (v8, st8["listed"]),
          st8["listed"] > 0 and st8["set_ok"] == v8)
    check("⑧ 열거 방위 집행=라벨(방위·칸) %d/%d" % (st8["exec_ok"], st8["exec_n"]),
          st8["exec_n"] > 0 and st8["exec_ok"] == st8["exec_n"])
    check("⑧ (type,target) 중복 0", st8["dup_ok"] == v8)
    check("⑧ 열거 방위의 문장 줄='트여 있다' %d/%d" % (st8["wire_ok"], st8["wire_n"]),
          st8["wire_n"] > 0 and st8["wire_ok"] == st8["wire_n"])
    check("⑧ 열거 시 '엔진에 맡긴다' 0", st8["generic_ok"] == v8)
    check("⑧ 스위치 끄면 구판 메뉴(탐색 줄 외 동일·'트여 있다' 0)", st8["off_ok"] == v8)

    brains._call_claude = stub
    raw1 = run_stub_game()
    raw2 = run_stub_game()
    recs = [json.loads(l) for l in raw1.splitlines()]
    meta = recs[0]
    decs = [d for r in recs if r["kind"] == "tick"
            for d in (r.get("decisions") or {}).values() if not d.get("skipped")]
    check("⑦ run_meta.menu=true", meta.get("menu") is True)
    check("⑦ 스텁 결정 전부 choice:int·src=haiku (%d결정)" % len(decs),
          len(decs) > 0 and all(isinstance(d.get("choice"), int)
                                and d.get("src") == "haiku" for d in decs))
    check("⑦ outcome 유효", recs[-1]["kind"] == "end"
          and recs[-1]["outcome"] in ("escaped", "wiped", "timeout"))
    check("⑦ 결정론(2회 라인 동일, started 제외)", normalized(raw1) == normalized(raw2))

    print()
    if C.failed:
        print("RESULT: %d FAIL" % C.failed)
        raise SystemExit(1)
    print("=" * 44)
    print("RESULT: ALL PASS — 리모컨 계약(전수성·시야-온리·번호=행동) 건전")


if __name__ == "__main__":
    main()
