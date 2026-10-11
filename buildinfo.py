# -*- coding: utf-8 -*-
"""판 기록에 남기는 빌드 정보(p0.5.1, 2026-10-11 — 라이브 서비스식 패치의 전제 '판 기록에 버전·지침').

어느 판이 어느 코드·어느 지침으로 돌았는지를 판 기록(run_meta·resume 줄)만 보고 알게 한다 — 벤치 전후 비교와 패치 되돌리기의 바닥.
  · 게임 버전 = 리포 루트 VERSION 파일 한 줄(단일 원본). 패치마다 올리고 같은 이름의 태그(v0.5.1)를 붙인다.
  · git = `git describe --tags --dirty`(마지막 태그 · 그 뒤 커밋 수 · 해시 · 작업 사본 수정 여부). git 이 없거나 저장소가 아니면 뺀다.
  · 지침 지문 = LLM 에 실제로 들어가는 지침 파일의 SHA-256 앞 12자. **디스크에 있는 그대로** 잰다(커밋 안 된 수정도 그대로).
    줄끝은 LF 로 맞춰 잰다(prompts/legacy/*/SHA256.json 과 같은 관례 — 체크아웃의 CRLF 설정이 지문을 바꾸지 않게).
    파일 단위라 `<!-- -->` 메모만 고쳐도 지문이 바뀐다(모델이 받는 글은 같아도 — 보수적으로).
    어느 파일이 대상인지는 판의 설정이 정한다(brains.prompt_files).
LLM 0콜 · 엔진 무접촉. 이 값들은 스트림에만 실리고 프롬프트에는 들어가지 않는다.
"""
import hashlib
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PRINT_LEN = 12          # 지문 길이(hex) — D62 몸짓 지문과 같은 12자


def _read_version():
    try:
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "unknown"
    except OSError:
        return "unknown"


GAME_VERSION = _read_version()

_GIT = []               # git describe 결과 한 칸 — 프로세스당 한 번만 묻는다(게이트가 판을 여러 번 열어도 같은 값 = 스트림 결정론 유지)


def git_describe():
    """`git describe --tags --dirty` 한 줄. 실패하면 None(배포 사본에 .git 이 없어도 판은 돈다)."""
    if not _GIT:
        out = ""
        try:
            r = subprocess.run(["git", "describe", "--tags", "--dirty"], cwd=HERE, capture_output=True, text=True,
                               timeout=5, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})   # 색인 잠금을 잡지 않는다(사람의 git 명령과 안 부딪히게)
            if r.returncode == 0:
                out = (r.stdout or "").strip()
        except (OSError, subprocess.SubprocessError):
            pass
        _GIT.append(out or None)
    return _GIT[0]


def _lf_bytes(path):
    with open(path, "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


def _abs(rel):
    return os.path.join(HERE, *rel.strip("/").split("/"))


def file_print(rel):
    """파일 하나의 지문. 없으면 None."""
    try:
        return hashlib.sha256(_lf_bytes(_abs(rel))).hexdigest()[:PRINT_LEN]
    except OSError:
        return None


def tree_print(rel):
    """폴더 하나(그 아래 .md 전부)의 지문 — 상대 경로와 내용을 함께 잰다(파일이 늘거나 이름이 바뀌어도 바뀐다). 비었거나 없으면 None."""
    root = _abs(rel)
    found = []
    for d, _, files in os.walk(root):
        for n in files:
            if n.endswith(".md"):
                p = os.path.join(d, n)
                found.append((os.path.relpath(p, root).replace(os.sep, "/"), p))
    if not found:
        return None
    h = hashlib.sha256()
    for name, p in sorted(found):
        h.update(name.encode("utf-8") + b"\0" + _lf_bytes(p) + b"\0")
    return h.hexdigest()[:PRINT_LEN]


def prompt_prints(rels):
    """리포 기준 상대 경로 목록 → {경로: 지문}. '/' 로 끝나면 폴더. 없는 파일은 뺀다(판에 안 쓰였다)."""
    out = {}
    for rel in rels:
        fp = tree_print(rel) if rel.endswith("/") else file_print(rel)
        if fp:
            out[rel] = fp
    return out


def run_fields(prompt_rels):
    """run_meta·resume 줄에 붙일 판 정보 {game_version, git?, prompts}."""
    g = git_describe()
    return {"game_version": GAME_VERSION, **({"git": g} if g else {}), "prompts": prompt_prints(prompt_rels)}
