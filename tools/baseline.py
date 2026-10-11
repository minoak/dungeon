# -*- coding: utf-8 -*-
"""단계 기준선 산출·비교 도구(master_plan §10.2-1·4, p0.5.3 — LLM 0콜).

스위치 없이 패치를 들이므로 "이 단계가 무엇을 바꿨나"를 기준선 차이로 가른다. 이 도구는 그 기준선을 뜨고 비교한다.

산출(capture) — 한 커밋(또는 작업 트리)의 코드를 **리포 밖 임시 폴더**에 그대로 풀어 놓고 거기서 돌린다
(루트의 개인 파일·state/·runs/ 를 건드리지 않고, 게이트가 트리 안에 쓰는 파일도 사본에만 남는다):
  · 판 3개(고정 시드·더미 두뇌, 론처가 실제로 주는 환경변수 그대로): stream.jsonl(관측 동봉) · 완성 프롬프트(LLM 에 갈 글 전부) ·
    마지막 스냅샷의 구조 요약(몸 dict 전체·시트·최상위 칸·판형) · 스냅샷 요약 json(러너가 쓴 바이트 그대로) · 이벤트 로그 · 환경변수
  · 기존 게이트 전부(_run_gates.sh 의 목록 그대로 + tools/check_words.py): 종료 코드 · 마지막 줄 · 출력(줄 끝 그대로, 실행마다 바뀌는 값만 덮음)
비교(diff) — 같은 이름의 두 산출을 **바이트로** 맞댄다. 다르면 반드시 차이 항목이 생긴다(줄 끝·끝 개행·JSON 직렬화 차이 포함 — 줄 단위·경로 단위
표시는 그 차이를 읽기 쉽게 나눈 것일 뿐이다). 차이 하나하나를 설명 규칙(--explain)에 대 본다: 규칙은 범위·경로와 **전·후 원문**(정확히 같거나
정규식 전체 일치)을 다 맞춰야 걸린다. 걸린 차이는 (가) 설명됨(그 단계의 의도 또는 원인을 확인한 실행 잡음), 안 걸린 차이는 (나) 설명 못 함.
규칙(설명)을 쓰는 것은 사람(구현·리뷰)이다. 실행마다 바뀌는 값(시각·소요 시간·사본 경로·임시 폴더·pid·uuid·계정 표식)은 비교 전에 덮는다.

쓰는 법(리포 루트에서):
  python tools/baseline.py capture --rev HEAD --label p053-before --fresh       # 판 + 게이트 전부(앞선 같은 label 산출을 지우고 새로)
  python tools/baseline.py capture --rev HEAD --label p053-before --part gates --chunk 2/4   # 10분 넘는 실행은 나눠서(같은 코드끼리만 합친다)
  python tools/baseline.py capture --rev WORKTREE --label p053-after --fresh    # 작업 트리(커밋 전 변경 포함)
  python tools/baseline.py diff p053-before p053-after --explain rules.json --out report.md [--dump occurrences.json]
결과: ab_runs/baseline/<label>/ (manifest.json · runs/<판>/ · gates/<게이트>.txt) — ab_runs/ 는 .gitignore.
사본: <임시 폴더>/wl_baseline/<label>/src. label 은 이름만(영숫자로 시작·끝, 영숫자·_·-·. 64자, '..' 금지) — 두 폴더 밖으로 못 나간다.
같은 label 에 다른 코드(커밋·작업 트리 내용 지문)의 산출을 덧붙이면 거절한다(--fresh 로 새로 뜬다).
"""
import argparse
import difflib
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_ROOT = os.path.join(REPO, "ab_runs", "baseline")
WORK_ROOT = os.path.join(tempfile.gettempdir(), "wl_baseline")
TOOL_VERSION = 2                                     # 2 = 바이트 비교·줄 끝 보존(p0.5.3b). 판이 다른 산출끼리는 비교하지 않는다

# 판 3개 — 론처 옵션 그대로(Runner.start 가 만드는 환경변수를 받아 쓴다). 두뇌는 더미, 틱만 줄인다.
#   live    : 지금 실판 구성(민옥 10-11 Haiku 판의 run_opts 에서 두뇌만 더미) — 마을·파티 결성·부활·스킬
#   dungeon : 스킬 원정이 던전에서 바로(마을 없음) — 몹·함정·스킬 판정이 많이 돈다
#   classic : 메뉴형·스킬 없음(게이트가 도는 옛 판)
RUNS = OrderedDict([
    ("live", {"seed": 7, "turns": 120, "opts": {
        "town": True, "town_apart": False, "npc_brain": True, "partyform": True, "strangers": True, "town_sight": "zone",
        "town_life": True, "npc_reply": True, "floor_life": True, "bestiary_plus": True, "loop": True, "revive": True,
        "bestiary": False, "boss": True, "action_mode": "compose", "mode": "standard", "party": "default", "map": "concept"}}),
    ("dungeon", {"seed": 37, "turns": 120, "opts": {
        "boss": True, "bestiary": False, "action_mode": "compose", "mode": "standard", "party": "default", "map": "concept"}}),
    ("classic", {"seed": 217, "turns": 120, "opts": {
        "bestiary": False, "action_mode": "menu", "mode": "classic", "party": "default", "map": "normal"}}),
])
GATE_ENV = {"PYTHONUTF8": "1", "DUNGEON_ACTION_MODE": "menu", "DUNGEON_BRAIN_BACKEND": "dummy",   # _run_gates.sh 와 같은 값
            "DUNGEON_SKILLS": "0", "DUNGEON_TRPG_COMBAT": "0", "DUNGEON_RANDOM_SKILL": "0"}
EXTRA_GATES = ["tools/check_words"]                  # §10.2-3 목록에 있고 _run_gates.sh 에는 없는 것
VOLATILE = {"started", "saved_at"}                   # 실행 시각 — 비교에서 덮는다(그 밖은 전부 비교한다: game_version·git 도)
_VOL_RAW = [(re.compile(r'("(?:started|saved_at)":\s*)"[^"]*"'), r'\1"<V>"'),   # 원문(바이트) 그대로 덮는다 — 다시 직렬화하지 않는다
            (re.compile(r'("run_id":\s*"[^"@]*@)[^"]*"'), r'\1<V>"')]           # run_id = 시드@시작 시각
LABEL_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,62}[A-Za-z0-9])?")   # 끝이 점·하이픈이면 안 된다(Windows 는 끝 점을 지워 다른 label 과 같은 폴더가 된다)
IDENT_KEYS = ("rev", "commit", "head", "status_sha")


# ── 공용 ──────────────────────────────────────────────────────────────

def _git(*args):
    return subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True, check=True).stdout


def _clean_env(extra=None):
    """부모 환경에서 DUNGEON_* 를 걷어 낸 사본(콘솔·.env 값이 산출에 새지 않게) + extra."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
    env.update(extra or {})
    return env


def _jload(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _jsave(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def under(root, label):
    """label → root 아래의 폴더 경로. 이름 규칙(LABEL_RE·'..' 금지)과, 실제 경로(realpath)가 root 바로 아래인지 둘 다 본다 — 아니면 거절.
    지우기(rmtree)·쓰기는 전부 이 경로 아래에서만 한다(절대경로·상위 폴더 label 로 루트 state/ 를 지우는 사고를 막는다)."""
    if not isinstance(label, str) or not LABEL_RE.fullmatch(label) or ".." in label:
        raise SystemExit("label 은 이름만 된다(영숫자로 시작·끝, 영숫자·_·-·. 64자 이내, '..' 금지): %r" % (label,))
    root_r = os.path.realpath(root)
    p = os.path.realpath(os.path.join(root_r, label))
    if os.path.dirname(p) != root_r:
        raise SystemExit("label 의 경로가 %s 바로 아래가 아니다: %r → %s" % (root, label, p))
    return p


def same_code(a, b):
    return {k: (a or {}).get(k) for k in IDENT_KEYS} == {k: (b or {}).get(k) for k in IDENT_KEYS}


def merge_policy(man, ident, part, partial, fresh):
    """같은 label 의 앞선 산출(man)에 이번 산출을 어떻게 놓나 → 'new'(새로) · 'merge'(같은 코드·같은 도구 판 — 나눈 실행을 합친다).
    다른 코드 또는 다른 도구 판(판 표시 없음 포함)의 산출에 부분 산출(--part runs|gates · --chunk · --only)을 덧붙이려 하면 거절 —
    두 코드(또는 두 비교 방식)가 섞인 산출이 지금 도구 판으로 표시되는 일을 막는다."""
    if fresh or not (man or {}).get("src"):
        return "new"
    if same_code(man["src"], ident) and man.get("tool_version") == TOOL_VERSION:
        return "merge"
    if part == "all" and not partial:
        return "new"
    raise SystemExit("이 label 에는 다른 코드 또는 다른 도구 판의 산출이 있다(%s · 도구 판 %s, 지금 %s) — 부분 산출을 합치지 않는다. "
                     "--fresh 로 새로 뜨거나 다른 label 을 써라"
                     % ({k: man["src"].get(k) for k in IDENT_KEYS if man["src"].get(k)}, man.get("tool_version"), TOOL_VERSION))


# ── 사본 풀기 ──────────────────────────────────────────────────────────

def src_ident(rev):
    """코드 지문 — 커밋은 해시, 작업 트리는 HEAD + 변경 내용(diff·추적 안 하는 파일의 바이트) 해시."""
    if rev != "WORKTREE":
        return {"rev": rev, "commit": _git("rev-parse", rev + "^{commit}").decode().strip()}
    head = _git("rev-parse", "HEAD").decode().strip()
    status = _git("status", "--porcelain", "--untracked-files=all").decode("utf-8", "replace")
    h = hashlib.sha256(_git("diff", "HEAD", "--binary"))        # 내용까지 — 이미 바뀐 파일을 또 고쳐도 다른 지문
    for rel in sorted(_git("ls-files", "-z", "--others", "--exclude-standard").decode("utf-8").split("\0")):
        if rel and os.path.isfile(os.path.join(REPO, rel)):
            with open(os.path.join(REPO, rel), "rb") as f:
                h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(f.read()).digest())
    return {"rev": "WORKTREE", "head": head, "status_sha": h.hexdigest()[:16], "status": status.splitlines()}


def prepare_src(ident, label, fresh=False):
    """ident 의 코드를 <임시>/wl_baseline/<label>/src 에 푼다. 같은 코드로 풀린 사본이 있으면 그대로 쓴다(나눈 실행)."""
    base = under(WORK_ROOT, label)
    src, mark = os.path.join(base, "src"), os.path.join(base, "src.json")
    old = _jload(mark)
    if not fresh and old and os.path.isdir(src) and same_code(old, ident):
        return src, old
    if os.path.isdir(base):
        shutil.rmtree(base)
    os.makedirs(src)
    t0 = time.time()
    ident = dict(ident)
    if ident["rev"] == "WORKTREE":
        names = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode("utf-8").split("\0")
        n = 0
        for rel in names:
            if not rel:
                continue
            s = os.path.join(REPO, rel)
            if not os.path.isfile(s):                 # 지운 파일(추적 중이지만 작업 트리에 없음)
                continue
            d = os.path.join(src, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            n += 1
        ident["files"] = n
    else:
        proc = subprocess.Popen(["git", "archive", "--format=tar", ident["commit"]], cwd=REPO, stdout=subprocess.PIPE)
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
            tf.extractall(src, filter="data")
        if proc.wait() != 0:
            raise SystemExit("git archive 실패: %s" % ident["rev"])
    ident["prepared_sec"] = round(time.time() - t0, 1)
    _jsave(mark, ident)
    return src, ident


# ── 판 산출 ───────────────────────────────────────────────────────────

_ENV_HELPER = r'''
import json, os, sys
src, opts_path, state, out = sys.argv[1:5]
sys.path.insert(0, src)
for k in [k for k in os.environ if k.startswith("DUNGEON_")]:
    del os.environ[k]
import launcher
got = {}
class _Fake:
    pid = 0
    def __init__(self, args, cwd=None, env=None, stdout=None, stderr=None):
        got.update(env or {})
    def poll(self):
        return 0
launcher.subprocess.Popen = _Fake
with open(opts_path, encoding="utf-8") as f:
    opts = json.load(f)
r = launcher.Runner(src, state, os.path.join(os.path.dirname(state), "runs"))
r.start(opts, os.path.join(src, "party.json"), "dummy")
with open(out, "w", encoding="utf-8") as f:
    json.dump({k: v for k, v in got.items() if k.startswith("DUNGEON_") or k == "PYTHONUTF8"}, f, ensure_ascii=False, sort_keys=True)
'''

_RUN_HELPER = r'''
import contextlib, io, json, os, pickle, shutil, sys, threading
src, out = sys.argv[1:3]
sys.path.insert(0, src)
import brains
import snapshot
tls = threading.local()
SENT = []
_orig_call, _orig_brain = brains._call_claude, brains.claude_brain
def _call(prompt, model="haiku"):
    SENT.append({"key": list(getattr(tls, "key", None) or ["-", "-"]), "model": model, "prompt": prompt})
    return _orig_call(prompt, model)
def _brain(obs, char, *a, **k):
    tls.key = [obs.get("turn"), char]
    try:
        return _orig_brain(obs, char, *a, **k)
    finally:
        tls.key = None
brains._call_claude, brains.claude_brain = _call, _brain
snapshot.remove = lambda state_dir: None            # 판이 끝나도 마지막 스냅샷을 남긴다(산출용)
import show_runner
show_runner.STEP_DELAY = 0
log = io.StringIO()
with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    show_runner.main()
state = show_runner.STATE
def canon(x, depth=0):
    """스냅샷 구조 요약 — JSON 으로 못 쓰는 것(set·tuple·객체)을 결정론적인 꼴로."""
    if depth > 12:
        return "<deep>"
    if isinstance(x, dict):
        return {str(k): canon(v, depth + 1) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (set, frozenset)):
        return sorted((canon(v, depth + 1) for v in x), key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True))
    if isinstance(x, (list, tuple)):
        return [canon(v, depth + 1) for v in x]
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return "<%s>" % type(x).__name__
summary = {}
pkl, mj = snapshot.paths(state)
if os.path.exists(pkl):
    raw = open(pkl, "rb").read()
    snap = pickle.loads(raw)                         # 방금 이 프로세스가 쓴 파일(산출용 사본)
    summary = {"pickle_bytes": len(raw), "top": {str(k): type(v).__name__ for k, v in snap.items()},
               "version": snap.get("version"), "state_version": snap.get("state_version"),
               "world": canon(snap.get("world")), "sheets": canon(snap.get("sheets")),
               "bots": [canon(b) for b in snap.get("bots") or []],
               "waiting": canon(snap.get("waiting")),
               "d_attrs": sorted(vars(snap["d"])) if snap.get("d") is not None else None}
with open(os.path.join(out, "snapshot.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1, sort_keys=True)
if os.path.exists(mj):
    shutil.copyfile(mj, os.path.join(out, "snapshot_meta.json"))   # 러너가 쓴 바이트 그대로
SENT.sort(key=lambda r: (str(r["key"][0]).zfill(6), str(r["key"][1])))   # 스레드 순서 무관(같은 판단 안의 순서는 보존 — 안정 정렬)
with open(os.path.join(out, "prompts.jsonl"), "w", encoding="utf-8", newline="\n") as f:
    for r in SENT:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(os.path.join(out, "run.log"), "w", encoding="utf-8", newline="") as f:
    f.write(log.getvalue())
for n in ("stream.jsonl", "stream_side.jsonl"):
    if os.path.exists(os.path.join(state, n)):
        shutil.copyfile(os.path.join(state, n), os.path.join(out, n))
'''


def capture_runs(src, label, out):
    base = under(WORK_ROOT, label)
    os.makedirs(base, exist_ok=True)
    for name, h in (("_bl_env.py", _ENV_HELPER), ("_bl_run.py", _RUN_HELPER)):
        with io.open(os.path.join(base, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(h)
    res = {}
    for name, spec in RUNS.items():
        rd = os.path.join(out, "runs", name)
        if os.path.isdir(rd):
            shutil.rmtree(rd)
        os.makedirs(rd)
        work = os.path.join(base, "run-" + name)
        if os.path.isdir(work):
            shutil.rmtree(work)
        os.makedirs(os.path.join(work, "state"))
        opts = dict(spec["opts"], brain="dummy", seed=spec["seed"])
        _jsave(os.path.join(work, "opts.json"), opts)
        envp = os.path.join(work, "env.json")
        p = subprocess.run([sys.executable, os.path.join(base, "_bl_env.py"), src, os.path.join(work, "opts.json"),
                            os.path.join(work, "state"), envp], cwd=src, env=_clean_env({"PYTHONUTF8": "1"}),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise SystemExit("론처 환경변수 받기 실패(%s):\n%s" % (name, p.stderr[-2000:]))
        env = _jload(envp)
        state = os.path.join(work, "state-run")
        os.makedirs(state)
        env.update(DUNGEON_TURNS=str(spec["turns"]), DUNGEON_STREAM_OBS="1", DUNGEON_STEP_DELAY="0", DUNGEON_STATE_DIR=state,
                   DUNGEON_GM="0", PYTHONUTF8="1")
        env.pop("DUNGEON_RESUME", None)
        env.pop("DUNGEON_RUNS_DIR", None)
        _jsave(os.path.join(rd, "env.json"), {k: v.replace(base, "<WORK>") for k, v in env.items()})   # 사본 경로는 label 마다 다르다
        t0 = time.time()
        p = subprocess.run([sys.executable, os.path.join(base, "_bl_run.py"), src, rd], cwd=src, env=_clean_env(env),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
        sec = round(time.time() - t0, 1)
        if p.returncode != 0:
            raise SystemExit("판 산출 실패(%s):\n%s" % (name, (p.stdout + p.stderr)[-3000:]))
        res[name] = {"seed": spec["seed"], "turns": spec["turns"], "sec": sec, "files": {}}
        for fn in sorted(os.listdir(rd)):
            with open(os.path.join(rd, fn), "rb") as f:
                b = f.read()
            res[name]["files"][fn] = {"bytes": len(b), "sha": _sha(mask_text(fn, b.decode("utf-8", "replace")))[:16]}
        print("  판 %-8s seed %-4d %3d틱  %5.1fs  %s" % (name, spec["seed"], spec["turns"], sec,
              " ".join("%s=%s" % (k, v["sha"][:8]) for k, v in res[name]["files"].items())))
    return res


def mask_volatile_raw(s):
    """원문에서 실행 시각 값만 덮는다(다시 직렬화하지 않는다 — 나머지 바이트는 그대로 비교된다)."""
    for rx, rep in _VOL_RAW:
        s = rx.sub(rep, s)
    return s


def mask_text(fn, s):
    """산출 파일 하나의 비교용 원문 — 줄 끝·순서·공백은 그대로, 실행마다 바뀌는 값만 덮는다."""
    if fn == "run.log":
        return _norm_text(s)
    if fn.endswith((".jsonl", ".json")):
        return mask_volatile_raw(s)
    return s


# ── 게이트 산출 ────────────────────────────────────────────────────────

def gate_list(src):
    with io.open(os.path.join(src, "_run_gates.sh"), encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"for v in (.*?);\s*do", txt, re.S)
    if not m:
        raise SystemExit("_run_gates.sh 에서 게이트 목록을 못 찾았다")
    names = [w for w in m.group(1).replace("\\", " ").split() if w]
    return names + [g for g in EXTRA_GATES if g not in names]


_TMP_RE = None


def _norm_text(s, src=None):
    """실행마다 바뀌는 것만 덮는다 — 사본 경로·임시 폴더·시각·소요 시간·pid·uuid·계정 표식. 줄 끝(CRLF)·공백은 건드리지 않는다."""
    global _TMP_RE
    if _TMP_RE is None:
        t = re.escape(tempfile.gettempdir())
        _TMP_RE = re.compile(t.replace(r"\\", r"[\\/]+") + r"[\\/]+[^\s'\")\],]*", re.I)
    if src:
        for form in (src, src.replace("\\", "/"), src.replace("\\", "\\\\")):
            s = s.replace(form, "<SRC>")
    s = _TMP_RE.sub("<TMP>", s)
    s = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?", "<TS>", s)
    s = re.sub(r"\b\d{8}-\d{6}\b", "<TS>", s)
    s = re.sub(r"\b\d+(\.\d+)?\s?(ms|s|초|sec)\b", "<DUR>", s)
    s = re.sub(r"\bpid[ =:]?\d+", "pid<N>", s)
    s = re.sub(r"(['\"]pid['\"]:\s*)\d+", r"\1<N>", s)            # 자식 프로세스 번호(론처 응답 dict)
    s = re.sub(r"\b[0-9a-f]{32}\b", "<HEX32>", s)                 # uuid4().hex·세션 쿠키 — 실행마다 새로 뽑는 id
    s = re.sub(r"(['\"](?:id|tag)['\"]:\s*['\"])[0-9a-f]{8}(['\"])", r"\1<HEX8>\2", s)   # 계정 표식(게이트마다 새 비밀로 지문)
    s = re.sub(r"\b1[6-9]\d{8}(\.\d+)?\b", "<EPOCH>", s)          # 유닉스 시각(초)
    return s


def capture_gates(src, out, chunk=None, only=None):
    names = gate_list(src)
    if only:
        names = [n for n in names if n in only]
    if chunk:
        i, n = chunk
        names = names[(i - 1) * len(names) // n: i * len(names) // n]
    env = _clean_env(GATE_ENV)
    gd = os.path.join(out, "gates")
    os.makedirs(gd, exist_ok=True)
    res = {}
    for g in names:
        path = os.path.join(src, g + ".py")
        t0 = time.time()
        if not os.path.exists(path):
            rc, text = None, "(파일 없음)"
        else:
            try:                                      # 2>&1 — _run_gates.sh 와 같은 한 줄기(마지막 줄 판정도 같다)
                p = subprocess.run([sys.executable, path], cwd=src, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1500)
                rc, text = p.returncode, p.stdout.decode("utf-8", "replace")
            except subprocess.TimeoutExpired as e:
                rc, text = "timeout", (e.stdout or b"").decode("utf-8", "replace")
        sec = round(time.time() - t0, 1)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        last = lines[-1] if lines else ""
        norm = _norm_text(text, src)                  # 줄 끝 그대로(newline="" — 쓸 때도 바꾸지 않는다)
        with io.open(os.path.join(gd, g.replace("/", "__") + ".txt"), "w", encoding="utf-8", newline="") as f:
            f.write(norm)
        res[g] = {"rc": rc, "last": _norm_text(last, src), "pass": "ALL PASS" in last or (g in EXTRA_GATES and rc == 0),
                  "sha": _sha(norm)[:16], "sec": sec}
        print("  %-28s rc=%-4s %5.1fs  %s" % (g, rc, sec, last[:110]))
    return res


def capture(args):
    out = under(OUT_ROOT, args.label)
    ident = src_ident(args.rev)
    man_p = os.path.join(out, "manifest.json")
    partial = args.part != "all" or bool(args.chunk) or bool(args.only)
    policy = merge_policy(_jload(man_p, {}), ident, args.part, partial, args.fresh)
    if policy == "new" and os.path.isdir(out):
        shutil.rmtree(out)                            # 이 label 의 앞선 산출(다른 코드거나 --fresh) — under() 가 경계를 보장
    os.makedirs(out, exist_ok=True)
    src, ident = prepare_src(ident, args.label, fresh=args.fresh)
    man = _jload(man_p, {}) or {}
    man.update(label=args.label, src=ident, tool_version=TOOL_VERSION, python=sys.version.split()[0])
    print("사본: %s (%s)" % (src, ident.get("commit") or ident.get("head")))
    if args.part in ("all", "runs"):
        man["runs"] = capture_runs(src, args.label, out)
    if args.part in ("all", "gates"):
        chunk = tuple(int(x) for x in args.chunk.split("/")) if args.chunk else None
        g = man.get("gates") or {}
        g.update(capture_gates(src, out, chunk, set(args.only.split(",")) if args.only else None))
        man["gates"] = g
    man["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _jsave(man_p, man)
    gates = man.get("gates") or {}
    print("저장: %s  (판 %d · 게이트 %d — 통과 %d)" % (out, len(man.get("runs") or {}), len(gates),
                                               sum(1 for v in gates.values() if v.get("pass"))))


# ── 비교 ──────────────────────────────────────────────────────────────

class _Missing:
    """한쪽에 없는 칸(비교 표시는 '<없음>' — 실제 문자열 '<없음>' 값과 섞이지 않게 따로 둔다)."""
    def __repr__(self):
        return "<없음>"


MISSING = _Missing()


def _paths(a, b, path="", out=None, conc=()):
    """두 값의 다른 곳 → [(표시 경로, 실제 경로, 전, 후)]. 표시 경로는 리스트 첨자·숫자 키를 '*' 로 접는다(같은 종류의 차이를 한데 모으려고),
    실제 경로(키·첨자 튜플)는 원문에서 그 자리를 찾는 데 쓴다(_residual)."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            kk = "*" if str(k).isdigit() else str(k)
            if k not in a:
                out.append((path + "." + kk, conc + (k,), MISSING, b[k]))
            elif k not in b:
                out.append((path + "." + kk, conc + (k,), a[k], MISSING))
            else:
                _paths(a[k], b[k], path + "." + kk, out, conc + (k,))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _paths(x, y, path + "[*]", out, conc + (i,))
    elif a != b or type(a) is not type(b):
        out.append((path or ".", conc, a, b))
    return out


def as_text(v):
    if v is MISSING:
        return "<없음>"
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True)


# ── 원문 위치가 남는 JSON 읽기 — 값 변경 밖의 바이트 차이(직렬화·공백·줄 끝)를 가려내려고 ──
_JWS = re.compile(r"[ \t\n\r]*")
_JNUM = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _jspan(s, i=0):
    """JSON 값 하나 → (마디, 끝 위치). 마디 = {"s": 시작, "e": 끝, "obj": [(키, 키 시작, 마디)] | "arr": [마디]}."""
    i = _JWS.match(s, i).end()
    c = s[i:i + 1]
    if c in ("{", "["):
        close, node = ("}", {"s": i, "obj": []}) if c == "{" else ("]", {"s": i, "arr": []})
        i = _JWS.match(s, i + 1).end()
        if s[i:i + 1] == close:
            node["e"] = i + 1
            return node, i + 1
        while True:
            i = _JWS.match(s, i).end()
            if c == "{":
                if s[i:i + 1] != '"':
                    raise ValueError("키 자리가 아니다: %d" % i)
                ks = i
                key, i = json.decoder.scanstring(s, i + 1)
                i = _JWS.match(s, i).end()
                if s[i:i + 1] != ":":
                    raise ValueError("':' 자리가 아니다: %d" % i)
                child, i = _jspan(s, i + 1)
                node["obj"].append((key, ks, child))
            else:
                child, i = _jspan(s, i)
                node["arr"].append(child)
            i = _JWS.match(s, i).end()
            if s[i:i + 1] == ",":
                i += 1
                continue
            if s[i:i + 1] == close:
                node["e"] = i + 1
                return node, i + 1
            raise ValueError("'%s' 자리가 아니다: %d" % (close, i))
    if c == '"':
        _, e = json.decoder.scanstring(s, i + 1)
        return {"s": i, "e": e}, e
    for lit in ("true", "false", "null"):
        if s.startswith(lit, i):
            return {"s": i, "e": i + len(lit)}, i + len(lit)
    m = _JNUM.match(s, i)
    if not m or m.end() == i:
        raise ValueError("값 자리가 아니다: %d" % i)
    return {"s": i, "e": m.end()}, m.end()


def _locate(node, conc):
    """실제 경로 → (부모 마디, 부모 안 순번, 마디). 같은 키가 둘이면 뒤의 것(json.loads 와 같다)."""
    parent, idx = None, None
    for k in conc:
        parent = node
        if "obj" in node:
            idx = max(j for j, (key, _ks, _c) in enumerate(node["obj"]) if key == k)
            node = node["obj"][idx][2]
        else:
            idx = k
            node = node["arr"][k]
    return parent, idx, node


def _residual(x, y, changes):
    """양쪽 원문에서 값이 바뀐 자리를 같은 표시('<값>')로 덮고, 한쪽에만 있는 칸은 칸째(앞뒤 쉼표·공백까지) 지운 원문 둘 → 남은 바이트를 비교할 재료.
    changes = [(실제 경로, 전 값, 후 값)]. 덮은 뒤에도 다르면 그 차이는 값 변경 밖(칸 순서·공백·이스케이프·줄 끝)이다."""
    out = []
    for side, text in enumerate((x, y)):
        root, _end = _jspan(text)
        masks, dels = [], {}
        for conc, a, b in changes:
            mine, other = (a, b) if side == 0 else (b, a)
            if mine is MISSING:                       # 이쪽엔 그 칸이 없다 — 다른 쪽에서 칸째 지운다
                continue
            parent, idx, node = _locate(root, conc)
            if other is MISSING:
                if parent is None or "obj" not in parent:
                    raise ValueError("칸이 아닌 자리의 추가·삭제")
                dels.setdefault(id(parent), (parent, set()))[1].add(idx)
            else:
                masks.append((node["s"], node["e"], "<값>"))
        spans = list(masks)
        for parent, gone in dels.values():
            items = parent["obj"]
            for idx in gone:
                prev = [j for j in range(idx) if j not in gone]
                if prev:                              # 앞에 남는 칸이 있으면: 그 값 끝부터 이 값 끝까지(앞 쉼표 포함)
                    spans.append((items[prev[-1]][2]["e"], items[idx][2]["e"], ""))
                else:                                 # 맨 앞 칸들: 이 키 시작부터 다음 남는 칸의 키 시작까지(뒤 쉼표 포함)
                    nxt = [j for j in range(idx + 1, len(items)) if j not in gone]
                    spans.append((items[idx][1], items[nxt[0]][1] if nxt else items[idx][2]["e"], ""))
        spans.sort()
        merged = []
        for s0, e0, rep in spans:
            if merged and s0 < merged[-1][1]:
                if rep or merged[-1][2]:
                    raise ValueError("덮을 자리가 겹친다")
                merged[-1] = (merged[-1][0], max(merged[-1][1], e0), "")
            else:
                merged.append((s0, e0, rep))
        buf, pos = [], 0
        for s0, e0, rep in merged:
            buf.append(text[pos:s0])
            buf.append(rep)
            pos = e0
        buf.append(text[pos:])
        out.append("".join(buf))
    return out


def _byte_rest(D, scope, kind, x, y, parts, where=""):
    """값 차이(parts)를 다 덮은 뒤에도 원문이 다르면 그 나머지를 따로 남긴다 — 값 변경이 규칙으로 설명돼도 섞인 직렬화 차이는 묻히지 않는다."""
    try:
        rx, ry = _residual(x, y, [(conc, u, v) for _p, conc, u, v in parts])
    except (ValueError, KeyError, IndexError, TypeError) as e:
        D.add(scope, kind + "(바이트: 구조 확인 불가)", x, y, (where + " " if where else "") + str(e)[:60])
        return
    if rx != ry:
        D.add(scope, kind + "(바이트: 직렬화·줄 끝)", x, y, where)


def _short(s, n=200):
    return s if len(s) <= n else s[:n] + "…(%d자)" % len(s)


def check_rules(rules):
    """설명 규칙 형식 — 범위·경로·설명에 더해 전·후 원문 조건(정확히 같음 before/after 또는 정규식 전체 일치 before_re/after_re)이 둘 다 있어야 한다.
    조건 없는 규칙은 그 경로의 어떤 변화든 덮어 버리므로 받지 않는다."""
    if not isinstance(rules, list):
        raise SystemExit("설명 규칙은 목록이어야 한다")
    for i, r in enumerate(rules):
        ok = (isinstance(r, dict) and all(isinstance(r.get(k), str) and r[k] for k in ("scope", "path", "why"))
              and sum(k in r for k in ("before", "before_re")) == 1 and sum(k in r for k in ("after", "after_re")) == 1)
        if not ok:
            raise SystemExit("설명 규칙 %d: scope·path·why 와 (before|before_re)·(after|after_re) 가 하나씩 있어야 한다: %r" % (i, r))
        for k in ("path", "before_re", "after_re"):
            if k in r:
                re.compile(r[k])
    return rules


def _side_ok(r, side, text):
    if side in r:
        return text == r[side]
    return re.fullmatch(r[side + "_re"], text, re.S) is not None


class Diffs:
    """차이 하나하나(occurrence)를 규칙에 대 보고 (범위, 경로, 설명)별로 센다. 같은 경로라도 원문이 규칙과 다른 것은 (나)로 따로 남는다."""

    def __init__(self, rules):
        self.rules = check_rules(rules)
        self.items = OrderedDict()
        self.occ = []

    def why(self, scope, path, bt, at):
        for r in self.rules:
            if fnmatch.fnmatchcase(scope, r["scope"]) and re.search(r["path"], path) and _side_ok(r, "before", bt) and _side_ok(r, "after", at):
                return r["why"]
        return None

    def add(self, scope, path, before, after, where=""):
        bt, at = as_text(before), as_text(after)
        why = self.why(scope, path, bt, at)
        self.occ.append({"scope": scope, "path": path, "where": where, "before": bt, "after": at, "why": why})
        it = self.items.setdefault((scope, path, why), {"n": 0, "ex": None})
        it["n"] += 1
        if it["ex"] is None:
            it["ex"] = (where, bt, at)


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8")
    except OSError:
        return None


def diff_text(D, scope, a, b, label="줄"):
    """두 원문을 줄 끝까지 포함해(keepends) 맞댄다 — 문자열이 다르면 차이가 반드시 하나 이상 생긴다."""
    if a is None or b is None:
        if (a is None) != (b is None):
            D.add(scope, "(파일)", "있음" if a is not None else "없음", "있음" if b is not None else "없음")
        return
    if a == b:
        return
    la, lb = a.splitlines(keepends=True), b.splitlines(keepends=True)
    n = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb, autojunk=False).get_opcodes():
        if tag != "equal":
            D.add(scope, "%s %s" % (label, tag), "".join(la[i1:i2]), "".join(lb[j1:j2]), "%s %d" % (label, i1 + 1))
            n += 1
    if not n:                                         # 있을 수 없지만(keepends 면 이어 붙이면 원문) — 다르면 반드시 남긴다
        D.add(scope, "(바이트)", a, b)


def diff_jsonl(D, scope, a, b):
    """JSON 줄 파일 — 줄마다 바이트가 같으면 끝. 다르면 칸 경로로 나눠 보이고, 칸이 같은데 바이트만 다르면(직렬화·줄 끝) 그대로 차이로 남긴다."""
    if a is None or b is None:
        return diff_text(D, scope, a, b)
    la, lb = a.splitlines(keepends=True), b.splitlines(keepends=True)
    if len(la) != len(lb):
        D.add(scope, "(줄 수)", len(la), len(lb))
    for i, (x, y) in enumerate(zip(la, lb)):
        if x == y:
            continue
        try:
            jx, jy = json.loads(x), json.loads(y)
        except ValueError:
            D.add(scope, "(JSON 아님)", x, y, "줄 %d" % (i + 1))
            continue
        kind = (jx.get("kind") if isinstance(jx, dict) else None) or "?"
        parts = _paths(jx, jy)
        for p, _conc, u, v in parts:
            if p == ".prompt" and isinstance(u, str) and isinstance(v, str):
                diff_text(D, scope, u, v, label="프롬프트(t%s 봇%s) 줄" % tuple((jx.get("key") or ["?", "?"])[:2]))
            else:
                D.add(scope, kind + p, u, v, "줄 %d" % (i + 1))
        _byte_rest(D, scope, kind, x, y, parts, "줄 %d" % (i + 1))   # 값 차이 밖의 바이트(칸이 다 같을 때도, 값 변경과 섞였을 때도)
    for i in range(min(len(la), len(lb)), max(len(la), len(lb))):
        D.add(scope, "(한쪽에만 있는 줄)", la[i] if i < len(la) else "<없음>", lb[i] if i < len(lb) else "<없음>", "줄 %d" % (i + 1))


def diff_jsondoc(D, scope, a, b):
    """JSON 문서 하나 — 칸 경로로 나누고, 값 차이를 다 덮은 뒤에도 바이트가 다르면(직렬화·공백·줄 끝) 그 나머지도 차이."""
    if a is None or b is None:
        return diff_text(D, scope, a, b)
    if a == b:
        return
    try:
        jx, jy = json.loads(a), json.loads(b)
    except ValueError:
        return diff_text(D, scope, a, b)
    parts = _paths(jx, jy)
    for p, _conc, u, v in parts:
        D.add(scope, p, u, v)
    _byte_rest(D, scope, "", a, b, parts)


def diff(args):
    A, B = under(OUT_ROOT, args.before), under(OUT_ROOT, args.after)
    ma, mb = _jload(os.path.join(A, "manifest.json")), _jload(os.path.join(B, "manifest.json"))
    if not ma or not mb:
        raise SystemExit("산출이 없다: %s / %s" % (A, B))
    if ma.get("tool_version") != TOOL_VERSION or mb.get("tool_version") != TOOL_VERSION:
        raise SystemExit("도구 판이 다른 산출은 비교하지 않는다(전 %s · 후 %s · 지금 %s) — 다시 떠라"
                         % (ma.get("tool_version"), mb.get("tool_version"), TOOL_VERSION))
    rules = _jload(args.explain) if args.explain else []
    if args.explain and rules is None:
        raise SystemExit("설명 규칙 파일을 못 읽었다: %s" % args.explain)
    D = Diffs(rules)
    for name in sorted(set(ma.get("runs") or {}) | set(mb.get("runs") or {})):
        ra, rb = os.path.join(A, "runs", name), os.path.join(B, "runs", name)
        rd = lambda d, fn: (lambda s: None if s is None else mask_text(fn, s))(_read(os.path.join(d, fn)))
        for fn in ("stream.jsonl", "stream_side.jsonl", "prompts.jsonl"):
            diff_jsonl(D, "runs/%s/%s" % (name, fn), rd(ra, fn), rd(rb, fn))
        for fn in ("snapshot.json", "snapshot_meta.json", "env.json"):
            diff_jsondoc(D, "runs/%s/%s" % (name, fn), rd(ra, fn), rd(rb, fn))
        diff_text(D, "runs/%s/run.log" % name, rd(ra, "run.log"), rd(rb, "run.log"))
    ga, gb = ma.get("gates") or {}, mb.get("gates") or {}
    gate_rows = []
    for g in [*ga, *[g for g in gb if g not in ga]]:
        x, y = ga.get(g), gb.get(g)
        if x is None or y is None:
            D.add("gates/" + g, "(실행)", "있음" if x else "없음", "있음" if y else "없음")
            continue
        fn = g.replace("/", "__") + ".txt"
        ta, tb = (_norm_text(_read(os.path.join(d, "gates", fn)) or "") for d in (A, B))   # 산출 뒤에 는 정규화 규칙도 건다
        gate_rows.append((g, x, y, ta == tb))
        if x.get("rc") != y.get("rc"):
            D.add("gates/" + g, "(종료 코드)", x.get("rc"), y.get("rc"))
        diff_text(D, "gates/" + g, ta, tb, label="출력")
    # 보고서
    rows_a = [(s, p, it, why) for (s, p, why), it in D.items.items() if why]
    rows_b = [(s, p, it, why) for (s, p, why), it in D.items.items() if not why]
    na, nb = sum(it["n"] for *_, it, _w in rows_a), sum(it["n"] for *_, it, _w in rows_b)
    w = io.StringIO()
    w.write("# 기준선 차이 보고서: %s → %s\n\n" % (args.before, args.after))
    w.write("- 전: `%s` %s\n- 후: `%s` %s\n" % (args.before, json.dumps({k: ma.get("src", {}).get(k) for k in IDENT_KEYS if ma.get("src", {}).get(k)}),
                                              args.after, json.dumps({k: mb.get("src", {}).get(k) for k in IDENT_KEYS if mb.get("src", {}).get(k)})))
    w.write("- 판 %d개 · 게이트 %d/%d개 · 설명 규칙 %d개 · 비교 = 바이트(실행 시각·사본 경로 등만 덮음, 도구 판 %d)\n"
            % (len(set(ma.get("runs") or {}) | set(mb.get("runs") or {})), len(ga), len(gb), len(rules), TOOL_VERSION))
    w.write("- **(가) 설명됨 %d항목(차이 %d건) · (나) 설명 못 함 %d항목(차이 %d건)** — (가) = 그 단계의 의도된 변화 또는 원인을 확인한 실행 잡음"
            "(설명 칸에 '잡음' 표시). 규칙은 전·후 원문까지 맞아야 걸린다\n\n" % (len(rows_a), na, len(rows_b), nb))
    cell = lambda s: s.replace("|", "\\|").replace("\r", "␍").replace("\n", " ⏎ ")
    for title, rows in (("(나) 설명 못 함", rows_b), ("(가) 설명됨(의도 · 확인된 잡음)", rows_a)):
        w.write("## %s\n\n" % title)
        if not rows:
            w.write("없음\n\n")
            continue
        w.write("| 범위 | 경로 | 횟수 | 예(위치: 전 → 후) | 설명 |\n|---|---|---|---|---|\n")
        for scope, path, it, why in rows:
            where, bf, af = it["ex"]
            w.write("| %s | `%s` | %d | %s: %s → %s | %s |\n" % (scope, cell(path), it["n"], where, cell(_short(bf)), cell(_short(af)), cell(why or "")))
        w.write("\n")
    w.write("## 게이트 결과표(전 → 후)\n\n| 게이트 | 전 | 후 | 출력 같음 |\n|---|---|---|---|\n")
    for g, x, y, same in gate_rows:
        w.write("| %s | %s | %s | %s |\n" % (g, "PASS" if x.get("pass") else "FAIL rc=%s" % x.get("rc"),
                                          "PASS" if y.get("pass") else "FAIL rc=%s" % y.get("rc"), "예" if same else "아니오"))
    for g in [g for g in gb if g not in ga]:
        y = gb[g]
        w.write("| %s | (없음) | %s | 새 게이트 |\n" % (g, "PASS" if y.get("pass") else "FAIL rc=%s" % y.get("rc")))
    text = w.getvalue()
    if args.dump:
        with io.open(args.dump, "w", encoding="utf-8", newline="\n") as f:
            json.dump(D.occ, f, ensure_ascii=False, indent=1)
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("보고서: %s — (가) 설명됨 %d항목(%d건) · (나) 설명 못 함 %d항목(%d건)" % (args.out, len(rows_a), na, len(rows_b), nb))
    else:
        sys.stdout.write(text)
    return 0 if not rows_b else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--rev", required=True, help="커밋(HEAD·태그·해시) 또는 WORKTREE")
    c.add_argument("--label", required=True)
    c.add_argument("--part", choices=("all", "runs", "gates"), default="all")
    c.add_argument("--chunk", help="게이트를 n등분한 i번째(예: 2/4)")
    c.add_argument("--only", help="게이트 이름 쉼표 목록")
    c.add_argument("--fresh", action="store_true", help="이 label 의 앞선 산출·사본을 지우고 새로")
    d = sub.add_parser("diff")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--explain", help="설명 규칙 JSON [{scope, path(정규식), before|before_re, after|after_re, why}]")
    d.add_argument("--out")
    d.add_argument("--dump", help="차이 하나하나(전·후 원문 전체)를 JSON 으로 — 규칙을 쓸 때 원문 확인용")
    args = ap.parse_args(argv)
    return capture(args) if args.cmd == "capture" else diff(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
