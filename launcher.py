#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""원더랜드 웹 론처(D31, 2026-09-05) — "게임처럼 시작한다".
─────────────────────────────────────────────
왜: 지금까지 판은 콘솔 메뉴(wonderland.bat)로 띄우고 브라우저(viewer/)로 관전했다. 뷰어는 정적
서버(python -m http.server)라 저장도 실행도 못 한다. 이 파일이 그 정적 서버를 **대신** 맡아(같은
포트 8000, 같은 서빙 루트 — 뷰어는 한 줄도 안 고침) 세 가지를 더 한다: 파티 저장 · 판 시작/중지 ·
상태 조회. 표준 라이브러리만 쓴다(새 의존 0). 127.0.0.1 만 듣는다.

흐름: 타이틀 → 파티(직업·성격 키워드 최대 3·이름·성별·배경 자유입력) → 옵션(맵·마을·두뇌·시드) →
시작 → 러너(show_runner.py)를 자식 프로세스로 띄우고 → 관전 뷰어로 이어진다.

API(JSON):
  GET  /api/presets  traits.json(키워드·직업) + 기본 파티(party.json) 미리보기 + 상태
  POST /api/party    {"slots":[{job,traits[],name,sex,background?,persona?}, ...]} → sheetkit 조립 →
                     러너의 load_party 로 재검증 → party_custom.json 저장 (실패 400 + 이유 한 줄)
  POST /api/start    {"map":"normal|big","town":bool,"brain":"gemini_api|claude_cli|anthropic_api|dummy",
                      "seed":int|null|"random","party":"custom|default"} → 이전 판 보존(live.bat 규칙)
                     → 러너 subprocess. 동시 1판(실행 중이면 409)
  GET  /api/status   {running,pid,started,seed,party,turn,outcome,viewer}
  POST /api/stop     러너 종료

⚠️ 사용자 자유 입력(이름·배경)은 시트 UGC 의 프롬프트 인젝션 관문이다 — sheetkit 이 격리(정제·
상한·인용 한 줄)하고 러너의 load_party 가 다시 검증한다. 막는 게 아니라 격리+관측(D31).
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import sheetkit                                   # noqa: E402

MAPS = {                                          # 시작 옵션 → 러너 환경변수(wonderland.bat 메뉴 값 그대로)
    "normal": {},
    "big": {"DUNGEON_W": "80", "DUNGEON_H": "30", "DUNGEON_MONSTERS": "7", "DUNGEON_TRAPS": "4",
            "DUNGEON_LURKERS": "2", "DUNGEON_POTIONS": "1", "DUNGEON_DEPTHS": "1", "DUNGEON_TURNS": "500"},
}
BRAINS = ("gemini_api", "claude_cli", "anthropic_api", "dummy")
BIG_KEYS = tuple(MAPS["big"])


class Conflict(Exception):
    pass


class BadRequest(Exception):
    pass


class Runner:
    """러너 프로세스 1개의 생애 — 시작(이전 판 보존 포함)·상태·중지. 동시 1판."""

    def __init__(self, root, state_dir, runs_dir):
        self.root, self.state_dir, self.runs_dir = root, state_dir, runs_dir
        self.proc = None
        self.started = None
        self.seed_requested = None
        self.lock = threading.Lock()

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def preserve_previous(self):
        """live.bat 규칙의 파이썬판: state/stream.jsonl 이 비어 있지 않으면 runs/stream-<mtime>.jsonl 로 복사."""
        src = os.path.join(self.state_dir, "stream.jsonl")
        if not (os.path.exists(src) and os.path.getsize(src) > 0):
            return None
        os.makedirs(self.runs_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(os.path.getmtime(src)))
        dst = os.path.join(self.runs_dir, "stream-%s.jsonl" % stamp)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        return dst

    def start(self, opts, party_path, default_brain=None):
        with self.lock:
            if self.running():
                raise Conflict("이미 판이 진행 중이다 — 중지하거나 끝나길 기다려라")
            env = dict(os.environ)
            env["PYTHONUTF8"] = "1"
            env["DUNGEON_GM"] = "0"
            env["DUNGEON_STATE_DIR"] = self.state_dir
            brain = str(opts.get("brain") or default_brain or "gemini_api")
            if brain not in BRAINS:
                raise BadRequest("두뇌는 %s 중 하나" % "/".join(BRAINS))
            env["DUNGEON_BRAIN_BACKEND"] = brain
            seed = opts.get("seed")
            if seed in (None, "", "random"):
                env["DUNGEON_SEED"] = "random"
            else:
                try:
                    env["DUNGEON_SEED"] = str(int(seed))
                except (TypeError, ValueError):
                    raise BadRequest("시드는 정수 또는 비움(랜덤)")
            which = opts.get("party", "custom")
            if which == "default":
                env["DUNGEON_PARTY_FILE"] = os.path.join(self.root, "party.json")
            else:
                if not os.path.exists(party_path):
                    raise BadRequest("저장된 커스텀 파티가 없다 — 먼저 파티를 저장하라(또는 기본 파티 선택)")
                env["DUNGEON_PARTY_FILE"] = party_path
            m = str(opts.get("map") or "normal")
            if m not in MAPS:
                raise BadRequest("맵은 normal/big")
            if m == "normal":
                for k in BIG_KEYS:                  # 이전 호출의 큰 판 값이 부모 env 에 남아 있어도 안 물려준다
                    env.pop(k, None) if k not in os.environ else None
            env.update(MAPS[m])
            if opts.get("town"):
                env["DUNGEON_TOWN"] = "1"
            else:
                env.pop("DUNGEON_TOWN", None)
            if brain == "dummy":                    # 규칙 두뇌 = 배관 점검용 — 도감 원장 격리(게이트 원칙)
                env["DUNGEON_BESTIARY_FILE"] = ""
            elif not env.get("DUNGEON_BESTIARY_FILE"):
                env["DUNGEON_BESTIARY_FILE"] = os.path.join(self.root, "bestiary.json")
            os.makedirs(self.state_dir, exist_ok=True)
            self.preserve_previous()
            out = io.open(os.path.join(self.state_dir, "runner.out"), "w", encoding="utf-8")
            self.proc = subprocess.Popen([sys.executable, os.path.join(self.root, "show_runner.py")],
                                         cwd=self.root, env=env, stdout=out, stderr=subprocess.STDOUT)
            self.started = time.strftime("%Y-%m-%dT%H:%M:%S")
            self.seed_requested = env["DUNGEON_SEED"]
            return {"ok": True, "pid": self.proc.pid, "seed": self.seed_requested, "brain": brain,
                    "party": which, "map": m, "town": bool(opts.get("town"))}

    def stop(self):
        with self.lock:
            if not self.running():
                return {"ok": True, "stopped": False}
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            return {"ok": True, "stopped": True}

    def status(self):
        """실행 여부 + 현 판의 사실(스트림에서 읽는다 — 러너 밖 원천 없음)."""
        out = {"running": self.running(), "pid": self.proc.pid if self.proc else None,
               "started": self.started, "seed": None, "party": [], "turn": None, "outcome": None,
               "viewer": "/viewer/?run=state/stream.jsonl"}
        path = os.path.join(self.state_dir, "stream.jsonl")
        if os.path.exists(path):
            try:
                with io.open(path, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except OSError:
                lines = []
            if lines:
                try:
                    meta = json.loads(lines[0])
                    if meta.get("kind") == "run_meta":
                        out["seed"] = meta.get("seed")
                        out["party"] = [{"char": p.get("char"), "name": p.get("name") or p.get("job"),
                                         "job": p.get("job")} for p in meta.get("party", [])]
                except ValueError:
                    pass
                for ln in reversed(lines):
                    try:
                        o = json.loads(ln)
                    except ValueError:
                        continue
                    if o.get("kind") == "end":
                        out["outcome"] = o.get("outcome")
                    if o.get("kind") == "tick":
                        out["turn"] = o.get("turn")
                        break
        return out


class Ctx:
    def __init__(self, root, party_path, state_dir, runs_dir, brain=None):
        self.root, self.party_path = root, party_path
        self.state_dir, self.runs_dir = state_dir, runs_dir
        self.default_brain = brain
        self.runner = Runner(root, state_dir, runs_dir)
        self.presets = sheetkit.load_traits()


def default_party_preview(root):
    """party.json 미리보기 — 검증은 러너 몫이라 여기선 읽기만(메타 키 제외)."""
    try:
        with io.open(os.path.join(root, "party.json"), encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for c in sorted(k for k in raw if not str(k).startswith("_")):
        s = raw[c]
        if isinstance(s, dict):
            out.append({"char": c, "name": s.get("name") or ("모험가 %s" % c), "job": s.get("job"),
                        "sex": s.get("sex"), "persona": s.get("persona"), "speech": s.get("speech"),
                        "goal": s.get("goal")})
    return out


def save_party(ctx, slots):
    """슬롯 → sheetkit 조립 → 파일 → 러너의 load_party 로 재검증(이중 검증). 실패는 BadRequest 한 줄."""
    try:
        sheets = sheetkit.build_party(slots, data=ctx.presets)
    except ValueError as e:
        raise BadRequest(str(e))
    sheetkit.write_party(sheets, ctx.party_path)
    import show_runner                                # 지연 import — 러너 모듈의 검증기를 그대로 쓴다
    with io.StringIO() as err:
        old = sys.stderr
        sys.stderr = err
        try:
            loaded = show_runner.load_party(ctx.party_path)
        finally:
            sys.stderr = old
        warn = err.getvalue()
    if "폴백" in warn or sorted(loaded) != sorted(sheets):
        try:
            os.remove(ctx.party_path)
        except OSError:
            pass
        raise BadRequest("러너 검증 실패: %s" % (warn.strip().splitlines()[-1] if warn.strip() else "시트 불일치"))
    return {"ok": True, "path": os.path.basename(ctx.party_path),
            "party": [{"char": c, "name": s["name"], "job": s["job"], "traits": s["traits"]}
                      for c, s in sorted(sheets.items())]}


class Handler(SimpleHTTPRequestHandler):
    """정적 서빙(뷰어·runs/ 자동 색인 그대로) + /api/*."""

    def __init__(self, *args, ctx=None, **kwargs):
        self.ctx = ctx
        super().__init__(*args, directory=ctx.root, **kwargs)

    # ── 유틸 ──
    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 64 * 1024:
            raise BadRequest("요청이 너무 크다")
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise BadRequest("JSON 이 아니다")
        if not isinstance(obj, dict):
            raise BadRequest("JSON 객체가 아니다")
        return obj

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/") and not self.path.startswith("/api/status"):
            sys.stderr.write("[launcher] %s\n" % (fmt % args))

    def end_headers(self):
        if self.path.startswith("/state/") or self.path.startswith("/runs/"):
            self.send_header("Cache-Control", "no-store")   # 라이브 스트림은 캐시 금지
        super().end_headers()

    # ── 라우팅 ──
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/presets":
            p = self.ctx.presets
            return self._json(200, {"traits": p["traits"], "max_traits": p["max_traits"], "jobs": p["jobs"],
                                    "default_party": default_party_preview(self.ctx.root),
                                    "custom_saved": os.path.exists(self.ctx.party_path),
                                    "default_brain": self.ctx.default_brain or "gemini_api",
                                    "status": self.ctx.runner.status()})
        if path == "/api/status":
            return self._json(200, self.ctx.runner.status())
        if path.startswith("/api/"):
            return self._json(404, {"error": "없는 API"})
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/launcher/")
            self.end_headers()
            return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/party":
                return self._json(200, save_party(self.ctx, body.get("slots") or []))
            if path == "/api/start":
                return self._json(200, self.ctx.runner.start(body, self.ctx.party_path, self.ctx.default_brain))
            if path == "/api/stop":
                return self._json(200, self.ctx.runner.stop())
            return self._json(404, {"error": "없는 API"})
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        except Conflict as e:
            return self._json(409, {"error": str(e)})
        except Exception as e:                        # 서버가 죽지 않게 — 이유는 한 줄로 돌려준다
            return self._json(500, {"error": "%s: %s" % (type(e).__name__, e)})


def make_server(host, port, root=HERE, party_path=None, state_dir=None, runs_dir=None, brain=None):
    ctx = Ctx(root, party_path or os.path.join(root, "party_custom.json"),
              state_dir or os.path.join(root, "state"), runs_dir or os.path.join(root, "runs"), brain)
    srv = ThreadingHTTPServer((host, port), partial(Handler, ctx=ctx))
    srv.daemon_threads = True
    srv.ctx = ctx
    return srv


def main():
    ap = argparse.ArgumentParser(description="원더랜드 웹 론처 — 파티 꾸미기·시작·관전을 한 창에서")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    try:
        srv = make_server(a.host, a.port)
    except OSError as e:
        print("[launcher] %s:%d 를 열 수 없다(%s) — 기존 뷰어 서버(python -m http.server 8000)가 떠 있으면 "
              "그 창을 닫고 다시, 또는 --port 8001" % (a.host, a.port, e), file=sys.stderr)
        return 1
    url = "http://%s:%d/launcher/" % (a.host, a.port)
    print("[launcher] %s  (Ctrl-C 로 종료 — 진행 중인 판도 함께 멈춘다)" % url)
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.ctx.runner.stop()
        srv.server_close()
    return 0


if __name__ == "__main__":
    import envload
    envload.load()          # show_runner 와 같은 규칙 — __main__ 안에서만(게이트는 안 밟는다)
    raise SystemExit(main())
