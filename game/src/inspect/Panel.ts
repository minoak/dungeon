// 관전 클릭 창(p0.5.12 — 설계 .orch/drafts/viewer_click_design.md v1 · 민옥 결정 1~3: 무대 왼쪽 아래 고정 창 + 대상의 점선 고리 ·
// 실명은 가리지 않고 부르는 이름과 나란히 · 비교는 한 사람 한 줄). 무대를 누르면 그 자리의 후보(scene.pickAt — 지금 그려진 것만, 정한 순서)를
// 칩으로 늘어놓고 첫째를 연다. 위 칸 = 시스템 정보(세계의 사실), 아래 칸 = 시점 사람(초점)의 기록(로어북 — 고치지 않고 그대로, 없으면 '모름').
// [모두 비교] = 파티 전원의 기록을 한 사람 한 줄로. 창을 열어도 재생은 멈추지 않는다(라이브 꽁무니를 놓치지 않게).
// 입력: scene 'pointerup' · app.playback('frame') · app.focus('change') · app.bus('run'·'grow'·'live'). 재료는 스트림뿐(LLM 0콜 순수 소비자).
// 훅(스모크·관리자 확인): #inspect[data-open] · .ins-chip[data-id] · .ins-call · .ins-real · .ins-facts · .ins-rec[data-key] · .ins-none · .ins-row[data-char] · .ins-cmp · .ins-pov
import type Phaser from 'phaser';
import type { App } from '../app';
import type { Char } from '../stream/types';
import { el, esc, typing } from '../ui/dom';
import { loreIndex, realName, targetId, windowModel, type Pick, type RecView, type Target } from './model';

const CSS = `
#inspect { position: absolute; left: 14px; bottom: 34px; z-index: 4; width: min(320px, calc(100% - 28px)); max-height: calc(100% - 96px);
  overflow: auto; background: var(--panel2); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 8px 24px #0006;
  padding: 8px 10px 9px; font-size: 12px; line-height: 1.6; }
#inspect .ins-head { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
#inspect .ins-here { color: var(--dim); font-size: 10px; margin-right: 2px; }
#inspect .ins-chip { font-size: 10px; padding: 1px 7px; border-radius: 10px; }
#inspect .ins-close { margin-left: auto; padding: 0 8px; font-size: 13px; line-height: 1.4; }
#inspect .ins-title { display: flex; gap: 6px; align-items: baseline; flex-wrap: wrap; margin: 6px 0 0; }
#inspect .ins-call { font-size: 15px; font-weight: 600; }
#inspect .ins-sub { color: var(--dim); font-size: 10px; }
#inspect .ins-real { margin-left: auto; color: var(--gold); font-size: 10px; }
#inspect .ins-gone { color: var(--low); font-size: 11px; margin: 2px 0 0; }
#inspect .ins-sec { margin: 8px 0 3px; padding-top: 6px; border-top: 1px solid var(--line); color: #a4b0c0; font-size: 10px; font-weight: 500; letter-spacing: 1px; }
#inspect .ins-facts { display: grid; grid-template-columns: auto 1fr; gap: 1px 9px; margin: 0; }
#inspect .ins-facts dt { color: var(--dim); white-space: nowrap; }
#inspect .ins-facts dd { margin: 0; overflow-wrap: anywhere; color: #cdd6e2; }
#inspect .ins-rec { padding: 2px 0; overflow-wrap: anywhere; color: #cdd6e2; }
#inspect .ins-lab { color: var(--dim); margin-right: 4px; }
#inspect .t { color: var(--dim); font-size: 10px; margin-left: 4px; white-space: nowrap; }
#inspect .ins-past { color: var(--gold); font-size: 10px; border: 1px solid #e8c26866; border-radius: 3px; padding: 0 4px; margin-left: 4px; white-space: nowrap; }
#inspect .ins-none { color: var(--dim); margin: 2px 0; }
#inspect details { margin: 1px 0 2px 8px; }
#inspect summary { color: var(--dim); font-size: 10px; cursor: pointer; }
#inspect details p { margin: 1px 0; color: #9aa6b5; }
#inspect .ins-row { padding: 3px 0 3px 6px; border-top: 1px dashed var(--line); }
#inspect .ins-row.me { background: #ffffff08; box-shadow: inset 2px 0 0 var(--gold); }
#inspect .ins-row .ins-who { font-weight: 600; margin-right: 6px; }
#inspect .ins-row .ins-rcall { color: var(--dim); font-size: 11px; }
#inspect .ins-foot { display: flex; gap: 6px; justify-content: flex-end; margin-top: 7px; }
#inspect .ins-foot button, #inspect .ins-pov { font-size: 10px; padding: 2px 9px; }
#inspect .ins-pov { margin-top: 4px; }
`;

/** 층에 묶인 대상 — 층이 바뀌면 창을 닫는다(사람·마을 구역은 유지, 설계 §1.4). */
const levelBound = (t: Target): boolean => t.t !== 'bot' && t.t !== 'region';

export function installInspect(app: App): void {
  if (new URLSearchParams(location.search).get('embed') === '1') return;   // 액자 모드(?embed=1)엔 창이 없다
  if (!document.getElementById('style-inspect')) {
    const st = document.createElement('style'); st.id = 'style-inspect'; st.textContent = CSS;
    document.head.appendChild(st);
  }
  const root = el('section', 'ins');
  root.id = 'inspect'; root.hidden = true; root.dataset.open = '0';
  root.setAttribute('aria-label', '누른 대상');
  app.dom.stage.appendChild(root);

  let picks: Pick[] = [];
  let sel: Target | null = null;
  let compare = false;                           // 마지막 모드를 기억한다(창을 닫았다 열어도)
  let levelIdx = -1;
  let last = '';
  const opened = new Set<string>();             // 펼친 '이전 글'(다시 그려도 유지)

  function setOpen(on: boolean): void {
    root.hidden = !on; root.dataset.open = on ? '1' : '0';
    if (!on) { sel = null; picks = []; last = ''; root.innerHTML = ''; }
    app.scene.setPicked(on ? sel : null);
  }
  function choose(t: Target): void { sel = t; app.scene.setPicked(t); render(); }

  app.scene.input.on('pointerup', (p: Phaser.Input.Pointer) => {
    if (p.event?.target !== app.game.canvas) return;                 // 무대 위 DOM(이 창·칩·도감 창)을 누른 것은 무대 클릭이 아니다
    if (Math.hypot(p.upX - p.downX, p.upY - p.downY) > 6) return;   // 끌기는 누름이 아니다
    const ps = app.scene.pickAt(p.worldX, p.worldY);
    if (!ps.length) return;                        // 벽·바깥·빈 곳 — 아무것도 안 한다(창도 닫지 않는다)
    picks = ps; levelIdx = app.playback.cur?.levelIdx ?? -1;
    sel = ps[0].target;
    setOpen(true);
    render();
  });
  root.addEventListener('click', e => {
    const t = e.target as HTMLElement;
    if (t.closest('.ins-close')) { setOpen(false); return; }
    const chip = t.closest<HTMLElement>('.ins-chip');
    if (chip) { const p = picks[Number(chip.dataset.i)]; if (p) choose(p.target); return; }
    if (t.closest('.ins-cmp')) { compare = !compare; render(); return; }
    const pov = t.closest<HTMLElement>('.ins-pov');
    if (pov?.dataset.char) app.focus.set(pov.dataset.char);
  });
  root.addEventListener('toggle', e => {
    const d = e.target as HTMLDetailsElement;
    if (d.dataset?.key) { if (d.open) opened.add(d.dataset.key); else opened.delete(d.dataset.key); }
  }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && sel && !typing(e)) setOpen(false); });

  app.bus.on('run', () => setOpen(false));
  app.bus.on('grow', () => { if (sel) render(); });
  app.bus.on('live', () => { if (sel) render(); });
  app.focus.on('change', () => { if (sel) render(); });
  app.playback.on('frame', ch => {
    if (!sel) return;
    if (ch.cur.levelIdx !== levelIdx) {          // 층이 바뀌었다 — 층의 대상이면 닫고, 사람·마을 구역은 남긴다
      levelIdx = ch.cur.levelIdx;
      picks = picks.filter(p => !levelBound(p.target));
      if (levelBound(sel)) { setOpen(false); return; }
    }
    render();
  });

  function recHtml(v: RecView, owner: string): string {
    if (v.state === 'old') return '<p class="ins-none">이 판은 기록 기능이 없던 판</p>';
    if (v.state === 'self') return '<p class="ins-none">자기 자신 — 대상 기록이 없다(자기 생각은 수첩·note)</p>';
    if (v.state === 'none') return '<p class="ins-none">모름</p>';
    return v.lines.map(l => {
      const hk = `${owner}|${l.key}`;
      const when = l.past ? '<span class="ins-past">지난 판</span>' : `<span class="t">t${l.turn}</span>`;
      const name = l.name ? `이름: ${esc(l.name)}${l.text ? ' — ' : ''}` : '';
      const body = l.text ? `「${esc(l.text)}」` : '<span class="ins-lab">(이름만 적어 두었다)</span>';
      const hist = l.history.length
        ? `<details data-key="${esc(hk)}"${opened.has(hk) ? ' open' : ''}><summary>이전 글 ${l.history.length}</summary>` +
          l.history.map(h => `<p>「${esc(h)}」</p>`).join('') + '</details>' : '';
      return `<div class="ins-rec" data-key="${esc(l.key)}">${l.label ? `<span class="ins-lab">${esc(l.label)}</span>` : ''}${name}${body}${when}${hist}</div>`;
    }).join('');
  }

  function render(): void {
    const run = app.run, f = app.playback.cur, i = app.playback.idx;
    if (!run || !f || !sel) return;
    const ix = loreIndex(run);
    const viewer: Char | null = app.focus.char;
    const m = windowModel(ix, sel, f, i, viewer, compare);
    const selId = targetId(sel);
    let h = '<div class="ins-head"><span class="ins-here">여기:</span>' + picks.map((p, n) => {
      const id = targetId(p.target);
      const short = p.target.t === 'bot' || p.target.t === 'region' ? '' : ' ' + id.replace(/^zone:/, '');
      return `<button type="button" class="ins-chip${id === selId ? ' on' : ''}" data-i="${n}" data-id="${esc(id)}">${esc(realName(ix, p.target, f))}${esc(short)}</button>`;
    }).join('') + '<button type="button" class="ins-close" aria-label="닫기" title="닫기 (Esc)">×</button></div>';
    h += `<div class="ins-title"><span class="ins-call">${esc(m.call)}</span><span class="ins-sub">${esc(m.sub)}</span>` +
         (m.call !== m.real ? `<span class="ins-real">관전자: ${esc(m.real)}</span>` : '') + '</div>';
    if (!m.present) h += '<p class="ins-gone">지금 화면에 없다</p>';
    if (m.facts.length) {
      h += '<h3 class="ins-sec">무엇인가</h3><dl class="ins-facts">' +
           m.facts.map(x => `<dt>${esc(x.k)}</dt><dd>${esc(x.v)}</dd>`).join('') + '</dl>';
    }
    const who = sel.t === 'bot' ? sel.char : null;   // 모험가를 고르면 그 사람 시점으로 바꾸는 단추
    if (who && who !== viewer && run.party.some(p => p.char === who)) {
      h += `<button type="button" class="ins-pov" data-char="${esc(who)}">이 사람 시점으로</button>`;
    }
    if (m.rows) {
      h += '<h3 class="ins-sec">모두의 기록</h3>' + m.rows.map(r =>
        `<div class="ins-row${r.me ? ' me' : ''}" data-char="${esc(r.char)}"><span class="ins-who" style="color:${esc(run.colors[r.char] || '#fff')}">${esc(r.name)}</span>` +
        `<span class="ins-rcall">${esc(r.job)} · 부르는 이름: ${esc(r.call)}</span>${recHtml(r.rec, r.char)}</div>`).join('');
    } else if (m.mine) {
      h += `<h3 class="ins-sec">${esc(viewer ? (run.names[viewer] || viewer) : '')}에게는</h3>` + recHtml(m.mine, viewer ?? '');
    }
    h += `<div class="ins-foot"><button type="button" class="ins-cmp${compare ? ' on' : ''}" aria-pressed="${compare}">${compare ? '시점 보기' : '모두 비교'}</button></div>`;
    if (h === last) return;                        // 같은 내용이면 다시 그리지 않는다(재생 중 매 틱 호출)
    last = h;
    root.innerHTML = h;
  }
}
