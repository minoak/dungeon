// 재생 컨트롤 — 판 선택 · 처음/뒤/재생/앞/끝 · 속도 1×/4×/16× · 슬라이더 · 틱 라벨 · LIVE 배지 · 줌 · 로그 접기.
// 단축키: Space 재생/정지, ←/→ 한 틱(Shift = 10틱), Home/End.
import type { App } from '../app';
import { SPEEDS } from '../play/Playback';
import { ZOOMS } from '../scene/DungeonScene';
import { $, esc, typing } from './dom';
import { fetchText } from '../stream/live';
import { STATIC, fetchRunIndex } from '../paths';
import { icon } from './icons';
import { alphaLabel } from '../../../viewer/assets/skills.js';

export function installControls(app: App): void {
  const root = $('controls');
  $('runPicker').innerHTML = '<label for="runSel">원정</label><select id="runSel" title="판 선택" aria-label="판 선택"></select>';
  root.innerHTML =
    `<div class="timeline"><span class="timeline-label">TURN</span><input id="slider" aria-label="재생 위치" type="range" min="0" max="0" value="0"><span class="tlabel" id="tlabel">—</span></div>` +
    `<div class="transport-row"><div class="transport">` +
    `<button id="bStart" title="처음" aria-label="처음으로">${icon('start')}</button><button id="bBack" title="한 턴 이전" aria-label="한 턴 이전">${icon('back')}</button>` +
    `<button id="bPlay" title="재생/정지 (Space)" aria-label="재생">${icon('play')}</button>` +
    `<button id="bFwd" title="한 턴 다음" aria-label="한 턴 다음">${icon('forward')}</button><button id="bEnd" title="끝" aria-label="끝으로">${icon('end')}</button></div>` +
    `<div id="speeds" aria-label="재생 속도"></div><span class="badge live" id="liveBadge">LIVE</span>` +
    `<span id="oracleBox" hidden><input id="oracleIn" maxlength="200" placeholder="신의 요청 한 줄 — 어디에 있든 캐릭터들에게(요청이지 명령이 아니다)" aria-label="신탁"><button id="oracleSend" title="론처 /api/oracle — 신전 문턱 근처에 선 캐릭터의 관측에 들어간다(요청이지 명령이 아니다)">신탁</button></span>` +
    `<div class="view-tools"><button id="bZoom" title="화면 확대">확대 ${app.scene?.zoom ?? 1.5}×</button>` +
    `<button id="bLog" title="기록 접기/펼치기" aria-expanded="true" aria-controls="log journalHead">기록 접기</button></div></div>`;
  const stageInfo = document.createElement('div');
  stageInfo.id = 'stageInfo'; stageInfo.innerHTML = '<span class="stage-kicker">원정</span><strong id="floorLabel">불러오는 중</strong><div id="alphaLabel" class="wl-alpha-label" hidden></div>';
  app.dom.hud.prepend(stageInfo);
  const pb = app.playback;
  app.bus.on('run', () => {
    const label = alphaLabel(app.run?.meta);
    $('alphaLabel').textContent = label;
    $('alphaLabel').hidden = !label;
  });
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
    $('bZoom').textContent = '확대 ' + z + '×';
  };
  $('bLog').onclick = () => {
    const closed = $('bottom').classList.toggle('collapsed');
    $('bLog').textContent = closed ? '기록 펼치기' : '기록 접기';
    $('bLog').setAttribute('aria-expanded', String(!closed));
  };

  function speeds(): void {
    $('speeds').innerHTML = SPEEDS.map((s, i) => `<button data-i="${i}" aria-label="${s}배속" aria-pressed="${i === pb.speedIdx}" class="${i === pb.speedIdx ? 'on' : ''}">${s}×</button>`).join('');
    $('speeds').querySelectorAll('button').forEach(b => { b.onclick = () => pb.setSpeed(+(b.dataset.i || 0)); });
  }
  speeds();
  pb.on('speed', speeds);
  pb.on('play', p => { $('bPlay').innerHTML = icon(p ? 'pause' : 'play'); $('bPlay').setAttribute('aria-label', p ? '일시정지' : '재생'); });
  pb.on('frames', n => { slider.max = String(Math.max(0, n - 1)); });
  pb.on('frame', ({ cur, idx }) => {
    slider.value = String(idx);
    const last = pb.frames[pb.last];
    $('tlabel').textContent = `${cur.turn} / ${last ? last.turn : '?'}`;
    slider.setAttribute('aria-valuetext', `${cur.turn}턴`);
    slider.style.setProperty('--progress', `${pb.last > 0 ? idx / pb.last * 100 : 0}%`);
    $('floorLabel').textContent = cur.level.depth === 0 && app.run?.town ? '모험가의 마을' : `지하 ${cur.level.depth}층`;
    updateCaption();
  });
  function updateCaption(): void {
    const c = app.focus.char;
    $('focusCaption').textContent = c ? `${app.name(c)}의 시선` : '모험가를 따라가는 중';
    $('sceneCaption').style.setProperty('--char-color', c ? app.color(c) : 'var(--gold)');
  }
  app.focus.on('change', updateCaption);
  app.bus.on('live', on => { $('liveBadge').classList.toggle('on', on); });
  pb.on('live', on => { $('liveBadge').classList.toggle('on', on && app.live); });

  document.addEventListener('keydown', e => {
    if (typing(e) || e.ctrlKey || e.metaKey || e.altKey) return;
    // 버튼·펼침 항목에 초점이 있으면 Space는 해당 요소의 기본 조작에 맡긴다.
    if (e.code === 'Space' && (e.target as HTMLElement | null)?.closest('button, summary, a')) return;
    if (e.code === 'Space') { e.preventDefault(); pb.toggle(); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); pb.setIdx(pb.idx - (e.shiftKey ? 10 : 1)); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); e.shiftKey ? pb.setIdx(pb.idx + 10) : pb.step(1); }
    else if (e.key === 'Home') pb.setIdx(0);
    else if (e.key === 'End') pb.setIdx(pb.last);
  });

  // 판 목록 — 론처의 /runs/ 자동 색인(<a href>)에서(뷰어와 같은 규칙). 없어도 URL 파라미터·라이브로 동작.
  const sel = $('runSel') as HTMLSelectElement;
  async function buildRunList(): Promise<void> {
    const opts: [string, string][] = STATIC ? [] : [['state/stream.jsonl', '진행 중인 원정 · LIVE']];
    if (STATIC)                                  // 정적 배포 — 론처 색인 대신 static-bundle.mjs 가 만든 runs/index.json(순서 = 목록 순서)
      for (const r of (await fetchRunIndex())?.runs ?? []) opts.push([r.path, r.label]);
    try {
      const html = STATIC ? '' : await fetchText('/runs/');
      const seen = new Set<string>();
      for (const m of html.matchAll(/href="([^"]+)"/g)) {
        let h = decodeURIComponent(m[1]);
        h = h.startsWith('/') ? h.slice(1) : 'runs/' + h;
        if (h.endsWith('/')) h += 'stream.jsonl';
        if (!h.endsWith('.jsonl') || seen.has(h)) continue;
        seen.add(h);
        const stamp = h.match(/stream-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})\.jsonl$/);
        const label = stamp ? `${stamp[1]}.${stamp[2]}.${stamp[3]} · ${stamp[4]}:${stamp[5]}:${stamp[6]}` : h.replace('runs/', '').replace('/stream.jsonl', '');
        opts.push([h, label]);
      }
    } catch { /* 목록 없음 */ }
    if (!STATIC) opts.sort((a, b) => (a[0].startsWith('state/') ? -1 : b[0].startsWith('state/') ? 1 : b[0].localeCompare(a[0])));
    sel.innerHTML = opts.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('');
    sel.onchange = () => {
      pb.pause();
      history.replaceState(null, '', '?run=' + encodeURIComponent(sel.value));
      void app.loadRun(sel.value);
    };
  }
  // D61 신탁 소켓 — 라이브 판(론처 상대)에서만 보인다. 서버가 state/oracle.json 에 두고 러너가 틱마다 읽는다. 정적 배포엔 없다.
  const oracleBox = $('oracleBox'), oracleIn = $('oracleIn') as HTMLInputElement, oracleSend = $('oracleSend') as HTMLButtonElement;
  const showOracle = (): void => { oracleBox.hidden = !app.live; };
  app.bus.on('live', showOracle); showOracle();
  oracleSend.onclick = async () => {
    const text = oracleIn.value.trim();
    try {
      const r = await fetch('/api/oracle', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
      const j = await r.json().catch(() => ({}));
      oracleSend.textContent = r.ok ? (j.oracle ? '보냄 ✓' : '거둠') : '실패';
    } catch { oracleSend.textContent = '실패'; }
    window.setTimeout(() => { oracleSend.textContent = '신탁'; }, 1500);
  };
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
