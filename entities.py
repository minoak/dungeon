# -*- coding: utf-8 -*-
"""엔티티 저장소(D50, 2026-09-11 — 파트너 설계 메모 `WONDERLAND_CHANGES_2026-09-11.md` §4-1 [제안] 구조의 1차:
저장소 틀 먼저, 동작은 그대로).

정의(Def) = 바뀌지 않는 것: id·name·kind·tags·sprite·comps(부품). 인스턴스(게임 중 바뀌는 것 — 좌표·hp·상태)는
지금처럼 엔진의 Monster/Trap/Feature 객체가 든다. 엔진은 여기서 수치·이름·지식 본문을 읽는다:
  · 몬스터: health.max / combat.atk·dmg·ac·on_hit(명중 시 태그) / ai.flee.hp_frac·stamina(없으면 도주 안 함)·to·join_range(D51: ally=근처 몹에게 합류)
  · 함정: trap.dc·dmg·status → dungeon_gm.TRAP_KINDS
  · 오브젝트: type(엔진 피처 type)·name → _add_feature 이름 / equipment.slot·bonus → GEAR_KINDS / tags → 조합형 관측 태그
  · NPC: npc.line·line_again·gift → show_runner.build_town (town.json 은 배치=id·좌표만)
  · 지식: knowledge.deep → Dungeon.lore (옛 lore.json 본문 그대로. 키 = monster:<name> / trap:<id> / feature:<type>)
    D53(09-12): knowledge.brief(처음 알게 된 한 줄)·unlock{event, count}(심층 해금 조건 — 코드가 센다, LLM 0콜)도 같은
    항목에 실린다. 지금 세는 사건은 encounter(개체 하나를 새로 인지한 순간 = aware_of 증분, 몬스터만)뿐 — 나머지 어휘는 자리.
자리만 있고 아직 안 읽는 것: ai.start·ai.concealed(스폰 코드가 명시),
loot·container·heal·consumable·exit 부품(메모 "부품은 필요할 때 하나씩"). 클라이언트 스프라이트 프레임 번호는
game/src/assets/world.ts 가 소유 — sprite 필드는 텍스처 참조(wl-<이름>[#프레임])이고 검증은 텍스처 파일 존재까지.
검증은 로드 단계(verify_entities 게이트): 모르는 kind·부품, id≠파일명, 중복, 없는 텍스처, 모르는 해금 사건, 수치 결손.
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, 'entities')
SPRITE_DIR = os.path.join(HERE, 'game', 'src', 'assets', 'world')
KINDS = ('monster', 'trap', 'object', 'npc', 'map', 'building', 'quest')   # quest(D61, 09-12): 길드 게시판의 의뢰 — 정보만
COMPS = {'monster': {'health', 'combat', 'ai', 'knowledge'},
         'trap': {'trap', 'knowledge'},
         'object': {'equipment', 'consumable', 'loot', 'container', 'heal', 'exit', 'knowledge'},
         'npc': {'npc', 'knowledge'},
         'map': {'space'}, 'building': {'building', 'board', 'oracle'},   # D61 건물 역할 부품(메모 §4-4 [제안]): 게시판·신탁
         'quest': {'quest'}}
UNLOCK_EVENTS = {'encounter', 'kill', 'search_first', 'trap_avoid', 'trap_disarm', 'visit', 'talk'}   # 메모 §2-5 어휘.
#   코드가 세는 건 encounter 뿐(bestiary.Issuer, D53) — 나머지는 검증기만 아는 예약어(정의에 적어도 아직 안 센다).
BASELINE_MONSTER = '고블린'   # 모르는 종(장면 저작의 임의 이름)은 기준선 몹의 몸 — 낯선 짐승도 몸은 있다


class EntityError(ValueError):
    """정의 파일의 문제 — 전부 모아 한 번에 알린다(로드 단계에서 죽는 게 낫다)."""


def _problems(pairs, root):
    out, ids = [], {}
    boards, kinds_by_id = [], {}                     # D61 2차 검사 재료
    for path, d in pairs:
        rel = os.path.relpath(path, root)
        stem = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.basename(os.path.dirname(path))
        if not isinstance(d, dict):
            out.append('%s: JSON 객체가 아니다' % rel)
            continue
        eid, kind = d.get('id'), d.get('kind')
        if eid != stem:
            out.append('%s: id %r ≠ 파일명 %r' % (rel, eid, stem))
        if kind not in KINDS:
            out.append('%s: 모르는 kind %r' % (rel, kind))
        elif folder != kind:
            out.append('%s: kind %r 인데 폴더가 %r' % (rel, kind, folder))
        if not d.get('name'):
            out.append('%s: name 없음' % rel)
        if eid in ids:
            out.append('%s: id %r 중복(%s)' % (rel, eid, ids[eid]))
        ids[eid] = rel
        comps = d.get('comps')
        if not isinstance(comps, dict):
            out.append('%s: comps 가 객체가 아니다' % rel)
            comps = {}
        for c in comps:
            if kind in COMPS and c not in COMPS[kind]:
                out.append('%s: 엔진이 모르는 부품 %r' % (rel, c))
        kn = comps.get('knowledge') or {}
        ev = (kn.get('unlock') or {}).get('event')
        if ev is not None and ev not in UNLOCK_EVENTS:
            out.append('%s: 존재하지 않는 해금 사건 %r' % (rel, ev))
        if kn.get('unlock') is not None:
            cnt = (kn.get('unlock') or {}).get('count')
            if ev is None or not (isinstance(cnt, int) and cnt >= 1):
                out.append('%s: knowledge.unlock 은 event + count(정수≥1) 필요' % rel)
            if not kn.get('deep'):
                out.append('%s: 해금 조건이 있는데 knowledge.deep(해금할 본문)이 없다' % rel)
        if kn.get('review') is not None:                     # D55 인식 갱신 조건(선택) — 있으면 unlock 과 같은 꼴
            rv = kn.get('review') or {}
            if rv.get('event') not in UNLOCK_EVENTS or not (isinstance(rv.get('count'), int) and rv['count'] >= 1):
                out.append('%s: knowledge.review 는 event(해금 사건 어휘) + count(정수≥1) 필요' % rel)
            if kn.get('unlock') is None:
                out.append('%s: 인식 갱신 조건(review)은 해금 조건(unlock)이 있어야 뜻이 있다' % rel)
        sp = d.get('sprite')
        if sp:
            tex = str(sp).split('#')[0]
            if not tex.startswith('wl-') or not os.path.exists(os.path.join(SPRITE_DIR, tex[3:] + '.png')):
                out.append('%s: 없는 스프라이트 텍스처 %r' % (rel, sp))
        if kind == 'object' and not d.get('type'):
            out.append('%s: object 는 type(엔진 피처 type) 필요' % rel)
        if kind == 'monster':
            for c, keys in (('health', ('max',)), ('combat', ('atk', 'dmg', 'ac'))):
                for k in keys:
                    if not isinstance((comps.get(c) or {}).get(k), int):
                        out.append('%s: %s.%s 정수 필요' % (rel, c, k))
        if kind == 'monster':
            fl = (comps.get('ai') or {}).get('flee')
            if fl is not None:
                if fl.get('to', 'away') not in ('away', 'ally'):
                    out.append('%s: ai.flee.to 는 away|ally (%r)' % (rel, fl.get('to')))
                if fl.get('to') == 'ally' and not (isinstance(fl.get('join_range'), int) and fl['join_range'] >= 1):
                    out.append('%s: ai.flee.to=ally 는 join_range(정수≥1) 필요' % rel)
        if kind == 'trap':
            for k in ('dc', 'dmg'):
                if not isinstance((comps.get('trap') or {}).get(k), int):
                    out.append('%s: trap.%s 정수 필요' % (rel, k))
        if kind == 'npc' and not (comps.get('npc') or {}).get('line'):
            out.append('%s: npc.line 필요' % rel)
        if kind == 'map':
            space = comps.get('space') or {}
            if space.get('role') not in ('town', 'district', 'street'):
                out.append('%s: space.role 은 town|district|street' % rel)
        if kind == 'building':
            b = comps.get('building') or {}
            size, entry = b.get('size'), b.get('entrance')
            valid_size = isinstance(size, list) and len(size) == 2 and all(type(v) is int and v > 0 for v in size)
            if not valid_size:
                out.append('%s: building.size 는 양의 정수 [가로,세로]' % rel)
            if not (valid_size and isinstance(entry, list) and len(entry) == 2 and
                    all(type(v) is int for v in entry) and 0 <= entry[0] < size[0] and entry[1] == size[1]-1):
                out.append('%s: building.entrance 는 남쪽 외벽의 칸' % rel)
            if not isinstance(b.get('texture'), str) or not b.get('texture'):
                out.append('%s: building.texture 필요' % rel)
            elif not os.path.isfile(os.path.join(SPRITE_DIR, 'town-' + b['texture'] + '.png')):
                out.append('%s: 건물 텍스처 파일이 없다: %s' % (rel, b['texture']))
            board = comps.get('board')
            if board is not None:                    # D61 게시판 부품 — 의뢰 id 목록(존재·kind 는 아래 2차 검사)
                if not isinstance(board.get('quests'), list) or not board['quests']:
                    out.append('%s: board.quests 는 비어 있지 않은 의뢰 id 목록' % rel)
                else:
                    boards.append((rel, list(board['quests'])))
        if kind == 'quest':                          # D61 의뢰 — goal 문장은 있어야 한다(정보만)
            q = comps.get('quest') or {}
            if not isinstance(q.get('goal'), str) or not q['goal'].strip():
                out.append('%s: quest.goal 필요' % rel)
        kinds_by_id[eid] = kind
    for rel, qids in boards:                         # 2차: 게시판이 가리키는 의뢰가 실제 quest 정의인가
        for qid in qids:
            if kinds_by_id.get(qid) != 'quest':
                out.append('%s: board.quests 의 %r 는 quest 정의가 아니다' % (rel, qid))
    return out


def read(root=ROOT):
    """폴더의 정의 전부 → {id: def}. 문제가 하나라도 있으면 EntityError(전부 나열)."""
    files = sorted(glob.glob(os.path.join(root, '*', '*.json')))
    pairs = []
    for p in files:
        with open(p, encoding='utf-8') as f:
            pairs.append((p, json.load(f)))
    problems = _problems(pairs, root) if pairs else ['정의가 없다: %s' % root]
    if problems:
        raise EntityError('\n'.join(problems))
    return {d['id']: d for _, d in pairs}


_DEFS = None


def load():
    """모듈 수명 동안 한 번 읽는다(엔진 import 시점). 파일을 고쳤으면 reload()."""
    global _DEFS
    if _DEFS is None:
        _DEFS = read()
    return _DEFS


def reload():
    global _DEFS
    _DEFS = None
    return load()


def by_kind(kind):
    return [d for d in load().values() if d['kind'] == kind]


def get(eid):
    return load()[eid]


def monster(name_or_id):
    """몬스터 정의 — id('goblin') 또는 엔진 kind 이름('고블린'). 모르면 None."""
    defs = load()
    d = defs.get(name_or_id)
    if d and d['kind'] == 'monster':
        return d
    return next((d for d in by_kind('monster') if d['name'] == name_or_id), None)


def monster_stats(kind_name):
    """{'hp','atk','dmg','ac'} — 모르는 종은 기준선 몹(BASELINE_MONSTER)의 몸."""
    d = monster(kind_name) or monster(BASELINE_MONSTER)
    c = d['comps']
    return {'hp': c['health']['max'], 'atk': c['combat']['atk'], 'dmg': c['combat']['dmg'], 'ac': c['combat']['ac']}


def monster_flee(kind_name):
    """(hp_frac, stamina) — ai.flee 가 없는 종은 (None, None)=도주 안 함. 모르는 종은 기준선 몹."""
    d = monster(kind_name) or monster(BASELINE_MONSTER)
    fl = (d['comps'].get('ai') or {}).get('flee')
    return (fl['hp_frac'], fl['stamina']) if fl else (None, None)


def monster_flee_mode(kind_name):
    """(방향, 합류 범위) — ai.flee.to: 'away'(봇에게서 멀어짐, 기본) | 'ally'(근처 다른 몹에게 붙어 같이 싸운다, D51).
    합류 범위 = BFS 걸음 수 상한(join_range). flee 가 없는 종은 ('away', 0)."""
    d = monster(kind_name) or monster(BASELINE_MONSTER)
    fl = (d['comps'].get('ai') or {}).get('flee') or {}
    return (fl.get('to', 'away'), int(fl.get('join_range') or 0))


def mon_status():
    """몬스터 명중 시 태그 {kind 이름: 태그} — combat.on_hit 이 있는 종만."""
    return {d['name']: d['comps']['combat']['on_hit'] for d in by_kind('monster') if d['comps']['combat'].get('on_hit')}


def trap_kinds():
    """dungeon_gm.TRAP_KINDS 꼴 {id: {name, dc, dmg[, status]}}."""
    out = {}
    for d in by_kind('trap'):
        t = d['comps']['trap']
        out[d['id']] = {'name': d['name'], 'dc': t['dc'], 'dmg': t['dmg'], **({'status': t['status']} if t.get('status') else {})}
    return out


def gear_kinds():
    """dungeon_gm.GEAR_KINDS 꼴 {장비 이름: 보정} — equipment 부품이 있는 오브젝트."""
    return {d['name']: d['comps']['equipment']['bonus'] for d in by_kind('object') if d['comps'].get('equipment')}


def object_name(eid):
    """오브젝트 id → 엔진 피처 이름('treasure' → '보물', 'dagger' → '단검')."""
    return get(eid)['name']


def feature_tags(ftype):
    """조합형 관측의 피처 태그 — 정의의 tags(없는 type, 예: 마을 npc 피처 = ['object'])."""
    d = next((d for d in by_kind('object') if d.get('type') == ftype), None)
    return list(d['tags']) if d and d.get('tags') else ['object']


def npc(eid):
    """마을 NPC 정의 → {'name', 'line', 'line_again', 'gift'} (없는 칸은 None)."""
    d = get(eid)
    if d['kind'] != 'npc':
        raise EntityError('%s 은(는) npc 가 아니다' % eid)
    c = d['comps']['npc']
    return {'name': d['name'], 'line': c.get('line'), 'line_again': c.get('line_again'), 'gift': c.get('gift')}


def lore():
    """Dungeon.lore 꼴 {종키: {name, lore, brief?, unlock?}} — knowledge.deep 이 있는 정의만(옛 lore.json 과 같은 키·본문).
    D53: brief(처음 알게 된 한 줄)·unlock({event, count} — 심층 해금 조건)은 있을 때만 실린다. 둘 다 없으면 옛 2층
    (모름/앎)이라 등재 즉시 본문(lore) 전체가 주입된다 — 함정·상자·샘이 지금 그렇다(몬스터만 3층, 파트너 결정 09-12)."""
    out = {}
    for d in load().values():
        kn = d['comps'].get('knowledge') or {}
        deep = kn.get('deep')
        if not deep:
            continue
        key = {'monster': 'monster:' + d['name'], 'trap': 'trap:' + d['id'],
               'object': 'feature:' + d.get('type', d['id']), 'npc': 'npc:' + d['id']}[d['kind']]
        out[key] = {'name': d['name'], 'lore': deep}
        if kn.get('brief'):
            out[key]['brief'] = kn['brief']
        if kn.get('unlock'):
            out[key]['unlock'] = {'event': kn['unlock']['event'], 'count': int(kn['unlock']['count'])}
        if kn.get('review'):
            out[key]['review'] = {'event': kn['review']['event'], 'count': int(kn['review']['count'])}
    return out


def unlock_rules():
    """{종키: {event, count}} — 심층 해금 조건이 있는 종만(발급기 bestiary.Issuer 가 센다)."""
    return {k: v['unlock'] for k, v in lore().items() if v.get('unlock')}


def review_rules():
    """{종키: {event, count}} — 인식 갱신 조건(D55). 정의에 review 가 없으면 해금 조건을 그대로 쓴다
    (⚠️임시 가정 — 메모 §2-5 "갱신 카운트의 기준은 해금 조건과 달라도 된다": 다르게 두려면 정의에 review 를 적는다)."""
    return {k: (v.get('review') or v['unlock']) for k, v in lore().items() if v.get('unlock')}
