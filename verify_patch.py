# -*- coding: utf-8 -*-
"""패치 운영의 전제(p0.5.1, 2026-10-11) 헤들리스 검증 — 89번째 게이트. LLM 0콜(러너는 dummy 두뇌).
게이트:
  ① 버전 단일 원본: VERSION 한 줄 = buildinfo.GAME_VERSION(점 세 칸 숫자) · 패치 노트에 같은 버전의 절
  ② 이관 틀(순수): 등록부 완결(종류마다 0..현재-1 함수) · 0판(칸 없음)·이상한 칸 → 현재 판, 내용·원본 불변 · 현재·더 새 판·dict 아님은 그대로 ·
     stamp(맨 앞·원본 불변) · 체인 순서(시험 종류 0→1→2→3, 함수가 받는 판 번호)
  ③ 덮기 전 백업: 옛 판 → .v0.bak(원본 바이트) · 두 번째는 건너뜀(첫 원본 유지) · 현재 판·없는 파일·깨진 파일은 안 함 · 더 새 판 → .v9.bak
  ④ 저장소 다섯(옛 파일 읽기 → 판 번호 붙여 저장 → 백업): presets · party(러너 load_party·론처 write_party) · campaign · bestiary · account ·
     v0.5.0 코드가 읽는 조건(프리셋/캠페인 version 1, 파티의 '_' 아닌 키 = 캐릭터 칸)이 그대로 · 계정 공개 dict 에 판 번호 없음 · 더 새 판 파일은 백업 뒤 덮음
  ⑤ 판 기록 메타(러너 dummy 판): run_meta 에 game_version · git(git describe 와 같다, 못 물으면 없음) · prompts{경로: 디스크 바이트의 LF 정규화
     SHA-256 앞 12자} — 판의 행동 방식에 맞는 지침 파일(조합형 판은 행동 말 폴더 prompts/actions/ 도 — p0.5.6) · 더미 판은 model 없음(두뇌별 모델 이름은 따로) · 두 번 돌려도 같은 메타(started 제외) ·
     **LLM 에 간 글 어디에도 버전·git·지문이 없다**
  ⑥ 지문 규칙(임시 루트): CRLF·LF 같은 지문 · 내용·폴더 안 파일 이름이 바뀌면 지문이 바뀐다 · 없는 파일은 빠진다
  ⑦ 옛 판 기록 읽기: 필드 없는 옛 스트림(runs/ 저장소 판)과 새 스트림을 같은 소비자(campaign.project · run_summary.replay · bestiary 발급기)가 읽는다
  ⑧ 실패 주입(p0.5.1b 리뷰 — 전부 임시 폴더): 백업 실패 → 저장소 다섯 모두 BackupError·원본 그대로·찌꺼기 없음 · 백업 뒤 본 교체 실패 → 원본 그대로·
     .bak 온전 · 쓰는 도중 실패(절반 쓰고 디스크 가득) → 파티 파일 그대로(옛 결함) · 잘린·판 다른 .bak 은 무시하고 새로 · 못 읽는 파일 → BackupError ·
     판 도중 도감 백업 실패 → 판은 끝까지·경고 한 번·원장 그대로
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_patch_")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_SEED="11",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0", DUNGEON_DEPTHS="1",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_STEP_DELAY="0",
                  DUNGEON_PARTY_FILE=os.path.join(TMP, "none.json"),   # 없는 파일 → 내장 2인(경고는 아래에서 삼킨다)
                  DUNGEON_STATE_DIR=os.path.join(TMP, "state"))
for k in ("DUNGEON_RESUME", "DUNGEON_RUNS_DIR", "DUNGEON_STREAM_OBS", "DUNGEON_TOWN", "DUNGEON_BOSS", "DUNGEON_START",
          "DUNGEON_MODEL_HAIKU", "DUNGEON_GEMINI_MODEL"):
    os.environ.pop(k, None)
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"

import brains                                        # noqa: E402
import buildinfo                                     # noqa: E402
import savedata                                      # noqa: E402

SENT = []                                            # LLM 에 간 글 전부(⑤ — 메타가 섞이지 않았나)


def _capture(prompt, model="haiku"):
    SENT.append(prompt)
    return ""                                        # 빈 응답 → dummy 폴백(결정론)


brains._call_claude = _capture
import accounts                                      # noqa: E402
import bestiary                                      # noqa: E402
import campaign                                      # noqa: E402
import run_summary                                   # noqa: E402
import sheetkit                                      # noqa: E402
import show_runner                                   # noqa: E402
from brain_config import model_id                    # noqa: E402
from character_presets import PresetStore            # noqa: E402

show_runner.STEP_DELAY = 0
fails = []


def check(name, ok, detail=""):
    print(("  ok  " if ok else "  FAIL") + " " + name + (("  — " + str(detail)) if detail and not ok else ""))
    if not ok:
        fails.append(name)


def jdump(path, doc):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def jload(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def raw(path):
    """파일 바이트 — 없으면 None(백업이 안 생긴 경우도 예외가 아니라 FAIL 로 말하게)."""
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


K = savedata.KEY

print("── ① 버전 단일 원본")
with io.open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
    vtxt = f.read()
notes = io.open(os.path.join(HERE, "docs", "PATCH_NOTES.md"), encoding="utf-8").read()
check("① VERSION 한 줄 = GAME_VERSION · 점 세 칸 숫자", vtxt.strip() == buildinfo.GAME_VERSION and len(vtxt.strip().splitlines()) == 1
      and re.fullmatch(r"\d+\.\d+\.\d+", buildinfo.GAME_VERSION), buildinfo.GAME_VERSION)
check("① 패치 노트에 지금 버전의 절(## " + buildinfo.GAME_VERSION + ")",
      re.search(r"^## %s\b" % re.escape(buildinfo.GAME_VERSION), notes, re.M) is not None)

print("── ② 이관 틀(순수)")
check("② 등록부 완결: 종류마다 이관 함수가 0..현재-1 판",
      all(sorted(savedata.MIGRATIONS[k]) == list(range(savedata.CURRENT[k])) for k in savedata.CURRENT), savedata.MIGRATIONS)
check("② 종류 다섯(party·presets·campaign·bestiary·account) · 칸 이름은 '_' 로 시작",
      set(savedata.CURRENT) == {"party", "presets", "campaign", "bestiary", "account"} and K.startswith("_"))
old = {"version": 1, "presets": [{"id": "a"}]}
up = savedata.upgrade("presets", old)
check("② 0판(칸 없음) → 현재 판 · 내용 그대로 · 원본 dict 는 안 바뀐다",
      up.get(K) == savedata.CURRENT["presets"] and {k: v for k, v in up.items() if k != K} == old and K not in old, up)
check("② 이상한 칸(문자열·참거짓·음수)은 0판으로 보고 올린다",
      all(savedata.upgrade("party", {K: bad, "1": {}}).get(K) == savedata.CURRENT["party"] for bad in ("1", True, -3, None)))
cur = {K: savedata.CURRENT["campaign"], "version": 1, "characters": {}}
newer = {K: 99, "version": 1, "characters": {"x": 1}}
check("② 현재 판·더 새 판(되돌린 코드가 읽음)·dict 아님은 그대로",
      savedata.upgrade("campaign", dict(cur)) == cur and savedata.upgrade("campaign", dict(newer)) == newer
      and savedata.upgrade("party", [1, 2]) == [1, 2] and savedata.upgrade("party", None) is None)
st = savedata.stamp("bestiary", {"_readme": "r", "카야": {}, K: 0})
check("② stamp: 판 번호가 맨 앞 · 옛 칸 덮음 · 원본 불변", list(st)[0] == K and st.get(K) == savedata.CURRENT["bestiary"] and list(st)[1:] == ["_readme", "카야"])
trail = []
savedata.CURRENT["_t"] = 3
savedata.MIGRATIONS["_t"] = {n: (lambda n: lambda d: (trail.append((n, savedata.version_of(d))), dict(d, **{"step%d" % n: True}))[1])(n)
                             for n in range(3)}
try:
    a = savedata.upgrade("_t", {"x": 1})
    t0, trail[:] = list(trail), []
    b = savedata.upgrade("_t", {K: 1, "x": 1})
    t1, trail[:] = list(trail), []
    c = savedata.upgrade("_t", {K: 3, "x": 1})
    check("② 체인: 0판은 0→1→2→3 차례로(함수가 받는 판 번호 = 제 출발 판) · 1판은 1→2→3 · 현재 판은 0번",
          t0 == [(0, 0), (1, 1), (2, 2)] and a.get(K) == 3 and a.get("step0") and a.get("step2")
          and t1 == [(1, 1), (2, 2)] and "step0" not in b and b.get(K) == 3 and trail == [] and c == {K: 3, "x": 1}, (t0, t1))
finally:
    savedata.CURRENT.pop("_t")
    savedata.MIGRATIONS.pop("_t")

print("── ③ 덮기 전 백업")
P = os.path.join(TMP, "b.json")
check("③ 없는 파일 → 백업 없음", savedata.backup_before_write("party", P) is None)
jdump(P, {"1": {"name": "카야"}})
orig = raw(P)
bk = savedata.backup_before_write("party", P)
check("③ 옛 판 → <파일>.v0.bak(원본 바이트 그대로)", bk == P + ".v0.bak" and raw(bk) == orig, bk)
jdump(P, {"1": {"name": "다른 내용"}})
check("③ 다시 불러도(아직 옛 판) 이미 있는 백업은 그대로 — 첫 원본을 지킨다",
      savedata.backup_before_write("party", P) is None and raw(P + ".v0.bak") == orig)
jdump(P, savedata.stamp("party", {"1": {}}))
check("③ 현재 판 파일 → 백업 없음", savedata.backup_before_write("party", P) is None)
with io.open(P, "w", encoding="utf-8") as f:
    f.write("{깨짐")
check("③ 깨진 JSON → 백업 없음(판을 모른다 — 대피는 저장소의 .corrupt 몫)", savedata.backup_before_write("party", P) is None)
jdump(P, {K: 9, "1": {}})
check("③ 더 새 판 → .v9.bak", savedata.backup_before_write("party", P) == P + ".v9.bak" and b'"_schema_version": 9' in (raw(P + ".v9.bak") or b""))

print("── ④ 저장소 다섯 — 옛 파일 읽기 → 판 번호 붙여 저장 → 백업")
data = sheetkit.load_traits()
slot = {"job": "도적", "traits": [], "name": "카야", "sex": "여", "persona": "과묵하고 앞장선다"}
# presets
PR = os.path.join(TMP, "character_presets.json")
jdump(PR, {"version": 1, "presets": [{"id": "pid1", "label": "카야", "slot": slot}]})
pr0 = raw(PR)
store = PresetStore(PR, data)
lst = store.list()
store.save(dict(slot, name="두란", job="전사"), "두란")
doc = jload(PR)
check("④ presets: 옛 파일(판 번호 없음)을 읽고 · 저장하면 지금 판(_schema_version 3 — p0.5.22 슬롯의 욕구 칸을 걷음) · .v0.bak = 원본 · v0.5.0 의 읽기 조건(version 1·presets 목록) 그대로",
      [e["id"] for e in lst] == ["pid1"] and doc.get(K) == savedata.CURRENT["presets"] == 3 and raw(PR + ".v0.bak") == pr0
      and doc.get("version") == 1 and isinstance(doc.get("presets"), list) and len(doc["presets"]) == 2, doc.get(K))
jdump(PR, {K: 7, "version": 1, "presets": [{"id": "pid9", "label": "카야", "slot": slot}]})
pr7 = raw(PR)
check("④ presets: 더 새 판 파일도 읽히고(모르는 칸 무시) 덮기 전에 .v7.bak",
      [e["id"] for e in store.list()] == ["pid9"] and store.save(slot, "카야2") and raw(PR + ".v7.bak") == pr7 and jload(PR).get(K) == savedata.CURRENT["presets"])
# party
PP = os.path.join(TMP, "party_custom.json")
sheets = sheetkit.build_party([slot, dict(slot, name="두란", job="전사")], data=data)
jdump(PP, {"_readme": "옛 파일", **sheets})
pp0 = raw(PP)
err = io.StringIO()
with contextlib.redirect_stderr(err):
    lp0 = show_runner.load_party(PP)
    sheetkit.write_party(sheets, PP)
    lp1 = show_runner.load_party(PP)
pdoc = jload(PP)
check("④ party: 옛 파일을 러너가 읽고(폴백 없음) · write_party 가 지금 판(_schema_version 2 — p0.5.22 시트의 욕구 칸을 걷음) · .v0.bak = 원본 · 다시 읽어도 같은 시트",
      sorted(lp0) == ["1", "2"] and lp0 == lp1 and "폴백" not in err.getvalue() and pdoc.get(K) == savedata.CURRENT["party"] == 2 and raw(PP + ".v0.bak") == pp0,
      err.getvalue().strip()[-120:])
check("④ party: v0.5.0 load_party 의 규칙 — '_' 로 시작하지 않는 최상위 키는 전부 캐릭터 칸('1'~'9')",
      all(k.startswith("_") or (len(k) == 1 and k.isdigit() and k != "0") for k in pdoc), list(pdoc))
# campaign
PC = os.path.join(TMP, "campaign.json")
jdump(PC, {"version": 1, "characters": {"pid1": {"name": "카야", "runs": {"7@x": {"seed": 7}}}}, "sources": {"a": "1:2"}})
pc0 = raw(PC)
book = campaign.Book(PC)
loaded_chars = dict(book.data["characters"])
book._save()
cdoc = jload(PC)
check("④ campaign: 옛 파일의 기록을 그대로 읽고(빈 책으로 갈아엎지 않음) · 저장하면 _schema_version 1 · version 1 그대로 · .v0.bak = 원본",
      "pid1" in loaded_chars and cdoc.get(K) == 1 and cdoc.get("version") == 1 and cdoc["characters"] == loaded_chars
      and cdoc["sources"] == {"a": "1:2"} and raw(PC + ".v0.bak") == pc0, cdoc.get(K))
# bestiary
PB = os.path.join(TMP, "bestiary.json")
jdump(PB, {"_readme": "옛 원장", "카야": {"monster:goblin": {"turn": 3, "depth": 1, "n": 2}}})
pb0 = raw(PB)
iss = bestiary.Issuer().load(PB)
knew = sorted(iss.known("카야"))
iss.save(PB)
bdoc = jload(PB)
iss2 = bestiary.Issuer().load(PB)
check("④ bestiary: 옛 원장을 읽고 · 저장하면 _schema_version 1 · 다시 읽어도 같은 지식(판 번호 칸은 캐릭터가 아니다) · .v0.bak = 원본",
      knew == ["monster:goblin"] and bdoc.get(K) == 1 and bdoc["카야"]["monster:goblin"]["n"] == 2
      and sorted(iss2.book) == ["카야"] and raw(PB + ".v0.bak") == pb0, sorted(iss2.book))
# account
AC = accounts.Accounts(os.path.join(TMP, "acct"), secret="verify-patch")
fp = AC.fingerprint("AIzaSy-verify-patch")
os.makedirs(AC.folder(fp), exist_ok=True)
PA = os.path.join(AC.folder(fp), "account.json")
jdump(PA, {"id": fp, "nick": "옛 계정", "created": 1, "keys": [{"fp": fp, "tag": fp[:8], "added": 1, "provider": "gemini_api"}]})
pa0 = raw(PA)
acc = AC.load(fp)
AC._save(acc)
adoc = jload(PA)
check("④ account: 옛 파일을 읽으면 현재 판 · 저장하면 _schema_version 1 · .v0.bak = 원본 · 공개 dict 에 판 번호 없음",
      acc.get(K) == 1 and acc["nick"] == "옛 계정" and adoc.get(K) == 1 and raw(PA + ".v0.bak") == pa0
      and K not in accounts.Accounts.public(acc), adoc.get(K))

print("── ⑤ 판 기록 메타(러너 dummy 판)")


def run_once():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
    with io.open(os.path.join(show_runner.STATE, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


recs = run_once()
meta = recs[0]
try:
    gd = subprocess.run(["git", "describe", "--tags", "--dirty"], cwd=HERE, capture_output=True, text=True, timeout=10)
    git_now = gd.stdout.strip() if gd.returncode == 0 else None
except (OSError, subprocess.SubprocessError):
    git_now = None
mode = brains.action_metadata()["action_mode"]
act = {"compose": "prompts/adventurer_prompt.md", "menu": "prompts/legacy/2026-09-10/adventurer_prompt_menu.md",
       "free": "prompts/legacy/2026-09-10/adventurer_prompt.md"}[mode]


def disk_print(rel):
    with open(os.path.join(HERE, *rel.split("/")), "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()[:12]


pp = meta.get("prompts") or {}
check("⑤ run_meta: game_version = VERSION", meta.get("kind") == "run_meta" and meta.get("game_version") == buildinfo.GAME_VERSION, meta.get("game_version"))
check("⑤ run_meta: git = git describe --tags --dirty(못 물으면 칸 없음)",
      meta.get("git") == git_now if git_now else "git" not in meta, (meta.get("git"), git_now))
check("⑤ run_meta.prompts: 이 판의 행동 지침(%s 판 → %s) · 맥락 · 엔티티의 말 폴더 · (조합형 판만) 행동 말 폴더 · 꺼진 사교·NPC·GM 은 없음" % (mode, act),
      set(pp) == {act, "prompts/context_prompt.md", "prompts/world/"} | ({"prompts/actions/"} if mode == "compose" else set()), sorted(pp))
check("⑤ 지문 = 디스크 바이트(작업 사본 그대로)의 LF 정규화 SHA-256 앞 12자",
      all(pp.get(r) == disk_print(r) for r in (act, "prompts/context_prompt.md")) and re.fullmatch(r"[0-9a-f]{12}", pp.get("prompts/world/", "")),
      {r: (pp.get(r), disk_print(r)) for r in (act, "prompts/context_prompt.md")})
check("⑤ 더미 판엔 model 칸 없음 · backend 그대로", "model" not in meta and meta.get("backend") == "dummy")
saved_be = os.environ["DUNGEON_BRAIN_BACKEND"]
try:
    names = {}
    for be in ("gemini_api", "anthropic_api", "openai_api", "claude_cli", "dummy"):
        os.environ["DUNGEON_BRAIN_BACKEND"] = be
        names[be] = brains.model_name()
finally:
    os.environ["DUNGEON_BRAIN_BACKEND"] = saved_be
check("⑤ model_name: HTTP 두뇌는 haiku 슬롯의 모델 id · claude_cli 는 'haiku' · 더미는 None",
      names["gemini_api"] == model_id("gemini_api", "haiku") and names["anthropic_api"] == model_id("anthropic_api", "haiku")
      and names["openai_api"] == model_id("openai_api", "haiku") and names["claude_cli"] == "haiku" and names["dummy"] is None, names)
saved_flags = (brains.COMPOSE, brains.MENU)
try:
    by_mode, lists = {}, {}
    for m, (c, mn) in {"compose": (True, False), "menu": (False, True), "free": (False, False)}.items():
        brains.COMPOSE, brains.MENU = c, mn
        lists[m] = brains.prompt_files(social=True, npc=True)
        by_mode[m] = lists[m][0]
    full = brains.prompt_files(social=True, npc=True)
finally:
    brains.COMPOSE, brains.MENU = saved_flags
check("⑤ prompt_files: 행동 방식마다 제 지침 파일 · 사교·NPC 를 켜면 그 지침도",
      by_mode == {"compose": "prompts/adventurer_prompt.md", "menu": "prompts/legacy/2026-09-10/adventurer_prompt_menu.md",
                  "free": "prompts/legacy/2026-09-10/adventurer_prompt.md"}
      and "prompts/npc_prompt.md" in full and ("prompts/social_prompt.md" in full) == bool(brains.SOCIAL_PROMPT), (by_mode, full))
check("⑤ prompt_files(p0.5.6): 행동 말 폴더 prompts/actions/(아이템 다루는 규칙·추가 행동 블록 — 조합형 관측에 실린다)는 조합형 판에만 · 지문이 잡힌다",
      {m: "prompts/actions/" in v for m, v in lists.items()} == {"compose": True, "menu": False, "free": False}
      and re.fullmatch(r"[0-9a-f]{12}", buildinfo.prompt_prints(["prompts/actions/"]).get("prompts/actions/", "")) is not None, lists)
n_sent = len(SENT)
recs2 = run_once()
m1 = {k: v for k, v in meta.items() if k != "started"}
m2 = {k: v for k, v in recs2[0].items() if k != "started"}
check("⑤ 두 번 돌려도 같은 메타(started 제외) — 스트림 결정론", m1 == m2)
leak = [t for t in [buildinfo.GAME_VERSION, git_now, "game_version"] + list(pp.values()) if t and any(t in s for s in SENT)]
check("⑤ LLM 에 간 글 %d건 어디에도 버전·git·지문이 없다" % len(SENT), n_sent > 0 and not leak, leak)

print("── ⑥ 지문 규칙(임시 루트)")
R = os.path.join(TMP, "fakeroot")
os.makedirs(os.path.join(R, "prompts", "world", "npc"), exist_ok=True)
real_here = buildinfo.HERE
buildinfo.HERE = R
try:
    with open(os.path.join(R, "prompts", "a.md"), "wb") as f:
        f.write(b"# \xec\xa7\x80\xec\xb9\xa8\r\nline\r\n")
    crlf = buildinfo.file_print("prompts/a.md")
    with open(os.path.join(R, "prompts", "a.md"), "wb") as f:
        f.write(b"# \xec\xa7\x80\xec\xb9\xa8\nline\n")
    lf = buildinfo.file_print("prompts/a.md")
    with open(os.path.join(R, "prompts", "a.md"), "ab") as f:
        f.write(b"more\n")
    edited = buildinfo.file_print("prompts/a.md")
    with open(os.path.join(R, "prompts", "world", "npc", "x.md"), "wb") as f:
        f.write(b"x\n")
    w1 = buildinfo.tree_print("prompts/world/")
    os.rename(os.path.join(R, "prompts", "world", "npc", "x.md"), os.path.join(R, "prompts", "world", "npc", "y.md"))
    w2 = buildinfo.tree_print("prompts/world/")
    got = buildinfo.prompt_prints(["prompts/a.md", "prompts/none.md", "prompts/world/", "prompts/empty/"])
finally:
    buildinfo.HERE = real_here
check("⑥ CRLF·LF 같은 지문 · 내용이 바뀌면 다른 지문", crlf == lf and edited != lf, (crlf, lf, edited))
check("⑥ 폴더 지문: 안의 파일 이름이 바뀌어도 바뀐다", w1 and w2 and w1 != w2)
check("⑥ 없는 파일·빈 폴더는 빠진다", set(got) == {"prompts/a.md", "prompts/world/"}, got)

print("── ⑦ 옛 판 기록 읽기")
OLD = os.path.join(HERE, "runs", "stream-20260909-202333.jsonl")   # 저장소에 남긴 판(필드가 생기기 전)
NEW = os.path.join(show_runner.STATE, "stream.jsonl")
with io.open(OLD, encoding="utf-8") as f:
    old_meta = json.loads(f.readline())
check("⑦ 옛 판은 정말 옛 판(game_version·git·prompts·model 없음)", old_meta.get("kind") == "run_meta"
      and not any(k in old_meta for k in ("game_version", "git", "prompts", "model")))
for tag, path in (("옛", OLD), ("새", NEW)):
    try:
        pj = campaign.project(path)
        col, end = run_summary.replay(path)
        res = col.result()
        iss = bestiary.Issuer()
        with io.open(path, encoding="utf-8") as f:
            first = json.loads(f.readline())
        iss.consume("run_meta", first)
        ok = pj is not None and pj["seed"] == first["seed"] and col.meta is not None and res is not None
        why = ""
    except Exception as e:                       # 소비자가 터지면 그 자체가 실패
        ok, why = False, "%s: %s" % (type(e).__name__, e)
    check("⑦ %s 판: campaign.project · run_summary.replay·result · 도감 발급기 run_meta 소비가 그대로 돈다" % tag, ok, why)

print("── ⑧ 실패 주입(임시 폴더) — 백업·쓰기가 실패해도 원본이 남는다")
F = os.path.join(TMP, "fault")
os.makedirs(F)
real_replace, real_fdopen = savedata._replace, os.fdopen


def fail_replace(pred):
    """교체 단계에서 pred(대상 경로)인 것만 실패시킨다(PermissionError 가 아닌 OSError — 재시도 없이 바로)."""
    def fake(tmp, dst):
        if pred(dst):
            raise OSError("주입된 실패: " + os.path.basename(dst))
        return real_replace(tmp, dst)
    return fake


def strays(folder):
    """남은 임시 파일·백업 — 실패한 저장은 아무것도 남기지 않아야 한다."""
    return sorted(n for n in os.listdir(folder) if n.endswith((".tmp", ".bak")))


def attempt(fn):
    try:
        fn()
        return None
    except Exception as e:                           # 어떤 예외가 났나만 본다
        return e


sheets2 = sheetkit.build_party([dict(slot, name="새 파티")], data=data)
v0 = {}                                              # 저장소별 옛 판(판 번호 없음) 파일
for name, doc in (("party_custom.json", {"_readme": "옛", **sheets}),
                  ("character_presets.json", {"version": 1, "presets": [{"id": "pid1", "label": "카야", "slot": slot}]}),
                  ("campaign.json", {"version": 1, "characters": {"pid1": {"name": "카야", "runs": {}}}, "sources": {}}),
                  ("bestiary.json", {"_readme": "옛", "카야": {"monster:goblin": {"turn": 3, "depth": 1, "n": 2}}})):
    d = os.path.join(F, "a_" + name.split(".")[0])
    os.makedirs(d)
    jdump(os.path.join(d, name), doc)
    v0[name] = os.path.join(d, name)
FA = accounts.Accounts(os.path.join(F, "acct"), secret="verify-patch-fault")
fa = FA.fingerprint("AIzaSy-fault")
os.makedirs(FA.folder(fa))
jdump(os.path.join(FA.folder(fa), "account.json"), {"id": fa, "nick": "옛", "created": 1, "keys": []})
v0["account.json"] = os.path.join(FA.folder(fa), "account.json")
before = {n: raw(p) for n, p in v0.items()}
saves = {"party_custom.json": lambda: sheetkit.write_party(sheets2, v0["party_custom.json"]),
         "character_presets.json": lambda: PresetStore(v0["character_presets.json"], data).save(dict(slot, name="두란"), "두란"),
         "campaign.json": lambda: campaign.Book(v0["campaign.json"])._save(),
         "bestiary.json": lambda: bestiary.Issuer().load(v0["bestiary.json"]).save(v0["bestiary.json"]),
         "account.json": lambda: FA._save(FA.load(fa))}
savedata._replace = fail_replace(lambda dst: dst.endswith(".bak"))
try:
    errs = {n: attempt(fn) for n, fn in saves.items()}
finally:
    savedata._replace = real_replace
check("⑧ 백업 실패 → 저장소 다섯 모두 BackupError(OSError) · 원본 바이트 그대로 · .bak·임시 파일 없음",
      all(isinstance(errs[n], savedata.BackupError) and isinstance(errs[n], OSError) for n in saves)
      and all(raw(p) == before[n] for n, p in v0.items()) and all(not strays(os.path.dirname(p)) for p in v0.values()),
      {n: type(e).__name__ for n, e in errs.items()})
savedata._replace = fail_replace(lambda dst: not dst.endswith(".bak"))
try:
    e_main = attempt(saves["party_custom.json"])
finally:
    savedata._replace = real_replace
pdir = os.path.dirname(v0["party_custom.json"])
check("⑧ 백업 뒤 본 파일 교체가 실패 → 원본 그대로 · .v0.bak 은 온전한 원본 · 임시 파일 없음",
      isinstance(e_main, OSError) and raw(v0["party_custom.json"]) == before["party_custom.json"]
      and raw(v0["party_custom.json"] + ".v0.bak") == before["party_custom.json"] and strays(pdir) == ["party_custom.json.v0.bak"],
      (e_main, strays(pdir)))
sheetkit.write_party(sheets, v0["party_custom.json"])           # 이제 현재 판 — 아래는 백업 없이 쓰는 길
cur = raw(v0["party_custom.json"])


class HalfWriter:
    """절반만 쓰고 '디스크 가득'으로 멈추는 파일 — 쓰는 도중 실패."""
    def __init__(self, f):
        self.f = f

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.f.close()
        return False

    def write(self, b):
        self.f.write(b[:len(b) // 2])
        self.f.flush()
        raise OSError(28, "디스크 가득(주입)")


os.fdopen = lambda fd, *a, **k: HalfWriter(real_fdopen(fd, *a, **k))
try:
    e_half = attempt(lambda: sheetkit.write_party(sheets2, v0["party_custom.json"]))
finally:
    os.fdopen = real_fdopen
err = io.StringIO()
with contextlib.redirect_stderr(err):
    still = show_runner.load_party(v0["party_custom.json"])
check("⑧ 쓰는 도중 실패(절반 쓰고 디스크 가득) → 파티 파일은 바이트 그대로 · 러너가 그대로 읽는다 · 임시 파일 없음(예전 결함: 제자리 잘라쓰기)",
      isinstance(e_half, OSError) and raw(v0["party_custom.json"]) == cur and sorted(still) == ["1", "2"] and "폴백" not in err.getvalue()
      and strays(pdir) == ["party_custom.json.v0.bak"], (e_half, strays(pdir)))
PI = os.path.join(F, "inc", "party_custom.json")
os.makedirs(os.path.dirname(PI))
jdump(PI, {"_readme": "옛", **sheets})
orig_i = raw(PI)
with open(PI + ".v0.bak", "wb") as f:
    f.write(orig_i[:len(orig_i) // 2])                         # 잘린 백업(옛 복사가 도중에 끊긴 것)
sheetkit.write_party(sheets2, PI)
PW = os.path.join(F, "inc", "w", "party_custom.json")
os.makedirs(os.path.dirname(PW))
jdump(PW, {"_readme": "옛", **sheets})
orig_w = raw(PW)
jdump(PW + ".v0.bak", {K: 1, "1": {}})                          # 온전한 JSON 이지만 다른 판 — 이 판의 백업이 아니다
sheetkit.write_party(sheets2, PW)
check("⑧ 잘린 .bak·판이 다른 .bak 은 백업으로 치지 않는다 → 온전한 원본으로 새로 남긴다",
      raw(PI + ".v0.bak") == orig_i and raw(PW + ".v0.bak") == orig_w and jload(PI).get(K) == savedata.CURRENT["party"])
DIRP = os.path.join(F, "isdir.json")
os.makedirs(DIRP)
e_dir = attempt(lambda: savedata.backup_before_write("party", DIRP))
check("⑧ 있는데 못 읽는 파일 → BackupError(판을 몰라 덮지 않는다)", isinstance(e_dir, savedata.BackupError), e_dir)
LD = os.path.join(F, "ledger")
os.makedirs(LD)
LP = os.path.join(LD, "bestiary.json")
jdump(LP, {"_readme": "옛 원장", "두란": {"monster:goblin": {"turn": 1, "depth": 1, "n": 1}}})
led0 = raw(LP)
saved_conf = (show_runner.BESTIARY_FILE, show_runner.MAX_TURNS)
show_runner.BESTIARY_FILE, show_runner.MAX_TURNS = LP, 40
savedata._replace = fail_replace(lambda dst: dst.endswith(".bak"))
err = io.StringIO()
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        e_run = attempt(show_runner.main)
finally:
    savedata._replace = real_replace
    show_runner.BESTIARY_FILE, show_runner.MAX_TURNS = saved_conf
with io.open(os.path.join(show_runner.STATE, "stream.jsonl"), encoding="utf-8") as f:
    last = [json.loads(x) for x in f if x.strip()][-1]
check("⑧ 판 도중 도감 저장의 백업이 실패해도 판은 끝까지 · 경고 한 번 · 원장 파일 바이트 그대로 · .bak·임시 파일 없음",
      e_run is None and last.get("kind") == "end" and err.getvalue().count("도감 원장") == 1 and raw(LP) == led0 and not strays(LD),
      (e_run, last.get("kind"), err.getvalue().strip()[-160:], strays(LD)))

shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAIL %d — %s" % (len(fails), "; ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_patch (p0.5.1 버전 단일 원본·저장 이관 틀·판 기록의 버전·git·지침 지문)")
