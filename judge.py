# -*- coding: utf-8 -*-
"""판정 함수 묶음(master_plan §8.1·§8.4) — p0.5.3 숙련 접근자 + p0.5.4 판정 함수 넷.

숙련 접근자(p0.5.3): 몸·시트의 정신(mind)·수색 숙련(search_prof)·손재주 숙련(steal_prof)을 읽는 길.
  · 시트(또는 몸)에 값이 있으면 그 값 → 직업이 traits.json 에 있으면 그 직업의 기본값 → 그 밖(손 시트의 모르는 직업)은 0.
  · 몹·NPC(dict 가 아닌 것)는 0 — 몹의 정신은 0이다(§2.1). 몹의 발각 보정은 지금 그대로 엔진이 따로 쥔다.
  · 기본값은 시트에 복사하지 않는다(sheetkit.build_sheet) — 스폰이 이 함수로 몸에 붙인다(dungeon_gm.spawn). 직업표를 고치면 옛 시트도 따라간다.

판정 함수(p0.5.4 — §6.2 F). 결과 = {공개 칸, 'audit': {...}}. 공개 칸은 성패·단계 하나뿐이고, 주사위 눈·보정·문턱은 전부 audit 으로 간다
(info_guard.secret 표식 — 행동 결과에 옮겨 적어도 공개 투영이 걸러 낸다). 사람 대상 판정은 자기 주사위 눈도 숨긴다(합계와 성패로 DC 를 좁힌다).
  notice(d, obs, subj, ctx)          관측자 d20 + 정신 + 수색 숙련(몹은 호출자가 기존 발각 보정을 mod 로) ≥ 13 + 대상 은신(ctx='steal' 이면 13 고정)
                                     → {'noticed'} — **관측자 쪽 사실**이다. 대상(행동자)의 결과에 싣지 않는다(행동자는 들켰는지 모른다 §3.2).
  contest(d, a, b, abil_a, abil_b)   a 먼저, b 다음 d20 + 능력치(고정 순서 — rng 소비 순서가 늘 같다). 동점은 방어자(b) → {'won'}(a 쪽)
  own_check(d, actor, mod, dc, tiers) 행동자가 고른 행동의 굴림 → {'stage'}: 0 실패, 1.. 여유 5마다 한 단계(최대 tiers)
                                     — 도움 +2 소비(5단계)·서툶 C안(C1)이 그 단계에서 여기에 붙는다
  mind_save(d, who, dc, source)      정신 내성(class_design §2.6) d20 + 정신 → {'saved'}
아직 엔진의 어느 판정도 이 함수를 부르지 않는다 — 쓰는 곳은 그 행동이 들어오는 단계(steal·hide·shove·demand·help·스킬)다.
그래서 0.5 는 판정 rng 소비가 늘지 않는다(§10.1). 주사위는 넘겨받은 던전의 것만(skill_combat.check → d.d20) — 이 모듈은 난수를 따로 갖지 않는다.
LLM 0콜 · 엔진 무의존(dungeon_gm 을 import 하지 않는다 — 엔진이 이 모듈을 쓴다).
"""
import info_guard as IG
import skill_combat as SC

PROF_KEYS = ("mind", "search_prof", "steal_prof")   # 몸에 붙는 정신·숙련 칸(은신 stealth 는 기존 몸 칸 그대로 — 쪼개지 않는다)
NOTICE_DC = 13                                       # notice 문턱 = 13 + 대상 은신(§2.2 — 지금 몹 발각 DETECT_DC_BASE 와 같은 꼴), steal 은 13 고정
TIER_STEP = 5                                        # own_check 단계 폭 — 여유 5·10(사람 읽기·살피기 §2.2)

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


def ability(who, name):
    """판정 능력치 — 봇 dict: 힘·민첩은 몸 칸, 정신은 prof. 몹: 정신 0, 힘 = atk, 민첩 = max(0, AC-10)(skill_core.ability 와 같은 규칙).
    그 밖(NPC 피처 등 — 몸이 없다)은 0."""
    if isinstance(who, dict):
        return prof(who, "mind") if name == "mind" else who[name]
    if name == "mind" or not hasattr(who, "atk"):
        return 0
    return who.atk if name == "str" else max(0, who.ac - 10)


def stealth(who):
    """은신 합계(기존 몸 칸) — 봇만. 몹·NPC 는 0."""
    v = who.get("stealth", 0) if isinstance(who, dict) else 0
    return v if _int(v) else 0


def _check(d, mod, dc, advantage, disadvantage, **extra):
    rec = SC.check(d, mod, dc, advantage=advantage, disadvantage=disadvantage)
    return rec, IG.secret({**rec, **extra})


def notice(d, obs, subj, ctx=None, mod=None, advantage=False, disadvantage=False):
    """관측자 obs 가 대상 subj 의 몰래 하는 일을 알아채나. mod 를 주지 않으면 봇은 정신 + 수색 숙련, 그 밖은 0."""
    dc = NOTICE_DC if ctx == "steal" else NOTICE_DC + stealth(subj)
    if mod is None:
        mod = prof(obs, "mind") + prof(obs, "search_prof")
    rec, audit = _check(d, mod, dc, advantage, disadvantage, ctx=ctx or "notice")
    return {"noticed": rec["success"], "audit": audit}


def contest(d, a, b, abil_a, abil_b):
    """힘 대결 등 — a(행동자) 먼저, b(방어자) 다음에 굴린다. a 의 합이 b 보다 커야 이긴다(동점 방어자)."""
    ra, rb = d.d20(), d.d20()
    ma, mb = ability(a, abil_a), ability(b, abil_b)
    won = ra + ma > rb + mb
    return {"won": won, "audit": IG.secret({"a": {"roll": ra, "mod": ma, "total": ra + ma, "ability": abil_a},
                                            "b": {"roll": rb, "mod": mb, "total": rb + mb, "ability": abil_b}, "won": won})}


def own_check(d, actor, mod, dc, tiers=1, advantage=False, disadvantage=False):
    """행동자 굴림 → 단계(0 실패 · 성공이면 1 + 여유 5마다 1, 최대 tiers). actor 는 도움 +2·서툶이 붙을 자리(지금은 읽지 않는다)."""
    rec, audit = _check(d, mod, dc, advantage, disadvantage)
    stage = min(int(tiers), 1 + (rec["total"] - dc) // TIER_STEP) if rec["success"] else 0
    return {"stage": stage, "audit": audit}


def mind_save(d, who, dc, source=None, advantage=False, disadvantage=False):
    """정신 내성 — d20 + 정신(봇: prof, 몹·NPC: 0) ≥ dc 면 버틴다. source = 건 사람(기록용)."""
    rec, audit = _check(d, ability(who, "mind"), dc, advantage, disadvantage,
                        **({"source": str(source)} if source is not None else {}))
    return {"saved": rec["success"], "audit": audit}
