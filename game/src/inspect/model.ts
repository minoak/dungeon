// 관전 클릭 보기의 순수 모형(p0.5.12 — 설계 .orch/drafts/viewer_click_design.md v1 · DECISIONS 2026-10-14 99·100행).
// 런타임 import 가 없다(import type 만) — 게이트(verify_viewer_click.py)가 node --experimental-strip-types 로 이 파일을 직접 불러 엔진과 맞대 본다.
//   접기: 시작 원장(run_meta.lore + 지난 판 도감 note) + 프레임의 resume·book_line·lore_ops·lore_tail → 사람마다 열쇠마다 판본 목록(프레임 오름차순).
//         아무 프레임의 값 = 그 목록에서 프레임 번호 이하의 마지막 판본(이진 탐색 — 되감기·라이브 성장이 같은 길). 종 앎 = run_meta.bestiary + known_ops.
//         파이썬 기준은 lorebook.fold_stream — 규칙을 바꾸면 둘을 같이 바꾼다(게이트 ②가 맞대 본다).
//   부르는 이름: identity.call · identity.grave_label · 엔진 _knowledge('낯선 짐승')와 같은 규칙. ⚠️ ID-6(0.5.18)이 identity.call 을 바꾸면 여기도 같은 커밋에서(게이트 ⑤).
//   대상 → 안쪽 열쇠: lorebook.inner_key·anchors 와 같은 규칙(게이트 ③). 겹침 순서: 사람 > 몬스터(산 것 → 시체) > 물건·설비 > 함정 > 문·계단 > 장소.
// 정보 등급: 관전자는 세계의 겉을 다 안다(실명·HP·물건 설명·모두의 기록 — STREAM_FORMAT '관전자는 안다'). 물건의 속(item.lore)은 스트림에 없다.
import type { Bot, Char, CellRuns, Decision, Feature, Frame, LevelLine, LoreEntry, LoreOps, Monster, PartyMember, Run, Trap } from '../stream/types';

export const STRANGER = '낯선 사람';            // identity.STRANGER
export const SOMEONE = '누군가';                // identity.SOMEONE
export const SELF = '너';                      // identity.SELF
export const UNKNOWN_BEAST = '낯선 짐승';       // dungeon_gm.UNKNOWN_BEAST
const NOTE_LEN = 80;                           // bestiary.NOTE_LEN(도감 note 상한)

/* ───────────── 접기(색인) ───────────── */

export interface Version { f: number; e: LoreEntry | null }      // f = 프레임 번호(-1 = 판 시작), e = 항목 | 지움
export interface LoreIndex {
  run: Run;
  sig: string;                                  // 색인을 만든 때의 판 모양(프레임 수·끝 줄) — 바뀌면 다시 만든다
  people: boolean;                              // 인물 기록 판(run_meta.strangers) — 아니면 기록 칸이 없던 옛 판
  books: Record<Char, Record<string, Version[]>>;
  known: Record<Char, Record<string, number>>;  // 종 열쇠 → 처음 안 프레임(-1 = 판 시작)
}

/** run_meta.party 항목 → 도감 원장 열쇠(lorebook.ledger_key — id → 이름 → '봇N'). */
export function ledgerKey(p: PartyMember): string {
  return (typeof p.id === 'string' && p.id) || p.name || '봇' + p.char;
}

export function indexSig(run: Run): string {
  const fr = run.frames, last = fr[fr.length - 1];
  return `${fr.length}|${run.end ? 1 : 0}|${last?.lore_tail?.length ?? 0}|${last?.resume ? 1 : 0}`;
}

/** 키 순서와 무관한 같음(판본을 거듭 쌓지 않으려고). */
function stable(e: LoreEntry | null): string {
  if (!e) return '';
  const o = e as unknown as Record<string, unknown>;
  return JSON.stringify(Object.keys(o).sort().map(k => [k, o[k]]));
}

export function buildIndex(run: Run): LoreIndex {
  const meta = run.meta;
  const ix: LoreIndex = { run, sig: indexSig(run), people: !!(meta?.strangers || meta?.lore), books: {}, known: {} };
  const cur: Record<Char, Record<string, LoreEntry>> = {};
  const put = (c: Char, key: string, f: number, e: LoreEntry | null): void => {
    const state = (cur[c] ??= {}), now = state[key] ?? null;
    if (stable(now) === stable(e)) return;
    ((ix.books[c] ??= {})[key] ??= []).push({ f, e });
    if (e) state[key] = e; else delete state[key];
  };
  for (const p of run.party) {
    const c = p.char, lk = ledgerKey(p);
    ix.books[c] ??= {}; ix.known[c] ??= {};
    for (const [k, e] of Object.entries(meta?.lore?.[c] ?? {})) put(c, k, -1, { ...e });
    for (const [k, e] of Object.entries(meta?.bestiary_progress?.[lk] ?? {})) {
      if (k.startsWith('monster:') && e.note?.text) put(c, k, -1, { text: e.note.text, turn: 0, src: 'book' });   // 지난 판 도감 note
    }
    for (const k of meta?.bestiary?.[lk] ?? []) ix.known[c][k] = -1;
  }
  const apply = (ops: LoreOps | undefined, i: number, decs?: Record<Char, Decision>): void => {
    for (const [c, list] of Object.entries(ops ?? {})) {
      const d = decs?.[c];
      const skip = d && (d.skipped || d.src === 'plan') ? d.lore_note?.key : undefined;   // 발급기가 접지 않는 결정의 도감 note
      for (const o of list) {
        if (o.op === 'set') {
          if (o.key.startsWith('monster:') && o.key === skip) continue;
          put(c, o.key, i, { ...(o.entry ?? {}) });
        } else put(c, o.key, i, null);                 // fade·sweep·merge = 지움
      }
    }
  };
  run.frames.forEach((f, i) => {
    if (f.resume?.lore) {                              // 이어가기 — 그 순간의 모든 몸 원장으로 갈아 끼운다(도감 note 는 발급기 몫이라 그대로)
      for (const [c, b] of Object.entries(f.resume.lore)) {
        for (const k of Object.keys(cur[c] ?? {})) if (!k.startsWith('monster:') && !(k in b)) put(c, k, i, null);
        for (const [k, e] of Object.entries(b)) put(c, k, i, { ...e });
      }
    }
    if (f.kind === 'tick') {
      for (const c of Object.keys(f.decisions).sort()) {   // D55 도감평 — 발급기 _settle 과 같은 조건(book_line 먼저, lore_note 나중)
        const d = f.decisions[c], bl = d.book_line;
        const text = String(bl?.text ?? '').trim();
        if (bl && text && !d.skipped && d.src !== 'plan') put(c, bl.key, i, { text: text.slice(0, NOTE_LEN), turn: f.turn, src: 'self' });
      }
      apply(f.lore_ops, i, f.decisions);
      for (const [c, ks] of Object.entries(f.known_ops ?? {})) {
        const kn = (ix.known[c] ??= {});
        for (const k of ks) if (!(k in kn)) kn[k] = i;
      }
    }
    for (const t of f.lore_tail ?? []) apply(t, i);
  });
  return ix;
}

const cache = new WeakMap<Run, LoreIndex>();
/** 판마다 한 번(라이브는 판 모양이 바뀔 때만 다시 — 판 전체를 다시 접어도 틱 수백에 1ms 안쪽). */
export function loreIndex(run: Run): LoreIndex {
  let ix = cache.get(run);
  if (!ix || ix.sig !== indexSig(run)) { ix = buildIndex(run); cache.set(run, ix); }
  return ix;
}

function lastAt(vs: Version[] | undefined, i: number): number {
  if (!vs) return -1;
  let lo = 0, hi = vs.length - 1, ans = -1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (vs[mid].f <= i) { ans = mid; lo = mid + 1; } else hi = mid - 1; }
  return ans;
}

/** 그 사람의 그 열쇠가 프레임 i 에서 가진 값(없으면 null). */
export function valueAt(ix: LoreIndex, c: Char, key: string, i: number): LoreEntry | null {
  const vs = ix.books[c]?.[key];
  const at = lastAt(vs, i);
  return at >= 0 ? vs![at].e : null;
}

/** 고쳐 쓰기 전의 글들(최근 것부터, 지금 글과 같은 것·되풀이는 뺀다) — '이전 글 n'. */
export function historyAt(ix: LoreIndex, c: Char, key: string, i: number): string[] {
  const vs = ix.books[c]?.[key];
  const at = lastAt(vs, i);
  const now = at >= 0 ? vs![at].e?.text ?? '' : '';
  const out: string[] = [];
  for (let j = at - 1; j >= 0; j--) {
    const t = vs![j].e?.text;
    if (t && t !== now && !out.includes(t)) out.push(t);
  }
  return out;
}

/** 이 판에서 프레임 i 까지 그 열쇠를 쓴 횟수(판 시작 판본·지움은 빼고) — 도감평의 '고쳐 씀 n번째'. */
export function writesAt(ix: LoreIndex, c: Char, key: string, i: number): number {
  return (ix.books[c]?.[key] ?? []).filter(v => v.f >= 0 && v.f <= i && v.e).length;
}

/** 판 시작 판본(지난 판 도감 note·시트 씨앗) — 없으면 null. */
export function startOf(ix: LoreIndex, c: Char, key: string): LoreEntry | null {
  const v = ix.books[c]?.[key]?.[0];
  return v && v.f < 0 ? v.e : null;
}

/** 그 사람의 프레임 i 장부 전부 {열쇠: 항목} — '기록' 탭·게이트 ②. */
export function ledgerAt(ix: LoreIndex, c: Char, i: number): Record<string, LoreEntry> {
  const out: Record<string, LoreEntry> = {};
  for (const [k, vs] of Object.entries(ix.books[c] ?? {})) {
    const at = lastAt(vs, i);
    if (at >= 0 && vs[at].e) out[k] = vs[at].e!;
  }
  return out;
}

export function knows(ix: LoreIndex, c: Char, key: string, i: number): boolean {
  const f = ix.known[c]?.[key];
  return f !== undefined && f <= i;
}

/** 그 사람이 프레임 i 에 아는 종 열쇠 전부(게이트 ⑩). */
export function knownAt(ix: LoreIndex, c: Char, i: number): string[] {
  return Object.entries(ix.known[c] ?? {}).filter(([, f]) => f <= i).map(([k]) => k).sort();
}

/* ───────────── 부르는 이름(엔진과 같은 규칙) ───────────── */

export function isPersonKey(k: string): boolean { return /^b\d+$/.test(k) || (k.startsWith('npc:') && k.length > 4); }

/** identity.call — 보는 사람이 모험가를 부르는 말. people = 그 사람의 장부(null = 옛 판·관전자 → 실명). */
export function callWith(people: Record<string, LoreEntry> | null, viewer: Char | null, target: Char, real: string): string {
  if (viewer !== null && viewer === target) return SELF;
  if (!people) return real;
  return people['b' + target]?.name || STRANGER;
}

/** identity.grave_label — '<호칭>의 묘'(모르면 '누군가의 묘', 내 묘는 내 이름). people null = 옛 판(피처 이름 그대로). */
export function graveWith(people: Record<string, LoreEntry> | null, viewer: Char | null, owner: Char | undefined,
                          ownName: string, fname: string): string {
  if (!people || owner === undefined) return fname;
  if (viewer !== null && owner === viewer) return (ownName || SOMEONE) + '의 묘';
  const nm = people['b' + owner]?.name || STRANGER;
  return (nm === STRANGER ? SOMEONE : nm) + '의 묘';
}

function peopleOf(ix: LoreIndex, viewer: Char | null, i: number): Record<string, LoreEntry> | null {
  if (!ix.people || viewer === null) return null;
  const out: Record<string, LoreEntry> = {};
  for (const [k, e] of Object.entries(ledgerAt(ix, viewer, i))) if (isPersonKey(k)) out[k] = e;
  return out;
}

export function callBot(ix: LoreIndex, viewer: Char | null, target: Char, i: number): string {
  const real = ix.run.names[target] || target;
  if (viewer !== null && viewer === target) return SELF;
  if (!ix.people || viewer === null) return real;
  return valueAt(ix, viewer, 'b' + target, i)?.name || STRANGER;
}

/** 엔진 _knowledge — 그 사람이 그 종을 알면 종 이름, 모르면 '낯선 짐승'(옛 판·관전자는 종 이름). */
export function monsterName(ix: LoreIndex, viewer: Char | null, kind: string, i: number): string {
  if (!ix.people || viewer === null) return kind;
  return knows(ix, viewer, 'monster:' + kind, i) ? kind : UNKNOWN_BEAST;
}

export function featName(ix: LoreIndex, viewer: Char | null, ft: Feature, i: number): string {
  if (ft.type !== 'grave') return ft.name;
  const own = ix.run.party.find(p => p.char === viewer);
  return graveWith(peopleOf(ix, viewer, i), viewer, ft.of, own?.name || own?.job || '', ft.name);
}

/* ───────────── 대상 ───────────── */

export type Target =
  | { t: 'bot'; char: Char }
  | { t: 'mob'; id: number }
  | { t: 'feat'; id: number }
  | { t: 'trap'; idx: number }                  // 엔진 d.traps 의 자리 = 스트림 traps 배열 자리(붙이기만 해서 밀리지 않는다)
  | { t: 'exit' }
  | { t: 'door'; id: string }
  | { t: 'zone'; id: string }                   // 관측의 장소 번호(obs.zone.id — 스캐너 구역 r·c, 마을의 생성기 방 r0)
  | { t: 'region'; name: string };              // 마을 구역(obs.town_zone)

export function targetId(t: Target): string {
  switch (t.t) {
    case 'bot': return 'b' + t.char;
    case 'mob': return 'm' + t.id;
    case 'feat': return 'f' + t.id;
    case 'trap': return 't' + t.idx;
    case 'exit': return 'exit';
    case 'door': return t.id;
    case 'zone': return 'zone:' + t.id;
    case 'region': return 'region:' + t.name;
  }
}

/** 칸 → 구간 값(level.zones 의 rows). */
export function cellRun(runs: CellRuns | undefined, x: number, y: number): string | null {
  const row = runs?.rows[y];
  if (!row) return null;
  for (let j = 0; j + 2 < row.length; j += 3) if (x >= row[j] && x < row[j] + row[j + 1]) return runs!.ids[row[j + 2]] ?? null;
  return null;
}

export function doorAt(L: LevelLine, x: number, y: number): string | null {
  return L.doors?.find(d => d[0] === x && d[1] === y)?.[2] ?? null;
}

/** 이 프레임까지 그 피처의 마지막 스냅샷 — 이 프레임 틱 목록에 없으면(주워 갔다 등) 같은 층의 앞 프레임을 거슬러, 그래도 없으면 층 줄.
 *  층 줄로 바로 가면 안 된다: 장비 uid 는 누가 기록하는 순간 붙어 그 뒤 프레임에만 있다(p0512b — Codex p0512r: 기록한 장비를 주우면 gear:<uid> 를 obj: 로 찾았다). */
function featAt(ix: LoreIndex, f: Frame, id: number): Feature | undefined {
  const own = f.features.find(x => x.id === id);
  if (own) return own;
  const fr = ix.run.frames;
  for (let j = f.idx - 1; j >= 0 && fr[j]?.levelIdx === f.levelIdx; j--) {
    const hit = fr[j].features.find(x => x.id === id);
    if (hit) return hit;
  }
  return f.level.features.find(x => x.id === id);
}
function levelSpace(L: LevelLine, id: number): string | undefined {
  return L.features.find(x => x.id === id)?.space;
}
export function present(f: Frame, t: Target): boolean {
  switch (t.t) {
    case 'bot': return f.bots.some(b => b.char === t.char);
    case 'mob': return f.monsters.some(m => m.id === t.id);
    case 'feat': return f.features.some(x => x.id === t.id);
    case 'trap': return !!f.traps[t.idx];
    case 'exit': return true;
    case 'door': return !!f.level.doors?.some(d => d[2] === t.id);
    case 'zone': return !!f.level.zones?.ids.includes(t.id);
    case 'region': return !!f.level.zones?.town?.ids.includes(t.name);
  }
}

/** 대상 → 안쪽 열쇠(lorebook.inner_key·anchors). one = 개별, kind = 종류(보는 사람이 부르는 이름으로). self = 보는 사람 자신(기록이 없다). */
export interface Keys { one: string | null; kind: string | null; self?: boolean }
export function keysFor(ix: LoreIndex, viewer: Char | null, tg: Target, f: Frame, i: number): Keys {
  const obj = (at: string) => `obj:${f.level.scope || 0}:${at}`;
  switch (tg.t) {
    case 'bot':
      return viewer === tg.char ? { one: null, kind: null, self: true } : { one: 'b' + tg.char, kind: null };
    case 'mob': {
      const m = f.monsters.find(x => x.id === tg.id);
      if (!m) return { one: obj('m' + tg.id), kind: null };
      const nm = monsterName(ix, viewer, m.kind, i);
      const mk = 'monster:' + m.kind;
      const kind = nm === UNKNOWN_BEAST ? 'kind:' + UNKNOWN_BEAST
        : (viewer !== null && valueAt(ix, viewer, mk, i)) || !ix.people ? mk : 'kind:' + m.kind;   // 도감 note 가 있으면 그것(합류 전의 같은 이름 기록은 안 띄운다 — lorebook.observe)
      return { one: obj('m' + tg.id), kind };
    }
    case 'feat': {
      const ft = featAt(ix, f, tg.id);
      if (!ft) return { one: obj('f' + tg.id), kind: null };
      if (ft.type === 'npc') return { one: 'npc:' + ft.name, kind: null };
      if (ft.type === 'exit') return keysFor(ix, viewer, { t: 'exit' }, f, i);
      if (ft.type === 'weapon' || ft.type === 'armor') return { one: ft.uid ? 'gear:' + ft.uid : obj('f' + ft.id), kind: 'kind:' + ft.name };
      const sp = levelSpace(f.level, ft.id);
      if (sp) return { one: 'place:' + sp, kind: 'kind:' + ft.name };
      return { one: obj('f' + ft.id), kind: 'kind:' + featName(ix, viewer, ft, i) };
    }
    case 'trap': {
      const tr = f.traps[tg.idx];
      return { one: obj('t' + tg.idx), kind: tr ? 'kind:' + tr.name : null };
    }
    case 'exit': return { one: obj('exit'), kind: 'kind:' + (f.level.gate ? '워프게이트' : '계단') };
    case 'door': return { one: obj(tg.id), kind: 'kind:문' };
    case 'zone': return { one: obj(tg.id), kind: null };
    case 'region': return { one: 'zone:' + tg.name, kind: null };
  }
}

/* ───────────── 겹침 순서 ───────────── */

/** 누른 자리의 후보 하나. group: 0 사람 · 1 몬스터 · 2 물건·설비 · 3 함정 · 4 문·계단 · 5 장소. depth = 씬의 실제 그리기 깊이(클수록 앞 —
 *  같은 줄이라도 NPC·몹은 모험가보다 0.005 뒤에 그려진다), y = 그 칸의 줄. */
export interface Pick { target: Target; group: number; depth: number; y: number; n: number; dead?: boolean }
export const GROUP = { person: 0, monster: 1, thing: 2, trap: 3, passage: 4, place: 5 } as const;

/** 정한 순서 — 무리 → (몬스터는 산 것 먼저) → 앞에 그려진 것(그리기 깊이가 큰 것 — p0512b: 줄만 보면 같은 줄의 NPC 가 모험가보다 먼저 잡혔다)
 *  → 아래 줄 → 번호 → 대상 열쇠(같은 입력 같은 순서). */
export function orderPicks(ps: Pick[]): Pick[] {
  return [...ps].sort((a, b) => (a.group - b.group)
    || (a.group === GROUP.monster ? Number(!!a.dead) - Number(!!b.dead) : 0)
    || (b.depth - a.depth) || (b.y - a.y) || (a.n - b.n)
    || (targetId(a.target) < targetId(b.target) ? -1 : targetId(a.target) > targetId(b.target) ? 1 : 0));
}

/* ───────────── 창 내용 ───────────── */

export interface Fact { k: string; v: string }
export interface RecLine { key: string; of: 'one' | 'kind'; label: string; name?: string; text: string; turn: number; past: boolean; history: string[] }
/** old = 기록 기능이 없던 판 · self = 보는 사람 자신 · none = 기록 없음('모름') · list = 기록 줄들. */
export interface RecView { state: 'old' | 'self' | 'none' | 'list'; lines: RecLine[] }
export interface CompareRow { char: Char; name: string; job: string; call: string; rec: RecView; me: boolean }
export interface WinModel {
  id: string; present: boolean;
  call: string;                                 // 시점 사람이 부르는 이름(비교 모드·시점 없음이면 관전자 이름)
  real: string;                                 // 관전자 이름(실명)
  sub: string;                                  // 무엇인지 한 마디('몬스터 m3')
  facts: Fact[];
  mine: RecView | null;                         // 시점 보기의 기록 칸(비교 모드면 null)
  rows: CompareRow[] | null;                    // 비교 모드 — 파티 순서 전원
}

const MOB_STATE: Record<string, string> = { SLEEPING: '잠듦', HUNTING: '쫓는 중', FLEEING: '도망', WANDERING: '배회' };
const FEAT_KIND: Record<string, string> = {
  treasure: '보물', chest: '상자', fountain: '샘', potion: '물약', boon: '축복의 물약', weapon: '무기', armor: '갑옷',
  grave: '묘', npc: '마을 사람', building: '건물', exit: '계단',
};

/** 관전자 이름. */
export function realName(ix: LoreIndex, tg: Target, f: Frame): string {
  switch (tg.t) {
    case 'bot': return ix.run.names[tg.char] || tg.char;
    case 'mob': return f.monsters.find(m => m.id === tg.id)?.kind ?? '몬스터';
    case 'feat': return featAt(ix, f, tg.id)?.name ?? '물건';
    case 'trap': return f.traps[tg.idx]?.name ?? '함정';
    case 'exit': return exitName(f);
    case 'door': return '문';
    case 'zone': return zoneWord(tg.id);
    case 'region': return tg.name;
  }
}
function exitName(f: Frame): string {
  return f.features.find(x => x.type === 'exit')?.name ?? (f.level.gate ? '워프게이트' : '계단');
}
function zoneWord(id: string): string { return (id[0] === 'c' ? '통로 ' : '방 ') + id; }

/** 보는 사람이 부르는 이름(엔진과 같은 규칙). */
export function callName(ix: LoreIndex, viewer: Char | null, tg: Target, f: Frame, i: number): string {
  switch (tg.t) {
    case 'bot': return callBot(ix, viewer, tg.char, i);
    case 'mob': { const m = f.monsters.find(x => x.id === tg.id); return m ? monsterName(ix, viewer, m.kind, i) : '몬스터'; }
    case 'feat': { const ft = featAt(ix, f, tg.id); return ft ? featName(ix, viewer, ft, i) : '물건'; }
    default: return realName(ix, tg, f);
  }
}

function subOf(ix: LoreIndex, tg: Target, f: Frame): string {
  switch (tg.t) {
    case 'bot': return '모험가';
    case 'mob': return '몬스터 m' + tg.id;
    case 'feat': { const ft = featAt(ix, f, tg.id); return `${FEAT_KIND[ft?.type ?? ''] ?? ft?.type ?? '물건'} f${tg.id}`; }
    case 'trap': return '함정 t' + tg.idx;
    case 'exit': return f.level.gate ? '워프게이트' : '계단';
    case 'door': return '문 ' + tg.id;
    case 'zone': return '장소';
    case 'region': return '마을 구역';
  }
}

/** 물건 설명 — 그 이름의 정의, 없으면 그 type 의 정의가 하나뿐일 때 그것(entities.item_def 와 같은 고르기). */
export function itemInfo(run: Run, type: string, name: string): { desc?: string; rule?: string } | null {
  const info = run.meta?.item_info;
  if (!info) return null;
  const hit = info[type + ':' + name];
  if (hit) return hit;
  const same = Object.keys(info).filter(k => k.startsWith(type + ':'));
  return same.length === 1 ? info[same[0]] : null;
}

/** 겉모습 한 줄 — run_meta.party[].looks(그림) + 틱의 무기·갑옷 이름(sheetkit.looks_line 과 같은 ' · '). */
export function looksLine(p: PartyMember | undefined, b: Bot | undefined): string {
  return [p?.looks, b?.weapon?.name, b?.armor?.name].filter(s => !!s).join(' · ');
}

function factsOf(ix: LoreIndex, tg: Target, f: Frame): Fact[] {
  const run = ix.run;
  switch (tg.t) {
    case 'bot': {
      const b = f.bots.find(x => x.char === tg.char), p = run.party.find(x => x.char === tg.char);
      if (!b) return [];
      const out: Fact[] = [{ k: '직업', v: [run.jobs[tg.char] || b.job, b.sex || p?.sex].filter(Boolean).join(' · ') }];
      const lk = looksLine(p, b);
      if (lk) out.push({ k: '겉모습', v: lk });
      const st = !b.alive ? ' · 쓰러짐' : b.won ? ' · 이 층을 떠났다' : '';
      out.push({ k: 'HP', v: `${Math.max(0, b.hp)}/${b.maxhp}${st}${b.status?.length ? ' · ' + b.status.join(' · ') : ''}` });
      out.push({ k: '차림', v: `무기 ${b.weapon?.name ?? '맨손'} · 방어구 ${b.armor?.name ?? '맨몸'}` });
      return out;
    }
    case 'mob': {
      const m: Monster | undefined = f.monsters.find(x => x.id === tg.id);
      if (!m) return [];
      return [{ k: '종', v: m.kind + (m.boss ? ' · 보스' : '') },
              { k: 'HP', v: `${Math.max(0, m.hp)}/${m.maxhp}` },
              { k: '상태', v: !m.alive ? '시체' : (MOB_STATE[m.state] ?? m.state) + (m.desperate ? ' · 필사' : '') }];
    }
    case 'feat': {
      const ft = featAt(ix, f, tg.id);
      if (!ft) return [];
      const out: Fact[] = [{ k: '종류', v: FEAT_KIND[ft.type] ?? ft.type }];
      const it = itemInfo(run, ft.type, ft.name);
      if (it?.desc) out.push({ k: '설명', v: it.desc });
      if (it?.rule) out.push({ k: '다루는 법', v: it.rule });
      if (ft.type === 'grave' && ft.of) out.push({ k: '누구의 묘', v: run.names[ft.of] || ft.of });
      return out;
    }
    case 'trap': {
      const tr: Trap | undefined = f.traps[tg.idx];
      return tr ? [{ k: '종류', v: tr.name }, { k: '상태', v: tr.sprung ? '밟혔다' : '드러나 있다' }] : [];
    }
    case 'exit': {
      const g = f.level.gate;
      if (!g) return [{ k: '종류', v: exitName(f) }];
      const boss = f.monsters.find(m => m.boss);
      return [{ k: '종류', v: '워프게이트' }, { k: '봉인', v: boss && !boss.alive ? '풀렸다' : '봉인됨' }];
    }
    case 'door': return [{ k: '종류', v: '문' }];
    case 'zone': return [{ k: '장소', v: zoneWord(tg.id) }];
    case 'region': return [{ k: '마을 구역', v: tg.name }];
  }
}

function recLine(ix: LoreIndex, c: Char, key: string, of: 'one' | 'kind', i: number, label: string): RecLine | null {
  const e = valueAt(ix, c, key, i);
  if (!e || (!e.text && !e.name)) return null;
  return { key, of, label, ...(e.name ? { name: e.name } : {}), text: e.text ?? '', turn: e.turn ?? 0, past: e.src === 'book',
           history: historyAt(ix, c, key, i) };
}

/** 그 사람(c)에게 그 대상의 기록 — 개별 → 종류. 기록이 하나도 없으면 none('모름' 한 줄). */
export function recordView(ix: LoreIndex, c: Char | null, tg: Target, f: Frame, i: number): RecView {
  if (!ix.people) return { state: 'old', lines: [] };
  if (c === null) return { state: 'none', lines: [] };
  const ks = keysFor(ix, c, tg, f, i);
  if (ks.self) return { state: 'self', lines: [] };
  const lines: RecLine[] = [];
  const short = targetId(tg).replace(/^(zone|region):/, '');
  if (ks.one) { const l = recLine(ix, c, ks.one, 'one', i, isPersonKey(ks.one) ? '' : short); if (l) lines.push(l); }
  if (ks.kind) { const l = recLine(ix, c, ks.kind, 'kind', i, '종류: ' + ks.kind.slice(ks.kind.indexOf(':') + 1)); if (l) lines.push(l); }
  return { state: lines.length ? 'list' : 'none', lines };
}

/** 창 하나의 내용. viewer = 시점 사람(초점), compare = [모두 비교] 모드. */
export function windowModel(ix: LoreIndex, tg: Target, f: Frame, i: number, viewer: Char | null, compare: boolean): WinModel {
  const real = realName(ix, tg, f);
  const cmp = compare || viewer === null;
  return {
    id: targetId(tg), present: present(f, tg),
    call: cmp ? real : callName(ix, viewer, tg, f, i), real,
    sub: subOf(ix, tg, f), facts: factsOf(ix, tg, f),
    mine: cmp ? null : recordView(ix, viewer, tg, f, i),
    rows: cmp ? ix.run.party.map(p => ({
      char: p.char, name: ix.run.names[p.char] || p.char, job: ix.run.jobs[p.char] || '', me: p.char === viewer,
      call: callName(ix, p.char, tg, f, i), rec: recordView(ix, p.char, tg, f, i),
    })) : null,
  };
}

/* ───────────── '기록' 탭 — 한 사람의 모든 기록 ───────────── */

export interface LedgerRow { group: string; key: string; title: string; name?: string; text: string; turn: number; past: boolean; elsewhere: boolean }
const GROUPS: [string, (k: string) => boolean][] = [
  ['사람', k => isPersonKey(k)],
  ['장소', k => k.startsWith('place:') || k.startsWith('zone:')],
  ['의뢰', k => k.startsWith('quest:')],
  ['종류', k => k.startsWith('kind:') || k.startsWith('monster:') || k.startsWith('trap:') || k.startsWith('feature:')],
  ['장비', k => k.startsWith('gear:')],
  ['층의 것', k => k.startsWith('obj:')],
];

/** 프레임 i 까지 접은 그 사람의 장부를 무리별로(무리 순서 → 최근에 쓴 것 먼저 → 열쇠). scope = 지금 화면의 층 일련(다른 층의 층 기록에 표시). */
export function ledgerRows(ix: LoreIndex, c: Char, i: number, scope?: number): LedgerRow[] {
  const run = ix.run;
  const rows: LedgerRow[] = [];
  for (const [k, e] of Object.entries(ledgerAt(ix, c, i))) {
    const g = GROUPS.find(([, f]) => f(k))?.[0] ?? '그 밖';
    const tail = k.slice(k.indexOf(':') + 1);
    const title = /^b\d+$/.test(k) ? (run.names[k.slice(1)] || k)
      : k.startsWith('npc:') ? tail
      : k.startsWith('obj:') ? `${e.label ?? tail.slice(tail.indexOf(':') + 1)} (${tail.slice(tail.indexOf(':') + 1)})`
      : (e.label ?? tail);
    const sc = k.startsWith('obj:') ? Number(tail.slice(0, tail.indexOf(':'))) : NaN;
    rows.push({ group: g, key: k, title, ...(e.name ? { name: e.name } : {}), text: e.text ?? '', turn: e.turn ?? 0,
                past: e.src === 'book', elsewhere: !Number.isNaN(sc) && scope !== undefined && sc !== scope });
  }
  const gi = (g: string) => { const n = GROUPS.findIndex(([x]) => x === g); return n < 0 ? GROUPS.length : n; };
  return rows.sort((a, b) => (gi(a.group) - gi(b.group)) || (b.turn - a.turn) || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
}
