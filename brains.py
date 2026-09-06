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


ADV_PROMPT, ADV_PROMPT_SOLO = _load_prompt("adventurer_prompt.md")
MENU_PROMPT, MENU_PROMPT_SOLO = _load_prompt("adventurer_prompt_menu.md", required=False)
# 사교 콜 프롬프트(채널 분리 2026-07-26) — 없으면 사교 채널이 통째로 꺼진다(안전망)
SOCIAL_PROMPT, SOCIAL_PROMPT_SOLO = _load_prompt("social_prompt.md", required=False)

# 리모컨 모드(기본 on): 행동=엔진 열거 옵션에서 번호 선택, 말·속내=자유.
# DUNGEON_MENU=0 이면 구식 자유서술(동사+target 직접 작성) — A/B 대조군.
MENU = os.environ.get("DUNGEON_MENU", "1") != "0" and bool(MENU_PROMPT)
if os.environ.get("DUNGEON_MENU", "1") != "0" and not MENU_PROMPT:
    import sys
    print("[경고] adventurer_prompt_menu.md 없음 — 리모컨 끄고 자유서술로 폴백", file=sys.stderr)

# D17-4 직렬화 스위치: LLM 에게 보내는 obs 표현(wire)에서 큰 덩어리를 한 변수씩 끄는 노브.
# obs dict 자체(스트림·BYO·검증 계약)는 불변 — 여기는 '보여주는 방법'만 만진다(options 선례).
# ascii 기본 0 = 2026-07-11 프로브 판정(조우·궁지·로어주입 ×8콜, 사전등록 "지지만 않으면
# 채택"): 전 지표 동질 — sights 문장만으로 공간 판단 유지("7×7 그림은 인간용" §8 인사이트 실증).
OBS_ASCII = os.environ.get("DUNGEON_OBS_ASCII", "0") != "0"   # 7×7 그림+기호 줄(기본 끔)
OBS_POS = os.environ.get("DUNGEON_OBS_POS", "1") != "0"       # 생좌표 pos 줄(실험 전 — 기본 켬)

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
    name = (os.environ.get("DUNGEON_BRAIN_BACKEND") or "claude_cli").strip()
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
NOTE_MAX = 5             # 유지 줄 수(합의 5~7 하한) — 넘치면 오래된 것부터 바랜다(FIFO,
                         #   사람도 옛 기억부터 바래듯). 판 간 영속은 없음(월드 러너 상 재론).
NOTE_LEN = 80            # 한 줄 상한 — 수필 방지(say 160 의 절반: 기억은 말보다 압축된다)

_TYPES = {"goto", "attack", "interact", "search", "explore", "follow", "drink", "wait", "rest"}
_BEARINGS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def _valid_targets(obs, verb="goto"):
    """obs 에 실제로 보이는 오브젝트 id 집합 — 환각 타겟 차단. 출구는 *보일 때만*(beacon 폐기).
    동료(b<char>)는 안 보여도 허용(파티 감각) — 하강 조율(데리러 가기)의 통로. 좌표는 여전히 비공개.
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
    for p in obs.get("party", []):          # 살아있는(안 내려간) 동료는 시야 밖이어도 핑 가능
        if p.get("alive") and not p.get("won"):
            ids.add("b%s" % p["char"])
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
    lines = ["## 너의 캐릭터",
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
    lines.append("- 시트의 성격·말투·목표·관계대로 판단하고 말하라.")
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
    s = str(tgt or "").replace("follow:", "")
    if s.startswith("b") and (names or {}).get(s[1:]):
        return names[s[1:]]
    return s


def _last_prose(last, names=None):
    """직전 결과(obs.last)를 1인칭 사실 문장으로 — show_runner.act_summary(관전 3인칭)의 자매.
    어휘 전거 = STREAM_FORMAT.md 이벤트 표. 모르는 형태는 컴팩트 JSON 폴백(정보 무소실 —
    미래 additive 필드의 안전망, verify_wire ③이 실전 폴백 0을 감시)."""
    t, r = last.get("type"), last.get("result")
    tgt = str(last.get("target", "") or "")
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
            " ".join(str(st[k]) for k in ("type", "target") if k in st) or "?")
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
        if r == "idle":
            return ("동행을 접었다 — %s이(가) 한동안 제자리라 같이 서 있기만 했다."
                    " 이제 뭘 할지 네가 정하라" % _tgt_name(tgt, names))
        if r == "arrived":
            if tgt and tgt.startswith("d") and tgt[1:].isdigit():
                # 문 핑 완결 = 이미 '지나 들어선' 상태(Door 계약) — "곁에 도착"으로 옮기면
                # 봇이 아직 안 넘었다고 믿고 같은 문을 재핑한다(암 B 2차 문턱 셔틀 패인)
                return "문 %s를 지나 들어섰다 — 지금 그 너머 공간 안이다" % tgt
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
                parts.append("아직 안 모였다(빠진 동료: 봇%s) — 기다리거나 데리러 가라"
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
            return "%s — 이미 곁이다" % (tgt or "?")
        if r == "no_path":
            if last.get("exhausted"):         # D19 개정: 보이는 새 길·기억의 계단·기억 속 안 가 본 문 전부 없음
                return ("탐색하려 했지만 — 새 길이 없다: 보이는 길은 전부 가 봤고,"
                        " 기억 속에도 안 가 본 문이 없다")
            return "탐색하려 했지만 — 지금 갈 수 있는 새 길이 없다"
        if r == "following":
            return "%s 곁에서 동행을 시작했다" % tgt
        if r == "pathed":
            return ("%s 쪽으로 걷기 시작했다" % tgt
                    if tgt and tgt != "auto" else "새 길로 걷기 시작했다")
    return json.dumps(last, ensure_ascii=False)        # 미지 형태 — 정직한 폴백(숨기지 않는다)


_TRAIL_RUNS = {"walking": "%d걸음 걸었다", "following": "%d틱 곁을 따라 걸었다",
               "waiting": "%d틱 기다렸다", "resting": "%d틱 쉬었다"}


def _trail_prose(trail, names=None):
    """궤적(D38, 09-06) — 마지막 결정 이후 일어난 일을 순서대로 ' → ' 로 잇는다.
    연속 걸음·동행·대기·휴식 틱은 'N걸음 걸었다' 꼴로 접고(그 사이 주운 보물·물약은 접미로 살린다),
    작정 집행 수는 '작정대로 ' 접두, 상한에 잘린 앞부분은 '…(n건 생략)'. 각 항목 문장은 _last_prose
    재사용 — 어휘 전거가 같아 새 폴백이 안 생긴다(verify_wire ③ 감시 그대로)."""
    parts, run = [], None                    # run = [result, n, 보물 n, 물약 n]

    def flush():
        if run:
            s = _TRAIL_RUNS[run[0]] % run[1]
            if run[2]:
                s += " — 길에서 보물을 주웠다" + (("(%d개)" % run[2]) if run[2] > 1 else "")
            if run[3]:
                s += " — 회복 물약도 챙겼다"
            parts.append(s)
    for e in trail:
        if not isinstance(e, dict):
            continue
        if e.get("type") == "gap":
            flush(); run = None
            parts.append("…(%d건 생략)" % int(e.get("n") or 0))
            continue
        r = e.get("result")
        if e.get("type") == "walk" and r in _TRAIL_RUNS:
            if run and run[0] == r:
                run[1] += 1
            else:
                flush(); run = [r, 1, 0, 0]
            run[2] += 1 if e.get("treasure") else 0
            run[3] += 1 if e.get("potion") else 0
            continue
        flush(); run = None
        parts.append(("작정대로 " if e.get("plan") else "") + _last_prose(e, names))
    flush()
    return " → ".join(parts)


# _wire 가 아는 obs 키 전부 — 밖의 키는 '그 밖의 정보' JSON 으로 정직하게 노출(조용한 누락 금지).
_WIRE_KEYS = frozenset((
    "pos", "hp", "maxhp", "job", "sex", "str", "dex", "inventory", "potions",
    "depth", "turn",
    "zone", "known", "witnessed", "memories", "dry", "last", "trail", "order", "ascii_view", "legend",
    "sights", "party", "options", "messages", "intent", "notes",
    "status",  # 상태 태그(D34): 아래 _wire "## 네 몸 상태" 절이 그린다
    "relations",   # 관계 장부(D36): 뼈 횟수·초대는 _wire, 살(한 줄)은 _sheet 가 그린다
    "exhausted",   # 탐색 소진(D19 개정 09-06): '탐색' 어휘 대신 사실 한 줄
    "town",    # 마을(D29): 안전한 층의 사실 한 줄 — 아래 _wire 가 그린다
    "gear"))   # 장비(07-30): 아는 키지만 wire 는 일부러 안 그린다 — 착용 정보의 표현은
               #   시트(_sheet 차림 줄, 불변 프리픽스=캐싱)가 소유하고, 비교는 입수 메뉴
               #   라벨에만 나온다(파트너 설계: 상시 가변부 미노출). 여기 등재를 빼면
               #   '그 밖의 정보' JSON 덤프로 매턴 새 나간다(화이트리스트 폴백)


def _wire(obs, names=None):
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
        return "동료 %s" % nm(char) if names.get(char) else "낯선 사람(봇%s)" % char

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
    L.append("- 너는 %s(%s) — HP %d/%d, 힘 +%d, 민첩 +%d, 모은 보물 %d개%s — 지금 %d층"
             % (obs.get("job", "?"), obs.get("sex", ""), obs.get("hp", 0), obs.get("maxhp", 0),
                obs.get("str", 0), obs.get("dex", 0), obs.get("inventory", 0),
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
                                 " (와 본 자리)" if f.get("visited") else ""))
        for t in s.get("traps", []):
            put(t.get("bearing"), t.get("dist", 0),
                "%s %dm (발각됨 — 위치를 안다)" % (t.get("name", "함정"), t.get("dist", 0)))
        for b in s.get("bots", []):
            put(b.get("bearing"), b.get("dist", 0),
                "%s(겉보기 %s) %dm%s" % (who(b.get("char", "?")),
                                         b.get("condition", "?"), b.get("dist", 0),
                                         " (이동중)" if b.get("moving") else ""))
        if under:
            L.append("- 발밑: " + " / ".join(under))
        KR = {"N": "북쪽", "NE": "북동쪽", "E": "동쪽", "SE": "남동쪽",
              "S": "남쪽", "SW": "남서쪽", "W": "서쪽", "NW": "북서쪽"}
        for b in order8:
            items = sorted(slots[b], key=lambda it: (it[0], it[1]))
            if items:
                L.append("- %s: %s" % (KR[b], ", ".join(t for _, t in items)))
                continue
            # 빈 방향의 정직화(07-15 정정): 전지 시절엔 침묵=벽이었지만, 이제 안 본 곳은
            # 벽이 아니라 미지다 — 시야 내 '미지로 트인' 방위(ways)는 트임으로 발화.
            wv = next((w for w in s.get("ways", []) if w.get("bearing") == b), None)
            if wv:
                L.append("- %s: 트여 있다 — 너머는 안 보인다%s"
                         % (KR[b], " (발자국 있는 길)" if wv.get("visited") else ""))
            else:
                L.append("- %s: 벽" % KR[b])
        for m in s.get("monsters", []):
            if m.get("lore"):
                L.append("  · %s 습성(네가 아는 것): %s" % (m.get("kind", "?"), m["lore"]))
    else:
        L += ["", "## 지금 보이는 것"]
        n0 = len(L)
        ex = s.get("exit")
        if ex:
            L.append("- 계단(exit) — %s" % at(ex))
        for m in s.get("monsters", []):
            L.append("- %s — %s" % (G._mfact(m), at(m)))
            if m.get("lore"):
                L.append("  · 네가 아는 습성: %s" % m["lore"])
        for f in s.get("features", []):
            L.append("- %s %s — %s%s" % (f.get("name", "?"), f.get("id", "?"), at(f),
                                         " (와 본 자리)" if f.get("visited") else ""))
        for b in s.get("bots", []):
            L.append("- %s — 겉보기 %s%s — %s%s%s"
                     % (who(b.get("char", "?")), b.get("condition", "?"),
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
    if pt:
        L += ["", "## 파티 명단"]
        for p in pt:
            if not p.get("alive"):
                st = "죽었다 — 이번 원정에는 돌아오지 않는다"   # D22 개정(09-06): 확정성 전달('구하러 올게' 유령 차단)
            elif p.get("won"):
                st = "먼저 내려갔다"
            elif p.get("visible"):
                st = "시야 안(위 목록에 있다)"
            else:
                st = "시야 밖 — 말은 안 닿고, 찾아갈 수는 있다(파티 감각)"
            L.append("- %s, %s — %s" % (nm(p.get("char", "?")), p.get("job", "?"), st))

    rels = obs.get("relations") or []
    if rels:                                # 관계 장부(D36) — 뼈 횟수(사실). 살은 시트에 산다
        L += ["", "## 동료와 겪은 일 (횟수 — 세계가 센 사실)"]
        for r in rels:
            bits = ["%s ×%d%s" % (b_.get("label", b_.get("kind", "?")), b_.get("n", 0),
                                 (" (%s)" % ago(b_["last"])) if b_.get("last") is not None else "")
                    for b_ in r.get("bones", [])]
            L.append("- %s: %s" % (nm(r.get("char", "?")), ", ".join(bits) if bits else "아직 없음"))

    k = obs.get("known")
    if k and (k.get("statics") or k.get("last_seen") or k.get("zones")):
        L += ["", "## 네가 기억하는 것 (이 층에서 직접 봄 — 지금은 시야 밖)"]
        for e in k.get("statics", []):
            L.append("- %s%s — %s에서 %s 봄%s"
                     % (e.get("name", "?"),
                        (" %s" % e["id"]) if e.get("id") else "",
                        e.get("zone", "?"), ago(e.get("turn", 0)),
                        "" if e.get("id") else " (위치만 기억해 둔 것)"))
        for e in k.get("last_seen", []):
            who = nm(e["char"]) if e.get("char") else (
                "%s %s" % (e.get("kind", "?"), e.get("id", "?")))
            L.append("- %s — %s에서 %s 마지막으로 봄 (지금도 거기 있단 보장은 없다)"
                     % (who, e.get("zone", "?"), ago(e.get("turn", 0))))
        zs = k.get("zones", [])
        if zs:
            L.append("- 가 본 방: " + ", ".join(x.get("id", "?") for x in zs))

    it, la, wit = obs.get("intent"), obs.get("last"), obs.get("witnessed")
    dry = obs.get("dry")
    trail = obs.get("trail") or []            # D38 궤적 — 마지막 결정 이후 일어난 일(순서). 1건이면 last 와 같다
    if it or la or wit or dry or trail:
        L += ["", "## 네 직전 판단과 그 결과 (네 자신의 기억)"]
        if it:
            line = "- 직전 판단%s: %s" % (("(t%d)" % it["turn"]) if it.get("turn") is not None else "",
                                          it.get("type", "?"))    # (tN) = D38 궤적 판만(얼마나 전의 판단인지)
            if it.get("target"):
                line += " %s" % it["target"]
            if it.get("reason"):
                line += ' — 이유: "%s"' % it["reason"]
            L.append(line)
            if it.get("say"):
                L.append('  그때 동료에게 한 말: "%s"' % it["say"])
        if len(trail) > 1:                    # 다건 = 궤적 체인. 1건이면 아래 구판 문장 그대로(핀 보호)
            L.append("- 그 뒤 일어난 일: " + _trail_prose(trail, names))
            bl = [e for e in trail if isinstance(e, dict) and e.get("bleed")]
            if bl:                            # 출혈(D34) — 걷는 동안 흘린 피(사실만), 마지막 값
                L.append("- 걷는 동안 출혈로 피를 흘렸다 — 남은 HP %d" % bl[-1]["bleed"].get("hp", 0))
        elif la:
            L.append("- 그 결과: %s" % _last_prose(la, names))
            if la.get("bleed"):                   # 출혈(D34) — 걷는 동안 흘린 피(사실만)
                L.append("- 걷는 동안 출혈로 피를 흘렸다 — 남은 HP %d" % la["bleed"].get("hp", 0))
        for w in (wit or []):
            L.append("- 네 눈으로 봤다: " + _witness_prose(w))
        if dry:                       # 무발견 신호(07-24) — 관찰 사실만(질문·조향 금지), 도달 1회
            L.append("- 한참을 걸었는데 새로 보이는 것이 없다 — 아는 자리만 이어진다")

    nts = obs.get("notes")
    if nts:                                 # D26 의미 기억 — 스스로 남긴 한 줄들(주관, 엔진 불가침)
        L += ["", "## 네가 기억해두기로 한 것 (스스로 남긴 한 줄 — 오래된 것부터 바랜다)"]
        for s2 in nts:
            L.append('- "%s"' % s2)

    mem = obs.get("memories")
    if mem:                                 # D22 기억층 — 휘발 0: 매 결정 다시 제시된다
        L += ["", "## 잊지 못할 일 (네가 목격하거나 알게 된 중대사)"]
        for e in mem:
            nm_ = "%s(봇%s)" % (e.get("name", "동료"), e.get("char", "?"))
            if e.get("kind") == "grave_found":      # 묘 발견 — 죽음을 못 봤어도 묘를 본 순간 안다
                L.append("- [%s의 죽음을 발견] %s — %s에서 (%s)"
                         % (nm_, e.get("grave", "묘"), e.get("zone", "?"), ago(e.get("turn", 0))))
            else:                                   # 목격 — 사인·장소(D22 기억층 v0=fallen)
                L.append("- [%s의 죽음을 목격] %s 죽었다 — %s에서 (%s)"
                         % (nm_, _by_phrase(e), e.get("zone", "?"), ago(e.get("turn", 0))))

    inv = next((r for r in (obs.get("relations") or []) if r.get("invite")), None)
    if inv:                                 # 살 초대(D36) — 강한 뼈 직후 또는 문턱 결정에만 칸이 생긴다
        who_ = nm(inv.get("char", "?"))
        why = {"rescued": "%s가 방금 너를 구했다" % who_,
               "at_death": "%s가 죽을 때 네가 곁에 있었다" % who_,
               }.get(inv["invite"], "%s와 그간 겪은 일이 쌓였다" % who_)
        L += ["", "## %s에 대해 남길 한 줄 (선택)" % who_,
              "- %s. %s에 대한 네 생각을 한 줄로 고쳐 써도 좋다 — 응답 JSON 의 `relation_line` 필드"
              " (안 써도 된다. 쓰면 이전 줄을 덮어 쓴다)" % (why, who_)]
        if inv.get("line"):
            L.append('- 지금까지의 한 줄: "%s" (%s)'
                     % (inv["line"], "시트" if inv.get("line_src") == "sheet"
                        else "네가 %s턴에 남긴 말" % inv.get("line_turn", "?")))

    ms = obs.get("messages")
    if ms:
        L += ["", "## 동료가 네게 한 말 (지난 턴)"]
        for m in ms:
            L.append('- %s: "%s"' % (nm(m.get("from", "?")), m.get("text", "")))

    extra = {kk: v for kk, v in obs.items() if kk not in _WIRE_KEYS}
    if extra:                       # 미래 additive 필드 — 조용한 누락 대신 정직한 노출
        L += ["", "## 그 밖의 정보", "```json",
              json.dumps(extra, ensure_ascii=False), "```"]
    return "\n".join(L)


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


def _fallback(obs, char, why="파싱 실패"):
    """엔진 규칙두뇌(dict 반환)에 say/reason/src 옷을 입혀 돌려준다.
    why = 실패 종류 라벨(타임아웃/빈 응답/JSON 불량/행동 해석 실패…) — 스트림·봇로그 계측."""
    fb = dict(G.dummy_brain(obs, char))            # {type, [dir]}
    fb.update(say="", reason="[폴백] %s -> 규칙두뇌" % why, src="fallback")
    return fb


def claude_brain(obs, char="?", bot=None, roster=None, solo=False):
    if bot is None:                          # 하위호환(구 시그니처): HEROES 로 유사 봇 구성
        h = G.HEROES.get(char, {})
        bot = {**h, "char": char, "maxhp": h.get("hp")}
    # D17-3: obs 는 JSON 덤프가 아니라 자기설명 문장(_wire)으로 나간다 — dict 계약은 불변.
    # options 는 _wire 가 렌더하지 않는다: 메뉴 모드=아래 번호 목록이 그것, 자유서술=비노출(순수성).
    names = {o["char"]: (o.get("name") or o.get("job", "동료")) for o in (roster or [])}
    if MENU:
        menu = "\n".join("%d. %s" % (o["n"], o["label"])
                         for o in (obs.get("options") or []))
        prompt = (_sheet(bot, roster) + "\n" + (MENU_PROMPT_SOLO if solo else MENU_PROMPT)
                  + "\n\n" + _wire(obs, names)
                  + "\n\n## 이번 턴 선택지 — 이 중 번호 하나를 골라라\n" + menu
                  + "\n\n오직 JSON 한 줄로만 답하라.")
    else:
        prompt = (_sheet(bot, roster) + "\n" + (ADV_PROMPT_SOLO if solo else ADV_PROMPT)
                  + "\n\n" + _wire(obs, names)
                  + "\n\n오직 JSON 한 줄로만 답하라.")
    res = _call_claude(prompt, "haiku")
    # verify/스모크가 _call_claude 를 str 반환 람다로 모킹한다 — 그 표면을 깨지 않는 하위호환.
    raw, why = res if isinstance(res, tuple) else (res, None)
    obj, jwhy = _extract(raw)
    why = why or jwhy
    if obj:
        then = _then(obj, obs)                      # 작정(D16) — 유효 수만 남긴 이어질 계획(없으면 [])
        note = (str(obj.get("note", "") or "").strip()[:NOTE_LEN]   # D26 남길 한 줄(선택 필드)
                if NOTES_ON else "")
        inv = next((r for r in (obs.get("relations") or []) if r.get("invite")), None)
        rline = (str(obj.get("relation_line", "") or "").strip()[:NOTE_LEN]   # D36 살 — 초대가 있을 때만
                 if inv else "")                                             #   받는다(에지 없는 콜은 무시)
        rel = {"relation": {"to": inv["char"], "line": rline}} if rline else {}
        if MENU:
            act = _pick(obj, obs)
            if act:
                if act["type"] == "follow":
                    then = []                       # 동행=열린 결말 — then 뒤수 부적합(D18 A-5)
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
    return _fallback(obs, char, why or "파싱 실패")


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


def think_all(d, bots, inbox=None):
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
        o["messages"] = inbox.get(b["char"], [])
        if b.get("intent"):
            o["intent"] = b["intent"]   # 판단 되먹임(D15①): 자기 직전 판단의 기억 — inbox와 같은
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
    by = {b["char"]: b for b in live}
    trail_on = bool(getattr(d, "trail_on", False))
    for c, dec in out.items():          # 이번 판단을 자기 기억으로 저장 → 다음 결정의 obs.intent.
        if trail_on and dec.get("src") == "plan":
            continue                     # D38(09-06): 작정 수는 궤적(trail)에 남는다 — 직전 판단은 마지막
                                         #   **실** 결정을 유지(09-06 마을 판: 미나의 '직전 판단'이 매번
                                         #   "[작정] 미리 정한 다음 수"라 자기 결정·결과가 두 수 전으로 사라졌다)
        it = {"type": dec.get("type", "")}   # bot_snapshot 화이트리스트 밖 = 스트림 계약 불변
        for k in ("target", "say", "reason", "src"):   # (직전 decisions에서 파생 가능한 값).
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
    if os.environ.get("DUNGEON_STREAM_OBS") == "1":
        # 스트림 opt-in: 결정에 '그때 그 봇이 본 것'(obs)을 병합 — think 시점 캡처.
        # 사후 d.view() 재호출로 얻으면 안 된다(시점 오염 + _perceive 부수효과).
        # 작정 수(src='plan')는 obs 미동봉 — view() 자체가 안 불렸다(그게 작정의 경제).
        for c in obss:
            if c in out:
                out[c] = {**out[c], "obs": obss[c]}
    return out
