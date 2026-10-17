# -*- coding: utf-8 -*-
"""스냅샷 — 판의 몸을 마지막 기록 자리에 얼려 두는 파일(D79, 2026-09-16 파트너 "저장 시점은 마지막 기록에서" ·
"일단 던전에서 이어가게 하자 … 요약해서 들고 있게 … 종료 전에는 미리 알림").

러너가 **틱마다 루프 머리에서**(그 틱의 기록을 쓰기 전에) 세계·파티·장부를 통째로 피클해 둔다 — 그래서 론처 중지·서버 재시작·크래시 어느 경우든
"마지막으로 스트림에 남은 틱"과 같은 몸이 남는다. 이어가기(DUNGEON_RESUME)는 이 파일을 되살려 스트림을 그 자리에 이어 쓴다(같은 판 = 같은 run_id).

  · 파일 둘: `snapshot.pkl`(몸 — 피클) + `snapshot.json`(요약 — 론처가 읽는 쪽. 피클을 안 열고도 "지하 3층 t158 에서 멈춤"을 안다).
  · 결정 재생(시드+decisions 리플레이)이 아니라 스냅샷인 이유: 부수 채널(수첩·관계 살·도감 note·NPC 두뇌 문장)이 기록에서 완전히 재유도되지 않고,
    배포 중 엔진이 바뀌면 재생 결과가 어긋난다. 스냅샷은 "그때 그 몸"이다(엔진이 바뀌면 되살리기 실패 → 러너가 정직하게 폴백한다).
  · ⚠️ 피클 보안: 이 파일은 **러너 자신이 자기 state/ 폴더에 쓰고 같은 서버의 러너가 되읽는다**. 사용자 업로드·네트워크 경로는 없다(론처 API 는 json 요약만
    돌려준다). 남이 만든 .pkl 을 여기 두면 임의 코드가 돈다 — 데이터 폴더의 쓰기 권한이 곧 서버 권한이라는 전제 위에 있다(accounts/·state/ 와 같은 급).
  · 판 번호(p0.5.3 — 라이브 패치의 '저장 데이터 호환'): 패치가 몸·장부의 꼴을 바꾸면 옛 스냅샷을 버리지 않고 새 꼴로 올려 읽는다.
      version       판형 — 2 = state_version 이 있는 판. ≤v0.5.2 코드는 1 만 읽으므로 새 스냅샷을 거절한다(되돌린 코드가 새 몸을 옛 규칙으로 잇지 않는다
                    — 러너는 정직하게 새 판으로 폴백, 옛 기록은 runs/ 로 대피). 이 코드는 1(=내용 판 0)과 2 를 읽는다.
      state_version 내용 판 — 몸·장부 꼴이 바뀌는 패치마다 STATE_VERSION 을 올리고 MIGRATIONS 에 n→n+1 함수 하나를 더한다(savedata 와 같은 체인).
                    더 새 내용 판(되돌린 코드가 새 스냅샷을 읽음)은 거절한다 — 요약(read_meta)도 None 이라 론처가 이어가기를 내밀지 않는다.
      0→1(p0.5.3): 몸에 정신·숙련 칸(mind·search_prof·steal_prof)이 생겼다 — 옛 몸에 직업 기본값을 채운다(스폰과 같은 규칙, judge.prof).
      1→2(p0.5.4): 반응 원장(social_reactions.ReactionBook)에 수신자별 번호표(alias)가 생겼다 — 옛 원장은 원장 순서로 번호표를 다시 매긴다
                   (ReactionBook.rebuild_alias — 지나간·대기 사건 모두 받은 순서대로, 이어간 뒤의 새 사건은 그 뒤 번호).
      2→3(p0.5.9 신원 ID-1): 기억·목격·쓰러진 사연의 '사람이 친 by'(실명 문자열)에 사람 열쇠(by_id)를 잇는다 — 호칭은 그릴 때 보는 사람이 붙인다
                   (_m2_refs: 그 판 시트의 이름과 정확히 한 명이 맞을 때만 잇고, 못 잇거나 동명이인이면 by_unknown — 렌더는 '누군가').
      3→4(p0.5.10 신원 ID-2): NPC 되받기 장부 npc_replies{이름: n} → 대화 장부 npc_talk{'npc:<이름>': n}(대화 세 길이 한 장부를 센다).
                   자동 접근 대기(approach)에 결정 때의 말(say·to)이 실릴 수 있다 — 옛 대기에는 없을 뿐이라 변환은 없다(도착 때 '말없이 다가왔다').
      4→5(p0.5.11 개인 로어북): 인물 기록 판의 몸에 로어북 장부 lore{} · 사람 기록의 이름·글을 20·80자로(옛 시트 씨앗은 안 잘랐다) ·
                   던전(층 인스턴스)마다 일련 scope · 마을엔 건물 피처 → 공간 id(building_ids — layout 의 문턱 칸으로 다시 잇는다) ·
                   최상위 lore_ids{scope, uid}(다음 층 일련·장비 번호). 인물 기록이 꺼진 판은 손대지 않는다(옛 피클 그대로).
      5→6(p0.5.13 경제 1a): 몸마다 골드(시작 지갑) · 의뢰 장부의 보상 받은 의뢰(paid — 옛 판에서 이미 보고한 완수는 다시 주지 않는다) ·
                   마을의 상인 선물(판매로 바뀌었다)을 걷고 상인·가게·숙소의 말을 지금 정의로 다시 읽는다(_m5_gold).
      6→7(p0.5.14 등 돌리기): 몸에 등 돌림 표식 npc_away{'npc:<이름>': 시작 틱}이 생겼다 — 옛 몸에서 대화 장부가 상한(고정 거절 차례)인 쌍을
                   이어간 틱(next_turn - 1)부터 등 돌림으로 올린다(_m6_away — 닫는 말의 진짜 틱은 옛 몸에 없다. 옛 규칙으로도 그 방문 동안은 거절이었다).
      7→8(p0.5.15 반복 신호 + 목표 칸): 몸에 연속 칸 repeat · 목표 칸 todo(적었을 때만)가 생겼다 — 옛 몸의 최근 판단 장부(history)로 연속을 다시 세운다
                   (_m7_repeat — 지난 신호 차례는 늦게 싣지 않는다 · 변화는 몰라 '달라진 것은 없다'는 붙이지 않는다). 목표 칸은 옛 몸에 없다.
      8→9(p0.5.16 욕구 틀 + 배고픔): 몸마다 욕구 충족도 needs(정의의 시작값)·기분 조각 moods·휴대식 rations · 식사·햇사과를 팔게 된
                   주점 주인·주점·채소 좌판·노점 상인의 말을 지금 정의로 다시 읽는다(_m8_needs). 세계의 욕구 사건 버퍼(need_log)는 getattr 기본값으로 받는다.
      9→10(p0.5.17 마을 NPC 는 마을 이야기만): 던전마다 옛 소문 재료 칸 rumor(지하 1층 실측)를 걷고, 던전 소문을 거둔 주점 주인·떠돌이 모험자·주점의 말
                   (정의 사본의 소문 인사 칸·역할·성격·대사·특징·이야기)을 지금 정의로 다시 읽는다(_m9_rumor).
      10→11(p0.5.18 몸·기분 줄): 기분 조각의 꼴이 바뀌었다(문장 line → 먹은 것 이름 what — 값·이유 낱말은 그릴 때 정의에서). 옛 꼴 조각(line 칸)은 걷는다
                   (_m10_moods — 이유를 다시 쓸 재료인 먹은 것 이름이 옛 조각에 없고, 길어야 120틱 남는 조각이다). 충족도는 그대로.
      11→12(p0.5.22 캐릭터 특성): 욕구 무게는 시트의 특성이 정한다. 그 판의 시트(sheets)에서 0.5.20~21 의 needs·needs_meta 칸을 걷고(입맛은 그대로),
                   몸마다 무게 need_w·배율 trait_fx 를 몸의 특성으로 다시 정한다(_m11_traits — 스폰과 같은 규칙 needs.fields. 층 이동·부활 때 스폰이 시트에서
                   다시 읽는 것과 이어간 순간의 몸이 같아진다). 충족도·기분 조각은 그대로.
      12→13(p0.5.25 주점 무료 식사): 몸에 무료 끼니 칸 free 가 생겼다 — p0.5.27 에 걷었다. 이 이관은 이제 할 일이 없다(_m12_pass — 그 칸은 13→14 가 버린다).
      13→14(p0.5.27 시작 골드 10): 0.5.25 판의 몸에 있던 무료 끼니 칸 free 를 버리고, 마을 던전의 주점 주인 말을 지금 정의로 다시 읽는다
                   (피클에 얼어 있던 정의 사본에서 line_free_end 가 빠지고 돈이 모자랄 때의 말 line_too_poor 가 든다 — _m13_meal). 골드는 그대로(시작 골드는 새 판에만).
LLM 0콜 · 순수 파일(이관 함수만 몸 dict·반응 원장을 고친다 — 그때 judge 를 늦게 import).
"""
import io
import json
import os
import pickle
import tempfile
import time

VERSION = 2                  # 판형(위 머리글) — 옛 코드(version 1 만 읽음)가 새 스냅샷을 거절하게 하는 문
READS = (1, 2)               # 이 코드가 읽는 판형. 1 = p0.5.2 까지(내용 판 0)
STATE_VERSION = 14           # 내용 판 — 올릴 때 MIGRATIONS 에 한 칸
PKL = "snapshot.pkl"
META = "snapshot.json"


def _bodies(snap):
    """스냅샷 안의 몸 dict 전부(중복 없이) — 지금 세계의 봇 · 다른 세계(D84 worlds)의 봇 · 부활 대기(D99 waiting)."""
    seen, out = set(), []
    lists = [snap.get("bots") or []] + [w.get("bots") or [] for w in (snap.get("worlds") or []) if isinstance(w, dict)]
    lists.append(list((snap.get("waiting") or {}).values()))
    for lst in lists:
        for b in lst:
            if isinstance(b, dict) and id(b) not in seen:
                seen.add(id(b))
                out.append(b)
    return out


def _m0_prof(snap):
    """0→1(p0.5.3): 옛 몸에 정신·숙련 칸 — 시트(그 판의 시트) 값 → 직업 기본값 → 0. 이미 있는 칸은 그대로."""
    import judge                                  # 늦은 import — 이관이 있을 때만 직업표를 읽는다
    sheets = snap.get("sheets") or {}
    for b in _bodies(snap):
        for k, v in judge.body_fields(sheets.get(str(b.get("char"))) or b).items():
            b.setdefault(k, v)
    return snap


def _books(snap):
    """스냅샷 안의 반응 원장 전부(보통 하나 — 세계·보존 층의 던전이 같은 원장을 가리킨다)."""
    ds = [snap.get("d")] + [w.get("d") for w in (snap.get("worlds") or []) if isinstance(w, dict)]
    ds += [v.get("d") for v in (snap.get("saved") or {}).values() if isinstance(v, dict)]
    found, out = set(), []
    for b in [snap.get("reaction_book")] + [getattr(x, "reaction_book", None) for x in ds]:
        if b is not None and id(b) not in found:
            found.add(id(b))
            out.append(b)
    return out


def _m1_alias(snap):
    """1→2(p0.5.4): 옛 반응 원장에 번호표 — 원장 순서(= 받은 순서)로 다시 매긴다. 이미 있으면 그대로."""
    for b in _books(snap):
        if not hasattr(b, "alias"):
            b.rebuild_alias()
    return snap


def _m2_refs(snap):
    """2→3(p0.5.9 신원 ID-1, 설계 §8.1): 옛 기억(fallen·died)·목격(ally_down·ally_hurt …)·쓰러진 사연(down_by) 중 **by_kind 'bot'**(사람이 쳤다)인
    항목의 실명 by → 그 판 시트의 이름 표로 사람을 찾는다. 정확히 한 명과 맞으면 by_id='b<char>', 맞는 사람이 없거나 둘 이상(동명이인)이면
    by_unknown True(인물 기록 판의 렌더는 '누군가' — 실명이 새지 않는다, 설계 X24). 원문 by 는 지우지 않는다(관전·분석용 — 렌더는 사람 by 를
    그대로 쓰지 않는다). 몹(by_kind 없음)·함정·출혈(trap·hazard·status)은 그대로. 인물 기록의 src 'party'(옛 파티 결성 자동 소개) 항목은 남긴다 —
    그 판에서 이미 일어난 일이다. 이미 by_id·by_unknown 이 있으면 손대지 않는다(제자리·한 번)."""
    names = {}
    for c, sh in (snap.get("sheets") or {}).items():
        nm = (sh or {}).get("name") or (sh or {}).get("job") if isinstance(sh, dict) else None
        if nm:
            names.setdefault(nm, []).append(str(c))

    def fix(e):
        if not isinstance(e, dict) or e.get("by_kind") != "bot" or "by_id" in e or e.get("by_unknown"):
            return
        hit = names.get(e.get("by")) or []
        if len(hit) == 1:
            e["by_id"] = "b" + hit[0]
        else:
            e["by_unknown"] = True

    for b in _bodies(snap):
        for e in (b.get("memories") or []) + (b.get("witnessed") or []):
            fix(e)
        fix(b.get("down_by"))
    return snap


def _m3_talk(snap):
    """3→4(p0.5.10 신원 ID-2, 설계 §8.1): 몸마다 옛 되받기 장부 npc_replies{NPC 이름: n} → 대화 장부 npc_talk{'npc:<이름>': n}.
    옛 장부는 되받기만 셌으므로 그 수를 대화 차례로 그대로 옮긴다(이미 npc_talk 에 같은 열쇠가 있으면 큰 쪽). 옛 칸은 지운다(제자리·한 번)."""
    for b in _bodies(snap):
        old = b.pop("npc_replies", None)
        if isinstance(old, dict) and old:
            book = b.setdefault("npc_talk", {})
            for nm, n in old.items():
                k = "npc:%s" % nm
                book[k] = max(int(book.get(k, 0) or 0), int(n or 0))
    return snap


def dungeons(snap):
    """스냅샷 안의 던전(층 인스턴스) 전부 — 보존 층(깊이 순) → 다른 세계 → 지금 층, 같은 객체는 한 번(결정론 순서 — 이관이 일련을 이 순서로 붙인다)."""
    seen, out = set(), []
    saved = snap.get("saved") or {}
    ds = [saved[k].get("d") for k in sorted(saved) if isinstance(saved[k], dict)]
    ds += [w.get("d") for w in (snap.get("worlds") or []) if isinstance(w, dict)]
    ds.append(snap.get("d"))
    for d in ds:
        if d is not None and id(d) not in seen:
            seen.add(id(d))
            out.append(d)
    return out


def _m4_lore(snap):
    """4→5(p0.5.11 개인 로어북, 설계 §6.2): 인물 기록 판(people 이 있는 몸이 하나라도 있다)에서만 — 몸마다 lore{}(있으면 그대로) · 사람 기록의
    이름·글을 20·80자로 · 일련 없는 던전에 scope(위 dungeons 순서로 1부터, 이미 붙은 번호 뒤로) · 마을 던전에 building_ids(lorebook.town_building_ids) ·
    최상위 lore_ids(옛 판엔 장비 번호가 없어 uid=1).
    러너가 이어갈 때 lore_ids 를 실제로 쓰인 가장 큰 번호 + 1 과 다시 견준다(망가진 발급 상태 방어 — lorebook.used_ids)."""
    import lorebook                               # 늦은 import — 이관이 있을 때만
    bodies = [b for b in _bodies(snap) if b.get("people") is not None]
    if not bodies:
        return snap
    for b in bodies:
        b.setdefault("lore", {})
        for e in b["people"].values():
            if isinstance(e, dict):
                for k, n in (("name", lorebook.NAME_LEN), ("text", lorebook.TEXT_LEN)):
                    if e.get(k):
                        e[k] = lorebook.clip(e[k], n)
    ds = dungeons(snap)
    nxt = 1 + max([int(getattr(d, "scope", None) or 0) for d in ds] or [0])
    for d in ds:
        if getattr(d, "scope", None) is None:
            d.scope, nxt = nxt, nxt + 1
        if getattr(d, "town", False) and getattr(d, "building_ids", None) is None:   # p0511b(Codex p0511r 필수 ①): 옛 마을에 건물 피처 → 공간 id
            bids = lorebook.town_building_ids(d)                                     #   (러너가 지을 때 다는 짝과 같다) — 없으면 건물 기록이 place: 가 아니라 층 기록이 된다
            if bids:
                d.building_ids = bids
    snap.setdefault("lore_ids", {"scope": nxt, "uid": 1})
    return snap


ECONOMY_DEFS = ("gear_merchant", "item_merchant", "innkeeper", "equipment_store", "general_store",
                "shared_lodging", "ordinary_inn", "garden_inn")   # p0.5.13 이관이 말을 새로 읽는 정의 — 선물이 판매로 바뀌어 거짓이 된 대사·역할·특징 · 가게가 된 건물


def _m5_gold(snap):
    """5→6(p0.5.13 경제 1a): ① 몸마다 골드(시작 지갑 dungeon_gm.START_GOLD — 이미 있으면 그대로) ② 의뢰 장부에 '보상을 이미 받은 의뢰'(paid) —
    옛 판에서 이미 보고한 완수는 보상이 없던 때의 일이라 다시 주지 않는다(장부가 보고를 찍은 원정의 완수 + 앞선 결산이 적은 완수) — 보고 전의 완수는 다음 보고에 받는다
    ③ 마을 던전마다: 판매로 바뀐 상인의 선물(npc_gifts)을 걷고, 피클에 얼어 있던 상인·가게·숙소의 말(대사·재방문 대사·역할·성격·특징·이야기·마을 안내)을
    지금 정의에서 다시 읽는다(ECONOMY_DEFS 만 — 공물 판이 갈아 끼운 신전 문장 같은 다른 자리는 손대지 않는다). 상품·값은 피클에 없다(정의에서 늘 다시 센다)."""
    import dungeon_gm as G                        # 늦은 import — 이관이 있을 때만
    for b in _bodies(snap):
        b.setdefault("gold", G.START_GOLD)
    q = snap.get("quests")
    if isinstance(q, dict) and "paid" not in q:
        reported = q.get("reported") is not None
        said = set(((snap.get("expedition") or {}).get("said")) or [])
        old = {qid: {"turn": t, "by": None} for qid, t in (q.get("done") or {}).items() if reported or qid in said}
        if old:
            q["paid"] = old
    for d in dungeons(snap):
        if getattr(d, "town", False):
            _refresh_economy_words(d, G)
    return snap


def _refresh_economy_words(d, G, defs=ECONOMY_DEFS):
    """마을 던전 하나 — defs(기본 ECONOMY_DEFS)의 NPC·건물·오브젝트 피처의 말을 지금 정의(마을 생활 판이면 life 를 얹은 것)로 다시 읽는다. 선물은 정의에 없으면 걷는다.
    p0.5.16: 오브젝트(마을 생활 판의 채소 좌판 같은 것)는 type 이 같은 피처의 특징·이야기(place_story)만."""
    life = bool(getattr(d, "town_life", False))
    by_name = {G.ENT.get(e)["name"]: e for e in defs if G.ENT.get(e)["kind"] == "npc"}
    by_type = {G.ENT.get(e)["type"]: e for e in defs if G.ENT.get(e)["kind"] == "object"}
    bdefs = getattr(d, "building_defs", None) or {}
    for fid, f in d.features.items():
        eid = (by_name.get(f.name) if f.type == "npc" else bdefs.get(fid) if f.type == "building" else by_type.get(f.type))
        if eid not in defs:
            continue
        comps = G.ENT.comps_of(eid, life)
        story = comps.get("story")
        if story and fid in (getattr(d, "place_story", None) or {}):
            d.place_story[fid] = dict(story)
        if f.type not in ("npc", "building"):        # 오브젝트 — 말은 특징·이야기뿐(위에서 다시 읽었다)
            continue
        if f.type == "npc":
            spec = G.ENT.npc(eid, life=life)
            walk_ = (d.npc_defs.get(f.name) or {}).get("walk")   # p0.5.17: 행인의 걷는 자리는 지을 때 layout 이 덮을 수 있다(walker_rects) — 말만 다시 읽는다
            d.npc_defs[f.name] = {k: v for k, v in spec.items() if v not in (None, [], "")}
            if walk_:
                d.npc_defs[f.name]["walk"] = walk_
            d.npc_lines[f.name] = spec.get("line") or "…"
            if spec.get("line_again"):
                d.npc_lines_again[f.name] = spec["line_again"]
            if spec.get("role"):
                d.feature_roles[fid] = spec["role"]
            if spec.get("gift"):
                d.npc_gifts[f.name] = dict(spec["gift"])
            else:
                d.npc_gifts.pop(f.name, None)
        else:
            role = (comps.get("building") or {}).get("role")
            if role and fid in (getattr(d, "feature_roles", None) or {}):
                d.feature_roles[fid] = role
    for p in getattr(d, "town_guide", None) or []:   # D81 마을 안내의 장소 줄(특징 한 줄) — 같은 이름의 피처 소개를 따라간다
        fid = next((k for k, f in d.features.items() if f.name == p.get("name") and k in (getattr(d, "place_story", None) or {})), None)
        if fid is not None and (d.place_story[fid] or {}).get("trait"):
            p["about"] = d.place_story[fid]["trait"]


def _m6_away(snap):
    """6→7(p0.5.14 등 돌리기): 몸마다 대화 장부 npc_talk 가 상한(dungeon_gm.NPC_REPLY_MAX — 옛 판의 고정 거절 차례)인 쌍을 등 돌림으로 —
    npc_away{열쇠: 이어간 틱(next_turn - 1)}. 이미 표식이 있으면 그대로 · 상한 아래는 손대지 않는다 · 걸린 쌍이 없으면 칸을 만들지 않는다(제자리·한 번)."""
    import dungeon_gm as G                        # 늦은 import — 이관이 있을 때만
    now = max(0, int(snap.get("next_turn") or 1) - 1)
    for b in _bodies(snap):
        over = [k for k, n in sorted((b.get("npc_talk") or {}).items()) if int(n or 0) >= G.NPC_REPLY_MAX]
        if over:
            aw = b.setdefault("npc_away", {})
            for k in over:
                aw.setdefault(k, now)
    return snap


def _m7_repeat(snap):
    """7→8(p0.5.15 반복 신호 + 목표 칸): 몸에 반복 신호의 연속 repeat{…}·목표 칸 todo 가 생겼다. 목표 칸은 옛 몸에 적은 적이 없다(칸을 만들지 않는다).
    연속은 옛 몸의 최근 판단 장부 history(D38)의 끝에서 같은 열쇠가 이어진 수로 다시 세운다(repeat_signal.seed — 지난 신호 차례는 늦게 싣지 않고,
    그동안의 변화는 몰라 '달라진 것은 없다'를 붙이지 않는다). 이어진 판단이 없거나 이미 칸이 있으면 그대로(제자리·한 번)."""
    import repeat_signal as RS                    # 늦은 import — 이관이 있을 때만
    for b in _bodies(snap):
        if "repeat" not in b:
            ch = RS.seed(b.get("history"), b.get("char"))
            if ch:
                b["repeat"] = ch
    return snap


NEED_DEFS = ("tavern_keeper", "tavern", "produce_stall", "street_vendor")   # p0.5.16 이관이 말을 새로 읽는 정의 — 식사를 팔게 된 주점(주인의 '안은 아직 준비 중'·맡은 가게) ·
#   햇사과를 팔게 된 채소 좌판('구경만 된다') · 노점 상인('아직 값은 안 매겼어요' — 가게가 생겨 거짓이 된 말, 경제 설계 §7)


def _m8_needs(snap):
    """8→9(p0.5.16 욕구 틀 + 배고픔): 몸마다 욕구 충족도 needs{욕구: 시작값}(정의의 start — 옛 판의 몸은 이 순간이 '판 시작'이다) · 빈 기분 조각 moods ·
    휴대식 rations 0 — 이미 있으면 그대로(제자리·한 번). 무게·취향은 시트에서 스폰이 읽는다(옛 시트엔 칸이 없어 모두 보통 — 몸에 칸을 만들지 않는다).
    마을 던전마다 식사·햇사과를 팔게 된 주점 주인·주점·채소 좌판과 노점 상인의 말을 지금 정의로 다시 읽는다(NEED_DEFS — 상품·값은 피클에 없다: 정의에서 늘 다시 센다)."""
    import dungeon_gm as G                        # 늦은 import — 이관이 있을 때만
    for b in _bodies(snap):
        b.setdefault("needs", {nid: int(sp["start"]) for nid, sp in G.NE.live()})
        b.setdefault("moods", [])
        b.setdefault("rations", 0)
    for d in dungeons(snap):
        if getattr(d, "town", False):
            _refresh_economy_words(d, G, NEED_DEFS)
    return snap


RUMOR_DEFS = ("tavern_keeper", "wandering_adventurer", "tavern")   # p0.5.17 이관이 말을 새로 읽는 정의 — 던전 소문을 거둔 주점 주인(소문 인사·역할·성격·특징·이야기) ·
#   떠돌이 모험자('2층 거미' 대사·역할의 '던전 소문'·성격) · 주점(역할·특징·이야기의 소문 구절)


def _m9_rumor(snap):
    """9→10(p0.5.17 마을 NPC 는 마을 이야기만 — 민옥 10-16 '던전 상세 정보는 아예 없앤다'): 던전마다 옛 소문 재료 칸 rumor(지하 1층 실측 —
    이 코드는 더 만들지도 읽지도 않는다)를 걷는다 · 마을 던전마다 RUMOR_DEFS 의 말을 지금 정의로 다시 읽는다(피클에 얼어 있던 정의 사본에서
    소문 인사 칸 hail_rumor·'소문' 역할이 빠진다 — 행인의 걷는 자리는 그대로). 이미 건넨 인사·대화(편지함·기억)는 그 판에서 일어난 일이라 손대지 않는다(제자리·한 번)."""
    import dungeon_gm as G                        # 늦은 import — 이관이 있을 때만
    for d in dungeons(snap):
        vars(d).pop("rumor", None)
        if getattr(d, "town", False):
            _refresh_economy_words(d, G, RUMOR_DEFS)
    return snap


def _m10_moods(snap):
    """10→11(p0.5.18 몸·기분 줄 — DECISIONS 10-16): 기분 조각이 문장(line)을 들던 꼴에서 먹은 것 이름(what)만 드는 꼴로 바뀌었다(값과 이유 낱말은
    '기분:' 줄을 그릴 때 정의에서 읽는다). 옛 꼴 조각(line 칸이 있는 것)은 걷는다 — 이유 낱말의 {what} 을 채울 먹은 것 이름이 옛 조각에 없고,
    길어야 120틱 남는 조각이라 지어내지 않는다. 충족도·새 꼴 조각은 그대로(제자리·한 번 — 다시 올려도 같다)."""
    for b in _bodies(snap):
        if isinstance(b.get("moods"), list):
            b["moods"] = [m for m in b["moods"] if not (isinstance(m, dict) and "line" in m)]
    return snap


GONE_SHEET_KEYS = ("needs", "needs_meta")   # p0.5.22 거둔 시트 칸(0.5.20~21 욕구 생성 호출) — savedata.GONE_NEED_KEYS 와 같은 목록(이관 함수끼리 서로 import 하지 않는다)


def _m11_traits(snap):
    """11→12(p0.5.22 캐릭터 특성 — DECISIONS 10-17): 욕구 무게는 시트의 특성이 정한다. 그 판의 시트(sheets)에서 0.5.20~21 의 needs·needs_meta 칸을
    걷는다(제자리 — 입맛 taste 는 그대로). 몸마다 무게 need_w·특성 배율 trait_fx 를 몸의 특성 이름(traits — 없으면 그 판의 시트)으로 다시 정한다 —
    스폰과 같은 규칙(needs.fields: 단계 있는 욕구만 · 보통·없음이면 칸을 지운다). 옛 몸의 need_w(생성 호출이 시트에 적은 무게)를 그대로 두면
    층 이동·부활(스폰이 시트에서 다시 읽는다) 때 무게가 바뀐다 — 이어간 순간부터 같게 맞춘다. 충족도·기분 조각은 그대로(다시 올려도 같다)."""
    import needs as NE                            # 늦은 import — 이관이 있을 때만(특성 정의를 읽는다)
    sheets = snap.get("sheets") if isinstance(snap.get("sheets"), dict) else {}
    for s in sheets.values():
        if isinstance(s, dict):
            for k in GONE_SHEET_KEYS:
                s.pop(k, None)
    for b in _bodies(snap):
        tr = b.get("traits") if "traits" in b else (sheets.get(str(b.get("char"))) or {}).get("traits")
        f = NE.fields({"traits": tr})
        for k in ("need_w", "trait_fx"):
            if k in f:
                b[k] = f[k]
            else:
                b.pop(k, None)
    return snap


def _m12_pass(snap):
    """12→13(p0.5.25 주점 무료 식사 — p0.5.27 에 걷었다): 그때 몸마다 채우던 무료 끼니 칸은 다음 이관(13→14)이 버린다 — 여기서는 할 일이 없다(판 번호만 지난다)."""
    return snap


MEAL_DEFS = ("tavern_keeper",)   # p0.5.27 이관이 말을 새로 읽는 정의 — 돈이 모자랄 때의 말(line_too_poor)이 생긴 주점 주인(빠진 옛 칸은 _m13_meal)


def _m13_meal(snap):
    """13→14(p0.5.27 시작 골드 10 — DECISIONS 10-17): 0.5.25 판의 몸(지금 세계·다른 세계·부활 대기)에 있던 무료 끼니 칸 free 를 버린다 ·
    마을 던전마다 주점 주인의 말을 지금 정의로 다시 읽는다(MEAL_DEFS — 피클에 얼어 있던 정의 사본의 line_free_end 가 빠지고 line_too_poor 가 든다).
    골드는 건드리지 않는다(이어가는 판의 지갑 그대로 — 시작 골드 10 은 새 판에만). 제자리·한 번(다시 올려도 같다)."""
    import dungeon_gm as G                        # 늦은 import — 이관이 있을 때만
    for b in _bodies(snap):
        b.pop("free", None)
    for d in dungeons(snap):
        if getattr(d, "town", False):
            _refresh_economy_words(d, G, MEAL_DEFS)
    return snap


MIGRATIONS = {0: _m0_prof, 1: _m1_alias, 2: _m2_refs, 3: _m3_talk, 4: _m4_lore, 5: _m5_gold, 6: _m6_away, 7: _m7_repeat, 8: _m8_needs,
              9: _m9_rumor, 10: _m10_moods, 11: _m11_traits, 12: _m12_pass, 13: _m13_meal}   # n → n+1 (0..STATE_VERSION-1 이 다 있어야 한다 — verify_class_foundation)


def state_version_of(doc):
    """스냅샷(또는 요약)의 내용 판 — 판형 1 은 0, 칸이 이상하면 0."""
    if not isinstance(doc, dict) or doc.get("version") == 1:
        return 0
    v = doc.get("state_version", 0)
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def upgrade(snap):
    """되살린 스냅샷 → 지금 꼴. 옛 내용 판이면 이관 함수를 한 판씩(제자리에서 고친다), 판 번호를 지금 것으로."""
    v = state_version_of(snap)
    while v < STATE_VERSION:
        snap = MIGRATIONS[v](snap)
        v += 1
    snap["version"], snap["state_version"] = VERSION, v
    return snap


class SnapshotError(RuntimeError):
    pass


def paths(state_dir):
    return os.path.join(state_dir, PKL), os.path.join(state_dir, META)


def _replace(tmp, dst):
    for i in range(20):                       # Windows: 방금 쓴 파일을 색인기·백신이 잠깐 잡으면 replace 가 WinError 5(bestiary.save 선례)
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05 * (i + 1))


def _atomic_bytes(dst, data):
    folder = os.path.dirname(dst) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".snap-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        _replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def write(state_dir, snap, meta):
    """몸(snap dict)과 요약(meta dict)을 원자적으로 쓴다. 둘 다 version·state_version 이, 요약에는 saved_at 도 덧붙는다. 반환 = 피클 바이트 수."""
    pkl, mj = paths(state_dir)
    data = pickle.dumps({"version": VERSION, "state_version": STATE_VERSION, **snap}, protocol=pickle.HIGHEST_PROTOCOL)
    _atomic_bytes(pkl, data)
    write_meta(state_dir, meta)
    return len(data)


def write_meta(state_dir, meta):
    """요약만 다시 쓴다(정지 사유 갱신 등 — 몸은 그대로)."""
    _, mj = paths(state_dir)
    doc = {"version": VERSION, "state_version": STATE_VERSION, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           **{k: v for k, v in meta.items() if k not in ("version", "state_version")}}   # 판 번호는 늘 지금 코드의 것(되읽은 옛 요약을 다시 써도)
    _atomic_bytes(mj, (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def read_meta(state_dir):
    """요약(json)만 읽는다 — 론처·상태 API 용(피클을 열지 않는다). 없거나 깨지면 None."""
    _, mj = paths(state_dir)
    try:
        with io.open(mj, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("version") not in READS or not doc.get("run_id"):
        return None
    if state_version_of(doc) > STATE_VERSION:         # 더 새 코드가 멈춘 판 — 이 코드로는 이어가기를 내밀지 않는다
        return None
    pkl, _ = paths(state_dir)
    if not os.path.isfile(pkl):
        return None
    return doc


def load(pkl_path):
    """피클을 되살린다 → (snap, meta). 요약이 없거나 run_id 가 어긋나면 SnapshotError(폴백 사유)."""
    state_dir = os.path.dirname(os.path.abspath(pkl_path))
    meta = read_meta(state_dir)
    if meta is None:
        raise SnapshotError("스냅샷 요약(snapshot.json)이 없거나 깨졌다")
    try:
        with open(pkl_path, "rb") as f:
            snap = pickle.load(f)               # ⚠️ 자기 폴더의 자기 파일만(모듈 머리글 보안 전제)
    except Exception as e:                      # 엔진이 바뀌어 클래스가 안 맞는 것까지 — 이유는 한 줄로
        raise SnapshotError("스냅샷을 되살리지 못했다: %s: %s" % (type(e).__name__, str(e)[:120]))
    if not isinstance(snap, dict) or snap.get("version") not in READS:
        raise SnapshotError("스냅샷 판형이 다르다")
    if state_version_of(snap) > STATE_VERSION:
        raise SnapshotError("더 새 코드가 쓴 스냅샷이다(내용 판 %d > %d)" % (state_version_of(snap), STATE_VERSION))
    if snap.get("run_id") != meta.get("run_id"):
        raise SnapshotError("스냅샷 몸과 요약이 다른 판이다")
    for k in ("d", "bots", "sheets", "next_turn", "stream_pos", "seed", "started"):
        if k not in snap:
            raise SnapshotError("스냅샷에 %s 가 없다" % k)
    try:
        return upgrade(snap), meta
    except Exception as e:                      # 이관이 깨지면 러너를 죽이지 않고 정직하게 폴백(새 판 + 옛 기록 대피)
        raise SnapshotError("옛 스냅샷을 새 꼴로 올리지 못했다: %s: %s" % (type(e).__name__, str(e)[:120]))


def remove(state_dir):
    """이어갈 몸이 없어졌다(판이 끝났거나 새 판을 시작했다)."""
    for p in paths(state_dir):
        try:
            os.remove(p)
        except OSError:
            pass
