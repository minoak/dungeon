# -*- coding: utf-8 -*-
"""욕구(need) 부품 — p0.5.16(경제 1b, .orch/drafts/economy_design.md §3 · DECISIONS 10-14·10-15).

고리(민옥 10-14): 배고프다 → 먹는다 → 기분이 좋다(기분 조각) · 배가 불러 더 못 먹는다(가득 참) → 시간이 지나 다시 배고프다.
이 고리 하나를 **데이터로** 정의한다(entities/need/<id>.json 의 comps.need + 말 파일 prompts/world/need/<id>.md). 배고픔이 첫 사례이고,
다음 욕구는 같은 틀에 정의 한 장을 더한다(코드 무수정 — verify_needs 가 시험용 정의 한 장으로 고리 전체를 돌려 본다).

  · 몸: bot['needs'] = {욕구: 충족도 0~100} · bot['moods'] = [{src, size, what?, until}](같은 욕구의 조각은 새것이 덮는다 — p0.5.18: 문장 대신 먹은 것 이름 ·
    값과 이유 낱말은 그릴 때 정의에서 읽는다) ·
    무게 bot['need_w'] = {욕구: 낮음|높음}(보통이 아닌 것만 — p0.5.22 부터 시트의 특성이 정한다: 특성 정의의 effects.need.<욕구>.level ·
    0.5.20~21 의 생성 호출·시트 needs 칸은 거뒀다) · 특성 배율 bot['trait_fx'] = {욕구: {fill?: %, mood?: {갈래: %}}}(있을 때만 — 대식가의
    채움·미식가·소박한의 기분 조각 크기) · 취향 bot['taste'] = {likes, dislikes}(시트 taste 칸 — 있을 때만).
    무게·배율·취향은 스폰이 시트에서 다시 읽는다(이월할 것이 없다). p0.5.23 특성의 기분 기본값(낙천적인·냉소적인)은 몸에 싣지 않고
    기분 합산이 몸의 특성 이름(bot['traits'])에서 읽는다(trait_mood).
  · 엔진 공용 지점 셋: 틱마다 줄이기(tick) · 채우기(eat — 먹을 것의 satisfies / on_result — 정의의 from_events) · 단계 판정(문장·효과·사건).
  · 숫자는 에이전트에게 보이지 않는다(§3.8.6) — p0.5.18(DECISIONS 10-16 '몸·기분 줄') 관측은 두 줄과 결과 사실 문장뿐:
      '몸:' = 보통이 아닌 단계의 몸 문장(가장 낮은 충족도부터, 한 번에 문장 LINE_CAP 개) ·
      '기분:' = 살아 있는 기분 조각(욕구 단계가 주는 것 + 먹은 뒤 조각)의 값을 엔진이 합해 좋다 / 좋지 않다 둘 중 하나와 이유(합에 가장 크게
      기여한 조각부터 WHY_CAP 개) — 합이 0 근처(|합| < MOOD_EDGE)면 줄이 없다(림월드 생각 → 기분 합산, 경제 설계 §1.4).
      p0.5.23 합에는 특성의 기분 기본값이 더해진다(이유로는 안 보임 · 조각이 하나도 없으면 줄이 없다).
    보통 단계·조각 없음이면 두 줄 다 없다. 낱말(좋다·좋지 않다·이유)은 prompts/world/mood.md, 몸 문장·이유 낱말은 욕구 말 파일. 충족도·단계 이름·무게·채운 양·
    기분 합은 결과 dict 에서도 공개 투영이 걷는다(info_guard.NEED_NUM_KEYS). 스트림(관전)은 원본을 싣는다 — tick.bots[].needs·moods·mood_now,
    사건 need_fill·need_none·need_stage·need_drain·need_mood.
  · 효과 어휘는 코드에 있는 둘뿐(entities.NEED_EFFECTS) — no_regen(쉬기·앉기·마시기·불 쬐기·묵기로 HP 가 차지 않음 — 물약·샘·스킬은 그대로) ·
    hp_drain{every, floor}(every 틱마다 HP −1, 최대 HP 의 floor% 에서 멈춘다 — 굶어 죽지 않는다).
  · 욕구 사건(type 'need' — 단계 변화·기운 빠짐·from_events 채움)은 행위가 아니라 몸의 변화라 `char` 대신 `bot`(그 몸의 번호)을 싣는다 —
    스트림 계약 '실행된 결정 = 그 char 의 이벤트 정확히 1개'(STREAM_FORMAT 파생 규칙)를 지킨다. 먹기(use i9 · 가게 사 먹기)는 행동이라 그 결과가 char 를 든다.
  · 판정 rng(d.rng·d20)를 건드리지 않는다 — 줄기·효과의 박자는 판의 틱 번호(turn % every)라 이어가기에도 같다.
  · 내성(tolerance)은 아직 없다(§10-23 — 호기심 단계부터). 결과의 tol 은 늘 100(그때의 배율 자리).
  · 문장은 사실만 — 엔진 문장(아래 ⚠️)·말 파일 문장 모두 지시·의무·권유 꼴로 끝내지 않는다(verify_needs 문장 게이트).
LLM 0콜.
"""
import re

import entities as ENT

LINE_CAP = 2                 # §10-20 '몸:' 줄 상한 — 한 번에 문장 2개(문장 묶음 수가 아니라 문장 수), 가장 낮은 충족도의 몸 문장부터
MOOD_EDGE = 3                # p0.5.18 기분 합의 절댓값이 이것보다 작으면(0 근처) '기분:' 줄이 없다 — 문턱은 여기 한 곳 ⚠️임시(값은 정의의 mood 칸들과 함께 교정)
WHY_CAP = 2                  # p0.5.18 '기분:' 줄의 이유 — 합에 가장 크게 기여한 조각부터 최대 2개(DECISIONS 10-16)
DEFAULT_LEVEL = '보통'       # 무게를 정하는 특성이 없으면 보통 = 정의의 decay · 채움 100% · 기분 시간 100%
TOL_FULL = 100               # 내성 배율 자리(%) — 내성이 없는 동안 늘 100
LIKES_MAX, DISLIKES_MAX = 2, 1   # §3.6 취향 — 좋아함 0~2 · 싫어함 0~1
NEED_RESULTS = ('need_fill', 'need_none', 'need_stage', 'need_drain',   # 이 모듈이 내는 결과·사건 이름(§10-19 — ate·full 이름은 쓰지 않는다)
                'need_mood')     # p0.5.18 기분 합산의 결과(좋다·좋지 않다·없음과 이유)가 바뀐 사건(관전·측정용)
MOOD_SIZE = {'like': '아주 좋음', 'plain': '좋음', 'dislike': '별로'}   # 관전·측정용 말(관측엔 안 나간다 — 기분은 문장으로만)

# ⚠️ 엔진 문장(임시 — 민옥 교정 대기). 결과 사실만: 무엇을 먹었고 몸이 어떻게 받았나. 숫자(충족도)는 없다.
NO_REGEN_TAIL = '기운이 돌아오지 않았다'            # no_regen 단계에서 쉬기·앉기·마시기·불 쬐기·묵기를 한 결과의 꼬리
FULL_FALLBACK = '더는 들어가지 않는다'              # 가득 참 단계에 상태 문장이 없는 욕구의 거절 꼬리
DRAIN_LINE = '기운이 빠졌다'                        # hp_drain 이 HP 를 1 깎은 틱의 궤적 꼬리표 사실

_IDX = {'src': None, 'n': -1, 'all': [], 'live': []}
_SENT_RE = re.compile(r'(?<=[.!?…])\s+')            # 문장 자르기 — 줄 상한(lines)·문장 게이트(order_problems) 공용
_JOSA = {'을': ('을', '를'), '은': ('은', '는'), '이': ('이', '가'), '과': ('과', '와')}


def _index():
    defs = ENT.load()
    if _IDX['src'] is not defs or _IDX['n'] != len(defs):   # 정의 사전이 바뀌면(재로드·게이트의 주입) 다시 짓는다(interactables._by_type 과 같은 꼴)
        alls = sorted((d for d in defs.values() if d.get('kind') == 'need'), key=lambda d: d['id'])
        _IDX.update(src=defs, n=len(defs), all=alls, live=[d for d in alls if (d['comps']['need'] or {}).get('stages')])
    return _IDX


def all_defs():
    """욕구 정의 전부(단계 없는 것 포함 — 준비 중 욕구도 든다)."""
    return list(_index()['all'])


def live():
    """엔진이 쓰는 욕구 [(id, spec)] — 단계가 있는 정의만, id 순(결정론). spec = comps.need."""
    return [(d['id'], d['comps']['need']) for d in _index()['live']]


def spec(nid):
    return next((s for i, s in live() if i == nid), None)


def name_of(nid):
    return next((d['name'] for d in _index()['all'] if d['id'] == nid), nid)


def stage_key(sp, v):
    """충족도 v 가 드는 단계 id — min 이 v 이하인 단계 중 가장 높은 것(검증기가 min 0 을 보장한다)."""
    rows = sorted(sp['stages'].items(), key=lambda kv: -kv[1]['min'])
    return next((k for k, st in rows if v >= st['min']), rows[-1][0])


def stage(sp, v):
    return sp['stages'][stage_key(sp, v)]


def is_full(sp, v):
    return v >= int(sp['full_at'])


def weight(sp, lvl):
    """등급 하나 → {every, fill, mood_time}(§10-13 — 셋을 함께 바꾼다). 보통 = 정의의 decay · 100 · 100."""
    w = (sp.get('weights') or {}).get(lvl)
    return dict(w) if w else {'every': int(sp['decay']), 'fill': 100, 'mood_time': 100}


def level(bot, nid):
    return (bot.get('need_w') or {}).get(nid, DEFAULT_LEVEL)


def weight_of(bot, nid, sp):
    """p0.5.22 몸 하나의 무게 — 등급(need_w)의 {every, fill, mood_time} 에 특성 배율(trait_fx 의 fill %)을 곱한 것.
    채우는 양은 이 fill 하나로 계산된다(_fill) — 대식가 70% × 등급 높음 70% = 49%. 줄어드는 빠르기·기분 시간은 등급 그대로."""
    w = weight(sp, level(bot, nid))
    f = ((bot.get('trait_fx') or {}).get(nid) or {}).get('fill')
    if f is not None:
        w['fill'] = w['fill'] * int(f) / 100.0
    return w


def _scaled(v, pct):
    """기분 값 v 에 특성 배율 pct(%)를 곱한다 — 0 에서 먼 쪽으로 반올림(+7.5 → +8 · −7.5 → −8). 배율이 없으면 v."""
    if pct is None:
        return v
    m = int(abs(v) * int(pct) / 100.0 + 0.5)
    return m if v > 0 else -m


def trait_effects(names):
    """p0.5.22 특성 이름들(시트 traits — 성격 줄에 든 글자 그대로) → (등급 {욕구: 낮음|높음}, 배율 {욕구: {fill?: %, mood?: {갈래: %}}}).
    특성 정의(entities/trait)의 effects.need 를 읽는다 — 모르는 이름은 건너뛴다(손 시트·지운 특성 — 판을 막지 않는다), 같은 이름은 한 번.
    겹침(여러 특성이 같은 칸을 바꾸면): 배율은 곱한다(정수 %로 반올림 — 70 × 70 = 49 · 미식가 150 × 소박한 50 = 75 — p0.5.24 부터 둘은 반대 짝이라 옛 시트에서만) ·
    등급은 모두 같으면 그 등급, 하나라도 다르면 보통(서로 지운다 — 보통은 칸을 두지 않는다).
    단계가 없는 욕구(준비 중)의 등급도 돌려준다 — 몸에 거는 것만 고르는 건 fields(엔진은 단계가 있는 욕구만 쓴다)."""
    by = ENT.trait_by_name()
    lv, pct = {}, {}
    for nm in dict.fromkeys(n for n in (names or ()) if isinstance(n, str)):
        d = by.get(nm)
        for nid, e in sorted((((((d or {}).get('comps') or {}).get('trait') or {}).get('effects') or {}).get('need') or {}).items()):
            if e.get('level'):
                lv.setdefault(nid, set()).add(e['level'])
            if e.get('fill') is not None:
                pct[(nid, 'fill', None)] = pct.get((nid, 'fill', None), 100.0) * e['fill'] / 100.0
            for mk, p in sorted((e.get('mood') or {}).items()):
                pct[(nid, 'mood', mk)] = pct.get((nid, 'mood', mk), 100.0) * p / 100.0
    levels = {nid: next(iter(s)) for nid, s in sorted(lv.items()) if len(s) == 1}
    fx = {}
    for (nid, k, mk), p in sorted(pct.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or '')):
        v = int(p + 0.5)
        if k == 'fill':
            fx.setdefault(nid, {})['fill'] = v
        else:
            fx.setdefault(nid, {}).setdefault('mood', {})[mk] = v
    return levels, fx


def trait_mood(names):
    """p0.5.23(DECISIONS 10-17 '낙천↔냉소 = 림월드식 B') 특성 이름들 → 기분 기본값의 합(특성 정의의 effects.mood — 낙천적인 +5 · 냉소적인 −5).
    trait_effects 와 같은 겹침 자리: 모르는 이름은 건너뛰고 같은 이름은 한 번, 여러 특성이면 더한다(반대 짝은 같이 고를 수 없다). 없으면 0.
    몸에 따로 싣지 않는다 — mood_of 가 몸의 특성 이름(traits — 스폰이 시트에서 옮긴 것)으로 그릴 때 읽는다(이어간 옛 판도 이관 없이 같다)."""
    by = ENT.trait_by_name()
    return sum(int((((((by.get(nm) or {}).get('comps') or {}).get('trait') or {}).get('effects') or {}).get('mood')) or 0)
               for nm in dict.fromkeys(n for n in (names or ()) if isinstance(n, str)))


def josa(word, mark):
    """조사 고르기 — 끝 글자 받침 유무로(한글이 아니면 '을(를)' 꼴 — 기존 문장 관례)."""
    a, b = _JOSA[mark]
    ch = str(word)[-1:]
    if '가' <= ch <= '힣':
        return a if (ord(ch) - 0xAC00) % 28 else b
    return '%s(%s)' % (a, b)


def fill_line(line, what):
    """기분 문장의 자리 — {what} = 먹은 것 이름, {what:을} = 이름 + 조사(entities._NEED_FILL_RE 와 같은 문법)."""
    what = what or '그것'
    return ENT._NEED_FILL_RE.sub(lambda m: what + (josa(what, m.group(1)) if m.group(1) else ''), line)


# ── 몸 ──────────────────────────────────────────────────────────────

def sheet_fields(s, vocab=None):
    """시트(파티 파일의 한 칸 · 저장 캐릭터 슬롯) → 거른 {taste?} — load_party·sheetkit.build_sheet 가 부른다. **판을 막지 않는다**:
    취향은 어휘 안의 꼬리표만 · 좋아함 2·싫어함 1까지 · 겹치면 싫어함에서 뺀다. 칸이 없거나 남는 것이 없으면 그 칸을 만들지 않는다.
    vocab(입맛 어휘)을 주면 정의를 읽지 않는다 — 정의를 읽는 도중의 검증기(entities 의 동료 시트)가 쓴다(다시 읽기 재귀를 막는다).
    p0.5.22: 욕구 무게(0.5.20~21 의 needs·needs_meta 칸)는 시트에서 읽지 않는다 — 특성이 정한다(trait_effects). 옛 칸은 저장 이관이 버린다(savedata)."""
    out = {}
    tt = s.get('taste')
    if isinstance(tt, dict):
        vocab = tastes() if vocab is None else vocab
        likes = [t for t in (tt.get('likes') or []) if isinstance(t, str) and t in vocab][:LIKES_MAX] if isinstance(tt.get('likes'), list) else []
        dis = [t for t in (tt.get('dislikes') or []) if isinstance(t, str) and t in vocab and t not in likes][:DISLIKES_MAX] if isinstance(tt.get('dislikes'), list) else []
        if likes or dis:
            out['taste'] = {'likes': likes, 'dislikes': dis}
    return out


def tastes():
    """취향 어휘 — 욕구 정의들의 tastes 합(정의 순서, 중복 없이)."""
    out = []
    for d in all_defs():
        for t in (d['comps']['need'] or {}).get('tastes') or []:
            if t not in out:
                out.append(t)
    return out


def fields(sheet=None):
    """스폰 몸의 칸 — 시작 충족도(정의의 start) · 빈 기분 조각 · 특성이 정한 무게(need_w — 보통이 아닌 것만)·배율(trait_fx — 있을 때만) ·
    시트의 취향(있을 때만). 무게·배율은 단계가 있는 욕구만 몸에 건다(준비 중 욕구의 등급은 엔진이 건너뛴다).
    판 안의 층 전이는 러너가 충족도·기분을 옮기고(carry), 부활은 되돌린다(reset)."""
    sheet = sheet or {}
    out = {'needs': {nid: int(sp['start']) for nid, sp in live()}, 'moods': []}
    lv, fx = trait_effects(sheet.get('traits'))
    w = {nid: v for nid, v in lv.items() if spec(nid)}
    if w:
        out['need_w'] = w
    fx = {nid: v for nid, v in fx.items() if spec(nid)}
    if fx:
        out['trait_fx'] = fx
    sf = sheet_fields(sheet)
    if sf.get('taste'):
        out['taste'] = sf['taste']
    return out


def carry(old, new):
    """층 전이·원정 — 충족도와 살아 있는 기분 조각은 그 몸을 따라간다(무게·취향은 스폰이 시트에서 다시 읽었다)."""
    if old.get('needs') is not None:
        new['needs'] = dict(old['needs'])
    new['moods'] = [dict(m) for m in (old.get('moods') or [])]


def reset(bot):
    """부활(신전에서 깨어남) — 새 판과 같은 시작 충족도, 기분 조각은 걷힌다(§6.3 '부활하면 시작값')."""
    bot['needs'] = {nid: int(sp['start']) for nid, sp in live()}
    bot['moods'] = []


def _log(d):
    lg = getattr(d, 'need_log', None)
    if lg is None:                                 # 옛 피클·from_ascii(__new__)엔 없는 속성 — 처음 쓸 때 만든다
        lg = d.need_log = []
    return lg


def drain(d):
    """이 세계에 쌓인 욕구 사건(이 틱) — 러너가 tick.events 에 붓는다. 비운다."""
    lg = getattr(d, 'need_log', None) or []
    out = list(lg)
    if lg:
        del lg[:]
    return out


def _set(d, bot, nid, v):
    """충족도를 바꾼다(0~100) — 단계가 바뀌면 need_stage 사건 한 줄."""
    sp = spec(nid)
    needs = bot.setdefault('needs', {})
    old = needs.get(nid, int(sp['start']))
    v = max(0, min(100, int(v)))
    needs[nid] = v
    a, b = stage_key(sp, old), stage_key(sp, v)
    if a != b:
        _log(d).append({'type': 'need', 'bot': bot['char'], 'result': 'need_stage', 'need': nid, 'from': a, 'to': b})
    return old, v


def effects(bot):
    """지금 몸에 걸린 효과 {효과 이름: (욕구 id, 값)} — 단계가 있는 욕구 순(앞의 것이 이긴다)."""
    out = {}
    for nid, sp in live():
        v = (bot.get('needs') or {}).get(nid)
        if v is None:
            continue
        for k, val in (stage(sp, v).get('effects') or {}).items():
            out.setdefault(k, (nid, val))
    return out


def no_regen(bot):
    """쉬기·앉기·마시기·불 쬐기·묵기로 HP 가 차지 않는 몸인가(효과 no_regen) → 그 욕구 id 또는 None."""
    e = effects(bot).get('no_regen')
    return e[0] if e else None


def tick(d, bots, turn):
    """한 세계의 한 틱 — 산 몸마다 줄기(every 틱마다 1) · hp_drain(every 틱마다 HP −1, 최대 HP 의 floor% 에서 멈춤) · 끝난 기분 조각 걷기.
    단계가 바뀌면 need_stage, HP 를 깎으면 need_drain(사건) + 그 몸의 궤적 한 칸(엔진 사실 — 관측의 HP 가 왜 줄었나).
    p0.5.18: 줄기·조각 끝남으로 기분 합산의 결과가 바뀌면 need_mood(전 = 지난 틱 끝의 몸). 판정 rng 무접촉."""
    specs = live()
    for b in bots:
        if not b.get('alive', True) or b.get('won'):
            continue
        m0 = _mood_key(b, int(turn) - 1)
        needs = b.setdefault('needs', {})
        for nid, sp in specs:
            if nid not in needs:                   # 판 중에 정의가 더해졌다(새 욕구 = 데이터 한 장) — 시작값부터
                needs[nid] = int(sp['start'])
            w = weight(sp, level(b, nid))
            if turn % max(1, int(w['every'])) == 0 and needs[nid] > 0:
                _set(d, b, nid, needs[nid] - 1)
            hd = (stage(sp, needs[nid]).get('effects') or {}).get('hp_drain')
            if hd and turn % max(1, int(hd['every'])) == 0:
                floor = -(-int(b['maxhp']) * int(hd['floor']) // 100)   # 최대 HP 의 floor%(올림) — 그 아래로는 깎지 않는다
                if b['hp'] > floor:
                    b['hp'] -= 1
                    rec = {'type': 'need', 'bot': b['char'], 'result': 'need_drain', 'need': nid, 'hp': b['hp'], 'maxhp': b['maxhp']}
                    _log(d).append(rec)
                    if hasattr(d, '_trail_add'):
                        d._trail_add(b, rec)
        if b.get('moods'):
            b['moods'] = [m for m in b['moods'] if int(m.get('until', 0)) > turn]
        _mood_event(d, b, m0, turn)


def _mood(sp, bot, tags):
    """먹은 것의 꼬리표 × 몸의 취향 → 기분 갈래(싫어함을 좋아함보다 먼저 본다 — §3.6). 정의에 그 갈래가 없으면 plain."""
    taste = bot.get('taste') or {}
    tags = set(tags or ())
    mk = 'dislike' if tags & set(taste.get('dislikes') or ()) else 'like' if tags & set(taste.get('likes') or ()) else 'plain'
    md = sp.get('mood') or {}
    return mk if mk in md else ('plain' if 'plain' in md else None)


def _fill(d, bot, nid, amount, turn, what=None, tags=(), via='eat', src_key=None):
    """한 욕구를 채운다 → need_fill 칸(dict). 무게의 fill% 를 곱하고(올림 없이 반올림) 100 에서 자른다 · 기분 조각을 붙인다(같은 욕구의 조각은 덮는다 —
    p0.5.18: 조각엔 갈래·먹은 것 이름·끝나는 틱만, 값과 이유 낱말은 그릴 때 정의에서 · p0.5.22 fill% 엔 특성 배율이 곱해져 있다(weight_of))."""
    sp = spec(nid)
    w = weight_of(bot, nid, sp)
    gain = max(1, int(round(int(amount) * w['fill'] / 100.0)))
    before, after = _set(d, bot, nid, (bot.get('needs') or {}).get(nid, int(sp['start'])) + gain)
    rec = {'result': 'need_fill', 'need': nid, 'via': via, **({'what': what} if what else {}),
           **({'src_key': src_key} if src_key else {}), 'tol': TOL_FULL, 'before': before, 'after': after}
    mk = _mood(sp, bot, tags)
    if mk:
        m = sp['mood'][mk]
        until = int(turn) + max(1, int(round(int(m['time']) * int(w['mood_time']) / 100.0)))
        moods = [x for x in (bot.get('moods') or []) if x.get('src') != nid]
        moods.append({'src': nid, 'size': mk, **({'what': what} if what else {}), 'until': until})
        bot['moods'] = moods
        rec['mood'] = mk
    return rec


def food_of(df):
    """먹을 것의 {욕구: 양} — 단계가 있는 욕구만(검증기가 이미 본다), id 순."""
    sat = ((df or {}).get('comps') or {}).get('satisfies') or {}
    return [(nid, int(sat[nid])) for nid in sorted(sat) if spec(nid)]


def full_block(bot, df):
    """이 먹을 것이 몸에 들어가지 않는가 → 가득 찬 욕구 id(가득 차면 거절하는 욕구만 — full_blocks) 또는 None."""
    for nid, _amt in food_of(df):
        sp = spec(nid)
        if sp.get('full_blocks') and is_full(sp, (bot.get('needs') or {}).get(nid, int(sp['start']))):
            return nid
    return None


def eat(d, bot, df, turn, via='eat'):
    """먹을 것 정의 df 하나를 먹는다 → 결과 칸 dict(need_fill 또는 need_none{why:'full'}). 가득 참이면 아무것도 바뀌지 않는다(물건·돈은 호출측이 그대로 둔다).
    여러 욕구를 채우는 것이면 첫 욕구(id 순)가 결과이고 나머지는 사건(need_fill)으로 쌓인다."""
    what = df.get('name')
    blk = full_block(bot, df)
    if blk:
        return {'result': 'need_none', 'need': blk, 'why': 'full', 'via': via, 'what': what, 'src_key': df['id']}
    tags = ((df.get('comps') or {}).get('taste')) or []
    m0 = _mood_key(bot, turn)
    rows = [_fill(d, bot, nid, amt, turn, what=what, tags=tags, via=via, src_key=df['id']) for nid, amt in food_of(df)]
    for extra in rows[1:]:
        _log(d).append({'type': 'need', 'bot': bot['char'], **extra})
    _mood_event(d, bot, m0, turn)                  # p0.5.18 먹어서 바뀐 기분(단계·새 조각) — 행동이 낳은 사건
    return rows[0]


def on_result(d, bot, res, turn):
    """정의의 from_events — 행동 결과(result 이름)가 그 욕구를 채운다(엔진이 결과를 판정한 뒤 · 그 몸의 행동·자동 보행 결과: Dungeon._note_last 가 부른다 —
    남이 내게 한 일(맞음·받음)은 _note_last 를 지나지 않아 세지 않는다).
    가득 찬 욕구는 더 채우지 않는다 — 행동은 이미 일어났으니 막지 않고 need_none{why:'full'} 사건만(§3.7 몸에 들어가지 않는 욕구의 가득 참)."""
    r = (res or {}).get('result')
    if not r or r in NEED_RESULTS:
        return
    m0 = _mood_key(bot, turn)
    for nid, sp in live():
        for e in sp.get('from_events') or ():
            if e.get('event') != r:
                continue
            v = (bot.get('needs') or {}).get(nid, int(sp['start']))
            what = res.get('what')
            if is_full(sp, v):
                _log(d).append({'type': 'need', 'bot': bot['char'], 'result': 'need_none', 'need': nid, 'why': 'full', 'via': 'event', 'src_key': r,
                                **({'what': what} if what else {})})
            else:
                _log(d).append({'type': 'need', 'bot': bot['char'], **_fill(d, bot, nid, e['amount'], turn, what=what, via='event', src_key=r)})
    _mood_event(d, bot, m0, turn)


# ── 관측 · 스트림 ───────────────────────────────────────────────────

def sentences(text):
    """글 → 문장들(마침표·느낌표·물음표·말줄임 뒤 공백에서 나눈다 — 문장 게이트 order_problems 와 같은 자르기)."""
    return [s for s in _SENT_RE.split(str(text or '').strip()) if s]


def lines(bot):
    """'몸:' 줄의 문장들 — 보통이 아닌 단계의 몸 문장(가장 낮은 충족도부터 · 같으면 욕구 id 순). 없으면 [](보통이면 줄이 없다).
    상한은 **문장 수**(LINE_CAP) — 문장이 둘인 단계(굶주림)는 그것만으로 찬다. 남은 자리보다 긴 묶음은 앞 문장만 남긴다(뒤의 것은 밀린다).
    p0.5.18: 기분 조각은 여기 없다 — '기분:' 줄(mood_line)이 합산해 말한다."""
    rows = []
    for nid, sp in live():
        v = (bot.get('needs') or {}).get(nid)
        if v is None:
            continue
        ln = stage(sp, v).get('line')
        if ln:
            rows.append((v, nid, ln))
    out, left = [], LINE_CAP
    for _v, _n, ln in sorted(rows):
        ss = sentences(ln)
        if left <= 0:
            break
        if ss:
            out.append(ln if len(ss) <= left else ' '.join(ss[:left]))
            left -= min(len(ss), left)
    return out


def _parts(bot, turn=None):
    """p0.5.18 살아 있는 기분 조각 [(값, 이유 낱말)] — 욕구 단계가 주는 것(그 단계의 mood·why — 가장 낮은 충족도부터, 같으면 욕구 id 순) 다음
    먹은 뒤 조각(정의의 mood.<갈래>.mood·why — 새것부터). 이 순서가 이유 정렬의 동점 순서다. turn 이 있으면 그 틱에 끝난 조각(until ≤ turn)은 뺀다
    (관측과 같은 자르기 — 없으면 몸의 목록 그대로: 틱 머리가 이미 걷었다). 정의에 값이 없는 조각(지운 욕구·지운 갈래)은 세지 않는다.
    p0.5.22 먹은 뒤 조각의 값엔 몸의 특성 배율(trait_fx 의 mood{갈래: %} — 미식가·소박한)을 곱한다 — 곱해서 0 이 된 조각은 세지 않는다. 단계가 주는 값은 그대로."""
    rows = []
    for nid, sp in live():
        v = (bot.get('needs') or {}).get(nid)
        if v is None:
            continue
        st = stage(sp, v)
        if st.get('mood'):
            rows.append((v, nid, int(st['mood']), st['why']))
    out = [(m, w) for _v, _n, m, w in sorted(rows, key=lambda r: (r[0], r[1]))]
    fx = bot.get('trait_fx') or {}
    for p in reversed(bot.get('moods') or []):
        if turn is not None and int(p.get('until', 0)) <= int(turn):
            continue
        mv = (((spec(p.get('src')) or {}).get('mood') or {}).get(p.get('size'))) or {}
        if mv.get('mood'):
            m = _scaled(int(mv['mood']), ((fx.get(p.get('src')) or {}).get('mood') or {}).get(p.get('size')))
            if m:
                out.append((m, fill_line(mv['why'], p.get('what'))))
    return out


def mood_of(bot, turn=None):
    """p0.5.18 기분 합산(림월드 생각 → 기분) — 조각 값의 합이 0 근처(|합| < MOOD_EDGE)면 None, 아니면 {key: good|bad, sum, why[이유 ≤ WHY_CAP]}.
    이유 = 합과 같은 쪽 조각만(반대쪽은 합에 기여하지 않았다), 값의 크기가 큰 것부터 · 같으면 _parts 순서(단계 먼저 · 낮은 충족도 먼저 · 조각은 새것 먼저) ·
    같은 낱말은 한 번. 숫자(sum)는 관전·측정용 — 관측엔 mood_line 의 낱말만 간다.
    p0.5.23 특성의 기분 기본값(trait_mood — 낙천적인·냉소적인)을 합에 더한다. 이유 낱말로는 보이지 않고(이유는 조각에서만 고른다),
    다른 이유(조각)가 하나도 없으면 줄이 없다 — 기본값만으로는 뜨지 않는다. 합이 기본값 때문에 조각과 반대쪽이 되면 이유 없이 낱말만 남는다."""
    parts = _parts(bot, turn)
    if not parts:
        return None
    s = sum(m for m, _w in parts) + trait_mood(bot.get('traits'))
    if abs(s) < MOOD_EDGE:
        return None
    why = []
    for _m, w in sorted((p for p in parts if (p[0] > 0) == (s > 0)), key=lambda p: -abs(p[0])):
        if w not in why:
            why.append(w)
    return {'key': 'good' if s > 0 else 'bad', 'sum': s, 'why': why[:WHY_CAP]}


def mood_line(bot, turn=None):
    """p0.5.18 관측의 '기분:' 줄 글 — '좋지 않다 (이유: 배고픔)'(낱말은 prompts/world/mood.md — ENT.mood_words · 숫자 없음). 0 근처면 None."""
    m = mood_of(bot, turn)
    if not m:
        return None
    w = ENT.mood_words()
    return '%s (%s: %s)' % (w[m['key']], w['why'], ', '.join(m['why'])) if m['why'] else w[m['key']]


def _mood_key(bot, turn):
    m = mood_of(bot, turn)
    return (m['key'], tuple(m['why'])) if m else None


def _mood_event(d, bot, before, turn):
    """p0.5.18 기분 합산의 결과(좋다·좋지 않다·없음과 이유)가 before 와 다르면 need_mood 사건 한 줄 — {from, to}(good|bad|None) + 새 결과의 sum·why.
    값만 바뀌고 낱말·이유가 그대로면 사건이 없다(관측의 '기분:' 줄이 그대로다)."""
    m = mood_of(bot, turn)
    if ((m['key'], tuple(m['why'])) if m else None) != before:
        _log(d).append({'type': 'need', 'bot': bot['char'], 'result': 'need_mood', 'from': before[0] if before else None,
                        'to': m['key'] if m else None, **({'sum': m['sum'], 'why': list(m['why'])} if m else {})})


def snap(bot):
    """봇 스냅샷(스트림 tick.bots[]·level.party[])에 얹을 칸 — 충족도 · 살아 있는 기분 조각(있을 때만) · 기분 합산 mood_now{key, sum, why}(0 근처가 아닐 때만).
    관전용(관측엔 안 나간다)."""
    if bot.get('needs') is None:
        return {}
    out = {'needs': dict(bot['needs'])}
    if bot.get('moods'):
        out['moods'] = [dict(m) for m in bot['moods']]
    m = mood_of(bot)
    if m:
        out['mood_now'] = m
    return out


def defs_meta():
    """run_meta.need_defs — 단계가 있는 욕구 정의(단계·효과·무게 숫자·기분 값·기분 시간·취향 어휘). 측정 도구가 스트림만으로 단계·기분 합을 다시 셀 수 있게(bestiary_defs 와 같은 꼴)."""
    out = {}
    for nid, sp in live():
        out[nid] = {'name': name_of(nid), 'start': sp['start'], 'decay': sp['decay'], 'full_at': sp['full_at'], 'full_blocks': sp['full_blocks'],
                    'stages': {k: {kk: v[kk] for kk in ('min', 'word', 'effects', 'mood') if kk in v} for k, v in sp['stages'].items()},
                    **({'weights': sp['weights']} if sp.get('weights') else {}),
                    **({'mood': {k: {kk: v[kk] for kk in ('time', 'mood')} for k, v in sp['mood'].items()}} if sp.get('mood') else {}),
                    **({'from_events': sp['from_events']} if sp.get('from_events') else {}),
                    **({'tastes': list(sp['tastes'])} if sp.get('tastes') else {})}
    return out


# ── 문장 — 결과 dict 하나를 자기 문장(_last_prose)·궤적 꼬리표(event_tags)·관전 요약(act_summary)이 읽는다. 사실만. ⚠️문구 임시 ──

def _full_tail(nid):
    sp = spec(nid)
    ln = stage(sp, int(sp['full_at'])).get('line') if sp else None
    return (ln or FULL_FALLBACK).rstrip('.')


def _fill_tail(last):
    """p0.5.18 먹은 순간 결과의 덧붙임 — 그 갈래(결과의 mood)의 결과 꼬리(정의의 mood.<갈래>.line, 끝 마침표 없이 · 배고픔은 싫어함만 '입에 맞지 않았다'). 없으면 None."""
    mv = (((spec(last.get('need')) or {}).get('mood') or {}).get(last.get('mood'))) or {}
    return fill_line(mv['line'], last.get('what')).rstrip('.') if mv.get('line') else None


def prose(last):
    """need_fill·need_none 결과의 1인칭 사실 문장 — 모르는 결과면 None. 숫자(충족도)는 없다 — 몸과 기분은 '몸:'·'기분:' 줄이 말한다.
    p0.5.18(문장 대원칙 '간결하고 명확하게'): '휴대식을 먹었다' · '휴대식을 먹지 못했다 — 배가 부르다'(가득 참의 몸 문장) · 싫어한 음식이면 '— 입에 맞지 않았다'."""
    r, what = last.get('result'), last.get('what') or '그것'
    shop, obj = last.get('shop'), what + josa(what, '을')
    if r == 'need_fill':
        bits = [b for b in (_fill_tail(last),) if b]
        if last.get('via') == 'buy':
            bits.append('%d골드를 냈다(남은 골드 %d)' % (last.get('price', 0), last.get('gold', 0)))
            return '%s에서 %s 사 먹었다 — %s' % (shop or '가게', obj, ' · '.join(bits))
        tail = (' (남은 휴대식 %d개)' % last['rations']) if 'rations' in last else ''
        return '%s 먹었다%s%s' % (obj, (' — ' + ' · '.join(bits)) if bits else '', tail)
    if r == 'need_none':
        if last.get('via') == 'buy':
            return '%s에서 %s 사지 않았다 — %s' % (shop or '가게', obj, _full_tail(last.get('need')))
        return '%s 먹지 못했다 — %s' % (obj, _full_tail(last.get('need')))
    return None


def event_tags(rec):
    """궤적 꼬리표(D40 사건 사전) — 새 키를 만들지 않는다(use·loot·misc·hurt 재사용 → EVENT_KINDS 무수정). 모르는 결과면 None.
    p0.5.18: 먹은 꼬리표에도 결과 꼬리('입에 맞지 않았다') · 못 먹은 꼬리표는 가득 참의 몸 문장(욕구마다 — 옛 '배가 불러 못 먹음' 고정 글 대신)."""
    r, what = rec.get('result'), rec.get('what') or '?'
    ft = _fill_tail(rec) if r == 'need_fill' else None
    if r == 'need_fill':
        if rec.get('via') == 'buy':
            return [('use', '사 먹음', '%s ← %s %d골드 (남은 %d)%s' % (what, rec.get('shop') or '가게', rec.get('price', 0), rec.get('gold', 0),
                                                                     (' · ' + ft) if ft else ''))]
        return [('use', '먹음', what + ((' — ' + ft) if ft else '') + ((' (남은 %d)' % rec['rations']) if 'rations' in rec else ''))]
    if r == 'need_none':
        return [('misc', '헛손질', '%s — %s' % (what, _full_tail(rec.get('need'))))]
    if r == 'need_drain':
        return [('hurt', '허기', '%s (HP %d/%d)' % (DRAIN_LINE, rec.get('hp', 0), rec.get('maxhp', 0)))]
    return None


def summary(res, names=None):
    """관전 로그 한 줄(show_runner.act_summary) — 관전자용이라 수치를 싣는다(충족도 전후·기분 갈래·단계 이동)."""
    r, nid = res.get('result'), res.get('need')
    nm = name_of(nid) if nid else '?'
    if r == 'need_fill':
        return '%s %s — %s %d→%d%s' % ('🍞' if res.get('via') != 'event' else '·', prose(res) if res.get('via') != 'event' else ('%s 결과로' % res.get('src_key', '?')),
                                     nm, res.get('before', 0), res.get('after', 0),
                                     (' · 기분 %s' % MOOD_SIZE.get(res['mood'], res['mood'])) if res.get('mood') else '')
    if r == 'need_none':
        return '%s — %s 가득 참' % (prose(res) if res.get('via') != 'event' else ('%s 결과' % res.get('src_key', '?')), nm)
    if r == 'need_stage':
        sp = spec(nid) or {}
        st = sp.get('stages') or {}
        return '%s: %s → %s' % (nm, (st.get(res.get('from')) or {}).get('word', res.get('from')), (st.get(res.get('to')) or {}).get('word', res.get('to')))
    if r == 'need_drain':
        return '%s — %s (HP %d/%d)' % (nm, DRAIN_LINE, res.get('hp', 0), res.get('maxhp', 0))
    if r == 'need_mood':                           # p0.5.18 기분 합산 결과 변화 — 관전 로그(합·이유를 싣는다)
        w = ENT.mood_words()
        return '기분: %s → %s%s' % (w.get(res.get('from'), '없음'), w.get(res.get('to'), '없음'),
                                   (' (%s · 합 %+d)' % (', '.join(res.get('why') or ()), res.get('sum', 0))) if res.get('to') else '')
    return None


_ORDER_RE = re.compile(r'(야\s*(?:한다|해|돼|된다|합니다|하지)'                      # 의무 — …해야 한다·먹어야 해·가야 한다
                       r'|(?:어|아|해|여|가|하|거)라|하라'                            # 명령 — 먹어라·가라·하라
                       r'|(?:하|가|먹|사|쉬|채우|찾|마시|보|오)자'                     # 청유 — 하자·가자·먹자
                       r'|(?:세요|십시오|시오)'                                       # 높임 명령
                       r'|하러\s*가)[.!…]*\s*$')


def order_problems(text):
    """문장 게이트(§3.8.6-6) — 명령·의무·청유 꼴로 끝나는 문장이면 그 문장(들). 0.5.14 약속 걸러내기(brains)와 같은 결: 말끝만 본다."""
    return [s for s in sentences(text) if _ORDER_RE.search(s)]
