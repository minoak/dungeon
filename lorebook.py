# -*- coding: utf-8 -*-
"""개인 로어북(p0.5.11 — 설계 .orch/drafts/personal_lorebook_design.md v3 · DECISIONS 2026-10-13 87·89 · 10-14 §7 결정 5개).

에이전트가 **직접 쓰는** 기록 사전이다. 세계(엔진)는 기록을 보관하고, 조건이 맞을 때 관측에 띄울 뿐 글을 읽지 않는다
("우리가 만드는 건 시스템이다" — 정리·해석은 각 에이전트 몫).

  쓰기   응답 칸 `lore_note` 하나 — {"target": "<보이는 ID>", "text"} = 그것 하나(개별) · {"kind": "<보이는 이름>", "text"} = 그 종류 전부.
         사람에게는 "name"(부를 이름)도. 칸 단위 병합: 준 칸만 바뀐다(옛 person_note 가 항목을 통째로 바꿔 이름·글을 지우던 구멍을 막는다).
  보관   장부 셋, 겉은 하나(설계 §5.2): 사람 = bot['people'](0.5.9 그대로 'b<char>'·'npc:<이름>') · 그 밖 = bot['lore'] ·
         몬스터 종류 = 도감 원장 note('monster:<이름>' — 발급기가 스트림을 접어 쓴다, 판을 넘는다).
         안쪽 열쇠(관측에 나가지 않는다): obj:<층 일련>:<번호>(방·몬스터·함정·피처·문·계단 — 그 층 인스턴스와 함께 사라진다) ·
         gear:<장비 고유 번호>(층을 넘고 남에게 건네져도 같은 장비) · place:<마을 공간 id> · zone:<마을 구역 이름> · quest:<의뢰 id> · kind:<보이는 이름>.
  띄우기 보임(제자리 줄 아래) · 말한 사람 · 이름 들림(글자 일치만) · 소지품 — 한 관측 6줄(가까운 것부터, 결정론). 잘린 것은 스트림에만.
  상한   글 80자 · 사람 이름 20자 · 한 몸 100개(넘치면 층 기록부터, 그다음 가장 오래전에 고쳐 쓴 것부터 바랜다).
  관전   run_meta.lore(시작 원장) · tick.lore_ops(set·fade·sweep·merge) · decisions.lore_note·lore_drop·lore_shown·lore_cut · level.scope · 피처 space·uid.
         p0.5.12 관전 클릭 보기의 접기 기준 = fold_stream(게임 화면 game/src/inspect/model.ts 와 같은 규칙 — verify_viewer_click 이 맞대 본다).

정보 보호: 띄우는 재료는 보는 사람 자신의 관측(obs.people · obs.lore)뿐이다 — 남의 장부를 읽는 길이 없다. 종류 열쇠는 **내가 본 이름**이라
같은 몹을 남은 '고블린'으로, 나는 '낯선 짐승'으로 보아도 서로의 지식이 새지 않는다.
LLM 0콜 · 판정 rng 무접촉 · 엔진 무의존(dungeon_gm 을 import 하지 않는다 — 엔진·두뇌·러너가 이 모듈을 쓴다).
"""
import re

import identity as ID

TEXT_LEN = 80             # 기록 한 줄 상한(= brains.NOTE_LEN)
NAME_LEN = 20             # 사람의 부를 이름 상한(= brains.PERSON_NAME_LEN)
SHOW_MAX = 6              # 한 관측에 떠오르는 기록 수(민옥 결정 4)
KEEP_MAX = 100            # 한 몸의 기록 수(사람 + 로어북 장부 — 도감 note 는 종 수가 닫혀 있어 세지 않는다)
UNKNOWN_BEAST = "낯선 짐승"   # dungeon_gm.UNKNOWN_BEAST 와 같은 글자(엔진 무의존이라 따로 둔다 — verify_lorebook 이 같은지 본다)
FAR = 99                  # 거리를 모르는 대상(문·의뢰)의 정렬 자리 — 거리가 있는 것 뒤, 화면 번호 순


def clip(s, n):
    """공백 정리 + 자르기 — 저장할 때와 그릴 때 같은 함수(어느 한쪽이 빠져도 넘치지 않게, 설계 §3.4)."""
    return " ".join(str(s or "").split())[:n]


def _nat(i):
    """화면 번호 순 — 'f3' < 'f10'(글자 → 숫자)."""
    m = re.match(r"([^\d]*)(\d*)(.*)", str(i))
    return (m.group(1), int(m.group(2)) if m.group(2) else -1, m.group(3))


# ── 관측에서 '지금 보이는 것' ─────────────────────────────────────────────────────────────

def anchors(obs):
    """이번 관측에 번호나 이름으로 나온 세계의 것 — 쓰기(받는 조건)·띄우기(자리)·고르기(순서)가 같은 목록을 본다.
    항목 {id, name, dist, person?(사람 열쇠), kind(종류 기록을 받는가), inv(소지품), quest?(의뢰 id)}.
    뺀 것: 길(w… — 관측마다 새 이름) · 나 자신 · 사회 사건 · 기억 속 장소(known — 지금 보이는 것이 아니다)."""
    s = obs.get("sights") or {}
    out, ids = [], set()

    def add(i, name, dist, **kw):
        if not i or i in ids:
            return
        ids.add(i)
        out.append({"id": i, "name": name, "dist": dist, "kind": True, "inv": False, **kw})

    z = obs.get("zone") or {}
    if z.get("id"):                                    # 서 있는 곳(방·통로·scan 구역) — 거리 0
        add(str(z["id"]), z.get("kind") or "방", 0, kind=False)
    if obs.get("town_zone"):                           # 마을 구역 — 번호가 없다(이름으로 적는다)
        add("zone", obs["town_zone"], 0, kind=False)
    ex = s.get("exit")
    if ex:
        add("exit", "워프게이트" if ex.get("gate") else "계단", ex.get("dist"))
    for m in s.get("monsters") or []:
        add(m.get("id"), m.get("kind"), m.get("dist"))
    for f in s.get("features") or []:
        if f.get("type") == "npc":
            add(f.get("id"), f.get("name"), f.get("dist"), person="npc:%s" % f.get("name"), kind=False)
        else:
            add(f.get("id"), f.get("name"), f.get("dist"))
    for b in s.get("bots") or []:
        add("b%s" % b.get("char"), None, b.get("dist"), person="b%s" % b.get("char"), kind=False)
    for dr in z.get("doors") or []:                    # scan 구역의 문 — 지금 보이는 것만(기억 속 문은 대상이 아니다)
        if dr.get("seen"):
            add(dr.get("id"), "문", dr.get("dist"))
    for n in obs.get("notices") or []:                 # 게시판 앞의 의뢰
        if n.get("kind") == "board":
            for q in n.get("quests") or []:
                if q.get("tid"):
                    add(q["tid"], q.get("title"), None, kind=False, quest=str(q.get("id")))
    for t in obs.get("targets") or []:                 # 조합형 대상 목록에만 번호가 있는 것(함정 t<n> · 문 d<n>)
        if t.get("kind") in ("trap", "door"):
            add(t.get("id"), t.get("name"), t.get("dist"))
    for it in obs.get("items") or []:                  # 소지품 — 물약(i1·i4)은 개체가 아니라 개수(종류로 받는다)
        add(it.get("id"), it.get("name"), None, inv=True, count=it.get("slot") in ("potion", "boon"))
    return out


def _dist(a):
    return a["dist"] if isinstance(a.get("dist"), int) else FAR


# ── 쓰기: 응답 칸 → 결정 칸 ───────────────────────────────────────────────────────────────

def _said(raw):
    if isinstance(raw, dict):
        return {k: clip(raw.get(k), TEXT_LEN) for k in ("target", "kind", "name", "text") if raw.get(k) not in (None, "")}
    return clip(raw, TEXT_LEN)


def _drop(raw, why):
    return {"said": _said(raw), "why": why}


def _person_names(obs, anc):
    """종류 이름으로 받지 않는 이름 — 사람(내가 적은 이름·'낯선 사람'·NPC 이름)과 의뢰 제목(설계 §2.2)."""
    out = {ID.STRANGER}
    out |= {str(e.get("name")) for e in (obs.get("people") or {}).values() if isinstance(e, dict) and e.get("name")}
    out |= {a["person"][4:] for a in anc if str(a.get("person") or "").startswith("npc:")}
    out |= {str(m.get("from"))[4:] for m in obs.get("messages") or [] if str(m.get("from") or "").startswith("npc:")}
    out |= {str(a["name"]) for a in anc if a.get("quest") and a.get("name")}
    return out


def parse(raw, obs, char):
    """응답의 `lore_note` → (결정 칸 | None, 버림 로그 | None). 인물 기록 판(obs.people 이 있다)에서만 부른다.
    결정 칸 = {key, of, at, label, name?, text, target_said?} — key 는 사람·종류·마을 구역·의뢰면 여기서 정하고, 층 번호·장비 고유 번호·
    건물 공간이 필요한 개별은 None(러너 쓰기 apply 가 세계로 채운다 — 같은 틱의 판단 직후라 세계가 관측 그대로다).
    버림 사유(설계 §3.2): self · no_target · person_kind · no_kind · both(target 을 따르고 kind 는 버림) · empty."""
    if raw in (None, "", {}, []):
        return None, None
    if not isinstance(raw, dict):
        return None, _drop(raw, "no_target")
    text = clip(raw.get("text"), TEXT_LEN)
    name = clip(str(raw.get("name") or "").replace('"', ""), NAME_LEN)
    tg, kd = clip(raw.get("target"), 40), clip(raw.get("kind"), 40)
    if not text and not name:
        return None, _drop(raw, "empty")
    anc = anchors(obs)
    if tg:
        note, why = _one(tg, obs, str(char), anc, name, text)
        if note is None:
            return None, _drop(raw, why)
        return note, (_drop(raw, "both") if kd else None)
    if kd:
        note, why = _kind(kd, obs, anc, text)
        return (note, None) if note else (None, _drop(raw, why))
    return None, _drop(raw, "no_target")


def _person(key, at, tg, name, text, label):
    out = {"key": key, "of": "one", "at": at, "label": label}
    if name:
        out["name"] = name
    out["text"] = text
    if tg != at:
        out["target_said"] = tg
    return out


def _one(tg, obs, char, anc, name, text):
    byid = {a["id"]: a for a in anc}
    people = obs.get("people") or {}
    s = (obs.get("sights") or {})
    mb = re.fullmatch(r"(?:봇|b|bot)?\s*(\d+)", tg, flags=re.I)
    if tg.lower() == "self" or tg == obs.get("actor") or (mb and mb.group(1) == char):
        return None, "self"
    if mb:                                             # 모험가 — 지금 보이거나 이번 관측의 들은 말을 한 사람
        c = mb.group(1)
        key = "b" + c
        vis = key in byid
        spoke = any(str(m.get("from")) == c for m in obs.get("messages") or [])
        if not (vis or spoke):
            return None, "no_target"
        label = ID.call({"people": people, "char": char}, key)
        return _person(key, key if vis else None, tg, name, text, label), None
    npc = next((f for f in s.get("features") or [] if f.get("type") == "npc" and tg in (f.get("id"), f.get("name"))), None)
    if npc is not None:                                # 보이는 NPC(번호 또는 이름)
        return _person("npc:%s" % npc["name"], npc["id"], tg, name, text, npc["name"]), None
    if any(str(m.get("from")) == "npc:%s" % tg for m in obs.get("messages") or []):   # 방금 내게 말한 NPC(안 보여도)
        return _person("npc:%s" % tg, None, tg, name, text, tg), None
    a = byid.get(tg) or byid.get(tg.lower())
    if a is None and obs.get("town_zone") and tg == obs["town_zone"]:
        a = byid.get("zone")
    if a is None or a.get("person"):
        return None, "no_target"
    if not text:                                       # 사람이 아니면 name 은 버린다 — 글이 없으면 빈 기록
        return None, "empty"
    out = {"key": None, "of": "one", "at": a["id"], "label": a.get("name"), "text": text}
    if a.get("count"):                                 # 물약 칸(i1·i4) = 개수 — 종류 기록으로 받는다(설계 §2.1)
        out.update(key="kind:%s" % a["name"], of="kind")
    elif a["id"] == "zone":
        out["key"] = "zone:%s" % a["name"]
    elif a.get("quest"):
        out["key"] = "quest:%s" % a["quest"]
    if tg != a["id"]:
        out["target_said"] = tg
    return out, None


def _kind(kd, obs, anc, text):
    if kd in _person_names(obs, anc):
        return None, "person_kind"
    hit = sorted((a for a in anc if a.get("kind") and a.get("name") == kd), key=lambda a: (a.get("inv"), _dist(a), _nat(a["id"])))
    if not hit:
        return None, "no_kind"
    if not text:
        return None, "empty"
    mon = kd != UNKNOWN_BEAST and any(m.get("kind") == kd for m in (obs.get("sights") or {}).get("monsters") or [])
    return {"key": ("monster:%s" if mon else "kind:%s") % kd, "of": "kind", "at": hit[0]["id"], "label": kd, "text": text}, None


# ── 쓰기: 러너 쪽(세계로 안쪽 열쇠를 채우고 장부에 병합) ─────────────────────────────────────

def ids_of(d):
    """판의 발급 상태 {scope: 다음 층 일련, uid: 다음 장비 번호} — 러너가 모든 층에 같은 dict 를 건다(없으면 이 층에 하나 — 검증 하네스)."""
    ids = getattr(d, "lore_ids", None)
    if ids is None:
        ids = d.lore_ids = {"scope": 1, "uid": 1}
    return ids


def stamp(d, ids):
    """층 인스턴스(마을 포함)에 일련을 붙인다 — 지을 때 한 번(이미 있으면 그대로). 깊이만으로는 새 원정의 같은 깊이 층과 구별이 안 된다."""
    d.lore_ids = ids
    if getattr(d, "scope", None) is None:
        d.scope = ids["scope"]
        ids["scope"] += 1
    return d.scope


def gear_uid(d, g):
    """장비 고유 번호 — 처음 누군가 그 장비를 기록할 때 붙인다(g = 몸의 장비 칸 dict 또는 바닥 피처). 붙은 뒤엔 착용 이력처럼 따라간다."""
    u = g.get("uid") if isinstance(g, dict) else getattr(g, "uid", None)
    if not u:
        ids = ids_of(d)
        u = ids["uid"]
        ids["uid"] += 1
        if isinstance(g, dict):
            g["uid"] = u
        else:
            g.uid = u
    return u


def inner_key(d, bot, at):
    """화면 번호 → 안쪽 열쇠(장비·건물·그 밖 층의 것)."""
    if at in ("i2", "i3"):
        g = bot.get("weapon" if at == "i2" else "armor")
        if g:
            return "gear:%d" % gear_uid(d, g)
    if at[:1] == "f" and at[1:].isdigit():
        f = d.features.get(int(at[1:]))
        if f is not None and f.type in ("weapon", "armor"):
            return "gear:%d" % gear_uid(d, f)
        sid = (getattr(d, "building_ids", None) or {}).get(int(at[1:]))
        if sid:
            return "place:%s" % sid
    return "obj:%s:%s" % (getattr(d, "scope", None) or 0, at)


def _entry_copy(e):
    return {k: e[k] for k in ("name", "text", "turn", "depth", "src", "label") if k in e}


def apply(d, bot, note, turn):
    """받은 쓰기 하나를 그 몸의 장부에 — 칸 단위 병합(준 칸만 바꾼다, 빈 칸은 '안 바꿈'). → tick.lore_ops 꼴의 변화 목록.
    note 의 key 를 채워 넣는다(결정 칸 = 스트림에도 안쪽 열쇠가 남는다). 몬스터 종류는 도감 원장 note 로 — 발급기가 같은 결정을 접어 쓴다
    (그 종이 내 도감에 아직 없는 어긋난 상태면 로어북의 kind:<이름> 에 둔다 — 뒤에 도감 쪽에 쓰이면 러너가 merge 로 지운다)."""
    if not note or bot.get("people") is None:
        return []
    key = note.get("key") or inner_key(d, bot, note["at"])
    if key.startswith("monster:"):
        if key in (bot.get("book") or {}):
            note["key"] = key
            return [{"op": "set", "key": key, "entry": {"text": note.get("text", ""), "turn": turn, "depth": d.depth, "src": "self"}}]
        key = "kind:" + key[len("monster:"):]
    note["key"] = key
    person = ID.is_person_key(key)
    book = bot["people"] if person else bot.setdefault("lore", {})
    e = book.get(key)
    if not isinstance(e, dict):
        e = book[key] = {}
    if person and note.get("name"):
        e["name"] = note["name"]
    if note.get("text"):
        e["text"] = note["text"]
    if not person and note.get("label"):
        e["label"] = note["label"]                     # 쓸 때 본 이름(이름 들림 대조·관전 표시)
    e.update(turn=turn, depth=d.depth, src="self")     # 세계 칸만 갱신 — 다른 칸은 건드리지 않는다(dict 교체 금지)
    return [{"op": "set", "key": key, "entry": _entry_copy(e)}] + fade(bot)


def fade(bot):
    """한 몸 100개 상한 — 넘친 만큼 바랜다: 층 기록(obj:)부터, 같은 층위 안에서는 가장 오래전에 고쳐 쓴 것부터, 같으면 열쇠 순."""
    books = [b for b in (bot.get("people"), bot.get("lore")) if b]
    n = sum(len(b) for b in books)
    if n <= KEEP_MAX:
        return []
    rows = sorted((0 if k.startswith("obj:") else 1, int((e or {}).get("turn") or 0), k, i)
                  for i, b in enumerate(books) for k, e in b.items())
    ops = []
    for _, _, k, i in rows[:n - KEEP_MAX]:
        del books[i][k]
        ops.append({"op": "fade", "key": k})
    return ops


def sweep(bot, live):
    """사라진 층 인스턴스의 기록(obj:<일련>:)을 지운다 — live = 아직 있는 층 일련 집합. 사람·장소·의뢰·종류·장비 기록은 남는다."""
    lore = bot.get("lore") or {}
    gone = [k for k in sorted(lore) if k.startswith("obj:") and k.split(":")[1] not in live]
    for k in gone:
        del lore[k]
    return [{"op": "sweep", "key": k} for k in gone]


def town_building_ids(d):
    """마을 층의 건물 문턱 피처 → 공간 id — 러너 build_town 이 지을 때 다는 짝과 같다(layout 의 문턱 칸 = 그 건물 피처의 자리).
    저장 판 4 → 5 이관이 옛 마을(building_ids 가 없다)에 다시 단다 — 없으면 이어간 판의 건물 기록이 place: 가 아니라 층 기록(obj:)이 된다."""
    res = getattr(d, "layout_result", None) or {}
    cells = {(int(e["cell"][0]), int(e["cell"][1])): e.get("building") for e in res.get("entrances") or [] if e.get("building")}
    return {f.id: cells[(f.x, f.y)] for f in (getattr(d, "features", None) or {}).values()
            if f.type == "building" and (f.x, f.y) in cells}


def merge(bot, key):
    """도감 쪽(원장 note)에 같은 종 기록이 생겼다(key = 'monster:<이름>') — 로어북에 둔 같은 이름 기록(도감 편입 전 어긋남, 설계 §2.3)을 합류해 지운다."""
    k = "kind:" + str(key)[len("monster:"):]
    if str(key).startswith("monster:") and (bot.get("lore") or {}).pop(k, None) is not None:
        return [{"op": "merge", "key": k, "into": key}]
    return []


def restore_ids(got, dungeons, bodies):
    """이어가기의 발급 상태 — 저장된 lore_ids 와 '실제로 쓰인 가장 큰 번호 + 1' 중 큰 쪽(망가진 상태 방어, 설계 §6.2)."""
    sc, ud = used_ids(dungeons, bodies)
    got = got or {}
    return {"scope": max(int(got.get("scope") or 1), sc + 1), "uid": max(int(got.get("uid") or 1), ud + 1)}


def seed(sheets, c):
    """시트의 관계 문장 → 인물 기록 씨앗(이 캐릭터가 이미 아는 사람) — 저장할 때 자른다(이름 20 · 글 80)."""
    return {"b%s" % oc: {"name": clip(sheets[oc].get("name") or sheets[oc].get("job") or "모험가", NAME_LEN),
                         "text": clip(txt, TEXT_LEN), "turn": 0, "src": "sheet"}
            for oc, txt in sorted((sheets[c].get("relationships") or {}).items()) if oc in sheets and oc != c}


def dump(bot):
    """관전용 원장 전부(run_meta.lore · resume.lore) — 사람 + 로어북 장부, 안쪽 열쇠 그대로. 도감 note 는 run_meta.bestiary_progress 가 맡는다."""
    both = {**(bot.get("people") or {}), **(bot.get("lore") or {})}
    return {k: _entry_copy(e) for k, e in sorted(both.items()) if isinstance(e, dict)}


def ledger_key(p):
    """run_meta.party 항목 → 도감 원장 열쇠(id → 이름 → '봇N' — 발급기의 오프라인 유도·러너와 같은 규칙)."""
    return p.get("id") or p.get("name") or "봇%s" % p.get("char")


def fold_stream(rows):
    """관전 접기의 파이썬 기준(p0.5.12 관전 클릭 보기 — verify_viewer_click 이 엔진 장부와 TS 모형 game/src/inspect/model.ts 에 맞대 본다).
    rows = 본 스트림 줄(dict) 차례 → 프레임(level·tick 줄 — 관전 StreamParser 와 같은 단위)마다 {kind, turn, lore: {char: {열쇠: 항목}}, known: {char: set}}.
    장부 = 사람·로어북(run_meta.lore 에서 시작, resume.lore 가 통째로 갈아 끼운다 — 도감 note 는 그대로) + 도감 note(monster: — 시작 진행도의 note ·
    decisions.book_line · lore_ops set). 한 프레임 안의 순서: 앞의 resume → book_line → lore_ops(fade·sweep·merge = 지움) — end·stopped 줄의 lore_ops 는 마지막 프레임에.
    엔진(발급기 _settle)이 접지 않는 결정 — 미실행(skipped)·작정 — 의 도감 note 는 lore_ops 에 실려도 접지 않는다. 종 앎 = run_meta.bestiary + known_ops."""
    lore, known, frames, resume = {}, {}, [], None

    def ops(m):
        for c, os_ in (m or {}).items():
            book = lore.setdefault(c, {})
            for o in os_:
                if o.get("op") == "set":
                    book[o["key"]] = dict(o.get("entry") or {})
                else:
                    book.pop(o.get("key"), None)

    def snap(kind, turn):
        frames.append({"kind": kind, "turn": turn, "lore": {c: {k: dict(e) for k, e in b.items()} for c, b in lore.items()},
                       "known": {c: set(s) for c, s in known.items()}})
    for r in rows:
        k = r.get("kind")
        if k == "run_meta":
            for p in r.get("party") or []:
                c, lk = p["char"], ledger_key(p)
                lore[c] = {key: dict(e) for key, e in ((r.get("lore") or {}).get(c) or {}).items()}
                for key, e in ((r.get("bestiary_progress") or {}).get(lk) or {}).items():
                    if key.startswith("monster:") and (e.get("note") or {}).get("text"):
                        lore[c][key] = {"text": e["note"]["text"], "turn": 0, "src": "book"}
                known[c] = set((r.get("bestiary") or {}).get(lk) or [])
        elif k == "resume":
            resume = r
        elif k in ("level", "tick"):
            if resume is not None:
                for c, b in (resume.get("lore") or {}).items():
                    keep = {key: e for key, e in lore.get(c, {}).items() if key.startswith("monster:")}
                    lore[c] = {**{key: dict(e) for key, e in b.items()}, **keep}
                resume = None
            if k == "tick":
                decs = r.get("decisions") or {}
                for c, dd in sorted(decs.items()):
                    bl = dd.get("book_line")
                    if isinstance(bl, dict) and str(bl.get("text") or "").strip() and not dd.get("skipped") and dd.get("src") != "plan":
                        lore.setdefault(c, {})[bl["key"]] = {"text": str(bl["text"]).strip()[:TEXT_LEN], "turn": r["turn"], "src": "self"}
                for c, os_ in (r.get("lore_ops") or {}).items():
                    dd = decs.get(c) or {}
                    skip = (dd.get("skipped") or dd.get("src") == "plan") and (dd.get("lore_note") or {}).get("key")
                    ops({c: [o for o in os_ if not (o.get("op") == "set" and str(o.get("key")).startswith("monster:") and o.get("key") == skip)]})
                for c, ks in (r.get("known_ops") or {}).items():
                    known.setdefault(c, set()).update(ks)
            snap(k, r.get("turn"))
        elif k in ("end", "stopped") and r.get("lore_ops") and frames:
            ops(r["lore_ops"])
            frames[-1]["lore"] = {c: {key: dict(e) for key, e in b.items()} for c, b in lore.items()}
    return frames


def used_ids(dungeons, bodies):
    """스냅샷 안에서 실제로 쓰인 가장 큰 층 일련·장비 번호(이어가기 방어 — lore_ids 가 망가져도 겹치지 않게)."""
    sc, ud = 0, 0
    for d in dungeons:
        sc = max(sc, int(getattr(d, "scope", None) or 0))
        for f in (getattr(d, "features", None) or {}).values():
            ud = max(ud, int(getattr(f, "uid", None) or 0))
    for b in bodies:
        for slot in ("weapon", "armor"):
            ud = max(ud, int((b.get(slot) or {}).get("uid") or 0))
        for k in (b.get("lore") or {}):
            p = k.split(":")
            if p[0] == "obj" and p[1].isdigit():
                sc = max(sc, int(p[1]))
            elif p[0] == "gear" and p[1].isdigit():
                ud = max(ud, int(p[1]))
    return sc, ud


# ── 띄우기: 엔진(안쪽 열쇠 → 지금 화면 번호) ───────────────────────────────────────────────

def observe(d, bot, obs):
    """관측의 obs['lore'] 목록과 그 안쪽 열쇠(같은 순서 — 몸에만 두고 관측에는 안 싣는다) → (rows, refs).
    rows 항목 {of: one|kind, at: 지금 화면 번호|None, name: 쓸 때 본 이름, text}. 층 개별·장비는 지금 보이는 것만 싣는다(안 보이면 뜰 길이 없다).
    오래 남는 개별(건물·구역·의뢰)은 안 보여도 싣는다(at None — 이름 들림 대조용). 몬스터 종류는 도감 원장 note(있으면 그것, 없으면 로어북의 같은 이름)."""
    anc = {a["id"]: a for a in anchors(obs)}
    scope = str(getattr(d, "scope", None) or 0)
    rows = {}
    book = bot.get("book") or {}
    notes = {k: r["note"]["text"] for k, r in book.items()
             if k.startswith("monster:") and isinstance(r, dict) and isinstance(r.get("note"), dict) and r["note"].get("text")}
    for k, t in notes.items():
        rows[k] = {"of": "kind", "at": None, "name": k[len("monster:"):], "text": t}
    bids = getattr(d, "building_ids", None) or {}
    for key, e in (bot.get("lore") or {}).items():
        if not isinstance(e, dict) or not e.get("text"):
            continue
        kind, _, rest = key.partition(":")
        at, of = None, "one"
        if kind == "obj":
            sc, _, i = rest.partition(":")
            if sc != scope or i not in anc:
                continue
            at = i
        elif kind == "gear":
            u = int(rest) if rest.isdigit() else -1
            at = next((i for i, slot in (("i2", "weapon"), ("i3", "armor"))
                       if i in anc and (bot.get(slot) or {}).get("uid") == u), None)
            if at is None:
                at = next((i for i in ("f%d" % f.id for f in d.features.values() if getattr(f, "uid", None) == u) if i in anc), None)
            if at is None:
                continue
        elif kind == "place":
            fs = sorted((a for a in anc.values() if a["id"][1:].isdigit() and a["id"][:1] == "f" and bids.get(int(a["id"][1:])) == rest),
                        key=lambda a: (_dist(a), _nat(a["id"])))
            at = fs[0]["id"] if fs else None
        elif kind == "zone":
            at = "zone" if obs.get("town_zone") == rest else None
        elif kind == "quest":
            at = next((a["id"] for a in anc.values() if a.get("quest") == rest), None)
        elif kind == "kind":
            if "monster:" + rest in notes:             # 도감 note 가 있으면 그것(합류 전의 같은 이름 기록은 안 띄운다)
                continue
            of = "kind"
        else:
            continue
        rows[key] = {"of": of, "at": at, "name": e.get("label") or rest, "text": e["text"]}
    refs = sorted(rows)                                # 안쪽 열쇠 순(고르는 순서의 마지막 동률 규칙이 이 순서를 쓴다)
    return [rows[k] for k in refs], refs


# ── 띄우기: 고르기(한 관측 6줄)와 그리기 재료 ───────────────────────────────────────────────

def _has(e):
    return isinstance(e, dict) and bool(e.get("name") or e.get("text"))


def _key_rank(person_key):
    """이름 들림 동률의 마지막 규칙 '안쪽 열쇠 순'(설계 §4.3)을 관측만으로 — 관측에는 사람 밖 기록의 열쇠가 없다.
    이름 들림 후보의 열쇠 머리는 b<번호> < kind:·monster:(관측의 종류 기록) < npc:<이름> < place:·quest:·zone:(안 보이는 오래 남는 개별) 순이고,
    obs.lore 는 엔진이 안쪽 열쇠 순으로 실으므로 무리 번호(0 b · 1 종류 · 2 npc · 3 오래 남는 개별) + 무리 안의 순서가 곧 열쇠 순이다.
    ⚠️ 열쇠 머리를 새로 만들면 이 무리 번호도 함께 본다(verify_lorebook ⑩ 이 실제 열쇠 정렬과 맞대 본다)."""
    return 0 if str(person_key).startswith("b") else 2


def pick(obs, cap=SHOW_MAX):
    """이번 관측에 뜰 기록 → (고른 것, 잘린 것). 항목 = (ref, 자리) — ref ('p', 사람 열쇠) | ('l', obs.lore 의 자리), 자리 = 그 줄 아래에 그릴 화면 번호
    (None = '떠오른 기록' 절). 순서(결정론, 설계 §4.3): ① 보이는 대상 — 거리 가까운 순·화면 번호 순, 한 대상 안에서는 개별 → 종류(종류는 그 이름의
    가장 가까운 대상 아래 한 번) ② 들은 말 — 메시지 순, 한 말 안에서는 말한 사람 → 말 속 이름(처음 나온 자리 · 긴 이름 먼저 · 열쇠 순)
    ③ 소지품 — 소지 칸 순. 이미 고른 기록은 다시 세지 않는다. 종류별 우선순위는 두지 않는다(무엇이 중요한지는 해석 — 에이전트 몫)."""
    people = obs.get("people")
    if people is None:
        return [], []
    lore = obs.get("lore") or []
    anc = anchors(obs)
    out, seen, kinds = [], set(), set()

    def add(ref, at):
        if ref not in seen:
            seen.add(ref)
            out.append((ref, at))

    def under(a):
        for i, r in enumerate(lore):
            if r["of"] == "one" and r["at"] == a["id"]:
                add(("l", i), a["id"])
        if a.get("kind") and a.get("name") and a["name"] not in kinds:
            kinds.add(a["name"])
            for i, r in enumerate(lore):
                if r["of"] == "kind" and r["name"] == a["name"]:
                    add(("l", i), a["id"])

    for a in sorted((a for a in anc if not a["inv"]), key=lambda a: (_dist(a), _nat(a["id"]))):
        if a.get("person"):
            if _has(people.get(a["person"])):
                add(("p", a["person"]), a["id"])
        else:
            under(a)
    for m in obs.get("messages") or []:
        fr = str(m.get("from") or "")
        sk = ("b" + fr) if fr.isdigit() else fr if fr.startswith("npc:") else None
        if sk and _has(people.get(sk)):
            add(("p", sk), None)
        text = str(m.get("text") or "")
        hits = [(text.find(str(e["name"])), -len(str(e["name"])), _key_rank(k), k, ("p", k))
                for k, e in people.items() if isinstance(e, dict) and len(str(e.get("name") or "")) >= 2 and str(e["name"]) in text]
        hits += [(text.find(str(r["name"])), -len(str(r["name"])), 1 if r["of"] == "kind" else 3, "%06d" % i, ("l", i))
                 for i, r in enumerate(lore)
                 if (r["of"] == "kind" or r.get("at") is None)        # 이름 들림이 거는 것: 사람 · 종류 · 오래 남는 개별(건물·구역·의뢰). 층의 개별·장비는 아니다(설계 §4.1 —
                 and len(str(r.get("name") or "")) >= 2 and str(r["name"]) in text]   #   그 이름은 종류 이름이라 종류 기록이 맡는다 · 소지 장비는 소지품 순서로)
        for h in sorted(hits):
            add(h[-1], None)
    for a in (a for a in anc if a["inv"]):
        under(a)
    return out[:cap], out[cap:]


def logged(obs, refs):
    """스트림 결정 칸(lore_shown · lore_cut)의 안쪽 열쇠 목록 — refs = 엔진이 몸에 둔 obs.lore 의 열쇠(같은 순서)."""
    chosen, cut = pick(obs)

    def key(ref):
        return ref[1] if ref[0] == "p" else (refs[ref[1]] if ref[1] < len(refs) else "?")
    return [key(r) for r, _ in chosen], [key(r) for r, _ in cut]


class Shown:
    """한 관측의 고른 기록을 그 자리에 그린다 — 자리마다 한 번(그린 것은 다시 안 그린다), 자리 없는 것은 '떠오른 기록' 절로.
    call(사람 열쇠) = 이름 없는 사람 기록을 부르는 호칭(보는 사람 기준 — '낯선 사람(봇2)' · NPC 이름). ⚠️문구 임시(설계 §4.2)."""

    def __init__(self, obs, call):
        self.people = obs.get("people") or {}
        self.lore = obs.get("lore") or []
        self.chosen, self.cut = pick(obs)
        self.drawn = set()
        self.call = call

    def at(self, anchor, label=None):
        out = []
        for ref, at in self.chosen:
            if at == anchor and ref not in self.drawn:
                self.drawn.add(ref)
                out.append("  · %s%s" % (("%s — " % label) if label else "", self._body(ref, anchor, bool(label))))
        return out

    def _body(self, ref, anchor, labeled):
        if ref[0] == "p":
            e = self.people.get(ref[1]) or {}
            nm, tx = clip(e.get("name"), NAME_LEN), clip(e.get("text"), TEXT_LEN)
            return "네 기록: %s%s" % (nm or "(이름 모름)", (" — 「%s」" % tx) if tx else " (이름만 적어 두었다)")
        r = self.lore[ref[1]]
        tx = clip(r.get("text"), TEXT_LEN)
        if r["of"] == "kind":
            return "네 기록(종류: %s): 「%s」" % (r.get("name"), tx)
        if labeled:
            return "네 기록: 「%s」" % tx
        return "네 기록(%s): 「%s」" % (r.get("name") if anchor == "zone" else anchor, tx)

    def recall(self):
        """'떠오른 기록' 절의 줄 — 들은 말(말한 사람·이름 들림)로 고른 것. 줄 꼴 '- <이름 또는 호칭>: 「글」'."""
        out = []
        for ref, at in self.chosen:
            if at is not None or ref in self.drawn:
                continue
            self.drawn.add(ref)
            if ref[0] == "p":
                e = self.people.get(ref[1]) or {}
                tx = clip(e.get("text"), TEXT_LEN)
                out.append("- %s: 「%s」" % (clip(e.get("name"), NAME_LEN) or self.call(ref[1]), tx or "(이름만 적어 두었다)"))   # 0.5.9 꼴 그대로
            else:
                r = self.lore[ref[1]]
                out.append("- %s%s: 「%s」" % (r.get("name"), "(종류)" if r["of"] == "kind" else "", clip(r.get("text"), TEXT_LEN)))
        return out
