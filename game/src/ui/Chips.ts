// 캐릭터 칩(우측 열) — SD 초상 + 이름·직업 + HP 바 + 상태 태그. 클릭·숫자키 1~9 = 초점 전환.
// 초점 캐릭터의 시야 밖이면 흐리게(파트너 동의), 죽으면 회색, 먼저 내려갔으면 별도 표식.
import type { App } from '../app';
import type { Char, Frame } from '../stream/types';
import { $, el, esc, typing } from './dom';
import { cellKey } from '../world/Sight';

interface ChipNode { root: HTMLElement; face: HTMLCanvasElement; hpfill: HTMLElement; hpnum: HTMLElement; tags: HTMLElement }

export function installChips(app: App): void {
  const root = $('chips');
  const nodes = new Map<Char, ChipNode>();

  function build(): void {
    root.innerHTML = '';
    nodes.clear();
    const run = app.run;
    if (!run) return;
    run.party.forEach((p, i) => {
      const c = p.char, color = run.colors[c] || '#fff';
      const chip = el('button', 'chip');
      chip.setAttribute('type', 'button');
      chip.style.setProperty('--char-color', color);
      chip.dataset.char = c;
      chip.title = `${run.names[c]} — 클릭하면 카메라가 따라간다 (키 ${i + 1})`;
      chip.innerHTML =
        `<canvas class="face" width="56" height="56"></canvas>` +
        `<div class="body"><div><span class="name" style="color:${color}">${esc(run.names[c])}</span>` +
        `<span class="job">${esc(run.jobs[c])}</span><span class="key">${i + 1}</span></div>` +
        `<div class="hpline"><div class="hpbar"><div class="hpfill"></div></div><div class="hpnum"></div></div>` +
        `<div class="tags"></div></div>`;
      chip.onclick = () => app.focus.set(c);
      root.appendChild(chip);
      const face = chip.querySelector('canvas.face') as HTMLCanvasElement;
      const pc = app.scene?.portrait(c, 56);
      if (pc) { const g = face.getContext('2d'); if (g) { g.imageSmoothingEnabled = false; g.drawImage(pc, 0, 0); } }
      nodes.set(c, { root: chip, face, hpfill: chip.querySelector('.hpfill') as HTMLElement,
                     hpnum: chip.querySelector('.hpnum') as HTMLElement, tags: chip.querySelector('.tags') as HTMLElement });
    });
  }

  function update(f: Frame | null): void {
    const run = app.run;
    if (!run || !f) return;
    const focus = app.focus.char;
    const vis = focus && !run.levels[f.levelIdx].town ? f.vis[focus] : null;
    for (const [c, n] of nodes) {
      const b = f.bots.find(x => x.char === c);
      const cls = n.root.classList;
      cls.toggle('focus', c === focus);
      n.root.setAttribute('aria-pressed', String(c === focus));
      let dead = false, won = false, unseen = false, tags = '';
      if (b) {
        const r = Math.max(0, Math.min(1, b.hp / Math.max(1, b.maxhp)));
        n.hpfill.style.width = (r * 100) + '%';
        n.hpfill.style.background = r > 0.5 ? 'var(--hp)' : (r > 0.25 ? 'var(--mid)' : 'var(--low)');
        n.hpnum.textContent = `${Math.max(0, b.hp)}/${b.maxhp}`;
        dead = !b.alive; won = b.alive && b.won;
        unseen = !!vis && c !== focus && b.alive && !b.won && !vis.has(cellKey(b.x, b.y));
        const st = (b.status || []).map(s => `<span class="tag">${esc(s)}</span>`).join('');
        if (dead) tags = `<span class="st">☠ 전사 (t${run.deathTurn[c] ?? '?'})</span>`;
        else if (won) tags = `<span class="st">▼ 먼저 내려갔다</span>`;
        else tags = st + (unseen ? '<span class="dim">시야 밖</span>' : '');
      } else {                                   // 이 층 스냅샷에 없음 — 전 층 전사자거나 이미 탈출
        n.hpfill.style.width = '0%'; n.hpnum.textContent = '—';
        if (c in run.deathTurn && run.deathTurn[c] <= f.turn) { dead = true; tags = `<span class="st">☠ 전사 (t${run.deathTurn[c]})</span>`; }
        else tags = '<span class="dim">이 층에 없다</span>';
      }
      cls.toggle('dead', dead); cls.toggle('won', won); cls.toggle('unseen', unseen);
      n.tags.innerHTML = tags;
    }
  }

  app.bus.on('run', () => { build(); update(app.playback.cur); });
  app.playback.on('frame', ({ cur }) => update(cur));
  app.focus.on('change', () => update(app.playback.cur));
  document.addEventListener('keydown', e => {
    if (typing(e) || e.ctrlKey || e.metaKey || e.altKey) return;
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= 9) { const p = app.run?.party[n - 1]; if (p) app.focus.set(p.char); }
  });
}
