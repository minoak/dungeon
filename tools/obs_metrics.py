# -*- coding: utf-8 -*-
"""관측 구성·언급률 지표 v0(c17, 2026-10-16) — 판단 프롬프트가 어떤 절로 얼마나 차 있고, 판단 이유에 어느 절의 내용이 끌려 나오는지 표로.
LLM 0콜, 판을 안 돌린다, 입력 파일을 고치지 않는다.

왜: 민옥(10-16) "텍스트가 너무 많으면 그 사이에 욕구 관련 내용이 무시될 수도 있다. 텍스트 중요도를 생각해 볼 문제." — 판단 전에 숫자부터.
지표 정의·한계·첫 숫자: .orch/drafts/obs_weight_v0.md.

쓰는 법:
    python tools/obs_metrics.py <stream.jsonl|prompts.jsonl> [더 …] [--by char] [--ticks N] [--src DIR] [--tpc X] [--json]
      stream.jsonl   관측 동봉 판(DUNGEON_STREAM_OBS=1 — run_meta.stream_obs). decisions[c].obs 를 brains._wire 로 다시 그려 관측 글을 얻고,
                     앞머리(맥락·시트·지침)는 claude_brain 과 같은 순서로 붙인다 — 시트는 run_meta.party 로 만든 추정(관계·차림 줄 없음).
                     관측 없는 판이면 구성 표를 못 낸다(작정 수 src=plan 은 원래 관측이 없다 — 빠진다).
      prompts.jsonl  완성 프롬프트 덤프({"key": [턴, char], "prompt": …} 한 줄씩 — tools/baseline.py 판 산출의 prompts.jsonl). LLM 에 간 글 그대로.
                     이유가 없으니 언급률은 안 낸다.
      --by char      캐릭터별 절 표를 더 낸다(모델별은 파일별 머리·끝의 판 비교 표 — 한 판 = 한 모델)
      --ticks N      앞 N틱만(turn ≤ N)
      --src DIR      관측을 다시 그릴 코드(그 판을 낸 코드의 사본). 기본은 이 리포 — 판의 코드와 지금 코드가 다르면 글이 어긋난다(머리의 game_version 확인)
      --tpc X        글자당 토큰 가정(기본 1.0 — 론처 가격표 기본값과 같다). 토큰은 전부 이 추정이다(토크나이저를 돌리지 않는다)
      --json         표 대신 지표 dict 를 JSON 으로

재는 것:
  ① 구성 — 글을 줄머리 '# '(갈래: 맥락·시트·모험가 지침·수첩·기억·판단 공간)와 '## '(절)로 나눈다. 절 이름은 ' (' · ' — ' 앞까지
     (괄호 속 틱·이름처럼 판단마다 바뀌는 말을 뗀다). 절마다 나온 비율·평균/최대 줄·글자·추정 토큰·전체 글자 중 몫·평균 시작 위치(글 앞에서 몇 %).
  ② 관심 줄 — 몸과 기분(brains.NEED_HEAD — p0.5.18 부터 몸 BODY_HEAD · 기분 MOOD_HEAD 두 줄) · 할 일(TODO_HEAD) · 반복 중(repeat_signal.LINES) · 휴대식:
     어느 절의 몇째 줄, 관측·전체 프롬프트 안 위치.
  ③ 언급률 — 판단 이유(reason, 모델 판단 src 만 — 폴백·작정 제외)가 그 절의 '단위'를 하나라도 품으면 그 절을 언급한 것으로 센다.
     단위 = ID(f3·m2·b1·i7·exit …, 영숫자 경계로 일치) + 한글 어절(2자 이상, 끝 조사 하나를 뗀 줄기 — 부분 문자열로 일치).
     거르는 한글 낱말: 앞머리(맥락·시트·지침 — 모델이 매번 읽는 고정 글)와 머리글(#·##)에도 있는 낱말(관측에서 왔다고 말할 수 없다),
     어디에나 붙는 서술어·부사(GENERIC). 관심 줄(몸과 기분·할 일·반복 중)의 낱말은 앞머리에 있어도 거르지 않는다(지침이 '몸과 기분'을 설명한다).
     ID 는 거르지 않는다(지침 예시의 d1·b2 와 겹쳐도 — 대상 지칭이지 틀 문장이 아니다).
     직전 판단 줄의 ' — 이유: "…"'·'그때 동료에게 한 말'(내 지난 이유·말)은 단위에서 뺀다(자기 메아리). 같은 단위가 여러 절에 있으면 모두에 센다(겹침) —
     '단독 언급'은 그 관측에서 그 절에만 있던 단위로 걸린 것만 센다. 어떤 단위로 걸렸는지 절마다 위 몇 개를 같이 낸다(사람이 판정한다).
  ④ 용량 — 스트림 크기, 관측 JSON 바이트(판단당 평균·스트림 중 몫).
⚠️ 세지 판정하지 않는다. 언급률은 하한에 가깝다(바꿔 말하기·활용형 '배고픔'↔'고파서'는 못 잡는다)이고 우연 일치도 섞인다 — obs_weight_v0.md §3.
"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))   # 리포 루트 모듈 import 용(--src 면 그 앞에 하나 더)
import collections
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBS_GROUPS = ("수첩", "기억", "판단 공간", "관측")          # _wire 가 그리는 갈래(그 앞은 앞머리 — 맥락·시트·지침)
TAIL = "오직 JSON 한 줄로만 답하라."                          # claude_brain 끝줄
SKIP_SRC = ("fallback", "plan", "error")                       # 언급률에서 빼는 판단 — 규칙 두뇌·작정 수·오류(모델의 이유가 아니다)
JOSA = sorted(("은 는 이 가 을 를 에 에서 에게 께 의 로 으로 와 과 도 만 까지 부터 한테 처럼 보다 하고 랑 이랑 이다 이라 라").split(),
              key=len, reverse=True)
ID_RE = re.compile(r"(?<![A-Za-z0-9])(?:[a-z]{1,2}\d+|exit)(?![A-Za-z0-9])")
HANGUL_RE = re.compile(r"[가-힣]{2,}")
ECHO_RE = re.compile(r' — 이유: "[^"\n]*"|그때 동료에게 한 말[^:\n]*: "[^"\n]*"')   # 직전 판단 줄에 실린 내 지난 이유·내가 한 말
GENERIC = frozenset(("않는다 않다 않았다 있다 없다 있는 없는 있고 없고 한다 하다 했다 하는 하고 해서 된다 되다 같다 좋다 아니다 "
                     "이다 그리고 그래서 지금 먼저 다시 이미 아직 더는 위해 전에").split())   # 어디에나 붙는 서술어·부사 — 관심 줄 낱말이어도 거른다
SELF = {("기억", "네가 기억해두기로 한 것"), ("기억", "최근 대화"), ("판단 공간", "(머리)"), ("·", "할 일")}   # 내가 쓴 글(수첩 한 줄·할 일·내 말)이
                                                               #   섞인 절 — 이유와 겹치면 관측을 읽어서인지 같은 손이 써서인지 못 가른다(표에 ✎)
B = {}                                                         # 다시 그릴 코드의 모듈(brains · repeat_signal) — _load 가 채운다


def _load(src):
    """관측을 다시 그릴 코드를 올린다. --src 면 그 사본을 sys.path 맨 앞에(같은 이름 모듈이 그쪽에서 올라온다)."""
    if src:
        sys.path.insert(0, os.path.abspath(src))
    B["brains"] = importlib.import_module("brains")
    B["RS"] = importlib.import_module("repeat_signal")
    B["root"] = os.path.dirname(os.path.abspath(B["brains"].__file__))
    br = B["brains"]
    rep = B["RS"].LINES["wait"].split(":")[0]                  # '반복 중'
    need = ((("몸과 기분", "- %s: " % br.NEED_HEAD),) if hasattr(br, "NEED_HEAD") else ()) + \
           ((("몸", "- %s: " % br.BODY_HEAD), ("기분", "- %s: " % br.MOOD_HEAD)) if hasattr(br, "BODY_HEAD") else ())   # p0.5.16 한 줄 · p0.5.18 두 줄(--src 의 옛 코드도 읽는다)
    B["special"] = need + (("할 일", "- %s: " % br.TODO_HEAD), ("반복 중", "- %s: " % rep), ("휴대식", "- 휴대식 "))


def _records(path):
    """유효 prefix — 돌고 있는 판의 잘린 마지막 줄에서 멈춘다(run_metrics 와 같은 규칙)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                return


# ── 글 나누기 ─────────────────────────────────────────────────────────────────────

def _title(line):
    """머리 줄 → 절 이름. 괄호·줄표 뒤(틱·이름처럼 바뀌는 말)를 뗀다. 예) '## 이 층에서 지금까지 (t12 진입, 30틱째 …)' → '이 층에서 지금까지'."""
    t = line.lstrip("#").strip()
    t = re.sub(r"^.+에 대해 남길 한 줄", "○에 대해 남길 한 줄", t)   # 사람 이름이 앞에 붙는 유일한 절(D36 살 초대)
    for sep in (" (", " — "):
        t = t.split(sep)[0]
    return t.strip()


def split(text):
    """글 → 블록 [{group, title, lines, c0, c1, l0}]. '# ' 는 갈래(그 머리 줄부터 첫 '## ' 앞까지가 '(머리)' 블록), '## ' 는 절.
    첫 '#' 앞은 '(맥락)', 끝줄(TAIL)은 '(끝줄)'. c0·c1 = 글자 위치(줄바꿈 포함), l0 = 줄 번호."""
    blocks, group, cur, pos = [], "(맥락)", None, 0
    for i, ln in enumerate(text.split("\n")):
        head = ln.startswith("# ") or ln.startswith("## ")
        if ln.startswith("# "):
            group = _title(ln)
        elif ln == TAIL:
            group, head = "(끝줄)", True
        if head or cur is None:
            cur = {"group": group, "title": _title(ln) if ln.startswith("## ") else "(머리)", "lines": [], "c0": pos, "l0": i}
            blocks.append(cur)
        cur["lines"].append(ln)
        pos += len(ln) + 1
        cur["c1"] = pos
    return blocks


def _units(text):
    """언급 단위 — ID 와 한글 어절 줄기(끝 조사 하나 뗌, 2자 이상). 내 지난 이유(ECHO_RE)는 뺀다."""
    text = ECHO_RE.sub("", text)
    u = set(ID_RE.findall(text))
    for w in HANGUL_RE.findall(text):
        for j in JOSA:
            if j == "로" and w.endswith("으로"):             # '쪽으로' → '쪽으' 찌꺼기 방지('으로'를 못 떼면 그대로 둔다)
                continue
            if len(w) - len(j) >= 2 and w.endswith(j):
                w = w[:-len(j)]
                break
        u.add(w)
    return u - GENERIC


def _hit(unit, reason):
    if unit.isascii():
        return re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(unit), reason) is not None
    return unit in reason


# ── 판단 하나 ─────────────────────────────────────────────────────────────────────

def measure_text(full, char, turn, reason=None, src=None, est=False, obs_bytes=None):
    """완성 프롬프트(또는 추정) 하나 → 판단 레코드. 관측 부분 = OBS_GROUPS 갈래."""
    blocks = split(full)
    obs_b = [b for b in blocks if b["group"] in OBS_GROUPS]
    o0 = obs_b[0]["c0"] if obs_b else len(full)
    o1 = obs_b[-1]["c1"] if obs_b else len(full)
    olen = max(1, o1 - o0)
    rec = {"char": str(char), "turn": turn, "src": src, "reason": reason, "est": est, "obs_bytes": obs_bytes,
           "total": len(full), "obs_len": o1 - o0, "obs_lines": sum(1 for b in obs_b for ln in b["lines"] if ln.strip()),
           "blocks": [], "special": [], "units": {}, "fixed_units": set()}
    for k, b in enumerate(blocks):
        key = (b["group"], b["title"])
        is_obs = b["group"] in OBS_GROUPS
        rec["blocks"].append({"key": key, "obs": is_obs, "chars": b["c1"] - b["c0"],
                              "lines": sum(1 for ln in b["lines"] if ln.strip()),
                              "pos_full": b["c0"] / max(1, len(full)), "pos_obs": (b["c0"] - o0) / olen if is_obs else None})
        if not is_obs:
            if b["group"] != "(끝줄)":
                rec["fixed_units"] |= _units("\n".join(b["lines"]))   # 앞머리(맥락·시트·지침)의 낱말 — 거르기 재료
            continue
        rec["fixed_units"] |= _units(b["lines"][0])                  # 머리 줄(# · ## — 괄호 속 말까지)의 낱말도 거르기 재료
        rec["units"].setdefault(key, set()).update(_units("\n".join(b["lines"][1:])))   # 첫 줄 = 머리 줄 — 단위에서 뺀다
        c = b["c0"]
        for i, ln in enumerate(b["lines"]):
            for name, pre in B["special"]:
                if ln.startswith(pre):
                    rec["special"].append({"name": name, "key": key, "line_in_block": i, "chars": len(ln),
                                           "line_obs": sum(1 for x in full[o0:c].split("\n") if x.strip()) + 1,
                                           "pos_obs": (c - o0) / olen, "pos_full": c / max(1, len(full))})
                    rec["units"].setdefault(("·", name), set()).update(_units(ln[len(pre):]))
            c += len(ln) + 1
    return rec


def _estimate_full(obs, char, meta, party):
    """스트림의 관측 → claude_brain 과 같은 꼴의 완성 프롬프트(추정). 관측 글은 _wire 그대로, 시트는 run_meta.party 로."""
    br = B["brains"]
    me = dict(party.get(char) or {"char": char})
    roster = list(party.values())
    for slot in ("weapon", "armor"):                   # 시트의 차림 줄 — 지금 든 것(관측 gear)으로. 관측에 칸이 없으면 줄도 없다
        if slot in (obs.get("gear") or {}):
            me[slot] = obs["gear"][slot]
    real = {c: (p.get("name") or p.get("job", "동료")) for c, p in party.items()}
    if obs.get("people") is not None:                  # D85 인물 기록 판 — 호칭은 보는 사람 기준(brains._names_for 와 같은 규칙)
        me["people"] = obs["people"]
        names = br.G.people_names(me)
        names[char] = me.get("name") or me.get("job", "나")
    else:
        names = real
    compose = meta.get("action_mode", "compose") == "compose"
    wire = br._wire(obs, names, compose=compose)
    solo = bool(meta.get("solo"))
    if compose:
        ins = br.COMPOSE_PROMPT_SOLO if solo else br.COMPOSE_PROMPT
        if obs.get("skills"):
            ins = ins.replace('매 판단에 제시되는 COMMON에서 행동 이름을 고른다.', '매 판단에 제시되는 COMMON 또는 SKILL에서 행동 이름을 고른다.')
    else:                                              # 메뉴형 — 선택지 목록은 빠진다(추정)
        ins = br.MENU_PROMPT_SOLO if solo else br.MENU_PROMPT
    full = br._sheet(me, roster) + "\n" + ins + "\n\n" + wire + "\n\n" + TAIL
    if meta.get("prompt_context", True):
        full = br.CONTEXT_LINE + "\n\n" + full
    return full


def read_stream(path, ticks=None):
    meta, party, out, size_obs, n_ticks = {}, {}, [], 0, 0
    fails = collections.Counter()
    for rec in _records(path):
        k = rec.get("kind")
        if k == "run_meta":
            meta = rec
            party = {str(p.get("char")): dict(p, char=str(p.get("char"))) for p in rec.get("party") or []}
        elif k == "tick":
            t = rec.get("turn") or 0
            if ticks and t > ticks:
                break
            n_ticks += 1
            for c, dec in (rec.get("decisions") or {}).items():
                if not isinstance(dec, dict) or not isinstance(dec.get("obs"), dict):
                    continue
                c = str(c)
                obs = dec["obs"]
                ob = len(json.dumps(obs, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                size_obs += ob
                try:
                    full = _estimate_full(obs, c, meta, party)
                except Exception as e:                 # 판의 코드와 다른 코드로 그려 칸이 어긋난 경우 — 조용히 버리지 않고 센다
                    fails[type(e).__name__] += 1
                    continue
                out.append(measure_text(full, c, t, dec.get("reason"), dec.get("src"), est=True, obs_bytes=ob))
    return {"meta": meta, "party": party, "recs": out, "fails": dict(fails), "ticks": n_ticks,
            "bytes": os.path.getsize(path), "obs_bytes": size_obs}


def read_prompts(path, ticks=None):
    out = []
    for r in _records(path):
        t, c = (r.get("key") or ["-", "-"])[:2]
        if c in ("-", None) or (ticks and isinstance(t, int) and t > ticks):
            continue                                   # 캐릭터 판단이 아닌 콜(NPC 대사·수첩 — 키 '-')은 뺀다
        out.append(measure_text(r.get("prompt") or "", c, t))
    return {"meta": {}, "party": {}, "recs": out, "fails": {}, "ticks": None, "bytes": os.path.getsize(path), "obs_bytes": None}


def read(path, ticks=None):
    with open(path, encoding="utf-8") as f:
        first = json.loads(f.readline() or "{}")
    return read_prompts(path, ticks) if "prompt" in first else read_stream(path, ticks)


# ── 모으기 ────────────────────────────────────────────────────────────────────────

def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def aggregate(recs, tpc, stop=None):
    """판단 레코드 묶음 → 절 표·관심 줄 표·언급률. stop = 거를 단위(없으면 이 묶음으로 만든다)."""
    n = len(recs)
    if stop is None:
        stop = stop_units(recs)
    S = collections.OrderedDict()
    tot_chars = sum(r["total"] for r in recs) or 1
    order = []                                         # 절의 실제 순서 — 판단마다 본 순서를 이어 붙인다(새 절은 그 판단에서 바로 앞 절 뒤에).
    for r in recs:                                     #   평균 위치로 줄 세우면 나오는 판단이 다른 절끼리 뒤집힌다(첫 판단에만 있는 '마을 안내'가 기억 앞으로)
        prev = None
        for b in r["blocks"]:
            if b["key"] not in order:
                order.insert(order.index(prev) + 1 if prev is not None else 0, b["key"])
            prev = b["key"]
    for r in recs:
        for b in r["blocks"]:
            s = S.setdefault(b["key"], {"obs": b["obs"], "n": 0, "chars": [], "lines": [], "pos_full": [], "pos_obs": [], "seen": set()})
            if id(r) not in s["seen"]:                  # 한 판단에 같은 절이 둘이면(드묾) 한 번 나온 것으로 — 글자·줄은 합친다
                s["seen"].add(id(r))
                s["n"] += 1
                s["chars"].append(0)
                s["lines"].append(0)
                s["pos_full"].append(b["pos_full"])
                if b["pos_obs"] is not None:
                    s["pos_obs"].append(b["pos_obs"])
            s["chars"][-1] += b["chars"]
            s["lines"][-1] += b["lines"]
    sections = []
    for key, s in S.items():
        sections.append({"group": key[0], "title": key[1], "obs": s["obs"], "present": s["n"], "present_share": s["n"] / n if n else None,
                         "lines_mean": _mean(s["lines"]), "lines_max": max(s["lines"]), "chars_mean": _mean(s["chars"]),
                         "chars_max": max(s["chars"]), "tok_mean": _mean(s["chars"]) * tpc, "share": sum(s["chars"]) / tot_chars,
                         "pos_full": _mean(s["pos_full"]), "pos_obs": _mean(s["pos_obs"])})
    sections.sort(key=lambda x: order.index((x["group"], x["title"])))
    obs_tot = sum(r["obs_len"] for r in recs) or 1
    for x in sections:
        x["share_obs"] = (x["chars_mean"] * x["present"] / obs_tot) if x["obs"] else None
    # 관심 줄
    SP = collections.OrderedDict()
    for r in recs:
        for sp in r["special"]:
            d = SP.setdefault(sp["name"], {"n": 0, "where": collections.Counter(), "line_obs": [], "pos_obs": [], "pos_full": [], "chars": [],
                                           "of_full": []})
            d["n"] += 1
            d["where"]["%s · %s" % sp["key"]] += 1
            d["line_obs"].append(sp["line_obs"])
            d["pos_obs"].append(sp["pos_obs"])
            d["pos_full"].append(sp["pos_full"])
            d["chars"].append(sp["chars"])
            d["of_full"].append(sp["chars"] / max(1, r["total"]))
    special = [{"name": k, "present": d["n"], "present_share": d["n"] / n if n else None, "where": dict(d["where"].most_common()),
                "line_obs_mean": _mean(d["line_obs"]), "line_obs_min": min(d["line_obs"]), "line_obs_max": max(d["line_obs"]),
                "pos_obs": _mean(d["pos_obs"]), "pos_full": _mean(d["pos_full"]),
                "chars_mean": _mean(d["chars"]), "of_full": _mean(d["of_full"])} for k, d in SP.items()]
    return {"n": n, "chars_mean": _mean([r["total"] for r in recs]), "chars_max": max((r["total"] for r in recs), default=0),
            "obs_chars_mean": _mean([r["obs_len"] for r in recs]), "obs_chars_max": max((r["obs_len"] for r in recs), default=0),
            "obs_lines_mean": _mean([r["obs_lines"] for r in recs]), "tok_mean": (_mean([r["total"] for r in recs]) or 0) * tpc,
            "obs_tok_mean": (_mean([r["obs_len"] for r in recs]) or 0) * tpc,
            "sections": sections, "special": special, "mention": mention(recs, stop)}


def stop_units(recs):
    """거를 한글 낱말 — 앞머리(맥락·시트·지침)·머리 줄에도 있는 낱말. 관심 줄('·' 키)의 낱말과 ID 는 거르지 않는다."""
    fixed, keep = set(), set()
    for r in recs:
        fixed |= r["fixed_units"]
        for key, u in r["units"].items():
            if key[0] == "·":
                keep |= u
    return {u for u in fixed - keep if not u.isascii()}


def mention(recs, stop):
    """절마다 — 그 절이 나온 모델 판단 중 이유가 그 절의 단위를 품은 비율(겹침 허용 · 단독)."""
    M = collections.OrderedDict()
    n_dec = 0
    for r in recs:
        if not r["reason"] or r["src"] in SKIP_SRC:
            continue
        n_dec += 1
        units = {k: (u - stop) for k, u in r["units"].items()}
        owner = collections.Counter(x for k, u in units.items() if k[0] != "·" for x in u)   # 단위가 몇 절에 있나(관심 줄은 제 절에도 있으니 빼고 센다)
        for k, u in units.items():
            d = M.setdefault(k, {"present": 0, "hit": 0, "solo": 0, "units": collections.Counter()})
            d["present"] += 1
            got = [x for x in u if _hit(x, r["reason"])]
            if got:
                d["hit"] += 1
                d["units"].update(got)
                if any(owner[x] <= 1 for x in got):
                    d["solo"] += 1
    rows = [{"group": k[0], "title": k[1], "present": d["present"], "hit": d["hit"], "solo": d["solo"],
             "rate": d["hit"] / d["present"] if d["present"] else None, "solo_rate": d["solo"] / d["present"] if d["present"] else None,
             "top_units": [u for u, _ in d["units"].most_common(6)]} for k, d in M.items()]
    return {"decisions": n_dec, "stop_n": len(stop), "rows": rows}


def measure(path, ticks=None, tpc=1.0, by_char=False):
    R = read(path, ticks)
    recs = R["recs"]
    meta = R["meta"]
    stop = stop_units(recs)
    out = {"file": path, "game_version": meta.get("game_version"), "git": meta.get("git"), "model": meta.get("model") or meta.get("backend"),
           "seed": meta.get("seed"), "stream_obs": meta.get("stream_obs"), "ticks": R["ticks"], "decisions_measured": len(recs),
           "render_fails": R["fails"], "est_prefix": bool(recs and recs[0]["est"]), "tpc": tpc,
           "src_code": B["root"], "bytes": R["bytes"], "obs_bytes": R["obs_bytes"],
           "obs_bytes_mean": (R["obs_bytes"] / len(recs)) if (R["obs_bytes"] and recs) else None,
           "all": aggregate(recs, tpc, stop)}
    names = {c: (p.get("name") or p.get("job") or c) for c, p in R["party"].items()}
    if by_char:
        out["chars"] = {c: dict(aggregate([r for r in recs if r["char"] == c], tpc, stop), name=names.get(c, c))
                        for c in sorted({r["char"] for r in recs}, key=lambda x: (len(x), x))}
    return out


# ── 표 ─────────────────────────────────────────────────────────────────────────────

def _p(x):
    return "-" if x is None else "%d%%" % round(100 * x)


def _f(x, k=0):
    return "-" if x is None else ("%%.%df" % k) % x


def _fname(path):
    """표 머리의 판 이름 — 폴더 하나까지(판마다 stream.jsonl 이라 파일 이름만으론 못 가른다)."""
    return "/".join(os.path.normpath(path).replace("\\", "/").split("/")[-2:])


def _self(key):
    return " ✎" if key in SELF else ""


def _sec_table(a, mention_on):
    L = ["| 갈래 · 절 (✎ 내가 쓴 글 섞임) | 나옴 | 평균 줄 | 평균 글자 (최대) | 추정 토큰 | 전체 중 몫 | 관측 중 몫 | 시작 위치(전체·관측) |%s" %
         (" 언급 · 단독 | 걸린 낱말 |" if mention_on else ""),
         "|---|---|---|---|---|---|---|---|%s" % ("---|---|" if mention_on else "")]
    mrow = {(m["group"], m["title"]): m for m in a["mention"]["rows"]}
    for s in a["sections"]:
        m = mrow.get((s["group"], s["title"]))
        L.append("| %s · %s%s | %s | %s | %s (%d) | %s | %s | %s | %s · %s |%s" % (
            s["group"], s["title"], _self((s["group"], s["title"])), _p(s["present_share"]), _f(s["lines_mean"], 1), _f(s["chars_mean"]), s["chars_max"],
            _f(s["tok_mean"]), _p(s["share"]), _p(s["share_obs"]), _p(s["pos_full"]), _p(s["pos_obs"]),
            (" %s · %s | %s |" % (_p(m["rate"]), _p(m["solo_rate"]), " ".join(m["top_units"][:4]) or "-") if m else " - | - |")
            if mention_on else ""))
    return L


def _special_table(a, mention_on):
    if not a["special"]:
        return ["- 관심 줄(몸과 기분·할 일·반복 중·휴대식) 없음"]
    mrow = {m["title"]: m for m in a["mention"]["rows"] if m["group"] == "·"}
    L = ["| 관심 줄 | 나옴 | 자리(절) | 평균 글자 (전체 중) | 관측 안 줄 번호 평균 (최소–최대) | 관측 안 위치 | 전체 프롬프트 안 위치 |%s" %
         (" 언급 · 단독 | 걸린 낱말 |" if mention_on else ""), "|---|---|---|---|---|---|---|%s" % ("---|---|" if mention_on else "")]
    for s in a["special"]:
        m = mrow.get(s["name"])
        L.append("| %s%s | %d (%s) | %s | %s (%.1f%%) | %s (%d–%d) | %s | %s |%s" % (
            s["name"], _self(("·", s["name"])), s["present"], _p(s["present_share"]), " · ".join("%s %d" % kv for kv in s["where"].items()),
            _f(s["chars_mean"]), 100 * (s["of_full"] or 0),
            _f(s["line_obs_mean"], 1), s["line_obs_min"], s["line_obs_max"], _p(s["pos_obs"]), _p(s["pos_full"]),
            (" %s · %s | %s |" % (_p(m["rate"]), _p(m["solo_rate"]), " ".join(m["top_units"][:4]) or "-") if m else " - | - |")
            if mention_on else ""))
    return L


def render(m):
    a = m["all"]
    mention_on = a["mention"]["decisions"] > 0
    L = ["## %s" % _fname(m["file"]), ""]
    L.append("%s(%s) · 시드 %s · %s · %s틱 · 잰 판단 %d%s · 다시 그린 코드 %s · 글자당 토큰 %.2f" % (
        m["game_version"] or "버전?", m["git"] or "-", m["seed"], m["model"], m["ticks"] if m["ticks"] is not None else "-",
        m["decisions_measured"], " · 그리기 실패 %s" % m["render_fails"] if m["render_fails"] else "", m["src_code"], m["tpc"]))
    L.append("")
    L.append("- 프롬프트 전체: 평균 %s자 (최대 %d) ≈ %s토큰%s · 관측(수첩·기억·판단 공간): 평균 %s자 (최대 %d) ≈ %s토큰 · %s줄 · 전체 중 %s" % (
        _f(a["chars_mean"]), a["chars_max"], _f(a["tok_mean"]), " (시트는 run_meta 추정)" if m["est_prefix"] else "",
        _f(a["obs_chars_mean"]), a["obs_chars_max"], _f(a["obs_tok_mean"]), _f(a["obs_lines_mean"], 1),
        _p((a["obs_chars_mean"] or 0) / a["chars_mean"]) if a["chars_mean"] else "-"))
    if m["obs_bytes"] is not None:
        L.append("- 용량: 스트림 %.2fMB · 관측 JSON %.2fMB (%s) · 판단당 관측 %s바이트" % (
            m["bytes"] / 1e6, m["obs_bytes"] / 1e6, _p(m["obs_bytes"] / m["bytes"]) if m["bytes"] else "-", _f(m["obs_bytes_mean"])))
    L.append("- 언급률: %s" % ("모델 판단 %d개 · 거른 낱말 %d개" % (a["mention"]["decisions"], a["mention"]["stop_n"]) if mention_on
                              else "모델 판단의 이유가 없다(폴백·작정만이거나 프롬프트 덤프) — 구성만 낸다"))
    L += ["", "### 절 (전체 프롬프트 앞에서부터)", ""] + _sec_table(a, mention_on)
    L += ["", "### 관심 줄", ""] + _special_table(a, mention_on)
    for c, v in (m.get("chars") or {}).items():
        L += ["", "### %s(%s) — 판단 %d · 관측 평균 %s자 · 전체 평균 %s자" % (v["name"], c, v["n"], _f(v["obs_chars_mean"]), _f(v["chars_mean"])), ""]
        L += _sec_table(v, v["mention"]["decisions"] > 0)
        L += [""] + _special_table(v, v["mention"]["decisions"] > 0)
    L.append("")
    return "\n".join(L)


def render_compare(ms):
    L = ["## 판 비교", "", "| 판 | 모델 | 판단 | 관측 평균 글자 | 전체 평균 글자 | 가장 큰 관측 절 3 | 몸과 기분 나옴 · 위치(전체) · 언급 |",
         "|---|---|---|---|---|---|---|"]
    for m in ms:
        a = m["all"]
        top = sorted((s for s in a["sections"] if s["obs"]), key=lambda s: -s["share"])[:3]
        need = next((s for s in a["special"] if s["name"] in ("몸과 기분", "몸")), None)   # p0.5.18 부터 '몸:' 줄(기분은 관심 줄 표에)
        nm = next((r for r in a["mention"]["rows"] if r["group"] == "·" and r["title"] == (need or {}).get("name")), None)
        L.append("| %s | %s | %d | %s | %s | %s | %s |" % (
            _fname(m["file"]), m["model"], a["n"], _f(a["obs_chars_mean"]), _f(a["chars_mean"]),
            " · ".join("%s %s" % (s["title"], _p(s["share"])) for s in top),
            ("%s · %s · %s" % (_p(need["present_share"]), _p(need["pos_full"]), _p(nm["rate"]) if nm else "-")) if need else "없음"))
    L.append("")
    return "\n".join(L)


def _jsonable(m):
    return json.loads(json.dumps(m, ensure_ascii=False, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))


def main(argv):
    opts = {"--ticks": None, "--src": None, "--tpc": "1.0"}
    for k in list(opts):
        if k in argv:
            i = argv.index(k)
            opts[k] = argv[i + 1]
            argv = argv[:i] + argv[i + 2:]
    flags = {a for a in argv if a in ("--json", "--by")}
    by_char = False
    if "--by" in argv:
        i = argv.index("--by")
        by_char = argv[i + 1] == "char"
        argv = argv[:i] + argv[i + 2:]
    argv = [a for a in argv if a not in flags]
    if not argv:
        print(__doc__)
        return 1
    _load(opts["--src"])
    ticks = int(opts["--ticks"]) if opts["--ticks"] else None
    ms = [measure(p, ticks, float(opts["--tpc"]), by_char) for p in argv]
    if "--json" in flags:
        print(json.dumps(_jsonable(ms if len(ms) > 1 else ms[0]), ensure_ascii=False, indent=1))
        return 0
    for m in ms:
        print(render(m))
    if len(ms) > 1:
        print(render_compare(ms))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main(sys.argv[1:]))
