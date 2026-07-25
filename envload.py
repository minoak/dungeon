#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""최소 .env 로더 — python-dotenv 미설치 환경(이 WSL 엔 pip 이 없다)용.

⚠️ **어디서 부르는지가 이 파일의 전부다.**
  · 부른다   : show_runner / scenario 의 `if __name__ == "__main__":` 안, 벤치 하니스
  · 안 부른다: verify_*.py / _smoke_*.py / _test_*.py / brains.py / 모듈 최상단

게이트 프로세스에 키가 **없는 것**이 구조적 안전핀이다: 백엔드가 키 없으면 소켓을 열기 전에
끊으므로, 게이트가 _call_claude 모킹을 빠뜨려도 실 API 가 물리적으로 못 나간다. 게이트는
`import show_runner; show_runner.main()` 으로 부르기 때문에 __main__ 훅을 밟지 않는다.
이 레포는 env 오염으로 이미 두 번 데였다(start.sh 의 DUNGEON_STATE_DIR unset 두 번,
verify.sh 의 DUNGEON_BESTIARY_FILE unset) — 그 학습의 계승: 위험한 값은 그 프로세스에
아예 없게 한다.

파싱은 일부러 멍청하게 뒀다: export 접두어·다중행·변수보간 전부 미지원. KEY=VALUE 한 줄씩.
이미 세팅된 env 는 덮지 않는다 — 셸에서 명시한 값이 항상 이긴다.
"""
import os


def load(path=None):
    """.env 를 읽어 os.environ 에 채운다(이미 있는 키는 보존). 반환 = 새로 채운 개수."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            body = f.read()
    except OSError:
        return 0                       # 없으면 조용히 통과 — .env 는 선택 사항이다
    n = 0
    for ln in body.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]                # 따옴표로 감싼 값 관용(넣지 말라고 문서화했지만 흡수)
        if not k or not v:
            continue                   # 빈 값은 안 채운다 — 빈 문자열 키가 '있는 키'로
        if k not in os.environ:        #   행세하면 백엔드의 NoAPIKey 단락이 안 걸린다
            os.environ[k] = v
            n += 1
    return n
