# -*- coding: utf-8 -*-
"""캠페인 — 판 기록(스트림)의 0콜 투영(D78, 2026-09-16 파트너 "저장 시점은 마지막 기록에서" · "던전에서 이어가게 하자").

저장한 캐릭터(론처 프리셋 id)는 원정을 넘어 기억한다. 몸(HP·장비·물약·축복)은 매 원정 새로 태어나고, 남는 것은 **기록**이다:
원정 이력(시드·시작·결과·도달 층·틱·의뢰·함께 간 동료) · 수첩 장(층을 떠날 때 쓴 것, D59) · 도감평 한 줄(D55) · 생사.
러너는 이 파일을 모른다 — 러너가 남긴 스트림을 **마지막 줄까지** 읽어 캐릭터별로 접는다(도감 발급기 bestiary.py 와 같은 소비자 구조).
그래서 끊긴 판(론처 중지·서버 재시작, `end` 없음)도 끊긴 자리까지가 기록이고, 진행 중인 판은 "지금 3층 158틱"으로 보인다.

  · 판 식별 = run_id = "<seed>@<run_meta.started>" — 같은 판을 다시 접어도 같은 항목(멱등). state/stream.jsonl 이 다음 판
    시작 때 runs/ 로 복사돼도 같은 run_id 라 두 번 세지 않는다.
  · status: `end` 있음 = ended(outcome) · 없고 러너가 살아 있음 = running · 없고 러너 없음 = stopped(끊긴 원정, ②-b 이어가기의 대상).
  · 저장한 캐릭터만 이어진다: run_meta.party[].id 가 없는 캐릭터(즉석 슬롯·기본 파티)는 캠페인에 안 실린다(1회용).
  · 이어간 판(D79): 같은 파일에 `stopped`(멈추며 쓴 수첩 장)·`resume` 줄이 붙고 틱이 이어진다 — run_id 그대로 한 항목(segments = 이어간 횟수).
  · 파일 = <파티 폴더>/campaign.json {version, characters{pid: {name, runs{run_id: 항목}}}, sources{키: "크기:mtime"}} — 아카이브는
    한 번만 읽고(서명 같으면 건너뜀), 현재 판(state)은 러너가 살아 있는 동안 부를 때마다 다시 읽는다.
LLM 0콜 · 엔진·러너 무접촉 · 순수 파일. 론처(launcher.Ctx.campaign)가 /api/characters 때 refresh 한다.
"""
import glob
import io
import json
import os
import tempfile
import time

VERSION = 1
OUTCOME_KR = {"returned": "귀환", "escaped": "탈출", "wiped": "전멸", "timeout": "시간 초과"}
STATUS_KR = {"running": "진행 중", "stopped": "중단", "ended": "끝남"}


def _iter(path):
    """스트림 줄 단위 — 쓰는 중인 마지막 반 줄은 거기서 멈춘다(그때까지가 기록)."""
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                return


def project(path, running=False):
    """스트림 하나 → 판 투영(마지막 줄까지). run_meta 가 없으면 None.
    {run_id, seed, started, status, outcome, warped, turn_last, depth_last, depth_max, segments, stops, quests_accepted[], quests_done[],
     party[{char, name, id?, job}], chars{char: {name, id, job, alive, hp, died_turn, pages[], book_lines[]}}}"""
    meta = None
    depth = depth_max = turn_last = 0
    segments = stops = 0                      # D79 이어간 횟수·수첩 쓰고 멈춘 횟수
    end = None
    chars = {}
    for rec in _iter(path):
        k = rec.get("kind")
        if k == "run_meta":
            meta = rec
            for p in rec.get("party") or []:
                c = str(p.get("char"))
                chars[c] = {"name": p.get("name") or ("봇%s" % c), "id": p.get("id"), "job": p.get("job"),
                            "alive": True, "hp": p.get("maxhp"), "died_turn": None, "pages": [], "book_lines": []}
            continue
        if meta is None:
            continue
        if k == "level":
            depth = int(rec.get("depth") or 0)
            depth_max = max(depth_max, depth)
        elif k == "tick":
            turn_last = int(rec.get("turn") or turn_last)
            for b in rec.get("bots") or []:
                c = chars.get(str(b.get("char")))
                if c is None:
                    continue
                c["hp"] = b.get("hp", c["hp"])
                if c["alive"] and b.get("alive") is False:
                    c["alive"], c["died_turn"] = False, turn_last
            for ch, d in (rec.get("decisions") or {}).items():
                bl = (d or {}).get("book_line") if isinstance(d, dict) else None
                if bl and str(ch) in chars and bl.get("text"):
                    chars[str(ch)]["book_lines"].append({"turn": turn_last, "key": bl.get("key"), "text": bl.get("text")})
        elif k in ("descend", "ascend"):
            turn_last = int(rec.get("turn") or turn_last)
            for ch, page in (rec.get("pages") or {}).items():
                if str(ch) in chars and page:
                    chars[str(ch)]["pages"].append({"turn": turn_last, "depth": depth, "text": page})
        elif k == "stopped":                       # D79 수첩 쓰고 멈춤 — 멈추기 전에 쓴 수첩 장(캐릭터별, stop 표식)
            turn_last = int(rec.get("turn") or turn_last)
            stops += 1
            for ch, page in (rec.get("pages") or {}).items():
                if str(ch) in chars and page:
                    chars[str(ch)]["pages"].append({"turn": turn_last, "depth": depth, "text": page, "stop": True})
        elif k == "resume":                        # D79 이어가기 — 같은 판이 이어진다(run_id 그대로)
            segments += 1
        elif k == "end":
            end = rec
            turn_last = int(rec.get("turn") or turn_last)
    if meta is None:
        return None
    quests = (end or {}).get("quests") or {}
    return {"run_id": "%s@%s" % (meta.get("seed"), meta.get("started") or ""),
            "seed": meta.get("seed"), "started": meta.get("started"),
            "status": "ended" if end else ("running" if running else "stopped"),
            "outcome": (end or {}).get("outcome"), "warped": bool((end or {}).get("warped")),
            "turn_last": turn_last, "depth_last": depth, "depth_max": depth_max, "segments": segments, "stops": stops,
            "quests_accepted": [q.get("id") for q in (quests.get("accepted") or []) if isinstance(q, dict)],
            "quests_done": sorted((quests.get("done") or {}).keys()),
            "party": [{"char": c, "name": v["name"], "id": v.get("id"), "job": v.get("job")} for c, v in sorted(chars.items())],
            "chars": chars}


def outcome_kr(entry):
    """한 항목의 결과 한마디 — 끝난 판은 결과, 아니면 상태."""
    if entry.get("status") == "ended":
        return OUTCOME_KR.get(entry.get("outcome"), entry.get("outcome") or "끝남")
    return STATUS_KR.get(entry.get("status"), entry.get("status") or "")


class Book:
    """<파티 폴더>/campaign.json — 캐릭터(프리셋 id)별 원정 항목."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.data = self._load()

    def _load(self):
        try:
            with io.open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, dict) and doc.get("version") == VERSION and isinstance(doc.get("characters"), dict):
                doc.setdefault("sources", {})
                return doc
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            pass                                          # 깨진 파일 = 빈 캠페인으로 시작하되 덮어쓰기 전에 대피
            try:
                os.replace(self.path, self.path + ".corrupt")
            except OSError:
                pass
        return {"version": VERSION, "characters": {}, "sources": {}}

    def _save(self):
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".campaign-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
                f.write("\n")
            for i in range(20):                       # Windows: 방금 쓴 파일을 색인기·백신이 잠깐 잡으면 replace 가 WinError 5 —
                try:                                  #   bestiary.save 와 같은 처방(짧게 물러섰다 재시도)
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if i == 19:
                        raise
                    time.sleep(0.05 * (i + 1))
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @staticmethod
    def _sig(path):
        st = os.stat(path)
        return "%d:%d" % (st.st_size, int(st.st_mtime))

    def fold(self, stream_path, running=False, key=None):
        """스트림 하나를 접어 넣는다. 반환 = 바뀌었나. 아카이브(running=False)는 서명이 같으면 건너뛴다."""
        if not os.path.isfile(stream_path):
            return False
        key = key or os.path.basename(stream_path)
        sig = self._sig(stream_path) + (":r" if running else "")   # 러너가 살아 있던 때의 서명엔 :r — 러너가 죽으면 파일이 그대로여도 다시 접어 stopped 로
        if not running and self.data["sources"].get(key) == sig:
            return False
        proj = project(stream_path, running)
        if proj is None:
            self.data["sources"][key] = sig
            return False
        others = {c: v["name"] for c, v in proj["chars"].items()}
        changed = False
        for c, v in proj["chars"].items():
            pid = v.get("id")
            if not pid:
                continue                                  # 저장한 캐릭터만 이어진다(1회용은 기록 없음)
            ch = self.data["characters"].setdefault(pid, {"name": v["name"], "runs": {}})
            ch["name"] = v["name"]
            entry = {"run_id": proj["run_id"], "seed": proj["seed"], "started": proj["started"], "status": proj["status"],
                     "outcome": proj["outcome"], "warped": proj["warped"], "turn_last": proj["turn_last"],
                     "depth_last": proj["depth_last"], "depth_max": proj["depth_max"], "segments": proj.get("segments", 0),
                     "alive_last": v["alive"], "hp_last": v["hp"], "died_turn": v["died_turn"],
                     "quests_accepted": proj["quests_accepted"], "quests_done": proj["quests_done"],
                     "party": [{"char": oc, "name": nm, "id": proj["chars"][oc].get("id")} for oc, nm in sorted(others.items()) if oc != c],
                     "pages": v["pages"], "book_lines": v["book_lines"], "source": key}
            if ch["runs"].get(proj["run_id"]) != entry:
                ch["runs"][proj["run_id"]] = entry
                changed = True
        self.data["sources"][key] = sig
        if changed or True:                               # sources 갱신도 저장(아카이브를 매번 다시 읽지 않게)
            self._save()
        return changed

    def refresh(self, state_stream, runs_dir, running=False):
        """runs/ 아카이브(한 번씩) + 현재 판(state)을 접는다. 반환 = 바뀐 수."""
        n = 0
        if runs_dir and os.path.isdir(runs_dir):
            for p in sorted(glob.glob(os.path.join(runs_dir, "stream-*.jsonl"))):
                n += bool(self.fold(p, False, key=os.path.basename(p)))
        if state_stream and os.path.isfile(state_stream):
            n += bool(self.fold(state_stream, running, key="state"))
        return n

    def runs(self, pid):
        """한 캐릭터의 원정 항목 — 최근 것부터."""
        ch = self.data["characters"].get(pid) or {}
        return sorted((ch.get("runs") or {}).values(), key=lambda e: (e.get("started") or "", e.get("run_id")), reverse=True)

    def summary(self, pid):
        """화면 한 줄용 — {runs, running, stopped, by_outcome{}, deaths, depth_max, last{started,status,outcome,depth_last,turn_last,label}} 또는 None."""
        rs = self.runs(pid)
        if not rs:
            return None
        by = {}
        for e in rs:
            if e.get("status") == "ended":
                by[e.get("outcome") or "?"] = by.get(e.get("outcome") or "?", 0) + 1
        last = rs[0]
        return {"runs": len(rs),
                "running": sum(1 for e in rs if e.get("status") == "running"),
                "stopped": sum(1 for e in rs if e.get("status") == "stopped"),
                "by_outcome": by,
                "deaths": sum(1 for e in rs if e.get("died_turn") is not None),
                "depth_max": max((e.get("depth_max") or 0) for e in rs),
                "last": {"started": last.get("started"), "status": last.get("status"), "outcome": last.get("outcome"),
                         "depth_last": last.get("depth_last"), "turn_last": last.get("turn_last"), "segments": last.get("segments", 0),
                         "label": "%s층 %s" % (last.get("depth_last"), outcome_kr(last))}}
