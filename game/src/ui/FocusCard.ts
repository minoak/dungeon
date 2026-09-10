// 초점 카드(Phase B1) — 초점 캐릭터 한 사람의 '지금': 이름·직업·성별(시트) · HP 바 · 상태 태그 · 소지 · 속내 · 최근 말 ·
// 관계(뼈 횟수 + 본인이 쓴 한 줄). GAME_CLIENT_PLAN §3 "초점 카드".
// 입력: app.focus('change') · app.playback('frame') · app.bus('run') · frame.bots[].{hp,maxhp,status,potions,weapon,armor,relations}
//       · decisions[char].{reason,src,say,say_kind,to,relation} · run.party[].{name,job,sex,persona,goal} · run.deathTurn.
// 산출: app.dom.focusCard 안 DOM — 훅(B6 스모크): .fc[data-char] .fc-hp("10/10") .fc-status .fc-items .fc-reason .fc-say
//       .fc-bones .fc-line(관계 상대마다 하나씩, 파티 순서).
// 갱신 규율: 노드는 한 번 만들고 텍스트만 바꾼다(변한 것만). 뒤로 훑는 검색(속내·최근 말·관계 한 줄)은 판 단위 색인
// (캐릭터별 '그 결정이 있던 프레임 번호' 오름차순 목록)에서 이진 탐색 — seek 도 O(log n), 층이 바뀌어도 이어진다.
// step/play(+1)는 cur.decisions 만 보고 덧쓴다. seek 는 HP 바 트윈을 끈다(스냅).
import type { App } from '../app';
import type { Bot, Char, Decision, Frame, Gear, PartyMember, Run } from '../stream/types';
import type { FrameChange } from '../play/Playback';
import { el, esc } from './dom';
import { reactionSummaryHtml } from '../text/reactions';
import { skillsHtml } from '../../../viewer/assets/skills.js';

/** 관계 뼈 라벨 — dungeon_gm.py BONES(422행) 를 그대로 복사(엔진 무접촉 — 값이 바뀌면 여기도 손으로 맞춘다).
 *  ⚠️ 라벨 문구는 엔진의 세션 임시안 — 파트너 문장 대기. 모르는 뼈 키는 키 그대로 보여준다. */
const BONES: Record<string, string> = {
  talk: '이야기를 나눔', fought: '함께 싸움', waited: '나를 기다려 줌',
  rescued: '나를 구함', at_death: '죽을 때 곁에 있었음',
  proposed: '제안함', asked: '제안받음', answered: '내 제안에 답함', replied: '제안에 답해 줌',
  gave: '물건을 건넴', received: '물건을 받음', bond: '친목행위',
};
const BONE_ORDER = Object.keys(BONES);          // 횟수가 같으면 사전 순서(안정)

const FALLBACK_TEXT = '⚙ 규칙 두뇌가 대신 움직였다';   // viewer/index.html 의 폴백 문장(폴백은 페르소나로 인용하지 않는다)

const CSS = `
#focusCard .fc { border: 1px solid var(--line); background: var(--panel2); border-radius: 6px; padding: 8px 10px;
  display: flex; flex-direction: column; gap: 5px; font-size: 13px; line-height: 1.4; }
#focusCard .fc-empty { color: var(--dim); font-size: 12px; padding: 6px 2px; }
.fc-head { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
.fc-name { font-weight: bold; font-size: 15px; }
.fc-job { color: var(--dim); font-size: 12px; }
.fc-mark { color: var(--gold); font-size: 12px; margin-left: auto; }
.fc-mark:empty { display: none; }
.fc.dead .fc-name { filter: grayscale(1); opacity: .7; }
.fc-sheet { color: var(--dim); font-size: 12px; line-height: 1.35; }
.fc-sheet:empty { display: none; }
.fc-sheet b { color: var(--fg); font-weight: normal; }
.fc-hpline { display: flex; align-items: center; gap: 6px; }
.fc-hpbar { flex: 1; height: 8px; background: #0e1014; border-radius: 4px; overflow: hidden; }
.fc-hpfill { height: 100%; background: var(--hp); transition: width .25s; }
.fc.snap .fc-hpfill { transition: none; }
.fc-hp { font-size: 12px; min-width: 44px; text-align: right; font-variant-numeric: tabular-nums; }
.fc-status { font-size: 11px; min-height: 1.1em; }
.fc-status .tag { display: inline-block; padding: 0 5px; border-radius: 3px; background: #2a2330; color: #f4a0c0; margin-right: 3px; }
.fc-status:empty::before { content: '—'; color: var(--dim); }
.fc-items { font-size: 12px; }
.fc-items .none { color: var(--dim); }
.fc-items .bonus { color: var(--gold); }
.fc-sec { color: var(--dim); font-size: 11px; letter-spacing: .5px; border-top: 1px solid var(--line); padding-top: 5px; margin-top: 2px; }
.fc-reason, .fc-say, .fc-line { word-break: break-word; }
.fc-reason.plan { color: var(--gold); }
.fc-reason.fb, .fc-say.none, .fc-line.none, .fc-bones.none { color: var(--dim); }
.fc .t { color: var(--dim); font-size: 11px; white-space: nowrap; }
.fc-say .kind { display: inline-block; padding: 0 5px; border-radius: 3px; background: #2b3040; color: var(--accent);
  font-size: 11px; margin-right: 4px; vertical-align: 1px; }
.fc-say .to { color: var(--dim); }
.fc-say .bub { color: #fff; }
.fc-rel { padding-top: 4px; }
.fc-rel + .fc-rel { border-top: 1px dashed var(--line); margin-top: 3px; }
.fc-rel-name { font-weight: bold; }
.fc-bones { font-size: 12px; }
.fc-bones .n { color: var(--gold); font-variant-numeric: tabular-nums; }
.fc-line { font-size: 12px; font-style: italic; }
.fc-line.none { font-style: normal; }
`;

/* ───────────── 결정 색인(판 단위) ───────────── */

interface DecIdx { reason: number[]; say: number[]; rel: Record<Char, number[]> }   // 프레임 번호 오름차순

/** 속내로 셀 결정인가 — 폴백은 reason 이 없어도 한 줄(FALLBACK_TEXT), 엔진이 건너뛴 결정은 로그처럼 안 센다. */
function hasReason(d: Decision | undefined): boolean {
  return !!d && !d.skipped && (d.src === 'fallback' || !!d.reason);
}
function hasSay(d: Decision | undefined): boolean {
  return !!d && !d.skipped && d.src !== 'fallback' && !!d.say;
}
function hasRel(d: Decision | undefined): boolean {
  return !!d && !d.skipped && !!d.relation && !!d.relation.to && !!d.relation.line;
}

/** arr(오름차순)에서 idx 이하의 가장 큰 값, 없으면 -1. */
function lastLE(arr: number[] | undefined, idx: number): number {
  if (!arr || !arr.length) return -1;
  let lo = 0, hi = arr.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] <= idx) { ans = arr[mid]; lo = mid + 1; } else hi = mid - 1;
  }
  return ans;
}

/** 캐릭터 한 사람의 '현재 프레임 이전(포함) 가장 최근' — 프레임 자체를 들고 있다(turn·decisions 를 같이 쓴다). */
interface Latest { reason: Frame | null; say: Frame | null; rel: Record<Char, Frame | null> }

/* ───────────── 문장 ───────────── */

function gearText(g: Gear | null | undefined, none: string): string {
  if (!g || !g.name) return `<span class="none">${none}</span>`;
  const b = typeof g.bonus === 'number' && g.bonus !== 0 ? ` <span class="bonus">${g.bonus > 0 ? '+' : '−'}${Math.abs(g.bonus)}</span>` : '';
  return esc(g.name) + b;
}

function bonesHtml(rel: Record<string, number> | undefined): string {
  if (!rel) return '';
  const keys = Object.keys(rel).filter(k => (rel[k] ?? 0) > 0);
  keys.sort((a, b) => (rel[b] - rel[a]) || (BONE_ORDER.indexOf(a) - BONE_ORDER.indexOf(b)));
  return keys.map(k => `${esc(BONES[k] ?? k)} <span class="n">${rel[k]}</span>`).join(' · ');
}

/* ───────────── 설치 ───────────── */

interface RelRow { root: HTMLElement; bones: HTMLElement; line: HTMLElement }
interface Nodes {
  fc: HTMLElement; name: HTMLElement; job: HTMLElement; mark: HTMLElement; sheet: HTMLElement;
  hpfill: HTMLElement; hp: HTMLElement; status: HTMLElement; items: HTMLElement;
  reason: HTMLElement; say: HTMLElement; rels: HTMLElement; reactions: HTMLElement; skills: HTMLElement;
}

export function installFocusCard(app: App): void {
  if (!document.getElementById('style-focuscard')) {
    const st = document.createElement('style'); st.id = 'style-focuscard'; st.textContent = CSS;
    document.head.appendChild(st);
  }
  const root = app.dom.focusCard;

  // ── 색인·캐시(판마다 리셋) ──
  let idxRun: Run | null = null;
  let indexed = 0;                                   // 색인이 덮은 프레임 수(frames 는 제자리 성장 — 라이브)
  const decIdx = new Map<Char, DecIdx>();
  const absentCache = new Map<string, Bot | null>(); // "char@levelIdx" → 이 층에 없을 때 마지막으로 있던 스냅샷
  let state: { char: Char; idx: number; latest: Latest } | null = null;   // step 덧쓰기용

  function resetIndex(run: Run | null): void {
    idxRun = run; indexed = 0; decIdx.clear(); absentCache.clear(); state = null;
  }
  function ensureIndex(run: Run): void {
    if (idxRun !== run) resetIndex(run);
    const fr = run.frames;
    for (let i = indexed; i < fr.length; i++) {
      const decs = fr[i].decisions;
      if (!decs) continue;
      for (const c of Object.keys(decs)) {
        const d = decs[c];
        let di = decIdx.get(c);
        if (!di) { di = { reason: [], say: [], rel: {} }; decIdx.set(c, di); }
        if (hasReason(d)) di.reason.push(i);
        if (hasSay(d)) di.say.push(i);
        if (hasRel(d)) (di.rel[d.relation!.to] ??= []).push(i);
      }
    }
    indexed = fr.length;
  }
  /** seek: 색인에서 이진 탐색. */
  function computeLatest(run: Run, char: Char, idx: number, others: Char[]): Latest {
    ensureIndex(run);
    const di = decIdx.get(char);
    const fr = run.frames;
    const at = (i: number): Frame | null => (i >= 0 ? fr[i] : null);
    const rel: Record<Char, Frame | null> = {};
    for (const o of others) rel[o] = at(lastLE(di?.rel[o], idx));
    return { reason: at(lastLE(di?.reason, idx)), say: at(lastLE(di?.say, idx)), rel };
  }
  /** step/play(+1): 현재 프레임의 결정만 덧쓴다. */
  function patchLatest(latest: Latest, cur: Frame, char: Char): void {
    const d = cur.decisions?.[char];
    if (!d) return;
    if (hasReason(d)) latest.reason = cur;
    if (hasSay(d)) latest.say = cur;
    if (hasRel(d) && d.relation!.to in latest.rel) latest.rel[d.relation!.to] = cur;
  }
  function latestFor(run: Run, char: Char, ch: FrameChange, others: Char[]): Latest {
    if (ch.mode !== 'seek' && state && state.char === char && state.idx === ch.idx - 1 && idxRun === run) {
      patchLatest(state.latest, ch.cur, char);
      state.idx = ch.idx;
      return state.latest;
    }
    const latest = computeLatest(run, char, ch.idx, others);
    state = { char, idx: ch.idx, latest };
    return latest;
  }
  /** 이 층 스냅샷에 없는 캐릭터 — 마지막으로 있던 프레임의 값(층 단위 캐시). */
  function lastBot(run: Run, char: Char, f: Frame): Bot | null {
    const key = `${char}@${f.levelIdx}`;
    const hit = absentCache.get(key);
    if (hit !== undefined) return hit;
    let found: Bot | null = null;
    for (let i = f.idx - 1; i >= 0; i--) {
      const b = run.frames[i].bots.find(x => x.char === char);
      if (b) { found = b; break; }
    }
    absentCache.set(key, found);
    return found;
  }

  // ── DOM(한 번 만들고 텍스트만 바꾼다) ──
  const written = new WeakMap<HTMLElement, string>();
  function put(n: HTMLElement, htmlStr: string): void {
    if (written.get(n) === htmlStr) return;
    written.set(n, htmlStr); n.innerHTML = htmlStr;
  }
  let nodes: Nodes | null = null;
  let rows = new Map<Char, RelRow>();
  let rowsFor: Char | null = null;                   // 관계 줄이 어느 캐릭터 기준인가
  let rowsRun: Run | null = null;

  function buildSkeleton(): Nodes {
    root.innerHTML = '';
    const fc = el('div', 'fc');
    fc.innerHTML =
      `<div class="fc-eyebrow">지금 바라보는 모험가</div>` +
      `<div class="fc-head"><span class="fc-name"></span><span class="fc-job"></span><span class="fc-mark"></span></div>` +
      `<div class="fc-hpline"><span class="fc-hplabel">HP</span><div class="fc-hpbar"><div class="fc-hpfill"></div></div><span class="fc-hp"></span></div>` +
      `<div class="fc-status"></div>` +
      `<div class="fc-items"></div>` +
      `<section class="fc-block fc-skill-section" hidden><h2 class="fc-sec">보유 스킬</h2><div class="fc-skills"></div>` +
      `<div class="wl-skill-note">대기는 다른 행동을 완료할 때 줄어들어.<br>준비된 스킬도 대상의 거리·시야·조건이 맞아야 해.</div></section>` +
      `<section class="fc-block"><h2 class="fc-sec">속내</h2><div class="fc-reason"></div></section>` +
      `<section class="fc-block fc-dialogue"><h2 class="fc-sec">최근 대화</h2><div class="fc-say"></div></section>` +
      `<details class="fc-profile"><summary>캐릭터 설정</summary><div class="fc-sheet"></div></details>` +
      `<section class="fc-block"><h2 class="fc-sec">동료에 대한 생각</h2><div class="fc-rels"></div></section>` +
      `<section class="fc-block"><h2 class="fc-sec">남긴 반응 · 관전 집계</h2><div class="fc-reactions"></div></section>`;
    root.appendChild(fc);
    const q = (s: string): HTMLElement => fc.querySelector(s) as HTMLElement;
    return { fc, name: q('.fc-name'), job: q('.fc-job'), mark: q('.fc-mark'), sheet: q('.fc-sheet'),
             hpfill: q('.fc-hpfill'), hp: q('.fc-hp'), status: q('.fc-status'), items: q('.fc-items'),
             reason: q('.fc-reason'), say: q('.fc-say'), rels: q('.fc-rels'), reactions: q('.fc-reactions'), skills: q('.fc-skills') };
  }
  /** 관계 줄 = 파티의 다른 캐릭터마다 하나(파티 순서). 초점·판이 바뀔 때만 다시 만든다. */
  function buildRows(run: Run, char: Char, n: Nodes): void {
    if (rowsFor === char && rowsRun === run && rows.size) return;
    n.rels.innerHTML = ''; rows = new Map(); rowsFor = char; rowsRun = run;
    for (const p of run.party) {
      if (p.char === char) continue;
      const row = el('div', 'fc-rel'); row.dataset.other = p.char;
      row.innerHTML = `<div class="fc-rel-name" style="color:${esc(run.colors[p.char] || '#fff')}">${esc(run.names[p.char] || p.char)}` +
                      ` <span class="fc-job">${esc(run.jobs[p.char] || '')}</span></div>` +
                      `<div class="fc-line"></div><details class="fc-history"><summary>함께한 일</summary><div class="fc-bones"></div></details>`;
      n.rels.appendChild(row);
      rows.set(p.char, { root: row, bones: row.querySelector('.fc-bones') as HTMLElement, line: row.querySelector('.fc-line') as HTMLElement });
    }
    if (!rows.size) n.rels.innerHTML = '<div class="fc-empty">혼자 왔다 — 관계 없음</div>';
  }

  function showEmpty(msg: string): void {
    nodes = null; rows = new Map(); rowsFor = null;
    root.innerHTML = `<div class="fc-empty">${esc(msg)}</div>`;
  }

  function render(ch: FrameChange | null): void {
    const run = app.run, char = app.focus.char;
    const f = ch?.cur ?? app.playback.cur;
    if (!run || !f || !char) { showEmpty(!run ? '판을 열면 초점 캐릭터가 여기 보인다' : (!f ? '틱이 아직 없다' : '초점 캐릭터가 없다')); return; }
    const change: FrameChange = ch ?? { prev: null, cur: f, idx: app.playback.idx, mode: 'seek' };
    if (!nodes) nodes = buildSkeleton();
    const n = nodes;
    const member: PartyMember | undefined = run.party.find(p => p.char === char);
    const others = run.party.filter(p => p.char !== char).map(p => p.char);
    buildRows(run, char, n);
    const stats = f.reaction_stats;
    put(n.reactions, stats
      ? `<b>이번 층</b><br>${reactionSummaryHtml(stats.floor, run, char)}<br>` +
        `<b>원정 전체</b><br>${reactionSummaryHtml(stats.run, run, char)}`
      : '<span class="none">반응 기록이 없는 이전 판</span>');

    // ── 머리: 이름·직업·성별·표식 ──
    n.fc.dataset.char = char;
    n.fc.style.setProperty('--char-color', run.colors[char] || '#fff');
    n.fc.classList.toggle('snap', change.mode === 'seek');
    n.name.style.color = run.colors[char] || '#fff';
    put(n.name, esc(run.names[char] || char));
    const sex = member?.sex ? ` · ${esc(member.sex)}` : '';
    put(n.job, esc(run.jobs[char] || member?.job || '?') + sex);
    const sheetBits: string[] = [];
    if (member?.persona) sheetBits.push(`<p><b>성격</b>${esc(member.persona)}</p>`);
    if (typeof member?.background === 'string' && member.background) sheetBits.push(`<p><b>배경</b>${esc(member.background)}</p>`);
    if (member?.goal) sheetBits.push(`<p><b>목표</b>${esc(member.goal)}</p>`);
    put(n.sheet, sheetBits.join(''));
    (n.sheet.parentElement as HTMLDetailsElement).hidden = !sheetBits.length;

    // ── 몸: 스냅샷(이 층에 없으면 마지막으로 있던 값) ──
    let b: Bot | null = f.bots.find(x => x.char === char) ?? null;
    const absent = !b;
    if (!b) b = lastBot(run, char, f);
    const skillCards = skillsHtml(run.meta?.alpha, b);
    put(n.skills, skillCards);
    n.skills.parentElement!.hidden = !skillCards;
    const deadNow = b ? !b.alive : false;
    const deadTurn = run.deathTurn[char];
    const dead = deadNow || (absent && deadTurn !== undefined && deadTurn <= f.turn);
    const won = !!b && b.alive && b.won && !absent;
    const marks: string[] = [];
    if (dead) marks.push(`☠ 전사 (t${deadTurn ?? '?'})`);
    else if (won) marks.push('▼ 먼저 내려갔다');
    if (absent) marks.push('이 층에 없다');
    put(n.mark, marks.map(esc).join(' · '));
    n.fc.classList.toggle('dead', dead);
    n.fc.classList.toggle('won', won);
    n.fc.classList.toggle('absent', absent);

    if (b) {
      const maxhp = Math.max(1, b.maxhp || member?.maxhp || 1);
      const hp = Math.max(0, b.hp);
      const r = Math.max(0, Math.min(1, hp / maxhp));
      const w = (r * 100) + '%';
      if (n.hpfill.style.width !== w) n.hpfill.style.width = w;
      const col = r > 0.5 ? 'var(--hp)' : (r > 0.25 ? 'var(--mid)' : 'var(--low)');   // 칩과 같은 색 규칙
      if (n.hpfill.style.background !== col) n.hpfill.style.background = col;
      put(n.hp, `${hp}/${b.maxhp}`);
      put(n.status, (b.status || []).map(s => `<span class="tag">${esc(s)}</span>`).join(''));
      put(n.items, `<div><span>물약</span><strong>${b.potions ?? 0}병</strong></div><div><span>무기</span><strong>${gearText(b.weapon, '맨손')}</strong></div><div><span>방어구</span><strong>${gearText(b.armor, '맨몸')}</strong></div>`);
    } else {
      if (n.hpfill.style.width !== '0%') n.hpfill.style.width = '0%';
      put(n.hp, '—'); put(n.status, ''); put(n.items, '<span class="none">—</span>');
    }

    // ── 속내·최근 말·관계 한 줄(가장 최근 결정 — 판 전체에서, 층 무관) ──
    const latest = latestFor(run, char, change, others);
    const t = (fr: Frame): string => ` <span class="t">(t${fr.turn})</span>`;
    const rd = latest.reason?.decisions[char];
    n.reason.classList.toggle('plan', rd?.src === 'plan');
    n.reason.classList.toggle('fb', rd?.src === 'fallback');
    n.reason.classList.toggle('none', !rd);
    if (!rd || !latest.reason) put(n.reason, '<span class="none">아직 없음</span>');
    else if (rd.src === 'fallback') put(n.reason, `${FALLBACK_TEXT}${t(latest.reason)}`);
    else put(n.reason, `${esc(rd.reason)}${t(latest.reason)}`);   // src=plan 은 "[작정] …" 그대로

    const sd = latest.say?.decisions[char];
    n.say.classList.toggle('none', !sd);
    if (!sd || !latest.say) put(n.say, '아직 없음');
    else {
      const kind = sd.say_kind === '제안' ? '<span class="kind">제안</span>' : '';
      const to = sd.to ? `<span class="to">→ ${sd.to === 'all' ? '모두' : esc(run.names[sd.to] || sd.to)}</span> ` : '';
      put(n.say, `${kind}${to}<span class="bub">「${esc(sd.say)}」</span>${t(latest.say)}`);
    }

    for (const o of others) {
      const row = rows.get(o);
      if (!row) continue;
      const bones = bonesHtml(b?.relations?.[o]);
      row.bones.classList.toggle('none', !bones);
      put(row.bones, bones || '—');
      const lf = latest.rel[o];
      const line = lf?.decisions[char]?.relation?.line;
      row.line.classList.toggle('none', !line);
      put(row.line, line && lf ? `「${esc(line)}」${t(lf)}` : '아직 남긴 생각이 없어요.');
    }
  }

  app.bus.on('run', run => { resetIndex(run); nodes = null; rowsFor = null; render(null); });
  app.playback.on('frame', ch => render(ch));
  app.focus.on('change', () => render(null));
  render(null);
}
