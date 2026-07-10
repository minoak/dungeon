#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
봇 두뇌 — claude_brain (레이어 2) : 캐릭터 연기 + 행동 선언
─────────────────────────────────────────────
claude.exe -p --model haiku 로 (캐릭터 시트 + obs)를 주고 한 '행동'을 받는다.
  · 과금: 구독(정액제) → 토큰 과금 0
  · 속도: 콜드 ~5-8초/콜. 봇들은 동시 호출(ThreadPool)로 묶어 턴당 1콜 폭.
  · 안전: 파싱 실패/타임아웃 → 엔진 규칙두뇌(dummy_brain) 폴백 → 절대 안 죽음.

진실(좌표·이동가능·주사위 판정)은 dungeon_gm 이 쥔다. 봇은 '의도'만 낸다.
반환: {type, [target], [choice], say, reason, src}
   type ∈ goto/attack/interact/search/explore ; target=보이는 오브젝트 id(explore는 선택적 방위).
   choice = 리모컨 모드에서 고른 옵션 번호(기록용 — 엔진 판정은 type/target 만 읽는다).
리모컨(기본): 행동은 obs['options'](엔진 열거)에서 번호 선택 — DUNGEON_MENU=0 이면 구식 자유서술.
"""
import os
import re
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

import dungeon_gm as G

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "adventurer_prompt.md"), encoding="utf-8") as _f:
    ADV_PROMPT = _f.read()
try:
    with open(os.path.join(HERE, "adventurer_prompt_menu.md"), encoding="utf-8") as _f:
        MENU_PROMPT = _f.read()
except OSError:                                  # 파일 누락 배포여도 게임은 죽지 않는다(안전망)
    MENU_PROMPT = ""

# 리모컨 모드(기본 on): 행동=엔진 열거 옵션에서 번호 선택, 말·속내=자유.
# DUNGEON_MENU=0 이면 구식 자유서술(동사+target 직접 작성) — A/B 대조군.
MENU = os.environ.get("DUNGEON_MENU", "1") != "0" and bool(MENU_PROMPT)
if os.environ.get("DUNGEON_MENU", "1") != "0" and not MENU_PROMPT:
    import sys
    print("[경고] adventurer_prompt_menu.md 없음 — 리모컨 끄고 자유서술로 폴백", file=sys.stderr)

# WSL 인터롭 네이티브 exe. npm 래퍼(claude)는 stdin 대기로 멈추므로 .exe 고정.
CLAUDE_BIN = "claude.exe"
TIMEOUT = 60   # 콜드스타트 ~8초라 넉넉

_TYPES = {"goto", "attack", "interact", "search", "explore"}
_BEARINGS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def _valid_targets(obs):
    """obs 에 실제로 보이는 오브젝트 id 집합 — 환각 타겟 차단. 출구는 *보일 때만*(beacon 폐기).
    동료(b<char>)는 안 보여도 허용(파티 감각) — 하강 조율(데리러 가기)의 통로. 좌표는 여전히 비공개."""
    s = obs.get("sights", {})
    ids = set()
    if s.get("exit"):                       # 출구는 sights['exit']가 있을 때(=보일 때)만 핑 허용
        ids.add("exit")
    for k in ("features", "monsters", "bots"):
        ids |= {o["id"] for o in s.get(k, [])}
    for p in obs.get("party", []):          # 살아있는(안 내려간) 동료는 시야 밖이어도 핑 가능
        if p.get("alive") and not p.get("won"):
            ids.add("b%s" % p["char"])
    return ids


def _head(s, n=60):
    """실패 원문의 머리 n자 — 개행·연속공백 접기(폴백 reason 한 줄 유지)."""
    return re.sub(r"\s+", " ", str(s).strip())[:n]


def _call_claude(prompt, model="haiku"):
    """프롬프트를 stdin으로 넘긴다(긴 프롬프트 argv 따옴표 문제 회피).
    반환 = (응답텍스트, 실패라벨|None). 타임아웃/호출에러/빈응답을 구분해 라벨링 —
    폴백 reason에 실려 스트림·봇로그에 남는 계측(한 라벨로 뭉개면 부검 불가)."""
    try:
        r = subprocess.run(
            [CLAUDE_BIN, "-p", "--model", model],
            input=prompt, capture_output=True,
            text=True, encoding="utf-8", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "", "타임아웃 %ds" % TIMEOUT
    except Exception as e:
        return "", "호출 실패 %s" % type(e).__name__
    out = (r.stdout or "").strip()
    if not out:
        why = "빈 응답 rc=%s" % r.returncode
        err = (r.stderr or "").strip().splitlines()
        if err:
            why += " | " + _head(err[-1])
        return "", why
    return out, None


def _extract(raw):
    """잡텍스트·코드펜스 속에서 첫 {...} JSON 객체만 건진다. 반환 = (obj|None, 실패라벨|None)."""
    if not raw:
        return None, None                    # 빈 입력의 라벨은 호출층(_call_claude)이 이미 만들었다
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None, "JSON 없음: " + _head(raw)
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None, "JSON 불량: " + _head(m.group(0))
    if not isinstance(obj, dict):
        return None, "JSON 비객체"
    return obj, None


def _sheet(bot, roster=None):
    """캐릭터 시트를 프롬프트 머리에 붙여 '정체성'을 박는다 — 봇 dict(시트 외부화) 기반.
    roster = 파티 봇 목록(관계·동료를 이름으로 풀이). 선택 필드(name/speech/goal/relationships)는
    있을 때만 줄이 생긴다 — 엔진 판정과 무관한 프롬프트 전용."""
    nm = bot.get("name") or ("모험가 %s" % bot.get("char", "?"))
    lines = ["## 너의 캐릭터",
             "- 번호 %s, 이름 **%s** — %s (%s)"
             % (bot.get("char", "?"), nm, bot.get("job", "모험가"), bot.get("sex", "")),
             "- 성격: %s" % bot.get("persona", "")]
    if bot.get("speech"):
        lines.append("- 말투: %s" % bot["speech"])
    if bot.get("goal"):
        lines.append("- 목표: %s" % bot["goal"])
    lines.append("- 능력: HP %s, 힘(STR) +%s, 민첩(DEX) +%s, 은신 +%s, 인지 반경 %s"
                 % (bot.get("maxhp"), bot.get("str"), bot.get("dex"),
                    bot.get("stealth", 0), bot.get("search_r", 1)))
    names = {o["char"]: (o.get("name") or "모험가 %s" % o["char"])
             for o in (roster or []) if o.get("char") != bot.get("char")}
    if names:
        lines.append("- 동료: " + ", ".join("%s(봇%s)" % (names[c], c) for c in sorted(names)))
    rel = bot.get("relationships") or {}
    for oc in sorted(rel):
        if oc not in names:
            continue                        # roster 밖 대상(무해 처리) — 죽은/없는 동료 관계는 침묵
        lines.append("- %s(봇%s)와의 관계: %s" % (names[oc], oc, rel[oc]))
    lines.append("- 시트의 성격·말투·목표·관계대로 판단하고 말하라.")
    return "\n".join(lines) + "\n"


def _pick(obj, obs):
    """리모컨 응답 {"choice": n} → obs['options'][n] 의 액션으로 해석.
    유효하면 {type, target?, choice} — choice 는 스트림 기록용(additive), 엔진 act 는 무시.
    관용 파싱: 3.0(JSON float)·"3."·"옵션 3" 같은 흔들림도 의지로 살린다(폴백行 방지)."""
    s = str(obj.get("choice", "")).strip()
    try:
        n = int(s)
    except (TypeError, ValueError):
        try:
            f = float(s)
            n = int(f) if f.is_integer() else None    # 3.0 → 3. (3.5는 기각 — 절삭 오해석 방지)
        except (TypeError, ValueError):
            m = re.search(r"-?\d+", s)                # "옵션 3"·"3번" → 3
            n = int(m.group(0)) if m else None
    if n is None:
        return None
    o = next((o for o in (obs.get("options") or []) if o.get("n") == n), None)
    if not o:
        return None
    out = {"type": o["type"], "choice": n}
    if "target" in o:
        out["target"] = o["target"]
    return out


def _fallback(obs, char, why="파싱 실패"):
    """엔진 규칙두뇌(dict 반환)에 say/reason/src 옷을 입혀 돌려준다.
    why = 실패 종류 라벨(타임아웃/빈 응답/JSON 불량/행동 해석 실패…) — 스트림·봇로그 계측."""
    fb = dict(G.dummy_brain(obs, char))            # {type, [dir]}
    fb.update(say="", reason="[폴백] %s -> 규칙두뇌" % why, src="fallback")
    return fb


def claude_brain(obs, char="?", bot=None, roster=None):
    if bot is None:                          # 하위호환(구 시그니처): HEROES 로 유사 봇 구성
        h = G.HEROES.get(char, {})
        bot = {**h, "char": char, "maxhp": h.get("hp")}
    if MENU:
        menu = "\n".join("%d. %s" % (o["n"], o["label"])
                         for o in (obs.get("options") or []))
        prompt = (_sheet(bot, roster) + "\n" + MENU_PROMPT
                  + "\n\n## 이번 턴 입력 (obs)\n```json\n"
                  + json.dumps(obs, ensure_ascii=False)
                  + "\n```\n\n## 이번 턴 선택지 — 이 중 번호 하나를 골라라\n" + menu
                  + "\n\n오직 JSON 한 줄로만 답하라.")
    else:
        wire = {k: v for k, v in obs.items() if k != "options"}  # 대조군(자유서술) 순수성 — 메뉴 미노출
        prompt = (_sheet(bot, roster) + "\n" + ADV_PROMPT
                  + "\n\n## 이번 턴 입력 (obs)\n```json\n"
                  + json.dumps(wire, ensure_ascii=False)
                  + "\n```\n오직 JSON 한 줄로만 답하라.")
    res = _call_claude(prompt, "haiku")
    # verify/스모크가 _call_claude 를 str 반환 람다로 모킹한다 — 그 표면을 깨지 않는 하위호환.
    raw, why = res if isinstance(res, tuple) else (res, None)
    obj, jwhy = _extract(raw)
    why = why or jwhy
    if obj:
        if MENU:
            act = _pick(obj, obs)
            if act:
                return {**act,
                        "say": str(obj.get("say", ""))[:160],
                        "reason": str(obj.get("reason", ""))[:160],
                        "src": "haiku"}
            # choice 불량/부재 → 아래 구식(type/target) 관용 파싱으로 폴스루(의지 최대 보존)
        typ = str(obj.get("type", "")).strip().lower()
        tgt = str(obj.get("target", "")).strip()
        if typ not in _TYPES and tgt:
            # 관용 보정 — LLM 의도를 최대한 살린다(전부 폴백으로 떨구면 '의지=LLM'이 소실):
            typ = "explore" if tgt.upper() in _BEARINGS else "goto"   # 방위만 준 응답 = 탐색 의도
        if typ == "goto" and not tgt:
            typ = "explore"                         # 목표 없는 goto = 탐색으로 강등(폴백行 방지)
        if typ in _TYPES:
            out = {"type": typ,
                   "say": str(obj.get("say", ""))[:160],
                   "reason": str(obj.get("reason", ""))[:160],
                   "src": "haiku"}
            if typ == "search":
                return out                          # search는 target 불필요
            if typ == "explore":                    # 탐색: 방위(N/S/E/W/NE…)만 선택적으로(없으면 엔진 자동)
                if tgt.upper() in _BEARINGS:
                    out["target"] = tgt.upper()
                return out
            if tgt in _valid_targets(obs):          # 보이는 id만 허용(환각 타겟 차단)
                out["target"] = tgt
                return out
        # JSON 은 왔으나 행동으로 해석 실패(무효 choice·type·target) — 원문 머리를 계측에 남긴다
        why = "행동 해석 실패: " + _head(json.dumps(obj, ensure_ascii=False))
    return _fallback(obs, char, why or "파싱 실패")


def think_all(d, bots, inbox=None):
    """order 없는(=재결정 필요한) 살아있는 봇만 '같은 틱-시작 스냅샷'에서 동시 사고.
    order 있는 봇은 엔진 자동보행 중이라 LLM 호출 안 함(콜 절약). inbox→obs.messages 주입."""
    live = [b for b in bots if b["alive"] and not b["won"] and not b.get("order")]
    if not live:
        return {}
    inbox = inbox or {}
    obss = {}
    for b in live:
        o = d.view(b, bots)
        o["messages"] = inbox.get(b["char"], [])
        if b.get("intent"):
            o["intent"] = b["intent"]   # 판단 되먹임(D15①): 자기 직전 판단의 기억 — inbox와 같은
        obss[b["char"]] = o             # 주입 솔기. 세계 정보가 아니라 자기 것이라 시야-온리 무관.
    with ThreadPoolExecutor(max_workers=len(live)) as ex:
        futs = {b["char"]: ex.submit(claude_brain, obss[b["char"]], b["char"], b, bots)
                for b in live}               # bot=시트 포함 봇 dict, roster=파티(관계 이름 풀이)
        out = {c: f.result() for c, f in futs.items()}
    by = {b["char"]: b for b in live}
    for c, dec in out.items():          # 이번 판단을 자기 기억으로 저장 → 다음 결정의 obs.intent.
        it = {"type": dec.get("type", "")}   # bot_snapshot 화이트리스트 밖 = 스트림 계약 불변
        for k in ("target", "say", "reason", "src"):   # (직전 decisions에서 파생 가능한 값).
            if dec.get(k):
                it[k] = dec[k]
        by[c]["intent"] = it
    if os.environ.get("DUNGEON_STREAM_OBS") == "1":
        # 스트림 opt-in: 결정에 '그때 그 봇이 본 것'(obs)을 병합 — think 시점 캡처.
        # 사후 d.view() 재호출로 얻으면 안 된다(시점 오염 + _perceive 부수효과).
        for c in out:
            out[c] = {**out[c], "obs": obss[c]}
    return out
