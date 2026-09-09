"""캐릭터 프리셋 저장·복원·API 검증. 임시 폴더만 사용하고 LLM은 호출하지 않는다."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import subprocess
import sys
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import launcher
import sheetkit
from character_presets import PresetStore


SLOT = {"name": "유나", "job": "전사", "sex": "여", "traits": ["신중한"],
        "persona": "친구에게 장난을 잘 친다.", "background": "광산 마을에서 자랐다.",
        "look": {"head": "M1", "body": "B1", "colors": {"hair": "#945C37"},
                 "sprite": "sd-warrior", "hairstyle": "twintails"}}


class PresetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wl_presets_")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "character_presets.json"
        self.store = PresetStore(self.path)

    def test_roundtrip_and_independent_variants(self):
        first = self.store.save(SLOT, "유나 · 양갈래")
        second = self.store.save(SLOT, "유나 · 다른 버전")
        self.assertNotEqual(first["id"], second["id"])
        reopened = PresetStore(self.path)
        restored = reopened.list()[0]["slot"]
        self.assertEqual(restored["persona"], SLOT["persona"])
        self.assertEqual(restored["traits"], SLOT["traits"])
        self.assertEqual(restored["look"]["hairstyle"], "twintails")
        self.assertEqual(restored["look"]["colors"]["hair"], "#945c37")
        self.assertNotIn("goal", restored)
        before = sheetkit.build_party([SLOT])
        self.assertEqual(sheetkit.build_party([restored]), before)
        restored["look"]["hairstyle"] = "long"
        reopened.save(restored, "유나 · 긴 머리", first["id"])
        result = reopened.list()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["slot"]["look"]["hairstyle"], "long")
        self.assertEqual(result[1], second)
        reopened.delete(first["id"])
        self.assertEqual(PresetStore(self.path).list(), [second])

    def test_invalid_and_failed_write_preserve_previous_file(self):
        self.store.save(SLOT)
        previous = self.path.read_bytes()
        for invalid in [None, {**SLOT, "name": ""}, {**SLOT, "traits": [{}]},
                        {**SLOT, "look": {**SLOT["look"], "hairstyle": "missing"}}]:
            with self.assertRaises(ValueError):
                self.store.save(invalid)
            self.assertEqual(self.path.read_bytes(), previous)
        with self.assertRaises(ValueError):
            self.store.save(SLOT, preset_id="missing")
        with patch("character_presets.os.replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.store.save(SLOT)
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.glob(".character-presets-*.tmp")), [])
        self.path.write_text("broken json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.save(SLOT)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken json")

    def test_concurrent_new_saves_are_all_kept(self):
        threads = [threading.Thread(target=self.store.save, args=(SLOT, "버전%d" % i)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        entries = self.store.list()
        self.assertEqual(len(entries), 8)
        self.assertEqual(len({e["id"] for e in entries}), 8)

    def test_api_and_party_save(self):
        folder = self.path.parent
        server = launcher.make_server("127.0.0.1", 0, party_path=str(folder / "party.json"),
                                      state_dir=str(folder / "state"), runs_dir=str(folder / "runs"), brain="dummy")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = "http://127.0.0.1:%d" % server.server_port

        def call(path, body=None):
            request = urllib.request.Request(origin + path, headers={"Content-Type": "application/json"},
                                             data=None if body is None else json.dumps(body).encode("utf-8"))
            try:
                response = urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as e:
                response = e
            with response:
                return response.status, json.loads(response.read())

        self.assertEqual(call("/api/characters"), (200, {"presets": []}))
        status, result = call("/api/characters", {"label": "유나", "slot": SLOT})
        self.assertEqual(status, 200)
        entry = result["preset"]
        self.assertEqual(call("/api/characters")[1]["presets"], [entry])
        self.assertEqual(call("/api/party", {"slots": [entry["slot"]]})[0], 200)
        saved = json.loads((folder / "party.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["1"]["look"]["hairstyle"], "twintails")
        self.assertNotIn("goal", saved["1"])
        self.assertEqual(saved["1"]["persona"].count(SLOT["persona"]), 1)
        self.assertEqual(call("/api/characters", {"slot": {}})[0], 400)
        modified = copy.deepcopy(entry["slot"])
        modified["look"]["hairstyle"] = "long"
        self.assertEqual(call("/api/characters", {"id": entry["id"], "slot": modified})[0], 200)
        self.assertEqual(call("/api/characters")[1]["presets"][0]["slot"], modified)
        self.assertEqual(call("/api/characters/delete", {"id": entry["id"]})[0], 200)
        self.assertEqual(call("/api/characters")[1]["presets"], [])

    @unittest.skipUnless(os.environ.get("WL_BROWSER"), "WL_BROWSER=1일 때 브라우저까지 검증")
    def test_browser_roundtrip(self):
        folder = self.path.parent
        server = launcher.make_server("127.0.0.1", 0, party_path=str(folder / "party.json"),
                                      state_dir=str(folder / "state"), runs_dir=str(folder / "runs"), brain="dummy")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        run = subprocess.run([os.environ.get("WL_NODE", "node"), "verify_character_presets_browser.mjs",
                              "http://127.0.0.1:%d" % server.server_port,
                              "docs/character-presets-preview.png"],
                             cwd=Path(__file__).resolve().parent, capture_output=True,
                             text=True, encoding="utf-8", timeout=90)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        print(run.stdout.strip())


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    if result.wasSuccessful():
        print("ALL PASS — verify_character_presets (캐릭터 프리셋 저장·복원)", flush=True)
    sys.exit(0 if result.wasSuccessful() else 1)
