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
    for name in (PAUSE_FILE, RETRY_FILE):
        (Path(state) / name).unlink(missing_ok=True)


def request_retry(state, pause_id, pid=None):
    paused = read_json(Path(state) / PAUSE_FILE)
    if (not paused or not pause_id or paused.get("id") != pause_id
            or (pid is not None and paused.get("pid") != pid) or paused.get("retrying")):
        raise ValueError("지금 재시도할 수 있는 판단 정지가 아니다. 상태를 새로 확인해 주세요.")
    write_json(Path(state) / RETRY_FILE, {"id": pause_id})


class BrainPause:
    def __init__(self, state, writer, names, report=print):
        self.state, self.writer, self.names, self.report = Path(state), writer, names, report
        self.active = False

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
        while True:
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
