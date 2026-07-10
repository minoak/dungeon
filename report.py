#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
원정 보고서 생성기 — 스트림+태그 원장 → 사람이 읽는 HTML. (D11②, 첫 웹 산출물)
─────────────────────────────────────────────
입력: 판 폴더(stream.jsonl). 태그는 tags.issue()로 그 자리에서 발급(결정론 — 원장과 항상 일치).
출력: reports/<판이름>.html + index.html. 자체 완결(외부 리소스 0), 라이트/다크.

문법: DF 전설모드(연대기 문장) + EVE 킬메일(전투 카드에 굴림 수치 전부).
reason 승격 — 판단(속내)을 사건 옆에 인용한다. 단 폴백 결정의 reason 은 판단이
아니라 계측 라벨이므로 '규칙 두뇌 대행'으로 표기하고 인용하지 않는다.

사용:  python3 report.py <run_dir>... [-o reports]
"""
import os
import sys
import json
import html
import collections

import tags as T

ESC = html.escape

# ── 이름 해소: run_meta.party.name(additive) → party.json(직업 일치 시) → 직업 ──
def resolve_names(meta_party):
    names = {}
    pj = {}
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "party.json"), encoding="utf-8") as f:
            pj = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    except Exception:
        pj = {}
    for p in meta_party or []:
        c = p.get("char")
        nm = p.get("name")
        if not nm:
            cand = pj.get(c) or {}
            if cand.get("name") and cand.get("job") == p.get("job"):
                nm = cand["name"]         # 구판 스트림: 시트 직업이 맞을 때만 현행 이름 차용
        names[c] = nm or p.get("job") or ("모험가 %s" % c)
    return names


def load_run(run_dir):
    lines = T.read_stream(os.path.join(run_dir, "stream.jsonl"))
    by_line = dict(lines)
    meta = next((o for _, o in lines if o.get("kind") == "run_meta"), {})
    end = next((o for _, o in lines if o.get("kind") == "end"), None)
    ticks = [(ln, o) for ln, o in lines if o.get("kind") == "tick"]
    tags_ = T.issue(lines)
    return {"dir": run_dir, "name": os.path.basename(os.path.normpath(run_dir)),
            "lines": lines, "by_line": by_line, "meta": meta, "end": end,
            "ticks": ticks, "tags": tags_, "names": resolve_names(meta.get("party"))}


# ── 통계 집계(캐릭터별 전과 + 결정 계기판) ──
def char_stats(run):
    st = {p["char"]: collections.Counter() for p in run["meta"].get("party", [])}
    quotes = {c: [] for c in st}      # (turn, say)
    minds = {c: [] for c in st}       # (turn, type, reason)
    for _, o in run["ticks"]:
        turn = o.get("turn", 0)
        for c, d in (o.get("decisions") or {}).items():
            if d.get("skipped") or c not in st:
                continue
            if d.get("say"):
                quotes[c].append((turn, d["say"]))
            if d.get("src") != "fallback" and d.get("reason"):
                minds[c].append((turn, d.get("type"), d["reason"]))
        for e in o.get("events") or []:
            c = e.get("char")
            t = e.get("type")
            if t == "attack" and e.get("result") == "attack" and e.get("hit") and c in st:
                st[c]["dealt"] += e.get("dmg") or 0
            if t == "monster_attack" and e.get("hit") and e.get("target") in st:
                st[e["target"]]["taken"] += e.get("dmg") or 0
            tr = e.get("trap") if t == "walk" else None
            if tr and not tr.get("safe") and c in st:
                st[c]["taken"] += tr.get("dmg") or 0
            if t == "interact" and e.get("result") in ("chest_trap", "fountain_harm") and c in st:
                st[c]["taken"] += e.get("dmg") or 0
    for t in run["tags"]:
        if t["axis"] == "char" and t["subject"] in st:
            # 보물은 사건 수가 아니라 아이템 수(상자 loot=2)로 — 최종 bag(엔진 진실)과 일치
            inc = (t["detail"].get("loot") or 1) if t["kind"] == "treasure" else 1
            st[t["subject"]][t["kind"]] += inc
    return st, quotes, minds


def decision_board(run):
    total = fb = say_n = 0
    fb_kinds = collections.Counter()
    hurt_next = collections.Counter()
    for _, o in run["ticks"]:
        for c, d in (o.get("decisions") or {}).items():
            if d.get("skipped"):
                continue
            total += 1
            if d.get("say"):
                say_n += 1
            if d.get("src") == "fallback":
                fb += 1
                r = d.get("reason") or ""
                label = r.replace("[폴백] ", "").replace(" -> 규칙두뇌", "")
                # 버킷은 실패 종류까지만 — '빈 응답 rc=1 | <stderr>' 의 가변 꼬리를 떼어낸다
                fb_kinds[label.split(" | ")[0].split(":")[0].strip()] += 1
    for t in run["tags"]:
        if t["kind"] == "hurt_decision":
            hurt_next[t["detail"].get("next")] += 1
    return {"total": total, "fallback": fb, "fb_kinds": fb_kinds,
            "says": say_n, "hurt_next": hurt_next}


# ── 마지막 스냅샷(최종 HP·생사) ──
def final_bots(run):
    if run["end"] and run["end"].get("bots"):
        return {b["char"]: b for b in run["end"]["bots"]}
    if run["ticks"]:
        return {b["char"]: b for b in run["ticks"][-1][1].get("bots", [])}
    return {}


# ── 연대기 문장 렌더러 ──
def _roll(e):
    """EVE 킬메일 문법: 굴림 수치를 있는 그대로 — 단, 있는 필드만
    (chest_trap 엔 ac 가, fountain_harm 엔 mod/total/ac 가 없다)."""
    bits = []
    if e.get("roll") is not None:
        if e.get("total") is not None and e.get("ac") is not None:
            bits.append("d20 %s%+d=%s vs AC %s" % (e["roll"], e.get("mod", 0),
                                                   e["total"], e["ac"]))
        elif e.get("total") is not None and e.get("dc") is not None:
            bits.append("d20 %s%+d=%s vs DC %s" % (e["roll"], e.get("mod", 0),
                                                   e["total"], e["dc"]))
        else:
            bits.append("d20 %s" % e["roll"])
    if e.get("dmg") is not None:
        bits.append("피해 %s" % e["dmg"])
    if e.get("crit"):
        bits.append("치명타!")
    if e.get("surprise"):
        bits.append("기습")
    return " · ".join(bits)


def describe(t, ev, names):
    """태그 하나 → (아이콘, 제목, 상세). ev = 원천 이벤트(있으면)."""
    d = t["detail"]
    n = names.get(t["subject"], t["subject"])
    k = t["kind"]
    if k == "first_blood":
        return "⚔", "%s — 이 원정의 선혈" % n, "%s 처치" % d.get("monster", "")
    if k == "kill":
        return "⚔", "%s — %s 처치" % (n, d.get("monster", "")), _roll(ev or {})
    if k == "critical_hit":
        return "✦", "%s — 회심의 일격" % n, _roll(ev or {})
    if k == "we_ambush":
        return "⚔", "%s — 기습 성공" % n, "%s 상대로 선제 일격" % d.get("monster", "")
    if k == "ambushed":
        return "☄", "%s — 기습당함" % n, "%s의 일격 · 피해 %s" % (d.get("monster", ""), d.get("dmg"))
    if k == "fallen":
        return "☠", "%s 전사" % n, "사인: %s" % d.get("cause", "?") + \
            ((" · " + _roll(ev)) if ev and ev.get("roll") is not None else "")
    if k == "hurt_decision":
        nx = {"attack": "반격", "goto": "이동(핑)", "explore": "탐색",
              "search": "수색", "interact": "상호작용"}.get(d.get("next"), d.get("next"))
        via = " (규칙 두뇌 대행)" if d.get("src") == "fallback" else ""
        return "♥", "%s — 맞고 멈춰 생각하다" % n, "t%s 피격 → 선택: %s%s" % (d.get("hurt_turn"), nx, via)
    if k == "trap_bitten":
        return "⚠", "%s — %s에 걸림" % (n, d.get("name", "함정")), \
            "판정 %s vs DC %s · 피해 %s" % (d.get("total"), d.get("dc"), d.get("dmg")) + \
            (" · 경보! 몹 %s 기상" % d["alarm"] if d.get("alarm") else "")
    if k == "trap_dodged":
        return "⚠", "%s — %s 회피" % (n, d.get("name", "함정")), \
            "판정 %s vs DC %s" % (d.get("total"), d.get("dc"))
    if k == "spotted_trap":
        return "👁", "%s — 함정 간파" % n, "%s (%s)" % (d.get("name", ""), "능동 수색" if d.get("via") == "search" else "지나며 알아챔")
    if k == "spotted_lurker":
        return "👁", "%s — 매복 간파" % n, "%s의 그림자를 알아챘다" % d.get("name", "")
    if k == "spotted_treasure":
        return "👁", "%s — 숨은 보물 발견" % n, d.get("name", "")
    if k == "treasure":
        src = {"chest": "상자에서", "walk": "길에서", "interact": ""}.get(d.get("src"), "")
        extra = (" %s" % d.get("loot")) if d.get("loot") else ""
        return "◆", "%s — 보물 획득" % n, (src + extra).strip()
    if k == "chest_stung":
        return "⚠", "%s — 상자의 독침" % n, "피해 %s" % d.get("dmg")
    if k == "fountain_blessed":
        return "♨", "%s — 샘의 축복" % n, "회복 %s" % d.get("heal")
    if k == "fountain_cursed":
        return "♨", "%s — 오염된 샘" % n, "피해 %s" % d.get("dmg")
    if k == "survivor":
        return "🛡", "%s — 생환" % n, ""
    if k == "unscathed":
        return "🛡", "%s — 무결" % n, "상처 하나 없이 (HP %s)" % d.get("hp")
    if k == "close_call":
        return "♥", "%s — 구사일생" % n, "한때 HP %s까지 몰렸다" % d.get("min_hp")
    if k == "lone_wolf":
        return "…", "%s — 홀로 걷는 자" % n, "%s틱 넘게 동료와 떨어져 있었다" % d.get("ticks")
    if k == "shoulder_to_shoulder":
        a, b = (t["subject"].split("+") + ["?", "?"])[:2]
        return "∥", "%s · %s — 어깨를 나란히" % (names.get(a, a), names.get(b, b)), \
            "%s틱을 붙어 다녔다" % d.get("ticks")
    if k == "first_encounter":
        return "◎", "첫 조우 — %s" % d.get("monster", "?"), "도감에 기록되었다"
    if k == "descended":
        return "▼", "파티 강하 — 지하 %s층으로" % d.get("to_depth"), \
            "함께 내려간 자: %s" % ", ".join(names.get(c, c) for c in d.get("party") or [])
    if k == "outcome":
        oc = {"escaped": "던전 돌파", "wiped": "전멸", "timeout": "시간 종료"}.get(d.get("outcome"), d.get("outcome"))
        return "▣", "원정 결말 — %s" % oc, ""
    return "·", k, ""


def quote_for(t, run):
    """태그 순간의 판단·발언 — 원천 틱의 그 캐릭터 decision 에서. 폴백은 인용하지 않는다."""
    if t["axis"] != "char":
        return None
    o = run["by_line"].get(t["line"])
    if not o or o.get("kind") != "tick":
        return None
    d = (o.get("decisions") or {}).get(t["subject"])
    if not d or d.get("skipped") or d.get("src") == "fallback":
        # 원천 이벤트에 붙은 reason(재결정 행동)도 시도
        if t["ev"] is not None:
            e = (o.get("events") or [])[t["ev"]]
            r = e.get("reason")
            if r and not r.startswith("[폴백]"):
                return (r, None)
        return None
    return (d.get("reason") or None, d.get("say") or None)


# ── HTML ──
CSS = """
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --line:#e1e0d9; --ring:rgba(11,11,11,.10);
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b; --serious:#ec835a;
  --good-ink:#006300; --hp:#2a78d6;
}
@media (prefers-color-scheme: dark){
  :root{
    --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --line:#2c2c2a; --ring:rgba(255,255,255,.10); --good-ink:#0ca30c; --hp:#3987e5;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:880px;margin:0 auto;padding:28px 20px 60px}
a{color:inherit}
h1{font-size:22px;margin:0 0 2px}
.sub{color:var(--ink2);font-size:13px;margin-bottom:14px}
.banner{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border-radius:8px;
  font-weight:600;font-size:14px;border:1px solid var(--ring);margin-bottom:18px}
.banner .dot{width:10px;height:10px;border-radius:50%}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:14px 0 22px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:12px 14px}
.tile .v{font-size:24px;font-weight:650}
.tile .l{font-size:12px;color:var(--ink2)}
.tile .d{font-size:11.5px;color:var(--muted);margin-top:2px}
h2{font-size:15px;color:var(--ink2);margin:26px 0 10px;letter-spacing:.02em}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:14px 16px}
.card h3{margin:0;font-size:16px}
.card .job{color:var(--ink2);font-size:12.5px;margin-bottom:8px}
.hp{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin:4px 0 2px}
.hp i{display:block;height:100%;border-radius:4px;background:var(--hp)}
.hp.dead i{background:var(--crit)}
.hpl{font-size:12px;color:var(--ink2);margin-bottom:8px}
.stats{font-size:12.5px;color:var(--ink2);display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.stats b{color:var(--ink);font-weight:650}
.badges{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0 8px}
.badge{font-size:11.5px;padding:2px 8px;border:1px solid var(--ring);border-radius:999px;color:var(--ink2)}
.badge b{color:var(--ink);font-weight:600}
.quote{font-size:13px;margin:6px 0 0;padding-left:10px;border-left:2px solid var(--line)}
.quote .t{color:var(--muted);font-size:11px;margin-right:4px}
.mind{color:var(--ink2);font-style:italic}
.tl{list-style:none;margin:0;padding:0;border-left:2px solid var(--line)}
.tl li{position:relative;padding:7px 0 7px 22px}
.tl .ico{position:absolute;left:-11px;top:8px;width:20px;height:20px;border-radius:50%;
  background:var(--surface);border:1px solid var(--ring);display:flex;align-items:center;
  justify-content:center;font-size:11px}
.tl .turn{color:var(--muted);font-size:11.5px;font-variant-numeric:tabular-nums;margin-right:6px}
.tl .title{font-weight:600;font-size:13.5px}
.tl .det{color:var(--ink2);font-size:12.5px}
.tl .q{font-size:12.5px;color:var(--ink2);margin-top:2px;padding-left:9px;border-left:2px solid var(--line)}
.tl li.grave .title{color:var(--crit)}
table{width:100%;border-collapse:collapse;font-size:12px;background:var(--surface);
  border:1px solid var(--ring);border-radius:10px;overflow:hidden}
th,td{padding:6px 9px;text-align:left;border-top:1px solid var(--line);vertical-align:top}
thead th{border-top:none;color:var(--ink2);font-weight:600;background:var(--surface)}
td.num{font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto;border-radius:10px}
.foot{margin-top:26px;color:var(--muted);font-size:11.5px}
.idx td a{text-decoration:none;font-weight:600}
.idx .oc{font-weight:600}
"""

OC = {"escaped": ("던전 돌파", "var(--good)", "🛡"),
      "wiped":   ("전멸",     "var(--crit)", "☠"),
      "timeout": ("시간 종료", "var(--warn)", "⏳"),
      None:      ("중단(진행 기록)", "var(--muted)", "…")}


def render_run(run):
    meta, end, names = run["meta"], run["end"], run["names"]
    st, quotes, minds = char_stats(run)
    board = decision_board(run)
    fin = final_bots(run)
    tags_ = run["tags"]
    fallen_turn = {t["subject"]: t for t in tags_ if t["kind"] == "fallen"}
    oc_key = end.get("outcome") if end else None
    oc_name, oc_color, oc_ico = OC.get(oc_key, OC[None])
    end_turn = end.get("turn") if end else (run["ticks"][-1][1]["turn"] if run["ticks"] else 0)

    kills = sum(1 for t in tags_ if t["kind"] == "kill")
    loot = sum((t["detail"].get("loot") or 1) for t in tags_ if t["kind"] == "treasure")
    deaths = sum(1 for t in tags_ if t["kind"] == "fallen")
    fbrate = ("%.0f%%" % (100 * board["fallback"] / board["total"])) if board["total"] else "—"
    fb_note = ", ".join("%s %d" % (k, v) for k, v in board["fb_kinds"].most_common(3)) or "없음"

    h = []
    h.append('<h1>원더랜드 원정 보고서 <span style="color:var(--muted)">— %s</span></h1>' % ESC(run["name"]))
    h.append('<div class="sub">시드 %s · %s×%s · 지하 %s층 · %s · %s두뇌 판</div>' % (
        meta.get("seed"), meta.get("w"), meta.get("h"), meta.get("depths"),
        ESC(meta.get("started", "")), "리모컨 " if meta.get("menu") else "자유서술 "))
    h.append('<div class="banner"><span class="dot" style="background:%s"></span>%s %s — %s틱</div>'
             % (oc_color, oc_ico, ESC(oc_name), end_turn))

    h.append('<div class="tiles">')
    for v, l, d in [(kills, "처치", "⚔ 파티 합계"), (loot, "보물", "◆ 파티 합계"),
                    (deaths, "전사자", "☠"), (board["total"], "결정", "재결정 틱 수"),
                    (fbrate, "폴백률", ESC(fb_note)), (board["says"], "발언", "say 수")]:
        h.append('<div class="tile"><div class="v">%s</div><div class="l">%s</div><div class="d">%s</div></div>'
                 % (v, l, d))
    h.append('</div>')

    # 파티 카드
    h.append("<h2>파티</h2><div class='cards'>")
    for p in meta.get("party", []):
        c = p["char"]
        nm, job = ESC(names.get(c, c)), ESC(p.get("job", ""))
        fb_ = fin.get(c, {})
        hp, mx = fb_.get("hp", 0), fb_.get("maxhp", p.get("maxhp", 1)) or 1
        dead = c in fallen_turn
        pct = 0 if dead else max(0, min(100, round(100 * hp / mx)))
        hp_label = ("☠ 전사 (t%s, %s)" % (fallen_turn[c]["turn"], ESC(str(fallen_turn[c]["detail"].get("cause", "?"))))
                    if dead else "HP %s / %s" % (hp, mx))
        s = st.get(c, {})
        h.append("<div class='card'><h3>%s</h3><div class='job'>%s · %s</div>" % (nm, job, ESC(p.get("sex", ""))))
        h.append("<div class='hp%s'><i style='width:%d%%'></i></div><div class='hpl'>%s</div>"
                 % (" dead" if dead else "", pct, hp_label))
        h.append("<div class='stats'><span>⚔ 처치 <b>%d</b></span><span>◆ 보물 <b>%d</b></span>"
                 "<span>피해 <b>%d</b>/<b>%d</b> <span style='color:var(--muted)'>(준/받은)</span></span></div>"
                 % (s.get("kill", 0), s.get("treasure", 0), s.get("dealt", 0), s.get("taken", 0)))
        badges = [(T.KINDS[k][1], v) for k, v in sorted(s.items())
                  if k in T.KINDS and k not in ("kill", "treasure")]
        if badges:
            h.append("<div class='badges'>" + "".join(
                "<span class='badge'>%s%s</span>" % (ESC(b), (" <b>×%d</b>" % v) if v > 1 else "")
                for b, v in badges) + "</div>")
        qs = quotes.get(c, [])
        pick_q = qs[:2] + ([qs[-1]] if len(qs) > 2 else [])
        for tn, q in pick_q:
            h.append("<div class='quote'><span class='t'>t%d</span>「%s」</div>" % (tn, ESC(q)))
        ms = minds.get(c, [])
        if ms:
            tn, _, r = ms[0]
            h.append("<div class='quote mind'><span class='t'>t%d 속내</span>%s</div>" % (tn, ESC(r)))
        h.append("</div>")
    h.append("</div>")

    # 연대기 — 같은 원천 이벤트(line·ev)의 부속 태그는 대표 항목에 흡수(원장 부록은 전건 유지)
    kill_src = {(t["line"], t["ev"]) for t in tags_ if t["kind"] == "kill"}
    fallen_src = {(t["line"], t["ev"]) for t in tags_ if t["kind"] == "fallen"}
    fb_src = {(t["line"], t["ev"]) for t in tags_ if t["kind"] == "first_blood"}
    ABSORBED = {"first_blood": kill_src, "critical_hit": kill_src,
                "we_ambush": kill_src, "ambushed": fallen_src}
    h.append("<h2>연대기</h2><ul class='tl'>")
    for t in tags_:
        src = (t["line"], t["ev"])
        if t["kind"] in ABSORBED and src in ABSORBED[t["kind"]]:
            continue        # 처치/전사 항목이 이미 치명타·기습·선혈을 수치로 보여준다
        ev = None
        if t["ev"] is not None:
            o = run["by_line"].get(t["line"]) or {}
            evs = o.get("events") or []
            ev = evs[t["ev"]] if 0 <= t["ev"] < len(evs) else None
        ico, title, det = describe(t, ev, names)
        if t["kind"] == "kill" and src in fb_src:
            title += " (선혈)"
        cls = " class='grave'" if t["kind"] == "fallen" else ""
        h.append("<li%s><span class='ico'>%s</span><span class='turn'>t%s·%s층</span>"
                 "<span class='title'>%s</span> <span class='det'>%s</span>"
                 % (cls, ico, t["turn"], t["depth"], ESC(title), ESC(det)))
        q = quote_for(t, run)
        if q:
            r, s = q
            if r:
                h.append("<div class='q mind'>%s</div>" % ESC(r))
            if s:
                h.append("<div class='q'>「%s」</div>" % ESC(s))
        h.append("</li>")
    if not tags_:
        h.append("<li><span class='ico'>·</span><span class='det'>기록할 사건 없음 — 조용한 판</span></li>")
    h.append("</ul>")

    # 판단 계기판(검증① 미니지표)
    if board["hurt_next"]:
        dist = " · ".join("%s %d" % ({"attack": "반격", "goto": "이동", "explore": "탐색"}.get(k, k), v)
                          for k, v in board["hurt_next"].most_common())
        h.append("<h2>피격 후 판단 분포 (생존 판단 계측)</h2><div class='sub'>%s</div>" % ESC(dist))

    # 원장 부록
    h.append("<h2>태그 원장 (증거 원문 — %d건)</h2><div class='scroll'><table><thead>"
             "<tr><th>t</th><th>태그</th><th>축</th><th>대상</th><th>상세</th><th>원천</th></tr></thead><tbody>" % len(tags_))
    for t in tags_:
        h.append("<tr><td class='num'>%s</td><td>%s <span style='color:var(--muted)'>%s</span></td>"
                 "<td>%s</td><td>%s</td><td>%s</td><td class='num'>L%s%s</td></tr>"
                 % (t["turn"], ESC(T.KINDS[t["kind"]][1]), ESC(t["kind"]), t["axis"],
                    ESC(names.get(t["subject"], t["subject"])),
                    ESC(json.dumps(t["detail"], ensure_ascii=False)),
                    t["line"], ("·e%d" % t["ev"]) if t["ev"] is not None else ""))
    h.append("</tbody></table></div>")
    h.append("<div class='foot'>원더랜드 — 스트림(stream.jsonl)과 태그 원장에서 기계 생성(LLM 0콜). "
             "기울임 = 에이전트의 자기 보고(속내·발언)이며 엔진 진실이 아니다.</div>")
    return _page("원정 보고서 — %s" % run["name"], "\n".join(h))


def _page(title, body):
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body><div class='wrap'>%s</div></body></html>"
            % (ESC(title), CSS, body))


def render_index(runs):
    h = ["<h1>원더랜드 — 원정 기록 보관소</h1>",
         "<div class='sub'>%d개 원정 · 기계 생성 보고서</div>" % len(runs),
         "<div class='scroll'><table class='idx'><thead><tr><th>원정</th><th>결말</th>"
         "<th>틱</th><th>파티</th><th>⚔</th><th>◆</th><th>☠</th><th>태그</th></tr></thead><tbody>"]
    for run in runs:
        end = run["end"]
        oc_key = end.get("outcome") if end else None
        oc_name, oc_color, oc_ico = OC.get(oc_key, OC[None])
        end_turn = end.get("turn") if end else (run["ticks"][-1][1]["turn"] if run["ticks"] else 0)
        tg = run["tags"]
        kills = sum(1 for t in tg if t["kind"] == "kill")
        loot = sum((t["detail"].get("loot") or 1) for t in tg if t["kind"] == "treasure")
        deaths = sum(1 for t in tg if t["kind"] == "fallen")
        party = "·".join(run["names"].get(p["char"], p["char"]) for p in run["meta"].get("party", []))
        h.append("<tr><td><a href='%s.html'>%s</a></td>"
                 "<td class='oc' style='color:%s'>%s %s</td><td class='num'>%s</td><td>%s</td>"
                 "<td class='num'>%d</td><td class='num'>%d</td><td class='num'>%d</td><td class='num'>%d</td></tr>"
                 % (ESC(run["name"]), ESC(run["name"]), oc_color, oc_ico, ESC(oc_name),
                    end_turn, ESC(party), kills, loot, deaths, len(tg)))
    h.append("</tbody></table></div>")
    h.append("<div class='foot'>스트림·태그 원장 기반 기계 생성(LLM 0콜).</div>")
    return _page("원더랜드 원정 기록 보관소", "\n".join(h))


def main(argv):
    out = "reports"
    if "-o" in argv:
        i = argv.index("-o")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    paths = [a for a in argv if not a.startswith("-")]
    if not paths:
        print(__doc__)
        return 1
    os.makedirs(out, exist_ok=True)
    runs = []
    for p in paths:
        sp = os.path.join(p, "stream.jsonl")
        if not os.path.exists(sp):
            print("건너뜀(스트림 없음): %s" % p, file=sys.stderr)
            continue
        run = load_run(p)
        runs.append(run)
        op = os.path.join(out, run["name"] + ".html")
        with open(op, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_run(run))
        print("%-28s -> %s" % (run["name"], op))
    if runs:
        with open(os.path.join(out, "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render_index(runs))
        print("%-28s -> %s" % ("(색인)", os.path.join(out, "index.html")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
