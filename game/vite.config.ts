// 원더랜드 게임 클라이언트 — Vite 설정.
// base '/game/' = 론처(launcher.py, 8000)가 game/dist/ 를 /game/ 으로 서빙하는 배포 경로와 같다.
// 개발·프리뷰에서는 wlStatic 플러그인이 리포 루트의 /viewer /runs /state /art 를 대신 서빙한다
// (론처 없이도 판 파일·에셋을 읽는다). /api/status 는 더미 응답(라이브는 론처가 있어야 한다).
import { defineConfig, type Plugin } from 'vite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { IncomingMessage, ServerResponse } from 'node:http';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');   // dungeon/
const PREFIXES = ['/viewer/', '/runs/', '/state/', '/art/'];
const MIME: Record<string, string> = {
  '.json': 'application/json; charset=utf-8', '.jsonl': 'application/x-ndjson; charset=utf-8',
  '.png': 'image/png', '.js': 'text/javascript; charset=utf-8', '.html': 'text/html; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8', '.css': 'text/css; charset=utf-8', '.md': 'text/markdown; charset=utf-8',
};

function wlStatic(): Plugin {
  const handler = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const p = decodeURIComponent(new URL(req.url || '/', 'http://x').pathname);
    if (p === '/api/status') {                       // 론처 없는 개발 모드 — 라이브 아님을 알린다
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.end(JSON.stringify({ running: false, dev: true, seed: null, turn: null, outcome: null }));
      return;
    }
    if (!PREFIXES.some(pre => p.startsWith(pre))) return next();
    if (p.includes('..')) { res.statusCode = 400; res.end('bad path'); return; }
    const file = path.join(ROOT, p);
    let st: fs.Stats;
    try { st = fs.statSync(file); } catch { res.statusCode = 404; res.end('not found'); return; }
    if (st.isDirectory()) {                          // python SimpleHTTPRequestHandler 의 색인과 같은 모양(<a href="이름">)
      const items = fs.readdirSync(file).map(n => {
        const dir = fs.statSync(path.join(file, n)).isDirectory();
        const h = encodeURIComponent(n) + (dir ? '/' : '');
        return `<li><a href="${h}">${h}</a></li>`;
      }).join('\n');
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end(`<!DOCTYPE html><html><body><ul>\n${items}\n</ul></body></html>`);
      return;
    }
    res.setHeader('Content-Type', MIME[path.extname(file).toLowerCase()] || 'application/octet-stream');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Length', String(st.size));
    fs.createReadStream(file).pipe(res);
  };
  return {
    name: 'wl-static',
    configureServer(server) { server.middlewares.use(handler); },
    configurePreviewServer(server) { server.middlewares.use(handler); },
  };
}

export default defineConfig({
  base: '/game/',
  plugins: [wlStatic()],
  // WL_NOHMR=1 → HMR 끔(다른 손이 편집 중인 트리에서 dev 서버 상대로 스모크를 돌릴 때 페이지 재로드를 막는다 — B6)
  server: { port: 5173, host: '127.0.0.1', ...(process.env.WL_NOHMR ? { hmr: false } : {}) },
  preview: { port: 4173, host: '127.0.0.1' },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 2000 },
});
