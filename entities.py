# -*- coding: utf-8 -*-
"""엔티티 저장소(D50, 2026-09-11 — 파트너 설계 메모 `WONDERLAND_CHANGES_2026-09-11.md` §4-1 [제안] 구조의 1차:
저장소 틀 먼저, 동작은 그대로).

정의(Def) = 바뀌지 않는 것: id·name·kind·tags·sprite·comps(부품). 인스턴스(게임 중 바뀌는 것 — 좌표·hp·상태)는
지금처럼 엔진의 Monster/Trap/Feature 객체가 든다. 엔진은 여기서 수치·이름·지식 본문을 읽는다:
  · 몬스터: health.max / combat.atk·dmg·ac·on_hit(명중 시 태그) / ai.flee.hp_frac·stamina(없으면 도주 안 함)·to·join_range(D51: ally=근처 몹에게 합류)
    D92(09-20): ai.pace(쫓을 때 한 칸 걷고 pace-1 틱을 선다 — 없으면 1=매 틱) · ai.spawn{pool:'plus', min_depth, pack}(새 몬스터 풀 —
    Dungeon(bestiary_plus=True) 인 층의 min_depth 부터 기존 고블린 일부와 바뀌어 놓인다. pack=한 묶음의 마릿수, 없으면 1)
  · 함정: trap.dc·dmg·status → dungeon_gm.TRAP_KINDS
  · 오브젝트: type(엔진 피처 type)·name → _add_feature 이름 / equipment.slot·bonus → GEAR_KINDS / tags → 조합형 관측 태그
  · NPC: npc.line·line_again·gift → show_runner.build_town (town.json 은 배치=id·좌표만)
  · 지식: knowledge.deep → Dungeon.lore (옛 lore.json 본문 그대로. 키 = monster:<name> / trap:<id> / feature:<type>)
    D53(09-12): knowledge.brief(처음 알게 된 한 줄)·unlock{event, count}(심층 해금 조건 — 코드가 센다, LLM 0콜)도 같은
    항목에 실린다. 지금 세는 사건은 encounter(개체 하나를 새로 인지한 순간 = aware_of 증분, 몬스터만)뿐 — 나머지 어휘는 자리.
  · 쓰임(D89, 09-20): 오브젝트·건물의 use{kind, …} — 곁에서 쓰면(use/interact) 무슨 일이 나는가를 정의가 말한다. 엔진은 kind 만 보고
    (interactables.py 의 kind 별 처리), 새 오브젝트·새 건물 기능은 JSON 한 장이다(D69 결정 ② "정의의 부품이 메뉴를 낸다"). 돈·가격은 없다.
    오브젝트의 story(trait·history)는 NPC·건물과 같은 꼴 — 배치한 쪽이 place_story 에 걸면 피처 줄 끝의 한 줄(about)이 된다.
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
KINDS = ('monster', 'trap', 'object', 'npc', 'map', 'building', 'quest', 'companion')   # quest(D61, 09-12): 길드 게시판의 의뢰 — 정보만
#   companion(D81, 09-17): 동료 프리셋 — 파티에 뽑히면 동료 칸의 시트(sheet), 안 뽑히면 마을 주민(npc·story, 2단계)
COMPS = {'monster': {'health', 'combat', 'ai', 'knowledge'},
         'trap': {'trap', 'knowledge'},
         'object': {'equipment', 'consumable', 'loot', 'container', 'heal', 'exit', 'knowledge',
                    'use', 'story'},             # D89(09-20): use=쓰임 부품(곁에서 쓰면 무슨 일이 나는가) · story=D75 와 같은 꼴(오브젝트의 특징 한 줄·이야기)
         'npc': {'npc', 'knowledge', 'story'},   # story=D75(09-15) 장소·사람 소개(trait 한 줄·history 본문) — 도감 지식과 다른 층(해금 없음)
         'map': {'space', 'story'}, 'building': {'building', 'board', 'oracle', 'story', 'use'},   # D61 건물 역할 부품(메모 §4-4 [제안]): 게시판·신탁 · story=D75 · use=D89 문턱에서 쓰는 기능
         'quest': {'quest'},
         'companion': {'sheet', 'npc', 'story'}}   # D81: sheet=파티 시트 칸(능력치 없음 — 직업에서) · npc/story=마을 주민일 때의 말·걸음·소개(NPC 와 같은 꼴)
UNLOCK_EVENTS = {'encounter', 'kill', 'search_first', 'trap_avoid', 'trap_disarm', 'visit', 'talk'}   # 메모 §2-5 어휘.
#   코드가 세는 건 encounter 뿐(bestiary.Issuer, D53) — 나머지는 검증기만 아는 예약어(정의에 적어도 아직 안 센다).
BASELINE_MONSTER = '고블린'   # 모르는 종(장면 저작의 임의 이름)은 기준선 몹의 몸 — 낯선 짐승도 몸은 있다
SPAWN_POOLS = ('plus',)       # D92(09-20) ai.spawn.pool 어휘 — plus = 새 몬스터 풀(스위치 DUNGEON_BESTIARY_PLUS 를 켠 판에만 놓인다)
PLUS_MIN_DEPTH = 2            # D92 새 몬스터가 놓이기 시작하는 층 — 1층은 의뢰(goblin_cull)·주점 소문의 실측이 걸려 있어 바꾸지 않는다


class EntityError(ValueError):
    """정의 파일의 문제 — 전부 모아 한 번에 알린다(로드 단계에서 죽는 게 낫다)."""


QUEST_REQ_KINDS = ('kill', 'reach', 'loot')   # D69(09-14) 의뢰 완료 조건의 종류 — dungeon_gm.QUEST_REQ_KINDS 와 같은 목록

# D89(2026-09-20) 쓰임 부품 use{kind, …} 의 어휘 — 처리는 interactables.py(kind 마다 하나), 여기는 검증기가 아는 꼴.
#   kind → 그 kind 가 읽는 칸. 공통 칸: once(true = 한 번 쓰면 끝 — 누가 쓰든 세계의 상태, 피처는 남는다)·note(저작 메모).
#   돈·가격·매매는 없다(D69 에서 제출 뒤로 보류) — browse 는 구경만, rummage 에서 나오는 건 엔진이 이미 아는 소지뿐.
USE_KINDS = {'read': ('text', 'texts'),      # 적힌 글을 읽는다 — text(한 편) 또는 texts(여러 편: 읽는 사람마다 읽을 때마다 다음 글)
             'sit': ('heal',),               # 앉아 숨을 돌린다 — heal(기본 1, 상처가 있을 때만 오른다)
             'drink': ('heal',),             # 물을 마신다 — heal(기본 1)
             'browse': ('wares',),           # 진열된 것을 구경한다 — wares(이름 목록)
             'practice': (),                 # 몸을 푼다 — 몸에 남는 효과 없음(한 턴)
             'rummage': ('loot',),           # 뒤진다 — loot[{item, w}] 가중 추첨(세계 시드·자리에서 정해진다 — 판정 rng 무접촉). 늘 한 번
             'lodge': (),                    # 묵는다 — HP 전부 + 상태 태그 소거(D34 '지우기는 휴식뿐': 묵기는 휴식이다)
             'warm': ('heal',)}              # 불을 쬔다 — heal(기본 1)
USE_LOOT = ('potion', 'treasure', 'nothing')   # rummage 에서 나오는 것 — 물약 수·보물 수(bag)·빈손
USE_RESERVED_TYPES = ('exit', 'stairs_up', 'npc', 'treasure', 'potion', 'weapon', 'armor', 'chest', 'fountain', 'grave', 'building')
#   엔진이 이미 제 뜻으로 다루는 피처 type — 오브젝트 정의가 이 type 에 use 를 달면 거절한다(_interact 의 타입 분기가 먼저 잡아
#   use 가 영영 안 불리는데 관측은 '쓸 수 있다'고 말하게 된다 = 거짓 선택지). 건물의 use 는 건물 정의(kind building)에 단다.


def _use_problems(rel, use):
    """use 부품 한 칸의 꼴 검사(D89) — 모르는 kind·모르는 칸·빈 글·음수 회복·빈 추첨표는 로드 단계에서 죽는다."""
    if not isinstance(use, dict) or use.get('kind') not in USE_KINDS:
        return ['%s: use.kind 는 %s 중 하나' % (rel, '|'.join(USE_KINDS))]
    out, kind = [], use['kind']
    extra = set(use) - {'kind', 'once', 'note'} - set(USE_KINDS[kind])
    if extra:
        out.append('%s: use(%s) 가 모르는 칸 %s' % (rel, kind, sorted(extra)))
    if use.get('once') is not None and type(use['once']) is not bool:
        out.append('%s: use.once 는 true|false' % rel)
    if kind == 'read':
        one, many = use.get('text'), use.get('texts')
        ok_one = isinstance(one, str) and bool(one.strip())
        ok_many = isinstance(many, list) and bool(many) and all(isinstance(t, str) and t.strip() for t in many)
        if (one is not None and not ok_one) or (many is not None and not ok_many) or (ok_one == ok_many):
            out.append('%s: use(read) 는 text(글 한 편) 또는 texts(비어 있지 않은 글 목록) 중 하나' % rel)
    if 'heal' in USE_KINDS[kind] and use.get('heal') is not None and not (type(use['heal']) is int and use['heal'] >= 0):
        out.append('%s: use.heal 은 정수≥0' % rel)
    if kind == 'browse':
        wares = use.get('wares')
        if not (isinstance(wares, list) and wares and all(isinstance(w, str) and w.strip() for w in wares)):
            out.append('%s: use(browse).wares 는 비어 있지 않은 이름 목록' % rel)
    if kind == 'rummage':
        loot = use.get('loot')
        if not (isinstance(loot, list) and loot and all(isinstance(e, dict) and e.get('item') in USE_LOOT
                                                          and type(e.get('w', 1)) is int and e.get('w', 1) >= 1 for e in loot)):
            out.append('%s: use(rummage).loot 는 [{item: %s, w: 정수≥1}] 목록' % (rel, '|'.join(USE_LOOT)))
        if use.get('once') is False:                 # 뒤질 때마다 나오면 소지가 끝없이 는다 — 통은 한 번 비면 빈 통이다
            out.append('%s: use(rummage) 는 늘 한 번이다(once 를 false 로 둘 수 없다)' % rel)
    return out


def _problems(pairs, root):
    out, ids = [], {}
    boards, kinds_by_id = [], {}                     # D61 2차 검사 재료
    quest_mons = []                                  # D69 2차 검사 재료(처치형 의뢰의 몬스터 id)
    companion_names = []                             # D81 2차 검사 재료(동료 이름 — 파티 안에서 이름이 곧 열쇠라 서로 달라야 한다)
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
        st = comps.get('story')                              # D75(09-15) 장소·사람 소개 — trait(특징 한 줄)·history(역사·이야기), 문자열만(하나 이상)
        if st is not None and (not isinstance(st, dict) or not st or set(st) - {'trait', 'history'}
                               or not all(isinstance(v, str) and v.strip() for v in st.values())):
            out.append('%s: story 는 trait(특징 한 줄)·history(역사·이야기) 문자열만(하나 이상)' % rel)
        if comps.get('use') is not None:                     # D89(09-20) 쓰임 부품 — 오브젝트·건물 공용(꼴은 _use_problems)
            out.extend(_use_problems(rel, comps['use']))
            if kind == 'object' and d.get('type') in USE_RESERVED_TYPES:
                out.append('%s: type %r 은(는) 엔진이 이미 제 뜻으로 다룬다 — use 부품을 달 수 없다' % (rel, d.get('type')))
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
            ai = comps.get('ai') or {}                       # D92(09-20) 걸음 박자·새 몬스터 풀 — 둘 다 선택
            if ai.get('pace') is not None and not (type(ai['pace']) is int and ai['pace'] >= 1):
                out.append('%s: ai.pace 는 정수≥1(쫓을 때 한 칸 걷고 pace-1 틱을 선다)' % rel)
            spawn = ai.get('spawn')
            if spawn is not None:
                if not isinstance(spawn, dict) or spawn.get('pool') not in SPAWN_POOLS:
                    out.append('%s: ai.spawn.pool 은 %s 중 하나' % (rel, '|'.join(SPAWN_POOLS)))
                elif not (type(spawn.get('min_depth', PLUS_MIN_DEPTH)) is int and spawn.get('min_depth', PLUS_MIN_DEPTH) >= PLUS_MIN_DEPTH):
                    out.append('%s: ai.spawn.min_depth 는 정수≥%d(1층은 바꾸지 않는다)' % (rel, PLUS_MIN_DEPTH))
                elif not (type(spawn.get('pack', 1)) is int and spawn.get('pack', 1) >= 1):
                    out.append('%s: ai.spawn.pack 은 정수≥1(한 묶음의 마릿수)' % rel)
        if kind == 'trap':
            for k in ('dc', 'dmg'):
                if not isinstance((comps.get('trap') or {}).get(k), int):
                    out.append('%s: trap.%s 정수 필요' % (rel, k))
        if kind == 'npc' and not (comps.get('npc') or {}).get('line'):
            out.append('%s: npc.line 필요' % rel)
        if kind == 'companion':                              # D81 동료 프리셋 — 시트 칸은 시트 조립기가 그대로 검증한다(직업·키워드·상한·외형)
            import sheetkit                                  # 지연 import — 엔진 import 경로에 시트 도구를 끌어들이지 않는다(표준 라이브러리만 쓰는 모듈)
            try:
                sheetkit.build_companion_sheet(d)
            except (ValueError, OSError) as e:
                out.append('%s: sheet — %s' % (rel, e))
            if comps.get('npc') is not None and not (comps.get('npc') or {}).get('line'):
                out.append('%s: npc 부품이 있으면 npc.line 필요' % rel)
            companion_names.append((rel, d.get('name')))
        if kind in ('npc', 'companion') and (comps.get('npc') or {}).get('walk') is not None:   # D73 행인 — 구역 id 문자열 + 걸음 확률 0~1
            wk = (comps.get('npc') or {}).get('walk')
            if not isinstance(wk, dict) or not isinstance(wk.get('region'), str) or not wk['region']:
                out.append('%s: npc.walk 는 {region(layout 구역 id), rate} 객체' % rel)
            elif not (isinstance(wk.get('rate', 0.5), (int, float)) and 0 <= wk.get('rate', 0.5) <= 1):
                out.append('%s: npc.walk.rate 는 0~1' % rel)
            elif wk.get('rect') is not None and not (isinstance(wk['rect'], list) and len(wk['rect']) == 4
                                                     and all(type(v) is int for v in wk['rect']) and wk['rect'][2] > 0 and wk['rect'][3] > 0):
                out.append('%s: npc.walk.rect 는 정수 [x,y,w,h](layout 좌표 — 구역 안의 걷는 자리, D82)' % rel)
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
            req = q.get('req')                       # D69(09-14) 완료 조건 — 엔진이 세는 사건. 없으면 정보만인 의뢰(맡을 수는 있다)
            if req is not None:
                if not isinstance(req, dict) or req.get('kind') not in QUEST_REQ_KINDS:
                    out.append('%s: quest.req.kind 는 %s 중 하나' % (rel, '|'.join(QUEST_REQ_KINDS)))
                else:
                    n = req.get('n', 1)
                    if not (isinstance(n, int) and n >= 1):
                        out.append('%s: quest.req.n 은 정수≥1' % rel)
                    if req['kind'] == 'kill' and not isinstance(req.get('monster'), str):
                        out.append('%s: quest.req(kill) 은 monster(몬스터 정의 id) 필요' % rel)
                    if req['kind'] == 'reach' and not (isinstance(req.get('depth'), int) and req['depth'] >= 1):
                        out.append('%s: quest.req(reach) 은 depth(정수≥1) 필요' % rel)
                    if req['kind'] == 'loot' and not isinstance(req.get('object'), str):
                        out.append('%s: quest.req(loot) 은 object(엔진 피처 type) 필요' % rel)
                    if req.get('depth') is not None and not (isinstance(req['depth'], int) and req['depth'] >= 1):
                        out.append('%s: quest.req.depth 는 정수≥1' % rel)
                    if req['kind'] == 'kill':
                        quest_mons.append((rel, req.get('monster')))
        kinds_by_id[eid] = kind
    for rel, qids in boards:                         # 2차: 게시판이 가리키는 의뢰가 실제 quest 정의인가
        for qid in qids:
            if kinds_by_id.get(qid) != 'quest':
                out.append('%s: board.quests 의 %r 는 quest 정의가 아니다' % (rel, qid))
    for rel, mid in quest_mons:                      # 2차(D69): 처치형 의뢰의 몬스터가 실제 monster 정의인가
        if kinds_by_id.get(mid) != 'monster':
            out.append('%s: quest.req.monster %r 는 monster 정의가 아니다' % (rel, mid))
    seen_names = {}
    for rel, nm in companion_names:                  # 2차(D81): 동료 이름은 서로 달라야 한다(둘을 같이 뽑으면 파티 이름 중복)
        if nm in seen_names:
            out.append('%s: 동료 이름 %r 중복(%s)' % (rel, nm, seen_names[nm]))
        seen_names[nm] = rel
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


def monster_pace(kind_name):
    """걸음 박자(D92, ai.pace) — 쫓을 때 한 칸 걷고 pace-1 틱을 선다. 정의에 없거나 모르는 종은 1(매 틱 걷는다 = 옛 그대로)."""
    d = monster(kind_name)
    return int(((d or {}).get('comps', {}).get('ai') or {}).get('pace') or 1)


def _in_plus_pool(d):
    return d['kind'] == 'monster' and ((d['comps'].get('ai') or {}).get('spawn') or {}).get('pool') == 'plus'


def plus_monsters():
    """새 몬스터 풀(D92) [{name, min_depth, pack}] — ai.spawn.pool == 'plus' 인 종, 정의 id 순(결정론).
    엔진(Dungeon._place_plus)이 bestiary_plus 를 켠 층에서만 읽는다 — 끈 판은 이 목록을 부르지도 않는다."""
    out = []
    for d in sorted(by_kind('monster'), key=lambda d: d['id']):
        if _in_plus_pool(d):
            sp = d['comps']['ai']['spawn']
            out.append({'name': d['name'], 'min_depth': int(sp.get('min_depth') or PLUS_MIN_DEPTH), 'pack': int(sp.get('pack') or 1)})
    return out


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
    return {'name': d['name'], 'line': c.get('line'), 'line_again': c.get('line_again'), 'gift': c.get('gift'),
            # D69(09-14): 역할 한 줄·성격·보고 역할·보고 대사(전부 선택 — 없으면 None. 판정은 report 만, 나머지는 문장 재료)
            'role': c.get('role'), 'persona': c.get('persona'), 'report': bool(c.get('report')),
            'line_report': c.get('line_report'), 'line_report_failed': c.get('line_report_failed'),
            'line_report_empty': c.get('line_report_empty'), 'knows': list(c.get('knows') or []),
            # D71(09-14): NPC 가 먼저 거는 인사 — hail(기본)·hail_no_potion·hail_board·hail_return·hail_rumor·hail_oracle(전부 선택, 상황별)
            **{k: c.get(k) for k in ('hail', 'hail_no_potion', 'hail_board', 'hail_return', 'hail_rumor', 'hail_oracle',
                                     'hail_party', 'line_party')},   # D84 조각 5: 파티 결성 판에서 입구의 규칙을 말해 주는 인사·대사 꼬리({party_need})
            'walk': (dict(c['walk']) if isinstance(c.get('walk'), dict) else None)}   # D73(09-14) 행인: {region: layout 구역 id, rate}


def companions():
    """동료 프리셋 {id: 정의} — 파일 이름(id) 순(D81). 시트는 sheetkit.build_companion_sheet(정의)로 조립한다."""
    return {d['id']: d for d in sorted(by_kind('companion'), key=lambda d: d['id'])}


def lore(plus=True):
    """Dungeon.lore 꼴 {종키: {name, lore, brief?, unlock?}} — knowledge.deep 이 있는 정의만(옛 lore.json 과 같은 키·본문).
    D53: brief(처음 알게 된 한 줄)·unlock({event, count} — 심층 해금 조건)은 있을 때만 실린다. 둘 다 없으면 옛 2층
    (모름/앎)이라 등재 즉시 본문(lore) 전체가 주입된다 — 함정·상자·샘이 지금 그렇다(몬스터만 3층, 파트너 결정 09-12).
    D92(09-20): plus=False 면 새 몬스터 풀(ai.spawn.pool 'plus')의 종을 뺀다 — 러너가 스위치를 끈 판의 사전(run_meta.bestiary_defs·
    도감 창의 카드)을 옛 판과 같게 두려고 쓴다. 기본(True)은 정의 전부."""
    out = {}
    for d in load().values():
        kn = d['comps'].get('knowledge') or {}
        deep = kn.get('deep')
        if not deep or (not plus and _in_plus_pool(d)):
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
