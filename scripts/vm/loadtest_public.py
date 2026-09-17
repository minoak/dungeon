# -*- coding: utf-8 -*-
"""다중 접속 연습(2026-09-17, 0콜) — 임시 폴더에 공개 서버(server.py, 두뇌 dummy)를 띄우고 가짜 사용자 N명을 붙인다.
사용: python scripts/vm/loadtest_public.py [사용자 수=12] [초=30] [동시 판 상한=3]
      LT_BIGSTREAM=<실제 판 기록 파일> 을 주면 8초 뒤 끝난 판의 기록을 그 사본으로 바꿔 폴링 부담을 실제 크기로 맞춘다.
VM 에서 그대로 돌리면 그 VM 의 체급을 잰다(운영 서버·운영 데이터와 무관한 임시 폴더·임시 포트. Caddy 압축은 거치지 않는다).
사용자마다 번호표(쿠키) 하나: 론처 열기 → 설정 읽기 → 기본 파티로 판 시작 시도(동시 3판까지만 성공, 나머지는 '자리 없음') →
T초 동안 실제 화면처럼 폴링(상태 1.5초마다 · 판을 가진 사용자는 판 파일 전체도 1.5초마다).
재는 것: 요청별 응답 시간(중앙값·95%·최대)·실패 수 · 서버와 러너 프로세스의 메모리.
⚠️ 돌린 기계의 값이다 — 노트북 값으로 VM(e2-small)을 말하지 마라. 리포·state/·운영 포트 무접촉. psutil 이 없으면 메모리 줄만 빠진다."""
import http.cookiejar
import io
import json
import os
import statistics
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

try:
    import psutil
except ImportError:                                  # VM 에 없을 수 있다 — 메모리 측정만 건너뛴다
    psutil = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 리포 루트(scripts/vm/ 의 조부모)
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ["PYTHONUTF8"] = "1"
for k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    os.environ[k] = ""
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"
os.environ["DUNGEON_TURNS"] = os.environ.get("LT_TURNS", "600")
import server as S

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
MAX_RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
FAKE_KEY = "LOADTEST-FAKE-KEY-0123456789abcdef"

tmp = tempfile.mkdtemp(prefix="wl_load_")
srv = S.make_public_server("127.0.0.1", 0, data_dir=tmp, brain="dummy", max_runs=MAX_RUNS, starts_per_hour=10000)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_port
lat = {"launcher": [], "presets": [], "start": [], "status": [], "stream": []}
fails = {k: 0 for k in lat}
codes = {}
bytes_stream = [0]
lock = threading.Lock()


def call(opener, kind, path, body=None):
    t0 = time.perf_counter()
    code, n = 0, 0
    try:
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=20) as r:
            data = r.read()
            code, n = r.status, len(data)
    except urllib.error.HTTPError as e:
        code = e.code
        e.read()
    except Exception:
        code = -1
    dt = (time.perf_counter() - t0) * 1000
    with lock:
        lat[kind].append(dt)
        if code not in (200, 404, 429, 409):
            fails[kind] += 1
        codes[(kind, code)] = codes.get((kind, code), 0) + 1
        if kind == "stream":
            bytes_stream[0] += n
    return code


def user(i, started_flags):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    call(opener, "launcher", "/launcher/")
    call(opener, "presets", "/api/presets")
    code = call(opener, "start", "/api/start", {"party": "default", "town": True, "provider": "gemini_api", "brain": "gemini_api",
                                                "key": FAKE_KEY, "mode": "standard", "action_mode": "compose", "map": "normal", "boss": True})
    has_run = code == 200
    started_flags[i] = has_run
    t_end = time.time() + SECONDS
    while time.time() < t_end:
        call(opener, "status", "/api/status")
        if has_run:
            call(opener, "stream", "/state/stream.jsonl?_=%d" % int(time.time() * 1000))
        time.sleep(1.5)
    if has_run:
        call(opener, "status", "/api/status")


flags = [None] * N
threads = [threading.Thread(target=user, args=(i, flags)) for i in range(N)]
BIG = os.environ.get("LT_BIGSTREAM")


def inflate():
    # 가짜 두뇌 판은 금방 끝나 파일이 작다 - 8초 뒤, 끝난 판의 기록을 실제 크기의 판 기록 사본으로 바꿔 폴링 부담을 현실에 맞춘다
    import shutil
    time.sleep(8)
    for root_, _dirs, files in os.walk(tmp):
        if "stream.jsonl" in files and os.path.basename(root_) == "state":
            try:
                shutil.copyfile(BIG, os.path.join(root_, "stream.jsonl"))
            except OSError:
                pass


if BIG:
    threading.Thread(target=inflate, daemon=True).start()
me = psutil.Process() if psutil else None
for t in threads:
    t.start()
    time.sleep(0.05)
peak_server, peak_runners, n_runners = 0, 0, 0
while any(t.is_alive() for t in threads):
    if me is None:
        time.sleep(0.5)
        continue
    kids = [c for c in me.children(recursive=True) if "python" in (c.name() or "").lower()]
    try:
        peak_server = max(peak_server, me.memory_info().rss)
        rs = [c.memory_info().rss for c in kids]
        if rs:
            peak_runners = max(peak_runners, max(rs))
            n_runners = max(n_runners, len(rs))
    except psutil.Error:
        pass
    time.sleep(0.5)

sizes = []
for root_, _dirs, files in os.walk(tmp):
    for f in files:
        if f == "stream.jsonl":
            sizes.append(os.path.getsize(os.path.join(root_, f)))
srv.sessions.stop_all()
srv.shutdown()
srv.server_close()

out.write("가짜 사용자 %d명 · %d초 · 동시 판 상한 %d\n" % (N, SECONDS, MAX_RUNS))
out.write("판을 연 사용자 %d명 / 자리 없음 %d명\n" % (sum(1 for f in flags if f), sum(1 for f in flags if f is False)))
for k, v in lat.items():
    if v:
        v2 = sorted(v)
        out.write("  %-9s 요청 %4d · 중앙값 %6.1fms · 95%% %6.1fms · 최대 %7.1fms · 실패 %d\n"
                  % (k, len(v), statistics.median(v2), v2[int(len(v2) * 0.95) - 1], v2[-1], fails[k]))
out.write("응답 코드: %s\n" % sorted(codes.items()))
out.write("판 파일 크기(끝난 뒤): %s · 받아 간 판 파일 합계 %.1fMB(압축 전)\n" % (["%.1fMB" % (s / 1e6) for s in sizes], bytes_stream[0] / 1e6))
out.write("메모리: 서버 프로세스 최고 %.0fMB · 러너 하나 최고 %.0fMB · 동시에 본 러너 %d개\n"
          % (peak_server / 1e6, peak_runners / 1e6, n_runners))
out.flush()
