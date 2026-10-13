# -*- coding: utf-8 -*-
"""걷기 타이밍(2026-10-12 c07 진단 → p057a 맞춤 · p057b 리뷰 반영) 게이트. LLM 0콜, 브라우저 없음 — 실제 코드를 node 가상 시계로 돌린다.
기준: 한 칸 이동 = 걷기 한 주기(WALK_FRAMES 프레임). 게임(Phaser)은 한 칸 = 트윈 stepMs, 리플레이 뷰어(Canvas)는 칸을 건너뛰어 한 칸 = 한 틱.
  ① 상수 원천: game/src/assets/sd.ts 의 WALK_FRAMES·WALK_CYCLE_MIN_MS 를 viewer/index.html 이 같은 값으로 옮겨 둔다(뷰어는 빌드 없이
     서빙돼 그 모듈을 못 읽는다) · 게임 쪽은 숫자를 다시 쓰지 않는다(stepMs 하한·걷기 열·frameIndex) · 뷰어는 옛 frameMs 시계를 안 쓴다
  ② 게임 산수(실제 stepMs·walkTimeScale 한 줄을 node 로): 1× 560 · 4×/16× 160 · 라이브 2200·5000 → 1000ms 모두 걷기 한 주기 = 한 칸 이동 시간 ·
     캐릭터 걷기 배속이 트윈과 같은 dur 로 걸린다
  ③~⑦ 뷰어 가상 시계(setIdx·schedule·syncWalk·setPlaying·drawBot 원문 그대로, 타이머·시계만 가짜): 재생 시작 · 멈췄다 재개 · 배속 변경 ·
     라이브 새 프레임 / 같은 프레임 갱신 · 16× — 첫 그림이 열 1(위상 0)이고 프레임마다 같은 시간 머문다
  ⑧ 배선: 게이트 목록
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
checks, fails = 0, []


def check(label, ok, detail=""):
    global checks
    checks += 1
    print(("  OK   " if ok else " FAIL  ") + label + (("  — " + str(detail)[:600]) if (detail != "" and not ok) else ""))
    if not ok:
        fails.append(label)


def src(*parts):
    with io.open(os.path.join(HERE, *parts), encoding="utf-8") as f:
        return f.read()


SD = src("game", "src", "assets", "sd.ts")
DS = src("game", "src", "scene", "DungeonScene.ts")
VW = src("viewer", "index.html")
FRAME_MS = json.loads(src("viewer", "assets", "sprites", "sd", "atlas.json"))["frame_ms"]


def const(text, name, export=False):
    m = re.search(r"^%sconst %s = (\d+);" % ("export " if export else "", name), text, re.M)
    return int(m.group(1)) if m else None


def line(text, pattern):
    m = re.search(pattern, text, re.M)
    return m.group(0) if m else ""


def js_func(text, name):
    """'function name(…) { … }' 원문 — 중괄호 짝으로 끝을 찾는다(템플릿 ${…} 도 짝이 맞는다)."""
    i = text.find("\nfunction %s(" % name)
    if i < 0:
        return ""
    depth = 0
    for k in range(text.find("{", text.find(")", i)), len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:k + 1]
    return ""


print("── ① 상수 원천")
sd_frames, sd_min = const(SD, "WALK_FRAMES", True), const(SD, "WALK_CYCLE_MIN_MS", True)
vw_frames, vw_min = const(VW, "WALK_FRAMES"), const(VW, "WALK_CYCLE_MIN_MS")
check("① 원천 sd.ts 와 뷰어의 걷기 상수가 같다(WALK_FRAMES·WALK_CYCLE_MIN_MS)",
      None not in (sd_frames, sd_min) and (sd_frames, sd_min) == (vw_frames, vw_min), (sd_frames, sd_min, vw_frames, vw_min))
step_line = line(DS, r"^export const stepMs = .*$")
check("① 게임은 숫자를 다시 쓰지 않는다: stepMs 하한 = WALK_CYCLE_MIN_MS · 걷기 열·frameIndex = WALK_FRAMES",
      "Math.max(WALK_CYCLE_MIN_MS," in step_line and "length: WALK_FRAMES" in SD and "% WALK_FRAMES" in SD
      and "[1, 2, 3, 4]" not in SD and "% 4)" not in SD, step_line)
check("① 뷰어 위상은 walkT0·walkCycle·WALK_FRAMES 로만 — 옛 frameMs 시계(위상 160·다시 그리기 140 따로)를 안 쓴다",
      "(performance.now() - walkT0) * WALK_FRAMES / walkCycle) % WALK_FRAMES" in VW and "frameMs(" not in VW)


print("── ② 게임 산수 · ③~⑦ 뷰어 가상 시계 (node)")
NODE = os.environ.get("WL_NODE") or shutil.which("node")
check("②~⑦ 준비: node 가 있다(WL_NODE 로 바꿀 수 있다)", bool(NODE))


def untype(s):
    return re.sub(r"^export ", "", re.sub(r":\s*(?:number|SdAtlas)\b", "", s))


GAME = "\n".join(untype(line(t, p)) for t, p in (
    (SD, r"^export const WALK_FRAMES = .*$"), (SD, r"^export const WALK_CYCLE_MIN_MS = .*$"),
    (DS, r"^const STEP_SHARE = .*$"), (DS, r"^const STEP_MAX_MS = .*$"),
    (DS, r"^export const stepMs = .*$"), (SD, r"^export const walkTimeScale = .*$")))
PACES = [700, 175, 43.75, 2200, 5000]                  # 1×·4×·16× 틱, 라이브 실측(2026-09-27 2.2초)·상한

VIEW_DECL = [ln for ln in VW.splitlines()
             if re.match(r"^const (BASE_MS|SPEEDS|WALK_FRAMES|WALK_CYCLE_MIN_MS) = ", ln) or re.match(r"^let (curIdx|walkT0) ", ln)]
VIEW_FUNCS = {n: js_func(VW, n) for n in ("setIdx", "schedule", "syncWalk", "setPlaying", "drawBot")}
check("③~⑦ 준비: 뷰어에서 상수 4·상태 2줄·함수 5개(setIdx·schedule·syncWalk·setPlaying·drawBot)를 원문으로 뽑았다",
      len(VIEW_DECL) == 6 and all(VIEW_FUNCS.values()), [VIEW_DECL, [n for n, v in VIEW_FUNCS.items() if not v]])
# 시나리오가 흉내 내는 호출 꼴이 원문에 그대로 있어야 한다(배속 버튼 onclick · loadRun 의 프레임 고르기)
check("③~⑦ 준비: 배속 버튼·라이브 갱신의 호출 꼴이 원문과 같다(시나리오가 이 꼴을 흉내 낸다)",
      "speedIdx = +b.dataset.i; buildSpeedButtons(); if (playing) schedule();" in VW
      and "setIdx(keepPos ? (wasAtEnd ? frames.length - 1 : prevIdx) : (isLive ? frames.length - 1 : 0));" in VW)

# 가짜 시계·타이머·DOM. WLSprites.cell 이 그려지는 순간(시각·프레임·위상)을 적고 null 을 돌려 드로잉은 건너뛴다.
PRELUDE = r"""
let __now = 0, __seq = 0;
const __timers = new Map(), TRACE = [];
const performance = { now: () => __now };
function setTimeout(fn, ms) { const id = ++__seq; __timers.set(id, { t: __now + ms, fn, seq: id }); return id; }
function setInterval(fn, ms) { const id = ++__seq; __timers.set(id, { t: __now + ms, fn, every: ms, seq: id }); return id; }
function clearTimeout(id) { __timers.delete(id); }
function clearInterval(id) { __timers.delete(id); }
function __advance(until) {
  for (;;) {
    let best = null;
    for (const [id, tm] of __timers)
      if (tm.t <= until && (!best || tm.t < best.tm.t || (tm.t === best.tm.t && tm.seq < best.tm.seq))) best = { id, tm };
    if (!best) break;
    __now = best.tm.t;
    if (best.tm.every) { best.tm.t += best.tm.every; best.tm.seq = ++__seq; } else __timers.delete(best.id);
    best.tm.fn();
  }
  __now = until;
}
const __mk = i => ({ turn: i, level: { depth: 1 }, bots: [{ char: '1', x: i, y: 0, job: '전사', alive: true }],
                     moved: { '1': true }, facing: { '1': 'right' } });
let frames = [], isLive = false;
const looks = { '1': { sprite: 'sd-test' } }, colors = {};
var window = globalThis;
var WLSprites = { ready: true, smooth: () => false, displayScale: () => 1.5,
                  cell(look, dir, phase) { TRACE.push([__now, curIdx, phase]); return null; } };
function $() { return {}; }
function renderParty() {}
function renderFeed() {}
function drawCell() {}
function render() { const f = frames[curIdx]; if (f) for (const b of f.bots) drawBot(b, f); }
"""
SCENARIOS = {
    "start": "frames = Array.from({ length: 10 }, (_, i) => __mk(i)); setIdx(0); setPlaying(true); __advance(2100);",
    "resume": "frames = Array.from({ length: 10 }, (_, i) => __mk(i)); setIdx(0); setPlaying(true); __advance(260);"
              " setPlaying(false); __advance(400); setPlaying(true); __advance(1300);",
    "speed": "frames = Array.from({ length: 10 }, (_, i) => __mk(i)); setIdx(0); setPlaying(true); __advance(260);"
             " speedIdx = 1; if (playing) schedule(); __advance(1000);",
    "live": "frames = Array.from({ length: 3 }, (_, i) => __mk(i)); isLive = true; setIdx(2); setPlaying(true); __advance(900);"
            " frames.push(__mk(3)); setIdx(frames.length - 1); __advance(1990); setIdx(frames.length - 1); __advance(2500);",
    "fast": "frames = Array.from({ length: 40 }, (_, i) => __mk(i)); speedIdx = 2; setIdx(0); setPlaying(true); __advance(1000);",
}
HARNESS = r"""
const vm = require('vm');
const out = {};
const g = vm.createContext({});
vm.runInContext(%(game)s + '\nglobalThis.__out = JSON.stringify(%(paces)s.map(p => { const d = stepMs(p), ts = walkTimeScale({ frame_ms: %(frame_ms)s }, d);'
                + ' return [p, d, %(frame_ms)s * WALK_FRAMES / ts]; }));', g);
out.game = JSON.parse(g.__out);
const code = %(prelude)s + '\n' + %(decl)s + '\n' + %(funcs)s;
for (const [name, s] of Object.entries(%(scen)s)) {
  const c = vm.createContext({});
  vm.runInContext(code + '\n' + s + '\nglobalThis.__out = JSON.stringify(TRACE);', c);
  out[name] = JSON.parse(c.__out);
}
console.log(JSON.stringify(out));
"""
res = {}
if NODE:
    tmp = tempfile.mkdtemp(prefix="wl_walk_")
    path = os.path.join(tmp, "harness.js")
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HARNESS % {"game": json.dumps(GAME), "paces": json.dumps(PACES), "frame_ms": json.dumps(FRAME_MS),
                           "prelude": json.dumps(PRELUDE), "decl": json.dumps("\n".join(VIEW_DECL)),
                           "funcs": json.dumps("\n\n".join(VIEW_FUNCS.values())), "scen": json.dumps(SCENARIOS)})
    run = subprocess.run([NODE, path], capture_output=True, text=True, encoding="utf-8", timeout=60)
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        res = json.loads(run.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        res = {}
    check("②~⑦ 준비: 가상 시계 하네스가 돈다", run.returncode == 0 and bool(res), (run.stdout + run.stderr)[-600:])

game = res.get("game") or []
check("② 게임: 한 칸 이동(stepMs) 1× 560 · 4× 160 · 16× 160 · 라이브 2200→1000 · 5000→1000ms",
      [d for _, d, _ in game] == [560, 160, 160, 1000, 1000], game)
check("② 게임: 그 모든 경우 걷기 한 주기(frame_ms×WALK_FRAMES÷배속) = 한 칸 이동 시간",
      bool(game) and all(abs(cyc - d) < 1e-9 for _, d, cyc in game), game)
check("② 게임: 캐릭터 걷기 배속이 트윈과 같은 dur 로 걸린다(updateActor)",
      re.search(r"const dur = stepMs\(this\.app\.playback\.paceMs\);\s*s\.anims\.timeScale = walkTimeScale\(this\.atlas, dur\);[^\n]*\n"
                r"\s*this\.tweens\.add\(\{ targets: s, x: target\.x, y: target\.y, duration: dur,", DS) is not None)


def states(trace, t0, t1, phase_only=False):
    """보이는 상태가 바뀐 순간 [(t, 프레임, 위상)] — 같은 순간 여러 번 그리면 마지막 그림이 보인다."""
    at = []
    for t, idx, ph in trace:
        if t0 <= t <= t1:
            if at and at[-1][0] == t:
                at[-1] = (t, idx, ph)
            else:
                at.append((t, idx, ph))
    out = []
    for s in at:
        key = s[2] if phase_only else s[1:]
        if not out or (out[-1][2] if phase_only else out[-1][1:]) != key:
            out.append(s)
    return out


def grid(t0, step, n, idx_of):
    """t0 부터 step 마다 위상이 하나씩 넘어가는 기대 줄 — 프레임 번호는 idx_of(k)."""
    return [(t0 + k * step, idx_of(k), k % 4) for k in range(n)]


def as_tuples(seq):
    return [tuple(x) for x in seq]


st = as_tuples(states(res.get("start", []), 0, 2100))
check("③ 재생 시작(1×): 누른 순간 열 1(위상 0) · 위상마다 175ms(= 틱 700 ÷ 4) · 틱마다 새 프레임이 위상 0부터",
      st == grid(0, 175, 13, lambda k: k // 4), st[:6])
tr = res.get("resume", [])
st = as_tuples(states(tr, 400, 1300))
paused = as_tuples(states(tr, 260, 260))
check("④ 멈춤 → 재개: 멈춘 순간 정지 그림(위상 -1) · 재개한 순간 위상 0 · 그 뒤 175ms 씩 · 다음 틱은 재개 + 700",
      paused[-1:] == [(260, 0, -1)] and st == grid(400, 175, 6, lambda k: k // 4), [paused, st])
st = as_tuples(states(res.get("speed", []), 260, 1000))
check("⑤ 배속 변경(1×→4×, 주기 한가운데): 바꾼 순간 위상 0 · 그 뒤 43.75ms 씩 · 4× 틱(175)마다 새 프레임 위상 0",
      st == grid(260, 43.75, 17, lambda k: k // 4), st[:6])
tr = res.get("live", [])
st = as_tuples(states(tr, 900, 2500))
before = as_tuples(states(tr, 0, 899))
at_refresh = [tuple(x) for x in tr if x[0] == 1990]
check("⑥ 라이브: 꽁무니에서 기다리는 동안 제자리 걸음이 끊기지 않고 · 새 프레임이 붙은 순간(900) 위상 0 · 175ms 씩",
      before == grid(0, 175, 6, lambda k: 2) and st == grid(900, 175, 10, lambda k: 3), [before, st])
check("⑥ 라이브: 같은 프레임 갱신(1990, 1.5초 폴링 꼴)은 주기를 처음으로 되돌리지 않는다(그 순간 위상 2 = 이어 돈다)",
      at_refresh == [(1990, 3, 2)], at_refresh)
tr = res.get("fast", [])
st = as_tuples(states(tr, 0, 1000, phase_only=True))
check("⑦ 16×(틱 43.75 < 하한 160): 시작 위상 0 · 프레임이 틱을 넘겨 40ms 씩 이어 돈다(열 1에 멈추지 않는다) · 틱은 계속 넘어간다",
      [(t, ph) for t, _, ph in st] == [(40 * k, k % 4) for k in range(26)] and bool(tr) and tr[-1][1] == 22,
      [st[:6], tr[-1:] if tr else None])


print("── ⑧ 배선")
check("⑧ 게이트 목록(_run_gates.sh)에 verify_walk_timing", re.search(r"\bverify_walk_timing\b", src("_run_gates.sh")) is not None)

if fails:
    print("FAIL — verify_walk_timing (%d/%d): %s" % (len(fails), checks, " · ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_walk_timing (걷기 타이밍: 상수 원천·게임 산수·뷰어 가상 시계 시작/재개/배속/라이브/16×, %d checks, 실 LLM 0콜)" % checks)
