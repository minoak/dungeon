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
  · 판 번호(p0.5.3 — 라이브 패치의 '저장 데이터 호환'): 패치가 몸·장부의 꼴을 바꾸면 옛 스냅샷을 버리지 않고 새 꼴로 올려 읽는다.
      version       판형 — 2 = state_version 이 있는 판. ≤v0.5.2 코드는 1 만 읽으므로 새 스냅샷을 거절한다(되돌린 코드가 새 몸을 옛 규칙으로 잇지 않는다
                    — 러너는 정직하게 새 판으로 폴백, 옛 기록은 runs/ 로 대피). 이 코드는 1(=내용 판 0)과 2 를 읽는다.
      state_version 내용 판 — 몸·장부 꼴이 바뀌는 패치마다 STATE_VERSION 을 올리고 MIGRATIONS 에 n→n+1 함수 하나를 더한다(savedata 와 같은 체인).
                    더 새 내용 판(되돌린 코드가 새 스냅샷을 읽음)은 거절한다 — 요약(read_meta)도 None 이라 론처가 이어가기를 내밀지 않는다.
      0→1(p0.5.3): 몸에 정신·숙련 칸(mind·search_prof·steal_prof)이 생겼다 — 옛 몸에 직업 기본값을 채운다(스폰과 같은 규칙, judge.prof).
LLM 0콜 · 순수 파일(이관 함수만 몸 dict 를 고친다 — 그때 judge 를 늦게 import).
"""
import io
import json
import os
import pickle
import tempfile
import time

VERSION = 2                  # 판형(위 머리글) — 옛 코드(version 1 만 읽음)가 새 스냅샷을 거절하게 하는 문
READS = (1, 2)               # 이 코드가 읽는 판형. 1 = p0.5.2 까지(내용 판 0)
STATE_VERSION = 1            # 내용 판 — 올릴 때 MIGRATIONS 에 한 칸
PKL = "snapshot.pkl"
META = "snapshot.json"


def _bodies(snap):
    """스냅샷 안의 몸 dict 전부(중복 없이) — 지금 세계의 봇 · 다른 세계(D84 worlds)의 봇 · 부활 대기(D99 waiting)."""
    seen, out = set(), []
    lists = [snap.get("bots") or []] + [w.get("bots") or [] for w in (snap.get("worlds") or []) if isinstance(w, dict)]
    lists.append(list((snap.get("waiting") or {}).values()))
    for lst in lists:
        for b in lst:
            if isinstance(b, dict) and id(b) not in seen:
                seen.add(id(b))
                out.append(b)
    return out


def _m0_prof(snap):
    """0→1(p0.5.3): 옛 몸에 정신·숙련 칸 — 시트(그 판의 시트) 값 → 직업 기본값 → 0. 이미 있는 칸은 그대로."""
    import judge                                  # 늦은 import — 이관이 있을 때만 직업표를 읽는다
    sheets = snap.get("sheets") or {}
    for b in _bodies(snap):
        for k, v in judge.body_fields(sheets.get(str(b.get("char"))) or b).items():
            b.setdefault(k, v)
    return snap


MIGRATIONS = {0: _m0_prof}   # n → n+1 (0..STATE_VERSION-1 이 다 있어야 한다 — verify_class_foundation)


def state_version_of(doc):
    """스냅샷(또는 요약)의 내용 판 — 판형 1 은 0, 칸이 이상하면 0."""
    if not isinstance(doc, dict) or doc.get("version") == 1:
        return 0
    v = doc.get("state_version", 0)
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def upgrade(snap):
    """되살린 스냅샷 → 지금 꼴. 옛 내용 판이면 이관 함수를 한 판씩(제자리에서 고친다), 판 번호를 지금 것으로."""
    v = state_version_of(snap)
    while v < STATE_VERSION:
        snap = MIGRATIONS[v](snap)
        v += 1
    snap["version"], snap["state_version"] = VERSION, v
    return snap


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
    """몸(snap dict)과 요약(meta dict)을 원자적으로 쓴다. 둘 다 version·state_version 이, 요약에는 saved_at 도 덧붙는다. 반환 = 피클 바이트 수."""
    pkl, mj = paths(state_dir)
    data = pickle.dumps({"version": VERSION, "state_version": STATE_VERSION, **snap}, protocol=pickle.HIGHEST_PROTOCOL)
    _atomic_bytes(pkl, data)
    write_meta(state_dir, meta)
    return len(data)


def write_meta(state_dir, meta):
    """요약만 다시 쓴다(정지 사유 갱신 등 — 몸은 그대로)."""
    _, mj = paths(state_dir)
    doc = {"version": VERSION, "state_version": STATE_VERSION, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           **{k: v for k, v in meta.items() if k not in ("version", "state_version")}}   # 판 번호는 늘 지금 코드의 것(되읽은 옛 요약을 다시 써도)
    _atomic_bytes(mj, (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def read_meta(state_dir):
    """요약(json)만 읽는다 — 론처·상태 API 용(피클을 열지 않는다). 없거나 깨지면 None."""
    _, mj = paths(state_dir)
    try:
        with io.open(mj, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("version") not in READS or not doc.get("run_id"):
        return None
    if state_version_of(doc) > STATE_VERSION:         # 더 새 코드가 멈춘 판 — 이 코드로는 이어가기를 내밀지 않는다
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
    if not isinstance(snap, dict) or snap.get("version") not in READS:
        raise SnapshotError("스냅샷 판형이 다르다")
    if state_version_of(snap) > STATE_VERSION:
        raise SnapshotError("더 새 코드가 쓴 스냅샷이다(내용 판 %d > %d)" % (state_version_of(snap), STATE_VERSION))
    if snap.get("run_id") != meta.get("run_id"):
        raise SnapshotError("스냅샷 몸과 요약이 다른 판이다")
    for k in ("d", "bots", "sheets", "next_turn", "stream_pos", "seed", "started"):
        if k not in snap:
            raise SnapshotError("스냅샷에 %s 가 없다" % k)
    try:
        return upgrade(snap), meta
    except Exception as e:                      # 이관이 깨지면 러너를 죽이지 않고 정직하게 폴백(새 판 + 옛 기록 대피)
        raise SnapshotError("옛 스냅샷을 새 꼴로 올리지 못했다: %s: %s" % (type(e).__name__, str(e)[:120]))


def remove(state_dir):
    """이어갈 몸이 없어졌다(판이 끝났거나 새 판을 시작했다)."""
    for p in paths(state_dir):
        try:
            os.remove(p)
        except OSError:
            pass
