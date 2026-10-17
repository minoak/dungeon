# -*- coding: utf-8 -*-
"""저장 데이터 이관 틀(p0.5.1, 2026-10-11 — 라이브 서비스식 패치의 전제 '저장 데이터 호환').

패치가 저장 파일의 꼴을 바꿀 때(정신 능력치·소지품 칸 확장 같은) 옛 파일을 버리지 않고 올려 읽는다.
  · 파일마다 종류(kind)와 현재 판(CURRENT[kind])이 있다. 저장할 때 `_schema_version` 을 붙이고(stamp),
    읽을 때 그 칸이 없거나(= 0판, p0.5.1 이전에 쓰인 파일) 낮으면 이관 함수를 한 판씩 거쳐 올린다(upgrade).
  · 이관 함수 = MIGRATIONS[kind][n] : n판 문서(dict) → n+1판 문서. 판 번호는 upgrade 가 붙인다(함수는 내용만 바꾼다).
    새 패치가 꼴을 바꾸면 CURRENT[kind] 를 한 칸 올리고 함수 하나를 더한다 — 예) 어떤 칸을 시트마다 채워 넣어야 하는 패치면 party·presets 에 1→2.
    (p0.5.3 정신·숙련은 해당 없음: 시트에 기본값을 쓰지 않고 스폰이 직업표에서 읽는다 — 옛 파일이 그대로 돈다, 판을 올리지 않았다)
  · 칸 이름이 `_` 로 시작하는 이유: 파티 시트(party*.json)·도감 원장(bestiary.json)은 최상위 키가 캐릭터 칸이고 `_` 로 시작하는 키만
    메타로 건너뛴다 — 밑줄 없는 이름이면 패치를 되돌린 옛 코드(v0.5.0)가 파티 파일을 통째로 거부한다(되돌리기 = 패치 단위 커밋/태그).
    파일 고유의 `version`(캠페인·프리셋·스냅샷)은 그대로 둔다 — 옛 코드가 그 값을 보고 읽는다.
  · 저장은 저장소 다섯이 모두 save() 하나로 한다: 덮기 전 백업 → 판 번호 → 원자적 교체(같은 폴더 임시 파일에 다 쓴 뒤 os.replace).
    쓰는 도중 실패해도 원래 파일은 그대로다(p0.5.1b — 리뷰: 파티 파일은 그 전까지 제자리에서 잘라 썼다).
  · 백업: 덮어쓰기 직전에 디스크의 파일이 현재 판이 아니면(옛 판 또는 더 새 판) `<파일>.v<n>.bak` 을 한 번 남긴다 — 읽은 바이트 그대로,
    백업도 임시 파일에 다 쓴 뒤 교체로 확정한다(반쪽짜리 .bak 이 그 이름으로 생기지 않는다). 온전한 백업(JSON 객체 · 같은 판)이 이미 있으면 그대로
    (가장 먼저 남긴 원본을 지킨다), 깨진 .bak 은 백업으로 치지 않고 새로 만든다. **백업을 못 하면 BackupError — 아무것도 덮지 않는다**
    (OSError 의 한 갈래라 저장소의 기존 '쓰기 실패' 처리가 그대로 받는다). 읽기만 하는 파일(저장소의 party.json 등)에는 백업이 생기지 않는다.
  · 더 새 판(되돌린 코드가 새 패치의 파일을 읽음)은 내용을 손대지 않고 돌려준다 — 모르는 칸은 저장소가 버릴 수 있으므로 덮어쓰기 전 백업이 지킨다.
대상과 빠진 것(p0.5.1 목록 — 새 저장 파일이 생기면 여기에 종류를 더한다):
  party     party_custom.json(론처가 쓰는 내 파티 · p0.5.22 판 2) · party*.json(저장소 기본 파티, 읽기만)   — sheetkit.write_party / show_runner.load_party
  presets   character_presets.json(저장 캐릭터 · p0.5.20 판 2 — 슬롯의 욕구 칸 · p0.5.22 판 3 — 욕구 칸을 걷는다 · p0.5.24 판 4 — 미식가↔소박한 짝) — character_presets.PresetStore
  campaign  campaign.json(저장 캐릭터별 원정 기록, 판 기록의 투영)                             — campaign.Book
  bestiary  bestiary.json(도감 원장 — 죽어도 남는 지식)                                        — bestiary.Issuer
  account   accounts/<id>/account.json(공개 서버 계정 — 열쇠 지문·별명)                       — accounts.Accounts
  ⚠️이관을 거치지 않는 읽기: tools/run_notes.py ledger_notes 가 bestiary.json 을 직접 읽는다 — 도감 꼴을 바꾸는 패치에서 upgrade 를 거치게 할 것(후속).
  빠짐: state/snapshot.pkl·snapshot.json(멈춘 판의 몸 — 피클이라 이 틀이 아니라 snapshot.py 가 제 판 번호(state_version)와 이관 체인을 쓴다, p0.5.3) ·
       run_opts.json(그 판을 시작한 옵션 — 론처가 이어가기에 그대로 쓴다) ·
       house_usage.json(서버 하루 판 수, 날마다 새로) · oracle/stop/brain_pause/brain_retry.json(러너와 주고받는 1회용 쪽지) ·
       판 기록(stream.jsonl — run_meta.v, additive 규칙).
LLM 0콜 · 엔진 무접촉 · 순수 파일.
"""
import json
import os
import tempfile
import time

KEY = "_schema_version"

CURRENT = {"party": 2, "presets": 4, "campaign": 1, "bestiary": 1, "account": 1}


def _stamp_only(doc):
    """0→1(p0.5.1): 꼴은 그대로, 판 번호만 붙는다(upgrade 가 붙인다)."""
    return doc


def _p1_needs(doc):
    """presets 1→2(p0.5.20 욕구 생성 호출): 슬롯에 needs·taste·needs_meta 칸이 생겼다(있을 때만). 옛 슬롯은 칸이 없다 = 아직 정하지 않았다 —
    채워 넣을 것이 없어 내용은 그대로다(저장·출발 때 생성 호출이 채운다). 판을 올리는 까닭은 되돌린 코드(v0.5.19)가 이 파일을 덮기 전에
    .v2.bak 을 남기게 하려는 것이다(옛 normalize_slot 은 모르는 칸을 버린다 — 정한 욕구·사람이 고친 칸을 잃지 않게)."""
    return doc


GONE_NEED_KEYS = ("needs", "needs_meta")     # p0.5.22 거둔 칸 — 욕구 무게(생성 호출 0.5.20~21)는 이제 특성이 정한다. 입맛(taste)은 남는다


def _drop_needs(sheet):
    return {k: v for k, v in sheet.items() if k not in GONE_NEED_KEYS} if isinstance(sheet, dict) else sheet


def _party_traits(doc):
    """party 1→2(p0.5.22 특성): 시트의 needs·needs_meta 칸을 걷는다(욕구 무게는 특성이 정한다 · taste 는 그대로). traits 칸(옛 성격 키워드)은
    그대로 특성 이름으로 맞는다 — 바꿀 것이 없다. 판을 막지 않는다(옛 칸이 남아 있어도 러너는 읽지 않는다 — 판 번호는 되돌린 코드의 백업용)."""
    return {k: (v if str(k).startswith("_") else _drop_needs(v)) for k, v in doc.items()}


def _opposites():
    import sheetkit                          # 지연 import — sheetkit 이 이 모듈을 import 한다
    return sheetkit.load_traits().get("opposites") or {}


def _first_of_pairs(slot, opp):
    """반대 짝을 둘 다 고른 슬롯 → 먼저 고른 쪽만 남긴다(나머지 순서 그대로). traits 가 목록이 아니면 그대로."""
    tr = slot.get("traits")
    if not isinstance(tr, list):
        return slot
    keep = []
    for t in tr:
        if not (isinstance(t, str) and opp.get(t) in keep):
            keep.append(t)
    return {**slot, "traits": keep}


def _each_slot(doc, fn):
    """presets 문서의 슬롯마다 fn(slot) — 꼴이 다른 항목·presets 가 목록이 아닌 문서는 그대로."""
    if not isinstance(doc.get("presets"), list):
        return doc
    out = []
    for e in doc["presets"]:
        if isinstance(e, dict) and isinstance(e.get("slot"), dict):
            e = {**e, "slot": fn(e["slot"])}
        out.append(e)
    return {**doc, "presets": out}


def _p2_traits(doc):
    """presets 2→3(p0.5.22 특성): 슬롯의 needs·needs_meta 를 걷는다(taste 는 그대로). traits 의 옛 키워드는 그대로 특성 이름이다.
    반대 짝(수다스러운 ↔ 과묵한 등 — 0.5.22 부터 같이 못 고른다)을 둘 다 고른 옛 슬롯은 먼저 고른 쪽만 남긴다 — 그대로 두면 저장소의
    검증(normalize_slot)이 그 슬롯을 거절해 저장 캐릭터 목록 전체를 못 읽는다. 반대 짝 표는 특성 저장소(sheetkit.load_traits — 지연 import)."""
    opp = _opposites()
    return _each_slot(doc, lambda s: _first_of_pairs(_drop_needs(s), opp))


def _p3_pairs(doc):
    """presets 3→4(p0.5.24 미식가 ↔ 소박한 = 반대 짝): 0.5.22~23 에서 둘을 같이 골라 둔 슬롯은 2→3 과 같은 규칙으로 먼저 고른 쪽만 남긴다
    (그대로 두면 저장소의 검증이 그 슬롯을 거절해 목록 전체를 못 읽는다). 표는 지금 특성 저장소 — 다른 짝도 같은 규칙(저장소가 막아 온 짝이라 보통 바꿀 것이 없다)."""
    opp = _opposites()
    return _each_slot(doc, lambda s: _first_of_pairs(s, opp))


MIGRATIONS = {kind: {0: _stamp_only} for kind in CURRENT}
MIGRATIONS["presets"][1] = _p1_needs
MIGRATIONS["presets"][2] = _p2_traits
MIGRATIONS["presets"][3] = _p3_pairs
MIGRATIONS["party"][1] = _party_traits


def version_of(doc):
    """문서의 판 번호 — 칸이 없거나 이상하면 0."""
    v = doc.get(KEY, 0) if isinstance(doc, dict) else 0
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def upgrade(kind, doc):
    """읽은 문서 → 현재 판. 옛 판이면 이관 함수를 한 판씩, 현재·더 새 판·dict 아님은 그대로."""
    if not isinstance(doc, dict):
        return doc
    v, target = version_of(doc), CURRENT[kind]
    while v < target:
        doc = MIGRATIONS[kind][v](dict(doc))
        v += 1
        doc[KEY] = v
    return doc


def stamp(kind, doc):
    """저장 직전 — 현재 판 번호를 맨 앞에 붙인 새 dict(원본은 그대로)."""
    return {KEY: CURRENT[kind], **{k: v for k, v in doc.items() if k != KEY}}


class BackupError(OSError):
    """덮기 전 백업을 못 했다 — 저장을 멈춘다(원래 파일은 그대로)."""


def _replace(tmp, dst):
    for i in range(20):                       # Windows: 방금 쓴 파일을 색인기·백신이 잠깐 잡으면 replace 가 WinError 5 — 짧게 물러섰다 재시도(bestiary.save 선례)
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05 * (i + 1))


def write_atomic(path, data):
    """bytes 를 같은 폴더의 임시 파일에 다 쓴 뒤 교체한다. 도중에 실패하면 원래 파일은 그대로, 임시 파일은 지운다."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        _replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _intact_backup(bak, v):
    """이미 있는 백업이 온전한가 — JSON 객체이고 판 번호가 같아야 백업으로 친다(잘린·깨진 .bak 은 아니다)."""
    try:
        with open(bak, "rb") as f:
            doc = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and version_of(doc) == v


def backup_before_write(kind, path):
    """덮어쓰기 직전: 디스크의 파일이 현재 판이 아니면 `<path>.v<n>.bak` 을 남긴다. 반환 = 백업 경로(안 했으면 None).
    없는 파일·깨진 JSON 은 건너뛴다(판을 알 수 없다 — 깨진 파일의 대피는 저장소 몫, .corrupt). 있는데 못 읽거나 백업을 못 쓰면 BackupError."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise BackupError("저장 파일을 읽지 못해 덮기 전 백업을 할 수 없다: %s" % e) from e
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError:
        return None
    v = version_of(doc)
    if not isinstance(doc, dict) or v == CURRENT[kind]:
        return None
    bak = "%s.v%d.bak" % (path, v)
    if _intact_backup(bak, v):
        return None
    try:
        write_atomic(bak, data)               # 판을 가른 그 바이트 그대로 — 다 쓴 뒤에만 .bak 이름이 생긴다
    except OSError as e:
        raise BackupError("덮기 전 백업(%s)을 만들지 못했다: %s" % (os.path.basename(bak), e)) from e
    return bak


def save(kind, path, doc, indent=1):
    """저장소 공용 저장 — 덮기 전 백업 → 판 번호(stamp) → 원자적 교체. 백업을 못 하면 BackupError 가 나고 아무것도 덮지 않는다.
    UTF-8 · LF · 끝 줄바꿈 하나."""
    backup_before_write(kind, path)
    write_atomic(path, (json.dumps(stamp(kind, doc), ensure_ascii=False, indent=indent) + "\n").encode("utf-8"))
