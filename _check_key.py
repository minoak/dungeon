# -*- coding: utf-8 -*-
"""API 키 점검 — 실 콜 **1회**로 두뇌가 살아 있는지 본다.

왜: 키가 맞는지 확인하려고 350원짜리 판을 25분 돌릴 수는 없다. 판을 시작하기 전에
1콜(약 0.2원)로 끝낸다.

⚠️ **키 값은 절대 출력하지 않는다** — 길이와 끝 4자리 지문만. 이 레포는 state/·runs/ 를
실제로 커밋하므로 비밀값이 화면에 찍히는 것부터 막는다(verify_brain ⑩과 같은 규율).

사용:
    python3 ~/dungeon/_check_key.py              # 기본 gemini_api
    DUNGEON_BRAIN_BACKEND=anthropic_api python3 ~/dungeon/_check_key.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DUNGEON_BRAIN_BACKEND", "gemini_api")

import envload                                                    # noqa: E402
n = envload.load()                                                # __main__ 이라 로드해도 된다

import brains                                                     # noqa: E402

BACKEND = brains.backend_name()
KEYNAME = {"gemini_api": "GEMINI_API_KEY",
           "anthropic_api": "ANTHROPIC_API_KEY"}.get(BACKEND)

print("백엔드 : %s" % BACKEND)
print(".env   : %d개 값 로드" % n)

if KEYNAME:
    key = os.environ.get(KEYNAME) or ""
    if not key:
        print("키     : %s 없음 — .env 에 넣어야 한다" % KEYNAME)
        raise SystemExit(2)
    print("키     : %s 있음 (%d자, ...%s)" % (KEYNAME, len(key), key[-4:]))
else:
    print("키     : 이 백엔드는 키를 안 쓴다")

print()
print("1콜 프로브 — 두뇌에게 아주 짧은 걸 묻는다...")
t0 = time.time()
raw, why = brains._call_claude(
    '오직 JSON 한 줄로만 답하라: {"ok":"yes"}', "haiku")
ms = int((time.time() - t0) * 1000)

if why:
    print("  실패 : %s  (%dms)" % (why, ms))
    print()
    print("  라벨 읽는 법: 'rc=401' 키가 틀림 · 'rc=429' 한도·과금 · 'rc=400' 요청 형식")
    print("               '타임아웃' 네트워크 · '빈 응답' 모델이 아무것도 안 줌")
    raise SystemExit(1)

print("  성공 : %dms" % ms)
print("  응답 : %s" % (raw or "").strip()[:120])
print()
print("판 돌려도 된다.")
