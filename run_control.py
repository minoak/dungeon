"""판단 실패 시 러너를 멈추고 같은 프로세스에서 재시도한다. 게임 틱과 분리된 제어 파일."""
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

POLICY = "retry-pause-v1"
PAUSE_FILE = "brain_pause.json"
RETRY_FILE = "brain_retry.json"
STOP_FILE = "stop.json"          # D79(09-16) 곱게 멈춤 요청 — 론처가 두고 러너가 다음 틱 머리에서 읽는다


class StopRequested(Exception):
    """정지 요청(D79) — 판단 정지(brain_pause) 대기 중에 사용자가 멈추면 대기 루프가 이걸 던진다(러너가 받아 조용히 닫는다)."""


class PauseTimeout(StopRequested):
    """F1(09-18) 판단 정지가 제한 시간을 넘겼다 — 아무도 재시도를 누르지 않는 판이 자리를 무기한 쥐지 못하게 러너가 스스로 닫는다.
    사용자가 멈춘 것과 같은 길(루프 머리 스냅샷이 진실 → 이어가기 가능)이라 StopRequested 의 한 갈래다."""


class BudgetExhausted(StopRequested):
    """D96(09-20) 이 판에 걸린 LLM 호출 한도에 닿았다 — 판단이 전부 '한도라서 전송 못 함'으로 실패했다.
    재시도를 눌러도 한도는 그대로라 같은 실패가 되풀이되므로 판단 정지를 열지 않고 곧바로 곱게 멈춘다.
    사람이 누른 멈춤·D91 과 같은 길(루프 머리 스냅샷이 진실 → 이어가기 가능)이라 StopRequested 의 한 갈래다.
    이어간 판은 새 러너 프로세스라 한도를 처음부터 다시 센다(파트너 09-20 설계)."""


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path, value):
    """상태 폴링이 반쪽 JSON을 읽지 않도록 같은 폴더에서 교체한다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        json.dump(value, f, ensure_ascii=False)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def reset(state):
    for name in (PAUSE_FILE, RETRY_FILE, STOP_FILE):
        (Path(state) / name).unlink(missing_ok=True)


def request_retry(state, pause_id, pid=None):
    paused = read_json(Path(state) / PAUSE_FILE)
    if (not paused or not pause_id or paused.get("id") != pause_id
            or (pid is not None and paused.get("pid") != pid) or paused.get("retrying")):
        raise ValueError("지금 재시도할 수 있는 판단 정지가 아니다. 상태를 새로 확인해 주세요.")
    write_json(Path(state) / RETRY_FILE, {"id": pause_id})


STOP_REASONS = ("unwatched",)    # D91(09-20) 사람이 누른 멈춤("user") 말고 러너가 그대로 받아 적는 사유 — unwatched = 공개 서버가 관전자 없는 판을 멈췄다


def request_stop(state, pages=True, reason=None):
    """D79 곱게 멈추기 — 러너가 다음 틱 머리에서 읽는다: 수첩 한 장(pages=True, 살아 있는 캐릭터당 1콜)을 쓰고 stopped 줄·스냅샷을 남긴 뒤 스스로 끝난다.
    reason(D91 additive): 사람이 누른 멈춤이 아닐 때만 적는다 — 없으면 옛 모양 그대로(= "user")."""
    write_json(Path(state) / STOP_FILE, {"id": uuid.uuid4().hex, "pages": bool(pages), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                         **({"reason": str(reason)} if reason else {})})


def stop_requested(state):
    """멈춤 요청이 있으면 그 dict, 없으면 None."""
    return read_json(Path(state) / STOP_FILE) or None


def stop_reason(req, default="user"):
    """D91 멈춤 요청(stop.json)이 말하는 사유 — 아는 사유(STOP_REASONS)만 받아 적고, 없거나 모르는 값이면 default(사람이 누른 멈춤)."""
    why = (req or {}).get("reason")
    return why if why in STOP_REASONS else default


def clear_stop(state):
    (Path(state) / STOP_FILE).unlink(missing_ok=True)


class BrainPause:
    def __init__(self, state, writer, names, report=print, limit=0):
        self.state, self.writer, self.names, self.report = Path(state), writer, names, report
        self.active = False
        self.limit = max(0, limit or 0)   # F1(09-18) 한 번의 판단 정지를 기다려 주는 초 — 0 = 끝없이(로컬 기본). 재시도가 또 실패하면 새로 센다

    def wait(self, turn, errors):
        """행동·몬스터 턴 실행 전에 호출. 여기서는 세계나 기억을 건드리지 않는다."""
        entries = [{"char": c, "name": self.names.get(c, c), **dec} for c, dec in errors.items()]
        paused = {"id": uuid.uuid4().hex, "pid": os.getpid(), "turn": turn,
                  "retrying": False, "errors": entries}
        self.active = True
        self.writer.emit("brain_pause", turn=turn, errors=entries)
        write_json(self.state / PAUSE_FILE, paused)
        self.report("[판단 정지] t%d · %s — 게임 시간이 멈췄습니다. 관전 화면에서 판단 재시도를 누르세요."
                    % (turn, ", ".join(e["name"] for e in entries)))
        self.report('콘솔 재시도: python run_control.py --state "%s" retry' % self.state)
        t0 = time.monotonic()
        while True:
            if stop_requested(self.state):        # D79: 판단 정지 중 사용자가 멈춤 — 재시도 없이 조용히 닫는다(루프 머리 스냅샷이 진실)
                raise StopRequested()
            if self.limit and time.monotonic() - t0 >= self.limit:   # F1: 제한 시간 동안 아무도 재시도를 안 눌렀다
                raise PauseTimeout()
            request = read_json(self.state / RETRY_FILE)
            if request.get("id") == paused["id"]:
                (self.state / RETRY_FILE).unlink(missing_ok=True)
                write_json(self.state / PAUSE_FILE, {**paused, "retrying": True})
                self.writer.emit("brain_retry", turn=turn, chars=list(errors))
                return
            time.sleep(0.2)

    def resolved(self, turn):
        if self.active:
            self.writer.emit("brain_resumed", turn=turn)
            reset(self.state)
            self.active = False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="멈춘 원정의 모델 판단 재시도")
    parser.add_argument("--state", default=str(Path(__file__).parent / "state"))
    parser.add_argument("command", choices=["retry"])
    args = parser.parse_args()
    try:
        request_retry(args.state, read_json(Path(args.state) / PAUSE_FILE).get("id"))
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
    print("판단 재시도를 요청했습니다.")
