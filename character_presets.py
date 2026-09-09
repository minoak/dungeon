"""캐릭터 생성 입력을 보관한다. 직업 목표·판에서 쌓인 기억을 새로 만들어 넣지 않는다.

브라우저와 분리한 JSON 저장소: 다음 클라이언트도 같은 슬롯 형식과 API를 쓸 수 있다.
성격 키워드와 자유 서술은 분리해서, 다시 불러올 때 키워드 문장이 중복되지 않게 한다.
"""
import json
import os
import tempfile
import threading
import uuid

import sheetkit


def normalize_slot(slot, data=None):
    """기존 시트 검증을 통과한 생성 입력만 저장한다. 수치·자동 목표는 저장 대상이 아니다."""
    if not isinstance(slot, dict):
        raise ValueError("캐릭터 설정은 객체여야 한다")
    try:
        sheet = sheetkit.build_sheet(slot.get("job"), slot.get("traits") or [],
                                    slot.get("name", ""), slot.get("sex"), slot.get("background"),
                                    data=data, persona_text=slot.get("persona"), look=slot.get("look"))
    except (TypeError, KeyError) as e:
        raise ValueError("캐릭터 설정 형식이 올바르지 않다") from e
    return {"name": sheet["name"], "sex": sheet["sex"], "job": sheet["job"],
            "traits": sheet["traits"],
            "persona": sheetkit.sanitize_freetext(slot.get("persona"), sheetkit.PERSONA_MAX) or "",
            "background": sheet.get("background", ""), "look": sheet.get("look")}


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
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        # 쓰기가 끝난 파일로 교체한다. 저장 도중 실패해도 이전 프리셋 파일이 남는다.
        fd, temporary = tempfile.mkstemp(prefix=".character-presets-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"version": 1, "presets": entries}, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

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

    def delete(self, preset_id):
        with self.lock:
            entries = self._read()
            remaining = [e for e in entries if e["id"] != preset_id]
            if len(remaining) == len(entries):
                raise ValueError("삭제할 프리셋이 없다")
            self._write(remaining)
