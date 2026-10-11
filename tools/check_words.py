# -*- coding: utf-8 -*-
"""말 파일 검사(D100, 2026-10-06) — prompts/world/ 를 고친 뒤 돌린다:  python tools/check_words.py

정의(entities/<종류>/<id>.json)와 말 파일(prompts/world/<종류>/<id>.md)을 합쳐 읽어 본다. 문제가 있으면 전부 나열하고 1 로 끝난다
(게임도 같은 이유로 안 뜬다 — 문제 줄을 고치면 된다). 밟은 양(정의 수·말 파일 수·말 칸 수)을 같이 찍는다 — '통과'만 찍는 검사는
빈 입력도 통과시키기 때문이다. 정의가 없는 말 파일은 경고로만 찍는다(초안을 먼저 써 둘 수 있다). 실 LLM 0콜.
p0.5.5: 행동 말 파일(prompts/actions/common_extra.md — 관측 '추가 행동' 블록)도 읽어 행동 등록부와 칸을 대조한다."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import entities as ENT   # noqa: E402
import words as WD       # noqa: E402


def main():
    md = sorted(glob.glob(os.path.join(WD.WORDS_ROOT, "*", "*.md")))
    jsons = sorted(glob.glob(os.path.join(ENT.ROOT, "*", "*.json")))
    try:
        defs = ENT.read()
    except ENT.EntityError as e:
        print("문제 %d줄:" % len(str(e).split("\n")))
        print(str(e))
        return 1
    cells = sum(len(WD.word_paths(d.get("comps") or {})) for d in defs.values())
    marked = 0
    for p in jsons:
        with open(p, encoding="utf-8") as f:
            marked += 1 if ('"%s"' % WD.WORD_MARK) in f.read() else 0
    print("정의 %d장 · 말 파일 %d장(표시가 선 정의 %d장) · 말 칸 %d개 — 합쳐 읽기 OK" % (len(defs), len(md), marked, cells))
    for o in WD.orphans(ENT.ROOT):
        print("경고: 정의가 없는 말 파일 — prompts/world/%s (entities/%s.json 이 없다)" % (o, o[:-3]))
    return check_actions()


def check_actions():
    """p0.5.5 행동 말 파일(prompts/actions/) — '추가 행동' 블록의 칸 = header + 행동 등록부(composed_actions.COMMON_EXT)의 동사 전부.
    등록부에 있는데 문장이 없거나(블록에 빈 줄이 갈 뻔) 문장만 있고 동사가 없으면(아무도 안 읽는 말) 문제로 찍는다."""
    import composed_actions as CA
    try:
        items = WD.action_words(CA.EXTRA_WORDS)
    except WD.WordsError as e:
        print("문제(행동 말 파일):")
        print(str(e))
        return 1
    rel = "prompts/actions/%s.md" % CA.EXTRA_WORDS
    want = {"header"} | set(CA.COMMON_EXT)
    problems = ["%s: 등록부 동사 `%s` 의 칸이 없다" % (rel, v) for v in sorted(want - set(items))]
    problems += ["%s: 칸 `%s` 는 등록부에 없는 동사다(composed_actions.COMMON_EXT)" % (rel, k) for k in sorted(set(items) - want)]
    if problems:
        print("문제 %d줄:" % len(problems))
        print("\n".join(problems))
        return 1
    print("행동 말 파일 %s — 칸 %d개(머리 1 · 등록부 동사 %d) — 등록부와 일치" % (rel, len(items), len(CA.COMMON_EXT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
