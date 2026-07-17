#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
태그 발급기 — 스트림(stream.jsonl) 소비자. 엔진 무수정. (설계 D5, 2026-07-03)
─────────────────────────────────────────────
태그 = 얇은 프리미티브 (종류 kind, 대상 axis+subject, 원천 이벤트 참조 line+ev,
월드시간 turn(+depth), 수명 ttl). 원장 = append-only JSONL(한 판당 tags.jsonl).

원칙:
 · 발급 조건은 **스트림 어휘로 닫힌다** — say/reason 텍스트 해석 금지(그건 표시 재료).
 · 결정론: 같은 스트림 → 같은 원장(벽시계·난수 사용 금지). 리플레이 재현 가능.
 · 스냅샷 산수(거리·HP 추이)는 허용 — 관전자 등급 진실의 기계 계산이지 해석이 아니다.
 · v0 종류 선정은 데이터 기반: 후보를 넉넉히 발급하고 13판 소급(--census)으로 추린다.

사용:
  python3 tags.py <run_dir|stream.jsonl> ...      # 각 판 옆에 tags.jsonl 기록
  python3 tags.py --census <run_dir|...> ...      # 쓰지 않고 종류별 발화 빈도만 집계
  python3 tags.py --stdout <run_dir>              # 원장을 표준출력으로
"""
import os
import sys
import json

# ── 태그 종류 등록부: kind → (axis, 한글 이름, 한 줄 설명) ──
# 보고서(report.py)가 이 표로 이름을 푼다. 여기 없는 kind 는 발급되지 않는다.
KINDS = {
    # char 축 — 전투
    "first_blood":    ("char",  "선혈",       "이 원정의 첫 처치"),
    "kill":           ("char",  "처치",       "몬스터를 쓰러뜨림"),
    "critical_hit":   ("char",  "회심의 일격", "치명타 명중"),
    "we_ambush":      ("char",  "기습 성공",   "먼저 보고 먼저 쳤다"),
    "ambushed":       ("char",  "기습당함",    "몹의 기습·매복 일격에 맞음"),
    "fallen":         ("char",  "전사",       "쓰러짐(사인 기록)"),
    "hurt_decision":  ("char",  "피격 후 판단", "맞고 멈춘 뒤 무엇을 골랐나(D1 계측)"),
    # char 축 — 함정·발견·보물
    "trap_bitten":    ("char",  "함정에 물림",  "함정 판정 실패"),
    "trap_dodged":    ("char",  "함정 회피",   "함정 판정 성공"),
    "spotted_trap":   ("char",  "함정 간파",   "숨은 함정을 알아챔"),
    "spotted_lurker": ("char",  "매복 간파",   "숨은 몹을 알아챔"),
    "spotted_treasure": ("char", "숨은 보물 발견", "숨겨진 보물을 알아챔"),
    "treasure":       ("char",  "보물 획득",   "보물을 손에 넣음"),
    "potion":         ("char",  "물약 획득",   "회복 물약을 챙김"),
    "potion_drunk":   ("char",  "물약 복용",   "회복 물약으로 상처를 전부 아물림"),
    "chest_stung":    ("char",  "독침",       "상자의 함정에 당함"),
    "fountain_blessed": ("char", "샘의 축복",  "샘물이 몸을 치유함"),
    "fountain_cursed":  ("char", "샘의 저주",  "오염된 샘물에 당함"),
    # char 축 — 생존 서사
    "survivor":       ("char",  "생환",       "던전을 살아서 나옴"),
    "unscathed":      ("char",  "무결",       "생환 시 만전(HP 최대)"),
    "close_call":     ("char",  "구사일생",    "HP 2 이하까지 몰렸다가 생환"),
    "lone_wolf":      ("char",  "홀로 걷는 자", "동료들과 멀리 떨어져 오래 헤맴"),
    # pair 축
    "shoulder_to_shoulder": ("pair", "어깨를 나란히", "오래 붙어 다닌 두 사람"),
    # party 축
    "first_encounter": ("party", "첫 조우",    "이 종류의 몹을 처음 목격(도감 씨앗)"),
    "descended":      ("party", "강하",       "전원 모여 다음 층으로"),
    # run 축
    "outcome":        ("run",   "원정 결말",   "escaped/wiped/timeout"),
}

# 스냅샷 산수 문턱(결정론 상수 — 튜닝은 소급 데이터 보고)
LONE_DIST, LONE_TICKS = 8, 8        # 가장 가까운 동료와 체비셰프 거리 ≥8 이 8틱 연속
PAIR_DIST, PAIR_TICKS = 1, 6        # 인접(≤1) 6틱 연속
CLOSE_HP = 2


def _cheb(a, b):
    return max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]))


def read_stream(path):
    """유효 prefix 규칙: 쓰다 만 마지막 라인은 무시. (line_no(1기준), obj) 리스트."""
    out = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append((i, json.loads(line)))
            except json.JSONDecodeError:
                continue
    return out


def issue(lines):
    """스트림 라인 리스트 → 태그 리스트(발급 순서 = 결정론). 순수 함수."""
    tags = []
    depth = 1
    first_kill_done = False
    seen_kinds = set()          # first_encounter (파티 공유 지식 — 도감 씨앗)
    pending_hurt = {}           # char → {turn} : 피격 후 '그 피격 때문에 멈춘' 다음 결정을 기다림
    min_hp = {}                 # char → 살아있는 동안 최저 HP
    lone_streak = {}            # char → 연속 고립 틱 수
    lone_issued = set()
    pair_streak = {}            # "a+b" → 연속 인접 틱 수
    pair_issued = set()
    end_obj = None
    end_line = None

    def tag(kind, subject, turn, line, ev=None, **detail):
        axis = KINDS[kind][0]
        tags.append({"kind": kind, "axis": axis, "subject": subject,
                     "turn": turn, "depth": depth, "line": line,
                     "ev": ev, "ttl": None, "detail": detail or {}})

    def note_kind(name, turn, line, ev):
        if name and name not in seen_kinds:
            seen_kinds.add(name)
            tag("first_encounter", "party", turn, line, ev, monster=name)

    for line_no, o in lines:
        k = o.get("kind")

        if k == "level":
            depth = o.get("depth", depth)
            lone_streak.clear()     # 층이 바뀌면 스냅샷 연속성 리셋
            pair_streak.clear()
            pending_hurt.clear()    # 피격 문맥도 층-로컬(새 층 첫 결정은 피격과 무관 — 리뷰 확증)

        elif k == "descend":
            tag("descended", "party", o.get("turn", 0), line_no,
                to_depth=o.get("to_depth"),
                party=[p.get("char") for p in o.get("party", [])])

        elif k == "end":
            end_obj, end_line = o, line_no

        elif k == "tick":
            turn = o.get("turn", 0)

            # ① 피격 후 판단(D1 계측): 이전 틱 피격자의 이번 틱 결정을 짝짓는다
            for ch, d in sorted((o.get("decisions") or {}).items()):
                if ch in pending_hurt and not d.get("skipped"):
                    h = pending_hurt.pop(ch)
                    tag("hurt_decision", ch, turn, line_no,
                        hurt_turn=h["turn"], gap=turn - h["turn"],
                        next=d.get("type"), next_target=d.get("target"),
                        src=d.get("src"))

            # ② 이벤트 스캔
            for ei, e in enumerate(o.get("events") or []):
                t = e.get("type")
                ch = e.get("char")

                if t == "attack" and e.get("result") == "attack":
                    note_kind(e.get("target"), turn, line_no, ei)
                    if e.get("hit"):
                        if e.get("crit"):
                            tag("critical_hit", ch, turn, line_no, ei,
                                monster=e.get("target"), dmg=e.get("dmg"))
                        if e.get("surprise"):
                            tag("we_ambush", ch, turn, line_no, ei,
                                monster=e.get("target"))
                        if e.get("killed"):
                            if not first_kill_done:
                                first_kill_done = True
                                tag("first_blood", ch, turn, line_no, ei,
                                    monster=e.get("target"))
                            tag("kill", ch, turn, line_no, ei,
                                monster=e.get("target"), id=e.get("target_id"),
                                dmg=e.get("dmg"), crit=bool(e.get("crit")),
                                surprise=bool(e.get("surprise")))

                elif t == "monster_attack":
                    note_kind(e.get("monster"), turn, line_no, ei)
                    victim = e.get("target")
                    if e.get("hit"):
                        if e.get("surprise") or e.get("from_hiding"):
                            tag("ambushed", victim, turn, line_no, ei,
                                monster=e.get("monster"), dmg=e.get("dmg"),
                                down=bool(e.get("down")))
                        if e.get("down"):
                            tag("fallen", victim, turn, line_no, ei,
                                cause=e.get("monster"), by="monster_attack")
                            pending_hurt.pop(victim, None)
                        else:
                            pending_hurt[victim] = {"turn": turn}

                elif t in ("monster_notice", "monster_flee",
                           "monster_desperate", "monster_move"):
                    note_kind(e.get("monster"), turn, line_no, ei)

                elif t == "walk":
                    if ch in pending_hurt and "reason" not in e:
                        # 다음 틱에도 자동보행이 이어짐 = 그 피격은 봇을 멈추지 못했다
                        # (D1 이전 데이터·비인터럽트 피해) → hurt_decision 짝짓기에서 제외.
                        # 같은 틱 오탐 없음: 이벤트는 순서 보존이라 봇의 walk 가 피격 등록보다 앞이다.
                        pending_hurt.pop(ch)
                    for m in e.get("monsters") or []:      # encounter/blocked 조우
                        note_kind(m.get("kind"), turn, line_no, ei)
                    tr = e.get("trap")
                    if tr:
                        if tr.get("safe"):
                            tag("trap_dodged", ch, turn, line_no, ei,
                                name=tr.get("name"), total=tr.get("total"),
                                dc=tr.get("dc"))
                        else:
                            tag("trap_bitten", ch, turn, line_no, ei,
                                name=tr.get("name"), dmg=tr.get("dmg"),
                                total=tr.get("total"), dc=tr.get("dc"),
                                alarm=tr.get("alarm"))
                            if tr.get("down"):
                                tag("fallen", ch, turn, line_no, ei,
                                    cause=tr.get("name"), by="trap")
                    if e.get("result") == "treasure" or e.get("treasure"):
                        tag("treasure", ch, turn, line_no, ei, src="walk")
                    if e.get("result") == "potion" or e.get("potion"):
                        tag("potion", ch, turn, line_no, ei, src="walk")

                elif t == "drink":
                    if e.get("result") == "drink_heal":
                        tag("potion_drunk", ch, turn, line_no, ei,
                            heal=e.get("heal"), left=e.get("potions"))

                elif t == "interact":
                    r = e.get("result")
                    if r == "treasure":
                        tag("treasure", ch, turn, line_no, ei, src="interact")
                    elif r == "potion":
                        tag("potion", ch, turn, line_no, ei, src="interact")
                    elif r == "chest_loot":
                        tag("treasure", ch, turn, line_no, ei, src="chest",
                            loot=e.get("loot"), roll=e.get("total"))
                    elif r == "chest_trap":
                        tag("chest_stung", ch, turn, line_no, ei,
                            dmg=e.get("dmg"), down=bool(e.get("down")))
                        if e.get("down"):
                            tag("fallen", ch, turn, line_no, ei,
                                cause="상자 독침", by="chest")
                    elif r == "fountain_heal":
                        tag("fountain_blessed", ch, turn, line_no, ei,
                            heal=e.get("heal"))
                    elif r == "fountain_harm":
                        tag("fountain_cursed", ch, turn, line_no, ei,
                            dmg=e.get("dmg"), down=bool(e.get("down")))
                        if e.get("down"):
                            tag("fallen", ch, turn, line_no, ei,
                                cause="오염된 샘", by="fountain")

                # found[] 는 walk(수동 인지)·search(능동 수색) 공통
                for f in e.get("found") or []:
                    fk = f.get("kind")
                    kindmap = {"trap": "spotted_trap", "monster": "spotted_lurker",
                               "treasure": "spotted_treasure"}
                    if fk in kindmap:
                        tag(kindmap[fk], ch, turn, line_no, ei,
                            name=f.get("name"), via=t)
                    if fk == "monster":
                        note_kind(f.get("name"), turn, line_no, ei)

            # ③ 스냅샷 산수(고립·동행·최저 HP) — 살아있고 아직 층에 있는 봇만
            bots = [b for b in (o.get("bots") or [])
                    if b.get("alive") and not b.get("won")]
            for b in bots:
                c = b["char"]
                min_hp[c] = min(min_hp.get(c, b["hp"]), b["hp"])
            if len(bots) >= 2:
                for b in bots:
                    near = min(_cheb(b, x) for x in bots if x["char"] != b["char"])
                    c = b["char"]
                    if near >= LONE_DIST:
                        lone_streak[c] = lone_streak.get(c, 0) + 1
                        if lone_streak[c] == LONE_TICKS and c not in lone_issued:
                            lone_issued.add(c)
                            tag("lone_wolf", c, turn, line_no,
                                ticks=LONE_TICKS, dist=near)
                    else:
                        lone_streak[c] = 0
                for i in range(len(bots)):
                    for j in range(i + 1, len(bots)):
                        a, b = bots[i], bots[j]
                        key = "+".join(sorted((a["char"], b["char"])))
                        if _cheb(a, b) <= PAIR_DIST:
                            pair_streak[key] = pair_streak.get(key, 0) + 1
                            if pair_streak[key] == PAIR_TICKS and key not in pair_issued:
                                pair_issued.add(key)
                                tag("shoulder_to_shoulder", key, turn, line_no,
                                    ticks=PAIR_TICKS)
                        else:
                            pair_streak[key] = 0

    # ── 종료 후 판정분(생환·무결·구사일생·결말) — end 라인이 있어야 발급 ──
    if end_obj:
        turn = end_obj.get("turn", 0)
        final_hp = {b["char"]: (b.get("hp"), b.get("maxhp"))
                    for b in end_obj.get("bots") or []}
        for c in sorted(end_obj.get("survivors") or []):
            tag("survivor", c, turn, end_line)
            hp = final_hp.get(c)
            if hp and hp[0] == hp[1]:
                tag("unscathed", c, turn, end_line, hp=hp[0])
            if min_hp.get(c, 99) <= CLOSE_HP:
                tag("close_call", c, turn, end_line, min_hp=min_hp[c])
        tag("outcome", "run", turn, end_line,
            outcome=end_obj.get("outcome"), depth=end_obj.get("depth"),
            survivors=end_obj.get("survivors"), fallen=end_obj.get("fallen"),
            remaining=end_obj.get("remaining"))
    return tags


def _stream_path(p):
    return os.path.join(p, "stream.jsonl") if os.path.isdir(p) else p


def main(argv):
    census = "--census" in argv
    to_stdout = "--stdout" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 1
    total = {}
    for p in paths:
        sp = _stream_path(p)
        if not os.path.exists(sp):
            print("건너뜀(스트림 없음): %s" % p, file=sys.stderr)
            continue
        tags = issue(read_stream(sp))
        for t in tags:
            total[t["kind"]] = total.get(t["kind"], 0) + 1
        if census:
            print("%-28s %3d개 태그" % (os.path.dirname(sp) or sp, len(tags)))
            continue
        out_lines = "\n".join(json.dumps(t, ensure_ascii=False,
                                         separators=(",", ":")) for t in tags)
        if to_stdout:
            print(out_lines)
        else:
            op = os.path.join(os.path.dirname(sp), "tags.jsonl")
            with open(op, "w", encoding="utf-8") as f:
                if out_lines:
                    f.write(out_lines + "\n")
            print("%-28s %3d개 태그 -> %s" % (os.path.dirname(sp) or sp, len(tags), op))
    if census or len(paths) > 1:
        print("\n== 종류별 발화 빈도 (%d판) ==" % len(paths))
        for k, n in sorted(total.items(), key=lambda kv: -kv[1]):
            axis, name, desc = KINDS[k]
            print("%5d  %-22s %-8s %s — %s" % (n, k, axis, name, desc))
        dead = [k for k in KINDS if k not in total]
        if dead:
            print("  발화 0: " + ", ".join(dead))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
