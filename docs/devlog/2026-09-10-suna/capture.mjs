// 저장된 실제 원정(seed 457294)을 현재 게임 화면으로 재생해 개발일지용 원본 스크린샷을 만든다.
// 실행: 론처(8000)가 떠 있는 상태에서  D:/node.exe docs/devlog/2026-09-10-suna/capture.mjs
// 화면과 기록을 고치지 않는다. 새 LLM 원정을 실행하지 않는다(읽기 전용 GET만).
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const require = createRequire(path.join(root, 'game/package.json'));
const { chromium } = require('playwright-core');

const run = 'runs/stream-20260910-213929.jsonl';
const raw = await fs.readFile(path.join(root, run), 'utf8');
const rows = raw.trim().split(/\r?\n/).map((line, index) => ({ line: index + 1, row: JSON.parse(line) }));

const shots = [
  { file: '01-lost.png',     turn: 50,  focus: '3', caption: '동료를 시야에서 놓친 수나. 아무에게도 배달되지 않는 외침.' },
  { file: '02-treasure.png', turn: 57,  focus: '3', caption: '혼자 함정을 피하고 보물을 챙긴 뒤, 보여줄 사람을 찾는다.' },
  { file: '03-stairs.png',   turn: 78,  focus: '3', caption: '계단 앞 여섯 번째 시도. 결과는 매번 wait_allies.' },
  { file: '04-alone.png',    turn: 132, focus: '3', caption: '다섯 번째 구역까지 혼자. 대답은 여전히 없다.' },
  { file: '05-reunion.png',  turn: 149, focus: '3', caption: '102틱 만의 재회. 처음으로 "유나 언니"라고 부른다.' },
  { file: '06-yuna.png',     turn: 150, focus: '1', caption: '유나의 대답. 어디 있었냐고 묻지 않는다.' },
];

const base = process.env.WL_GAME_URL || 'http://127.0.0.1:8000/game/';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => errors.push(error.message));
  for (const shot of shots) {
    const url = new URL(base);
    url.searchParams.set('run', run);
    url.searchParams.set('focus', shot.focus);
    url.searchParams.set('t', String(shot.turn));
    await page.goto(url.href, { waitUntil: 'networkidle' });
    await page.waitForFunction(({ turn, focus }) => {
      const app = window.__wl;
      return app?.run && app.scene && app.playback.cur?.turn === turn && app.focus.char === focus;
    }, shot);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(800);
    const grp = page.locator(`#log .grp[data-turn="${shot.turn}"]`);
    if (await grp.count()) await grp.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(here, 'images', shot.file) });
    const source = rows.find(({ row }) => row.kind === 'tick' && row.turn === shot.turn);
    shot.sourceLine = source.line;
    shot.decisions = source.row.decisions;
    shot.events = source.row.events;
    shot.url = url.href;
    console.log(`captured ${shot.file}: t${shot.turn} focus ${shot.focus}, source line ${source.line}`);
  }
  if (errors.length) throw new Error(errors.join('\n'));
  await fs.writeFile(path.join(here, 'sources.json'), JSON.stringify({
    capturedAt: new Date().toISOString(),
    run,
    seed: rows[0].row.seed,
    sha256: createHash('sha256').update(raw).digest('hex'),
    note: '2026-09-10 21:39 의 실제 원정을 같은 날 현재 게임 화면으로 재생한 스크린샷. 원본 대사·사건 무수정.',
    shots,
  }, null, 2) + '\n', 'utf8');
} finally {
  await browser.close();
}
