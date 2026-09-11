#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
봇 두뇌 — claude_brain (레이어 2) : 캐릭터 연기 + 행동 선언
─────────────────────────────────────────────
claude.exe -p --model haiku 로 (캐릭터 시트 + obs)를 주고 한 '행동'을 받는다.
  · 과금: 구독(정액제) → 토큰 과금 0
  · 속도: 콜드 ~5-8초/콜. 봇들은 동시 호출(ThreadPool)로 묶어 턴당 1콜 폭.
  · 실패: 같은 관측으로 한 번 재판단 → 계속 실패하면 실행 전 보류. 규칙 두뇌는 dummy 테스트 전용.

진실(좌표·이동가능·주사위 판정)은 dungeon_gm 이 쥔다. 봇은 '의도'만 낸다.
반환: {type, [target], [choice], say, reason, src}
   조합형 type = COMMON 10개 동사, target = 관측 대상 ID(self 포함, explore는 길 ID).
   choice = 리모컨 모드에서 고른 옵션 번호(기록용 — 엔진 판정은 type/target 만 읽는다).
조합형(기본): COMMON과 현재 대상 ID를 조합한다. 이전 방식은 백업 비교용 명시 설정에서만 읽는다.
"""
import os
import re
import json
import time                 # 콜별 지연 계측(사이드카 전용 — 스트림엔 절대 안 실린다)
import threading            # think_all 이 스레드풀 — 계측 줄 섞임 방지
import subprocess
from concurrent.futures import ThreadPoolExecutor

import dungeon_gm as G

HERE = os.path.dirname(os.path.abspath(__file__))


def _variant(text, solo):
    """프롬프트에서 판에 맞는 쪽만 남긴다 — `<!--PARTY-->…<!--/PARTY-->` / `<!--SOLO-->…<!--/SOLO-->`.

    왜 파일을 둘로 안 쪼갰나(2026-07-29): 갈리는 건 10줄인데 같은 건 60줄이다(세계 물리·작정·
    출력 형식). 파일이 둘이면 물리를 고칠 때 한쪽만 고치고 나머지가 조용히 낡는다 —
    이 레포는 verify_plan 이 4커밋 동안 빨간불인 걸 아무도 못 본 전적이 있다.

    이게 왜 중요한가: 솔로 판 첫 실측에서 두란이 계단을 t156 에 확보하고도 **t210 까지 54틱을
    없는 동료를 찾아다녔다**. 역할극이 아니었다 — 프롬프트가 "계단은 전원이 모여야 하강"이라고
    **규칙으로** 알려주고 있었다. 엔진은 이미 면제했는데 프롬프트가 거짓말을 한 것.
    세계가 바뀌면 세계 설명서도 같이 바뀌어야 한다 — verify_solo ⑪이 그물이다."""
    keep, drop = ("SOLO", "PARTY") if solo else ("PARTY", "SOLO")
    text = re.sub(r"<!--%s-->\n?.*?<!--/%s-->\n?" % (drop, drop), "", text, flags=re.S)
    return text.replace("<!--%s-->\n" % keep, "").replace("<!--/%s-->\n" % keep, "")


def _load_prompt(fname, required=True):
    try:
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            raw = f.read()
    except OSError:                              # 파일 누락 배포여도 게임은 죽지 않는다(안전망)
        if required:
            raise
        return "", ""
    return _variant(raw, False), _variant(raw, True)


LEGACY_PROMPT_DIR = os.path.join("backups", "prompts", "2026-09-10")
ADV_PROMPT, ADV_PROMPT_SOLO = _load_prompt(os.path.join(LEGACY_PROMPT_DIR, "adventurer_prompt.md"), required=False)
MENU_PROMPT, MENU_PROMPT_SOLO = _load_prompt(os.path.join(LEGACY_PROMPT_DIR, "adventurer_prompt_menu.md"), required=False)
COMPOSE_PROMPT, COMPOSE_PROMPT_SOLO = _load_prompt("adventurer_prompt.md")
# 사교 콜 프롬프트(채널 분리 2026-07-26) — 없으면 사교 채널이 통째로 꺼진다(안전망)
SOCIAL_PROMPT, SOCIAL_PROMPT_SOLO = _load_prompt("social_prompt.md", required=False)

# 조합형을 기본으로 사용한다. 명시적인 구형 환경 변수는 과거 비교 하니스와 호환한다.
_ACTION_MODE = os.environ.get("DUNGEON_ACTION_MODE", "").strip().lower()
if not _ACTION_MODE:
    _ACTION_MODE = ("menu" if os.environ["DUNGEON_MENU"] != "0" else "free") if "DUNGEON_MENU" in os.environ else "compose"
if _ACTION_MODE not in ("", "menu", "free", "compose"):
    raise ValueError("DUNGEON_ACTION_MODE는 menu/free/compose 중 하나여야 한다")
COMPOSE = _ACTION_MODE == "compose"
MENU = _ACTION_MODE == "menu"
if (MENU and not MENU_PROMPT) or (_ACTION_MODE == "free" and not ADV_PROMPT):
    raise FileNotFoundError("비교용 이전 프롬프트 백업이 없다: " + LEGACY_PROMPT_DIR)

# D17-4 직렬화 스위치: LLM 에게 보내는 obs 표현(wire)에서 큰 덩어리를 한 변수씩 끄는 노브.
# obs dict 자체(스트림·BYO·검증 계약)는 불변 — 여기는 '보여주는 방법'만 만진다(options 선례).
# ascii 기본 0 = 2026-07-11 프로브 판정(조우·궁지·로어주입 ×8콜, 사전등록 "지지만 않으면
# 채택"): 전 지표 동질 — sights 문장만으로 공간 판단 유지("7×7 그림은 인간용" §8 인사이트 실증).
OBS_ASCII = os.environ.get("DUNGEON_OBS_ASCII", "0") != "0"   # 7×7 그림+기호 줄(기본 끔)
OBS_POS = os.environ.get("DUNGEON_OBS_POS", "0") != "0"       # 생좌표 pos 줄 — 09-08 기본 끔(D17-4 pos 판정: 62판 6,080
                                                                #   LLM 결정 중 reason·say 좌표 사용 0·notes 5 = 계단·함정
                                                                #   위치 메모, 지금은 장부가 대신하는 목발. 파트너 발제)

# WSL 인터롭 네이티브 exe. npm 래퍼(claude)는 stdin 대기로 멈추므로 .exe 고정.
CLAUDE_BIN = "claude.exe"
TIMEOUT = 60   # 콜드스타트 ~8초라 넉넉

# ── 두뇌 백엔드(2026-07-25) ────────────────────────────────────────────────────
# 왜 가르나: claude.exe 는 콜마다 Node CLI 프로세스를 통째로 띄운다 — 20초/틱의 대부분이
# 모델이 아니라 프로세스 기동일 수 있다는 가설을, *같은 모델·같은 프롬프트*로 HTTP 한 방과
# 견줘야 잰다. 그래서 1단계 목적은 질감(모델) 교체가 아니라 지연 계측뿐이다.
# 기본값 = claude_cli: 라이브 판도 게이트도 지금 그대로 돈다(새 기능은 스위치 뒤 — gm.py 선례).
BACKENDS = ("claude_cli", "anthropic_api", "gemini_api", "dummy")

# 별칭 → 백엔드별 모델 id. 별칭("haiku")은 claude.exe 어휘 그대로 둔다 — 호출부
# `_call_claude(prompt, "haiku")` 가 계약이라 번역은 여기 한 곳에서만 한다. 두 곳에 흩으면
# 기본인자와 호출지점 중 한쪽만 바뀌는 사고가 난다.
_MODEL_ID = {
    "anthropic_api": {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-4-6"},
    "gemini_api":    {"haiku": "gemini-3-flash-preview", "sonnet": "gemini-3.1-pro"},
}
API_URL_ANTHROPIC = "https://api.anthropic.com/v1/messages"
API_URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

_warned = set()          # 경고 1회만 — _run_gates.sh 가 `2>&1 | tail -1` 로 판정한다.
                         #   stderr 가 stdout 에 머지되므로 경고 한 줄이 통과를 FAIL 로 뒤집는다.


def _warn_once(msg):
    """같은 경고는 한 번만. stdout 을 먼저 flush 해 게이트 판정줄을 보호한다."""
    if msg in _warned:
        return
    _warned.add(msg)
    import sys
    sys.stdout.flush()
    print(msg, file=sys.stderr)


def backend_name():
    """백엔드 이름을 *호출 시점에* 환경에서 읽는다.
    ⚠️ 모듈 로드 시점 상수로 굳히면 안 된다 — 게이트의 '스텁 먼저 박고 러너 나중 import'
    관용구(verify_stream 등)와 env 를 나중에 세팅하는 하니스(ab_menu)가 함께 깨진다.
    잘못된 값은 claude_cli 로 퇴화한다(판을 죽이지 않는다) + 경고 1회."""
    ov = getattr(_TLS, "backend_override", None)     # 안전 차단 재시도(09-11): 이 스레드의 이번 호출만 다른 두뇌
    name = (ov or os.environ.get("DUNGEON_BRAIN_BACKEND") or "claude_cli").strip()
    if name not in BACKENDS:
        _warn_once("[경고] 알 수 없는 DUNGEON_BRAIN_BACKEND=%r -> claude_cli 로 폴백" % name)
        return "claude_cli"
    return name


# 콜별 계측(기본 꺼짐). ⚠️ 스트림에는 절대 안 싣는다 — verify_stream 결정론 검사가 run_meta 의
# started 하나만 빼고 *전 라인* 바이트 동일을 요구한다(decisions 도 포함). 지연은 판마다
# 달라지므로 스트림에 넣는 순간 결정론이 깨진다. 프롬프트·응답 원문도 안 남긴다(글자 수만).
_LOG_LK = threading.Lock()
_TLS = threading.local()     # 봇마다 스레드가 다르다 — 모듈 전역이면 계측이 서로 섞인다


def _brainlog(**f):
    """DUNGEON_BRAIN_LOG=<경로> 일 때만 JSONL 한 줄. 값이 없으면 완전 무비용."""
    path = os.environ.get("DUNGEON_BRAIN_LOG", "")
    if not path:
        return
    try:
        line = json.dumps({"t": time.time(), **f}, ensure_ascii=False,
                          separators=(",", ":")) + "\n"
        with _LOG_LK:                        # think_all 이 스레드풀 — 줄 섞임 방지
            with open(path, "a", encoding="utf-8", newline="\n") as fp:
                fp.write(line)
    except Exception:
        pass                                 # 계측이 판을 죽이지 않는다(관측은 사치품)

# D26 의미 기억(07-24 확정): 결정 응답에 "남길 한 줄"(note) 선택 필드 피기백 — 추가 콜 0.
# 프레임 "사실=엔진(D22), 의미=에이전트(여기)": 엔진 판정 불가침 — 틀린 기억도 그 캐릭터의
# 착각으로 격리(시트 관계 필드 선례), 세계의 진실은 사건층이 쥔다. 표현층이라 brains 소유
# (obs dict 계약·엔진 코드 불변·결정론 무사 — 스트림 decisions.note 는 additive 파생).
# 프롬프트 캐싱 구조(파트너 발제)와 수렴: 시트=불변 프리픽스 + 기억=append 로그.
NOTES_ON = os.environ.get("DUNGEON_NOTES", "1") != "0"
HISTORY_ON = os.environ.get("DUNGEON_HISTORY", "1") != "0"   # 최근 판단 장부(D38 개정 2, 09-07 파트너 "과거 로그를
                                                                #   좀 더 제공") — 표현층 스위치(notes 선례, 기본 켬).
                                                                #   2-b(같은 날 밤): 선택만 — "엔진 결과가 들어가면 캐릭터는
                                                                #   유의미한 정보를 못 가져간다"(컨텍스트 걱정) → 결과 없이 창을 늘림
HISTORY_MAX = 10          # 되돌려줄 선택 수(직전 포함) — 파트너 미확정 임시 가정(09-07 밤, 5→10: 선택만이라 짧다)
DIALOGUE_ON = os.environ.get("DUNGEON_DIALOGUE", "1") != "0"   # 대화 기억(D43, 09-07 파트너 "대화 내용도 과거로 조금만 더
                                                                  #   확장") — 표현층 스위치(notes 선례, 기본 켬). 들은 말+내 말
DIALOGUE_MAX = 6          # 되돌려줄 마디 수 — 파트너 미확정 임시 가정(09-07 밤). 한 마디 ~40자 → 250자 안팎(+6%)
NOTE_MAX = 5             # 유지 줄 수(합의 5~7 하한) — 넘치면 오래된 것부터 바랜다(FIFO,
                         #   사람도 옛 기억부터 바래듯). 판 간 영속은 없음(월드 러너 상 재론).
NOTE_LEN = 80            # 한 줄 상한 — 수필 방지(say 160 의 절반: 기억은 말보다 압축된다)

_TYPES = {"goto", "attack", "interact", "search", "explore", "follow", "drink", "wait", "rest"}
_BEARINGS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def action_metadata():
    """프롬프트 실험을 구식 자유출력과 구분한다. 기존 menu/choice 계약은 유지."""
    return {"action_mode": "compose" if COMPOSE else "menu" if MENU else "free",
            **({"compose_profile": G.CA.PROFILE, "auto_approach": True} if COMPOSE else {})}


def _compose_types():
    """기본 동사 + 켜진 기능. 대상·거리·소지품에 따라 행동 목록을 좁히지 않는다."""
    types = ["goto", "follow", "explore", "search", "attack", "interact", "drink"]
    types += [t for t in ("give", "bond", "wait", "rest")
              if os.environ.get("DUNGEON_" + t.upper(), "1") != "0"]
    return types


def _compose_pick(obj, obs):
    """선행 프로브: 기존 동사를 직접 읽는다. 모르는 동사를 이동으로 바꾸지 않는다."""
    if obs.get('action_schema') == G.CA.SCHEMA:
        return G.CA.parse(obj, obs)
    typ = str(obj.get("type") or "").strip().lower()
    if typ not in _compose_types():
        return None, "invalid_type"
    tgt = str(obj.get("target") or "").strip()
    out = {"type": typ}
    if typ in ("search", "drink", "wait", "rest"):
        if tgt:
            return None, "unexpected_target"
    elif typ == "explore":
        if tgt:
            directions = {w["bearing"] for w in obs.get("sights", {}).get("ways", [])}
            if tgt.upper() not in directions:
                return None, "invalid_target"
            out["target"] = tgt.upper()
    else:
        if tgt not in _valid_targets(obs, typ):
            return None, "invalid_target"
        out["target"] = tgt
    if typ == "give":
        item = obj.get("item")
        if item not in ("potion", "weapon", "armor"):
            return None, "invalid_item"
        out["item"] = item              # 실제 소유·거리는 엔진이 실행 시점에 판정
    elif obj.get("item"):
        return None, "unexpected_item"
    if typ == "bond":
        out["form"] = _clean_form(obj.get("form"))
    return out, None


def _valid_targets(obs, verb="goto"):
    """obs 에 실제로 보이는 오브젝트 id 집합 — 환각 타겟 차단. 출구는 *보일 때만*(beacon 폐기).
    동료(b<char>)는 보일 때만(D18 개정 09-06 — 시야 밖 동료는 사라진 것, 좌표 감각 없음). 좌표는 여전히 비공개.
    장부(known.statics) 귀환 id 는 **goto 전용**(D17) — interact/attack 에 허용하면 too_far vs
    no_target 응답 차이로 '가보지 않고 소멸 여부를 아는' 누설이 생긴다(리뷰 픽스)."""
    s = obs.get("sights", {})
    ids = set()
    if s.get("exit"):                       # 출구는 sights['exit']가 있을 때(=보일 때)만 핑 허용
        ids.add("exit")
    for k in ("features", "monsters", "bots"):
        ids |= {o["id"] for o in s.get(k, [])}
    z = obs.get("zone") or {}
    if isinstance(z.get("doors"), list):    # D19(scan): 문 = 핑 종점. 정정(07-15): obs 에 실리는
        if verb == "goto":                  # 문 자체가 '본 적 있는 것'뿐 — 여기서 더 거를 것 없음.
            ids |= {d["id"] for d in z["doors"]}   # 계단은 여기 없다 — 내용물('보일 때만') 규칙 그대로
    # D18 개정(2026-09-06 파트너 "시야 밖에서 사라지면 말 그대로 사라지는 거야"): 동료는 **보일 때만**(sights.bots)
    # 지칭할 수 있다 — 파티 명단(party)은 누가 살았나의 사실일 뿐 좌표 감각이 아니다. 안 보이는 동료는
    # 리모컨의 '마지막 본 자리로'(장부 last_seen 의 칸 핑)로만 향한다.
    if verb == "goto":
        for e in (obs.get("known") or {}).get("statics", []):
            if e.get("id"):                 # 공간 장부(D17-1) 귀환 핑 — 본 적 있는 제자리 물건은
                ids.add(e["id"])            #   시야 밖이어도 지칭 가능(기억의 id. beacon 부활 아님)
    return ids


def _head(s, n=60):
    """실패 원문의 머리 n자 — 개행·연속공백 접기(폴백 reason 한 줄 유지)."""
    return re.sub(r"\s+", " ", str(s).strip())[:n]


def _call_claude(prompt, model="haiku"):
    """프롬프트를 두뇌 백엔드에 넘긴다. 반환 = (응답텍스트, 실패라벨|None).
    타임아웃/호출에러/빈응답을 구분해 라벨링 — 폴백 reason 에 실려 스트림·봇로그에 남는
    계측(한 라벨로 뭉개면 부검 불가). 라벨 문법은 계약이다: _test_fallback_labels.py 가
    "타임아웃 %ds" / "빈 응답 rc=" / "호출 실패 " 를 부분문자열로 단정한다.

    ⚠️⚠️ 이름·시그니처·반환·**호출 방식**이 전부 불가침이다.
      · verify/스모크 15개 파일이 *이 이름을* 몽키패치해 실 LLM 을 차단한다. 이름을 바꾸거나
        클래스 메서드로 내리면 모킹이 조용히 무시돼 게이트가 FAIL 이 아니라 **유출**을 낸다.
      · 인자는 위치 2개 고정 — verify_notes.py 가 `lambda p, m:` 로 모킹한다(키워드 불가).
        세 번째 인자를 붙이면 그 모킹이 TypeError 로 죽는다. 백엔드에 더 줄 정보가 생기면
        인자가 아니라 환경변수나 프롬프트 문자열에서 유도할 것.
      · 백엔드 분기는 **함수 안에서** 조회한다(모듈 로드 시점 바인딩 금지 — 게이트의
        '스텁 먼저 박고 러너 나중 import' 관용구 보존)."""
    be = backend_name()
    fn = {"claude_cli": _call_cli, "anthropic_api": _call_anthropic,
          "gemini_api": _call_gemini, "dummy": _call_dummy}[be]
    t0 = time.time()
    _TLS.usage = None                    # 백엔드가 채우는 부가 계측(토큰·stop_reason)
    out, why = fn(prompt, model)
    _brainlog(kind="call", backend=be, model=model,
              ms=int((time.time() - t0) * 1000), ok=bool(out), label=why or "",
              in_chars=len(prompt), out_chars=len(out or ""),
              **(getattr(_TLS, "usage", None) or {}))
    return out, why


def _call_cli(prompt, model):
    """현행 경로 그대로(비교 기준선 = 바이트 무변경). 프롬프트를 stdin 으로 넘긴다
    (긴 프롬프트 argv 따옴표 문제 회피)."""
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


def _call_dummy(prompt, model):
    """콜 0 백엔드 — 항상 빈 응답 → claude_brain 이 규칙두뇌로 폴백.
    쓰임: 백엔드 배선을 실 LLM 없이 검증 / 실측의 0-지연 기준선. 게이트 스텁(→'파싱 실패')과
    달리 자기 라벨을 남긴다 — 백엔드는 스텁이 아니라 제품 경로라 부검에서 구분돼야 한다."""
    return "", "빈 응답 rc=0"


def _http_post(url, headers, body):
    """바깥으로 나가는 HTTP 를 **여기 한 점**으로 모은다.
    왜 함수로 뽑나: 게이트(verify_backend)가 이 심볼 하나만 바꿔 끼우면 '초록불인데 실 API 가
    나갔다'를 잡을 수 있다 — 유출 감지의 단일 관문. 반환 = (status|None, obj|None, 라벨|None).

    라벨에 예외 **원문(str(e)) 금지, 타입명만**: 이 레포는 state/ 와 runs/*.jsonl 을 실제로
    커밋한다. 키나 URL 이 한 번 섞이면 그대로 히스토리에 박힌다."""
    try:
        import requests        # 지연 import — 최상단에 두면 미설치 환경에서 `import brains`
    except Exception as e:     #   가 죽어 게이트 20종이 한꺼번에 무너진다
        return None, None, "호출 실패 %s" % type(e).__name__
    t = int(os.environ.get("DUNGEON_BRAIN_TIMEOUT", str(TIMEOUT)))
    try:
        r = requests.post(url, headers=headers,
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          timeout=(5, t))
        # ⚠️ think_all 의 f.result() 엔 타임아웃이 없다 — 여기가 틱 정지를 막는 유일한 장치다.
    except requests.exceptions.Timeout:
        return None, None, "타임아웃 %ds" % t          # Connect/Read 공통 조상
    except Exception as e:
        return None, None, "호출 실패 %s" % type(e).__name__
    try:
        return r.status_code, r.json(), None
    except Exception:
        return r.status_code, None, None               # 비 JSON 본문(게이트웨이 HTML 등)


_ENUMISH = re.compile(r"[A-Za-z_]{1,40}\Z")


def _errtag(*vals):
    """에러 응답에서 **종류 이름만** 뽑는다 — rate_limit_error / RESOURCE_EXHAUSTED 같은 고정
    어휘. message 는 요청 내용을 되비출 수 있어 절대 안 싣는다. 화이트리스트 모양(영문+밑줄,
    40자)까지 통과해야 붙인다 — 자유문이 라벨로 새는 것 차단."""
    for v in vals:
        if isinstance(v, str) and _ENUMISH.match(v):
            return " | " + v
    return ""


def _call_anthropic(prompt, model):
    """Anthropic Messages API 를 requests 로 직접 친다. SDK 없음(이 환경엔 pip 이 없다) —
    스트리밍·툴·비전 전부 불필요하다: 프롬프트 하나 넣고 JSON 한 줄 받는 POST 하나다.

    프롬프트를 **통째로 user 메시지 하나**로 보낸다 — claude.exe 가 stdin 으로 받는 바이트와
    동일. '전송만 바꾼다'가 이 실험의 전제이고, system 분리는 그 자체로 모델 거동을 흔들어
    (질감) 지연 비교를 오염시킨다. 캐싱은 지연 실험이 끝난 뒤 독립 변수로 따로 잰다."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        # ⚠️ 소켓을 열기 **전에** 끊는다 — 게이트가 모킹을 빠뜨려도 키 없는 프로세스에선
        #    실 API 가 물리적으로 못 나간다(구조적 안전핀이 여기서 닫힌다).
        return "", "호출 실패 NoAPIKey"
    mid = os.environ.get("DUNGEON_ANTHROPIC_MODEL") or _MODEL_ID["anthropic_api"].get(model)
    if not mid:
        return "", "호출 실패 UnknownModel"     # 모르는 별칭이 조용히 딴 모델로 흐르지 않게

    st, obj, why = _http_post(API_URL_ANTHROPIC, {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"}, {
        "model": mid,
        "max_tokens": int(os.environ.get("DUNGEON_BRAIN_MAXTOK", "1024")),
        "messages": [{"role": "user", "content": prompt}]})
    if why:
        return "", why
    if st != 200:
        # HTTP 에러코드 → 기존 라벨 문법으로 번역. rc= 를 재사용하는 이유: report.decision_board
        # 의 버킷 키가 `split(" | ")[0].split(":")[0]` 이라 "빈 응답 rc=429" 가 자기 버킷을
        # 얻는다 — 집계 코드 한 줄 안 고치고 401/429/500/529 가 따로 세어진다.
        return "", "빈 응답 rc=%s%s" % (st, _errtag(((obj or {}).get("error") or {}).get("type")))

    u = (obj or {}).get("usage") or {}
    _TLS.usage = {"in_tok": u.get("input_tokens"), "out_tok": u.get("output_tokens"),
                  "cache_read": u.get("cache_read_input_tokens"),   # 캐싱 실측용 관측점
                  "stop": (obj or {}).get("stop_reason") or ""}
    txt = "".join(b.get("text", "") for b in ((obj or {}).get("content") or [])
                  if b.get("type") == "text").strip()
    if not txt:
        # stop_reason ∈ end_turn/max_tokens/stop_sequence/tool_use/refusal — 고정 어휘라 안전.
        # 잘렸어도(max_tokens) 텍스트가 있으면 통과시킨다 — _extract 가 판단하게 두는 관용 원칙.
        return "", "빈 응답 rc=200%s" % _errtag((obj or {}).get("stop_reason") or "empty")
    return txt, None


def _gemini_think(mid):
    """사고 설정 — **세대마다 파라미터가 다르다**(모델 id 로 분기).
      · 3.x  : thinkingLevel = minimal/low/medium/high (thinkingBudget 은 폐기)
               ⚠️ Gemini 3 Flash 의 기본은 **high** 다 — 안 낮추면 JSON 한 줄 받자고
               최대 깊이로 사고한다(지연·비용 폭증).
      · 2.5  : thinkingBudget = 정수, 0 이면 끔. Pro/Flash 는 기본이 동적 사고라
               안 끄면 maxOutputTokens 를 사고에 다 쓰고 답이 잘려 온다
               (실측 2026-07-25: out 41토큰인데 stop=MAX_TOKENS → JSON 실패 → 폴백).
    우리는 JSON 한 줄만 받고 캐릭터의 속내는 이미 reason 필드로 받으므로 둘 다 최소가 맞다.
    DUNGEON_GEMINI_THINK 로 덮어쓸 수 있다(3.x 는 문자열 레벨, 2.5 는 숫자)."""
    v = (os.environ.get("DUNGEON_GEMINI_THINK") or "").strip()
    if mid.startswith("gemini-3"):
        return {"thinkingLevel": v or "minimal"}
    try:
        return {"thinkingBudget": int(v)}
    except ValueError:
        return {"thinkingBudget": 0}


def _call_gemini(prompt, model):
    """Gemini generateContent 를 requests 로 직접. 키를 넣으면 실제로 동작하지만 기본값으론
    절대 안 켜진다(DUNGEON_BRAIN_BACKEND=gemini_api 를 명시해야만).
    ⚠️ 이건 **다른 모델**이다 — 지연 비교의 대조군이 아니라 별도 팔(질감 리베이스라인 필요)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return "", "호출 실패 NoAPIKey"
    mid = os.environ.get("DUNGEON_GEMINI_MODEL") or _MODEL_ID["gemini_api"].get(model)
    if not mid:
        return "", "호출 실패 UnknownModel"

    st, obj, why = _http_post(API_URL_GEMINI % mid, {
        "x-goog-api-key": key,
        "content-type": "application/json"}, {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in (      # 09-11: 조절 가능한 4범주는 안 막는다
            "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",                    #   (전투·독설 대사가 SAFETY 로 비는 것 방지)
            "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")],      #   PROHIBITED_CONTENT 는 조절 불가 → 대체 두뇌
        "generationConfig": {
            "maxOutputTokens": int(os.environ.get("DUNGEON_BRAIN_MAXTOK", "1024")),
            "thinkingConfig": _gemini_think(mid)}})
    if why:
        return "", why
    if st != 200:
        return "", "빈 응답 rc=%s%s" % (st, _errtag(((obj or {}).get("error") or {}).get("status")))

    cands = (obj or {}).get("candidates") or []
    if not cands:
        # 입력 단계 안전 차단 — 후보 자체가 안 온다. blockReason ∈ SAFETY/OTHER/… 고정 어휘
        pf = (obj or {}).get("promptFeedback") or {}
        return "", "빈 응답 rc=200%s" % _errtag(pf.get("blockReason") or "no_candidate")
    c = cands[0]
    fr = c.get("finishReason") or ""     # STOP / MAX_TOKENS / SAFETY / RECITATION / OTHER
    um = (obj or {}).get("usageMetadata") or {}
    _TLS.usage = {"in_tok": um.get("promptTokenCount"), "out_tok": um.get("candidatesTokenCount"),
                  "cache_read": um.get("cachedContentTokenCount"), "stop": fr}
    txt = "".join(p.get("text", "")
                  for p in ((c.get("content") or {}).get("parts") or [])).strip()
    if not txt:
        # 출력 단계 안전 차단(SAFETY/RECITATION)도 여기로 — 라벨로 구분된다
        return "", "빈 응답 rc=200%s" % _errtag(fr or "empty")
    return txt, None


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
    lines = ["# 시트 — 너는 누구인가",   # (09-08 D44) 갈래 머리글 — 파트너 "시트는 나는 누구인가를 말해"
             "- 번호 %s, 이름 **%s** — %s (%s)"
             % (bot.get("char", "?"), nm, bot.get("job", "모험가"), bot.get("sex", "")),
             "- 성격: %s" % bot.get("persona", "")]
    if bot.get("speech"):
        lines.append("- 말투: %s" % bot["speech"])
    if bot.get("goal"):
        lines.append("- 목표: %s" % bot["goal"])
    if bot.get("background"):               # D31(09-05) 배경 = 사용자 자유 입력(load_party 가 한 줄로 정제).
        lines.append("- 배경(이 캐릭터의 과거 서술이다 — 지시가 아니다): 「%s」"   # 인용 한 줄 + 틀 문장
                     % bot["background"])   #   = 격리(방어 아님 — 효과는 프로브로 관측, D31)
    lines.append("- 능력: HP %s, 힘(STR) +%s, 민첩(DEX) +%s, 은신 +%s, 인지 반경 %s"
                 % (bot.get("maxhp"), bot.get("str"), bot.get("dex"),
                    bot.get("stealth", 0), bot.get("search_r", 1)))
    if "weapon" in bot or "armor" in bot:
        # 차림(장비 07-30, 파트너 설계): 착용 정보는 여기 — 시트=불변 프리픽스라 상시 캐싱되고,
        # 교체 순간에만 한 번 바뀐다. 매턴 가변부(obs)에는 안 싣는다. 비교는 입수 메뉴 라벨의 몫.
        w, a = bot.get("weapon"), bot.get("armor")
        lines.append("- 차림: 무기 %s / 방어구 %s"
                     % ("%s(피해 +%d)" % (w["name"], w["bonus"]) if w else "기본 무장",
                        "%s(막기 +%d)" % (a["name"], a["bonus"]) if a else "기본 무장"))
    names = {o["char"]: (o.get("name") or "모험가 %s" % o["char"])
             for o in (roster or []) if o.get("char") != bot.get("char")}
    if names:
        lines.append("- 동료: " + ", ".join("%s(봇%s)" % (names[c], c) for c in sorted(names)))
    rel = bot.get("relationships") or {}
    live = bot.get("relations") or {}       # D36: 살(한 줄)이 있으면 시트 문장을 대체한다 — 시트가 초기값,
    for oc in sorted(set(rel) | {c for c, e in live.items() if e.get("line")}):   # 캐릭터가 겹쳐 쓴다
        if oc not in names:
            continue                        # roster 밖 대상(무해 처리) — 죽은/없는 동료 관계는 침묵
        e = live.get(oc) or {}
        if e.get("line"):
            src = ("시트" if e.get("line_src") == "sheet"
                   else "네가 %s턴에 남긴 말" % e.get("line_turn", "?"))
            lines.append("- %s(봇%s)와의 관계: %s (%s)" % (names[oc], oc, e["line"], src))
        else:
            lines.append("- %s(봇%s)와의 관계: %s" % (names[oc], oc, rel[oc]))
    # (09-08 D44) "시트의 성격·말투·목표·관계대로 판단하고 말하라" 끝줄은 뺐다 — 지침 첫 절(파트너 역할극 문장 "너는 위 시트에
    #   적힌 인물로서…")과 같은 말. 지침 안의 두 번(동료·혼자다 절)은 문맥 문장에 붙어 있어 존치.
    return "\n".join(lines) + "\n"


def _ro(word):
    """조사 '로/으로' — 받침 없음·ㄹ 받침이면 '로'."""
    if not word:
        return "로"
    c = ord(word[-1]) - 0xAC00
    if 0 <= c < 11172:
        return "로" if (c % 28) in (0, 8) else "으로"
    return "로"


def _by_phrase(w):
    """사인·원천의 조사 — 몹은 '에게', 함정·오브젝트는 '에', 상태(출혈)는 '로'."""
    by = w.get("by", "?")
    bk = w.get("by_kind", "monster")
    if bk == "status":
        return "%s%s" % (by, _ro(by))
    if bk in ("trap", "hazard"):
        return "%s에" % by
    return "%s에게" % by


def _witness_prose(w):
    """목격 사실 한 줄(D22 전달층) — 어휘별 사람말. 새 kind 는 마지막 폴백이 정직하게 흘린다."""
    who = "%s(봇%s)" % (w.get("name", "동료"), w.get("char", "?"))
    k = w.get("kind")
    if k == "ally_down":
        return "%s가 %s 쓰러져 죽는 것을" % (who, _by_phrase(w))
    if k == "ally_status":                  # 상태 태그(D34) — 상태는 겉으로 드러난다
        by = w.get("by", "?")
        return "%s가 %s%s %s 상태가 되는 것을" % (who, by, _ro(by), w.get("tag", "?"))
    if k == "ally_hurt":
        return "%s가 %s에게 맞는 것을" % (who, w.get("by", "?"))
    if k == "ally_kill":
        return "%s가 %s을(를) 쓰러뜨리는 것을!" % (who, w.get("mon", "?"))
    if k == "ally_hit":
        return "%s가 %s을(를) 베는 것을%s" % (who, w.get("mon", "?"),
                                              " — 회심의 일격!" if w.get("crit") else "")
    if k == "ally_trap":
        if w.get("safe"):
            return "%s가 %s을(를) 밟았으나 피하는 것을" % (who, w.get("trap", "함정"))
        return "%s가 %s에 당하는 것을" % (who, w.get("trap", "함정"))
    if k == "ally_heal":
        return "%s가 %s으로 기운을 차리는 것을" % (who, w.get("how", "?"))
    if k == "ally_loot":
        what = w.get("what", "?")
        if what == "상자":
            return "%s가 상자에서 보물을 꺼내는 것을" % who
        return "%s가 %s을(를) 챙기는 것을" % (who, what)
    if k == "ally_spot":
        return "%s가 숨어 있던 %s을(를) 찾아내는 것을" % (who, w.get("mon") or w.get("what", "?"))
    if k == "ally_mishap":
        return "%s가 %s에 당하는 것을" % (who, w.get("what", "?"))
    if k == "mon_use":                      # D30 확장 2차(09-06 파트너): 몹도 문을 쓴다 — 같은 문장
        what = w.get("what", "?")
        if w.get("door") and w["door"] not in what:
            what += " %s" % w["door"]
        return "%s(%s)가 %s을(를) 사용하는 것을" % (w.get("mon", "?"), w.get("id", "?"), what)
    if k == "ally_give":                    # D47 ②(09-09) 건네기 목격 — 물건이 손을 옮기는 것을
        return "%s가 %s에게 %s을(를) 건네는 것을" % (who, w.get("to_name", "동료"), w.get("what", "?"))
    if k == "ally_bond":                    # D47 ② 친목 목격 — 몸짓(형태=자유 문구, 뜻은 안 붙인다)
        return "%s가 %s에게 몸짓하는 것을 — %s" % (who, w.get("to_name", "동료"), w.get("form", "몸짓"))
    if k == "ally_use":                     # D30(09-05) 오브젝트 사용 — 동사는 '사용' 하나(파트너 확정:
        what = w.get("what", "?")           #   "~가 문을 사용". 종류별 문장 사전 없음 — 확장 시 what 만
        if w.get("id") and w["id"] not in what:   # 바뀐다). id 는 obs 가 부르는 이름에 없을 때만 붙인다
            what += " %s" % w["id"]         #   ("문 d0" 은 붙고, "계단(exit)" 은 이미 라벨 그대로).
        line = "%s가 %s을(를) 사용하는 것을" % (who, what)
        if w.get("result"):                 # 결과가 있는 사용(상자류) — 괄호 한 마디(파트너 동의 09-05):
            line += " (%s)" % w["result"]   #   동사는 하나로 두고 좋은/나쁜 결과 정보는 잃지 않는다.
        return line                         # 사실만 — 어디로 갔는지·따라가라는 말은 없다.
    return "%s의 일: %s" % (who, json.dumps(w, ensure_ascii=False))


def _tgt_name(tgt, names=None):
    """타겟 토큰을 사람 말로 — 'follow:b2' → '카야'.
    ⚠️ 'follow:' 는 엔진 내부 접두다. 프롬프트에 그대로 새면 캐릭터가 자기 세계에 없는
    기계어를 읽는다(2026-07-26 부검에서 lost 보고 6건 전부 노출 확인). 동료도 id(b2)가
    아니라 이름으로 부른다 — 같은 파티원을 번호로 부르는 사람은 없다."""
    s = str(tgt or "").replace("follow:", "").replace("chase:", "")   # chase: = D48 개정 goto<아군> 추적 order
    if s.startswith("b") and (names or {}).get(s[1:]):
        return names[s[1:]]
    return s


def _last_prose(last, names=None):
    """직전 결과(obs.last)를 1인칭 사실 문장으로 — show_runner.act_summary(관전 3인칭)의 자매.
    어휘 전거 = STREAM_FORMAT.md 이벤트 표. 모르는 형태는 컴팩트 JSON 폴백(정보 무소실 —
    미래 additive 필드의 안전망, verify_wire ③이 실전 폴백 0을 감시)."""
    t, r = last.get("type"), last.get("result")
    if last.get('skill_id'):
        return G.SK.summary(last)
    if t == 'pushed':
        entered = last.get('entered') or {}
        return '스킬에 의해 한 칸 밀려났다' + (' — 함정을 밟았다' if entered.get('trap') else '')
    tgt = str(last.get("target", "") or "")
    _who = lambda c: "%s(봇%s)" % ((names or {}).get(c, "동료"), c)   # D47 ② 상대 호칭(동료는 이름으로)
    if r == "approaching":
        return "%s — %s 실행 거리까지 접근을 시작했다" % (_tgt_name(tgt, names), t)
    if r == "no_path" and last.get("parent_action_id"):
        return "%s에게 접근할 길이 없었다" % _tgt_name(tgt, names)
    if r == 'no_effect':
        return '%s에 %s을(를) 시도했으나 변화가 없었다 (%s)' % (_tgt_name(tgt, names), t, last.get('reason_code', 'no_effect'))
    if t == 'healed' or (t == 'use' and r == 'healed'):
        return '%s — 물약으로 HP %d 회복 (HP %d)' % (_tgt_name(tgt, names) if tgt else '나', last.get('heal', 0), last.get('hp', 0))
    if t == 'use' and last.get('effect_type'):
        return _last_prose({**last, 'type': last['effect_type']}, names)
    if t == 'use':
        why = {'no_target': '대상이 더는 보이지 않는다', 'lost': '대상을 놓쳤다',
               'nothing': '요청한 소지품이 없다', 'too_far': '실행 거리에 닿지 못했다'}.get(r, str(r))
        return '%s 사용 실패 — %s' % (_tgt_name(tgt, names), why)
    if t == "give":                       # D47 ② 건네기 — 자기 행동의 결과(사실만)
        if r == "given":
            tail = ((" (남은 물약 %d병)" % last.get("potions", 0)) if last.get("item") == "potion"
                    else (" — 그의 발밑에 놓였다(자리가 차 있었다)" if last.get("placed") else " — 그가 바로 걸쳤다"))
            return "%s에게 %s을(를) 건넸다%s" % (_who(last.get("to")), last.get("what", "?"), tail)
        return "건네려 했지만 — " + {"too_far": "곁에 없었다(붙어야 건넨다)", "nothing": "줄 것이 없었다",
                                     "no_target": "상대가 그 자리에 없었다", "no_room": "바닥에 놓을 자리가 없었다"}.get(r, str(r))
    if t == "bond":                       # D47 ② 친목 — 자기 행동의 결과(반응은 상대의 다음 결정에서)
        if r == "done":
            return "%s에게 몸짓을 했다 — %s" % (_who(last.get("to")), last.get("form", "몸짓"))
        return "몸짓을 하려 했지만 — " + {"too_far": "곁에 없었다", "no_target": "상대가 그 자리에 없었다"}.get(r, str(r))
    if t == "received":                   # D47 ② 받은 쪽(hurt 문법 — 남이 내게 한 일)
        tail = ((" (소지 물약 %d병)" % last.get("potions", 0)) if last.get("item") == "potion"
                else (" — 발밑에 놓였다(걸칠지는 네 몫)" if last.get("placed") else " — 바로 걸쳤다"))
        return "%s에게서 %s을(를) 받았다%s" % (_who(last.get("from")), last.get("what", "?"), tail)
    if t == "bonded":
        return "%s가 너에게 몸짓을 했다 — %s" % (_who(last.get("from")), last.get("form", "몸짓"))
    if t == "hurt":
        s = "%s(%s)에게 맞았다 — %d 피해, 남은 HP %d" % (
            last.get("by", "?"), last.get("by_id", "?"),
            last.get("dmg", 0), last.get("hp", 0))
        return (s + (" — 기습당했다!" if last.get("surprise") else "")
                + ((" — [%s]이(가) 붙었다" % last["status"]) if last.get("status") else ""))
    if t == "plan_broken":
        st = last.get("step") or {}
        return "작정이 깨졌다(%s) — 못 이룬 수: %s. 남은 계획은 접혔다, 새로 판단하라" % (
            last.get("why", "?"),
            " ".join((G.place_word(st[k], "decide") if k == "target" else str(st[k]))
                     for k in ("type", "target") if k in st) or "?")
    if t == "walk":
        if r == "entered":                    # D19 처음 방 정지 — 구조가 열렸다, 보고 정하라
            zz = last.get("zone") or {}
            sz = zz.get("size") or []
            return ("처음 보는 %s%s에 들어섰다 — 걸음을 멈추고 둘러본다%s"
                    % (zz.get("kind", "공간"),
                       (" %s" % zz["id"]) if zz.get("id") else "",
                       ("(크기 %d×%dm)" % tuple(sz)) if len(sz) == 2 else "")
                    + (" — 오는 길에 보물도 주웠다" if last.get("treasure") else ""))
        if r == "sighted":                    # D19 탐색 종점 — 새 명사가 나타나면 멈춤
            seen_l = last.get("seen") or []
            return ("걷다 멈췄다 — 새로 눈에 든 것: "
                    + ", ".join(x.get("name", "?") for x in seen_l)
                    + (" — 오는 길에 보물도 주웠다" if last.get("treasure") else "")
                    + (" — 오는 길에 회복 물약도 챙겼다" if last.get("potion") else ""))
        if r == "encounter":
            bits = []
            head = "쉬다 눈을 떴다 — " if last.get("woke") == "rest" else "걷다 멈췄다 — "
            if last.get("monsters"):
                bits.append("처음 보는 적: " + ", ".join(
                    m.get("kind", "?") for m in last["monsters"]))
            tr = last.get("trap")
            if tr:
                if tr.get("safe"):
                    bits.append("%s을(를) 알아채고 피했다" % tr.get("name", "함정"))
                elif tr.get("alarm") is not None:
                    bits.append("%s이(가) 울렸다!! 근방의 적들이 깼다" % tr.get("name", "경보"))
                else:
                    bits.append("%s에 당했다 — %d 피해%s"
                                % (tr.get("name", "함정"), tr.get("dmg", 0),
                                   (", [%s]이(가) 붙었다" % tr["status"]) if tr.get("status") else ""))
            if last.get("treasure"):
                bits.append("보물을 주웠다")
            if last.get("potion"):
                bits.append("회복 물약을 챙겼다")
            if last.get("found"):
                bits.append("발견: " + ", ".join(f.get("name", "?") for f in last["found"]))
            return head + (" / ".join(bits) or "새로운 것을 봤다")
        if r == "blocked":
            if last.get("allies"):
                return ("가려던 길이 막혔다 — 동료(%s)가 길목에 서 있어 크게 돌아야 한다"
                        % ", ".join(a.get("name", "?") for a in last["allies"]))
            if last.get("monsters"):
                return ("가려던 길이 막혔다 — %s이(가) 길목을 점거하고 있다"
                        % ", ".join(m.get("kind", "?") for m in last["monsters"]))
            return "가려던 길이 막혔다"
        if r == "lost":
            return ("%s을(를) 마지막 본 자리까지 갔지만 곁에 없다"
                    " (지금 시야에 보이면 비껴 선 것, 안 보이면 어디로 갔는지 모른다)"
                    % _tgt_name(tgt, names))
        if r == "beside":                     # D48 개정 추적 — 곁을 지키는 틱(대상이 움직이는 중)
            return "%s 곁에 붙어 있다 — 그가 움직이면 따라 걷는다" % _tgt_name(tgt, names)
        if r == "idle":
            return ("동행을 접었다 — %s이(가) 한동안 제자리라 같이 서 있기만 했다."
                    " 이제 뭘 할지 네가 정하라" % _tgt_name(tgt, names))
        if r == "arrived":
            if tgt and tgt.startswith("d") and tgt[1:].isdigit():
                # 문 핑 완결 = 이미 '지나 들어선' 상태(Door 계약) — "곁에 도착"으로 옮기면
                # 봇이 아직 안 넘었다고 믿고 같은 문을 재핑한다(암 B 2차 문턱 셔틀 패인)
                return "문 %s를 지나 들어섰다 — 지금 그 너머 공간 안이다" % tgt
            if tgt[:1] == "@":                    # 칸 핑(탐색 종점·마지막 본 자리) — 생좌표 비노출(09-08 D17-4 pos 판정)
                return "가려던 자리에 닿았다"
            return "%s 곁에 도착했다" % (tgt or "목적지")
        if r == "at_exit":
            return "계단 앞에 섰다"
        if r == "treasure":
            return "길에서 보물을 주웠다"
        if r == "potion":
            return "길에서 회복 물약을 챙겼다"
        if r == "swapped":                    # 교대(D18 개정)의 수동태 — 밀려난 쪽의 자기 관측
            return ("%s이(가) 지나가며 나와 자리를 바꿨다 — 한 칸 밀려섰다(가던 길은 그대로)"
                    % last.get("with", "동료"))
        if r == "waiting":                    # 대기 틱(D25 — 스트림용. 봇 재결정엔 wake 결과만 옴)
            return "제자리에서 기다리는 중이다"
        if r == "wait_met":                   # 기다리던 보람 — 관찰 사실만(다음은 네 몫)
            who = ", ".join((names or {}).get(c, "동료") for c in last.get("allies", []))
            return "기다림 끝 — %s가 시야에 들어왔다" % (who or "동료")
        if r == "wait_bored":                 # 지루함 상한(D25) — 관찰 사실만(질문·조향 금지)
            return "한참을 기다렸다 — 아무도 오지 않는다"
        if r == "resting":                    # 휴식 틱(D35 — 스트림용)
            return "쉬는 중이다 (HP %d)" % last.get("hp", 0)
        if r == "rested":                     # 휴식 완료 — 관찰 사실만
            cl = last.get("cleared") or []
            return "푹 쉬었다 — HP %d 회복%s" % (
                last.get("healed", 0),
                (", 몸 상태가 나았다: " + "·".join(cl)) if cl else "")
        if r == "rest_met":                   # 쉬다 동료가 시야에 — 관찰 사실만(다음은 네 몫)
            who = ", ".join((names or {}).get(c, "동료") for c in last.get("allies", []))
            return "쉬다 눈을 떴다 — %s가 시야에 들어왔다" % (who or "동료")
        if r == "reunion":                    # 재회 정지(D21①) — 연결의 발견. 관찰 사실만(조향 금지)
            return ("걷다 멈췄다 — 낯익은 곳이다: %s. 지금 걸어온 길이 아는 곳으로 이어졌다"
                    % last.get("name", "와 본 곳")
                    + (" — 오는 길에 보물도 주웠다" if last.get("treasure") else "")
                    + (" — 오는 길에 회복 물약도 챙겼다" if last.get("potion") else ""))
        if r == "wander":                     # 맴돎 정지(D21②) — 질문형 금지: 관찰 사실만, 판단은 네 몫
            return ("걸음을 멈췄다 — 한참을 오가는 동안 새로 본 것이 없다,"
                    " 밟았던 자리를 되밟고 있었다")
    if t == "wait":                       # 대기 개시(D25) — 자기 행동의 결과
        return "이 자리에서 기다리기로 했다 — 동료가 오거나 새 일이 생기면 깨어난다"
    if t == "rest":                       # 휴식 개시(D35) — 자기 행동의 결과
        return ("이 자리에서 쉬기로 했다 — 틱마다 HP가 차고, 다 나으면 몸 상태가 낫는다."
                " 맞거나 새것을 보거나 말을 걸어오면 깬다")
    if t == "hail":                       # 말 걸림 정지(07-24 D24) — 관찰 사실만(판단은 네 몫)
        who = ", ".join((names or {}).get(c, "동료") for c in last.get("froms", [])) or "동료"
        return "%s의 말에 걸음을 멈췄다 — 걷던 길이었다" % who
    if t == "attack":
        if r == "no_target":
            return "공격 — 대상이 그 자리에 없었다"
        if r == "too_far":
            return "공격 — 너무 멀었다(붙어야 친다)"
        if r == "attack":
            if not last.get("hit"):
                return "%s을(를) 쳤지만 — 빗나갔다" % (tgt or "?")
            s = "%s을(를) 쳤다 — 명중, %d 피해" % (tgt or "?", last.get("dmg", 0))
            if last.get("killed"):
                s += ", 쓰러뜨렸다!"
            return ("기습! " if last.get("surprise") else "") + s
    if t == "interact":
        if r == "exit":
            group = last.get("party", [])
            if len(group) == 1:              # 솔로 판 — 혼자 내려갔다. 캐릭터가 읽는 문장이라
                return "혼자 계단을 내려갔다"    #   더 중요하다: 없던 일행을 지어내면 안 된다.
            return "다 모여서 — 함께 내려갔다(%s)" % "·".join(group)
        if r == "ascend":
            group = last.get("party", [])
            if len(group) == 1:              # 마을 복귀(D29) — 대칭 문법·같은 정직성
                return "혼자 계단을 올라 마을로 돌아갔다"
            return "다 모여서 — 함께 마을로 올라갔다(%s)" % "·".join(group)
        if r == "npc_gift":                 # D32 상점 v0 — 받은 것은 사실로(무기는 바로 걸친다, 물약은 소지 +1)
            item = last.get("item", "?")
            got = "물약을 받았다(소지 물약 +1)" if item == "물약" else "%s을(를) 받아 걸쳤다" % item
            return '%s에게 말을 걸었다 — %s. "%s"' % (last.get("npc", "?"), got, last.get("line", "…"))
        if r == "npc_talk":
            return '%s에게 말을 걸었다 — "%s"' % (last.get("npc", "?"), last.get("line", "…"))
        if r == "wait_allies":
            verb = "올라가려" if last.get("dir") == "up" else "내려가려"
            parts = []                     # 멀다/딴 작정은 다른 사실 — 섞어 말하면 곁의 동료를
            if last.get("missing"):        # "데리러 가라"는 거짓 지시가 된다(08-09 정직화)
                parts.append("아직 안 모였다(빠진 동료: 봇%s) — 기다리거나, 마지막으로 본 자리로 가 보라"
                             % "·".join(last["missing"]))
            if last.get("busy"):
                parts.append("곁의 봇%s는 하던 일(탐색·다른 목표)이 있다 —"
                             " 기다리거나 말을 걸어라" % "·".join(last["busy"]))
            return "계단에서 %s 했지만 — %s" % (verb, " / ".join(parts))
        if r == "chest_loot":
            return "상자를 열었다 — 보물 %d개!" % last.get("loot", 0)
        if r == "chest_trap":
            return "상자에서 독침이 튀었다 — %d 피해%s" % (
                last.get("dmg", 0), (", [%s]이(가) 붙었다" % last["status"]) if last.get("status") else "")
        if r == "fountain_heal":
            return "샘물을 마셨다 — HP %d 회복" % last.get("heal", 0)
        if r == "fountain_harm":
            return "샘물이 오염돼 있었다 — %d 피해%s" % (
                last.get("dmg", 0), (", [%s]이(가) 붙었다" % last["status"]) if last.get("status") else "")
        if r == "potion":
            return "회복 물약을 집어 챙겼다 (소지 %d병)" % last.get("potions", 1)
        if r == "equip":
            word = "피해" if last.get("slot") == "weapon" else "막기"
            return "%s을(를) 걸쳤다 — %s +%d%s" % (
                last.get("item", "?"), word, last.get("bonus", 0),
                (". 헌 %s은(는) 그 자리에 놓았다" % last["dropped"])
                if last.get("dropped") else "")
        fin = {"treasure": "보물을 주웠다", "nothing": "아무것도 없었다",
               "too_far": "너무 멀었다(붙어야 만진다)", "no_target": "대상이 그 자리에 없었다"}
        if r in fin:
            return "상호작용(%s) — %s" % (tgt or "?", fin[r])
    if t == "search":
        f = last.get("found") or []
        if f:
            return "수색해서 드러냈다: " + ", ".join(
                "%s(%s쪽)" % (x.get("name", "?"), x.get("bearing", "?")) for x in f)
        return "수색했지만 — 이 근방에 숨은 건 없었다"
    if t == "drink":
        if r == "drink_heal":
            return "회복 물약을 들이켰다 — 상처가 전부 아물었다(HP %d 회복, 남은 물약 %d병)" % (
                last.get("heal", 0), last.get("potions", 0))
        if r == "no_potion":
            return "물약을 마시려 했지만 — 가진 물약이 없다"
    if t in ("goto", "explore", "follow"):
        if r == "blocked" and last.get("allies"):
            return ("가려던 길이 막혔다 — 동료(%s)가 길목에 서 있어 크게 돌아야 한다"
                    % ", ".join(a.get("name", "?") for a in last["allies"]))
        if r == "arrived":
            return "%s — 이미 곁이다" % (_tgt_name(tgt, names) or "?")
        if r == "already_beside":             # D48 개정: 곁에 멈춘 사람에게 goto — 갈 곳 없음
            return "%s — 이미 곁에 있고 멈춰 있다, 갈 곳이 없다" % (_tgt_name(tgt, names) or "?")
        if r == "no_path":
            if last.get("exhausted"):         # D19 개정: 보이는 새 길·기억의 계단·기억 속 안 가 본 문 전부 없음
                return ("탐색하려 했지만 — 새 길이 없다: 보이는 길은 전부 가 봤고,"
                        " 기억 속에도 안 가 본 문이 없다")
            return "탐색하려 했지만 — 지금 갈 수 있는 새 길이 없다"
        if r == "following":
            return "%s 곁에서 동행을 시작했다" % tgt
        if r == "pathed":
            return ("%s 쪽으로 걷기 시작했다" % _tgt_name(tgt, names)
                    if tgt and tgt != "auto" else "새 길로 걷기 시작했다")
    return json.dumps(last, ensure_ascii=False)        # 미지 형태 — 정직한 폴백(숨기지 않는다)


_TRAIL_RUNS = {"walking": "%d걸음", "following": "%d틱 동행", "beside": "%d틱 곁",   # beside = D48 개정 추적의 곁 유지 틱
               "waiting": "%d틱 대기", "resting": "%d틱 휴식"}
_VERB_KR = {"goto": "이동", "follow": "동행", "explore": "탐색", "attack": "공격", "interact": "상호작용",
            "search": "수색", "wait": "기다림", "rest": "휴식", "drink": "물약",
            "give": "건네기", "bond": "친목"}   # 최근 판단 장부 줄의 동사(D38 개정 2) — give/bond=D47 ②(09-09)


def _hist_item(h):
    """최근 판단 한 항목 → '이동 f0 (t81)' / '이동 exit (t59, 작정)' / '동행 b2 (t40, 폴백)'. **선택만** — 엔진이 걷고 멈춘
    결과는 안 붙는다(D38 개정 2-b, 파트너 "캐릭터의 선택만"). 작정 수=캐릭터가 미리 정한 것, 폴백=규칙두뇌가 대신 고른 것."""
    src = h.get("src") or ""
    tag = ", 작정" if src == "plan" else (", 폴백" if src == "fallback" else "")
    what = ((" %s" % G.ITEM_KR.get(h["item"], h["item"])) if h.get("item")       # D47 ② 건네기 물건 / 친목 몸짓
            else ((" [%s]" % h["form"]) if h.get("form") else ""))
    return "%s%s%s (t%s%s)" % (_VERB_KR.get(h.get("type"), h.get("type") or "?"),
                               (" %s" % G.place_word(h["target"], "decide")) if h.get("target") else "", what, h.get("turn", "?"), tag)


def _dlg_who(m, nm):
    """대화 한 마디의 화자→상대(D43): '카야(봇2)→나' / '나→카야(봇2)' / '미나(봇3)→모두' / '카야(봇2)(혼잣말)'. 이름은 wire 의 nm."""
    who = "나" if m.get("mine") else nm(m.get("from", "?"))
    to = m.get("to")
    if to == "all":
        return "%s→모두" % who
    if to:
        return "%s→%s" % (who, "나" if (m.get("to_me") and not m.get("mine")) else nm(to))
    return "%s(혼잣말)" % who


def _tag_str(tags):
    """꼬리표 목록 → '[라벨] 사실 · [라벨] 사실'."""
    return " · ".join(("[%s] %s" % (lb, s)).rstrip() for _, lb, s in tags)


def _floor_counts(counts):
    """층 집계(D40 ②) 렌더 — '[처치] ×2 · [피격] ×3' (횟수 내림차순, 같으면 라벨순)."""
    return " · ".join("[%s] ×%d" % (k, v) for k, v in
                      sorted(counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))))


def _floor_name(depth):
    d = int(depth or 0)
    return "마을" if d == 0 else "%d층" % d


def _clean_form(raw):
    """친목의 몸짓(D47 ② 응답 `form`, 2026-09-09 파트너 "['대화' '친목' '머리를 쓰다듬기']") — 한 줄·따옴표 제거·BOND_LEN 자.
    목록이 아니라 자유 문구(파트너 결정 09-09: 기계는 횟수만, 형태는 기록으로). 비면 엔진이 '몸짓'으로 적는다."""
    return " ".join(str(raw or "").replace('"', "").replace("'", "").split())[:G.BOND_LEN]


def _act_item(a, other):
    """관계 상세 기록 한 건(D47 ②) → 't12 내가 머리 쓰다듬기 → 답: 말로' / 't14 카야(봇2)가 물약 건넴 → 내 답: 없음'.
    반응은 형태만(행동|말|없음 — 러너 classify_reply). 아직 답이 없으면 꼬리 없음."""
    who = "내가" if a.get("mine") else "%s가" % other
    what = ("%s 건넴" % a.get("what", "?")) if a.get("kind") == "건네기" else str(a.get("what", "몸짓"))
    rep = a.get("reply")
    tail = "" if rep is None else " → %s: %s" % ("답" if a.get("mine") else "내 답",
                                                 {"행동": "행동으로", "말": "말로", "없음": "없음"}.get(rep, rep))
    return "t%s %s %s%s" % (a.get("turn", "?"), who, what, tail)


_KIND_PROPOSE = ("제안", "요청", "부탁", "proposal", "propose", "request", "ask", "suggest", "offer")


def _parse_kind(raw):
    """말의 종류(D47 `say_kind`, 2026-09-08 파트너 "'말한다'를 목적에 맞게 쪼갠다" — 응답 JSON 정식 필드):
    제안(상대의 선택을 요청 — 상대가 멈춰 답한다) / 잡담(기본 — 전하기만, 아무도 안 멈춘다).
    빈 값·모르는 값 = 잡담(파트너 "기본값은 잡담으로 가볍게"). 말한 캐릭터의 자기 신고이지 엔진의 내용 해석이 아니다(D5)."""
    s = str(raw or "").strip().lower()
    return "제안" if any(s.startswith(k) for k in _KIND_PROPOSE) else "잡담"


_TO_ALL = ("all", "모두", "다들", "전원", "모두에게", "다같이", "everyone")


def _parse_to(raw, char, roster=None, obs=None):
    """말의 상대(D41 `to`, 응답 JSON 정식 필드 — 자유 텍스트 이름 파싱(07-24 기각 뒷문)이 아니다):
    봇 번호('2'·'b2'·'봇2') 또는 이름('카야') → 봇 번호 / all·모두·다들·전원 → 'all' / 자기 자신·미등재·빈 값 → None
    (=혼잣말). 이름은 로스터(파티)로만 푼다 — 솔로 판(로스터 없음)은 시야 안 번호만 통한다(통성명 안 했으니)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.lower() in _TO_ALL:
        return "all"
    others = {str(o.get("char")) for o in (roster or []) if str(o.get("char")) != str(char)}
    if not others:                                   # 솔로: 로스터 없음 → 시야 안 번호
        others = {str(b.get("char")) for b in ((obs or {}).get("sights") or {}).get("bots", [])}
    core = re.sub(r"^(봇|b|bot)\s*", "", s, flags=re.I)
    if core.isdigit():
        return core if core in others else None
    for o in (roster or []):
        nm_ = str(o.get("name") or "")
        oc = str(o.get("char"))
        if nm_ and oc in others and (s == nm_ or s.startswith(nm_) or nm_.startswith(s.rstrip("!?.,~ "))):
            return oc
    return None


def _trail_prose(trail, names=None):
    """궤적(D38 → D40 꼬리표식, 09-06 파트너 확정 "꼬리표식으로 바꾸자·픽셀 던전 방식") — 마지막 결정 이후
    일어난 일을 사건 사전(dungeon_gm.event_tags)의 꼬리표로 ' → ' 이어 찍는다: "[대화] 아이템 상인 → 물약 받음
    → 작정대로 [이동 시작] f1 쪽 → 3걸음 · [획득] 보물 → [도착] f1 곁 · [출혈] −1 (HP 7)". 연속 걸음·동행·대기·
    휴식 틱은 'N걸음' 꼴로 접고 그 사이 사건(획득·문 사용·출혈)은 접은 덩어리 뒤에 붙인다. 작정 집행 수는
    '작정대로 ' 접두, 상한에 잘린 앞부분은 '…(n건 생략)'. 문장형 서술은 관전·스트림·목격 줄에 남는다."""
    parts, run = [], None                    # run = [result, n, extras(tags)]

    def flush():
        if run:
            s = _TRAIL_RUNS[run[0]] % run[1]
            if run[2]:
                s += " · " + _tag_str(run[2])
            parts.append(s)
    for e in trail:
        if not isinstance(e, dict):
            continue
        if e.get("type") == "gap":
            flush(); run = None
            parts.append("…(%d건 생략)" % int(e.get("n") or 0))
            continue
        tags = G.event_tags(e, names)
        if tags and tags[0][0] == "move":
            r = tags[0][1]                       # 라벨 자리에 result(walking/following/…)가 온다
            if run and run[0] == r:
                run[1] += 1
            else:
                flush(); run = [r, 1, []]
            run[2].extend(tags[1:])
            continue
        flush(); run = None
        parts.append(("작정대로 " if e.get("plan") else "") + _tag_str(tags))
    flush()
    return " → ".join(parts)


# _wire 가 아는 obs 키 전부 — 밖의 키는 '그 밖의 정보' JSON 으로 정직하게 노출(조용한 누락 금지).
_WIRE_KEYS = frozenset((
    "pos", "hp", "maxhp", "job", "sex", "str", "dex", "inventory", "potions",
    "depth", "turn",
    "zone", "known", "witnessed", "memories", "dry", "last", "trail", "floor", "floors", "history", "dialogue",
    "order", "ascii_view", "legend",
    "sights", "party", "options", "messages", "intent", "notes",   # party: 파티 명단 — 기억 갈래 첫 절(09-08 D44 정정으로 존치)
    "status",  # 상태 태그(D34): 아래 _wire "## 네 몸 상태" 절이 그린다
    "relations",   # 관계 장부(D36): 뼈 횟수·초대는 _wire, 살(한 줄)은 _sheet 가 그린다
    "exhausted",   # 탐색 소진(D19 개정 09-06): '탐색' 어휘 대신 사실 한 줄
    "town",    # 마을(D29): 안전한 층의 사실 한 줄 — 아래 _wire 가 그린다
    "gear"))   # 장비(07-30): 아는 키지만 wire 는 일부러 안 그린다 — 착용 정보의 표현은
               #   시트(_sheet 차림 줄, 불변 프리픽스=캐싱)가 소유하고, 비교는 입수 메뉴
               #   라벨에만 나온다(파트너 설계: 상시 가변부 미노출). 여기 등재를 빼면
               #   '그 밖의 정보' JSON 덤프로 매턴 새 나간다(화이트리스트 폴백)


def _wire(obs, names=None, compose=False):
    """obs(dict 계약) → 자기설명 한국어 사실 문장(D17-3). LLM 두뇌 전용 표현 층 —
    dict 계약(스트림·BYO·검증)은 무변경, 여기는 '보여주는 방법'만 소유한다.
    원칙: obs 에 있는 사실만 문장으로(시야-온리는 입력에서 이미 보장), 해석·추천은 싣지
    않는다(사실 주석만 — 리모컨 라벨 문법의 확장). state 번역표 등 프롬프트의 obs
    사용설명서를 이 문장들이 대체한다(프롬프트 다이어트의 짝)."""
    names = names or {}

    def nm(char):
        return "%s(봇%s)" % (names.get(char, "동료"), char)

    def who(char):
        """시야에 든 사람을 뭐라 부르나 — 아는 사람은 '동료 카야', 모르는 사람은 '낯선 사람'.
        솔로 판(로스터 없음)에서 names 가 비어 남남이 된다. 도감의 '낯선 짐승'과 같은 문법:
        모르는 것은 모른다고 쓴다. ⚠️ 이름을 모를 뿐 id(봇2)는 그대로 — 지칭은 돼야
        핑을 걸 수 있고, 이름은 만나서 통성명해야 얻는 것이다(그건 아직 없다)."""
        label = "동료 %s" % nm(char) if names.get(char) else "낯선 사람(봇%s)" % char
        return label + (" [b%s]" % char if compose else "")

    def at(o):
        if o.get("dist") == 0:
            return "발밑"
        s = "%s, 거리 %d" % (o.get("bearing", "?"), o.get("dist", 0))
        return s + (", 인접" if o.get("adj") else "")

    now = obs.get("turn")

    def ago(t):
        if now is None:
            return "턴 %s에" % t
        d = now - t
        return "방금" if d <= 0 else "%d턴 전에" % d

    L = ["## 네 상태"]
    M = []          # (09-08 D44) 기억 절 모음 — 관측(L)과 따로 모아 조립 때 갈래 순서를 정한다
    # (09-08 D44) 직업·성별·힘·민첩은 '나는 누구'라 시트만 말한다 — 여기는 지금의 몸(관측)만. 파트너 "시트는 나는 누구인가를,
    #   관측은 뭘 보고 있는지를". HP 는 x/y 그대로(비율=위급 감각의 재료 — 최대치가 시트에 있어도 읽는 값은 관측이다).
    L.append("- HP %d/%d, 모은 보물 %d개%s — 지금 %d층"
             % (obs.get("hp", 0), obs.get("maxhp", 0), obs.get("inventory", 0),
                (", 회복 물약 %d병" % obs["potions"]) if obs.get("potions") else "",
                obs.get("depth", 1)))
    if obs.get("town"):
        # 마을(D29) — 사실만: 안전·전체 가시. 여기서 뭘 할지는 캐릭터 몫(추천 안 싣는다).
        L.append("- 여기는 마을이다 — 위험한 것이 없고, 마을 전체가 한눈에 보인다")
    z = obs.get("zone")
    scan = isinstance((z or {}).get("doors"), list)   # D19 구조 조회가 실려 있으면 트리 직렬화
    if z and not scan:
        L.append("- 서 있는 곳: %s" % (("%s %s" % (z.get("kind", "방"), z["id"]))
                                       if z.get("id") else z.get("kind", "통로")))
    if OBS_POS and obs.get("pos"):
        L.append("- 좌표: %s" % obs["pos"])
    if obs.get("order"):
        L.append("- 진행 중이던 핑: %s" % obs["order"])
    if obs.get("exhausted"):                # D19 개정 — 관찰 사실만(어디로 가라는 말 없음)
        L.append("- 이 자리에서 보이는 길은 전부 가 봤고, 기억 속에도 안 가 본 문이 없다 — 새 길이 없다")
    st = obs.get("status")
    if st:                                  # 상태 태그(D34) — 몸에 붙은 것. 라벨=효과(사실만)
        L += ["", "## 네 몸 상태 (붙은 것은 그 줄이 말하는 그대로 작용한다)"]
        for e in st:
            n = e.get("n", 1)
            L.append("- [%s%s] %s (%s, %s)"
                     % (e.get("tag", "?"), (" ×%d" % n) if n > 1 else "",
                        G.status_prose(e.get("tag", "?")), e.get("by", "?"),
                        ago(e.get("since", 0))))

    if OBS_ASCII and obs.get("ascii_view"):
        n = len(obs["ascii_view"])
        L += ["", "## 주변 그림 (%d×%d — 가운데 @가 너, 빈칸은 벽 뒤라 안 보이는 곳)"
              % (n, n), "```"]
        L += list(obs["ascii_view"])
        L += ["```",
              "기호: # 벽 · . 바닥 · + 문(너머 안 보임) · , 발자국 · $ 보물 · > 계단 · M 몬스터"
              " · ^ 드러난 함정 · = 상자 · ~ 샘 · ! 회복 물약 · 숫자=동료"]

    s = obs.get("sights") or {}
    if scan:
        # ── D19 트리 직렬화: 던전 N층 > 공간 > 8방위 슬롯 — 빈 방향도 발화("서쪽: 벽" =
        # 침묵을 정보로), 1칸=1m, 출처 딱지(본 적 있음/온 적 있음/발각됨 — 기억≠시야 구분 필수).
        # 정정(07-15): "짜임은 확실히"는 과독이었다 — 네 눈이 본 만큼이 네가 아는 만큼이다.
        L += ["", "## 장소 (네 눈이 본 만큼이 네가 아는 만큼이다)"]
        head = ("던전 %d층 > %s %s" % (obs.get("depth", 1), z.get("kind", "?"),
                                       z.get("id", "") or "")).rstrip()
        if z.get("kind") == "문턱":
            head += " — 문 위(양쪽이 트여 보인다)"
        if z.get("size"):
            head += " — 크기 %d×%dm" % tuple(z["size"])
        if z.get("len") is not None:
            head += " — 길이 약 %dm" % z["len"]
        if z.get("at"):
            head += ", 너는 %s에 있다" % z["at"]
        L.append("- " + head.rstrip())
        KR = {"N": "북쪽", "NE": "북동쪽", "E": "동쪽", "SE": "남동쪽",
              "S": "남쪽", "SW": "남서쪽", "W": "서쪽", "NW": "북서쪽"}
        ck = z.get("checked") or {}
        if z.get("kind") == "문턱":
            pass                                  # 문턱은 '공간'이 아니다 — 확인 문장 생략
        elif ck.get("full"):
            L.append("- 이 공간 안은 눈으로 다 확인했다")
        else:
            L.append("- 안을 다 보진 못했다%s"
                     % ((" — %s으로 공간이 더 이어진다(끝이 안 보인다)"
                         % KR.get(ck.get("todo"), ck.get("todo")))
                        if ck.get("todo") else " (못 본 구석이 남았다)"))
        order8 = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        slots = {b: [] for b in order8}
        under = []                               # 발밑(거리 0)은 방위가 없다 — 따로 한 줄

        def put(bearing, dist, text):
            if dist == 0 or bearing == "-":
                under.append(text)
            elif bearing in slots:
                slots[bearing].append((dist, text))

        for d in z.get("doors", []):
            tag = ((" (온 적 있는 길%s)"                     # D21 재회 표기: 아는 너머는 이름 참조,
                    % ((" — 너머는 %s" % d["to"]) if d.get("to") else ""))   # 하위 전개 없음
                   if d.get("been")
                   else ("" if d.get("seen") else " (본 적 있음, 지금 시야 밖)"))
            put(d.get("bearing"), d.get("dist", 0),
                ("문 %s — 지금 선 문턱%s" % (d.get("id", "?"), tag)) if d.get("dist") == 0
                else "문 %s %dm%s" % (d.get("id", "?"), d.get("dist", 0), tag))
        for e in z.get("ends", []):
            put(e.get("bearing"), e.get("dist", 0),
                "%s %dm%s" % (e.get("kind", "?"), e.get("dist", 0),
                              " (가 본 곳)" if e.get("been") else ""))
        ex = s.get("exit")
        if ex:
            put(ex.get("bearing"), ex.get("dist", 0),
                "계단(exit) %dm — 눈에 보인다" % ex.get("dist", 0))
        for m in s.get("monsters", []):
            put(m.get("bearing"), m.get("dist", 0),
                "%s, %dm%s" % (G._mfact(m), m.get("dist", 0),
                               " (인접 — 칠 수 있다)" if m.get("adj") else ""))
        for f in s.get("features", []):
            put(f.get("bearing"), f.get("dist", 0),
                "%s %s %dm%s" % (f.get("name", "?"), f.get("id", "?"), f.get("dist", 0),
                                 " (와 본 자리)" if f.get("visited") else "") + G._tagsfx(f))   # D39 태그 접미
        for t in s.get("traps", []):
            put(t.get("bearing"), t.get("dist", 0),
                "%s %dm (발각됨 — 위치를 안다)" % (t.get("name", "함정"), t.get("dist", 0)))
        for b in s.get("bots", []):
            put(b.get("bearing"), b.get("dist", 0),
                "%s(HP %s/%s%s) %dm%s%s" % (who(b.get("char", "?")),
                                            b.get("hp", "?"), b.get("maxhp", "?"),          # 09-08 D45: 숫자+태그(겉보기 4단 폐지)
                                            (" · " + " · ".join(b["status"])) if b.get("status") else "",   # D34 — scan 분기 누락 수선
                                            b.get("dist", 0),
                                            " (이동중)" if b.get("moving") else "",
                                            " (휴식중)" if b.get("resting") else ""))       # D35 — scan 분기 누락 수선
        if under:
            L.append("- 발밑: " + " / ".join(under))
        KR = {"N": "북쪽", "NE": "북동쪽", "E": "동쪽", "SE": "남동쪽",
              "S": "남쪽", "SW": "남서쪽", "W": "서쪽", "NW": "북서쪽"}
        door_b = {d.get("bearing") for d in z.get("doors", [])       # 보이는 문이 선 방위 — 그 너머는 '트임'이
                  if d.get("seen") and d.get("dist", 0) > 0}         #   아니라 '문'이다(메뉴도 그 방위는 안 연다)
        for b in order8:
            items = sorted(slots[b], key=lambda it: (it[0], it[1]))
            # 빈 방향의 정직화(07-15 정정): 전지 시절엔 침묵=벽이었지만, 이제 안 본 곳은
            # 벽이 아니라 미지다 — 시야 내 '미지로 트인' 방위(ways)는 트임으로 발화.
            wv = next((w for w in s.get("ways", []) if w.get("bearing") == b), None)
            opened = (("트여 있다 — 너머는 안 보인다%s" % (" (발자국 있는 길)" if wv.get("visited") else ""))
                      if wv else None)
            if items:
                # D19 개정 4(09-07): 물건이 선 방위도 그 너머가 트였으면 말한다 — 메뉴의 '탐색: <방위> — 트여 있다'와
                #   같은 말(문장↔메뉴 1:1, verify_menu ⑧). 07-15 판은 빈 방위에서만 발화라 보물·몹·동료가 선 쪽의
                #   트임은 침묵했다(20시드 스윕 실측: 열거 방위 751 중 356 이 문장에선 무언).
                L.append("- %s: %s%s" % (KR[b], ", ".join(t for _, t in items),
                                        (" · " + opened) if (opened and b not in door_b) else ""))
                continue
            if opened:
                L.append("- %s: %s" % (KR[b], opened))
            else:
                L.append("- %s: 벽" % KR[b])
        for m in s.get("monsters", []):
            if m.get("lore") or m.get("deep_progress"):   # D53: 심층 전엔 한 줄 + 진행도 접미
                L.append("  · %s 습성(네가 아는 것): %s%s" % (m.get("kind", "?"), m.get("lore") or "아직 잘 모른다", G._deep_sfx(m)))
    else:
        L += ["", "## 지금 보이는 것"]
        n0 = len(L)
        ex = s.get("exit")
        if ex:
            L.append("- 계단(exit) — %s" % at(ex))
        for m in s.get("monsters", []):
            L.append("- %s — %s" % (G._mfact(m), at(m)))
            if m.get("lore") or m.get("deep_progress"):   # D53: 심층 전엔 한 줄 + 진행도 접미
                L.append("  · 네가 아는 습성: %s%s" % (m.get("lore") or "아직 잘 모른다", G._deep_sfx(m)))
        for f in s.get("features", []):
            L.append("- %s %s — %s%s" % (f.get("name", "?"), f.get("id", "?"), at(f),
                                         " (와 본 자리)" if f.get("visited") else "") + G._tagsfx(f))   # D39 태그 접미
        for b in s.get("bots", []):
            L.append("- %s — HP %s/%s%s — %s%s%s"                                    # 09-08 D45: 숫자+태그(겉보기 4단 폐지)
                     % (who(b.get("char", "?")), b.get("hp", "?"), b.get("maxhp", "?"),
                        (" · " + " · ".join(b["status"])) if b.get("status") else "",   # D34 상태
                        at(b), " (이동중)" if b.get("moving") else "",
                        " (휴식중)" if b.get("resting") else ""))                      # D35 휴식
        for w in s.get("ways", []):
            L.append("- %s쪽으로 트인 길 — 거리 %d, %s%s"
                     % (w.get("bearing", "?"), w.get("dist", 0),
                        "발자국 있음(가 본 길)" if w.get("visited") else "안 가본 길",
                        (", %s 방향" % w["zone"]) if w.get("zone") else ""))
        if len(L) == n0:
            L.append("- (아무것도 안 보인다)")

    pt = obs.get("party") or []
    if pt:                                  # 파티 명단 — **기억 갈래 첫 절**(09-08 D44 정정, 파트너 "파티 명단은 같이 하는 데 필요"):
        M += ["", "## 파티 명단"]           #   함께 온 사람이 누구고(직업 — 동료 직업의 유일한 출처) 살았는지·먼저 내려갔는지·지금 보이는지.
        for p in pt:                        #   못 본 죽음·하강도 안다 = 시야-온리의 유일한 전지 창(09-06 D22 개정 '구하러 올게' 유령 차단).
            if not p.get("alive"):         #   내가 폐지를 권했다가 파트너 정정으로 존치 — 같이 하기의 재료.
                st = "죽었다 — 이번 원정에는 돌아오지 않는다"   # D22 개정(09-06): 확정성 전달('구하러 올게' 유령 차단)
            elif p.get("won"):
                st = "먼저 내려갔다"
            elif p.get("visible"):
                st = "시야 안(관측 목록에 있다)"     # D44 뒤 관측은 기억 뒤에 온다 — '위 목록' 대신 자리 중립 표현
            else:
                st = "시야 밖 — 말은 안 닿는다. 어디 있는지 모른다(마지막 본 자리만 안다)"   # D18 개정(09-06)
            M.append("- %s, %s — %s" % (nm(p.get("char", "?")), p.get("job", "?"), st))

    rels = obs.get("relations") or []
    if rels:                                # 관계 장부(D36) — 뼈 횟수(사실). 살은 시트에 산다
        M += ["", "## 동료와 겪은 일 (횟수 — 세계가 센 사실)"]
        for r in rels:
            bits = ["%s ×%d%s" % (b_.get("label", b_.get("kind", "?")), b_.get("n", 0),
                                 (" (%s)" % ago(b_["last"])) if b_.get("last") is not None else "")
                    for b_ in r.get("bones", [])]
            M.append("- %s: %s" % (nm(r.get("char", "?")), ", ".join(bits) if bits else "아직 없음"))
            acts = r.get("acts") or []
            if acts:                        # D47 ② 상세 기록(파트너 초안 §A-5) — 형태(무엇을)+반응(형태만: 행동|말|없음)
                M.append("  · 최근 친목·건네기: " + " / ".join(_act_item(a, nm(r.get("char", "?"))) for a in acts))

    k = obs.get("known")
    if k and (k.get("statics") or k.get("last_seen") or k.get("zones")):
        M += ["", "## 네가 기억하는 것 (이 층에서 직접 봄 — 지금은 시야 밖)"]
        def far(e):                          # 09-06: 얼마나 먼지(방위+직선 칸) — 문(D19)과 같은 자, 좌표 아님
            return (", %s %d칸" % (e["bearing"], e["dist"])) if e.get("bearing") and e.get("dist") is not None else ""
        for e in k.get("statics", []):
            M.append("- %s%s — %s에서 %s 봄%s%s"
                     % (e.get("name", "?"),
                        (" %s" % e["id"]) if e.get("id") else "",
                        e.get("zone", "?"), ago(e.get("turn", 0)), far(e),
                        "" if e.get("id") else " (위치만 기억해 둔 것)"))
        for e in k.get("last_seen", []):
            who = nm(e["char"]) if e.get("char") else (
                "%s %s" % (e.get("kind", "?"), e.get("id", "?")))
            M.append("- %s — %s에서 %s 마지막으로 봄%s (지금도 거기 있단 보장은 없다)"
                     % (who, e.get("zone", "?"), ago(e.get("turn", 0)), far(e)))
        zs = k.get("zones", [])
        if zs:
            M.append("- 가 본 방: " + ", ".join(x.get("id", "?") for x in zs))

    hist = obs.get("history") or []          # D38 개정 2-b(09-07 밤): 최근 **선택**들만 한 줄(오래된 것부터 직전까지, 작정·폴백
                                              #   표식). 엔진 결과는 안 싣는다 — 반복인지는 캐릭터가 읽는다(사실만·해석 없음)
    it, la, wit = obs.get("intent"), obs.get("last"), obs.get("witnessed")
    dry = obs.get("dry")
    trail = obs.get("trail") or []            # D38 궤적 — 마지막 결정 이후 일어난 일(순서). 1건이면 last 와 같다
    if it or la or wit or dry or trail or hist:
        M += ["", "## 네 직전 판단과 그 결과 (네 자신의 기억)"]
        if hist:
            M.append("- 최근 판단(오래된 것부터, 직전까지): " + " · ".join(_hist_item(h) for h in hist))
        if it:
            line = "- 직전 판단%s: %s" % (("(t%d)" % it["turn"]) if it.get("turn") is not None else "",
                                          it.get("type", "?"))    # (tN) = D38 궤적 판만(얼마나 전의 판단인지)
            if it.get("target"):
                line += " %s" % G.place_word(it["target"], "decide")   # 칸 핑 '@x,y' → 사람 말(09-08)
            if it.get("item"):
                line += " %s" % G.ITEM_KR.get(it["item"], it["item"])   # D47 ② 건네기 — 무엇을
            if it.get("form"):
                line += " [%s]" % it["form"]                            # D47 ② 친목 — 어떤 몸짓
            if it.get("reason"):
                line += ' — 이유: "%s"' % it["reason"]
            M.append(line)
            if it.get("say"):
                M.append('  그때 동료에게 한 말%s: "%s"' % (" (제안)" if it.get("say_kind") == "제안" else "", it["say"]))
        if len(trail) > 1:                    # 다건 = 꼬리표 체인(D40). 출혈은 꼬리표가 실어 별도 줄 없음
            M.append("- 그 뒤 일어난 일: " + _trail_prose(trail, names))
        elif trail:                           # 1건 — 궤적 판은 1건도 꼬리표(파트너 확정 "꼬리표식으로 바꾸자")
            M.append("- 그 결과: " + _trail_prose(trail, names))
        elif la:
            M.append("- 그 결과: %s" % _last_prose(la, names))
            if la.get("bleed"):                   # 출혈(D34) — 걷는 동안 흘린 피(사실만)
                M.append("- 걷는 동안 출혈로 피를 흘렸다 — 남은 HP %d" % la["bleed"].get("hp", 0))
        for w in (wit or []):
            M.append("- 네 눈으로 봤다: " + _witness_prose(w))
        if dry:                       # 무발견 신호(07-24) — 관찰 사실만(질문·조향 금지), 도달 1회
            M.append("- 한참을 걸었는데 새로 보이는 것이 없다 — 아는 자리만 이어진다")

    fl = obs.get("floor")                   # D40 ② 층 집계 — 세계가 센 횟수(숫자만 늘지 줄은 안 는다)
    if fl and (fl.get("n") or fl.get("w")):
        M += ["", "## 이 층에서 지금까지 (t%s 진입, %d틱째 — 세계가 센 횟수)"
              % (fl.get("since", "?"), int(fl.get("turns") or 0))]
        if fl.get("n"):
            M.append("- " + _floor_counts(fl["n"]))
        if fl.get("w"):
            M.append("- 목격: " + _floor_counts(fl["w"]))
        if fl.get("rooms"):
            M.append("- 가 본 곳: 방·통로 %d" % int(fl["rooms"]))
    fls = obs.get("floors")                 # D40 ② 지난 층 결산 — 뼈(횟수)+살(네가 남긴 한 줄)
    if fls:
        M += ["", "## 지난 층 (결산 — 세계가 센 횟수 + 네가 남긴 한 줄)"]
        for f in fls:
            body = _floor_counts(f.get("n") or {}) or "특별한 일 없음"
            if f.get("w"):
                body += " — 목격: " + _floor_counts(f["w"])
            if f.get("line"):
                body += ' — "%s"' % f["line"]
            M.append("- %s (t%d~t%d, %d틱): %s" % (_floor_name(f.get("depth")), int(f.get("t0") or 0),
                                                  int(f.get("t1") or 0),
                                                  int(f.get("t1") or 0) - int(f.get("t0") or 0), body))
        last = fls[-1]
        if last.get("invite") and not last.get("line"):
            M.append("- 방금 떠난 %s을(를) 한 줄로 남기려면 응답 JSON 의 `floor_line` 필드"
                     " (선택, 80자 — 다음 층들에서도 다시 본다)" % _floor_name(last.get("depth")))

    nts = obs.get("notes")
    if nts:                                 # D26 의미 기억 — 스스로 남긴 한 줄들(주관, 엔진 불가침)
        M += ["", "## 네가 기억해두기로 한 것 (스스로 남긴 한 줄 — 오래된 것부터 바랜다)"]
        for s2 in nts:
            M.append('- "%s"' % s2)

    mem = obs.get("memories")
    if mem:                                 # D22 기억층 — 휘발 0: 매 결정 다시 제시된다
        M += ["", "## 잊지 못할 일 (네가 목격하거나 알게 된 중대사)"]
        for e in mem:
            nm_ = "%s(봇%s)" % (e.get("name", "동료"), e.get("char", "?"))
            if e.get("kind") == "grave_found":      # 묘 발견 — 죽음을 못 봤어도 묘를 본 순간 안다
                M.append("- [%s의 죽음을 발견] %s — %s에서 (%s)"
                         % (nm_, e.get("grave", "묘"), e.get("zone", "?"), ago(e.get("turn", 0))))
            else:                                   # 목격 — 사인·장소(D22 기억층 v0=fallen)
                M.append("- [%s의 죽음을 목격] %s 죽었다 — %s에서 (%s)"
                         % (nm_, _by_phrase(e), e.get("zone", "?"), ago(e.get("turn", 0))))

    inv = next((r for r in (obs.get("relations") or []) if r.get("invite")), None)
    if inv:                                 # 살 초대(D36) — 강한 뼈 직후 또는 문턱 결정에만 칸이 생긴다
        who_ = nm(inv.get("char", "?"))
        why = {"rescued": "%s가 방금 너를 구했다" % who_,
               "at_death": "%s가 죽을 때 네가 곁에 있었다" % who_,
               }.get(inv["invite"], "%s와 그간 겪은 일이 쌓였다" % who_)
        M += ["", "## %s에 대해 남길 한 줄 (선택)" % who_,
              "- %s. %s에 대한 네 생각을 한 줄로 고쳐 써도 좋다 — 응답 JSON 의 `relation_line` 필드"
              " (안 써도 된다. 쓰면 이전 줄을 덮어 쓴다)" % (why, who_)]
        if inv.get("line"):
            M.append('- 지금까지의 한 줄: "%s" (%s)'
                     % (inv["line"], "시트" if inv.get("line_src") == "sheet"
                        else "네가 %s턴에 남긴 말" % inv.get("line_turn", "?")))

    dlg = obs.get("dialogue") or []           # D43 대화 기억(09-07): 지난 결정까지 들은 말과 내가 한 말 — 오래된 것부터.
    if dlg:                                   #   이번 턴 새로 들린 말은 아래 절(중복 없음 — 장부엔 다음 결정부터 실린다)
        M += ["", "## 최근 대화 (오래된 것부터 — 이번 턴에 새로 들린 말은 관측의 '동료가 한 말'에)"]
        for m in dlg:
            M.append('- %s (t%s%s): "%s"' % (_dlg_who(m, nm), m.get("turn", "?"),
                                              ", 제안" if m.get("kind") == "제안" else "", m.get("text", "")))
    ms = obs.get("messages")
    if ms:
        L += ["", "## 동료가 한 말 (걷는 동안 들린 것까지 — 오래된 것부터. 너를 세운 건 제안뿐이다)"]
        for m in ms:
            to = m.get("to")                     # D41 지목 표식 — 누구에게 한 말인지(혼잣말은 아무도 안 멈춘다)
            if m.get("kind") == "제안":          # D47 말의 종류 — 제안만 세운다(대상 없는 제안=회의)
                tag = (" (모두에게 제안 — 회의)" if to in (None, "all") else " (너에게 제안)" if m.get("to_me")
                       else " (%s에게 제안)" % nm(to))
            else:
                tag = (" (모두에게)" if to == "all" else " (너에게)" if m.get("to_me")
                       else (" (%s에게)" % nm(to)) if to else " (혼잣말)")
            mt = m.get("turn")                   # D47 배관: 보관된 말 — 지난 턴보다 오래된 말은 얼마나 전인지 병기
            old = (" — %d턴 전" % (now - mt)) if (now is not None and mt is not None and now - mt >= 2) else ""
            L.append('- %s: "%s"%s%s' % (nm(m.get("from", "?")), m.get("text", ""), tag, old))

    # ── 조립(09-08 D44, 파트너 네 갈래 "시트=나는 누구인가 · 관측=뭘 보고 있나 · 기억=무엇을 기억하나 · 선택지=지금 주어진 것"):
    #   시트·지침은 claude_brain 이 앞에 붙이고 선택지는 뒤에 붙인다. 여기서는 **기억 → 관측** 순 — 내 선택(임시 가정): 지금 보고
    #   들은 것(장소·동료가 한 말)이 선택지 바로 위에 오도록(과거→현재→행동, D41 지목 응답이 '동료가 한 말' 인접성에 기대 왔다).
    #   파트너 열거는 관측→기억 — 뒤집으려면 아래 두 덩이만 바꾼다. 기억이 비면(첫 결정) 머리글도 없다.
    out = []
    if M:
        out += ["# 기억 — 무엇을 기억하나"] + M + [""]
    out += ["# 판단 공간 — 지금 보고 듣는 것" if compose else "# 관측 — 지금 보고 듣는 것", ""] + L
    if compose:
        # 메뉴가 사라져도 장비 효과·공격 가능 거리 같은 사실은 잃지 않는다.
        out += ["", "## 소지품 — 착용 현황"]
        if not obs.get('action_schema'):
            out += ["- potion: 회복 물약 %d병" % obs.get("potions", 0)]
        for slot in ("weapon", "armor"):
            gear = (obs.get("gear") or {}).get(slot)
            out.append("- %s: %s" % (slot, gear["name"] if gear else "없음"))
        facts = []
        for f in s.get("features", []):
            if f.get("type") in ("weapon", "armor"):
                effect = "피해" if f["type"] == "weapon" else "막기"
                facts.append("- %s: 착용하면 %s +%d, 교체한 장비는 그 자리에 놓인다"
                             % (f["id"], effect, G.GEAR_KINDS.get(f["name"], 0)))
        for m in s.get("monsters", []):
            facts.append("- %s: 현재 자리에서 %s" % (m["id"], "공격 사거리·사선 안" if m.get("in_range") else "공격 범위 밖"))
            if m.get('status'):
                facts.append('- %s: %s' % (m['id'], ' · '.join(m['status'])))
        if facts:
            out += ["", "## 대상의 현재 사실"] + facts
        ways = s.get("ways", []) if not obs.get('action_schema') else []
        if ways:
            out += ["", "## 탐색 후보 — 방향"] + [
                "- %s: %d칸, %s" % (w["bearing"], w["dist"], "가 본 길" if w.get("visited") else "안 가본 길")
                for w in ways]
        if obs.get('action_schema') == G.CA.SCHEMA:
            out += ["", "## 대상 — 지금 참조할 수 있는 ID"]
            for target in obs.get('targets', []):
                out.append('- [%s] %s (%s)%s%s' % (
                    target['id'], target.get('name', target['id']), ', '.join(target['tags']),
                    (' — ' + at(target)) if 'dist' in target else '',
                    (' · %d개' % target['count']) if 'count' in target else ''))
        out += ["", "## 행동과 의사소통", "COMMON: " + " / ".join(G.CA.COMMON if obs.get('action_schema') else _compose_types()),
                "의사소통: 잡담 / 제안"]
        if obs.get('skills'):
            out += ['', 'SKILL:']
            for skill in obs['skills']:
                out.append('- %s (%s): %s · 남은 재사용 %d행동' % (
                    skill['id'], skill['name'], skill['description'], skill['cooldown']))
            out.append('SKILL도 type + target으로 선택하며 범위 밖이면 기존 자동 접근을 따른다.')
    if obs.get('social_events'):
        out += ['', '## 네가 받은 사회적 상호작용 — 선택적으로 한 사건에 반응할 수 있다']
        for event in obs['social_events']:
            out.append('- [%s] t%s · %s(봇%s)에게서: %s' % (
                event['id'], event['turn'], names.get(event['actor'], '상대'), event['actor'], G.SR.describe(event)))
    extra = {kk: v for kk, v in obs.items() if kk not in _WIRE_KEYS
             and kk not in ('action_schema', 'actor', 'targets', 'items', 'ways', 'social_events', 'skills')}
    if extra:                       # 미래 additive 필드 — 조용한 누락 대신 정직한 노출
        out += ["", "## 그 밖의 정보", "```json",
                json.dumps(extra, ensure_ascii=False), "```"]
    return "\n".join(out)


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
    if "item" in o:
        out["item"] = o["item"]               # D47 ② 건네기 — 물건은 메뉴 줄이 정한다(응답 필드 아님)
    return out


def _then(obj, obs):
    """작정(D16): 응답의 선택 필드 "then" = 이번 행동에 이어질 행동, 최대 PLAN_MAX수.
    항목 = 메뉴 번호(리모컨 어휘 그대로) 또는 행동 객체 {type, target}.
    저작 시점 검증(시야-온리): goto/attack/interact 의 target 은 지금 보이는 id 만 —
    못 본 것을 향한 작정은 열린 동사(explore/search)로만 표현된다(D16).
    불량 항목을 만나면 그 항목부터 뒤 전부 버림(사슬 중간이 끊기면 뒷수는 근거를 잃는다).
    본 행동은 건드리지 않는다 — then 은 보너스(관용 원칙)."""
    raw = obj.get("then")
    if not isinstance(raw, list):
        return []
    if obs.get('action_schema') == G.CA.SCHEMA:
        out = []
        for item in raw[:G.PLAN_MAX]:
            if not isinstance(item, dict):
                break
            step, error = G.CA.parse(item, obs)
            if error:
                break
            out.append(step)
            if step['type'] in ('wait', 'rest'):      # D48: follow 는 COMMON 밖(parse 가 먼저 거른다)
                break
        return out
    out, valid = [], None
    for item in raw[:G.PLAN_MAX]:
        step = None
        if isinstance(item, dict):
            typ = str(item.get("type", "")).strip().lower()
            tgt = str(item.get("target", "")).strip()
            if typ == "search":
                step = {"type": "search"}
            elif typ == "explore":
                step = {"type": "explore"}
                if tgt.upper() in _BEARINGS:
                    step["target"] = tgt.upper()
            elif typ in ("goto", "attack", "interact"):
                if valid is None:
                    valid = {}
                if typ not in valid:        # 동사별 유효 집합 — 장부 id 는 goto 에만(리뷰 픽스)
                    valid[typ] = _valid_targets(obs, typ)
                if tgt in valid[typ]:
                    step = {"type": typ, "target": tgt}
        else:
            pick = _pick({"choice": item}, obs)   # 메뉴 번호 관용 — 엔진 열거 행동이라 환각 무해
            if pick and pick.get("type") != "follow":   # 동행=열린 결말 — 작정 수로 부적합(D18 A-5)
                step = {k: pick[k] for k in ("type", "target") if k in pick}
        if not step:
            break
        out.append(step)
    return out


_BLOCK_TAGS = ("PROHIBITED_CONTENT", "SAFETY", "BLOCKLIST", "IMAGE_SAFETY", "RECITATION", "OTHER")   # Gemini blockReason/finishReason 어휘


def _safety_blocked(why):
    """빈 응답 라벨이 모델의 안전 차단(입력·출력 단계)인가 — "빈 응답 rc=200 | <TAG>" 꼴만. 타임아웃·JSON 불량은 아니다."""
    s = str(why or "")
    return "rc=200 | " in s and any(s.rstrip().endswith(t) for t in _BLOCK_TAGS)


def fallback_backend(current=None):
    """안전 차단 때 같은 판단을 대신 물을 두뇌(09-11, 파트너 "계속 검열이 걸리네"): DUNGEON_BRAIN_FALLBACK 이 있으면 그것
    (빈 문자열=끔), 없으면 키가 있는 Claude(anthropic_api → claude_cli), 그마저 현재 두뇌면 gemini_api. 현재와 같거나 dummy 면 None.
    검열 회피가 아니라 판단 주체 교체 — 규칙 두뇌 대행은 여전히 없다(06d4b30). 어느 두뇌가 답했는지는 결정의 brain_fallback 에 남는다."""
    cur = current or backend_name()
    # 09-12 파트너 "우회 로직은 도움이 되는 방법이 아냐, 근본 문제를 해결하자" → 기본 꺼짐(opt-in). 켜려면 DUNGEON_BRAIN_FALLBACK=<backend>.
    cands = [os.environ.get("DUNGEON_BRAIN_FALLBACK", "").strip()]
    for c in cands:
        if c and c in BACKENDS and c != cur and c != "dummy":
            return c
    return None


def _dump_blocked_prompt(char, obs, label, prompt):
    """모델의 안전 차단에 걸린 프롬프트 원문을 state/brain_block.log 에 JSONL 로 남긴다(09-12 파트너 "근본적 문제를 해결하자").
    스트림에는 안 싣는다(원문 = 시트·관측 전체). 어느 문장이 필터를 건드리는지는 이 파일로 이분한다."""
    try:
        path = os.path.join(os.environ.get("DUNGEON_STATE_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "state"),
                            "brain_block.log")
        with _LOG_LK:
            with open(path, "a", encoding="utf-8", newline="\n") as fp:
                fp.write(json.dumps({"t": time.time(), "turn": obs.get("turn"), "char": char, "backend": backend_name(),
                                     "label": label, "prompt": prompt}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _dummy_decision(obs, char, why="테스트"):
    """명시적인 dummy 백엔드 전용. src=fallback은 기존 테스트 기록과 호환한다."""
    if backend_name() != "dummy":
        raise RuntimeError("실플레이에서 규칙 두뇌를 호출할 수 없다")
    fb = dict(G.dummy_brain(obs, char))            # {type, [dir]}
    if obs.get('action_schema') == G.CA.SCHEMA:
        fb = G.CA.fallback(fb, obs)
    fb.update(say="", reason="[폴백] %s -> 규칙두뇌" % why, src="fallback")
    return fb


class DecisionBlocked(RuntimeError):
    """실행할 행동이 없는 판단 오류. 대기·탐색으로 바꾸면 안 된다."""
    def __init__(self, errors):
        self.errors = errors
        super().__init__("모델 판단 실패 — 원정 진행 보류")


def claude_brain(obs, char="?", bot=None, roster=None, solo=False):
    if bot is None:                          # 하위호환(구 시그니처): HEROES 로 유사 봇 구성
        h = G.HEROES.get(char, {})
        bot = {**h, "char": char, "maxhp": h.get("hp")}
    # D17-3: obs 는 JSON 덤프가 아니라 자기설명 문장(_wire)으로 나간다 — dict 계약은 불변.
    # options 는 _wire 가 렌더하지 않는다: 메뉴 모드=아래 번호 목록이 그것, 자유서술=비노출(순수성).
    names = {o["char"]: (o.get("name") or o.get("job", "동료")) for o in (roster or [])}
    if COMPOSE:
        instructions = COMPOSE_PROMPT_SOLO if solo else COMPOSE_PROMPT
        if obs.get('skills'):
            instructions = instructions.replace('매 판단에 제시되는 COMMON에서 행동 이름을 고른다.',
                                                '매 판단에 제시되는 COMMON 또는 SKILL에서 행동 이름을 고른다.')
            instructions = instructions.replace('이어질 행동도 같은 COMMON과', '이어질 행동도 같은 COMMON 또는 SKILL과')
        prompt = (_sheet(bot, roster) + "\n" + instructions
                  + "\n\n" + _wire(obs, names, compose=True)
                  + "\n\n오직 JSON 한 줄로만 답하라.")
    elif MENU:
        menu = "\n".join("%d. %s" % (o["n"], o["label"])
                         for o in (obs.get("options") or []))
        prompt = (_sheet(bot, roster) + "\n" + (MENU_PROMPT_SOLO if solo else MENU_PROMPT)
                  + "\n\n" + _wire(obs, names)
                  + "\n\n# 선택지 — 이 중 번호 하나를 골라라\n" + menu   # (09-08 D44) 갈래 머리글
                  + "\n\n오직 JSON 한 줄로만 답하라.")
    else:
        prompt = (_sheet(bot, roster) + "\n" + (ADV_PROMPT_SOLO if solo else ADV_PROMPT)
                  + "\n\n" + _wire(obs, names)
                  + "\n\n오직 JSON 한 줄로만 답하라.")
    errors = []
    request = prompt
    fallback = None                                   # 안전 차단 → 두 번째 시도의 대체 두뇌(있을 때만)
    for attempt in range(2):
        _TLS.backend_override = fallback if attempt == 1 else None
        try:
            res = _call_claude(request, "haiku")
        finally:
            _TLS.backend_override = None
        raw, why = res if isinstance(res, tuple) else (res, None)
        dec = _parse_decision(raw, why, obs, char, roster)
        if dec.get("src") != "error":
            if errors:
                dec["brain_retries"] = errors
            if attempt == 1 and fallback:
                dec["brain_fallback"] = fallback          # 이 판단은 대체 두뇌가 했다(스트림 additive)
            return dec
        if backend_name() == "dummy":
            fb = _dummy_decision(obs, char, dec["reason"])
            fb.update({k: v for k, v in dec.items() if k not in ("src", "reason")})
            return fb
        errors.append({"code": dec["input_error"], "reason": dec["reason"],
                       "detail": dec["input_error_detail"]})
        if attempt == 0 and _safety_blocked(dec["reason"]):
            _dump_blocked_prompt(char, obs, dec["reason"], request)   # 근본 원인 부검용(09-12): 걸린 프롬프트 원문을 state 에 남긴다
            fallback = fallback_backend()
            if fallback:                              # 같은 프롬프트를 다른 두뇌에게 — 오류 덧말은 이 모델에겐 뜻이 없다
                request = prompt
                continue
        # 원래 관측과 시트는 그대로 둔다. 대체 행동은 추천하지 않고 실패 사실만 돌려준다.
        request = (prompt + "\n\n# 직전 응답의 입력 오류 — 아직 행동하지 않았고 시간도 흐르지 않았다\n"
                   + json.dumps(errors[-1], ensure_ascii=False)
                   + "\n위 오류와 현재 관측을 확인하고 네 의도에 맞는 행동을 다시 판단하라. 오직 JSON 한 줄로 답하라.")
    return {**dec, "attempt_errors": errors}


def _already_beside(composed, char, roster):
    """goto <아군>인데 그 사람이 이미 곁(체비셰프 1)에 있고 멈춰 있으면 사유 문장, 아니면 None(D48 개정, 09-11 메모 §2-4 [제안]
    "이미 곁에 있는 아군에게 goto 하면 '이미 곁에 있다' 결과 + 같은 틱 재판단 — 기존 입력 무효 처리와 같은 방식").
    엔진 _set_follow(chase) 의 already_beside 와 같은 판정을 결정 시점(틱 시작 스냅샷)에 미리 한다."""
    if composed.get("type") != "goto":
        return None
    tgt = str(composed.get("target") or "")
    if tgt[:1] != "b" or tgt[1:] == str(char):
        return None
    me = next((o for o in (roster or []) if str(o.get("char")) == str(char)), None)
    other = next((o for o in (roster or []) if str(o.get("char")) == tgt[1:]), None)
    if not me or not other or "x" not in me or "x" not in other:
        return None
    if G.Dungeon._beside_xy(me["x"], me["y"], other["x"], other["y"], "bot") and not G.is_moving(other):
        return "%s은(는) 이미 곁에 있고 멈춰 있다 — 곁에 멈춘 사람에게는 갈 수 없다" % (other.get("name") or other.get("job") or tgt)
    return None


def _parse_decision(raw, why, obs, char, roster):
    """응답을 행동 또는 오류로 읽는다. 오류에는 실행 가능한 type이 없다."""
    obj, jwhy = _extract(raw)
    why = why or jwhy
    if obj:
        reaction = G.SR.parse(obj, obs) if COMPOSE else {}
        if COMPOSE:
            composed, input_error = _compose_pick(obj, obs)
            if input_error:
                fb = {"src": "error", "reason": input_error}
                fb["input_error"] = input_error
                fb['input_error_detail'] = G.CA.error_detail(obj, obs, input_error)
                fb.update(reaction)
                return fb
            ab = _already_beside(composed, char, roster)   # D48 개정(메모 §2-4 [제안]): 곁에 멈춘 사람에게 goto = 입력 무효 → 같은 틱 재판단
            if ab:
                fb = {"src": "error", "reason": ab, "input_error": "already_beside",
                      "input_error_detail": {**G.CA.error_detail(obj, obs, "already_beside"), "reason": ab}}
                fb.update(reaction)
                return fb
            # 번호 작정은 이 모드의 문법이 아니다. 기존 객체 작정 검증은 그대로 재사용.
            raw_then = obj.get("then")
            if raw_then is not None and (not isinstance(raw_then, list) or any(not isinstance(s, dict) for s in raw_then)):
                obj = {**obj, "then": []}
        then = _then(obj, obs)                      # 작정(D16) — 유효 수만 남긴 이어질 계획(없으면 [])
        note = (str(obj.get("note", "") or "").strip()[:NOTE_LEN]   # D26 남길 한 줄(선택 필드)
                if NOTES_ON else "")
        inv = next((r for r in (obs.get("relations") or []) if r.get("invite")), None)
        rline = (str(obj.get("relation_line", "") or "").strip()[:NOTE_LEN]   # D36 살 — 초대가 있을 때만
                 if inv else "")                                             #   받는다(에지 없는 콜은 무시)
        rel = {"relation": {"to": inv["char"], "line": rline}} if rline else {}
        fline = (str(obj.get("floor_line", "") or "").strip()[:NOTE_LEN]     # D40 ② 결산 한 줄 — 초대(새 층
                 if any(f.get("invite") for f in (obs.get("floors") or [])) else "")   #   첫 결정)에서만 받는다
        if fline:
            rel = {**rel, "floor_line": fline}
        to_ = _parse_to(obj.get("to"), char, roster, obs)   # D41 지목 — 말의 상대(없으면 혼잣말)
        said = bool(str(obj.get("say", "") or "").strip())
        if to_ and said:
            rel = {**rel, "to": to_}
        if said:                                            # D47 말의 종류 — 말이 있을 때만(잡담|제안, 기본 잡담)
            rel = {**rel, "say_kind": _parse_kind(obj.get("say_kind"))}
        if COMPOSE:
            if composed["type"] in ("wait", "rest"):    # 열린 결말 — then 못 이음(D48 뒤 follow 없음)
                then = []
            return {**composed, **({"then": then} if then else {}),
                    **({"note": note} if note else {}), **rel, **reaction,
                    "say": str(obj.get("say", "") or "")[:160],
                    "reason": str(obj.get("reason", "") or "")[:160], "src": "haiku"}
        if MENU:
            act = _pick(obj, obs)
            if act:
                if act["type"] == "follow":
                    then = []                       # 동행=열린 결말 — then 뒤수 부적합(D18 A-5)
                if act["type"] == "bond":           # D47 ② 친목 — 몸짓은 응답 form(자유 문구, 엔진 무해석·BOND_LEN)
                    act["form"] = _clean_form(obj.get("form"))
                return {**act,
                        **({"then": then} if then else {}),
                        **({"note": note} if note else {}),
                        **rel,
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
        if typ == "follow" and tgt and tgt[:1] != "b":
            tgt = "b" + tgt                         # 동행 '2' → 'b2' 관용(자유서술 흔들림 흡수)
        if typ in _TYPES:
            if typ == "follow":
                then = []                           # 동행=열린 결말 — then 뒤수 부적합(D18 A-5)
            out = {"type": typ,
                   **({"then": then} if then else {}),
                   **({"note": note} if note else {}),
                   **rel,
                   "say": str(obj.get("say", ""))[:160],
                   "reason": str(obj.get("reason", ""))[:160],
                   "src": "haiku"}
            if typ in ("search", "drink", "wait", "rest"):
                return out                          # search·drink·wait·rest 는 target 불필요
            if typ == "explore":                    # 탐색: 방위(N/S/E/W/NE…)만 선택적으로(없으면 엔진 자동)
                if tgt.upper() in _BEARINGS:
                    out["target"] = tgt.upper()
                return out
            if tgt in _valid_targets(obs, typ):     # 보이는 id만 허용(환각 타겟 차단.
                out["target"] = tgt                 #   장부 귀환 id 는 goto 전용 — 리뷰 픽스)
                return out
        # JSON 은 왔으나 행동으로 해석 실패(무효 choice·type·target) — 원문 머리를 계측에 남긴다
        why = "행동 해석 실패: " + _head(json.dumps(obj, ensure_ascii=False))
    fb = {"src": "error", "reason": why or "파싱 실패", "input_error": "invalid_response",
          "input_error_detail": {"code": "invalid_response", "reason": why, "raw_response": raw}}
    return fb


def social_all(d, bots, inbox=None):
    """사교 콜(채널 분리 2026-07-26) — **걷는 중에도 열리는 말의 채널**.

    행동 콜(think_all)과 갈린 이유: 콜이 '작정 없는 봇'에게만 열려서, 말을 들으려면 작정을
    부수는 것 말고 길이 없었다(D24). 그 부작용이 목적 상실이었다 — 07-26 부검에서 작정
    파기 직후 follow 46% vs 평상시 29%. 여기서는 **행동을 못 바꾼다** — order·path·plan 을
    건드리지 않고 say 만 낸다. '대화는 행동을 방해할 권한이 없다'가 훈계가 아니라 구조다.

    대상 = 말을 들었고(hailed) 작정 수행 중인 봇. 작정 없는 봇은 어차피 행동 콜에서
    say 칸을 함께 받으므로 여기 오지 않는다(콜 중복 금지).

    ⚠️ 반드시 _call_claude 를 거친다 — 게이트 15개가 그 이름을 몽키패치해 실 LLM 을
    차단하고, verify_brain ⑤가 '스텁이 백엔드보다 우선'을 감시한다. 새 경로를 뚫으면
    초록불 유출이 생긴다.

    프로브 판정(2026-07-26, 6콜): 판단 필드(need)를 **앞에** 두면 캐릭터가 침묵을 고를 줄
    안다 — 카야(과묵 시트) 3/3 의도대로, 피른(수다 시트)은 3/3 발화. 즉 say 빈도는 병리가
    아니라 시트다. 원래 프롬프트처럼 say 하나만 물으면 빈칸을 못 견뎌 100% 발화한다.
    반환 = {char: say} (침묵은 키 자체가 없다)."""
    if not getattr(d, 'social', False) or not SOCIAL_PROMPT:
        return {}
    inbox = inbox or {}
    talkers = [b for b in bots
               if b['alive'] and not b['won'] and b.get('order') and b.get('hailed')]
    if not talkers:
        return {}
    roster = [] if getattr(d, 'solo', False) else bots   # 솔로 판: 로스터 없음(위 think_all 과 같은 이유)
    names = {o['char']: (o.get('name') or o.get('job', '동료')) for o in roster}
    obss = {}
    for b in talkers:
        o = d.view(b, bots)
        o['messages'] = inbox.get(b['char'], [])
        obss[b['char']] = o

    def ask(b):
        prompt = (_sheet(b, roster) + "\n"
                  + (SOCIAL_PROMPT_SOLO if getattr(d, 'solo', False) else SOCIAL_PROMPT)
                  + "\n\n" + _wire(obss[b['char']], names)
                  + "\n\n오직 JSON 한 줄로만 답하라.")
        raw, why = _call_claude(prompt, "haiku")
        obj, _jwhy = _extract(raw)
        if not obj:
            return ""                      # 실패 = 침묵(폴백이 말을 지어내지 않는다)
        if str(obj.get('need', '')).strip().lower() != 'yes':
            return ""                      # 판단이 먼저다 — no 면 say 를 읽지 않는다
        return str(obj.get('say', ''))[:160]

    out = {}
    with ThreadPoolExecutor(max_workers=len(talkers)) as ex:
        futs = {b['char']: ex.submit(ask, b) for b in talkers}
        for c, f in futs.items():
            s = f.result()
            if s:
                out[c] = s
    return out


def think_all(d, bots, inbox=None, on_error=None):
    """order 없는(=재결정 필요한) 살아있는 봇만 '같은 틱-시작 스냅샷'에서 동시 사고.
    order 있는 봇은 엔진 자동보행 중이라 LLM 호출 안 함(콜 절약). inbox→obs.messages 주입.
    작정(D16): 남은 계획이 있는 봇은 LLM 대신 다음 수를 집행(src='plan', 콜 0) —
    엔진 착수 재검증(plan_step)이 깨지면 그 자리에서 계획이 찢기고 **같은 틱에** LLM 재결정으로
    넘어간다(틱 손실 없음, obs.last=plan_broken 이 사유를 보고). 작정 집행 틱엔 view() 미호출 —
    inbox 는 다음 결정점까지 못 읽는다(D16 문서화된 트레이드오프, PLAN_MAX 로 억제)."""
    live = [b for b in bots if b["alive"] and not b["won"] and not b.get("order")]
    if not live:
        return {}
    inbox = inbox or {}
    out = {}
    thinkers = []
    for b in live:
        step = d.plan_step(b, bots)       # 작정 다음 수(착수 재검증 포함) — 없거나 깨지면 None
        if step:
            out[b["char"]] = {**step, "say": "",
                              "reason": "[작정] 미리 정한 다음 수", "src": "plan"}
        else:
            thinkers.append(b)
    obss = {}
    for b in thinkers:
        o = d.view(b, bots)
        reaction_book = G.SR.book(d)
        if reaction_book is not None:
            o['social_events'] = reaction_book.offer(b['char'])
        o["messages"] = [{**m, **({"to_me": True} if (G.addressed_to(m, b["char"]) and m.get("to") != "all") else {})}
                         for m in inbox.get(b["char"], [])]   # D41: 나를 지목한 말 표식(렌더용, 스트림 무접촉)
        if b.get("intent"):
            o["intent"] = b["intent"]   # 판단 되먹임(D15①): 자기 직전 판단의 기억 — inbox와 같은
        if HISTORY_ON and b.get("history"):
            o["history"] = list(b["history"][-HISTORY_MAX:])   # D38 개정 2-b: 최근 선택들(작정·폴백 포함, 직전까지)
        if DIALOGUE_ON:
            # D43 대화 기억(09-07 파트너 "대화 내용도 과거로 조금만 더 확장"): 지난 결정까지의 대화(들은 말+내 말)를 되돌려주고,
            # 이번 틱에 읽은 인박스는 장부에 잇는다(다음 결정부터 보인다 — 아래 '동료가 한 말' 절과 중복 없음). 지난 틱의 말이라 turn-1.
            if b.get("dialogue"):
                o["dialogue"] = list(b["dialogue"][-DIALOGUE_MAX:])
            dl = b.setdefault("dialogue", [])
            for m in inbox.get(b["char"], []):
                # D47 배관: 보관된 말은 제 turn(말한 틱)으로 — 없으면 지난 틱(turn−1). 제안은 종류 표식을 함께
                dl.append({"turn": m.get("turn", d.turn - 1), "from": m.get("from"), "to": m.get("to"), "text": m.get("text", ""),
                           **({"to_me": True} if (G.addressed_to(m, b["char"]) and m.get("to") != "all") else {}),
                           **({"kind": "제안"} if m.get("kind") == "제안" else {})})
            del dl[:-DIALOGUE_MAX]
        if NOTES_ON and b.get("notes"):
            o["notes"] = list(b["notes"])   # D26 의미 기억 — 스스로 남긴 한 줄들(자기 것=시야-온리 무관)
        obss[b["char"]] = o             # 주입 솔기. 세계 정보가 아니라 자기 것이라 시야-온리 무관.
    if thinkers:
        _t0 = time.time()               # 플레이어가 실제로 기다리는 시간 = 틱 벽시계.
                                        # 콜당 지연의 합이 아니라 **최댓값**이다(동시 호출) —
                                        # 이 둘이 벌어지면 동시성이 실효하지 않는다는 뜻.
        with ThreadPoolExecutor(max_workers=len(thinkers)) as ex:
            solo = bool(getattr(d, 'solo', False))
            roster = [] if solo else bots    # 솔로 판(07-29)은 로스터가 없다 —
            futs = {b["char"]: ex.submit(claude_brain, obss[b["char"]], b["char"], b,
                                         roster, solo)
                    for b in thinkers}       # bot=시트 포함 봇 dict, roster=파티(관계 이름 풀이)
                                             #   시트에서 relationships 를 빼도 '- 동료: 두란(봇1)…'
                                             #   줄이 로스터에서 되살아나 이름을 알려준다(누출).
                                             #   남남은 명단도 이름도 모르는 채로 시작한다.
            out.update({c: f.result() for c, f in futs.items()})
        _brainlog(kind="tick", backend=backend_name(), n=len(thinkers),
                  ms=int((time.time() - _t0) * 1000))
        # 성공한 결정·작정·관측은 보관한다. 실패한 봇만 같은 관측으로 재시도하며,
        # 모두 준비되기 전에는 아래의 기억 반영이나 러너의 세계 진행으로 넘어가지 않는다.
        while errors := {c: dec for c, dec in out.items() if dec.get("src") == "error"}:
            if on_error is None:
                raise DecisionBlocked(errors)
            on_error(errors)
            with ThreadPoolExecutor(max_workers=len(errors)) as ex:
                futs = {b["char"]: ex.submit(claude_brain, obss[b["char"]], b["char"], b, roster, solo)
                        for b in thinkers if b["char"] in errors}
                out.update({c: f.result() for c, f in futs.items()})
    by = {b["char"]: b for b in live}
    trail_on = bool(getattr(d, "trail_on", False))
    for c, dec in out.items():          # 이번 판단을 자기 기억으로 저장 → 다음 결정의 obs.intent.
        if HISTORY_ON:                   # D38 개정 2-b(09-07 밤, 파트너 "캐릭터의 선택만"): 결정마다 한 항목 — 실 결정·
            hist = by[c].setdefault("history", [])   #   작정 수·폴백 전부(캐릭터가 정했거나 미리 정한 것 + 대신 골라진 것의 표식).
            hist.append({"turn": d.turn, "type": dec.get("type", ""), "target": dec.get("target"),
                         "src": dec.get("src", ""),           #   엔진이 걷고 멈춘 결과는 안 담는다(직전 절·궤적의 몫)
                         **({"item": dec["item"]} if dec.get("item") else {}),    # D47 ② 건네기 물건 / 친목 몸짓 — 선택의 일부
                         **({"form": dec["form"]} if dec.get("form") else {})})
            del hist[:-HISTORY_MAX]
        if DIALOGUE_ON and dec.get("say"):     # D43: 내가 한 말도 대화 장부에(들은 말과 한 흐름 — 한쪽만 있으면 독백 기록)
            dl = by[c].setdefault("dialogue", [])
            dl.append({"turn": d.turn, "from": c, "to": dec.get("to"), "text": dec.get("say", ""), "mine": True,
                       **({"kind": "제안"} if dec.get("say_kind") == "제안" else {})})
            del dl[:-DIALOGUE_MAX]
        if trail_on and dec.get("src") == "plan":
            continue                     # D38(09-06): 작정 수는 궤적(trail)에 남는다 — 직전 판단은 마지막
                                         #   **실** 결정을 유지(09-06 마을 판: 미나의 '직전 판단'이 매번
                                         #   "[작정] 미리 정한 다음 수"라 자기 결정·결과가 두 수 전으로 사라졌다)
        it = {"type": dec.get("type", "")}   # bot_snapshot 화이트리스트 밖 = 스트림 계약 불변
        for k in ("target", "item", "form", "say", "to", "say_kind", "reason", "src"):   # (직전 decisions에서 파생 가능한 값). to=D41 지목·say_kind=D47·item/form=D47 ② 건네기 물건·친목 몸짓
            if dec.get(k):                   # (궤적 끈 판) 작정 수도 자기 판단의 연속이라 intent 갱신
                it[k] = dec[k]
        if trail_on:
            it["turn"] = d.turn              # D38: "(tN)" — 얼마나 전의 판단인지
        by[c]["intent"] = it
        rl = dec.get("relation")
        if rl and rl.get("line"):        # D36 살 — 그 상대 항목에 한 줄 겹쳐쓰기(옛 줄은 스트림 decisions 에)
            e = by[c].setdefault("relations", {}).setdefault(
                rl["to"], {"bones": {}, "total": 0, "line": None, "line_turn": None,
                           "line_src": None, "queue": []})
            e["line"], e["line_turn"], e["line_src"] = rl["line"], d.turn, "self"
        if dec.get("note"):              # D26 의미 기억 — 남긴 한 줄은 그 봇의 기억 로그로(FIFO)
            ns = by[c].setdefault("notes", [])
            ns.append(dec["note"])
            del ns[:-NOTE_MAX]           # 넘치면 오래된 것부터 바랜다
        fls = by[c].get("floors")        # D40 ② 결산 살 — 초대는 실 결정 1회(답이 없어도 닫힌다), 엔진 불가침
        if fls:
            if dec.get("floor_line"):
                fls[-1]["line"] = dec["floor_line"]
            fls[-1]["invite"] = False
    if os.environ.get("DUNGEON_STREAM_OBS") == "1":
        # 스트림 opt-in: 결정에 '그때 그 봇이 본 것'(obs)을 병합 — think 시점 캡처.
        # 사후 d.view() 재호출로 얻으면 안 된다(시점 오염 + _perceive 부수효과).
        # 작정 수(src='plan')는 obs 미동봉 — view() 자체가 안 불렸다(그게 작정의 경제).
        for c in obss:
            if c in out:
                out[c] = {**out[c], "obs": obss[c]}
    return out
