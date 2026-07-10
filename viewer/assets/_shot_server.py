# 검증용 초소형 업로드 서버 — 뷰어 캔버스 스크린샷을 PUT 으로 받는다.
# 개발 도구(게임 무관). 127.0.0.1 전용 — 외부 노출 없음. 쓰기 대상도 _shot.png 한 파일 고정.
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_PUT(self):
        n = int(self.headers.get("content-length", 0))
        data = self.rfile.read(n)
        with open("~/dungeon/viewer/assets/_shot.png", "wb") as f:
            f.write(data)
        self.send_response(200); self._cors(); self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 8001), H).serve_forever()
