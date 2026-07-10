#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GM 진행자 — claude.exe -p --model sonnet 로 매 턴 events를 '장면'으로 연출 (레이어 4).
brains.py(봇 두뇌)와 같은 방식: claude.exe -p, 프롬프트 stdin, 구독 과금 0.
시스템 프롬프트 = gm_prompt.md (사관 → 던전 마스터로 전환).
GM에겐 이 턴의 진실(events + party)만 준다 — 맵 전체 X. 없는 것 창작 금지는 프롬프트에 내장.
반환: 내레이션 텍스트(실패 시 'GM 침묵').
"""
import os
import json
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE_BIN = "claude.exe"   # brains.py와 동일(npm 래퍼는 stdin 멈춤)
TIMEOUT = int(os.environ.get("DUNGEON_GM_TIMEOUT", "60"))
MODEL = os.environ.get("DUNGEON_GM_MODEL", "sonnet")   # 페이싱 급하면 haiku 강등 가능

_p = os.path.join(HERE, "gm_prompt.md")
GM_PROMPT = open(_p, encoding="utf-8").read() if os.path.exists(_p) else ""

_CAST = ""   # 등장인물 블록(시트 외부화, 파티 가변) — set_party 가 채운다. 미설정=폴백(char/job 호칭)


def set_party(sheets):
    """러너가 시작 때 1회 호출: {char: sheet} → 등장인물 명단(이름·직업·성격·말투).
    GM 은 이 명단 밖 인물을 창작하지 않는다."""
    global _CAST
    lines = ["[등장인물 — 이 명단이 파티의 전부다. 명단 밖 인물 창작 금지]"]
    for c in sorted(sheets):
        s = sheets[c]
        nm = s.get("name") or ("모험가 %s" % c)
        lines.append("- 봇%s **%s** — %s(%s): %s"
                     % (c, nm, s.get("job", ""), s.get("sex", ""), s.get("persona", "")))
        if s.get("speech"):
            lines.append("  · 말투: %s" % s["speech"])
    _CAST = "\n".join(lines)


def narrate(turn, events, party):
    """events: 이 턴 봇 행동(판정 포함) + 몬스터 행동. party: 파티(가변 인원) 현재 상태."""
    if not GM_PROMPT:
        return "(gm_prompt.md 없음 — GM 침묵)"
    pkg = {"turn": turn, "party": party, "events": events}
    prompt = (GM_PROMPT + (("\n\n" + _CAST) if _CAST else "")
              + "\n\n## 이번 턴 (JSON)\n" + json.dumps(pkg, ensure_ascii=False))
    try:
        r = subprocess.run(
            [CLAUDE_BIN, "-p", "--model", MODEL],
            input=prompt, capture_output=True,
            text=True, encoding="utf-8", timeout=TIMEOUT)
        return (r.stdout or "").strip() or "(GM 침묵)"
    except Exception as e:
        return f"(GM 침묵: {e})"
