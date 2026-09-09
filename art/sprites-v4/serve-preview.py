"""에셋 검토용 론처. 파티·실행 로그는 임시 폴더에 쓰고 규칙 두뇌를 기본으로 쓴다."""
import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import launcher

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8766)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix="wl_art_preview_") as tmp:
    tmp = Path(tmp)
    server = launcher.make_server("127.0.0.1", args.port, root=str(ROOT),
                                  party_path=str(tmp / "party.json"), state_dir=str(tmp / "state"),
                                  runs_dir=str(tmp / "runs"), brain="dummy")
    print(f"http://127.0.0.1:{args.port}/art/sprites-v4/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.ctx.runner.stop()
        server.server_close()
