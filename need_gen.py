# -*- coding: utf-8 -*-
"""욕구 생성 호출(p0.5.20 — .orch/drafts/economy_design.md §3.8.2·§3.8.6 · §10-12·16·22·24·25, DECISIONS 10-15·10-16).

캐릭터를 저장하거나 출발할 때 모델을 **한 번** 불러 시트 글(이름·직업·성별·성격·배경)을 읽고, 욕구마다 무게 등급(낮음·보통·높음)과
입맛(좋아함·싫어함 꼬리표)을 정한다. 결과는 시트 칸 셋에 남는다 — 판 중에는 부르지 않는다(같은 시트면 판마다 같다).
  · 시트 칸: needs{욕구: {level, why?, src: model|user|fallback}} · taste{likes, dislikes} · needs_meta{by, model?, at, ok, prompt, of}.
    엔진은 needs 의 level 과 taste 만 읽는다(needs.fields — 스폰). why·needs_meta 는 론처 화면과 판 기록(run_meta.party[])에만 간다 —
    게임 프롬프트에는 안 나간다(§3.8.6).
  · 욕구 목록 = entities/need/*.json 전부(아직 엔진에 단계가 없는 '준비 중' 욕구도 — 미리 채운다, §3.2 끝).
  · 낡음: of(시트 글 해시)가 지금 글과 다르거나, prompt(이 프롬프트 + 욕구 뜻·어휘 해시)가 다르면 낡은 것. 출발 때는 표시만 한다(§10-25).
  · 검증(0콜 — 모델 답의 꼴만 본다, 성격 해석 규칙은 없다): 등급 셋 밖 → 그 욕구만 보통(fallback) · 목록 밖 id 는 버린다 · 빠진 욕구는 보통(fallback) ·
    why 는 sanitize_freetext 뒤 한 줄 needs.WHY_MAX 자 · 꼬리표는 어휘 안의 것만 받고 겹치면 싫어함에서 뺀다 · 좋아함 2·싫어함 1을 넘거나 꼴이 틀리면 빈 입맛 ·
    JSON 이 아니면 전부 보통 + 빈 입맛 + ok:false ·
    (p0.5.21) 보통이 아닌데 why 가 비었거나 근거 없음 표시(NO_WHY — 프롬프트 {no_why} 자리와 같은 값, 앞뒤 공백·따옴표·마침표와 낱말 사이 공백은 빼고 맞댄다)면
    그 욕구만 보통(fallback — why 는 그대로 둔다. 화면에 '보통 · 글에 없다'로 보여 모델이 스스로 보통이라 한 줄과 같은 꼴이다).
  · 호출: 그 판(화면에서 고른) 두뇌·모델 그대로(§10-24). 러너와 같은 brains._call_claude 를 **자식 프로세스**에서 부른다 — 키는 그 프로세스 env 에만
    있고 론처·공개 서버 프로세스의 환경에 섞이지 않는다(러너와 같은 규칙). dummy 두뇌는 부르지 않고 전부 보통(by:'dummy' — '정한 것'으로 치지 않는다).
  · 실패(§3.8.2 표): 키 없음·인증·연결 실패 → NeedGenError(출발이면 출발을 멈춘다 · 저장이면 needs 없이 저장한다) · 시간 초과·서버 오류 → 한 번 다시 ·
    모델 거절·빈 답 → 전부 보통 + ok:false(막지 않는다) · 꼴 틀림 → 그 칸만 fallback.
LLM: 순수 함수는 0콜. 호출은 call_model 한 곳(게이트는 이것만 바꿔 끼운다 — 바꿔 끼우지 않으면 자식 프로세스가 진짜 두뇌를 부른다).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import entities as ENT
import needs as NE
import sheetkit
from brain_config import KEY_ENV, MODEL_ENV

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_FILE = os.path.join("prompts", "launcher", "need_gen.md")   # D100 — 문장은 prompts/ 안(게임 프롬프트가 아니라 론처의 호출)
SRCS = ("model", "user", "fallback")      # needs[].src — 모델이 정함 · 사람이 고침 · 검증이 보통으로 채움
SHEET_KEYS = ("name", "job", "sex", "persona", "background")   # 생성 호출의 재료 = 낡음 해시(of)의 재료(§3.8.2 입력 표)
HASH_LEN = 16
CALL_TIMEOUT = 180       # 자식 프로세스 상한(초) — 안쪽 HTTP·CLI 는 brains 의 제 상한(기본 60초)이 먼저 끊는다. 한 번 다시 부르기는 generate 가 한다
EMPTY_TASTE = {"likes": [], "dislikes": []}
NO_WHY = "글에 없다"      # 근거 없음 표시 — 이 값 하나를 프롬프트 {no_why} 자리(모델에게 시키는 글)와 검증(no_basis)이 같이 쓴다
_NO_WHY_EDGE = " \"'“”‘’「」『』.。"   # no_basis 가 맞대기 전에 앞뒤에서 걷는 글자(공백·따옴표·마침표)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SLOT = re.compile(r"\{(name|job|sex|persona|background|needs|tastes|likes_max|dislikes_max|why_max|no_why)\}")   # 프롬프트의 자리(그 밖 중괄호 — JSON 예시 — 는 그대로)
_JSON = re.compile(r"\{.*\}", re.S)
_RC = re.compile(r"rc=(\d+)")

# ⚠️ 론처 화면에 나가는 사람용 문장(임시) — %s = brains 의 실패 라벨(키·주소는 들지 않는다)
FAIL_START = "출발 전 연결 확인에 실패했다(%s). 판도 같은 키·모델로 돈다 — 키와 모델을 확인해 줘."
FAIL_GEN = "욕구를 정하지 못했다(%s). 키와 모델을 확인해 줘."


class NeedGenError(Exception):
    """모델에 닿지 못했다(키 없음·인증·연결 — 다시 불러도 같은 실패). label = brains 의 실패 라벨."""

    def __init__(self, label):
        super().__init__(label)
        self.label = label


# ── 목록 · 프롬프트 · 해시 ─────────────────────────────────────────────

def need_list():
    """생성 호출의 욕구 목록 [{id, name, about, ready}] — 욕구 정의 전부(id 순). ready = 엔진에 단계가 있다(없으면 화면에 '준비 중')."""
    return [{"id": d["id"], "name": d["name"], "about": (d["comps"]["need"] or {}).get("about") or "",
             "ready": bool((d["comps"]["need"] or {}).get("stages"))} for d in NE.all_defs()]


def ui():
    """론처 화면 '욕구와 입맛'이 읽는 것(/api/presets.needs_ui) — 목록·등급·입맛 어휘·상한."""
    return {"needs": need_list(), "levels": list(ENT.NEED_LEVELS), "default": NE.DEFAULT_LEVEL, "tastes": NE.tastes(),
            "likes_max": NE.LIKES_MAX, "dislikes_max": NE.DISLIKES_MAX, "why_max": NE.WHY_MAX}


def template():
    with open(os.path.join(HERE, PROMPT_FILE), encoding="utf-8") as f:
        return _COMMENT.sub("", f.read()).strip() + "\n"


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:HASH_LEN]


def prompt_hash():
    """needs_meta.prompt — 프롬프트 글(주석 걷은 것) + 욕구 목록의 뜻(id·이름·about) + 입맛 어휘 + 등급 + 근거 없음 표시. 하나라도 바뀌면 정한 욕구가 낡는다."""
    return _hash({"prompt": template(), "needs": [[n["id"], n["name"], n["about"]] for n in need_list()],
                  "tastes": NE.tastes(), "levels": list(ENT.NEED_LEVELS), "no_why": NO_WHY})


def sheet_text(sheet):
    """시트 → 생성 호출의 재료 {이름·직업·성별·성격·배경}(정제 — 한 줄 · 마크다운 표식 없음. 조립된 시트면 그대로다)."""
    out = {}
    for k in SHEET_KEYS:
        v = sheet.get(k)
        out[k] = (sheetkit.sanitize_freetext(v, sheetkit.BACKGROUND_MAX) or "") if isinstance(v, str) else ""
    return out


def sheet_hash(sheet):
    """needs_meta.of — 시트 글 해시. 저장 캐릭터 슬롯은 build_sheet 를 거친 시트(성격 = 키워드 + 서술)로 잰다 — 파티 시트와 같은 값."""
    return _hash(sheet_text(sheet))


def build_prompt(sheet):
    """시트 하나 → 생성 호출 프롬프트. 값이 빈 자리가 든 줄은 빠진다(배경이 없으면 배경 줄이 없다)."""
    vals = dict(sheet_text(sheet),
                needs="\n".join("- %s(%s): %s" % (n["id"], n["name"], n["about"]) for n in need_list()),
                tastes=" · ".join(NE.tastes()), likes_max=str(NE.LIKES_MAX), dislikes_max=str(NE.DISLIKES_MAX), why_max=str(NE.WHY_MAX),
                no_why=NO_WHY)
    out = []
    for ln in template().split("\n"):
        if any(not vals[k] for k in _SLOT.findall(ln)):
            continue
        out.append(_SLOT.sub(lambda m: vals[m.group(1)], ln))
    return "\n".join(out)


# ── 검증 ──────────────────────────────────────────────────────────────

def all_normal():
    return {n["id"]: {"level": NE.DEFAULT_LEVEL, "src": "fallback"} for n in need_list()}


def clean_why(v):
    """근거 한 줄 — sanitize_freetext(개행·표식 제거) 뒤 WHY_MAX 자. 비면 None."""
    if not isinstance(v, str):
        return None
    s = sheetkit.sanitize_freetext(v, sheetkit.BACKGROUND_MAX)
    return s[:NE.WHY_MAX] if s else None


def no_basis(why):
    """근거가 없나 — 정제한 근거(clean_why 의 값)가 비었거나, 앞뒤 공백·따옴표·마침표를 걷고 낱말 사이 공백을 빼면 비거나 NO_WHY 와 같다.
    '글에 없다고 보기 어렵다'처럼 표시를 품은 다른 글은 근거로 친다(통째로 같을 때만)."""
    s = "".join((why or "").strip(_NO_WHY_EDGE).split())
    return not s or s == "".join(NO_WHY.split())


def clean_taste(t):
    """입맛 — 어휘 안의 꼬리표만(중복 없이) · 겹치면 싫어함에서 뺀다 · 좋아함 LIKES_MAX·싫어함 DISLIKES_MAX 를 넘거나 꼴이 틀리면 빈 입맛."""
    if not isinstance(t, dict):
        return dict(EMPTY_TASTE)
    likes, dis = t.get("likes", []), t.get("dislikes", [])
    if not (isinstance(likes, list) and isinstance(dis, list) and all(isinstance(x, str) for x in likes + dis)):
        return dict(EMPTY_TASTE)
    vocab = NE.tastes()
    likes = [x for i, x in enumerate(likes) if x in vocab and x not in likes[:i]]
    dis = [x for i, x in enumerate(dis) if x in vocab and x not in dis[:i] and x not in likes]
    if len(likes) > NE.LIKES_MAX or len(dis) > NE.DISLIKES_MAX:
        return dict(EMPTY_TASTE)
    return {"likes": likes, "dislikes": dis}


def parse(raw):
    """모델의 답 → (needs, taste, ok). 첫 { 부터 마지막 } 까지를 JSON 으로 읽는다(코드 울타리·앞뒤 말 무시). JSON 객체가 아니면 전부 보통 + 빈 입맛 + ok False."""
    m = _JSON.search(raw or "")
    try:
        obj = json.loads(m.group(0)) if m else None
    except ValueError:
        obj = None
    if not isinstance(obj, dict):
        return all_normal(), dict(EMPTY_TASTE), False
    got = obj.get("needs") if isinstance(obj.get("needs"), dict) else {}
    out = {}
    for n in need_list():
        e = got.get(n["id"])
        if isinstance(e, dict) and e.get("level") in ENT.NEED_LEVELS:
            row = {"level": e["level"], "src": "model"}
            why = clean_why(e.get("why"))
            if why:
                row["why"] = why
            if row["level"] != NE.DEFAULT_LEVEL and no_basis(why):    # 근거 없는 낮음·높음 — 프롬프트 규칙 '근거를 찾지 못하면 보통'(why 는 그대로)
                row.update(level=NE.DEFAULT_LEVEL, src="fallback")
        else:
            row = {"level": NE.DEFAULT_LEVEL, "src": "fallback"}
        out[n["id"]] = row
    return out, clean_taste(obj.get("taste")), True


# ── 시트 칸 · 낡음 ─────────────────────────────────────────────────────

def meta(sheet, by, model, ok):
    m = {"by": by, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": bool(ok), "prompt": prompt_hash(), "of": sheet_hash(sheet)}
    if model:
        m["model"] = str(model)
    return m


def has(sheet):
    """정한 욕구가 있나 — needs 칸이 있고, dummy 두뇌가 채운 '전부 보통'이 아니다(dummy 결과는 정한 것으로 치지 않는다 — 다음 진짜 두뇌가 정한다)."""
    return bool(isinstance(sheet.get("needs"), dict) and sheet["needs"]) and (sheet.get("needs_meta") or {}).get("by") != "dummy"


def state(sheet):
    """{state: none|fresh|stale, why: [sheet|prompt]} — none = 정한 적 없다 · stale = 시트 글이나 프롬프트(욕구 뜻)가 정한 뒤 바뀌었다.
    needs_meta 가 없는 손 시트는 판단할 재료가 없어 fresh 다."""
    if not has(sheet):
        return {"state": "none", "why": []}
    m = sheet.get("needs_meta") or {}
    why = [w for w, bad in (("sheet", m.get("of") and m["of"] != sheet_hash(sheet)),
                            ("prompt", m.get("prompt") and m["prompt"] != prompt_hash())) if bad]
    return {"state": "stale" if why else "fresh", "why": why}


def sheet_of_slot(slot, data=None):
    """저장 캐릭터 슬롯(화면의 칸) → 조립된 시트(성격 = 키워드 + 서술 · 욕구 칸 셋 포함). 틀린 슬롯은 ValueError(build_sheet 그대로)."""
    if not isinstance(slot, dict):
        raise ValueError("캐릭터 설정은 객체여야 한다")
    try:
        return sheetkit.build_sheet(slot.get("job"), slot.get("traits") or [], slot.get("name", ""), slot.get("sex"), slot.get("background"),
                                    data=data, persona_text=slot.get("persona"), look=slot.get("look"),
                                    needs=slot.get("needs"), taste=slot.get("taste"), needs_meta=slot.get("needs_meta"))
    except (TypeError, KeyError) as e:
        raise ValueError("캐릭터 설정 형식이 올바르지 않다") from e


# ── 호출 ──────────────────────────────────────────────────────────────

def _kind(label):
    """실패 라벨 → retry(시간 초과·서버 오류·속도 제한 — 한 번 다시) · empty(모델이 답했는데 비었다·거절) · fail(키 없음·인증·연결 — 그 밖 전부)."""
    if label.startswith("타임아웃"):
        return "retry"
    m = _RC.search(label)
    if label.startswith("빈 응답") and m:
        rc = int(m.group(1))
        if rc in (0, 200):
            return "empty"
        if rc == 429 or rc >= 500:
            return "retry"
    return "fail"


def generate(sheet, brain, call):
    """시트 하나 → 칸 셋 {needs, taste, needs_meta}. call(prompt) → (text, label, model). 모델에 닿지 못하면 NeedGenError(label)."""
    if brain == "dummy":
        return {"needs": all_normal(), "taste": dict(EMPTY_TASTE), "needs_meta": meta(sheet, "dummy", None, True)}
    prompt = build_prompt(sheet)
    text, label, model = call(prompt)
    if not text and _kind(label) == "retry":
        text, label, model = call(prompt)
    if text:
        nd, tt, ok = parse(text)
    elif _kind(label) == "empty":
        nd, tt, ok = all_normal(), dict(EMPTY_TASTE), False
    else:
        raise NeedGenError(label or "호출 실패")
    return {"needs": nd, "taste": tt, "needs_meta": meta(sheet, brain, model, ok)}


def call_env(brain, model=None, key=None, extra=None):
    """자식 프로세스 env — 부모 env(로컬 론처: .env 의 키) + extra(공개 서버: 키 칸을 비우고 요청의 키 하나) + 두뇌·모델(러너와 같은 칸).
    대체 두뇌 없음(그 두뇌의 연결을 보는 호출이다) · 판의 두뇌 계측 파일에 섞이지 않는다."""
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (extra or {}).items()})
    env.update(PYTHONUTF8="1", DUNGEON_BRAIN_BACKEND=brain, DUNGEON_BRAIN_FALLBACK="", DUNGEON_BRAIN_LOG="")
    if key:
        env.update({k: "" for k in KEY_ENV.values()})
        env[KEY_ENV[brain]] = key
    if model is not None:
        for k in MODEL_ENV:
            env[k] = model
    return env


def call_model(prompt, env):
    """자식 프로세스에서 brains._call_claude(prompt, 'haiku') 한 번 — 러너와 같은 두뇌·모델 해석·실패 라벨. → (text, label, model)."""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "need_gen.py"), "--call"], input=json.dumps({"prompt": prompt}, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=HERE, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "", "타임아웃 %ds" % CALL_TIMEOUT, None
    except OSError as e:
        return "", "호출 실패 %s" % type(e).__name__, None
    for ln in reversed((r.stdout or "").strip().splitlines()):
        try:
            o = json.loads(ln)
        except ValueError:
            continue
        if isinstance(o, dict) and "label" in o:
            return str(o.get("text") or ""), str(o.get("label") or ""), o.get("model")
    return "", "호출 실패 NeedGenChild", None


def _child():
    """--call: stdin {prompt} → stdout 한 줄 {text, label, model, backend}. 두뇌 모듈은 여기서만 싣는다(론처 프로세스는 brains 를 import 하지 않는다)."""
    req = json.loads(sys.stdin.read() or "{}")
    import brains
    out, why = brains._call_claude(str(req.get("prompt") or ""), "haiku")
    sys.stdout.write(json.dumps({"text": out or "", "label": why or "", "model": brains.model_name(), "backend": brains.backend_name()},
                                ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["--call"]:
        _child()
    else:
        print("need_gen.py 는 론처가 부른다(--call). 동료·기본 파티에 적는 도구는 tools/need_gen.py", file=sys.stderr)
        raise SystemExit(2)
