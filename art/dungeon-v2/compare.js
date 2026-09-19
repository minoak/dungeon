const $ = id => document.getElementById(id);
const frames = [$('prototype'), $('baseline')];
let apps = [], level = null, active = 0, seed = 7, profile = 'concept', camera = null, loading = false;
const status = text => { $('status').textContent = text; };
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const source = seed => `api/dungeon-preview.jsonl?seed=${seed}&profile=${profile}`;
const gameUrl = (seed, prototype) => '/game/?' + new URLSearchParams({ run: source(seed), t: '1', dungeonArt: prototype ? 'prototype' : 'flat' });

async function ready(frame) {
  for (let i = 0; i < 400; i++) {
    const a = frame.contentWindow?.__wl;
    if (a?.scene?.frame && a?.run?.meta?.seed === seed) return a;
    const error = frame.contentDocument?.getElementById('hudError');
    if (error && !error.hidden && error.textContent) throw new Error(error.textContent);
    await pause(50);
  }
  throw new Error('게임 화면을 불러오지 못했습니다. 빌드와 로컬 서버를 확인해 주세요.');
}
function embed(frame) {
  if (frame.contentDocument.getElementById('lab-style')) return;
  const style = frame.contentDocument.createElement('style');
  style.id = 'lab-style';
  style.textContent = 'html,body{overflow:hidden!important}#app{display:block!important;padding:0!important;height:100vh!important}#topbar,#side,#bottom,#hud,#sceneCaption,.stage-help{display:none!important}#stage{width:100vw!important;height:100vh!important;min-height:0!important;border:0!important;border-radius:0!important;margin:0!important}';
  frame.contentDocument.head.append(style);
}
function applyCamera() {
  if (!level || !camera) return;
  for (const a of apps) {
    const s = a.scene, c = s.cameras.main;
    c.stopFollow(); c.panEffect.reset(); s.followChar = null;
    c.removeBounds(); // The full map can be smaller than the viewport at overview zoom.
    s.setZoom(camera.zoom);
    c.centerOn(camera.x, camera.y);
  }
  minimap();
}
function viewRoom() {
  if (!level) return;
  const c = apps[0].scene.cameras.main;
  const room = level.rooms.find(r => String(r.id) === $('room').value);
  camera = room
    ? { x: (room.x + room.w / 2) * 48, y: (room.y + room.h / 2) * 48, zoom: Math.min(1.7, c.width / ((room.w + 6) * 48), c.height / ((room.h + 5) * 48)) }
    : { x: level.w * 24, y: level.h * 24 - 24, zoom: Math.min(c.width / (level.w * 48 + 96), c.height / (level.h * 48 + 144)) };
  applyCamera();
}
function visibility() {
  for (const a of apps) {
    a.focus.char = $('fog').checked ? '1' : null;
    a.focus.emit('change', { char: a.focus.char, prev: null });
    a.scene.applyFrame({ prev: null, cur: a.playback.cur, mode: 'seek' });
  }
  if ($('fog').checked) {
    const b = apps[0].playback.cur.bots.find(b => b.char === '1');
    camera = { x: (b.x + .5) * 48, y: (b.y + .5) * 48, zoom: 1.3 };
  }
  applyCamera();
}
function minimap() {
  if (!level) return;
  const canvas = $('minimap');
  canvas.width = level.w * 8; canvas.height = level.h * 8;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#0b1119'; ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (let y = 0; y < level.h; y++) for (let x = 0; x < level.w; x++) {
    const cell = level.grid[y][x];
    if (cell === '#') continue;
    ctx.fillStyle = cell === '+' ? '#bd9860' : '#697577'; ctx.fillRect(x * 8, y * 8, 7, 7);
  }
  if (camera) {
    const c = apps[active].scene.cameras.main;
    const w = c.width / camera.zoom / 48 * 8, h = c.height / camera.zoom / 48 * 8;
    ctx.strokeStyle = '#f1d09b'; ctx.lineWidth = 1.5;
    ctx.strokeRect(camera.x / 48 * 8 - w / 2, camera.y / 48 * 8 - h / 2, w, h);
  }
}
function setArt(index) {
  active = index;
  frames.forEach((f, i) => f.classList.toggle('hidden', i !== index));
  $('new-art').setAttribute('aria-pressed', String(index === 0));
  $('old-art').setAttribute('aria-pressed', String(index === 1));
  $('open-game').href = gameUrl(seed, index === 0);
  applyCamera();
}
async function generate() {
  if (loading || !$('seed-form').reportValidity()) return;
  loading = true;
  $('generate').disabled = $('random').disabled = true;
  seed = Number($('seed').value);
  profile = $('layout').value;
  status(`시드 ${seed}의 실제 던전을 생성하고 있습니다.`);
  try {
    if (!apps.length) {
      frames.forEach((f, i) => { f.src = gameUrl(seed, i === 0); });
      apps = await Promise.all(frames.map(ready));
      frames.forEach(embed);
      await pause(180);
    } else {
      await Promise.all(apps.map(a => a.loadRun(source(seed), { focus: '1', turn: 1 })));
      if (apps.some(a => a.run?.meta.seed !== seed || a.run?.meta.art_profile !== profile)) throw new Error('새 시드 로드에 실패했습니다.');
    }
    level = apps[0].playback.cur.level;
    if (JSON.stringify(level.grid) !== JSON.stringify(apps[1].playback.cur.level.grid)) throw new Error('비교 화면의 격자가 다릅니다.');
    const select = $('room'); select.replaceChildren(new Option('전체 지도', 'all'));
    const styles = { pillared_hall: '네 기둥 홀', hall: '대홀', gallery: '회랑', chamber: '작은 방', two_columns: '쌍기둥 방' };
    for (const r of level.rooms) select.add(new Option(`방 ${r.id + 1} · ${styles[r.art_style] ?? '일반 방'} · ${r.w}×${r.h}`, String(r.id)));
    const largest = [...level.rooms].sort((a, b) => b.w * b.h - a.w * a.h)[0];
    if (largest && profile === 'original') select.value = String(largest.id);
    viewRoom(); visibility(); setArt(active);
    const floor = level.grid.join('').split('').filter(c => '.+'.includes(c)).length;
    const columns = level.grid.reduce((count,row,y) => count + [...row].filter((c,x) => c === '#' && [[x-1,y],[x+1,y],[x,y-1],[x,y+1]].every(([xx,yy]) => '.+'.includes(level.grid[yy]?.[xx] ?? '#'))).length, 0);
    $('stats').textContent = `시드 ${seed} · ${level.w}×${level.h} · 방 ${level.rooms.length}개 · 독립 기둥 ${columns}개 · 보행 ${floor}칸`;
    status('시드마다 방 배치와 통로 연결이 달라집니다. 입체 재구축 / 직전 구현은 같은 던전을 표시합니다.');
    history.replaceState(null, '', '?seed=' + seed + '&profile=' + profile);
    window.dungeonLab = { seed, profile, level, apps, get camera() { return camera; }, ready: true };
  } catch (error) { status('오류: ' + error.message); console.error(error); }
  finally { loading = false; $('generate').disabled = $('random').disabled = false; }
}
$('seed-form').addEventListener('submit', e => { e.preventDefault(); generate(); });
$('random').onclick = () => { $('seed').value = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483648; generate(); };
$('room').onchange = viewRoom;
$('layout').onchange = generate;
$('fog').onchange = visibility;
$('new-art').onclick = () => setArt(0); $('old-art').onclick = () => setArt(1);
for (const [id, amount] of [['zoom-in', 1.25], ['zoom-out', .8]]) $(id).onclick = () => { if (camera) { camera.zoom = Math.max(.2, Math.min(3, camera.zoom * amount)); applyCamera(); } };
$('minimap').onclick = e => { if (!camera) return; const r = e.currentTarget.getBoundingClientRect(); camera.x = (e.clientX - r.left) / r.width * level.w * 48; camera.y = (e.clientY - r.top) / r.height * level.h * 48; applyCamera(); };
window.addEventListener('resize', () => setTimeout(applyCamera, 150));
const initial = new URLSearchParams(location.search).get('seed');
if (new URLSearchParams(location.search).get('profile') === 'original') $('layout').value = 'original';
if (initial && /^\d{1,10}$/.test(initial) && Number(initial) <= 2147483647) $('seed').value = initial;
generate();
