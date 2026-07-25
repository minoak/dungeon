# -*- coding: utf-8 -*-
"""두뇌 백엔드 어댑터(2026-07-25) 검증 — 26번째 게이트.

왜 이 게이트가 필요한가: 어댑터 도입의 최대 위험은 FAIL 이 아니라 **"초록불인데 실 API 가
나가는" 유출**이다. 기존 25종은 저마다 `_call_claude` 를 몽키패치해 실 LLM 을 차단하지만,
"그 스텁이 실제로 백엔드를 가로막았는가"는 **아무도 검사하지 않는다**. 누군가 _call_claude 를
클래스 메서드로 내리거나 claude_brain 이 백엔드를 직접 부르게 리팩터링하면, 모킹이 조용히
무시되면서 게이트는 여전히 초록불인 채 실제 API 가 호출된다(과금·유출). ⑤가 그 자리를 막는다.

게이트:
  ① 기본값 = claude_cli (env 없이 import 하면 오늘까지의 판과 동일 경로)
  ② 시그니처 핀 = (prompt, model="haiku"), 위치인자 2개 — 15개 파일의 모킹 표면
  ③ 호출 방식 = 위치 2개·키워드 0 (verify_notes 의 `lambda p, m:` 모킹 보존)
  ④ 함수-안 디스패치 — import 이후의 env 변경이 즉시 반영(모듈 상수 바인딩 금지)
  ⑤ **유출 차단** — 표준 스텁이 백엔드보다 우선(백엔드 호출 0회)
  ⑥ 키 없는 프로세스는 소켓 열기 전에 끊는다(모킹 누락의 최후 방어선)
  ⑦ import 청결 — `import brains` 만으로 requests 가 안 올라온다(지연 import)
  ⑧ 라벨 문법 계약 — _test_fallback_labels 의 3대 부분문자열이 API 백엔드에서도 산다
  ⑨ 별칭→모델 id 매핑이 백엔드별로 갈린다
  ⑩ 비밀값 위생 — 라벨에 키·URL·예외 원문이 없다(state/·runs/ 가 실제로 커밋되는 레포)
  ⑪ 경고 위생 — 유효한 이름엔 stderr 침묵, 잘못된 이름은 정확히 1회
(기존 verify 25종은 별도 실행.)
"""
import io
import os
import re
import sys
import contextlib
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 게이트 자신의 환경 소독 ───────────────────────────────────────────────────
# 셸·tmux 서버에 남은 값이 이 프로세스에 상속될 수 있다(이 레포는 env 오염으로 두 번 데였다:
# start.sh 의 DUNGEON_STATE_DIR unset 두 번, verify.sh 의 BESTIARY unset).
os.environ.pop("DUNGEON_BRAIN_BACKEND", None)
os.environ.pop("DUNGEON_BRAIN_LOG", None)
_LEAKED = [k for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY") if os.environ.get(k)]
for _k in _LEAKED:
    os.environ.pop(_k)          # 이 프로세스에서 지운다 — 게이트가 실 API 를 때릴 물리적
                                #   수단 자체를 없앤다(⑥의 안전핀을 게이트에도 적용)
os.environ["DUNGEON_BESTIARY_FILE"] = ""            # 도감 영속 차단(게이트 격리 원칙)
os.environ["DUNGEON_STATE_DIR"] = os.path.join(HERE, "state_brainverify")

FAKE_KEY = "sk-ant-TESTKEY-DO-NOT-USE-0123456789"   # 라벨 오염 탐지용 지문

import brains                                        # noqa: E402
from dungeon_gm import Dungeon                        # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


ROWS = ["##########",
        "#1.2.....#",
        "#........#",
        "####>#####"]


def mkbot(char, x, y):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': []}


def stage():
    """실제 obs 한 개 — claude_brain 을 진짜 경로로 태우기 위해(verify_motion 선례)."""
    d, _ = Dungeon.from_ascii(ROWS, scan=False)
    bots = [mkbot('1', 1, 1), mkbot('2', 3, 1)]
    for b in bots:
        d.view(b, bots)
    return d, bots


_ORIG_CALL = brains._call_claude
_ORIG_POST = brains._http_post
_ORIG_BE = {n: getattr(brains, "_call_" + n.split("_")[0]) for n in ()}   # 자리표시(아래서 채움)
_BACKEND_FNS = {"claude_cli": "_call_cli", "anthropic_api": "_call_anthropic",
                "gemini_api": "_call_gemini", "dummy": "_call_dummy"}
_ORIG_BE = {k: getattr(brains, v) for k, v in _BACKEND_FNS.items()}


def restore():
    brains._call_claude = _ORIG_CALL
    brains._http_post = _ORIG_POST
    for k, v in _BACKEND_FNS.items():
        setattr(brains, v, _ORIG_BE[k])
    os.environ.pop("DUNGEON_BRAIN_BACKEND", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)


print("== 두뇌 백엔드 어댑터 검증 ==")

# ───────────────────────── ① 기본값 ─────────────────────────
check("① env 없으면 기본 백엔드 = claude_cli (오늘까지의 판과 동일 경로)",
      brains.backend_name() == "claude_cli")

# ───────────────────────── ② 시그니처 핀 ─────────────────────────
import inspect                                        # noqa: E402
_sig = inspect.signature(_ORIG_CALL)
check("② _call_claude 시그니처 = (prompt, model='haiku') — 15개 파일의 모킹 표면",
      list(_sig.parameters) == ["prompt", "model"]
      and _sig.parameters["model"].default == "haiku"
      and all(p.kind is p.POSITIONAL_OR_KEYWORD for p in _sig.parameters.values()))

# ───────────────────────── ③ 호출 방식(위치 2개) ─────────────────────────
d, bots = stage()
obs = d.view(bots[0], bots)
seen = {}
brains._call_claude = lambda *a, **k: (seen.update(a=a, k=k), ("", None))[1]
brains.claude_brain(obs, "1", bots[0], bots)
check("③ claude_brain 은 위치인자 2개·키워드 0 으로 부른다"
      " (verify_notes 의 `lambda p, m:` 모킹이 살아야 한다)",
      len(seen.get("a", ())) == 2 and not seen.get("k") and seen["a"][1] == "haiku")

brains._call_claude = lambda p, m: ""     # 구식 str 반환·위치 2개 모킹 하위호환
check("③ `lambda p, m:` 형 모킹이 그대로 통한다(폴백으로 떨어짐)",
      brains.claude_brain(obs, "1", bots[0], bots)["src"] == "fallback")
restore()

# ───────────────────────── ④ 함수-안 디스패치 ─────────────────────────
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"         # brains 는 이미 import 됐다
check("④ import 이후 env 변경이 즉시 반영(모듈 로드 시점 바인딩 아님) —"
      " 게이트의 '스텁 먼저, 러너 나중 import' 관용구 보존",
      brains.backend_name() == "dummy"
      and brains._call_claude("x")[1] == "빈 응답 rc=0")
restore()
check("④ 소독 후 기본값 복귀", brains.backend_name() == "claude_cli")

# ───────────────────────── ⑤ 유출 차단(핵심) ─────────────────────────
hits = {"n": 0}


def _tripwire(name):
    def f(prompt, model):
        hits["n"] += 1
        return "", "호출 실패 Tripwire"
    return f


os.environ["DUNGEON_BRAIN_BACKEND"] = "anthropic_api"
os.environ["ANTHROPIC_API_KEY"] = FAKE_KEY     # 키를 *일부러* 넣는다 — NoAPIKey 단락에 기대지
for k, v in _BACKEND_FNS.items():              #   않고 순수하게 '스텁이 이겼는가'만 본다
    setattr(brains, v, _tripwire(k))
brains._call_claude = lambda prompt, model="haiku": ""    # 15개 파일의 표준 스텁
for _ in range(3):
    brains.claude_brain(obs, "1", bots[0], bots)
check("⑤ 표준 스텁이 백엔드보다 우선 — 백엔드 호출 0회 (초록불 유출 차단)",
      hits["n"] == 0)
restore()

# ───────────────────────── ⑥ 키 없음 단락 ─────────────────────────
def _boom(url, headers, body):
    raise AssertionError("실 API 유출! 키 없는 프로세스에서 소켓이 열렸다")


brains._http_post = _boom
os.environ["DUNGEON_BRAIN_BACKEND"] = "anthropic_api"
os.environ.pop("ANTHROPIC_API_KEY", None)
try:
    _lbl = _ORIG_CALL("프롬프트", "haiku")[1]          # 스텁 없이 진짜 경로
    _ok6a = _lbl == "호출 실패 NoAPIKey"
except AssertionError:
    _ok6a = False
os.environ["DUNGEON_BRAIN_BACKEND"] = "gemini_api"
os.environ.pop("GEMINI_API_KEY", None)
try:
    _ok6b = _ORIG_CALL("프롬프트", "haiku")[1] == "호출 실패 NoAPIKey"
except AssertionError:
    _ok6b = False
check("⑥ 키 없는 프로세스는 소켓 열기 전에 끊는다 — 모킹 누락의 최후 방어선(anthropic)", _ok6a)
check("⑥ 같은 방어선(gemini)", _ok6b)
restore()

# ───────────────────────── ⑦ import 청결 ─────────────────────────
_r = subprocess.run([sys.executable, "-c",
                     "import sys, brains; print('requests' in sys.modules)"],
                    capture_output=True, text=True, cwd=HERE)
check("⑦ `import brains` 만으로 requests 가 안 올라온다(지연 import) —"
      " 최상단 import 면 미설치 환경에서 게이트 20종이 한꺼번에 무너진다",
      _r.stdout.strip().endswith("False"))

# ───────────────────────── ⑧ 라벨 문법 계약 ─────────────────────────
CASES = [(401, {"error": {"type": "authentication_error"}}, "빈 응답 rc=401"),
         (429, {"error": {"type": "rate_limit_error"}},     "빈 응답 rc=429"),
         (500, {"error": {"type": "api_error"}},            "빈 응답 rc=500"),
         (529, {"error": {"type": "overloaded_error"}},     "빈 응답 rc=529"),
         (200, {"content": [], "stop_reason": "refusal"},   "빈 응답 rc=200"),
         (200, {"content": [{"type": "text", "text": ""}]}, "빈 응답 rc=200")]
os.environ["DUNGEON_BRAIN_BACKEND"] = "anthropic_api"
os.environ["ANTHROPIC_API_KEY"] = FAKE_KEY
labels = []
for st, body, want in CASES:
    brains._http_post = (lambda s, b: (lambda u, h, j: (s, b, None)))(st, body)
    lbl = _ORIG_CALL("프롬프트", "haiku")[1]
    labels.append(lbl)
    if not (lbl or "").startswith(want):
        check("⑧ HTTP %s -> %r (기대 %r 로 시작)" % (st, lbl, want), False)
brains._http_post = lambda u, h, j: (None, None, "타임아웃 %ds" % 60)
labels.append(_ORIG_CALL("프롬프트", "haiku")[1])
brains._http_post = lambda u, h, j: (None, None, "호출 실패 ConnectionError")
labels.append(_ORIG_CALL("프롬프트", "haiku")[1])

check("⑧ HTTP 에러코드가 전부 'rc=' 문법으로 번역된다"
      " (report.decision_board 버킷이 401/429/500/529 를 따로 센다)",
      len({l.split(" | ")[0] for l in labels if "rc=" in l}) >= 4)
check("⑧ _test_fallback_labels 의 3대 부분문자열이 API 백엔드에서도 산다",
      all(any(s in l for l in labels if l)
          for s in ("타임아웃 ", "빈 응답 rc=", "호출 실패 ")))
check("⑧ 타임아웃 라벨 = '타임아웃 <초>s'",
      any(re.fullmatch(r"타임아웃 \d+s", l or "") for l in labels))
restore()

# ───────────────────────── ⑨ 별칭 매핑 ─────────────────────────
check("⑨ 'haiku' 별칭이 백엔드별로 갈린다(CLI 어휘 ≠ API 모델 id)",
      brains._MODEL_ID["anthropic_api"]["haiku"] == "claude-haiku-4-5"
      and brains._MODEL_ID["gemini_api"]["haiku"].startswith("gemini"))

os.environ["DUNGEON_BRAIN_BACKEND"] = "anthropic_api"
os.environ["ANTHROPIC_API_KEY"] = FAKE_KEY
_sent = {}
brains._http_post = lambda u, h, j: (_sent.update(url=u, hdr=h, body=j), (200, {
    "content": [{"type": "text", "text": '{"choice": 1}'}]}, None))[1]
_ORIG_CALL("프롬프트", "haiku")
check("⑨ 요청 바디의 model = claude-haiku-4-5 (별칭이 그대로 새어나가지 않는다)",
      _sent["body"]["model"] == "claude-haiku-4-5")
check("⑨ 프롬프트는 user 메시지 하나로 통째 전송(claude.exe stdin 과 같은 바이트)",
      len(_sent["body"]["messages"]) == 1
      and _sent["body"]["messages"][0]["content"] == "프롬프트"
      and "system" not in _sent["body"])

os.environ["DUNGEON_BRAIN_BACKEND"] = "anthropic_api"
os.environ["DUNGEON_ANTHROPIC_MODEL"] = "claude-sonnet-4-6"
_ORIG_CALL("프롬프트", "haiku")
check("⑨ DUNGEON_ANTHROPIC_MODEL 이 별칭 표를 우회한다(gm.py DUNGEON_GM_MODEL 선례)",
      _sent["body"]["model"] == "claude-sonnet-4-6")
os.environ.pop("DUNGEON_ANTHROPIC_MODEL", None)
restore()

# ───────────────────────── ⑩ 비밀값 위생 ─────────────────────────
check("⑩ 라벨에 키 지문이 없다", all(FAKE_KEY not in (l or "") and "sk-ant" not in (l or "")
                                     for l in labels))
check("⑩ 라벨에 URL·호스트가 없다",
      all(not any(s in (l or "") for s in ("http", "api.anthropic.com", "googleapis"))
          for l in labels))
check("⑩ '호출 실패' 라벨은 예외 타입명만(원문 아님) — state/·runs/ 가 커밋되는 레포",
      all(re.fullmatch(r"호출 실패 [A-Za-z]+", l) for l in labels
          if (l or "").startswith("호출 실패")))
check("⑩ _errtag 는 화이트리스트 모양만 통과시킨다(자유문 차단)",
      brains._errtag("rate_limit_error") == " | rate_limit_error"
      and brains._errtag("키가 sk-ant-xxx 라서 실패했습니다") == ""
      and brains._errtag("http://evil.example/?k=1") == "")

# ───────────────────────── ⑪ 경고 위생 ─────────────────────────
_buf = io.StringIO()
with contextlib.redirect_stderr(_buf):
    for name in brains.BACKENDS:
        os.environ["DUNGEON_BRAIN_BACKEND"] = name
        brains.backend_name()
check("⑪ 유효한 백엔드 이름에선 stderr 한 글자도 안 나온다"
      " (_run_gates.sh 가 `2>&1 | tail -1` 로 판정 — 경고 한 줄이 통과를 FAIL 로 뒤집는다)",
      _buf.getvalue() == "")

_buf2 = io.StringIO()
with contextlib.redirect_stderr(_buf2):
    os.environ["DUNGEON_BRAIN_BACKEND"] = "nonsense"
    for _ in range(5):
        _fell_back = brains.backend_name() == "claude_cli"
check("⑪ 잘못된 값은 claude_cli 로 퇴화(판을 죽이지 않는다)", _fell_back)
check("⑪ 그 경고는 정확히 1회(콜마다 찍으면 판정줄이 오염된다)",
      _buf2.getvalue().count("[경고]") == 1)
restore()

if _LEAKED:      # ALL PASS 앞에서 낸다 — 마지막 줄이 되지 않게
    print("[알림] 셸 env 에 %s 가 있었다 — 이 게이트에선 제거했다. 키는 .env 에만 두라"
          % ",".join(_LEAKED), file=sys.stderr)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_brain (백엔드 어댑터: 모킹 표면 불변·유출 차단·라벨 계약·비밀값 위생)")
