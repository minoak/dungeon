# -*- coding: utf-8 -*-
"""쓰임 부품(D89, 2026-09-20) — 오브젝트·건물과의 상호작용을 **정의(JSON)의 부품**이 낸다.

배경: 실판 집계로 마을은 '성직자 → 접수원 → 주점 → 게시판 → 던전 입구' 체크리스트였다. 설계 원장 D83 의 남은 기둥 C =
"마을에서 할 일의 행동 수단이 없다", D69 결정 ② = "마을 동사를 코드에 하나씩 박지 않고 정의의 부품이 관측 대상·메뉴를 낸다 …
엔진은 부품만 보고, 새 건물은 JSON 한 장". 이 모듈이 그 뼈대다.

  · 새 동사는 없다 — 전부 기존 `use`(메뉴형 `interact`) 밑이다. Dungeon._interact 가 아는 타입(계단·NPC·보물·상자·샘·장비)을
    다 지난 마지막 'nothing' 직전에 handle() 한 줄로 이어진다. 메뉴형·조합형이 같은 _interact 를 타므로 두 경로가 한 번에 열린다.
  · 엔진은 kind 만 본다: 피처 → 정의(오브젝트 = type·이름이 같은 entities/object 정의, 건물 = building_defs 의 정의 id) →
    comps.use → kind 처리기. 새 오브젝트·새 건물 기능 = JSON 한 장(코드 무수정). 새 kind 만 여기 처리기 하나 + entities.USE_KINDS 한 줄.
  · 쓰고도 남는다 — 피처를 지우지 않는다(샘·상자의 del 을 따라 하지 않는다). once 로 다 쓴 것은 세계의 상태(d.use_spent)로 남고
    다시 쓰면 'used_up' 사실이 돌아온다. 스트림의 피처 as_dict 는 그대로다(verify_stream 필드 전수 일치).
  · 판정 rng(d.rng·d20)를 건드리지 않는다 — 뒤지기의 추첨은 세계 시드·층·피처 자리의 해시다(통에 무엇이 들었나는 세계가 지어질 때
    이미 정해진 사실이다). 그래서 use 부품이 없는 세계는 옛 판과 바이트가 같다(verify_skill_off).
  · p0.5.13(경제 1a, .orch/drafts/economy_design.md): 돈은 골드(몸의 정수 bot['gold'])다. 가게 = kind 'shop' 하나 — 상품은 문턱 SHOP_RANGE 칸 안에서
    ID(g<n>)가 붙은 관측 대상이고 `buy g<n>` = 사기(buy — 메뉴형은 `interact g<n>`), `sell <가게 f…> item=<소지 ID>` = 팔기(sell — 엔진이 값을 정한다: buys 에 적힌 값 또는
    파는 값의 절반). p0.5.29 전엔 둘 다 use 의 갈래였다(지금 use 로는 사고팔지 않는다 — composed_actions._use). 묵기는 정의의 price 를 낸다. browse 는 여전히 구경만이다. 흥정·재고·NPC 지갑은 없다(1a 범위 밖).
  · 문장은 사실만(조언·결론·행동 지시 없음) — 엔진이 실제로 한 일만 말한다. ⚠️아래 문장·라벨·태그 낱말은 전부 임시(검토표 등재 대상).
  · 다 쓴 것은 다 쓴 것으로 보인다(09-20 리뷰 수선) — once 로 다 쓴 피처는 관측의 use 칸에 spent 가 실리고, 메뉴 라벨·조합형
    '대상의 현재 사실' 줄이 효과 꼬리('마시면 HP +3') 대신 '이미 쓰였다'는 사실만 말한다(남이 다 쓴 뒤의 다른 캐릭터에게도 — 세계의 상태).
  · 마을 생활 판(D90, d.town_life)의 건물은 정의의 life.use 를 쓴다(entities.comps_of) — 끈 판의 건물은 옛 판 그대로 쓰임이 없다.
  · 세계의 스위치 뒤에 있는 kind 가 있다(D95 공물, _GATE_ATTR) — 끈 판에서는 정의에 부품이 있어도 use_of 가 None 이라
    관측·메뉴·태그·실행·오브젝트 태그가 한 눈으로 '없는 것'이 된다(끈 판 = 옛 판과 바이트 동일).

결과 dict 는 기존 interact 결과와 같은 꼴: {char, type:'interact', target, result, what, use_kind, …사실}.
  kind → result:  read→read{text[,page,pages]} · sit→sat{heal,hp} · drink→drank{heal,hp} · browse→browsed{wares} ·
                  practice→practiced · rummage→rummaged{got[,potions|bag,quest]} · lodge→lodged{heal,hp,cleared[,paid,gold]} | too_poor{price,gold} ·
                  warm→warmed{heal,hp} · offer→offered{cost,bag,stat,value[,hp]} | offer_short{cost,bag} · once 로 다 쓴 뒤→used_up ·
                  shop→browsed{wares,buys}(물건 없이 쓰면 진열과 값) · buy(g<n>)→bought{what,price,gold,…}|too_poor|no_room ·
                  sell(item)→sold{what,n,price,got,gold,…}|no_deal|not_enough ·
                  p0.5.16 그 자리에서 먹는 음식(type food)의 buy → need_fill{via:'buy',need,what,price,gold,…}|need_none{why:'full'}(사지 않는다)|too_poor ·
                  쉬기 효과가 막힌 몸(needs.no_regen — 굶주림)의 sit·drink·warm·lodge → heal 0 + no_regen{욕구 id}(묵기는 몸 상태는 낫는다)
  (뒤져서 나온 것의 칸 이름이 `found` 가 아니라 `got` 인 까닭: `found` 는 수색 결과의 [{kind,name…}] 목록 계약이라
   tags.py·bestiary.py 가 모든 이벤트의 found 를 목록으로 돈다 — 문자열을 실으면 그 집계기들이 죽는다.)
"""
import hashlib

import entities as ENT
import needs as NE

# kind → 표현 재료. label=메뉴형 줄 머리 · tag=조합형 대상의 사실 태그 · tried=D39 오브젝트 태그의 '~해 봄' · seen=목격(ally_use)의 괄호 한 마디
# ⚠️문구 임시 — 전부 SilenceBreaker 초안(파트너 문장 대기)
KINDS = {
    'read':     {'label': '읽기',     'tag': 'readable',  'tried': '읽어 봄',     'seen': '글을 읽었다'},
    'sit':      {'label': '앉기',     'tag': 'seat',      'tried': '앉아 봄',     'seen': '앉아 쉬었다'},
    'drink':    {'label': '마시기',   'tag': 'drinkable', 'tried': '마셔 봄',     'seen': '물을 마셨다'},
    'browse':   {'label': '구경하기', 'tag': 'wares',     'tried': '구경해 봄',   'seen': '구경했다'},
    'practice': {'label': '몸 풀기',  'tag': 'practice',  'tried': '몸 풀어 봄',  'seen': '몸을 풀었다'},
    'rummage':  {'label': '뒤지기',   'tag': 'container', 'tried': '뒤져 봄',     'seen': None},      # 목격 한 마디는 나온 것에 따라(아래 _GOT_SEEN)
    'lodge':    {'label': '묵기',     'tag': 'lodging',   'tried': '묵어 봄',     'seen': '묵었다'},
    'warm':     {'label': '불 쬐기',  'tag': 'warmth',    'tried': '불 쬐어 봄',  'seen': '불을 쬐었다'},
    'offer':    {'label': '바치기',   'tag': 'offering',  'tried': '바쳐 봄',     'seen': None},      # 목격 한 마디는 바쳤나·못 바쳤나에 따라(아래 _OFFER_SEEN)
    'shop':     {'label': '사고팔기', 'tag': 'shop',      'tried': '들러 봄',     'seen': '진열된 것을 둘러보았다'},   # p0.5.13 가게 — 사고판 목격은 물건 이름으로(buy·sell)
}
assert set(KINDS) == set(ENT.USE_KINDS), '쓰임 kind 어휘는 entities.USE_KINDS 와 같아야 한다(검증기 ↔ 처리기)'
# D90(09-20) read 의 동사 변형(use.verb) — 처리·결과 이름은 read 그대로이고 말만 바뀐다(글이 아니라 눈에 보이는 것을 돌려주는 화단 같은 것).
# ⚠️문구 임시
VERBS = {'look': {'label': '살펴보기', 'tag': 'lookable', 'tried': '살펴봄', 'seen': '살펴보았다'}}
assert set(VERBS) == set(ENT.USE_READ_VERBS), 'read 동사 어휘는 entities.USE_READ_VERBS 와 같아야 한다(검증기 ↔ 처리기)'


def _info(use):
    """쓰임(정의의 use 부품 또는 관측의 use 칸) → 표현 재료 — read 에 verb 가 있으면 그 동사의 말, 아니면 kind 의 말. 모르면 None."""
    use = use or {}
    return VERBS.get(use.get('verb')) if (use.get('kind') == 'read' and use.get('verb')) else KINDS.get(use.get('kind'))

RESULTS = ('read', 'sat', 'drank', 'browsed', 'practiced', 'rummaged', 'lodged', 'warmed', 'used_up',
           'offered', 'offer_short',       # D95(09-20) 공물 — 바쳤다 / 바칠 보물이 모자랐다
           'bought', 'sold', 'too_poor', 'no_deal', 'not_enough', 'no_room')   # p0.5.13 가게·묵기 값 — 샀다 / 팔았다 / 골드가 모자랐다 /
#   이 가게는 그것을 사들이지 않는다 / 판다는 개수만큼 지니지 않았다 / 산 장비와 바꿔 들 때 들던 것을 내려놓을 발밑이 없다
SHOP_RANGE = 2       # p0.5.13 상품(g<n>)이 관측 대상이 되고 살 수 있는 거리 — 가게 피처(문턱)에서 체비셰프 칸 수(게시판 의뢰의 range 2 와 같은 자)
COUNTED = {'treasure': 'bag', 'potion': 'potions', 'boon': 'boons', 'gold': 'gold',   # 몸의 정수로 세는 소지 type → 몸 칸
           'ration': 'rations'}                                                     # p0.5.16 휴대식(소지 칸 i9)
AMOUNT_SLOTS = ('gold', 'treasure')   # p0.5.13 개수(amount)를 받는 소지 — 골드(액수)·보물(개수). 물약·축복은 지금처럼 한 병씩
_HEAL_KINDS = {'sit': 'sat', 'drink': 'drank', 'warm': 'warmed'}
_GOT_KR = {'potion': '물약', 'treasure': '보물', 'ration': '휴대식'}
_GOT_SEEN = {'potion': '물약을 꺼냈다', 'treasure': '보물을 꺼냈다', 'nothing': '빈손이었다',
             'ration': '휴대식을 꺼냈다'}   # p0.5.16 ⚠️문구 임시

# ── D95(2026-09-20) 공물 — 파트너 "원정을 돌고 나서 보물이나 특정 재물을 신에게 바치면 신이 모험가의 능력치를 올려줄수 있어야 한다고
#    생각해. 캐릭터를 관리하는건 신의 몫으로 두는거지" / "결산을 통해서 얻은 자원들로 캐릭터 성장에 이용해야 한다".
#    돈은 만들지 않는다(D69 에서 제출 뒤로 보류) — 보물(bot['bag'])은 이미 세계에 있는 물건이고 지금 쓸 곳이 없었다. 그 빈자리를 쓴다.
OFFER_COST = 3                             # ⚠️값 임시 — 한 번 바치는 데 드는 보물 수(파트너 값 대기). 상한은 두지 않는다: 모은 보물이 곧 상한이다
OFFER_STATS = ('str', 'dex', 'maxhp')      # 신이 고르는 칸(차례 = 해시 자리) — 몸에 직접 적히는 수치뿐(새 몸 변수를 만들지 않는다)
_STAT_KR = {'str': '힘', 'dex': '민첩', 'maxhp': '최대 HP'}         # dungeon_gm.STAT_KR + 최대 HP(공물에서만 쓰는 말이라 여기 사본)
_STAT_OBJ = {'str': '힘을', 'dex': '민첩을', 'maxhp': '최대 HP 를'}   # 목적격 — 라틴 글자 뒤는 띄어 쓴다('HP 가 전부 돌아오고' 관례)
_OFFER_SEEN = {'offered': '신전에 보물을 바쳤다', 'offer_short': '바치려다 그만두었다'}   # ⚠️문구 임시 — 곁의 사람이 보는 한 마디(ally_use 괄호)
# p0.5.13 가게·묵기 값의 목격 한 마디(ally_use 괄호) — 무엇을 사고팔았나는 보이고, 얼마를 냈는지·남은 지갑은 보이지 않는다. ⚠️문구 임시
_TRADE_SEEN = {'bought': '%s 샀다', 'sold': '%s 팔았다', 'buy_short': '사려다 그만두었다', 'lodge_short': '묵으려다 그만두었다',
               'ate': '%s 사 먹었다', 'full': '사 먹으려다 그만두었다'}   # p0.5.16 그 자리에서 먹는 음식 — 먹었다·안 먹었다는 보이고 배가 불렀는지는 보이지 않는다

_IDX = {'src': None, 'n': -1, 'by_type': {}}


def _by_type():
    """오브젝트 정의 색인 {피처 type: [use 부품이 있는 정의]} — 정의 사전이 바뀌면(재로드·게이트의 주입) 다시 짓는다."""
    defs = ENT.load()
    if _IDX['src'] is not defs or _IDX['n'] != len(defs):
        idx = {}
        for df in sorted(defs.values(), key=lambda v: v['id']):
            if (df.get('kind') == 'object' and df.get('type') and (df.get('comps') or {}).get('use')
                    and df['type'] not in ENT.USE_RESERVED_TYPES):      # 엔진이 제 뜻으로 아는 type 은 검증기가 이미 거절한다 — 여기서도 안 집는다
                idx.setdefault(df['type'], []).append(df)
        _IDX.update(src=defs, n=len(defs), by_type=idx)
    return _IDX['by_type']


# D95(09-20) 세계의 스위치 뒤에 있는 kind → 그 스위치를 담은 Dungeon 속성. 끈 판에서는 정의에 부품이 있어도 use_of 가 None 을 돌려준다
#   = 관측의 use 칸·메뉴 줄·조합형 태그·실행·오브젝트 태그가 한 눈으로 '없는 것'이 된다(끈 판 = 옛 판과 바이트 동일).
_GATE_ATTR = {'offer': 'offer_on'}


def use_of(d, f):
    """피처 → use 부품(dict) 또는 None. 건물 = 그 문턱 피처의 정의 id(building_defs — build_town 이 둔다),
    오브젝트 = type 이 같은 정의(같은 type 을 여러 정의가 쓰면 이름이 같은 것 먼저 — 무기 단검·장검과 같은 문법).
    스위치 뒤의 kind(_GATE_ATTR)는 그 스위치를 켠 세계에서만 돌려준다."""
    use = _use_raw(d, f)
    attr = _GATE_ATTR.get((use or {}).get('kind'))
    if attr and not getattr(d, attr, False):   # 옛 피클 스냅샷·from_ascii(__new__)엔 없는 속성 — getattr 기본 False
        return None
    return use


def _use_raw(d, f):
    """정의·세계가 적어 둔 그대로의 use 부품(스위치 무시) — use_of 만 부른다."""
    if f is None:
        return None
    over = (getattr(d, 'use_over', None) or {}).get(f.id)   # D92(09-20) 피처마다 다른 쓰임 — 던전 석판의 본문은 그 층의 사실이라
    if over:                                                #   정의 한 장으로는 말할 수 없다. 세계의 상태가 정의보다 먼저다(옛 피클엔 없는 칸 — getattr)
        return over
    if f.type == 'building':
        eid = (getattr(d, 'building_defs', None) or {}).get(f.id)
        try:                                     # D90: 마을 생활 판(d.town_life — build_town 이 켠 판에만 건다)이면 정의의 life.use 를 얹어 읽는다
            return (ENT.comps_of(eid, life=bool(getattr(d, 'town_life', False))).get('use') or None) if eid else None
        except KeyError:
            return None
    cands = _by_type().get(f.type)
    if not cands:
        return None
    df = next((c for c in cands if c.get('name') == f.name), cands[0])
    return df['comps']['use']


def _heal_of(use):
    return int(use.get('heal', 1)) if use.get('heal') is not None else 1


def obs_fact(d, f):
    """view() 용 — 피처 항목에 얹을 {'use': {kind[, verb][, heal | spent]}}(쓰임 부품이 있는 피처만 — 없는 피처는 {} = 옛 obs 그대로).
    메뉴 라벨·조합형 '대상의 현재 사실' 줄·대상 태그가 전부 이 한 칸에서 나온다(건물의 정의는 두뇌 쪽에서 못 찾으므로 여기서 싣는다)."""
    use = use_of(d, f)
    if not use:
        return {}
    k = use['kind']
    spent = (bool(use.get('once')) or k == 'rummage') and f.id in (getattr(d, 'use_spent', None) or {})   # 다 쓴 것 = 세계의 상태(누가 보든)
    return {'use': {'kind': k, **({'verb': use['verb']} if (k == 'read' and use.get('verb')) else {}),
                    **({'spent': True} if spent else ({'heal': _heal_of(use)} if k in _HEAL_KINDS else {})),   # 다 쓴 것엔 효과 수치를 싣지 않는다(있을 때만)
                    **({'price': int(use['price'])} if (k == 'lodge' and use.get('price')) else {})}}   # p0.5.13 묵는 값(있을 때만 — 값 없는 숙소는 옛 칸 그대로)


def tags(fact):
    """조합형 대상 목록의 사실 태그 — obs 피처의 use 칸 → ['interactable', '<kind 태그>']."""
    info = _info(fact)
    return ['interactable', info['tag']] if info else []


def fact_text(fact):
    """몸에 남는 효과의 사실 한 줄(엔진이 실제로 하는 것만 — 수치는 정의에서). 메뉴 라벨 꼬리·조합형 '대상의 현재 사실' 줄 공용.
    효과가 없는 kind(읽기·구경·몸 풀기·뒤지기)와 heal 0 은 None — 줄 머리·태그가 이미 말한다. once 로 다 쓴 것(spent)은 kind 와
    무관하게 그 사실 한 줄만(효과 수치 없음 — 09-20 리뷰: 남이 다 쓴 마시는 곳이 다른 캐릭터에게 '마시면 HP +3' 이라던 자리). ⚠️문구 임시"""
    k, heal = (fact or {}).get('kind'), int((fact or {}).get('heal') or 0)
    if (fact or {}).get('spent'):                # once 로 다 쓴 것 — 효과 꼬리 대신 그 사실만(직전 결과 used_up 의 문장과 같은 말)
        return '이미 비어 있다' if k == 'rummage' else '이미 쓰였다 — 더 나오는 것이 없다'
    if k == 'sit' and heal:
        return '앉으면 HP +%d (상처가 있을 때)' % heal
    if k == 'drink' and heal:
        return '마시면 HP +%d (상처가 있을 때)' % heal
    if k == 'warm' and heal:
        return '불을 쬐면 HP +%d (상처가 있을 때)' % heal
    if k == 'lodge':
        price = int((fact or {}).get('price') or 0)  # p0.5.13 묵는 값 — 값이 있는 숙소만 꼬리가 붙는다(⚠️문구 임시)
        return (('묵으면 몸 상태가 낫는다' if (fact or {}).get('no_regen')   # p0.5.16 굶주린 몸 — HP 가 돌아온다는 말을 하지 않는다(보는 사람 몫의 사실)
                 else '묵으면 HP 가 전부 돌아오고 몸 상태가 낫는다') + ((' — 값 %d골드' % price) if price else ''))
    if k == 'offer':                             # D95 — 값·오르는 칸은 사실, 무엇이 오를지는 말하지 않는다(신이 고른다)
        return '모은 보물 %d개를 바치면 %s 중 하나가 1 오른다(무엇이 오를지는 신이 정한다)' % (
            OFFER_COST, '·'.join(_STAT_KR[s] for s in OFFER_STATS))
    return None


def menu_label(f, sfx=''):
    """메뉴형 한 줄 — '앉기: 벤치 f6 (발밑/인접) — 앉으면 HP +1 (상처가 있을 때)'. 머리 낱말이 무엇을 하는 줄인지 말하고(말 걸기·장비 선례),
    몸에 남는 효과가 있는 kind 만 꼬리에 수치를 단다(장비 라벨 '걸치면 피해 +N' 선례 — 사실만, 결론 없음). f = obs 피처 항목."""
    fact = f.get('use') or {}
    tail = fact_text(fact)
    return '%s: %s %s (%s)%s%s' % (_info(fact)['label'], f['name'], f['id'], '문턱' if f.get('type') == 'building' else '발밑/인접',
                                   (' — ' + tail) if tail else '', sfx)


def fact_line(f):
    """조합형 '## 대상의 현재 사실' 한 줄 — '- f6 벤치: 앉으면 HP +1 (상처가 있을 때)'. 몸에 남는 효과가 있는 kind 만(장비 줄과 같은 자리 —
    수치가 있는 사실). 읽기·구경·몸 풀기·뒤지기는 대상 태그(readable·wares·practice·container)가 이미 말한다 → None.
    다 쓴 것은 kind 와 무관하게 '- f6 통: 이미 비어 있다' 한 줄(대상 태그는 그대로라 이 줄이 지금의 사실을 말한다)."""
    txt = fact_text(f.get('use'))
    return ('- %s %s: %s' % (f.get('id', '?'), f.get('name', '?'), txt)) if txt else None


def _spent(d):
    st = getattr(d, 'use_spent', None)          # from_ascii(__new__)·옛 피클 스냅샷엔 없는 속성 — 처음 쓸 때 만든다
    if st is None:
        st = d.use_spent = {}
    return st


def _draw(d, f, loot):
    """뒤지기의 추첨 — 세계 시드·층·피처 번호·자리의 해시로 가중표에서 하나(결정론, 판정 rng 무접촉).
    누가 언제 뒤지든 그 통에서 나오는 것은 같다 = 세계가 지어질 때 정해진 사실."""
    key = '%s|%s|%s|%s|%s' % (getattr(d, 'master_seed', 0), getattr(d, 'depth', 0), f.id, f.x, f.y)
    n = int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest()[:8], 'big')
    total = sum(int(e.get('w', 1)) for e in loot)
    pick = n % total
    for e in loot:
        pick -= int(e.get('w', 1))
        if pick < 0:
            return e['item']
    return loot[-1]['item']


def _offer_stat(d, bot):
    """신이 고르는 한 칸 — 세계 시드·바치는 이의 이름·그 몸의 지금 수치(힘·민첩·최대 HP)의 해시. 판정 rng 무접촉이라
    같은 상태면 늘 같은 결과다(D95: "캐릭터를 관리하는건 신의 몫" — 바치는 이가 무엇을 올릴지 지정하지 않는다).
    바칠 때마다 한 칸이 오르므로 다음 번의 해시 재료도 저절로 달라진다(따로 세는 장부를 두지 않는 까닭)."""
    key = '%s|%s|%s' % (getattr(d, 'master_seed', 0), bot.get('char'),
                        '|'.join('%s=%d' % (s, int(bot.get(s) or 0)) for s in OFFER_STATS))
    n = int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest()[:8], 'big')
    return OFFER_STATS[n % len(OFFER_STATS)]


def handle(d, bot, f, bots=None, target_id=None):
    """곁의 피처 f 를 쓴다 → 결과 dict, 쓰임 부품이 없으면 None(호출측이 'nothing' 으로 떨어진다). 거리·숨김은 _interact 가 이미 봤다."""
    use = use_of(d, f) if (f is not None and not getattr(f, 'concealed', False)) else None   # 숨은 건 아직 '없는' 것
    if not use:
        return None
    kind = use['kind']
    fid = 'f%d' % f.id
    base = {'char': bot['char'], 'type': 'interact', 'target': target_id or fid, 'what': f.name, 'use_kind': kind}
    once = bool(use.get('once')) or kind == 'rummage'          # 뒤지기는 늘 한 번(검증기도 once:false 를 거절한다)
    spent = _spent(d)
    if once and f.id in spent:
        d._witness_use(bots, f.x, f.y, [bot], f.name, fid, _GOT_SEEN['nothing'] if kind == 'rummage' else None)
        return {**base, 'result': 'used_up'}
    out = None
    seen = _info(use)['seen']
    if kind == 'read':
        pages = list(use['texts']) if use.get('texts') else [use['text']]
        n = int((bot.get('use_pages') or {}).get(f.id, 0))     # 읽는 사람마다 제 쪽수(봇 dict 수명 = 층 재스폰이면 처음부터 — shop_served 리듬)
        bot.setdefault('use_pages', {})[f.id] = n + 1
        out = {**base, 'result': 'read', 'text': pages[n % len(pages)],
               **({'verb': use['verb']} if use.get('verb') else {}),   # D90 동사 변형(살펴보기) — 있을 때만(문장·꼬리표가 읽는다)
               **({'page': n % len(pages) + 1, 'pages': len(pages)} if len(pages) > 1 else {})}
    elif kind in _HEAL_KINDS:
        nr = NE.no_regen(bot)                                  # p0.5.16 굶주림 — 쉬어도 기운이 돌아오지 않는다(상태 문장이 약속하는 규칙)
        heal = 0 if nr else max(0, min(_heal_of(use), bot['maxhp'] - bot['hp']))
        bot['hp'] += heal
        out = {**base, 'result': _HEAL_KINDS[kind], 'heal': heal, 'hp': bot['hp'], **({'no_regen': nr} if nr else {})}
    elif kind == 'browse':
        out = {**base, 'result': 'browsed', 'wares': list(use['wares'])}
    elif kind == 'practice':
        out = {**base, 'result': 'practiced'}
    elif kind == 'rummage':
        got = _draw(d, f, use['loot'])
        out = {**base, 'result': 'rummaged', 'got': got}
        if got == 'potion':
            bot['potions'] = bot.get('potions', 0) + 1
            out['potions'] = bot['potions']
        elif got == 'treasure':
            bot['bag'] = bot.get('bag', 0) + 1
            out['bag'] = bot['bag']
            qv = d._quest_event('loot', object='treasure')     # D69: 보물은 어디서 나왔든 획득이다(상자 선례)
            if qv:
                out['quest'] = qv
        elif got == 'ration':                                  # p0.5.16 휴대식 — 소지 칸 i9 에 하나
            bot['rations'] = int(bot.get('rations') or 0) + 1
            out['rations'] = bot['rations']
        seen = _GOT_SEEN[got]
    elif kind == 'offer':                                      # D95(09-20) 공물 — 모은 보물을 내면 신이 몸의 한 칸을 올린다. 굴림 없음(결정론)
        bag = int(bot.get('bag') or 0)
        if bag < OFFER_COST:                                   # 모자라면 사실만 돌려준다 — 권유·조언 없음(무엇을 하라고 말하지 않는다)
            out, seen = {**base, 'result': 'offer_short', 'cost': OFFER_COST, 'bag': bag}, _OFFER_SEEN['offer_short']
        else:
            bot['bag'] = bag - OFFER_COST
            stat = _offer_stat(d, bot)
            bot[stat] = int(bot.get(stat) or 0) + 1
            if stat == 'maxhp':                                # 몸 자체가 커진다 — 없던 상처가 생기지 않게 지금 HP 도 같이 오른다
                bot['hp'] = int(bot.get('hp') or 0) + 1
            out = {**base, 'result': 'offered', 'cost': OFFER_COST, 'bag': bot['bag'],
                   'stat': stat, 'value': bot[stat], **({'hp': bot['hp']} if stat == 'maxhp' else {})}
            seen = _OFFER_SEEN['offered']
    elif kind == 'lodge':                                      # D34 '지우기는 휴식뿐' — 묵기는 휴식이다(휴식 완료와 같은 소거)
        price, gold = int(use.get('price') or 0), int(bot.get('gold') or 0)   # p0.5.13 묵는 값 — 모자라면 사실만(묵지 못했다), 몸·지갑 그대로
        if gold < price:
            out, seen = {**base, 'result': 'too_poor', 'price': price, 'gold': gold}, _TRADE_SEEN['lodge_short']
        else:
            nr = NE.no_regen(bot)                              # p0.5.16 굶주림 — 묵어도 HP 는 차지 않는다(몸 상태는 낫는다 — 휴식의 소거는 그대로)
            heal = 0 if nr else max(0, bot['maxhp'] - bot['hp'])
            bot['hp'] += heal
            cleared = sorted(bot.get('status') or {})
            if cleared:
                bot['status'], bot['bleed_steps'], bot['slow_beat'] = {}, 0, 0
            if price:
                bot['gold'] = gold - price
            out = {**base, 'result': 'lodged', 'heal': heal, 'hp': bot['hp'], 'cleared': cleared,
                   **({'paid': price, 'gold': bot['gold']} if price else {}),   # 값 없는 숙소는 옛 결과 그대로
                   **({'no_regen': nr} if nr else {})}
    elif kind == 'shop':                                       # p0.5.13 물건 없이 가게를 쓰면 = 진열과 값을 본다(사기는 상품 ID, 팔기는 item 칸 — buy·sell)
        out = {**base, 'result': 'browsed', 'wares': ['%s %d골드' % (g['name'], g['price']) for g in goods(d) if g['fid'] == f.id],
               'buys': ['%s %d골드' % (n, p) for n, p in buy_list(use)]}
    if out is None:
        return None
    if once:
        spent[f.id] = {'char': bot['char'], 'turn': getattr(d, 'turn', 0)}
    d._witness_use(bots, f.x, f.y, [bot], f.name, fid, seen)   # 목격 = 기존 ally_use{what,id,result} 그대로(동사는 '사용' 하나 — 파트너 확정)
    return out


# ── p0.5.13(경제 1a) 가게 — 상품 목록·값·사기·팔기. 굴림 없음(판정 rng 무접촉) · 값은 정의의 사실(흥정 없음) ──
def shops(d):
    """세계의 가게 [(피처, use)] — 피처 번호 순(결정론). 쓰임이 shop 인 피처(마을 생활 판의 건물 — use_of 가 판의 스위치를 따른다)."""
    out = []
    for fid in sorted(getattr(d, 'features', None) or {}):
        f = d.features[fid]
        use = use_of(d, f)
        if (use or {}).get('kind') == 'shop':
            out.append((f, use))
    return out


def goods(d):
    """상품 [{gid, fid, item, name, type, price}] — 가게(피처 번호 순) × sells 순서로 g1, g2 …. 마을이 지어지면 바뀌지 않는다(게시판 q<n> 과 같은 꼴).
    상태를 들지 않는다 — 부를 때마다 세계(피처·정의)에서 다시 센다(옛 피클·스냅샷 이관에 새 칸이 필요 없다)."""
    out = []
    for f, use in shops(d):
        for e in use.get('sells') or []:
            df = ENT.get(e['item'])
            out.append({'gid': 'g%d' % (len(out) + 1), 'fid': f.id, 'item': e['item'], 'name': df['name'],
                        'type': df['type'], 'price': int(e['price'])})
    return out


def good(d, gid):
    return next((g for g in goods(d) if g['gid'] == gid), None)


def count(raw):
    """행동의 amount → 정수 ≥1(빼면·못 읽으면 1). 조합형 입력은 parse 가 이미 꼴을 봤다 — 메뉴형·BYO 길에서 엉뚱한 값이 와도 죽지 않게."""
    try:
        return max(1, int(raw)) if raw not in (None, '', True, False) else 1
    except (TypeError, ValueError):
        return 1


def item_name(bot, slot):
    """소지 type → 그 물건의 이름(장비는 든 것의 이름 · 나머지는 아이템 정의의 이름 — 정의가 없으면 type)."""
    if slot in ('weapon', 'armor'):
        return (bot.get(slot) or {}).get('name')
    df = ENT.item_def(slot)
    return df['name'] if df else slot


def buy_price(use, ftype, name):
    """이 가게가 그 물건을 사들이는 값(골드) — buys 에 적힌 type 이면 그 값 · 이 가게가 파는 물건(type·이름이 같은 정의)이면 파는 값 // SHOP_RESALE.
    아니면 None(사들이지 않는다). 되사는 값이 0 이 되는 싼 물건도 사들이지 않는다."""
    buys = use.get('buys') or {}
    if ftype in buys:
        return int(buys[ftype])
    for e in use.get('sells') or []:
        df = ENT.get(e['item'])
        if df.get('type') == ftype and df.get('name') == name:
            return (int(e['price']) // ENT.SHOP_RESALE) or None
    return None


def buy_list(use):
    """사들이는 값 [(이름, 값)] — buys(정의 순서) 다음 파는 물건의 되사는 값(sells 순서). 0 은 뺀다."""
    out = []
    for t, p in (use.get('buys') or {}).items():
        df = ENT.item_def(t)
        out.append((df['name'] if df else t, int(p)))
    for e in use.get('sells') or []:
        p = int(e['price']) // ENT.SHOP_RESALE
        if p and ENT.get(e['item']).get('type') in ENT.SHOP_BUY_TYPES:   # p0.5.16 그 자리에서 먹는 음식(food)은 지닐 수 없어 되사는 값이 없다
            out.append((ENT.get(e['item'])['name'], p))
    return out


def notices(d, bot):
    """관측 notices 의 가게 항목 — 문턱 SHOP_RANGE 칸 안의 가게마다 {kind:'shop', id:'f…', name, goods:[{tid, name, type, price}], buys:[{name, price}]}.
    상품 줄이 곧 사기의 대상(g<n>)이고, 팔기 설명은 이 항목이 있을 때만 관측에 붙는다(런타임 주입 — 지침 파일은 그대로). 없으면 []."""
    out, gl, seen = [], None, None
    for f, use in shops(d):
        if getattr(f, 'concealed', False) or max(abs(bot['x'] - f.x), abs(bot['y'] - f.y)) > SHOP_RANGE:
            continue
        seen = d.visible_cells(bot['x'], bot['y']) if seen is None else seen   # p0513b(Codex 리뷰 P2): 가까워도 안 보이는 가게(벽 너머·다른 구역)의 상품은 없다
        if (f.x, f.y) not in seen:
            continue
        gl = goods(d) if gl is None else gl
        out.append({'kind': 'shop', 'id': 'f%d' % f.id, 'name': f.name,
                    'goods': [{'tid': g['gid'], 'name': g['name'], 'type': g['type'], 'price': g['price']} for g in gl if g['fid'] == f.id],
                    'buys': [{'name': n, 'price': p} for n, p in buy_list(use)]})
    return out


def shop_at(d, f):
    """피처가 지금 가게인가 → 그 use(아니면 None). 숨은 피처는 아직 없는 것."""
    if f is None or getattr(f, 'concealed', False):
        return None
    use = use_of(d, f)
    return use if (use or {}).get('kind') == 'shop' else None


def keeper_of(d, shop_id):
    """가게 피처('f<n>' 또는 번호) → 그 가게를 맡은 NPC 이름(정의 npc.shop = 그 건물 정의 id · 이 세계에 서 있는 사람만 — 이름 순 첫 사람) 또는 None.
    p0.5.27: 손님의 돈이 모자랄 때 그 사람의 정해진 말(러너 too_poor_says)을 찾는 데 쓴다."""
    try:
        bid = (getattr(d, 'building_defs', None) or {}).get(int(str(shop_id).lstrip('f')))
    except ValueError:
        return None
    here = {f.name for f in d.features.values() if f.type == 'npc'}
    return next((n for n, nd in sorted((getattr(d, 'npc_defs', None) or {}).items()) if bid and nd.get('shop') == bid and n in here), None)


def buy(d, bot, gid, bots=None):
    """상품 g<n> 을 산다(조합형 buy g<n> · 메뉴형 interact g<n>) — 그 가게 문턱 SHOP_RANGE 칸 안이어야 한다. 값이 지닌 골드보다 크면 too_poor(사실만 — 몸·지갑 그대로).
    물약은 소지 물약 +1, 무기·갑옷은 바로 든다 — 들던 것은 발밑에 놓인다(바꿔 들기와 같은 문법 · 발밑이 차 있으면 no_room). 원자적: 물건이 못 오면 골드도 안 나간다."""
    base = {'char': bot['char'], 'type': 'interact', 'target': gid, 'use_kind': 'shop'}
    g = good(d, gid)
    f = d.features.get(g['fid']) if g else None
    if not g or shop_at(d, f) is None or (f.x, f.y) not in d.visible_cells(bot['x'], bot['y']):   # p0513b(리뷰 P2): 안 보이는 가게의 상품은 없는 것
        return {**base, 'result': 'no_target'}
    if max(abs(bot['x'] - f.x), abs(bot['y'] - f.y)) > SHOP_RANGE:
        return {**base, 'result': 'too_far'}
    base.update(what=g['name'], shop=f.name, shop_id='f%d' % f.id)
    price, gold = g['price'], int(bot.get('gold') or 0)
    df = ENT.get(g['item'])
    if g['type'] == 'food' and NE.full_block(bot, df):      # p0.5.16 그 자리에서 먹는 음식 — 배가 불러 들어가지 않으면 사지 않는다(값을 보기 전에 몸이 거절한다 · 돈 그대로)
        d._witness_use(bots, f.x, f.y, [bot], f.name, 'f%d' % f.id, _TRADE_SEEN['full'])
        return {**base, **NE.eat(d, bot, df, getattr(d, 'turn', 0), via='buy'), 'price': price, 'gold': gold}
    if gold < price:
        d._witness_use(bots, f.x, f.y, [bot], f.name, 'f%d' % f.id, _TRADE_SEEN['buy_short'])
        return {**base, 'result': 'too_poor', 'price': price, 'gold': gold}
    extra = {}
    if g['type'] == 'food':                                    # p0.5.16 사는 순간 그 자리에서 먹는다(몸에 들지 않는다) — 결과는 need_fill(via buy)
        bot['gold'] = gold - price
        fill = NE.eat(d, bot, df, getattr(d, 'turn', 0), via='buy')
        d._witness_use(bots, f.x, f.y, [bot], f.name, 'f%d' % f.id, _TRADE_SEEN['ate'] % (g['name'] + _j(g['name'], '을', '를')))
        return {**base, **fill, 'price': price, 'gold': bot['gold']}
    if g['type'] in ('potion', 'ration'):                      # 몸의 정수로 세는 소지(물약 · p0.5.16 휴대식)
        key = COUNTED[g['type']]
        bot[key] = int(bot.get(key) or 0) + 1
        extra[key] = bot[key]
    else:                                                      # weapon · armor(ENT.SHOP_ITEM_TYPES — 검증기가 막는다)
        slot, old = g['type'], bot.get(g['type'])
        if old and d.feature_at(bot['x'], bot['y']) is not None:
            return {**base, 'result': 'no_room', 'slot': slot, 'price': price, 'gold': gold}
        bonus = int(((ENT.get(g['item']).get('comps') or {}).get('equipment') or {}).get('bonus') or 0)
        if old:
            did = d._put_gear(slot, old, bot['x'], bot['y'], bot['char'])   # D57: 같은 번호로 발밑에(바꿔 들기 문법)
            extra.update(dropped=old['name'], dropped_id='f%d' % did)
        bot[slot] = {'id': d._alloc_fid(), 'name': g['name'], 'bonus': bonus, 'worn': [bot['char']]}   # 손에서 태어난 장비(D57 — NPC 선물과 같은 꼴)
        extra.update(slot=slot, bonus=bonus)
    bot['gold'] = gold - price
    d._witness_use(bots, f.x, f.y, [bot], f.name, 'f%d' % f.id, _TRADE_SEEN['bought'] % (g['name'] + _j(g['name'], '을', '를')))
    return {**base, 'result': 'bought', 'price': price, 'gold': bot['gold'], **extra}


def sell(d, bot, f, slot, amount=None, bots=None, target_id=None, item_id=None):
    """가게 f 에 소지품(slot)을 판다(sell <가게> item=<소지 ID> [amount]) — 값은 이 가게가 정한다(buy_price). 개수는 보물만(amount, 빼면 1).
    사들이지 않는 물건이면 no_deal, 지닌 것보다 많이 팔려 하면 not_enough(둘 다 몸·지갑 그대로). 거리는 호출측(CA.execute 의 sell 거리 — 자동 접근)이 봤다."""
    use = shop_at(d, f)
    fid = 'f%d' % f.id
    name = item_name(bot, slot) or slot
    base = {'char': bot['char'], 'type': 'interact', 'target': target_id or fid, 'use_kind': 'shop',
            'what': name, 'shop': f.name, 'shop_id': fid, **({'item': item_id} if item_id else {})}
    price = buy_price(use, slot, name) if (use is not None and slot in ENT.SHOP_BUY_TYPES) else None
    if not price:
        return {**base, 'result': 'no_deal'}
    n = count(amount) if slot in AMOUNT_SLOTS else 1
    have = (1 if bot.get(slot) else 0) if slot in ('weapon', 'armor') else int(bot.get(COUNTED[slot]) or 0)   # p0.5.16 휴대식은 한 번에 하나(amount 없음 — 물약 문법)
    if have < n:
        return {**base, 'result': 'not_enough', 'have': have, 'amount': n}
    got, extra = price * n, {}
    if slot in ('weapon', 'armor'):
        bot[slot] = None
    else:
        bot[COUNTED[slot]] = have - n
        extra[COUNTED[slot]] = bot[COUNTED[slot]]
    bot['gold'] = int(bot.get('gold') or 0) + got
    d._witness_use(bots, f.x, f.y, [bot], f.name, fid, _TRADE_SEEN['sold'] % (name + _j(name, '을', '를')))
    return {**base, 'result': 'sold', 'n': n, 'price': price, 'got': got, 'gold': bot['gold'], **extra}


# ── 표현 — 결과 dict 하나를 세 군데(자기 문장·궤적 꼬리표·관전 요약)가 읽는다. 전부 사실만. ⚠️문구 임시 ──
def _hp_sfx(res):
    return ('(HP +%d)' % res['heal']) if res.get('heal') else (' — ' + NE.NO_REGEN_TAIL) if res.get('no_regen') else ''   # p0.5.16 굶주림 — 쉬었지만 HP 가 안 찼다


def _j(word, final, open_):
    """조사 고르기 — 이름의 끝 글자에 받침이 있으면 final('을'·'은'), 없으면 open_('를'·'는'). 한글이 아니면 '을(를)' 꼴(기존 문장 관례)."""
    ch = str(word)[-1:]
    if '가' <= ch <= '힣':
        return final if (ord(ch) - 0xAC00) % 28 else open_
    return '%s(%s)' % (final, open_)


def prose(last):
    """직전 결과의 1인칭 사실 문장(brains._last_prose 의 interact 분기가 부른다). 모르는 result 는 None."""
    r, what = last.get('result'), last.get('what') or '그것'
    if r == 'read' and last.get('verb') == 'look':   # D90 살펴보기 — 글이 아니라 눈에 보인 것(쪽수는 말하지 않는다: 볼 때마다 다른 것이 눈에 든다)
        return '%s%s 살펴보았다: %s' % (what, _j(what, '을', '를'), last.get('text', ''))
    if r == 'read':
        pg = (' (%d/%d)' % (last['page'], last['pages'])) if last.get('pages') else ''
        return '%s의 글을 읽었다%s: "%s"' % (what, pg, last.get('text', ''))
    if r == 'sat':
        return '%s에 앉아 숨을 돌렸다%s' % (what, _hp_sfx(last))
    if r == 'drank':
        return '%s의 물을 마셨다%s' % (what, _hp_sfx(last))
    if r == 'warmed':
        return '%s의 불을 쬐었다%s' % (what, _hp_sfx(last))
    if r == 'browsed':
        s = '%s에 진열된 것을 구경했다: %s' % (what, ', '.join(last.get('wares') or []))
        if last.get('buys') is not None:            # p0.5.13 가게 — 진열(파는 값) 다음 사들이는 값(가게만 실린다 — 구경 결과는 옛 문장 그대로)
            s += ' · 사들이는 것: %s' % (', '.join(last['buys']) or '없음')
        return s
    shop = last.get('shop') or '가게'                 # p0.5.13 가게 결과의 what = 사고판 물건 이름 · shop = 가게 이름
    if r == 'bought':
        tail = ((' · 소지 물약 %d병' % last['potions']) if 'potions' in last
                else (' · 소지 휴대식 %d개' % last['rations']) if 'rations' in last   # p0.5.16 ⚠️문구 임시
                else (' · 바로 %s%s' % ('손에 들었다' if last.get('slot') == 'weapon' else '걸쳤다',
                                     (' — 들던 %s%s 발밑에 놓였다' % (last['dropped'], _j(last['dropped'], '은', '는'))) if last.get('dropped') else '')))
        return '%s에서 %s%s 샀다 — %d골드를 냈다(남은 골드 %d)%s' % (shop, what, _j(what, '을', '를'), last.get('price', 0), last.get('gold', 0), tail)
    if r == 'sold':
        n = int(last.get('n') or 1)
        thing = ('%s %d개를' % (what, n)) if ('bag' in last or n > 1) else '%s%s' % (what, _j(what, '을', '를'))
        return '%s에 %s 팔았다 — %d골드를 받았다(지금 골드 %d)' % (shop, thing, last.get('got', 0), last.get('gold', 0))
    if r == 'too_poor':
        if last.get('use_kind') == 'lodge':
            return '%s에 묵으려 했다 — 값이 %d골드인데 지닌 골드가 %d다' % (what, last.get('price', 0), last.get('gold', 0))
        return '%s에서 %s%s 사려 했다 — 값이 %d골드인데 지닌 골드가 %d다' % (shop, what, _j(what, '을', '를'), last.get('price', 0), last.get('gold', 0))
    if r == 'no_deal':
        return '%s에 %s%s 팔려 했다 — 이 가게는 %s%s 사들이지 않는다' % (shop, what, _j(what, '을', '를'), what, _j(what, '을', '를'))
    if r == 'not_enough':
        return '%s에 %s %d개를 팔려 했다 — 지닌 것은 %d개다' % (shop, what, last.get('amount', 0), last.get('have', 0))
    if r == 'no_room':
        return '%s에서 %s%s 사려 했다 — 들던 것을 내려놓을 발밑 자리가 없다(사지 않았다)' % (shop, what, _j(what, '을', '를'))
    if r == 'practiced':
        return '%s%s 상대로 몸을 풀었다' % (what, _j(what, '을', '를'))
    if r == 'rummaged':
        got = last.get('got')
        if got == 'potion':
            return '%s%s 뒤졌다 — 물약 하나가 나왔다(소지 물약 %d병)' % (what, _j(what, '을', '를'), last.get('potions', 1))
        if got == 'treasure':
            return '%s%s 뒤졌다 — 보물 하나가 나왔다(모은 보물 %d개)' % (what, _j(what, '을', '를'), last.get('bag', 1))
        if got == 'ration':                         # p0.5.16 ⚠️문구 임시
            return '%s%s 뒤졌다 — 휴대식 하나가 나왔다(소지 휴대식 %d개)' % (what, _j(what, '을', '를'), last.get('rations', 1))
        return '%s%s 뒤졌다 — 비어 있다' % (what, _j(what, '을', '를'))
    if r == 'lodged':
        cl = last.get('cleared') or []
        paid = (' · %d골드를 냈다(남은 골드 %d)' % (last['paid'], last.get('gold', 0))) if last.get('paid') else ''   # p0.5.13 값 있는 숙소만
        if last.get('no_regen'):                    # p0.5.16 굶주림 — 묵었지만 HP 는 차지 않았다(몸 상태는 나았다)
            return '%s에 묵었다 — %s%s%s' % (what, NE.NO_REGEN_TAIL, (' · 나은 상태: ' + '·'.join(cl)) if cl else '', paid)
        if not last.get('heal') and not cl:
            return '%s에 묵었다 — 나을 상처가 없었다%s' % (what, paid)
        return '%s에 묵었다 — 몸이 다 나았다(HP +%d%s)%s' % (what, last.get('heal', 0), (', 나은 상태: ' + '·'.join(cl)) if cl else '', paid)
    if r == 'offered':                              # D95 — 무엇을 냈고 무엇이 올랐나(사실만). 고른 것은 신이다
        st = last.get('stat')
        return '%s에 보물 %d개를 바쳤다 — 신이 %s 1 올렸다(지금 %s %d · 모은 보물 %d개)' % (
            what, last.get('cost', OFFER_COST), _STAT_OBJ.get(st, '한 칸을'),
            _STAT_KR.get(st, '?'), last.get('value', 0), last.get('bag', 0))
    if r == 'offer_short':
        return '%s에 바치려 했다 — 모은 보물이 %d개다(한 번 바치는 데 보물 %d개가 든다)' % (
            what, last.get('bag', 0), last.get('cost', OFFER_COST))
    if r == 'used_up':
        if last.get('use_kind') == 'rummage':
            return '%s%s 이미 비어 있다' % (what, _j(what, '은', '는'))
        return '%s%s 이미 쓰였다 — 더 나오는 것이 없다' % (what, _j(what, '은', '는'))
    return None


def summary(res):
    """관전·로그용 한 줄(show_runner.act_summary 의 interact 분기가 부른다) — 주어가 없는 사실 문장이라 1인칭 문장과 같은 소스."""
    return prose(res)


def event_tags(rec):
    """궤적 꼬리표(D40 사건 사전) — [(키, 라벨, 짧은 사실)]. 새 키는 만들지 않는다(use·loot·misc 재사용 → EVENT_KINDS 무수정)."""
    r, what = rec.get('result'), rec.get('what') or '?'
    if r == 'read':
        return [('use', '살펴봄' if rec.get('verb') == 'look' else '읽음', '%s "%s"' % (what, str(rec.get('text') or '')[:30]))]
    if r in ('sat', 'drank', 'warmed'):
        return [('use', '사용', '%s +%d (HP %d)%s' % (what, rec.get('heal', 0), rec.get('hp', 0), ' · 기운 안 돎' if rec.get('no_regen') else ''))]   # p0.5.16 굶주림
    if r == 'browsed':
        return [('use', '구경', what)]
    if r == 'practiced':
        return [('use', '사용', '%s — 몸 풀기' % what)]
    if r == 'rummaged':
        got = rec.get('got')
        if got == 'potion':
            return [('loot', '획득', '%s → 물약 (소지 %d)' % (what, rec.get('potions', 0)))]
        if got == 'treasure':
            return [('loot', '획득', '%s → 보물' % what)]
        if got == 'ration':                          # p0.5.16
            return [('loot', '획득', '%s → 휴대식 (소지 %d)' % (what, rec.get('rations', 0)))]
        return [('use', '사용', '%s — 비어 있음' % what)]
    if r == 'lodged':
        return [('use', '사용', '%s — 묵음 +%d (HP %d)%s%s' % (what, rec.get('heal', 0), rec.get('hp', 0),
                                                         (' · %d골드' % rec['paid']) if rec.get('paid') else '',   # p0.5.13 값 있는 숙소만
                                                         ' · 기운 안 돎' if rec.get('no_regen') else ''))]          # p0.5.16 굶주림
    shop = rec.get('shop') or '가게'                 # p0.5.13 가게 — 새 키를 만들지 않는다(loot·use·misc 재사용, EVENT_KINDS 무수정)
    if r == 'bought':
        return [('loot', '구입', '%s ← %s %d골드 (남은 %d)' % (what, shop, rec.get('price', 0), rec.get('gold', 0)))]
    if r == 'sold':
        return [('use', '팔기', '%s %d → %s %d골드 (지금 %d)' % (what, int(rec.get('n') or 1), shop, rec.get('got', 0), rec.get('gold', 0)))]
    if r == 'too_poor':
        return [('misc', '헛손질', '%s — %d골드 · 지닌 %d' % (what, rec.get('price', 0), rec.get('gold', 0)))]
    if r in ('no_deal', 'not_enough', 'no_room'):
        return [('misc', '헛손질', '%s — %s' % (what, {'no_deal': '%s에서 안 삼' % shop, 'not_enough': '지닌 %d개' % rec.get('have', 0),
                                                       'no_room': '발밑 자리 없음'}[r]))]
    if r == 'offered':                    # D95 — 새 키를 만들지 않는다(use 재사용, EVENT_KINDS 무수정)
        return [('use', '바침', '%s — 보물 %d개 → %s +1 (지금 %d · 남은 보물 %d)'
                 % (what, rec.get('cost', OFFER_COST), _STAT_KR.get(rec.get('stat'), '?'),
                    rec.get('value', 0), rec.get('bag', 0)))]
    if r == 'offer_short':
        return [('misc', '헛손질', '%s — 모은 보물 %d개(바치는 데 %d개)' % (what, rec.get('bag', 0), rec.get('cost', OFFER_COST)))]
    if r == 'used_up':
        return [('misc', '헛손질', '%s — 이미 %s' % (what, '비어 있음' if rec.get('use_kind') == 'rummage' else '쓰였음'))]
    return [('misc', '기타', str(r))]


def tried(d, f):
    """D39 오브젝트 태그의 동사('읽어 봄' …) — 쓰임 부품이 있는 피처만(쓰고도 남는 오브젝트라 '×N' 이 뜻이 있다). 없으면 None."""
    use = use_of(d, f)
    return _info(use)['tried'] if use else None


def obj_note(res):
    """D39 오브젝트 태그의 마지막 사실 한 마디 — 뒤지기만(무엇이 나왔나·비었나). 나머지는 None(이전 note 유지)."""
    if res.get('result') == 'rummaged':
        return ('%s 나옴' % _GOT_KR[res['got']]) if res.get('got') in _GOT_KR else '비어 있음'
    if res.get('result') == 'used_up' and res.get('use_kind') == 'rummage':
        return '비어 있음'
    if res.get('result') == 'offered':      # D95 — 지난번에 신이 올려 준 칸(나↔그 신전 사이의 사실)
        return '%s +1' % _STAT_KR.get(res.get('stat'), '?')
    if res.get('result') == 'offer_short':
        return '보물 모자람'
    if res.get('result') == 'sold':          # p0.5.13 가게 — 지난번에 무엇을 팔았나(나↔그 가게 사이의 사실)
        return '%s %d개 팖' % (res.get('what', '?'), int(res.get('n') or 1))
    if res.get('result') in ('too_poor', 'no_deal'):
        return '골드 모자람' if res['result'] == 'too_poor' else '%s 안 삼' % res.get('what', '?')
    return None


def place(d, eid, x, y):
    """배치 도우미 — 오브젝트 정의 한 장(eid)을 (x,y) 바닥 칸에 피처로 놓는다 → 피처 번호. build_town·장면 저작이 부른다(층 생성은 바닥 검사 없이 place_def 직접).
    정의에 story 가 있으면 place_story 에 걸어(D75) 피처 줄 끝의 한 줄(about)·곁 2칸의 이야기가 된다. 바닥이 아니거나 이미 다른
    피처가 선 칸이면 시작 전에 죽는다(_interact 는 칸의 첫 피처를 집는다 — 한 칸에 하나). rng 를 쓰지 않는다."""
    df = ENT.get(eid)
    if df.get('kind') != 'object' or not df.get('type'):
        raise ValueError('%r 은(는) 오브젝트 정의가 아니다' % eid)
    if not (0 <= y < d.h and 0 <= x < d.w) or d.grid[y][x] != '.' or d.feature_at(x, y) is not None:
        raise ValueError('오브젝트 %r 자리 (%d,%d)가 빈 바닥이 아니다' % (eid, x, y))
    return d.place_def(eid, x, y)                  # p0.5.6: 정의 → 피처 + 이야기는 Dungeon.place_def 한 길(이 함수는 바닥 검사를 얹은 겉)
