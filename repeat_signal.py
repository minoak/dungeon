# -*- coding: utf-8 -*-
"""반복 신호(p0.5.15 — DECISIONS 2026-10-15 민옥 제안 "같은 행동을 반복중이라면 트리거로 한번 환기").

같은 대상에 대한 연속 판단과 기다리기(wait) 연속을 센다 — 동사는 보지 않는다(goto·use·search·attack·말 걸기 … 대상 ID 가 같으면 한 연속).
대상이 바뀌거나 다른 행동(대상 없는 행동·탐색·휴식)이 끼면 끊긴다. 판단 = think_all 이 낸 결정 하나(작정 수 포함) — 자동 보행 틱은 판단이 아니라 세지 않는다.
연속이 AT(5·10)번째가 된 판단 뒤의 다음 관측에 한 번 obs['repeat'] — 관측 사실 한 줄(무발견 신호 DRY 와 같은 자리: '직전 판단과 그 결과' 절).
한 연속에 5번째·10번째 두 번뿐이다(그 뒤 5회마다는 없다). 무엇을 하라는 말은 없다 — 줄은 꼬리표 `반복 중: {대상} ×{n}`(LINES·SAME 한 곳 —
p0515d DECISIONS 10-15 '0.5.15 문장 간소화' 민옥 문구: 문장 대신 꼬리표).

' · 변화 없음'(SAME)은 그 연속 동안 아래가 하나도 없었을 때만 붙는다(하나라도 있으면 `반복 중: {대상} ×{n}`까지):
  · 몸이 바뀜 — HP·최대 HP·골드·보물·물약·축복 물약·장비·상태 태그·맡은 의뢰·파티원(연속 첫 판단 때의 관측과 맞댄다)
  · 대상이 바뀜 — 관측에 보이는 대상의 상태(몬스터 HP·상태 · 사람 HP·상태 태그 · 피처의 이름·종류·등 돌림 · 계단의 봉인)나, 보이다가 안 보임(p0515b)
  · 같은 동사의 결과가 바뀜 — 결과 기록 원문(장부·자리 칸 _VOLATILE 등 아래 p0519 칸만 뺀다 — 읽은 글 전문·피해 그대로, p0515b: 꼬리표 요약이 아니라)과
    들린 말(대상이 한 말·내게 한 말)을 그 동사의 첫 결과와 맞댄다(goto 와 use 를 섞어도 동사마다 처음과 같으면 '같다'). 걸음·행동 시작·도착만 있는 기록은 결과가 아니다.
    p0519: 궤적의 생략 표식(gap)·내가 한 말(said)도 결과가 아니고, 굴림 수치(_ROLL — 빗나감의 굴린 눈)와 내 몸짓 서술(_ECHO)은 맞대지 않는다
  · 한 번뿐인 결과 — 빈 결과가 아닌데 그 연속에서 한 번만 나온 동사의 결과는 새 정보다(되풀이돼야 '같다' — p0515b: goto 4번 뒤 첫 use)
  · 새로 발견함 — 발견 꼬리표(spot) · 찾아낸 것이 있는 search
엔진·판정 무접촉 · 0콜. 상태는 몸의 bot['repeat']{key, n, verb, body, base, cnt, npc?, moved?, due?}(봇 dict 수명 — 층 전이 = 새 몸이면 새로 센다 ·
스냅샷에 실린다, 저장 판 8 이관 snapshot._m7_repeat). 관측 칸은 그 몸 자신의 것뿐이다(남의 관측·스트림 봇 스냅샷에 실리지 않는다).
"""
import json

import dungeon_gm as G
import identity as ID

AT = (5, 10)                     # 신호가 뜨는 연속 횟수 — 한 연속에 이 둘만
WAIT = "wait"                    # 기다리기 연속의 열쇠(대상 ID 와 겹치지 않는다 — 대상 ID 는 f3·b2·m1·self·exit·@x,y …)
LINES = {   # p0515d 민옥 문구(DECISIONS 10-15 '0.5.15 문장 간소화') — 꼬리표. {what} = 그 관측의 대상 이름(사람은 이름 층 호칭) · {n} = 연속 수(5·10)
    "target": "반복 중: {what} ×{n}",
    "self": "반복 중: 제자리 ×{n}",     # 대상이 self(자기 자리 살피기·자기에게 쓰기)
    "wait": "반복 중: 기다리기 ×{n}",
}
SAME = " · 변화 없음"             # 위 '달라진 것' 판정이 하나도 없을 때만
_QUIET = ("move", "start")       # 결과 비교에서 빼는 꼬리표 — 걸음 수(N걸음·N틱 곁)와 행동의 시작(접근 시작·대기 시작 — 판단의 메아리)
_ARRIVED = ("arrive", "도착")     #   + 도착(가려던 자리·곁에 닿음) — 걸어서 닿으면 'f3 곁', 이미 곁이면 'f3 — 이미 곁'으로 글만 갈린다(판단의 메아리)
_BODY = ("hp", "maxhp", "gold", "inventory", "potions", "boons", "gear", "quests")
_VOLATILE = ("turn", "parent_action_id", "interrupted_action_id", "resolution", "char", "job",   # 결과 기록에서 비교하지 않는 칸 — 장부(틱·행동 번호·판정 요약
             "plan",                                                                              #   · p0519 작정 수로 한 행동 표식 — 같은 결과가 작정으로 나와도 같다)
             "len", "to", "bearing", "source_xy", "target_xy", "paced", "approach_status", "required_range", "action_type")   #   와 자리(걸음 수·좌표·방위·접근 단계)
_NOT_RESULT = ("gap", "said")    # p0519 결과가 아닌 궤적 칸 — 생략 표식(12칸 상한에 잘린 앞부분 수 — 긴 걸음 뒤 첫 관측에만 붙는다)과 내가 한 말(러너가 지목한 말마다
                                 #   남긴다 — 판단의 메아리, 행동 시작·도착을 뺀 것과 같은 이유). 대상이 한 말·내게 한 말(들린 말)은 그대로 본다
_ROLL = ("roll", "mod", "total", "combat_roll", "damage_roll", "skill_roll")   # p0519 굴림 수치 — 결과는 형태(종류·대상·성패)로 맞댄다: 빗나감은 굴린 눈이 달라도
_EFFECT_ROLL = ("save", "rolls", "value")   #   같은 빗나감(Codex p0515rr 권장). 스킬 효과 칸(effects[])은 내성 굴림·주사위 눈·굴린 값만 뺀다(실제 피해·회복·HP 는 남는다)
_ECHO = {"bond": ("form",)}      # p0519 내 행동 기록 속 내 판단의 자유 글(몸짓 서술 — 말과 같은 판단의 메아리). 남이 내게 한 몸짓(bonded)의 글은 본다
_NONE = json.dumps([[], []])     # 빈 결과(결과 기록도 들린 말도 없음)


def key_of(dec, char=None):
    """판단 → 연속의 열쇠. wait = WAIT · 대상이 있는 행동 = 대상 ID · 그 밖(탐색 — 길 ID 는 관측마다 새것 · 휴식 · 대상 없는 행동) = None(끊긴다).
    char = 판단한 사람 — 조합형은 self 를 행동자 ID(b<번호>)로 풀어 두므로 자기 자신은 'self' 하나로 모은다."""
    t = str((dec or {}).get("type") or "")
    if t == WAIT:
        return WAIT
    tgt = (dec or {}).get("target")
    if not tgt or t in ("explore", "rest"):
        return None
    tgt = str(tgt)
    return "self" if (char is not None and tgt == "b%s" % char) else tgt


def _target(obs, key):
    """p0515b 대상의 보이는 상태(관측에서) — 몬스터 [종, HP, 상태, 상태 태그] · 사람 [HP, 최대 HP, 상태 태그] · 피처 [이름, 종류, 등 돌림] · 계단 [워프게이트, 봉인].
    D39 오브젝트 태그(말 걸어 본 횟수)·거리는 안 본다(그 판단의 메아리·자리). 지금 안 보이면 '?'(보이다 안 보이면 달라진 것). 대상이 없는 연속(wait·self)은 None."""
    if key in (None, WAIT, "self"):
        return None
    s = obs.get("sights") or {}
    if ID.is_bot_key(key):
        b = next((x for x in (s.get("bots") or []) if str(x.get("char")) == key[1:]), None)
        return "?" if b is None else [b.get("hp"), b.get("maxhp"), sorted(map(str, b.get("status") or []))]
    if key == "exit":
        ex = s.get("exit")
        return "?" if not ex else [bool(ex.get("gate")), bool(ex.get("sealed"))]
    m = next((x for x in (s.get("monsters") or []) if x.get("id") == key), None)
    if m is not None:
        return [m.get("kind"), m.get("hp"), m.get("state"), sorted(map(str, m.get("status") or []))]
    f = next((x for x in (s.get("features") or []) if x.get("id") == key), None)
    return "?" if f is None else [f.get("name"), f.get("type"), bool(f.get("away"))]


def _body(obs, key=None):
    """몸의 사실 지문(관측에서) — 물건·골드·HP·장비·상태·의뢰·파티가 바뀌면 달라진다. 상태 태그는 이름과 겹친 수만(남은 틱은 안 본다).
    key = 연속의 열쇠 — 대상의 보이는 상태(_target)도 함께(p0515b: 나는 무사하고 대상에게 같은 피해를 이어 입혀도 대상 HP 가 준다)."""
    st = sorted((str(s.get("tag")), int(s.get("n", 1) or 1)) for s in (obs.get("status") or []) if isinstance(s, dict))
    pf = (obs.get("partyform") or {}).get("mine")
    return json.dumps([obs.get(k) for k in _BODY] + [st, pf, _target(obs, key)], ensure_ascii=False, sort_keys=True, default=str)


def _npc_name(obs, key):
    """대상 ID 가 마을 사람(NPC 피처)이면 그 이름 — 그 사람이 한 말('npc:<이름>')을 고르는 재료."""
    for f in (obs.get("sights") or {}).get("features") or []:
        if f.get("id") == key and f.get("type") == "npc":
            return f.get("name")
    return None


def _shape(e):
    """결과 기록 → 맞댈 원문: 장부·자리 칸(_VOLATILE)·굴림 수치(_ROLL · 스킬 효과 칸의 _EFFECT_ROLL)·내 판단의 자유 글(_ECHO)을 뺀 나머지 그대로(p0519)."""
    drop = _VOLATILE + _ROLL + _ECHO.get(str(e.get("type")), ())
    out = {k: v for k, v in e.items() if k not in drop}
    if isinstance(out.get("effects"), list):
        out["effects"] = [{k: v for k, v in x.items() if k not in _EFFECT_ROLL} if isinstance(x, dict) else x for x in out["effects"]]
    return out


def _outcome(obs, ch):
    """이 관측에 온 직전 판단의 결과 → (결과 지문 JSON, 새로 발견했나). 결과 = 궤적(있으면) 또는 직전 결과의 기록 원문(_shape — 장부·자리·굴림 수치·
    내 몸짓 서술만 뺀다 — p0515b: 꼬리표는 요약이라 읽은 글 뒷부분 같은 변화를 놓친다. 꼬리표가 걸음·행동 시작·도착뿐인 기록과
    생략 표식·내가 한 말(_NOT_RESULT)은 결과가 아니다) + 들린 말 중 연속의 대상이 한 말·내게 한 말(누가·무엇을)."""
    evs = obs["trail"] if "trail" in obs else ([obs["last"]] if isinstance(obs.get("last"), dict) else [])
    tags, found = set(), False
    for e in evs:
        if not isinstance(e, dict) or e.get("type") in _NOT_RESULT:
            continue
        if e.get("type") == "search" and e.get("found"):
            found = True
        loud = [t for t in G.event_tags(e) if not (t[0] in _QUIET or tuple(t[:2]) == _ARRIVED)]
        if any(t[0] == "spot" for t in loud):
            found = True
        if loud:
            tags.add(json.dumps(_shape(e), ensure_ascii=False, sort_keys=True, default=str))
    key = str(ch.get("key") or "")
    who = {key[1:]} if ID.is_bot_key(key) else set()
    if ch.get("npc"):
        who.add("npc:" + ch["npc"])
    said = {(str(m.get("from")), str(m.get("text", ""))) for m in (obs.get("messages") or [])
            if isinstance(m, dict) and (m.get("to_me") or str(m.get("from")) in who)}
    return json.dumps([sorted(tags), sorted(said)], ensure_ascii=False), found


def see(bot, obs):
    """판단 관측 하나(think_all — 들은 말까지 붙인 뒤)를 연속에 대 본다: 몸·대상·같은 동사의 결과·발견으로 '달라짐'을 적고,
    신호 차례(due)면 obs['repeat'] = {n, target | wait, same?} 를 한 번 싣는다(내보내고 비운다). 연속이 없으면 아무것도 안 한다.
    same 은 달라짐이 없고, 빈 결과가 아닌 동사마다 그 결과가 두 번 이상 나왔을 때만(p0515b — 한 번뿐인 결과는 새 정보)."""
    ch = bot.get("repeat")
    if not ch:
        return obs
    body = _body(obs, ch.get("key"))
    if ch.get("body") is None:
        ch["body"] = body
    elif body != ch["body"]:
        ch["moved"] = True
    out, found = _outcome(obs, ch)
    if found:
        ch["moved"] = True
    base = ch.setdefault("base", {})
    verb = str(ch.get("verb") or "")
    if verb not in base:
        base[verb] = out
    elif base[verb] != out:
        ch["moved"] = True
    if out != _NONE:
        cnt = ch.setdefault("cnt", {})
        cnt[verb] = int(cnt.get(verb) or 0) + 1
    due = ch.pop("due", None)
    if due:
        same = not ch.get("moved") and all(int(v) >= 2 for v in (ch.get("cnt") or {}).values())
        obs["repeat"] = {"n": due, **({"wait": True} if ch.get("key") == WAIT else {"target": ch.get("key")}),
                         **({"same": True} if same else {})}
    return obs


def step(bot, dec, obs=None):
    """판단 하나를 센다 — 같은 열쇠면 n+1(AT 에 닿으면 다음 관측에 싣는다), 다르면 새 연속(n=1, 몸 지문 = 그 판단의 관측), 열쇠가 없으면 연속을 지운다.
    obs = 그 판단의 관측(작정 수는 None — 몸 지문은 다음 관측에서 잡는다). 반환 = 지금 연속(없으면 None)."""
    key = key_of(dec, bot.get("char"))
    if key is None:
        bot.pop("repeat", None)
        return None
    ch = bot.get("repeat")
    if ch and ch.get("key") == key:
        ch.pop("due", None)                          # 앞 신호를 실을 관측이 없었다(작정 수가 이어졌다) — 늦게 싣지 않는다
        ch["n"] = int(ch.get("n") or 0) + 1
        if ch["n"] in AT:
            ch["due"] = ch["n"]
    else:
        ch = bot["repeat"] = {"key": key, "n": 1, "body": _body(obs, key) if obs is not None else None}
    ch["verb"] = str(dec.get("type") or "")
    if obs is not None and not ch.get("npc"):
        nm = _npc_name(obs, key)
        if nm:
            ch["npc"] = nm
    return ch


def seed(history, char=None):
    """저장 판 7→8 이관(snapshot._m7_repeat): 옛 몸의 최근 판단 장부(D38 history — type·target)의 끝에서 같은 열쇠가 이어진 수로 연속을 다시 세운다.
    지난 신호 차례는 늦게 싣지 않는다(due 없음) · 장부가 꽉 찬 연속은 그보다 길 수 있어 10 에서 멈춘다 · 그동안의 변화는 모른다(moved — '달라진 것은 없다'를 붙이지 않는다).
    char = 그 몸(자기 자신 b<번호> = self). 이어진 판단이 없으면 None."""
    hist = [h for h in (history or []) if isinstance(h, dict)]
    if not hist:
        return None
    key = key_of(hist[-1], char)
    if key is None:
        return None
    n = 0
    for h in reversed(hist):
        if key_of(h, char) != key:
            break
        n += 1
    return {"key": key, "n": min(n, max(AT)), "verb": str(hist[-1].get("type") or ""), "body": None, "moved": True}


def line(rep, what=None, near=False):
    """obs['repeat'] → 관측 꼬리표 한 줄(머리 '- ' 없이). what = 그 관측의 대상 이름(부르는 쪽 — brains._wire 가 이름 층 규칙으로 붙인다).
    near(곁 1칸 안에 보인다)는 부르는 쪽이 넘기지만 p0515d 꼬리표에는 쓰지 않는다(곁에서/두고 문장이 없어졌다)."""
    n = int(rep.get("n") or 0)
    if rep.get("wait"):
        s = LINES["wait"]
    elif rep.get("target") == "self":
        s = LINES["self"]
    else:
        s = LINES["target"]
    return s.format(what=what or str(rep.get("target") or ""), n=n) + (SAME if rep.get("same") else "")
