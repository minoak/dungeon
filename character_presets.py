"""캐릭터 생성 입력을 보관한다. 직업 목표·판에서 쌓인 기억을 새로 만들어 넣지 않는다.

브라우저와 분리한 JSON 저장소: 다음 클라이언트도 같은 슬롯 형식과 API를 쓸 수 있다.
성격 키워드와 자유 서술은 분리해서, 다시 불러올 때 키워드 문장이 중복되지 않게 한다.
"""
import json
import os
import threading
import uuid

import savedata
import sheetkit


def normalize_slot(slot, data=None):
    """기존 시트 검증을 통과한 생성 입력만 저장한다. 수치·자동 목표는 저장 대상이 아니다.
    p0.5.20 욕구 칸 셋(needs·taste·needs_meta — 생성 호출이 채우고 사람이 고친 것)은 시트 검증기를 거친 것만, 있을 때만 남는다
    (없는 옛 슬롯은 생성 입력 7칸 그대로). 부르기(생성 호출)는 저장소가 아니라 론처 처리부가 한다 — 저장소는 담기만 한다."""
    if not isinstance(slot, dict):
        raise ValueError("캐릭터 설정은 객체여야 한다")
    try:
        sheet = sheetkit.build_sheet(slot.get("job"), slot.get("traits") or [],
                                    slot.get("name", ""), slot.get("sex"), slot.get("background"),
                                    data=data, persona_text=slot.get("persona"), look=slot.get("look"),
                                    **{k: slot.get(k) for k in sheetkit.NEED_FIELDS})
    except (TypeError, KeyError) as e:
        raise ValueError("캐릭터 설정 형식이 올바르지 않다") from e
    return {"name": sheet["name"], "sex": sheet["sex"], "job": sheet["job"],
            "traits": sheet["traits"],
            "persona": sheetkit.sanitize_freetext(slot.get("persona"), sheetkit.PERSONA_MAX) or "",
            "background": sheet.get("background", ""), "look": sheet.get("look"),
            **{k: sheet[k] for k in sheetkit.NEED_FIELDS if k in sheet}}


def normalize_label(label, fallback):
    if label is None or label == "":
        return fallback
    if not isinstance(label, str):
        raise ValueError("프리셋 이름은 문자열이어야 한다")
    label = " ".join(label.split())
    if len(label) > 40:
        raise ValueError("프리셋 이름은 40자 이내")
    return label or fallback


class PresetStore:
    """요청마다 디스크에서 읽고, 같은 서버의 동시 저장은 순서대로 처리한다."""
    def __init__(self, path, data=None):
        self.path = os.path.abspath(path)
        self.data = data
        self.lock = threading.Lock()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as e:
            raise ValueError("프리셋 파일을 읽을 수 없다. JSON 형식을 확인해 주세요.") from e
        doc = savedata.upgrade("presets", doc)   # p0.5.1 이관 틀 — 옛 판은 현재 판으로 올려 읽는다
        if not isinstance(doc, dict) or doc.get("version") != 1 or not isinstance(doc.get("presets"), list):
            raise ValueError("지원하지 않는 프리셋 파일 형식이다")
        entries, ids = [], set()
        for entry in doc["presets"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"] or entry["id"] in ids:
                raise ValueError("프리셋 id가 없거나 중복됐다")
            slot = normalize_slot(entry.get("slot"), self.data)
            entries.append({"id": entry["id"], "label": normalize_label(entry.get("label"), slot["name"]), "slot": slot})
            ids.add(entry["id"])
        return entries

    def _write(self, entries):
        # 쓰기가 끝난 파일로 교체한다. 저장 도중 실패해도 이전 프리셋 파일이 남는다.
        # p0.5.1: 저장소 공용 저장(덮기 전 .v<n>.bak · 판 번호 · 원자적 교체). 백업을 못 하면 BackupError(OSError) — 덮지 않는다.
        savedata.save("presets", self.path, {"version": 1, "presets": entries}, indent=2)

    def list(self):
        with self.lock:
            return self._read()

    def save(self, slot, label=None, preset_id=None):
        slot = normalize_slot(slot, self.data)
        label = normalize_label(label, slot["name"])
        if preset_id is not None and (not isinstance(preset_id, str) or not preset_id):
            raise ValueError("덮어쓸 프리셋을 선택해 주세요")
        with self.lock:
            entries = self._read()
            if preset_id is None:
                entry = {"id": uuid.uuid4().hex, "label": label, "slot": slot}
                entries.append(entry)
            else:
                entry = next((e for e in entries if e["id"] == preset_id), None)
                if entry is None:
                    raise ValueError("프리셋이 없다. 목록을 새로 불러와 주세요.")
                entry.update(label=label, slot=slot)
            self._write(entries)
            return entry

    def set_needs(self, preset_id, fields, of):
        """p0.5.20 출발 때 정한 욕구를 옛 저장본에 한 번 적어 둔다(다음 출발에 다시 부르지 않게 — 판마다 같은 무게).
        그 저장본이 아직 정한 욕구가 없고(dummy 결과는 없는 것) 지금 글이 정할 때의 글(of)과 같을 때만. 적었으면 True."""
        import need_gen                                  # 지연 import — 저장소는 욕구 모듈 없이도 읽는다
        with self.lock:
            entries = self._read()
            entry = next((e for e in entries if e["id"] == preset_id), None)
            if entry is None:
                return False
            sheet = need_gen.sheet_of_slot(entry["slot"], self.data)
            if need_gen.has(sheet) or need_gen.sheet_hash(sheet) != of:
                return False
            entry["slot"] = normalize_slot({**entry["slot"], **fields}, self.data)
            self._write(entries)
            return True

    def delete(self, preset_id):
        with self.lock:
            entries = self._read()
            remaining = [e for e in entries if e["id"] != preset_id]
            if len(remaining) == len(entries):
                raise ValueError("삭제할 프리셋이 없다")
            self._write(remaining)
