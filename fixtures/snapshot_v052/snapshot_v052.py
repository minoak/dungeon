# -*- coding: utf-8 -*-
"""스냅샷 — 판의 몸을 마지막 기록 자리에 얼려 두는 파일(D79, 2026-09-16 파트너 "저장 시점은 마지막 기록에서" ·
"일단 던전에서 이어가게 하자 … 요약해서 들고 있게 … 종료 전에는 미리 알림").

러너가 **틱마다 루프 머리에서**(그 틱의 기록을 쓰기 전에) 세계·파티·장부를 통째로 피클해 둔다 — 그래서 론처 중지·서버 재시작·크래시 어느 경우든
"마지막으로 스트림에 남은 틱"과 같은 몸이 남는다. 이어가기(DUNGEON_RESUME)는 이 파일을 되살려 스트림을 그 자리에 이어 쓴다(같은 판 = 같은 run_id).

  · 파일 둘: `snapshot.pkl`(몸 — 피클) + `snapshot.json`(요약 — 론처가 읽는 쪽. 피클을 안 열고도 "지하 3층 t158 에서 멈춤"을 안다).
  · 결정 재생(시드+decisions 리플레이)이 아니라 스냅샷인 이유: 부수 채널(수첩·관계 살·도감 note·NPC 두뇌 문장)이 기록에서 완전히 재유도되지 않고,
    배포 중 엔진이 바뀌면 재생 결과가 어긋난다. 스냅샷은 "그때 그 몸"이다(엔진이 바뀌면 되살리기 실패 → 러너가 정직하게 폴백한다).
  · ⚠️ 피클 보안: 이 파일은 **러너 자신이 자기 state/ 폴더에 쓰고 같은 서버의 러너가 되읽는다**. 사용자 업로드·네트워크 경로는 없다(론처 API 는 json 요약만
    돌려준다). 남이 만든 .pkl 을 여기 두면 임의 코드가 돈다 — 데이터 폴더의 쓰기 권한이 곧 서버 권한이라는 전제 위에 있다(accounts/·state/ 와 같은 급).
LLM 0콜 · 엔진 무접촉 · 순수 파일.
"""
import io
import json
import os
import pickle
import tempfile
import time

VERSION = 1
PKL = "snapshot.pkl"
META = "snapshot.json"


class SnapshotError(RuntimeError):
    pass


def paths(state_dir):
    return os.path.join(state_dir, PKL), os.path.join(state_dir, META)


def _replace(tmp, dst):
    for i in range(20):                       # Windows: 방금 쓴 파일을 색인기·백신이 잠깐 잡으면 replace 가 WinError 5(bestiary.save 선례)
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05 * (i + 1))


def _atomic_bytes(dst, data):
    folder = os.path.dirname(dst) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".snap-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        _replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def write(state_dir, snap, meta):
    """몸(snap dict)과 요약(meta dict)을 원자적으로 쓴다. 요약에는 version·saved_at 이 덧붙는다. 반환 = 피클 바이트 수."""
    pkl, mj = paths(state_dir)
    data = pickle.dumps({"version": VERSION, **snap}, protocol=pickle.HIGHEST_PROTOCOL)
    _atomic_bytes(pkl, data)
    write_meta(state_dir, meta)
    return len(data)


def write_meta(state_dir, meta):
    """요약만 다시 쓴다(정지 사유 갱신 등 — 몸은 그대로)."""
    _, mj = paths(state_dir)
    doc = {"version": VERSION, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"), **meta}
    _atomic_bytes(mj, (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def read_meta(state_dir):
    """요약(json)만 읽는다 — 론처·상태 API 용(피클을 열지 않는다). 없거나 깨지면 None."""
    _, mj = paths(state_dir)
    try:
        with io.open(mj, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("version") != VERSION or not doc.get("run_id"):
        return None
    pkl, _ = paths(state_dir)
    if not os.path.isfile(pkl):
        return None
    return doc


def load(pkl_path):
    """피클을 되살린다 → (snap, meta). 요약이 없거나 run_id 가 어긋나면 SnapshotError(폴백 사유)."""
    state_dir = os.path.dirname(os.path.abspath(pkl_path))
    meta = read_meta(state_dir)
    if meta is None:
        raise SnapshotError("스냅샷 요약(snapshot.json)이 없거나 깨졌다")
    try:
        with open(pkl_path, "rb") as f:
            snap = pickle.load(f)               # ⚠️ 자기 폴더의 자기 파일만(모듈 머리글 보안 전제)
    except Exception as e:                      # 엔진이 바뀌어 클래스가 안 맞는 것까지 — 이유는 한 줄로
        raise SnapshotError("스냅샷을 되살리지 못했다: %s: %s" % (type(e).__name__, str(e)[:120]))
    if not isinstance(snap, dict) or snap.get("version") != VERSION:
        raise SnapshotError("스냅샷 판형이 다르다")
    if snap.get("run_id") != meta.get("run_id"):
        raise SnapshotError("스냅샷 몸과 요약이 다른 판이다")
    for k in ("d", "bots", "sheets", "next_turn", "stream_pos", "seed", "started"):
        if k not in snap:
            raise SnapshotError("스냅샷에 %s 가 없다" % k)
    return snap, meta


def remove(state_dir):
    """이어갈 몸이 없어졌다(판이 끝났거나 새 판을 시작했다)."""
    for p in paths(state_dir):
        try:
            os.remove(p)
        except OSError:
            pass
