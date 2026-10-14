// 도감·수첩 창(D63, 2026-09-13 파트너 "화면은 별개로 확인 가능한 창을 만들어 두자 도감 창이랑 같이 기록을 볼수 있게") —
// 관전 화면 헤더 버튼으로 여닫는 별개 창. 재생 위치까지 캐릭터가 '알게 된 것'과 '쓴 것'만 보여 준다(관전 원칙 — 그 시점에 존재하는 것만).
//   도감 탭: 몬스터 종별 카드(그림·이름). 세계 지식(등재 한 줄·심층 본문 = run_meta.bestiary_defs)은 파티 중 누군가 그 층에 닿았을 때만.
//            캐릭터별 줄 = 상태(모름·등재·심층, 조우 n/해금 수) + 도감평(이 판 decisions.book_line / 지난 판 run_meta.bestiary_progress.note).
//   수첩 탭: 캐릭터별, 층을 떠날 때 쓴 장(descend/ascend.pages).
//   기록 탭(p0.5.12 민옥 결정 4): 고른 캐릭터가 lore_note 로 쓴 기록 전부(사람·장소·의뢰·종류·장비·층의 것)를 재생 위치까지 접은 목록 —
//            지도에서 누를 수 없는 의뢰·지금 층에 없는 대상·다른 세계의 대상 기록을 볼 길. 관전 클릭 창과 같은 접기(inspect/model).
// 조우 수의 재구성 = bestiary.py 와 같은 규칙: tick.bots[].aware_of 에 몹 id 가 *새로* 오른 순간(층이 바뀌면 새 id 공간) + 판 시작 진행도 시드.
// 도감평 = 그 종의 도감 note 를 접은 것(p0.5.12 — book_line 과 인물 기록 판의 lore_note 가 같은 칸, 지난 판 note 는 '지난 판').
// 입력: app.bus('run'·'grow') · app.playback('frame') · app.focus('change'). 엔진·러너 판정 무접촉(run_meta.bestiary_defs 는 러너 additive).
// 훅(스모크): #codexBtn · #codex[data-open] · .cx-tab[data-tab=bestiary|notebook|records] · .cx-card[data-key] · .cx-row[data-char] · .cx-char[data-char] · .cx-page[data-char] · .cx-rec[data-key]
import type { App } from '../app';
import type { BestiaryDef, Char, Run } from '../stream/types';
import type { FrameChange } from '../play/Playback';
import { $, el, esc, typing } from './dom';
import { ledgerRows, loreIndex, startOf, valueAt, writesAt } from '../inspect/model';
import goblinUrl from '../assets/world/goblin.png';
import spiderUrl from '../assets/world/spider.png';

const MONSTER_IMG: Record<string, string> = { '고블린': goblinUrl, '그림자거미': spiderUrl };   // world.ts MONSTERS 와 같은 키 — 시트 frame 0 을 자른다
const CELL = 96;                                   // world.ts WORLD_CELL — 시트 한 칸(288×384 = 3×4 칸)
const DEFAULT_UNLOCK = 5;                          // 정의(unlock)가 없는 옛 판의 심층 문턱 — bestiary.py 기본과 같다

type Tab = 'bestiary' | 'notebook' | 'records';
interface Encounter { idx: number; char: Char; key: string }
interface Page { idx: number; turn: number; char: Char; depth: number; kind: 'descend' | 'ascend'; text: string }
interface Index { enc: Encounter[]; pages: Page[]; kinds: Set<string> }
interface Tier { known: boolean; deep: boolean; n: number; need: number }

/** 판 전체를 한 번 훑어 '알게 된 순간'·'쓴 순간'을 프레임 번호와 함께 색인한다(재생 위치 ≤ idx 로 거른다). */
function buildIndex(run: Run): Index {
  const enc: Encounter[] = [], pages: Page[] = [], kinds = new Set<string>();
  let prev: Record<Char, Set<number>> = {}, levelIdx = -1;
  for (const f of run.frames) {
    if (f.levelIdx !== levelIdx) { levelIdx = f.levelIdx; prev = {}; }   // 새 층 = 새 몹 id 공간(bestiary.py consume 'level')
    if (f.kind !== 'tick') continue;
    const kindOf = new Map<number, string>();
    for (const m of f.monsters || []) kindOf.set(m.id, m.kind);
    for (const b of f.bots || []) {
      const cur = new Set<number>();
      for (const id of b.aware_of || []) if (typeof id === 'number') cur.add(id);
      const was = prev[b.char] || new Set<number>();
      for (const id of cur) {
        if (was.has(id)) continue;
        const k = kindOf.get(id);
        if (k) { enc.push({ idx: f.idx, char: b.char, key: 'monster:' + k }); kinds.add(k); }
      }
      prev[b.char] = cur;
    }
    const pg = f.descend?.pages;
    if (pg) {
      const depth = f.level.depth;               // 떠나는 층(descend 는 다음 프레임이 level 이라 이 틱의 층이 곧 떠난 층)
      for (const [c, text] of Object.entries(pg)) pages.push({ idx: f.idx, turn: f.turn, char: c, depth, kind: f.descend!.kind, text });
    }
  }
  return { enc, pages, kinds };
}

/** 그 캐릭터가 재생 위치(idx)까지 그 종을 어디까지 아는가 — 시작 진행도(원장) + 이 판의 조우 증분. */
function tierOf(run: Run, ix: Index, idx: number, char: Char, key: string, def: BestiaryDef | undefined): Tier {
  const name = run.names[char] || char;
  const start = run.meta?.bestiary_progress?.[name]?.[key];
  const startKnown = !!start || !!run.meta?.bestiary?.[name]?.includes(key);
  let n = start?.n ?? 0;
  for (const e of ix.enc) if (e.char === char && e.key === key && e.idx <= idx) n++;
  const need = def?.unlock?.count ?? (def ? 1 : DEFAULT_UNLOCK);   // 정의에 unlock 이 없으면 옛 2층(등재 즉시 본문)
  const known = startKnown || n > 0;
  const deep = known && (!!start?.deep || n >= need);
  return { known, deep, n, need };
}

const sheetCache = new Map<string, HTMLImageElement>();
function drawMonster(canvas: HTMLCanvasElement, kind: string): void {
  const url = MONSTER_IMG[kind];
  if (!url) return;
  const paint = (img: HTMLImageElement) => {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, CELL, CELL, 0, 0, canvas.width, canvas.height);   // frame 0 = 왼쪽 위 칸
  };
  const cached = sheetCache.get(kind);
  if (cached && cached.complete) { paint(cached); return; }
  const img = cached || new Image();
  if (!cached) { img.src = url; sheetCache.set(kind, img); }
  img.addEventListener('load', () => paint(img), { once: true });
}

export function installCodex(app: App): void {
  const root = $('codex');
  const btn = document.getElementById('codexBtn') as HTMLButtonElement | null;
  let tab: Tab = 'bestiary';
  let ix: Index | null = null;
  let picked: Char | null = null;                  // 수첩·기록 탭에서 고른 캐릭터(없으면 초점을 따른다)
  let lastIdx = -1;

  root.innerHTML =
    `<div class="cx-head"><h2>도감·수첩</h2><div class="cx-tabs" role="tablist">` +
    `<button type="button" class="cx-tab on" data-tab="bestiary" role="tab" aria-selected="true">도감</button>` +
    `<button type="button" class="cx-tab" data-tab="notebook" role="tab" aria-selected="false">수첩</button>` +
    `<button type="button" class="cx-tab" data-tab="records" role="tab" aria-selected="false">기록</button></div>` +
    `<button type="button" class="cx-close" aria-label="닫기" title="닫기 (Esc)">×</button></div>` +
    `<div class="cx-body"></div>`;
  const body = root.querySelector('.cx-body') as HTMLElement;

  const isOpen = () => root.dataset.open === '1';
  function setOpen(on: boolean): void {
    root.hidden = !on;
    root.dataset.open = on ? '1' : '0';
    btn?.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (on) { lastIdx = -1; render(); }
  }
  function setTab(t: Tab): void {
    tab = t;
    root.querySelectorAll<HTMLButtonElement>('.cx-tab').forEach(b => {
      const on = b.dataset.tab === t;
      b.classList.toggle('on', on); b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    lastIdx = -1; render();
  }

  btn?.addEventListener('click', () => setOpen(!isOpen()));
  root.querySelector('.cx-close')?.addEventListener('click', () => setOpen(false));
  root.querySelectorAll<HTMLButtonElement>('.cx-tab').forEach(b => b.addEventListener('click', () => setTab(b.dataset.tab as Tab)));
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && isOpen() && !typing(e)) setOpen(false); });
  body.addEventListener('click', e => {
    const c = (e.target as HTMLElement).closest<HTMLElement>('.cx-char');
    if (c?.dataset.char) { picked = c.dataset.char; lastIdx = -1; render(); }
  });

  app.bus.on('run', () => { ix = null; picked = null; lastIdx = -1; if (isOpen()) render(); });
  app.bus.on('grow', () => { ix = null; lastIdx = -1; if (isOpen()) render(); });   // 라이브: 프레임이 붙으면 색인을 다시(작다)
  app.playback.on('frame', (_ch: FrameChange) => { if (isOpen()) render(); });
  app.focus.on('change', () => { if (isOpen() && tab !== 'bestiary' && !picked) { lastIdx = -1; render(); } });
  app.bus.on('live', () => { lastIdx = -1; if (isOpen()) render(); });   // 판 끝 줄(end)의 남은 원장 변화 — 프레임은 안 붙는다

  function render(): void {
    const run = app.run;
    const idx = app.playback.idx;
    if (!run) { body.innerHTML = '<p class="cx-empty">판이 아직 없다</p>'; return; }
    if (idx === lastIdx) return;                   // 같은 프레임이면 다시 그리지 않는다(재생 중 매 틱 호출)
    lastIdx = idx;
    if (!ix) ix = buildIndex(run);
    body.innerHTML = tab === 'bestiary' ? bestiaryHtml(run, ix, idx) : tab === 'notebook' ? notebookHtml(run, ix, idx) : recordsHtml(run, idx);
    if (tab === 'bestiary') body.querySelectorAll<HTMLCanvasElement>('canvas.cx-img').forEach(cv => drawMonster(cv, cv.dataset.kind || ''));
  }

  function bestiaryHtml(run: Run, ix: Index, idx: number): string {
    const lx = loreIndex(run);
    const defs = run.meta?.bestiary_defs || {};
    const chars = run.party.map(p => p.char);
    const keys = new Set<string>();
    for (const k of Object.keys(defs)) if (k.startsWith('monster:')) keys.add(k);
    for (const k of ix.kinds) keys.add('monster:' + k);
    for (const c of chars) {
      const name = run.names[c] || c;
      for (const k of Object.keys(run.meta?.bestiary_progress?.[name] || {})) if (k.startsWith('monster:')) keys.add(k);
      for (const k of run.meta?.bestiary?.[name] || []) if (k.startsWith('monster:')) keys.add(k);
    }
    const cur = run.frames[idx];
    let out = `<p class="cx-note">t${cur ? cur.turn : 0} 까지 파티가 알게 된 것 — 세계 지식은 파티 중 누군가 닿은 층까지, 도감평은 각자 쓴 한 줄` +
      (Object.keys(defs).length ? '' : ' <span class="cx-prev">옛 판: 세계 지식 본문 없음</span>') + '</p>';
    if (!keys.size) return out + '<p class="cx-empty">아직 만난 몬스터가 없다</p>';
    for (const key of [...keys].sort()) {
      const kind = key.slice('monster:'.length);
      const def = defs[key];
      const tiers = chars.map(c => [c, tierOf(run, ix, idx, c, key, def)] as const);
      const knownBy = tiers.filter(([, t]) => t.known).map(([c]) => c);
      const deepBy = tiers.filter(([, t]) => t.deep).map(([c]) => c);
      const names = (cs: readonly Char[]) => cs.map(c => esc(run.names[c] || c)).join('·');
      out += `<section class="cx-card" data-key="${esc(key)}"><div class="cx-title"><canvas class="cx-img" width="48" height="48" data-kind="${esc(kind)}"></canvas>` +
        `<span>${esc(def?.name || kind)} <small>${esc(key)}</small></span></div>`;
      if (!knownBy.length) out += '<p class="cx-none">아직 아무도 모른다</p>';
      else if (def && deepBy.length) out += `<p class="cx-lore"><b>심층</b>${esc(def.lore)}<span class="cx-who">— ${names(deepBy)}</span></p>`;
      else if (def && def.brief) out += `<p class="cx-brief"><b>등재</b>${esc(def.brief)}<span class="cx-who">— ${names(knownBy)}</span></p>`;
      else if (def) out += `<p class="cx-brief"><b>등재</b>${esc(def.lore)}<span class="cx-who">— ${names(knownBy)}</span></p>`;
      for (const [c, t] of tiers) {
        const name = run.names[c] || c;
        const tier = !t.known ? '모름' : t.deep ? `심층 (조우 ${t.n})` : `등재 (조우 ${t.n}/${t.need})`;
        out += `<div class="cx-row" data-char="${esc(c)}"><b style="color:${esc(run.colors[c] || '#fff')}">${esc(name)}</b><span class="cx-tier">${tier}</span>`;
        const now = valueAt(lx, c, key, idx), n = writesAt(lx, c, key, idx);   // 도감 note 접기(book_line · lore_note 의 monster: — 같은 칸)
        if (now?.text && now.src !== 'book') out += `<span class="cx-line">「${esc(now.text)}」<span class="t">(t${now.turn ?? 0}${n > 1 ? ` · 고쳐 씀 ${n}번째` : ''})</span></span>`;
        const prev = startOf(lx, c, key);
        if (prev?.text && (!now || now.src === 'book' || now.text !== prev.text)) out += `<span class="cx-line">「${esc(prev.text)}」<span class="cx-prev">지난 판</span></span>`;
        out += '</div>';
      }
      out += '</section>';
    }
    return out;
  }

  /** 수첩·기록 탭의 캐릭터 고르기 — 고른 사람(없으면 초점) · 칩 줄. */
  function charPick(run: Run): { sel: Char | undefined; html: string } {
    const chars = run.party.map(p => p.char);
    const sel = picked && chars.includes(picked) ? picked : (app.focus.char && chars.includes(app.focus.char) ? app.focus.char : chars[0]);
    return { sel, html: '<div class="cx-chars">' + chars.map(c =>
      `<button type="button" class="cx-char${c === sel ? ' on' : ''}" data-char="${esc(c)}" aria-pressed="${c === sel ? 'true' : 'false'}" style="color:${esc(run.colors[c] || '#fff')}">${esc(run.names[c] || c)}</button>`).join('') + '</div>' };
  }

  /** p0.5.12 기록 탭 — 고른 캐릭터의 로어북 전부(재생 위치까지 접은 것). 다른 층의 층 기록은 표시를 붙인다. */
  function recordsHtml(run: Run, idx: number): string {
    const { sel, html } = charPick(run);
    let out = html;
    if (!sel) return out + '<p class="cx-empty">파티가 없다</p>';
    const lx = loreIndex(run);
    if (!lx.people) return out + '<p class="cx-note">이 판은 기록 기능이 없던 판이다 — 인물 기록 판에서 캐릭터가 직접 쓴 기록이 여기 모인다</p>';
    const cur = run.frames[idx];
    const rows = ledgerRows(lx, sel, idx, cur?.level.scope);
    const who = esc(run.names[sel] || sel);
    out += `<p class="cx-note">t${cur ? cur.turn : 0} 까지 ${who}이(가) 쓴 기록 — 고치지 않고 그대로(관전자는 모두의 기록을 본다)</p>`;
    if (!rows.length) return out + `<p class="cx-empty">${who}이(가) 아직 쓴 기록이 없다</p>`;
    let group = '';
    for (const r of rows) {
      if (r.group !== group) { group = r.group; out += `<h3 class="cx-grp">${esc(group)}</h3>`; }
      const when = r.past ? '<span class="cx-prev">지난 판</span>' : `<span class="t">(t${r.turn})</span>`;
      out += `<div class="cx-row cx-rec" data-key="${esc(r.key)}"><b>${esc(r.title)}</b>` +
        (r.name ? `<span class="cx-tier">적은 이름: ${esc(r.name)}</span>` : '') + (r.elsewhere ? '<span class="cx-prev">다른 층</span>' : '') +
        `<span class="cx-line">${r.text ? `「${esc(r.text)}」` : '(이름만 적어 두었다)'}${when}</span></div>`;
    }
    return out;
  }

  function notebookHtml(run: Run, ix: Index, idx: number): string {
    const { sel, html } = charPick(run);
    let out = html;
    if (!sel) return out + '<p class="cx-empty">파티가 없다</p>';
    const pages = ix.pages.filter(p => p.char === sel && p.idx <= idx);
    if (run.meta && run.meta.notebook === false) out += '<p class="cx-note">이 판은 수첩을 끈 판이다</p>';
    if (!pages.length) return out + `<p class="cx-empty">${esc(run.names[sel] || sel)}이(가) 아직 쓴 장이 없다 — 층을 떠날 때 한 장을 쓴다</p>`;
    for (const p of pages) {
      const where = p.kind === 'descend' ? `${p.depth}층을 떠나며` : `${p.depth}층에서 올라가며`;
      out += `<article class="cx-page" data-char="${esc(sel)}"><div class="cx-when">t${p.turn} · ${where}</div><p>${esc(p.text)}</p></article>`;
    }
    return out;
  }
}
