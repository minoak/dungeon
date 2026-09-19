import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..'),game=path.join(root,'game');
const require=createRequire(path.join(game,'package.json'));
const {chromium}=require('playwright-core');
const {createServer}=await import(pathToFileURL(path.join(game,'node_modules/vite/dist/node/index.js')).href);
const server=await createServer({root:game,configFile:path.join(game,'vite.config.ts'),server:{port:4216,strictPort:true,hmr:false,host:'127.0.0.1'}});
await server.listen();
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:4216/game/?run=art/town-v3/preview-run.jsonl&focus=1&t=1');
 await page.waitForFunction(()=>window.__wl?.playback.cur?.turn===1);
 const info=await page.evaluate(()=>{const a=window.__wl;return {buildings:a.playback.cur.level.visual.buildings.length,textures:['guild','temple','tavern','gate','general_store','blacksmith','craft_workshop','equipment_store','shared_lodging','small_home','ordinary_inn','garden_inn'].map(n=>a.game.textures.exists('wl-town-'+n))}});
 assert.equal(info.buildings,14);assert(info.textures.every(Boolean));
 assert(await page.evaluate(()=>window.__wl.playback.cur.level.visual.props.every(p=>window.__wl.game.textures.get('wl-town-props').has(p.frame))),'all scenery frames loaded');
 assert(await page.evaluate(()=>{
   const a=window.__wl,V=a.playback.cur.level.visual;
   return V.paving?.drains.length>0 && V.ground.filter(g=>g.frame!==undefined).every(g=>
     a.game.textures.get('wl-town-terrain').has(g.frame) && a.scene.map.getTileAt(g.rect[0]+V.offset[0],g.rect[1]+V.offset[1]).index===g.frame);
 }),'paving material frames reached the actual tilemap');
  await page.waitForTimeout(400);await page.screenshot({path:path.join(here,'game-preview.png')});
  await page.evaluate(()=>{const a=window.__wl,c=a.scene.cameras.main,L=a.playback.cur.level;const tile=a.scene.map.tileWidth;
    c.stopFollow();a.scene.setZoom(Math.min(c.width/(L.w*tile),c.height/(L.h*tile))*.9);c.centerOn(L.w*tile/2,L.h*tile/2);
  });
  await page.waitForTimeout(200);await page.screenshot({path:path.join(here,'game-overview.png')});
 // 이전 판도 신규 엔티티 없이 기존 시각 레이어 그대로 열린다.
 await page.goto('http://127.0.0.1:4216/game/?run=runs/stream-20260909-203709.jsonl&focus=1&t=5');
 await page.waitForFunction(()=>window.__wl?.playback.cur?.turn===5);
 assert.deepEqual(errors,[]);
 await fs.mkdir(path.join(here,'verification'),{recursive:true});await fs.writeFile(path.join(here,'verification/game.json'),JSON.stringify({passed:true,newMap:true,oldReplay:true,llmCalls:0,errors},null,2));
 console.log('PASS — 실제 게임 클라이언트 새 마을·건물 12종·옛 판 리플레이·스크립트 오류 없음');
}finally{await browser.close();await server.close()}
