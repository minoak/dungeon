# -*- coding: utf-8 -*-
"""욕구(need) 부품 — p0.5.16(경제 1b, .orch/drafts/economy_design.md §3 · DECISIONS 10-14·10-15).

고리(민옥 10-14): 배고프다 → 먹는다 → 기분이 좋다(기분 조각) · 배가 불러 더 못 먹는다(가득 참) → 시간이 지나 다시 배고프다.
이 고리 하나를 **데이터로** 정의한다(entities/need/<id>.json 의 comps.need + 말 파일 prompts/world/need/<id>.md). 배고픔이 첫 사례이고,
다음 욕구는 같은 틀에 정의 한 장을 더한다(코드 무수정 — verify_needs 가 시험용 정의 한 장으로 고리 전체를 돌려 본다).

  · 몸: bot['needs'] = {욕구: 충족도 0~100} · bot['moods'] = [{src, size, line, until}](같은 욕구의 조각은 새것이 덮는다) ·
    무게 bot['need_w'] = {욕구: 낮음|높음}(보통이 아닌 것만 — 시트 needs 칸에서, 0.5.16 은 시트에 칸이 없어 모두 보통) ·
    취향 bot['taste'] = {likes, dislikes}(시트 taste 칸 — 있을 때만). 무게·취향은 스폰이 시트에서 다시 읽는다(이월할 것이 없다).
  · 엔진 공용 지점 셋: 틱마다 줄이기(tick) · 채우기(eat — 먹을 것의 satisfies / on_result — 정의의 from_events) · 단계 판정(문장·효과·사건).
  · 숫자는 에이전트에게 보이지 않는다(§3.8.6) — 관측은 '몸과 기분' 줄(지금 단계의 상태 문장 + 살아 있는 기분 조각, 한 번에 문장 LINE_CAP 개,
    가장 낮은 단계부터)과 결과 사실 문장뿐. 보통 단계는 문장이 없어 줄이 안 생긴다. 충족도·단계 이름·무게·채운 양은 결과 dict 에서도
    공개 투영이 걷는다(info_guard.NEED_NUM_KEYS). 스트림(관전)은 원본을 싣는다 — tick.bots[].needs·moods, 사건 need_fill·need_none·need_stage·need_drain.
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

LINE_CAP = 2                 # §10-20 '몸과 기분' 줄 상한 — 한 번에 문장 2개(조각 수가 아니라 문장 수), 가장 낮은 단계의 상태 문장부터 · 그다음 새 기분 조각부터
DEFAULT_LEVEL = '보통'       # 시트에 무게가 없으면(0.5.16 은 모두) 보통 = 정의의 decay · 채움 100% · 기분 시간 100%
TOL_FULL = 100               # 내성 배율 자리(%) — 내성이 없는 동안 늘 100
WHY_MAX = 40                 # 시트 needs[].why(생성 근거 — 론처에만) 상한. 엔진은 읽지 않는다
LIKES_MAX, DISLIKES_MAX = 2, 1   # §3.6 취향 — 좋아함 0~2 · 싫어함 0~1
NEED_RESULTS = ('need_fill', 'need_none', 'need_stage', 'need_drain')   # 이 모듈이 내는 결과·사건 이름(§10-19 — ate·full 이름은 쓰지 않는다)
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
    """욕구 정의 전부(단계 없는 것 포함 — 시트 needs 칸의 열쇠 어휘·생성 호출 목록)."""
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

def sheet_fields(s):
    """시트(파티 파일의 한 칸) → 몸에 걸 칸만 거른 {needs?, taste?} — load_party 가 부른다. **판을 막지 않는다**: 모르는 욕구·등급이 아닌 값은
    그 칸만 버린다(그 욕구는 보통 — 설계 §3.8.2 검증 '그 욕구만 보통'), 취향은 어휘 안의 꼬리표만 · 좋아함 2·싫어함 1까지 · 겹치면 싫어함에서 뺀다.
    why 는 한 줄 WHY_MAX 자(론처용 — 게임 프롬프트에 안 나간다). 칸이 없거나 남는 것이 없으면 그 칸을 만들지 않는다."""
    out = {}
    nd = s.get('needs')
    ids = {d['id'] for d in all_defs()}
    if isinstance(nd, dict):
        keep = {}
        for nid, e in sorted(nd.items()):
            if nid not in ids or not isinstance(e, dict) or e.get('level') not in ENT.NEED_LEVELS:
                continue
            row = {'level': e['level']}
            if isinstance(e.get('why'), str) and e['why'].strip():
                row['why'] = ' '.join(e['why'].split())[:WHY_MAX]
            if e.get('src') in ('model', 'user', 'fallback'):
                row['src'] = e['src']
            keep[nid] = row
        if keep:
            out['needs'] = keep
    tt = s.get('taste')
    if isinstance(tt, dict):
        vocab = tastes()
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
    """스폰 몸의 칸 — 시작 충족도(정의의 start) · 빈 기분 조각 · 시트의 무게(보통이 아닌 것만 — 0.5.16 은 시트에 칸이 없어 생기지 않는다)·취향(있을 때만).
    판 안의 층 전이는 러너가 충족도·기분을 옮기고(carry), 부활은 되돌린다(reset)."""
    out = {'needs': {nid: int(sp['start']) for nid, sp in live()}, 'moods': []}
    sf = sheet_fields(sheet or {})
    w = {nid: e['level'] for nid, e in (sf.get('needs') or {}).items() if e['level'] != DEFAULT_LEVEL and spec(nid)}
    if w:
        out['need_w'] = w
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
    단계가 바뀌면 need_stage, HP 를 깎으면 need_drain(사건) + 그 몸의 궤적 한 칸(엔진 사실 — 관측의 HP 가 왜 줄었나). 판정 rng 무접촉."""
    specs = live()
    for b in bots:
        if not b.get('alive', True) or b.get('won'):
            continue
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


def _mood(sp, bot, tags):
    """먹은 것의 꼬리표 × 몸의 취향 → 기분 갈래(싫어함을 좋아함보다 먼저 본다 — §3.6). 정의에 그 갈래가 없으면 plain."""
    taste = bot.get('taste') or {}
    tags = set(tags or ())
    mk = 'dislike' if tags & set(taste.get('dislikes') or ()) else 'like' if tags & set(taste.get('likes') or ()) else 'plain'
    md = sp.get('mood') or {}
    return mk if mk in md else ('plain' if 'plain' in md else None)


def _fill(d, bot, nid, amount, turn, what=None, tags=(), via='eat', src_key=None):
    """한 욕구를 채운다 → need_fill 칸(dict). 무게의 fill% 를 곱하고(올림 없이 반올림) 100 에서 자른다 · 기분 조각을 붙인다(같은 욕구의 조각은 덮는다)."""
    sp = spec(nid)
    w = weight(sp, level(bot, nid))
    gain = max(1, int(round(int(amount) * int(w['fill']) / 100.0)))
    before, after = _set(d, bot, nid, (bot.get('needs') or {}).get(nid, int(sp['start'])) + gain)
    rec = {'result': 'need_fill', 'need': nid, 'via': via, **({'what': what} if what else {}),
           **({'src_key': src_key} if src_key else {}), 'tol': TOL_FULL, 'before': before, 'after': after}
    mk = _mood(sp, bot, tags)
    if mk:
        m = sp['mood'][mk]
        until = int(turn) + max(1, int(round(int(m['time']) * int(w['mood_time']) / 100.0)))
        moods = [x for x in (bot.get('moods') or []) if x.get('src') != nid]
        moods.append({'src': nid, 'size': mk, 'line': fill_line(m['line'], what), 'until': until})
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
    rows = [_fill(d, bot, nid, amt, turn, what=what, tags=tags, via=via, src_key=df['id']) for nid, amt in food_of(df)]
    for extra in rows[1:]:
        _log(d).append({'type': 'need', 'bot': bot['char'], **extra})
    return rows[0]


def on_result(d, bot, res, turn):
    """정의의 from_events — 행동 결과(result 이름)가 그 욕구를 채운다(엔진이 결과를 판정한 뒤 · 그 몸의 행동·자동 보행 결과: Dungeon._note_last 가 부른다 —
    남이 내게 한 일(맞음·받음)은 _note_last 를 지나지 않아 세지 않는다).
    가득 찬 욕구는 더 채우지 않는다 — 행동은 이미 일어났으니 막지 않고 need_none{why:'full'} 사건만(§3.7 몸에 들어가지 않는 욕구의 가득 참)."""
    r = (res or {}).get('result')
    if not r or r in NEED_RESULTS:
        return
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


# ── 관측 · 스트림 ───────────────────────────────────────────────────

def sentences(text):
    """글 → 문장들(마침표·느낌표·물음표·말줄임 뒤 공백에서 나눈다 — 문장 게이트 order_problems 와 같은 자르기)."""
    return [s for s in _SENT_RE.split(str(text or '').strip()) if s]


def lines(bot, turn):
    """'몸과 기분' 줄의 조각들 — 지금 단계의 상태 문장(가장 낮은 충족도부터) 다음 살아 있는 기분 조각(새것부터). 없으면 [].
    상한은 **문장 수**(LINE_CAP) — 조각 하나가 문장 둘이면(굶주림) 그것만으로 찬다. 남은 자리보다 긴 조각은 앞 문장만 남긴다(뒤의 것은 밀린다)."""
    rows = []
    for nid, sp in live():
        v = (bot.get('needs') or {}).get(nid)
        if v is None:
            continue
        ln = stage(sp, v).get('line')
        if ln:
            rows.append((v, nid, ln))
    pieces = [ln for _v, _n, ln in sorted(rows)]
    pieces += [m['line'] for m in reversed(bot.get('moods') or []) if int(m.get('until', 0)) > int(turn) and m.get('line')]
    out, left = [], LINE_CAP
    for ln in pieces:
        ss = sentences(ln)
        if left <= 0:
            break
        if ss:
            out.append(ln if len(ss) <= left else ' '.join(ss[:left]))
            left -= min(len(ss), left)
    return out


def snap(bot):
    """봇 스냅샷(스트림 tick.bots[]·level.party[])에 얹을 칸 — 충족도 · 살아 있는 기분 조각(있을 때만). 관전용(관측엔 안 나간다)."""
    if bot.get('needs') is None:
        return {}
    out = {'needs': dict(bot['needs'])}
    if bot.get('moods'):
        out['moods'] = [dict(m) for m in bot['moods']]
    return out


def defs_meta():
    """run_meta.need_defs — 단계가 있는 욕구 정의(단계·효과·무게 숫자·기분 시간·취향 어휘). 측정 도구가 스트림만으로 단계를 다시 셀 수 있게(bestiary_defs 와 같은 꼴)."""
    out = {}
    for nid, sp in live():
        out[nid] = {'name': name_of(nid), 'start': sp['start'], 'decay': sp['decay'], 'full_at': sp['full_at'], 'full_blocks': sp['full_blocks'],
                    'stages': {k: {kk: v[kk] for kk in ('min', 'word', 'effects') if kk in v} for k, v in sp['stages'].items()},
                    **({'weights': sp['weights']} if sp.get('weights') else {}),
                    **({'mood': {k: {'time': v['time']} for k, v in sp['mood'].items()}} if sp.get('mood') else {}),
                    **({'from_events': sp['from_events']} if sp.get('from_events') else {}),
                    **({'tastes': list(sp['tastes'])} if sp.get('tastes') else {})}
    return out


# ── 문장 — 결과 dict 하나를 자기 문장(_last_prose)·궤적 꼬리표(event_tags)·관전 요약(act_summary)이 읽는다. 사실만. ⚠️문구 임시 ──

def _full_tail(nid):
    sp = spec(nid)
    ln = stage(sp, int(sp['full_at'])).get('line') if sp else None
    return (ln or FULL_FALLBACK).rstrip('.')


def prose(last):
    """need_fill·need_none 결과의 1인칭 사실 문장 — 모르는 결과면 None. 숫자(충족도)는 없다 — 기분은 '몸과 기분' 줄이 말한다."""
    r, what = last.get('result'), last.get('what') or '그것'
    shop = last.get('shop')
    if r == 'need_fill':
        if last.get('via') == 'buy':
            return '%s에서 %s 사서 그 자리에서 먹었다 — %d골드를 냈다(남은 골드 %d)' % (
                shop or '가게', what + josa(what, '을'), last.get('price', 0), last.get('gold', 0))
        tail = (' (남은 휴대식 %d개)' % last['rations']) if 'rations' in last else ''
        return '%s 먹었다%s' % (what + josa(what, '을'), tail)
    if r == 'need_none':
        if last.get('via') == 'buy':
            return '%s에서 %s 사 먹으려 했다 — %s(사지 않았다)' % (shop or '가게', what + josa(what, '을'), _full_tail(last.get('need')))
        return '%s 먹으려 했다 — %s(그대로 남았다)' % (what + josa(what, '을'), _full_tail(last.get('need')))
    return None


def event_tags(rec):
    """궤적 꼬리표(D40 사건 사전) — 새 키를 만들지 않는다(use·loot·misc·hurt 재사용 → EVENT_KINDS 무수정). 모르는 결과면 None."""
    r, what = rec.get('result'), rec.get('what') or '?'
    if r == 'need_fill':
        if rec.get('via') == 'buy':
            return [('use', '사 먹음', '%s ← %s %d골드 (남은 %d)' % (what, rec.get('shop') or '가게', rec.get('price', 0), rec.get('gold', 0)))]
        return [('use', '먹음', what + ((' (남은 %d)' % rec['rations']) if 'rations' in rec else ''))]
    if r == 'need_none':
        return [('misc', '헛손질', '%s — 배가 불러 못 먹음' % what)]
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
    return None


_ORDER_RE = re.compile(r'(야\s*(?:한다|해|돼|된다|합니다|하지)'                      # 의무 — …해야 한다·먹어야 해·가야 한다
                       r'|(?:어|아|해|여|가|하|거)라|하라'                            # 명령 — 먹어라·가라·하라
                       r'|(?:하|가|먹|사|쉬|채우|찾|마시|보|오)자'                     # 청유 — 하자·가자·먹자
                       r'|(?:세요|십시오|시오)'                                       # 높임 명령
                       r'|하러\s*가)[.!…]*\s*$')


def order_problems(text):
    """문장 게이트(§3.8.6-6) — 명령·의무·청유 꼴로 끝나는 문장이면 그 문장(들). 0.5.14 약속 걸러내기(brains)와 같은 결: 말끝만 본다."""
    return [s for s in sentences(text) if _ORDER_RE.search(s)]
