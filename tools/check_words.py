# -*- coding: utf-8 -*-
"""말 파일 검사(D100, 2026-10-06) — prompts/world/ 를 고친 뒤 돌린다:  python tools/check_words.py

정의(entities/<종류>/<id>.json)와 말 파일(prompts/world/<종류>/<id>.md)을 합쳐 읽어 본다. 문제가 있으면 전부 나열하고 1 로 끝난다
(게임도 같은 이유로 안 뜬다 — 문제 줄을 고치면 된다). 밟은 양(정의 수·말 파일 수·말 칸 수)을 같이 찍는다 — '통과'만 찍는 검사는
빈 입력도 통과시키기 때문이다. 정의가 없는 말 파일은 경고로만 찍는다(초안을 먼저 써 둘 수 있다). 실 LLM 0콜.
p0.5.5: 행동 말 파일(prompts/actions/common_extra.md — 관측 '추가 행동' 블록)도 읽어 행동 등록부와 칸을 대조한다.
p0.5.6: 아이템의 다루는 규칙(prompts/actions/item_rules.md)은 정의 읽기(ENT.read)가 아이템 type 과 대조한다 — 여기서는 밟은 양을 찍는다.
p0.5.18: 기분 낱말(prompts/world/mood.md — '기분:' 줄의 좋다·좋지 않다·이유)도 정의 읽기가 칸을 대조한다 — 여기서는 밟은 양을 찍는다.
p0.5.23: 위치 낱말(prompts/world/place.md — '현재 위치:' 줄)도 같다.
p0.5.28: 동사 설명(prompts/world/verb/<동사>.md)은 위 합쳐 읽기에 든다 — 동사 세트(entities/verb_set.json)가 정의·처리기와 맞는지도 본다."""
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
    items = [d for d in defs.values() if (d.get("comps") or {}).get("item")]   # p0.5.6 — 꼴(설명·규칙 칸 대조)은 ENT.read 가 이미 봤다
    print("아이템 정의 %d장(설명 %d개) · 다루는 규칙 prompts/actions/%s.md — 칸 %d개 = 아이템 type(%s)"
          % (len(items), sum(1 for d in items if d["comps"]["item"].get("desc")), ENT.ITEM_RULES,
             len(WD.action_words(ENT.ITEM_RULES)), "·".join(ENT.ITEM_TYPES)))
    print("기분 낱말 prompts/world/%s.md — 칸 %d개(%s)" % (ENT.MOOD_WORDS, len(WD.world_words(ENT.MOOD_WORDS)), "·".join(ENT.MOOD_WORD_KEYS)))   # p0.5.18 — 꼴은 ENT.read 가 이미 봤다
    print("위치 낱말 prompts/world/%s.md — 칸 %d개(%s)" % (ENT.PLACE_WORDS, len(WD.world_words(ENT.PLACE_WORDS)), "·".join(ENT.PLACE_WORD_KEYS)))   # p0.5.23 — 꼴은 ENT.read 가 이미 봤다
    return check_verbs(defs) or check_actions()


def check_verbs(defs):
    """p0.5.28 동사 세트(entities/verb_set.json) — 세트의 동사마다 동사 정의가 있고(설명은 말 파일 — 위 합쳐 읽기가 봤다) 처리기 열쇠가 엔진에 있는지,
    같은 동사가 두 번 없는지(composed_actions.read_set — 게임이 뜰 때와 같은 검사). 세트 밖 동사 정의는 읽히기만 한다(개수만 찍는다)."""
    try:
        import composed_actions as CA      # 모듈을 읽을 때 기본 세트를 쓴다 — 세트가 틀리면 여기서 VerbError(ValueError)
        names, _ = CA.read_set()
    except ValueError as e:
        print("문제(동사 세트):")
        print(str(e))
        return 1
    verbs = [d for d in defs.values() if d.get("kind") == "verb"]
    print("동사 세트 entities/%s — 동사 %d개(%s) · 동사 정의 %d장 · 처리기 %d개 — 세트와 정의·처리기 일치"
          % (os.path.basename(CA.VERB_SET), len(names), "·".join(names), len(verbs), len(CA.HANDLERS)))
    return 0


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
