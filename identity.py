# -*- coding: utf-8 -*-
"""신원 — 사람을 문장 속에서 부르는 말(호칭)의 단일 원천(신원 설계 v2 §1.4 · p0.5.9 ID-1 이름 층).

원칙(설계 §0.2): **기록은 내부 열쇠로, 호칭은 그릴 때.** 결과·기억·장부에는 실명 문자열 대신 내부 열쇠를 적고,
프롬프트를 그릴 때 보는 사람(viewer)의 호칭 함수가 이름을 붙인다. 판정은 엔진, 해석은 에이전트 — 누가 누구인지는
모험가가 lore_note(p0.5.11 개인 로어북 — 옛 person_note)로 스스로 정리한다(DECISIONS 2026-10-12 67). 두뇌가 없는 NPC 자리만 엔진 규칙이 메운다(길드 등록 = 모험가 이름을 다 안다, 69).

내부 열쇠(이 모듈은 바꾸지 않는다): 모험가 'b<char>'(예 'b2') · NPC 'npc:<정의 name>'(예 'npc:대장장이').
  call(viewer, key, real)  — 모험가가 보는 호칭. 인물 기록 판(viewer['people'] 이 있다)은 내 기록 → 살펴 안 것(inspected, MP1 연결 자리 — 지금 비어 있다)
                             → 없으면 '낯선 사람'.
                             인물 기록이 꺼진 판은 명단 실명(real) 그대로(옛 판 바이트 불변). NPC 는 ID-6 전까지 정의 이름(모두에게 보인다).
  pick(names, char, default) — 이미 만든 호칭 사전(brains 의 names — '?' 칸 = 인물 기록 판의 '모르는 사람' 호칭)으로 같은 규칙.
  call_npc(key, real)      — NPC 두뇌 입력의 호칭: 모험가는 실명, NPC 는 정의 이름.
  npc_heard(text, real)    — 모험가 말을 NPC 입력에 넣을 때 '봇N'·'bN' 같은 세계 밖 손잡이를 NPC 가 아는 이름으로(설계 §1.6, c05 ④).
꼬리 '(봇N)' 같은 ID 표기는 ID-6 전까지 부르는 쪽(렌더)의 지금 꼴 그대로다 — 여기는 이름 자리만 정한다.
LLM 0콜 · 판정 rng 무접촉 · 엔진 무의존(dungeon_gm 을 import 하지 않는다 — 엔진·두뇌·러너가 이 모듈을 쓴다).
"""
import re

STRANGER = "낯선 사람"     # 이름을 모르는 사람(인물 기록 판)
SOMEONE = "누군가"         # 누구였는지 잇지 못한 사람(옛 기록의 실명을 이관이 사람과 잇지 못했을 때 · 모르는 사람의 묘)
SELF = "너"


def is_bot_key(key):
    """'b<번호>' — 모험가 내부 열쇠."""
    s = str(key or "")
    return s[:1] == "b" and s[1:].isdigit()


def is_person_key(key):
    """사람 내부 열쇠인가 — 모험가 'b<번호>' 또는 NPC 'npc:<이름>'. 사람 판정은 이 함수 하나로(설계 X6)."""
    s = str(key or "")
    return is_bot_key(s) or (s.startswith("npc:") and len(s) > 4)


def char_of(key):
    """'b2' → '2'. 모험가 열쇠가 아니면 None."""
    s = str(key or "")
    return s[1:] if is_bot_key(s) else None


def bot_key(char):
    return "b%s" % char


def _norm(key):
    """'2'(char) · 'b2' · 'npc:<이름>' → 내부 열쇠."""
    s = str(key or "")
    return "b" + s if s.isdigit() else s


def _named(book, k):
    """기록 장부(people·inspected) 한 칸의 이름 — 없으면 None."""
    e = (book or {}).get(k)
    return e["name"] if isinstance(e, dict) and e.get("name") else None


def people_names(viewer):
    """보는 사람 기준 호칭 사전(D85) — 이름을 아는 모험가만 {char: 이름}. 없는 사람은 부르는 쪽이 '낯선 사람'이라 쓴다.
    우선순위(call 과 같다): 내 기록 people(내 lore_note · 시트 씨앗) > 살펴 안 것 inspected(설계 §1.5 — **MP1 사람 search 의 연결 자리**:
    search 가 이름 단계에 닿으면 엔진이 inspected[key].name 을 적는다. p0.5.9 지금은 아무도 채우지 않아 늘 비어 있다)."""
    v = viewer or {}
    out = {k[1:]: _named(v.get("inspected"), k) for k in (v.get("inspected") or {}) if is_bot_key(k) and _named(v.get("inspected"), k)}
    out.update({k[1:]: _named(v.get("people"), k) for k in (v.get("people") or {}) if is_bot_key(k) and _named(v.get("people"), k)})
    return out


def knows(viewer):
    """인물 기록 판의 몸인가(이름을 겪은 만큼만 안다). False = 옛 판(명단 실명이 곧 호칭)."""
    return isinstance(viewer, dict) and viewer.get("people") is not None


def call(viewer, key, real=None, default=None):
    """보는 사람(viewer)이 사람(key)을 부르는 말 — 설계 §1.4. 우선순위:
      자기 자신 → '너'
      인물 기록 판: ① 내 기록 people[key].name(내 lore_note · 시트 씨앗) ② 살펴 안 것 inspected[key].name(MP1 사람 search 의 연결 자리 —
                    p0.5.9 지금은 비어 있다. 내 기록과 다르면 내 기록이 이긴다) ③ '낯선 사람'
      옛 판(인물 기록 꺼짐): 명단 실명(real {char: 실명}) → default(없으면 '낯선 사람')
    NPC('npc:<이름>')는 ID-6 전까지 정의 이름 그대로(지금 관측과 같은 바이트 — 모두에게 보이는 이름)."""
    k = _norm(key)
    if k.startswith("npc:"):
        return k[4:]
    c = char_of(k)
    if c is not None and viewer is not None and str(viewer.get("char")) == c:
        return SELF
    if knows(viewer):
        return _named(viewer["people"], k) or _named(viewer.get("inspected"), k) or STRANGER
    return (real or {}).get(c) or (default if default is not None else STRANGER)


def pick(names, char, default):
    """이미 만든 호칭 사전으로 부르기 — names[char] → 인물 기록 판('?' 칸)이면 그 호칭(낯선 사람) → default(옛 판의 자리별 기본값)."""
    n = names or {}
    return n.get(str(char)) or n.get("?") or default


def call_npc(key, real=None):
    """NPC 두뇌 입력의 호칭(설계 §1.4 call_npc) — NPC 는 모든 모험가의 실명을 안다(길드 등록, DECISIONS 69).
    모험가 → 실명(real {char: 실명 — 이름 없는 시트는 부르는 쪽이 직업을 넣는다}, 그래도 없으면 번호 대신 '모험가') · NPC → 정의 이름(ID-5 전)."""
    k = _norm(key)
    if k.startswith("npc:"):
        return k[4:]
    return (real or {}).get(char_of(k)) or "모험가"


_HANDLE = re.compile(r"(?<![0-9A-Za-z])(?:봇\s*(\d+)|[bB](\d+))(?![0-9A-Za-z])")


def npc_heard(text, real=None):
    """모험가의 말을 NPC 두뇌 입력에 넣을 때 — '봇2'·'b2' 꼴 낱말을 NPC 가 아는 이름으로 바꿔 넣는다(설계 §1.6).
    ID 는 세계 밖의 손잡이라 NPC 두뇌는 그게 누구인지 알 길이 없다(c05 t84·t211 — NPC 가 'b2'·'봇1'을 따라 말했다).
    명단에 없는 번호는 그대로 둔다(누구인지 모르는 것을 지어내지 않는다). 모험가끼리 들은 말은 바꾸지 않는다."""
    if not text or not real:
        return text

    def sub(m):
        c = m.group(1) or m.group(2)
        return real.get(c) or m.group(0)
    return _HANDLE.sub(sub, str(text))


def grave_label(viewer, char, real_label):
    """묘 이름 — 인물 기록 판의 보는 사람에겐 '<호칭>의 묘'(모르면 '누군가의 묘'), 옛 판은 피처 이름(관전 원본) 그대로."""
    if not knows(viewer):
        return real_label
    if char is not None and str(char) == str(viewer.get("char")):
        nm = viewer.get("name") or viewer.get("job") or SOMEONE          # 내 묘(부활 판) — 내 이름은 안다
    else:
        nm = call(viewer, char) if char is not None else SOMEONE
    return "%s의 묘" % (SOMEONE if nm == STRANGER else nm)
