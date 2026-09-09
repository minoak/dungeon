// 재생 컨트롤 — 판 선택 · 처음/뒤/재생/앞/끝 · 속도 1×/4×/16× · 슬라이더 · 틱 라벨 · LIVE 배지 · 줌 · 로그 접기.
// 단축키: Space 재생/정지, ←/→ 한 틱(Shift = 10틱), Home/End.
import type { App } from '../app';
import { SPEEDS } from '../play/Playback';
import { ZOOMS } from '../scene/DungeonScene';
import { $, esc, typing } from './dom';
import { fetchText } from '../stream/live';

export function installControls(app: App): void {
  const root = $('controls');
  root.innerHTML =
    `<select id="runSel" title="판 선택"></select>` +
    `<button id="bStart" title="처음">⏮</button><button id="bBack" title="한 틱 뒤">◀</button>` +
    `<button id="bPlay" title="재생/정지 (Space)">▶</button>` +
    `<button id="bFwd" title="한 틱 앞">▶|</button><button id="bEnd" title="끝">⏭</button>` +
    `<span id="speeds"></span>` +
    `<input id="slider" type="range" min="0" max="0" value="0">` +
    `<span class="tlabel" id="tlabel">—</span>` +
    `<span class="badge live" id="liveBadge">LIVE</span>` +
    `<button id="bZoom" title="줌">${app.scene?.zoom ?? 1.5}×</button>` +
    `<button id="bLog" title="로그 접기/펼치기">로그</button>`;
  const pb = app.playback;
  const slider = $('slider') as HTMLInputElement;

  $('bStart').onclick = () => pb.setIdx(0);
  $('bEnd').onclick = () => pb.setIdx(pb.last);
  $('bBack').onclick = () => pb.step(-1);
  $('bFwd').onclick = () => pb.step(1);
  $('bPlay').onclick = () => pb.toggle();
  slider.oninput = () => pb.setIdx(+slider.value, 'seek');
  $('bZoom').onclick = () => {
    const i = ZOOMS.indexOf(app.scene.zoom as typeof ZOOMS[number]);
    const z = ZOOMS[(i + 1) % ZOOMS.length];
    app.scene.setZoom(z);
    $('bZoom').textContent = z + '×';
  };
  $('bLog').onclick = () => $('bottom').classList.toggle('collapsed');

  function speeds(): void {
    $('speeds').innerHTML = SPEEDS.map((s, i) => `<button data-i="${i}" class="${i === pb.speedIdx ? 'on' : ''}">${s}×</button>`).join('');
    $('speeds').querySelectorAll('button').forEach(b => { b.onclick = () => pb.setSpeed(+(b.dataset.i || 0)); });
  }
  speeds();
  pb.on('speed', speeds);
  pb.on('play', p => { $('bPlay').textContent = p ? '⏸' : '▶'; });
  pb.on('frames', n => { slider.max = String(Math.max(0, n - 1)); });
  pb.on('frame', ({ cur, idx }) => {
    slider.value = String(idx);
    const last = pb.frames[pb.last];
    $('tlabel').textContent = `t${cur.turn} / ${last ? last.turn : '?'} · ${cur.level.depth === 0 && app.run?.town ? '마을' : cur.level.depth + '층'}`;
  });
  app.bus.on('live', on => { $('liveBadge').classList.toggle('on', on); });
  pb.on('live', on => { $('liveBadge').classList.toggle('on', on && app.live); });

  document.addEventListener('keydown', e => {
    if (typing(e) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.code === 'Space') { e.preventDefault(); pb.toggle(); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); pb.setIdx(pb.idx - (e.shiftKey ? 10 : 1)); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); e.shiftKey ? pb.setIdx(pb.idx + 10) : pb.step(1); }
    else if (e.key === 'Home') pb.setIdx(0);
    else if (e.key === 'End') pb.setIdx(pb.last);
  });

  // 판 목록 — 론처의 /runs/ 자동 색인(<a href>)에서(뷰어와 같은 규칙). 없어도 URL 파라미터·라이브로 동작.
  const sel = $('runSel') as HTMLSelectElement;
  async function buildRunList(): Promise<void> {
    const opts: [string, string][] = [['state/stream.jsonl', '⦿ 라이브 (state/)']];
    try {
      const html = await fetchText('/runs/');
      const seen = new Set<string>();
      for (const m of html.matchAll(/href="([^"]+)"/g)) {
        let h = decodeURIComponent(m[1]);
        h = h.startsWith('/') ? h.slice(1) : 'runs/' + h;
        if (h.endsWith('/')) h += 'stream.jsonl';
        if (!h.endsWith('.jsonl') || seen.has(h)) continue;
        seen.add(h); opts.push([h, h.replace('runs/', '').replace('/stream.jsonl', '')]);
      }
    } catch { /* 목록 없음 */ }
    opts.sort((a, b) => (a[0].startsWith('state/') ? -1 : b[0].startsWith('state/') ? 1 : b[0].localeCompare(a[0])));
    sel.innerHTML = opts.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('');
    sel.onchange = () => {
      pb.pause();
      history.replaceState(null, '', '?run=' + encodeURIComponent(sel.value));
      void app.loadRun(sel.value);
    };
  }
  void buildRunList().then(() => {
    if (app.path) {
      if (![...sel.options].some(o => o.value === app.path)) sel.insertAdjacentHTML('beforeend', `<option value="${esc(app.path)}">${esc(app.path)}</option>`);
      sel.value = app.path;
    }
  });
  app.bus.on('run', () => {
    if (app.path && sel.options.length) {
      if (![...sel.options].some(o => o.value === app.path)) sel.insertAdjacentHTML('beforeend', `<option value="${esc(app.path)}">${esc(app.path)}</option>`);
      sel.value = app.path;
    }
  });
}
