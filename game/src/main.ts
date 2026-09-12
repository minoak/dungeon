// 부트 — 에셋 사전(atlas·tiles) → Phaser → 씬 준비 → UI 설치 → 판 로드(URL ?run= ?focus= ?t=).
import './style.css';
import '../../viewer/assets/skills.css';
import Phaser from 'phaser';
import { App } from './app';
import { DungeonScene } from './scene/DungeonScene';
import { fetchAtlas } from './assets/sd';
import { fetchTiles } from './assets/tiles';
import { installControls } from './ui/Controls';
import { installChips } from './ui/Chips';
import { installFocusCard } from './ui/FocusCard';
import { installLog } from './ui/Log';
import { installBubbles } from './scene/Bubbles';
import { installFog } from './scene/Fog';
import { installHandoff } from './fx/Handoff';
import { installLive } from './stream/live';
import { STATIC, fetchRunIndex } from './paths';

declare global { interface Window { __wl?: App } }

async function boot(): Promise<void> {
  const app = new App();
  window.__wl = app;
  // 오류 문구는 #hud 의 제 자리(span)에만 — 라이브 배지(installLive) 등 다른 HUD 요소를 지우지 않는다. 판이 열리면 숨긴다.
  const errEl = document.createElement('span');
  errEl.id = 'hudError'; errEl.className = 'badge'; errEl.hidden = true;
  app.dom.hud.appendChild(errEl);
  app.bus.on('error', msg => { errEl.textContent = msg; errEl.hidden = false; });
  app.bus.on('run', () => { errEl.hidden = true; });
  const [atlas, tiles] = await Promise.all([fetchAtlas(), fetchTiles()]);
  const sceneReady = new Promise<DungeonScene>(res => { app.bus.on('scene', res); });
  const game = new Phaser.Game({
    type: Phaser.AUTO, parent: 'stage', pixelArt: true, roundPixels: true, backgroundColor: '#0a0b0e',
    scale: { mode: Phaser.Scale.RESIZE, width: '100%', height: '100%' },
    audio: { noAudio: true }, banner: false, scene: [],
  });
  app.game = game;
  // 기록 접기·반응형 배치로 무대 크기만 변해도 캔버스와 카메라가 즉시 따라간다.
  const stageSize = new ResizeObserver(([entry]) => {
    const w = Math.round(entry.contentRect.width), h = Math.round(entry.contentRect.height);
    if (w > 0 && h > 0 && (game.scale.width !== w || game.scale.height !== h)) {
      // RESIZE 모드는 부모 크기의 캐시를 사용하므로 먼저 새 경계를 읽어야 한다.
      game.scale.getParentBounds(); game.scale.refresh();
    }
  });
  stageSize.observe(app.dom.stage);
  game.events.once('destroy', () => stageSize.disconnect());
  game.scene.add('dungeon', new DungeonScene(), true, { app, atlas, tiles });
  app.scene = await sceneReady;

  installControls(app); installChips(app);
  installFocusCard(app); installLog(app); installBubbles(app); installFog(app); installHandoff(app);   // Phase B 카드
  installLive(app);                                                                                     // B5 라이브 배지(론처 /api/status)
  if (STATIC) {                                  // 정적 배포(paths.STATIC) — 론처가 없으니 시작 화면 링크는 리포로
    for (const a of document.querySelectorAll<HTMLAnchorElement>('a[href="/launcher/"]')) {
      a.href = 'https://github.com/minoak/dungeon'; a.target = '_blank'; a.rel = 'noopener';
      if (a.classList.contains('home-link')) a.innerHTML = 'GitHub <span aria-hidden="true">↗</span>';
    }
  }

  const q = new URLSearchParams(location.search);
  const t = q.get('t');
  // 정적 배포: 라이브 판이 없다 — 기본 판은 runs/index.json 의 첫 항목(static-bundle.mjs 가 첨부한 판)
  const fallback = STATIC ? ((await fetchRunIndex())?.runs[0]?.path ?? '') : 'state/stream.jsonl';
  const run = q.get('run') || fallback;
  if (!run) { app.bus.emit('error', '첨부된 판이 없다 (runs/index.json)'); return; }
  await app.loadRun(run, { focus: q.get('focus'), turn: t ? +t : null });
}

boot().catch(e => {
  console.error(e);
  const hud = document.getElementById('hud');
  if (hud) hud.textContent = '부팅 실패: ' + (e instanceof Error ? e.message : String(e));
});
