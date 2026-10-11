# -*- coding: utf-8 -*-
"""기준선 도구(tools/baseline.py, p0.5.3) 헤들리스 검증 — 91번째 게이트. LLM 0콜 · git 0회 · 러너 무접촉(show_runner 를 import 하지 않는다 —
import 만으로 state/ 를 만들기 때문).
게이트:
  ① label = 이름만: 절대경로·드라이브·'..'·구분자·빈 값·끝 점·65자 → 거절, 보통 이름 → 출력 루트 바로 아래 경로
  ② 경계 이중 확인: 이름이 맞아도 실제 경로(realpath — 링크·정션)가 루트 밖이면 거절 · capture/diff 는 git·폴더보다 label 검사가 먼저
  ③ 합치기: 같은 코드·같은 도구 판은 나눈 실행을 합친다 · 다른 코드 또는 다른 도구 판에 부분 산출(--part·--chunk·--only)을 덧붙이면 거절 ·
     전체 산출·--fresh 는 새로
  ④ 바이트 비교: 끝 개행·CRLF 한 줄·내용 차이가 전부 차이로 남는다(splitlines 가 지우던 것) · 같으면 0
  ⑤ JSON 줄: 같은 값·다른 직렬화(칸 순서)도 차이 · 값 차이는 칸 경로로 · 실행 시각만 다른 줄은 0 · 프롬프트 끝 개행 차이도 남는다
  ⑥ 설명 규칙: 전·후 원문 조건 없는 규칙은 거절 · 같은 경로라도 원문이 규칙과 다른 차이는 (나)로 남는다 ·
     허용된 값 변경에 직렬화 변경(칸 순서·공백·CRLF·이스케이프)이 섞이면 남는 바이트 차이가 (나) — 값 변경만, 문서 가운데 칸 추가는 (나) 0
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
import baseline as BL                                # noqa: E402

TMP = tempfile.mkdtemp(prefix="wl_baseline_verify_")
fails = []


def check(name, ok, detail=""):
    print(("  ok  " if ok else "  FAIL") + " " + name + (("  — " + str(detail)[:300]) if detail and not ok else ""))
    if not ok:
        fails.append(name)


def rejects(fn):
    try:
        fn()
        return False
    except SystemExit:
        return True


print("── ① label = 이름만")
ROOT = os.path.join(TMP, "out")
os.makedirs(ROOT)
bad = ["C:\\Users\\x\\state", "/etc/x", "..", "../state", "a/../../state", "p053\\..\\..\\state", "a/b", "a\\b", "", ".", ".hidden",
       "p053.", "p053-", "x" * 65, "C:state", None, 7]
got_bad = {repr(b): rejects(lambda b=b: BL.under(ROOT, b)) for b in bad}
check("① 절대경로·드라이브·'..'·구분자·빈 값·점으로 시작/끝·65자·문자열 아님 → 전부 거절", all(got_bad.values()),
      [k for k, v in got_bad.items() if not v])
good = ["p053-before", "p0.5.3_b", "A1", "x" * 64]
paths = {g: BL.under(ROOT, g) for g in good}
check("① 보통 이름 → 출력 루트 바로 아래(realpath 기준)",
      all(os.path.dirname(p) == os.path.realpath(ROOT) and os.path.basename(p) == g for g, p in paths.items()), paths)
check("① under() 는 폴더를 만들지 않는다(검사만)", os.listdir(ROOT) == [])

print("── ② 경계 이중 확인")
real_rp = BL.os.path.realpath
outside = os.path.join(TMP, "elsewhere", "evil")


def fake_realpath(p, *a, **k):                       # 링크·정션 흉내: 이름은 맞지만 실제 경로가 다른 곳
    return outside if os.path.basename(str(p)) == "evil" else real_rp(p, *a, **k)


BL.os.path.realpath = fake_realpath
try:
    linked = rejects(lambda: BL.under(ROOT, "evil"))
finally:
    BL.os.path.realpath = real_rp
check("② 이름이 맞아도 실제 경로가 루트 밖(링크·정션)이면 거절", linked)
calls = []
real_git = BL._git
BL._git = lambda *a: calls.append(a) or b""
try:
    r1 = rejects(lambda: BL.main(["capture", "--rev", "HEAD", "--label", "..\\..\\state"]))
    r2 = rejects(lambda: BL.main(["capture", "--rev", "WORKTREE", "--label", os.path.join(HERE, "state")]))
    r3 = rejects(lambda: BL.main(["diff", "p053-before", "../state"]))
finally:
    BL._git = real_git
check("② capture·diff: 나쁜 label 은 git 을 부르기도 전에 거절(아무것도 안 만들고 안 지운다)", r1 and r2 and r3 and calls == [], calls)

print("── ③ 같은 label 에 합치기")
A = {"rev": "HEAD", "commit": "a" * 40}
B = {"rev": "WORKTREE", "head": "a" * 40, "status_sha": "1234abcd1234abcd"}
B2 = dict(B, status_sha="ffffffffffffffff")
man = {"src": dict(A, prepared_sec=1.0), "tool_version": BL.TOOL_VERSION}
check("③ 앞선 산출 없음·--fresh → 새로 · 같은 코드·같은 도구 판 → 합친다",
      BL.merge_policy({}, A, "gates", True, False) == "new" and BL.merge_policy(man, A, "gates", True, True) == "new"
      and BL.merge_policy(man, A, "gates", True, False) == "merge"
      and BL.merge_policy({"src": B, "tool_version": BL.TOOL_VERSION}, dict(B, status=["x"]), "runs", True, False) == "merge")
check("③ 다른 코드(커밋이 다름·작업 트리 내용이 다름)에 부분 산출 → 거절",
      rejects(lambda: BL.merge_policy(man, B, "runs", True, False)) and rejects(lambda: BL.merge_policy({"src": B}, B2, "gates", True, False))
      and rejects(lambda: BL.merge_policy({"src": B}, B2, "all", True, False)))
check("③ 다른 코드라도 나누지 않은 전체 산출 → 새로(앞 산출을 지운다)", BL.merge_policy({"src": B}, B2, "all", False, False) == "new")
old_tool = {"src": dict(A), "tool_version": BL.TOOL_VERSION - 1}
check("③ 같은 코드라도 도구 판이 다른 산출(또는 판 표시 없음)에 부분 산출 → 거절 · 전체 산출·--fresh 는 새로",
      rejects(lambda: BL.merge_policy(old_tool, A, "gates", True, False)) and rejects(lambda: BL.merge_policy({"src": dict(A)}, A, "runs", True, False))
      and BL.merge_policy(old_tool, A, "all", False, False) == "new" and BL.merge_policy(old_tool, A, "gates", True, True) == "new"
      and BL.merge_policy({"src": dict(A), "tool_version": BL.TOOL_VERSION}, A, "gates", True, False) == "merge")

print("── ④ 바이트 비교(줄 끝까지)")


def occ(fn, *args, **kw):
    D = BL.Diffs([])
    fn(D, "s", *args, **kw)
    return D.occ


same = occ(BL.diff_text, "a\nb\n", "a\nb\n")
tail = occ(BL.diff_text, "a\nb\n", "a\nb")
crlf = occ(BL.diff_text, "a\nb\nc\n", "a\nb\r\nc\n")
body = occ(BL.diff_text, "a\nb\n", "a\nB\n")
check("④ 같으면 0 · 끝 개행 하나 · 가운데 줄 CRLF · 내용 차이 — 셋 다 차이로 남는다(원문 그대로)",
      same == [] and len(tail) == 1 and tail[0]["before"] == "b\n" and tail[0]["after"] == "b"
      and len(crlf) == 1 and crlf[0]["after"] == "b\r\n" and len(body) == 1 and body[0]["before"] == "b\n", (tail, crlf, body))
check("④ 한쪽 파일 없음 → 차이", len(occ(BL.diff_text, None, "x")) == 1 and occ(BL.diff_text, None, None) == [])

print("── ⑤ JSON 줄")
l1 = '{"kind": "tick", "turn": 1, "hp": 3}\n'
l1b = '{"turn": 1, "kind": "tick", "hp": 3}\n'
l1c = '{"kind": "tick", "turn": 1, "hp": 4}\n'
meta = '{"kind": "run_meta", "started": "%s", "seed": 7}\n'
check("⑤ 같은 값·다른 직렬화(칸 순서) → '(바이트: 직렬화·줄 끝)' 차이",
      [o["path"] for o in occ(BL.diff_jsonl, l1, l1b)] == ["tick(바이트: 직렬화·줄 끝)"])
check("⑤ 값 차이 → 칸 경로(tick.hp)", [(o["path"], o["before"], o["after"]) for o in occ(BL.diff_jsonl, l1, l1c)] == [("tick.hp", "3", "4")])
ma_, mb_ = (BL.mask_text("stream.jsonl", meta % t) for t in ("2026-10-12T00:00:00", "2026-10-12T09:09:09"))
check("⑤ 실행 시각만 다른 줄 → 0(원문에서 그 값만 덮는다)", occ(BL.diff_jsonl, ma_, mb_) == [] and "<V>" in ma_)
check("⑤ 줄 수가 다르면 줄 수 + 한쪽에만 있는 줄", [o["path"] for o in occ(BL.diff_jsonl, l1, l1 + l1c)] == ["(줄 수)", "(한쪽에만 있는 줄)"])
p_a = json.dumps({"key": [3, "1"], "model": "haiku", "prompt": "지침\n관측\n"}, ensure_ascii=False) + "\n"
p_b = json.dumps({"key": [3, "1"], "model": "haiku", "prompt": "지침\n관측"}, ensure_ascii=False) + "\n"
po = occ(BL.diff_jsonl, p_a, p_b)
check("⑤ 프롬프트 끝 개행 하나만 달라도 차이(예전 splitlines 비교는 0이었다)",
      len(po) == 1 and po[0]["path"].startswith("프롬프트(t3 봇1)") and po[0]["before"] == "관측\n" and po[0]["after"] == "관측", po)

print("── ⑥ 설명 규칙")
check("⑥ 전·후 원문 조건 없는 규칙·둘 다 준 규칙은 거절",
      rejects(lambda: BL.check_rules([{"scope": "s", "path": ".", "why": "w"}]))
      and rejects(lambda: BL.check_rules([{"scope": "s", "path": ".", "why": "w", "before": "a", "before_re": "a", "after": "b"}]))
      and rejects(lambda: BL.check_rules({"scope": "s"})))
D = BL.Diffs([{"scope": "gates/x", "path": "^출력 replace$", "before": "버전 0.5.2\n", "after": "버전 0.5.3\n", "why": "버전"}])
D.add("gates/x", "출력 replace", "버전 0.5.2\n", "버전 0.5.3\n")
D.add("gates/x", "출력 replace", "판형 1\n", "판형 2\n")
D.add("gates/x", "출력 replace", "버전 0.5.2\n", "버전 0.5.3\r\n")
whys = [o["why"] for o in D.occ]
check("⑥ 같은 범위·경로라도 원문이 규칙과 다르면(다른 줄·줄 끝만 달라도) (나)", whys == ["버전", None, None], whys)
VR = [{"scope": "s", "path": "^run_meta\\.game_version$", "before": "0.5.2", "after": "0.5.3", "why": "버전"},
      {"scope": "s", "path": "^\\.state_version$", "before": "<없음>", "after": "1", "why": "판 번호"},
      {"scope": "s", "path": "^\\.version$", "before": "1", "after": "2", "why": "판형"}]


def unexplained(fn, a, b):
    D2 = BL.Diffs(VR)
    fn(D2, "s", a, b)
    return [o for o in D2.occ if not o["why"]]


v0 = '{"kind": "run_meta", "game_version": "0.5.2", "seed": 7}\n'
check("⑥ 허용된 값 변경만 → (나) 0", unexplained(BL.diff_jsonl, v0, v0.replace("0.5.2", "0.5.3")) == [])
mixed = {"칸 순서": '{"seed": 7, "kind": "run_meta", "game_version": "0.5.3"}\n',
         "공백": '{"kind": "run_meta",  "game_version": "0.5.3", "seed": 7}\n',
         "CRLF": '{"kind": "run_meta", "game_version": "0.5.3", "seed": 7}\r\n',
         "이스케이프": '{"\\u006bind": "run_meta", "game_version": "0.5.3", "seed": 7}\n'}   # 같은 키 'kind' 를 다른 바이트로
got_mixed = {k: len(unexplained(BL.diff_jsonl, v0, v)) for k, v in mixed.items()}
check("⑥ 허용된 값 변경 + 직렬화 변경(칸 순서·공백·CRLF·이스케이프)이 한 줄에 섞이면 → 남는 바이트 차이가 (나) 1 이상",
      all(n >= 1 for n in got_mixed.values()), got_mixed)
d0 = '{\n "version": 1,\n "saved_at": "<V>",\n "seed": 11\n}\n'
d1 = '{\n "version": 2,\n "state_version": 1,\n "saved_at": "<V>",\n "seed": 11\n}\n'
d2 = '{\n "version": 2,\n "state_version": 1,\n "saved_at": "<V>",\n  "seed": 11\n}\n'
check("⑥ 문서 가운데 칸 추가 + 값 변경(허용) → (나) 0 · 같은 변경에 들여쓰기 한 칸이 섞이면 → (나) 1 이상",
      unexplained(BL.diff_jsondoc, d0, d1) == [] and len(unexplained(BL.diff_jsondoc, d0, d2)) >= 1,
      (unexplained(BL.diff_jsondoc, d0, d1), unexplained(BL.diff_jsondoc, d0, d2)))
VR[:] = VR + [{"scope": "s", "path": "^\\.a$", "before": "<없음>", "after": "1", "why": "a"},
              {"scope": "s", "path": "^\\.b$", "before": "<없음>", "after": "2", "why": "b"}]
edge = {"맨 앞 두 칸": ('{"c": 3}\n', '{"a": 1, "b": 2, "c": 3}\n'), "맨 뒤 두 칸": ('{"c": 3}\n', '{"c": 3, "a": 1, "b": 2}\n'),
        "가운데 띄엄": ('{"c": 3, "d": 4}\n', '{"a": 1, "c": 3, "b": 2, "d": 4}\n'), "유일한 칸": ('{}\n', '{"a": 1}\n')}
got_edge = {k: unexplained(BL.diff_jsondoc, a, b) for k, (a, b) in edge.items()}
check("⑥ 허용된 칸 추가가 맨 앞·맨 뒤·띄엄·유일한 칸이어도 쉼표·공백을 바르게 걷어 (나) 0",
      all(v == [] for v in got_edge.values()), got_edge)
R = BL.Diffs([{"scope": "runs/*/snapshot.json", "path": "^\\.pickle_bytes$", "before_re": "\\d+", "after_re": "\\d+", "why": "w"}])
R.add("runs/live/snapshot.json", ".pickle_bytes", 100, 200)
R.add("runs/live/snapshot.json", ".pickle_bytes", 100, "x200")
check("⑥ 정규식 조건은 전체 일치(부분 일치로 새지 않는다)", [o["why"] for o in R.occ] == ["w", None])

check("러너 무접촉: 이 검사는 show_runner·dungeon_gm 을 import 하지 않았다",
      "show_runner" not in sys.modules and "dungeon_gm" not in sys.modules)
shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAIL %d — %s" % (len(fails), "; ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_baseline (기준선 도구: label 경계·코드 섞임 거절·바이트 비교·좁은 설명 규칙, 0콜)")
