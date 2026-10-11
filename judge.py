# -*- coding: utf-8 -*-
"""판정 함수 묶음(master_plan §8.1·§8.4, p0.5.3 뼈대 — 판정은 0.5단계에서 채운다).

p0.5.3(0단계)에 들어간 것은 **숙련 접근자 하나**다: 몸·시트의 정신(mind)·수색 숙련(search_prof)·손재주 숙련(steal_prof)을 읽는 길.
  · 시트(또는 몸)에 값이 있으면 그 값 → 직업이 traits.json 에 있으면 그 직업의 기본값 → 그 밖(손 시트의 모르는 직업)은 0.
  · 몹·NPC(dict 가 아닌 것)는 0 — 몹의 정신은 0이다(§2.1). 몹의 발각 보정은 지금 그대로 엔진이 따로 쥔다.
  · 기본값은 시트에 복사하지 않는다(sheetkit.build_sheet) — 스폰이 이 함수로 몸에 붙인다(dungeon_gm.spawn). 직업표를 고치면 옛 시트도 따라간다.
  · 아직 이 값을 읽는 판정은 없다(0단계는 칸만). 이 모듈은 판정 rng 를 쓰지 않는다.

0.5단계에서 채울 것(§8.4 — 결과 = {공개 단계, audit}, 사람 대상 판정은 상대에게서 나온 수치를 audit 으로만):
  notice(obs, subj, ctx)      관측자 d20 + 정신 + 수색 숙련(몹은 기존 발각 보정) ≥ 13 + 대상 은신(ctx=steal 이면 13 고정)
  contest(a, b, abil_a, abil_b)  양쪽 d20 + 능력치, 고정 순서, 동점은 방어자
  own_check(actor, mod, dc, ...) 행동자가 고른 행동의 굴림 — 도움 +2 소비 · 서툶 C안
  mind_save(d, who, dc, ...)  정신 내성(CD §2.6)
LLM 0콜 · 엔진 무의존(dungeon_gm 을 import 하지 않는다 — 엔진이 이 모듈을 쓴다).
"""
PROF_KEYS = ("mind", "search_prof", "steal_prof")   # 몸에 붙는 정신·숙련 칸(은신 stealth 는 기존 몸 칸 그대로 — 쪼개지 않는다)

_JOBS = {}                                            # traits.json jobs 캐시(경로별)


def _jobs():
    """직업표 — sheetkit.load_traits 와 같은 검증을 거친 jobs. 못 읽으면 빈 표(모든 숙련 0) — 엔진이 시트 도구 때문에 멈추지 않게."""
    import sheetkit                                   # 늦은 import — 엔진은 시트 도구에 기대지 않는다(직업표만 빌린다)
    path = sheetkit.TRAITS_FILE
    if path not in _JOBS:
        try:
            _JOBS[path] = sheetkit.load_traits(path)["jobs"]
        except (OSError, ValueError):
            _JOBS[path] = {}
    return _JOBS[path]


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def prof(actor, key):
    """숙련 접근자(§8.1). actor = 시트 dict 또는 봇 몸 dict(그 밖은 0). key ∈ PROF_KEYS."""
    if key not in PROF_KEYS:
        raise KeyError(key)
    if not isinstance(actor, dict):
        return 0
    if _int(actor.get(key)):
        return actor[key]
    v = (_jobs().get(actor.get("job")) or {}).get(key, 0)
    return v if _int(v) else 0


def body_fields(sheet):
    """스폰·옛 스냅샷 이관이 몸에 붙이는 칸 {mind, search_prof, steal_prof}."""
    return {k: prof(sheet, k) for k in PROF_KEYS}


def notice(obs, subj, ctx=None):
    raise NotImplementedError("p0.5.3 뼈대 — 0.5단계(정보 보호 공통 인프라)에서 채운다")


def contest(a, b, abil_a, abil_b):
    raise NotImplementedError("p0.5.3 뼈대 — 0.5단계에서 채운다")


def own_check(actor, mod, dc, **kw):
    raise NotImplementedError("p0.5.3 뼈대 — 0.5단계에서 채운다")


def mind_save(d, who, dc, **kw):
    raise NotImplementedError("p0.5.3 뼈대 — 0.5단계에서 채운다")
