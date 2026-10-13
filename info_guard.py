# -*- coding: utf-8 -*-
"""정보 보호 공통 인프라(master_plan §6, p0.5.4) — 공개 투영 · audit 표식 · 폴백 축소 · 불투명 ID.

원칙(§6.1):
  1. 모델 프롬프트에 들어가는 입력은 **공개 투영을 거친 사본**이다. 관전 스트림·도감 발급기·run_summary 는 원본(audit 포함)을 읽는다.
  2. 숨은 원인과 판정 실패는 공개 결과가 같다(행동자가 보는 글자까지).
  3. 실제로 보이거나 들리는 사건으로 이어진 변화는 숨기지 않는다 — 금지는 "코드가 속사정을 문장으로 만들어 주는 것".
  4. 번호·순서가 정보가 되지 않게 한다(수신자별 사건 번호 — social_reactions, 불투명 ID — 아래 opaque_id).

audit(§6.2 A): 결과 dict 의 `audit` 칸에 **상대에게서 나온 것 전부**(상대 굴림, 상대 수치로 만든 DC, 알아챘는지, 비공개 사건 id, 숨은 원인)를 둔다.
  judge.py 의 판정 함수가 audit 값을 secret() 으로 표식해 내보낸다 — 누가 그 값을 다른 칸에 옮겨 적어도(복사·별칭·dict(audit))
  public() 이 걸러 낸다. ⚠️ 표식은 값 자체에 붙는다: 산술로 새 값을 만들면(roll + 1) 표식이 사라진다 — 그런 값은 처음부터 audit 에 둘 것.
  표식 값은 int·float·str 의 하위 클래스라 JSON·피클·deepcopy 에서 보통 값처럼 굴고(관전 스트림 그대로), bool 은 1/0 으로 남는다.

public(result, viewer) — 결과 하나를 "그 사람이 실제로 볼 수 있는 것"만 남긴 사본으로(§6.2 B). 원본은 건드리지 않는다.
  걷어 내는 것: ① 어느 깊이든 `audit` 칸 ② audit 표식 값(어디로 복사됐든)과 audit 안 객체를 가리키는 다른 칸
  ③ social_event_id — 원정 전체 일련번호(§6.3-4). 받은 사람의 번호는 social_reactions 가 따로 매긴다
  ④ 사람 대상 판정의 굴림·문턱(PERSON_ROLL_KEYS) — 상대 민첩·갑옷으로 만든 AC, 상대의 내성 굴림, 자기 주사위 눈(합계와 성패로 DC 를 좁힌다).
     몹 대상 판정(명중 굴림의 AC 등)은 지금 그대로 둔다 — 범위는 '사람 대상'(class_design §8.2 A).
  ⑤ (p0.5.9 신원 ID-1) viewer 가 인물 기록 판의 몸(viewer['people'] 이 있다)이면 사람을 가리키는 **실명 문자열 칸** — 사람 대상의
     `target`(공격 결과의 상대 이름) · 사람이 친 `by`(by_kind 'bot') · 교대의 `with` · 길막힘 동료의 `allies[].name` · 묘 `grave.name`.
     내부 열쇠(target_id · by_id · with_char · allies[].char)는 그대로 남는다 — 호칭은 그릴 때 보는 사람이 붙인다(identity.call).
     **저장용 정제**일 뿐 ID 를 바꾸지 않는다(설계 §2.3-3). 옛 판(인물 기록이 꺼진 몸)은 사본 꼴이 옛 그대로다.
  viewer(보는 사람)의 가시성(perceives, 4a)은 아직 쓰지 않는다.
LLM 0콜 · 판정 rng 무접촉 · 엔진 무의존(dungeon_gm 을 import 하지 않는다 — 엔진이 이 모듈을 쓴다).
"""
import copy
import hashlib
import json

import identity

AUDIT = "audit"
DROP_KEYS = ("social_event_id",)
PERSON_ROLL_KEYS = ("roll", "mod", "total", "ac", "combat_roll", "skill_roll", "skill_dc")   # CA.attack_actor · SK.execute 의 사람 대상 굴림
EFFECT_ROLL_KEYS = ("save",)                                                                # SK.execute effects[] 의 대상 내성 굴림


class _SecretInt(int):
    __slots__ = ()


class _SecretFloat(float):
    __slots__ = ()


class _SecretStr(str):
    __slots__ = ()


_SECRET = (_SecretInt, _SecretFloat, _SecretStr)


def secret(v):
    """audit 값 표식(깊이 전부). dict·list·tuple 은 새 그릇에, 잎(int·float·str·bool)은 표식 하위 클래스로. 그 밖(None 등)은 그대로."""
    if isinstance(v, _SECRET) or v is None:
        return v
    if isinstance(v, dict):
        return {k: secret(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [secret(x) for x in v]
    if isinstance(v, bool):
        return _SecretInt(int(v))
    if isinstance(v, int):
        return _SecretInt(v)
    if isinstance(v, float):
        return _SecretFloat(v)
    if isinstance(v, str):
        return _SecretStr(v)
    return v


def is_secret(v):
    return isinstance(v, _SECRET)


def add_audit(result, key, value):
    """결과 dict 의 audit 칸에 한 항목(표식을 붙여) — 판정 함수 결과의 'audit' 를 행동 결과로 옮길 때."""
    result.setdefault(AUDIT, {})[key] = secret(value)
    return result


def _audit_ids(v, out):
    """audit 안의 그릇(dict·list) id 전부 — 같은 객체가 다른 칸에 별칭으로 걸려 있으면 그것도 걷는다."""
    if isinstance(v, (dict, list)) or (isinstance(v, tuple) and v):    # 빈 튜플은 하나뿐인 객체라 id 로 가리면 남의 () 까지 걷는다
        out.add(id(v))
        for x in (v.values() if isinstance(v, dict) else v):
            _audit_ids(x, out)
    return out


def _collect(v, out):
    if isinstance(v, dict):
        for k, x in v.items():
            if k == AUDIT:
                _audit_ids(x, out)
            else:
                _collect(x, out)
    elif isinstance(v, (list, tuple)):
        for x in v:
            _collect(x, out)
    return out


def _clean(v, hidden):
    """audit 칸·표식 값·audit 그릇 별칭을 뺀 깊은 사본(dict 는 키 순서 그대로)."""
    if isinstance(v, dict):
        return {k: _clean(x, hidden) for k, x in v.items()
                if k != AUDIT and not is_secret(x) and id(x) not in hidden}
    if isinstance(v, list):
        return [_clean(x, hidden) for x in v if not is_secret(x) and id(x) not in hidden]
    if isinstance(v, tuple):
        return tuple(_clean(x, hidden) for x in v if not is_secret(x) and id(x) not in hidden)
    return copy.deepcopy(v)


def is_person_ref(ref):
    """'b<번호>' — 사람(모험가) 대상 ID. 판정은 identity 한 곳(설계 X6)."""
    return identity.is_bot_key(ref)


def _drop_person_names(out):
    """머리글 ⑤ — 사람을 가리키는 실명 문자열 칸만 걷는다(열쇠 칸은 그대로). out 은 이미 깊은 사본."""
    if out.get("by_kind") == "bot":
        out.pop("by", None)
    if identity.is_person_key(out.get("target_id")) and not identity.is_person_key(out.get("target")):
        out.pop("target", None)
    if "with_char" in out:
        out.pop("with", None)
    if isinstance(out.get("allies"), list):
        out["allies"] = [{k: v for k, v in a.items() if k != "name"} if isinstance(a, dict) and "char" in a else a
                         for a in out["allies"]]
    if isinstance(out.get("grave"), dict):
        out["grave"].pop("name", None)
    return out


def public(result, viewer=None):
    """결과 → viewer 가 볼 수 있는 사본(머리글 ①~⑤). dict 가 아니면 그대로."""
    if not isinstance(result, dict):
        return result
    out = _clean(result, _collect(result, set()))
    for k in DROP_KEYS:
        out.pop(k, None)
    if is_person_ref(result.get("target_id")) or is_person_ref(result.get("target")):
        for k in PERSON_ROLL_KEYS:
            out.pop(k, None)
        for e in out.get("effects") or []:
            if isinstance(e, dict):
                for k in EFFECT_ROLL_KEYS:
                    e.pop(k, None)
    if identity.knows(viewer):
        _drop_person_names(out)
    return out


def fallback_view(rec):
    """문장 렌더러가 모르는 결과의 최소 꼴(§6.3-2) — {type, target, status} 만. 나머지 칸(수치·원인)은 싣지 않는다.
    status = 조합형 공통 결과(resolution.status — success/failed/no_effect)가 있으면 그것, 없으면 result."""
    rec = rec if isinstance(rec, dict) else {}
    status = (rec.get("resolution") or {}).get("status") if isinstance(rec.get("resolution"), dict) else None
    view = {"type": rec.get("type"), "target": rec.get("target"), "status": status or rec.get("result")}
    return {k: v for k, v in view.items() if v is not None and not is_secret(v) and isinstance(v, (str, int, float))}


def fallback_json(rec):
    return json.dumps(fallback_view(rec), ensure_ascii=False)


def opaque_id(prefix, *parts, taken=(), width=4):
    """실행 중 생기는 엔티티의 ID(§6.2 E) — 전역 순번 대신 (세계 시드·층·자리·틱 …) 해시. 순서가 정보가 되지 않는다.
    같은 parts → 같은 ID(결정론, rng 무접촉). 해시 부분이 숫자뿐이면 건너뛴다(옛 'f12' 같은 순번 ID 와 섞이지 않게).
    이미 쓰인 ID(taken)와 겹치면 한 자씩 늘린다. 쓰임은 3단계(놓인 물건)·13단계(시체)."""
    h = hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()
    for w in range(width, len(h) + 1):
        tail = h[:w]
        oid = prefix + tail
        if not tail.isdigit() and oid not in taken:
            return oid
    raise ValueError("opaque_id: 빈 ID 를 찾지 못했다")
