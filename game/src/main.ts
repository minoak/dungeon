// 부트 — 에셋 사전(atlas·tiles) → Phaser → 씬 준비 → UI 설치 → 판 로드(URL ?run= ?focus= ?t=).
import './style.css';
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

declare global { interface Window { __wl?: App } }

async function boot(): Promise<void> {
  const app = new App();
  window.__wl = app;
  app.bus.on('error', msg => { app.dom.hud.textContent = msg; });
  const [atlas, tiles] = await Promise.all([fetchAtlas(), fetchTiles()]);
  const sceneReady = new Promise<DungeonScene>(res => { app.bus.on('scene', res); });
  const game = new Phaser.Game({
    type: Phaser.AUTO, parent: 'stage', pixelArt: true, roundPixels: true, backgroundColor: '#0a0b0e',
    scale: { mode: Phaser.Scale.RESIZE, width: '100%', height: '100%' },
    audio: { noAudio: true }, banner: false, scene: [],
  });
  app.game = game;
  game.scene.add('dungeon', new DungeonScene(), true, { app, atlas, tiles });
  app.scene = await sceneReady;

  installControls(app); installChips(app);
  installFocusCard(app); installLog(app); installBubbles(app); installFog(app); installHandoff(app);   // Phase B 카드

  const q = new URLSearchParams(location.search);
  const t = q.get('t');
  await app.loadRun(q.get('run') || 'state/stream.jsonl', { focus: q.get('focus'), turn: t ? +t : null });
}

boot().catch(e => {
  console.error(e);
  const hud = document.getElementById('hud');
  if (hud) hud.textContent = '부팅 실패: ' + (e instanceof Error ? e.message : String(e));
});
