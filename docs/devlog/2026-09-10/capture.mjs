// 저장된 실제 원정을 현재 게임 화면으로 재생해 개발일지용 원본 스크린샷을 만든다.
// 실행: D:/node.exe docs/devlog/2026-09-10/capture.mjs
// 화면과 기록을 고치거나 새 LLM 원정을 실행하지 않는다.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const require = createRequire(path.join(root, 'game/package.json'));
const { chromium } = require('playwright-core');
const run = 'runs/stream-20260909-203709.jsonl';
const raw = await fs.readFile(path.join(root, run), 'utf8');
const rows = raw.trim().split(/\r?\n/).map((line, index) => ({ line: index + 1, row: JSON.parse(line) }));
const shots = [
  { file: '01-armor.png', turn: 179, focus: '2', caption: '수나가 유나에게 가죽 갑옷을 건네고, 실제 방어구가 바뀐다.' },
  { file: '02-comfort.png', turn: 182, focus: '1', caption: '고블린을 처치한 다음, 유나가 수나의 머리를 쓰다듬는다.' },
  { file: '03-relationship.png', turn: 246, focus: '2', caption: '거미와 싸운 뒤의 걱정, 수나가 남긴 동료 평가, 중간에 잘린 친목 지문.' },
];
await fs.mkdir(path.join(here, 'images'), { recursive: true });
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => errors.push(error.message));
  for (const shot of shots) {
    const url = new URL(process.env.WL_GAME_URL || 'http://127.0.0.1:4197/game/');
    url.searchParams.set('run', run);
    url.searchParams.set('focus', shot.focus);
    url.searchParams.set('t', String(shot.turn));
    await page.goto(url.href, { waitUntil: 'networkidle' });
    await page.waitForFunction(({ turn, focus }) => {
      const app = window.__wl;
      return app?.run && app.scene && app.playback.cur?.turn === turn && app.focus.char === focus;
    }, shot);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(700);
    await page.locator(`#log .grp[data-turn="${shot.turn}"]`).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(here, 'images', shot.file) });
    const source = rows.find(({ row }) => row.kind === 'tick' && row.turn === shot.turn);
    shot.sourceLine = source.line;
    shot.events = source.row.events;
    shot.decisions = source.row.decisions;
    shot.url = url.href;
    console.log(`captured ${shot.file}: t${shot.turn}, source line ${source.line}`);
  }
  if (errors.length) throw new Error(errors.join('\n'));
  await fs.writeFile(path.join(here, 'sources.json'), JSON.stringify({
    capturedAt: new Date().toISOString(),
    run,
    sha256: createHash('sha256').update(raw).digest('hex'),
    note: '2026-09-09의 실제 원정을 2026-09-10 현재 그래픽으로 다시 재생한 스크린샷. 원본 대사·사건 무수정.',
    shots,
  }, null, 2) + '\n', 'utf8');
} finally {
  await browser.close();
}
