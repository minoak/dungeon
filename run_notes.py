# -*- coding: utf-8 -*-
"""판 하나의 캐릭터 기록 읽기(LLM 0콜) — 수첩(D59 `descend/ascend.pages`)·도감평(D55 `decisions.book_line`)·원장 note(bestiary.json).

사용:
  python run_notes.py runs/stream-20260912-222231.jsonl            # 캐릭터별 수첩 장·도감 한 줄 + 원장(bestiary.json)의 그 이름 note
  python run_notes.py runs/stream-....jsonl --ledger ""             # 원장 생략
  python run_notes.py runs/stream-....jsonl --md > notes.md         # 마크다운으로

무엇을 어디서 읽나(전부 판 데이터 — 엔진·프롬프트 무접촉):
  · 수첩 = 층을 떠나는 순간의 `descend`/`ascend` 프레임 `pages{char: 글}`(캐릭터당 한 장, 실패한 캐릭터는 키 없음). 층 번호는 그 프레임 직전 `level.depth`.
  · 도감평 = 그 틱 결정 원본 `decisions[char].book_line{key, text}`(해금 순간 초대 → 답 한 줄, N번 조우 뒤 고쳐 쓸 기회).
  · 원장 = bestiary.json `{이름: {종키: {..., note{text,n,turn,depth}}}}` — 캐릭터 **이름**으로 판을 넘어 남는다(죽어도 남는 지식, D4·D9).
    run_meta.bestiary_progress 는 판 시작 시점의 n/deep 만 있고 note 본문은 없다 → 본문은 원장 파일에서만.
"""
import argparse
import io
import json
import os


def load(path):
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def collect(rows):
    """스트림 → (party 이름표, 수첩 [(turn, depth, char, text)], 도감평 [(turn, depth, char, key, text)])."""
    meta = rows[0] if rows and rows[0].get("kind") == "run_meta" else {}
    names = {str(p.get("char")): (p.get("name") or p.get("job") or str(p.get("char"))) for p in (meta.get("party") or [])}
    pages, books, depth = [], [], 0
    for r in rows:
        k = r.get("kind")
        if k == "level":
            depth = r.get("depth", depth)
        elif k in ("descend", "ascend") and r.get("pages"):
            for c, txt in sorted(r["pages"].items()):
                pages.append((r.get("turn"), depth, c, txt, k))
        elif k == "tick":
            for c, d in sorted((r.get("decisions") or {}).items()):
                bl = d.get("book_line") if isinstance(d, dict) else None
                if isinstance(bl, dict) and bl.get("text"):
                    books.append((r.get("turn"), depth, c, bl.get("key", "?"), bl["text"]))
    return meta, names, pages, books


def ledger_notes(path, names):
    """원장에서 파티 이름들의 note 만 — [(이름, 종키, text, n, turn, depth)]."""
    if not path or not os.path.exists(path):
        return []
    with io.open(path, encoding="utf-8") as f:
        led = json.load(f)
    out = []
    for nm in names.values():
        for key, e in sorted((led.get(nm) or {}).items()):
            if isinstance(e, dict) and isinstance(e.get("note"), dict) and e["note"].get("text"):
                n = e["note"]
                out.append((nm, key, n["text"], n.get("n"), n.get("turn"), n.get("depth")))
    return out


def render(meta, names, pages, books, notes, md=False):
    h1, h2, bullet = ("# ", "## ", "- ") if md else ("== ", "-- ", "  · ")
    lines = [h1 + "판 %s (seed %s) — 캐릭터 기록: 수첩 %d장 · 도감평 %d줄 · 원장 note %d" % (
        os.path.basename(meta.get("_file", "")), meta.get("seed"), len(pages), len(books), len(notes))]
    for c in sorted(names):
        nm = names[c]
        lines += ["", h2 + "%s(봇%s)" % (nm, c)]
        mine = [p for p in pages if p[2] == c]
        lines.append(bullet + "수첩 %d장" % len(mine))
        for turn, depth, _, txt, kind in mine:
            where = "%d층을 떠나며" % depth if kind == "descend" else "%d층에서 올라가며" % depth
            lines.append("    [t%s · %s] %s" % (turn, where, txt))
        mine_b = [b for b in books if b[2] == c]
        lines.append(bullet + "도감평(이 판에서 쓴 것) %d줄" % len(mine_b))
        for turn, depth, _, key, txt in mine_b:
            lines.append("    [t%s · %d층 · %s] %s" % (turn, depth, key, txt))
        mine_n = [n for n in notes if n[0] == nm]
        if mine_n:
            lines.append(bullet + "원장(bestiary.json, 판을 넘어 남는 것) %d줄" % len(mine_n))
            for _, key, txt, n, turn, depth in mine_n:
                lines.append("    [%s · 조우 %s · t%s/%s층에 씀] %s" % (key, n, turn, depth, txt))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stream")
    ap.add_argument("--ledger", default="bestiary.json", help="원장 파일(빈 문자열이면 생략)")
    ap.add_argument("--md", action="store_true", help="마크다운 머리글로")
    a = ap.parse_args()
    rows = load(a.stream)
    meta, names, pages, books = collect(rows)
    meta = dict(meta, _file=a.stream)
    notes = ledger_notes(a.ledger, names)
    print(render(meta, names, pages, books, notes, md=a.md))


if __name__ == "__main__":
    main()
