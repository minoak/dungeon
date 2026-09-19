"""Seeded architecture with varied room packing, circulation and optional columns.

D88(2026-09-20): 생성기 본문은 리포 루트의 dungeon_concept.py 로 옮겼다 — 이어가기(D79)가 Dungeon 을 통째로 피클하고
피클은 클래스를 '모듈명.클래스명'으로 되살리므로, 하이픈 폴더(sys.path 밖)의 모듈에 두면 되살리기가 실패한다.
이 파일은 실험실(preview_server.py · verify-architecture.py · verify-decor.mjs)이 그대로 돌게 하는 재수출만 남긴다.
클래스의 __module__ 은 'dungeon_concept' 하나다(같은 클래스를 두 모듈 이름으로 피클하지 않는다)."""
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:                  # 이 파일만 단독으로 import 해도 루트 모듈이 잡히게(preview_server 는 이미 넣는다)
    sys.path.insert(0, _ROOT)

from dungeon_concept import ConceptDungeon  # noqa: E402,F401
