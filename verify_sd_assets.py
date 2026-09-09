"""SD 외형의 저장·러너 전달·게임 판정 분리를 검증한다. LLM 0콜, 임시 폴더 사용.

--demo를 붙이면 검증에서 생성한 짧은 판을 에셋 검토 화면용으로 보존한다.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import sheetkit

ROOT = Path(__file__).resolve().parent
catalog = sheetkit.load_looks()
assert set(catalog["illustrations"]) == {"sd-warrior", "sd-archer", "sd-rogue"}
base = sheetkit.sanitize_look({"head": "M1", "body": "B1"})
assert "sprite" not in base  # 예전 저장 형식을 임의로 새 외형으로 바꾸지 않는다.
for sprite, info in catalog["illustrations"].items():
    assert len(info["hairstyles"]) == (5 if sprite == "sd-warrior" else 3)
    assert "default" in info["hairstyles"]
    assert "hairstyle" not in sheetkit.sanitize_look({**base, "sprite": sprite})
    for hairstyle in info["hairstyles"]:
        assert sheetkit.sanitize_look({**base, "sprite": sprite, "hairstyle": hairstyle})["hairstyle"] == hairstyle
for bad in ["missing", "../warrior", [], {}]:
    try:
        sheetkit.sanitize_look({**base, "sprite": bad})
    except ValueError:
        pass
    else:
        raise AssertionError("미등재 외형이 통과했다")
for wrong in [{**base, "hairstyle": "default"},
              {**base, "sprite": "sd-warrior", "hairstyle": "bob"},
              {**base, "sprite": "sd-archer", "hairstyle": []},
              {**base, "sprite": "sd-rogue", "hairstyle": {}}]:
    try:
        sheetkit.sanitize_look(wrong)
    except ValueError:
        pass
    else:
        raise AssertionError("다른 외형의 머리 또는 잘못된 헤어 값이 통과했다")

with tempfile.TemporaryDirectory(prefix="wl_sd_") as tmp:
    tmp = Path(tmp)
    party = {}
    for i, (sprite, job, sex) in enumerate([
        ("sd-warrior", "전사", "남"), ("sd-archer", "궁수", "여"), ("sd-rogue", "도적", "여")
    ], 1):
        selected = {"sd-warrior": "long", "sd-archer": "braid", "sd-rogue": "ponytail"}[sprite]
        look = sheetkit.sanitize_look({**base, "sprite": sprite, "hairstyle": selected})
        assert look["sprite"] == sprite
        party[str(i)] = sheetkit.build_sheet(job, ["신중한"], job, sex, look=look)
    env = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
    env.update(DUNGEON_GM="0", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_TURNS="24",
               DUNGEON_W="32", DUNGEON_H="16", DUNGEON_SEED="37", DUNGEON_MONSTERS="1",
               DUNGEON_TRAPS="1", DUNGEON_LURKERS="0", DUNGEON_DEPTHS="1",
               DUNGEON_BESTIARY_FILE="", PYTHONIOENCODING="utf-8")
    streams = []
    for mode in ["hair", "sd", "parts"]:
        content = copy.deepcopy(party)
        if mode != "hair":
            for member in content.values():
                del member["look"]["hairstyle"]
        if mode == "parts":
            for member in content.values():
                del member["look"]["sprite"]
        party_path = tmp / (mode + ".json")
        party_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        state = tmp / mode
        run_env = {**env, "DUNGEON_PARTY_FILE": str(party_path), "DUNGEON_STATE_DIR": str(state)}
        run = subprocess.run([sys.executable, "-c", "import show_runner; show_runner.STEP_DELAY=0; show_runner.main()"],
                             cwd=ROOT, env=run_env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert run.returncode == 0, run.stderr[-2000:]
        streams.append((state / "stream.jsonl").read_text(encoding="utf-8"))
    hair, sd, parts = [[json.loads(line) for line in raw.splitlines()] for raw in streams]
    assert {m["look"]["sprite"] for m in sd[0]["party"]} == set(catalog["illustrations"])
    assert [m["look"]["hairstyle"] for m in hair[0]["party"]] == ["long", "braid", "ponytail"]
    assert all("hairstyle" not in m["look"] for m in sd[0]["party"])
    fields = ["char", "x", "y", "hp", "alive", "won", "bag", "job", "order"]
    def physical(records):
        return [[{k: bot.get(k) for k in fields} for bot in record["bots"]]
                for record in records if record["kind"] == "tick"]
    assert physical(hair) and physical(hair) == physical(sd) == physical(parts), "외형이 게임 진행을 바꿨다"
    if "--demo" in sys.argv:
        (ROOT / "art/sprites-v4/demo-hairstyles.jsonl").write_text(streams[0], encoding="utf-8")
print("PASS: SD 외형 3종·헤어 포함 11종 저장·run_meta 전달, 잘못된 조합 거부, 기존 외형 보존, 머리 변경 전후 게임 진행 일치")
