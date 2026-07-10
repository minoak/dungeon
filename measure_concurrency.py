#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""동시성 측정: claude -p 1개 vs 2개 동시. 지연 설계의 토대 확인용."""
import subprocess, time
from concurrent.futures import ThreadPoolExecutor


def call(word):
    t = time.time()
    try:
        r = subprocess.run(
            ["claude.exe", "-p", "--model", "haiku",
             f"Reply with exactly one word, nothing else: {word}"],
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = (r.stdout or "").strip()
    except Exception as e:
        out = f"<ERR {e}>"
    return time.time() - t, out[:30]


print("측정 시작 (콜드스타트라 각 10~20초 예상)...\n", flush=True)

t = time.time()
d1, o1 = call("ALPHA")
single = time.time() - t
print(f"[1] SINGLE      : {single:5.1f}s   out={o1!r}", flush=True)

t = time.time()
with ThreadPoolExecutor(max_workers=2) as ex:
    f1 = ex.submit(call, "BETA")
    f2 = ex.submit(call, "GAMMA")
    (e1, p1), (e2, p2) = f1.result(), f2.result()
par = time.time() - t
print(f"[2] PARALLEL x2 : {par:5.1f}s   outs={p1!r}, {p2!r}", flush=True)

ratio = par / single if single else 0
verdict = "CONCURRENT (병렬 OK)" if par < single * 1.6 else "SERIALIZED (직렬화됨)"
print(f"\n=> par/single = {ratio:.2f}   판정: {verdict}")
print("   (1.0~1.5 = 진짜 병렬 / 1.8~2.0 = 직렬화 → 동시성 설계 폐기, 이벤트게이팅 강화)")
