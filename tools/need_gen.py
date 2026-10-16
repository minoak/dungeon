# -*- coding: utf-8 -*-
"""동료 프리셋·기본 파티의 욕구 무게·입맛을 정해 데이터에 적는다(p0.5.20 — .orch/drafts/economy_design.md §3.8.2 '저장 자리' · §10-16).

론처의 생성 호출(need_gen.py)과 같은 프롬프트·검증·해시를 쓴다. 대상(지금 6명):
  · 동료 프리셋 entities/companion/<id>.json 의 comps.sheet 에 needs·taste·needs_meta (두란·카야·피른)
  · 기본 파티 party.json 의 각 칸에 "needs"·"taste"·"needs_meta" (같은 세 사람 — 손으로 맞춘 줄 배치를 지키려고 그 칸의 "name" 줄 바로 뒤에
    한 줄씩 끼운다. 끼운 결과가 JSON 으로 다시 읽히지 않으면 파일 전체를 들여쓰기 2칸으로 다시 쓰고 그렇다고 찍는다)
⚠️ 기본은 **부르지 않는다** — 대상·지금 상태·프롬프트만 찍는다(0콜). --run 을 줘야 모델을 부른다(1명 = 1콜 · 시간 초과·서버 오류면 한 번 더).
   민옥이 결과를 확인한 뒤 커밋한다(DECISIONS 10-15 §10-16 — 실행자는 돌리지 않는다, 관리자가 민옥 확인 뒤 돌린다).

쓰는 법(리포 루트에서):
  python tools/need_gen.py                                                    # 대상·상태·프롬프트만(0콜)
  python tools/need_gen.py --run --brain anthropic_api --model claude-haiku-5-5   # 6명을 정해 적는다(키는 .env 또는 환경변수 — 6콜)
  python tools/need_gen.py --run --brain gemini_api --only duran,party:1          # 고른 대상만(동료 id · party:<칸 번호>)
  python tools/need_gen.py --run --brain anthropic_api --force                    # 이미 정했고 낡지 않은 대상도 다시
옵션: --root(리포 대신 사본 폴더 — entities/·party.json 이 있는 곳, 게이트가 쓴다) · --model 을 비우면 그 회사의 기본 모델(brain_config).
이미 정했고 낡지 않은 대상은 건너뛴다. 모델에 닿지 못하면(키 없음·인증·연결) 그 자리에서 멈춘다 — 앞에서 정한 것은 적는다.
끝에 대상마다 한 줄(보통이 아닌 등급·근거·입맛)을 찍는다.
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import entities as ENT                    # noqa: E402
import need_gen as NG                     # noqa: E402
import sheetkit                           # noqa: E402
from brain_config import BACKENDS         # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _fields(out):
    """generate 결과 → 데이터에 적을 칸(입맛이 비면 칸을 두지 않는다 — 시트 검증기가 빈 입맛을 걷으므로 동료 정의 검사와 맞춘다)."""
    tt = out.get("taste") or {}
    return {"needs": out["needs"], **({"taste": tt} if (tt.get("likes") or tt.get("dislikes")) else {}), "needs_meta": out["needs_meta"]}


def targets(root):
    """[(이름표, 시트)] — 동료(id 순) 다음 기본 파티(칸 번호 순). 시트는 론처·러너가 보는 것과 같은 조립(낡음 해시가 같게)."""
    defs = ENT.read(os.path.join(root, "entities"))
    out = [(cid, sheetkit.build_companion_sheet(d)) for cid, d in sorted((k, v) for k, v in defs.items() if v.get("kind") == "companion")]
    with io.open(os.path.join(root, "party.json"), encoding="utf-8") as f:
        party = json.load(f)
    out += [("party:%s" % c, party[c]) for c in sorted(k for k in party if not k.startswith("_")) if isinstance(party[c], dict)]
    return out


def _write_companion(root, cid, fields):
    path = os.path.join(root, "entities", "companion", cid + ".json")
    with io.open(path, encoding="utf-8") as f:
        raw = json.load(f)
    sheet = raw["comps"]["sheet"]
    for k in sheetkit.NEED_FIELDS:
        sheet.pop(k, None)
    sheet.update(fields)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")


def _insert_party(text, c, fields):
    """party.json 글에서 칸 c 의 "name" 줄 뒤에 욕구 칸을 한 줄씩(옛 욕구 줄은 걷는다). 줄 배치를 못 찾으면 None."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if re.match(r'\s*"%s"\s*:\s*\{\s*$' % re.escape(c), ln)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if re.match(r'\s*"\d"\s*:\s*\{', lines[i]) or lines[i].startswith("}")), len(lines))
    body = [ln for ln in lines[start + 1:end] if not re.match(r'\s*"(needs|taste|needs_meta)"\s*:', ln)]
    at = next((i for i, ln in enumerate(body) if re.match(r'\s*"name"\s*:', ln)), None)
    if at is None:
        return None
    ind = re.match(r"\s*", body[at]).group(0)
    new = [ind + '"%s": %s,' % (k, json.dumps(v, ensure_ascii=False)) for k, v in fields.items()]
    return "\n".join(lines[:start + 1] + body[:at + 1] + new + body[at + 1:] + lines[end:])


def _write_party(root, by_char):
    """기본 파티에 적는다 → 줄 배치를 지켰나(False 면 전체를 다시 썼다)."""
    path = os.path.join(root, "party.json")
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    doc = json.loads(text)
    new = text
    for c, fields in by_char.items():
        new = _insert_party(new, c, fields) if new is not None else None
    try:
        back = json.loads(new) if new is not None else None
    except ValueError:
        back = None
    kept = back is not None and all({k: back[c].get(k) for k in fields} == fields for c, fields in by_char.items())
    if not kept:
        for c, fields in by_char.items():
            for k in sheetkit.NEED_FIELDS:
                doc[c].pop(k, None)
            doc[c].update(fields)
        new = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    return kept


def summary(tag, sheet):
    nd, tt = sheet.get("needs") or {}, sheet.get("taste") or {}
    names = {n["id"]: n["name"] for n in NG.need_list()}
    odd = ["%s %s(%s)" % (names.get(k, k), e["level"], e.get("why", "")) for k, e in sorted(nd.items()) if e.get("level") != "보통"]
    return "%-10s %s · 입맛 좋아함 %s 싫어함 %s" % (tag, " · ".join(odd) or "모두 보통", tt.get("likes") or "-", tt.get("dislikes") or "-")


def run(root, brain, call, only=None, force=False, log=print):
    """정해서 적는다 → {이름표: 칸}. call(prompt) → (text, label, model) — 게이트는 가짜를 넣는다. 못 닿으면 앞의 것을 적고 NeedGenError 를 올린다."""
    done, err = {}, None
    for tag, sheet in targets(root):
        if only and tag not in only:
            continue
        st = NG.state(sheet)
        if st["state"] == "fresh" and not force:
            log("건너뜀 %s — 이미 정했다(%s)" % (tag, (sheet.get("needs_meta") or {}).get("at", "?")))
            continue
        try:
            done[tag] = _fields(NG.generate(sheet, brain, call))
        except NG.NeedGenError as e:
            err = e
            log("멈춤 %s — %s" % (tag, e.label))
            break
    for tag, fields in done.items():
        if not tag.startswith("party:"):
            _write_companion(root, tag, fields)
    party = {tag.split(":", 1)[1]: fields for tag, fields in done.items() if tag.startswith("party:")}
    if party and not _write_party(root, party):
        log("party.json: 줄 배치를 찾지 못해 전체를 들여쓰기 2칸으로 다시 썼다")
    for tag, fields in done.items():
        log(summary(tag, fields))
    if err:
        raise err
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description="동료 프리셋·기본 파티의 욕구 무게·입맛을 정해 데이터에 적는다(기본은 0콜 — --run 을 줘야 부른다)")
    ap.add_argument("--run", action="store_true", help="모델을 부른다(대상 1명 = 1콜)")
    ap.add_argument("--brain", default="anthropic_api", help="두뇌 — %s 중 하나(dummy 제외)" % "/".join(b for b in BACKENDS if b != "dummy"))
    ap.add_argument("--model", default=None, help="모델 id(비우면 그 회사의 기본 — brain_config)")
    ap.add_argument("--only", default="", help="쉼표로 고른 대상(동료 id · party:<칸 번호>)")
    ap.add_argument("--force", action="store_true", help="이미 정했고 낡지 않은 대상도 다시")
    ap.add_argument("--root", default=HERE, help="entities/·party.json 이 있는 폴더(기본 리포)")
    a = ap.parse_args(argv)
    only = [x.strip() for x in a.only.split(",") if x.strip()] or None
    ts = [(t, s) for t, s in targets(a.root) if not only or t in only]
    if not a.run:
        for tag, sheet in ts:
            st = NG.state(sheet)
            print("── %s · %s%s" % (tag, st["state"], (" (" + ", ".join(st["why"]) + ")") if st["why"] else ""))
        if ts:
            print("\n── 프롬프트(%s)\n%s" % (ts[0][0], NG.build_prompt(ts[0][1])))
        print("\n(0콜 — 부르려면 --run --brain <두뇌> [--model <모델>])")
        return 0
    if a.brain not in BACKENDS or a.brain == "dummy":
        print("두뇌는 %s 중 하나" % "/".join(b for b in BACKENDS if b != "dummy"), file=sys.stderr)
        return 2
    import envload
    envload.load()                         # 키는 .env 에서(셸에서 준 값이 이긴다) — 자식 프로세스 env 로만 간다
    env = NG.call_env(a.brain, a.model)
    try:
        run(a.root, a.brain, lambda p: NG.call_model(p, env), only=only, force=a.force)
    except NG.NeedGenError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
