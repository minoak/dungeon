// JSONL 스트림 파서 — 뷰어(viewer/index.html parseStream)의 규칙을 그대로 잇는다:
//  · tick ↔ level 조인은 turn 이 아니라 **파일 순서**(강하 턴의 tick 은 옛 층 좌표)
//  · 마지막 라인이 개행으로 안 끝나면 미완성 — 버린다(tail 규칙). 깨진 라인은 조용히 무시.
//  · 발자국 = level.party 스폰 칸 + 이후 각 tick 의 봇 좌표 누적
//  · 방향 = 직전 프레임과의 좌표 차(안 움직이면 유지, 처음 front), 새 층은 재스폰이라 이동으로 안 센다
//  + 시야(관전 근사 LOS)·캐릭터별 본 칸 누적을 프레임에 파생한다.
// 라이브용 증분: feed(전체 텍스트)를 다시 불러도 앞부분이 그대로면 붙은 라인만 파싱한다(level 객체 안정).
import type {
  Bot, Char, DescendLine, Dir, EndLine, Feature, Frame, LevelLine, LevelState, Monster, PartyMember,
  RunMeta, Run, StreamLine, TickLine, Trap,
} from './types';
import { allCells, cellKey, lineOfSight, EMPTY_SET } from '../world/Sight';

export const BOT_COLORS = ['#ffd166', '#6fe3b0', '#c77dff', '#ef476f', '#38b6ff',
                           '#ff9f1c', '#90e0ef', '#f4a0c0', '#b5e48c'];

export function emptyRun(): Run {
  return { meta: null, end: null, party: [], frames: [], levels: [], names: {}, jobs: {}, colors: {},
           looks: {}, deathTurn: {}, sight: 6, town: false };
}

interface LevelScratch { visitedSet: Set<string>; seenSet: Record<Char, Set<string>>; townVis: Set<string> | null }

export class StreamParser {
  run: Run = emptyRun();
  private consumed = 0;
  private consumedText = '';
  private cur: LevelState | null = null;
  private scratch: LevelScratch | null = null;
  private face: Record<Char, Dir> = {};
  private prev: Record<Char, [number, number]> = {};

  reset(): void {
    this.run = emptyRun(); this.consumed = 0; this.consumedText = '';
    this.cur = null; this.scratch = null; this.face = {}; this.prev = {};
  }

  /** 전체 텍스트를 넣는다. 앞부분이 바뀌었으면(다른 판) 처음부터 다시. */
  feed(text: string): { added: number; reset: boolean } {
    let didReset = false;
    if (this.consumed && !text.startsWith(this.consumedText)) { this.reset(); didReset = true; }
    const end = text.lastIndexOf('\n') + 1;                    // 완결 라인까지만
    if (end <= this.consumed) return { added: 0, reset: didReset };
    const chunk = text.slice(this.consumed, end);
    this.consumed = end; this.consumedText = text.slice(0, end);
    const before = this.run.frames.length;
    for (const raw of chunk.split('\n')) {
      const s = raw.trim();
      if (!s) continue;
      let o: StreamLine;
      try { o = JSON.parse(s) as StreamLine; } catch { continue; }
      this.line(o);
    }
    return { added: this.run.frames.length - before, reset: didReset };
  }

  private line(o: StreamLine): void {
    switch (o.kind) {
      case 'run_meta': this.meta(o as RunMeta); break;
      case 'level': this.level(o as LevelLine); break;
      case 'tick': this.tick(o as TickLine); break;
      case 'descend': case 'ascend': {            // 전이 자체는 프레임이 아니다 — 직전 틱에 붙인다
        const last = this.run.frames[this.run.frames.length - 1];
        if (last) last.descend = o as DescendLine;
        break;
      }
      case 'end': this.run.end = o as EndLine; break;
      default: break;                            // 모르는 kind: 조용히 무시(additive)
    }
  }

  private meta(m: RunMeta): void {
    const r = this.run;
    r.meta = m; r.party = m.party || []; r.sight = typeof m.sight === 'number' ? m.sight : 6; r.town = !!m.town;
    r.party.forEach((p, i) => {
      r.names[p.char] = p.name || p.job || ('봇' + p.char);
      r.jobs[p.char] = p.job || '?';
      r.colors[p.char] = BOT_COLORS[i % BOT_COLORS.length];
      if (p.look) r.looks[p.char] = p.look;
    });
  }

  private ensureBot(b: Bot): void {              // meta 없이 온 봇(파일 머리 미도착) — 스냅샷에서 유도
    const r = this.run;
    if (!(b.char in r.names)) {
      r.names[b.char] = '봇' + b.char; r.jobs[b.char] = b.job || '?';
      r.colors[b.char] = BOT_COLORS[Object.keys(r.colors).length % BOT_COLORS.length];
      if (!r.party.some(p => p.char === b.char)) r.party.push({ char: b.char, job: b.job } as PartyMember);
    }
  }

  private level(L: LevelLine): void {
    const town = this.run.town && L.depth === 0;
    const ls: LevelState = { idx: this.run.levels.length, line: L, town, visitedList: [], seenList: {} };
    this.run.levels.push(ls);
    this.cur = ls;
    this.scratch = { visitedSet: new Set(), seenSet: {}, townVis: town ? allCells(L.w, L.h) : null };
    this.prev = {};                              // 재스폰 — 좌표 연속성 없음(방향은 유지)
    this.frame('level', L.turn, L.party, L.monsters, L.features, L.traps, { reaction_stats: L.reaction_stats });
  }

  private tick(t: TickLine): void {
    if (!this.cur) return;                       // 방어: level 없는 tick 은 못 그린다
    this.frame('tick', t.turn, t.bots, t.monsters, t.features, t.traps, t);
  }

  private frame(kind: 'level' | 'tick', turn: number, bots: Bot[], monsters: Monster[], features: Feature[],
                traps: Trap[], t: Partial<TickLine>): void {
    const ls = this.cur!, sc = this.scratch!, r = this.run, grid = ls.line.grid;
    const facing: Record<Char, Dir> = {}, moved: Record<Char, boolean> = {};
    const vis: Record<Char, Set<string>> = {}, seen: Record<Char, number> = {};
    for (const b of bots) {
      this.ensureBot(b);
      // 발자국
      const k = cellKey(b.x, b.y);
      if (!sc.visitedSet.has(k)) { sc.visitedSet.add(k); ls.visitedList.push([b.x, b.y]); }
      // 방향·이동
      const p = this.prev[b.char];
      if (p && (p[0] !== b.x || p[1] !== b.y)) {
        const dx = b.x - p[0], dy = b.y - p[1];
        this.face[b.char] = Math.abs(dx) >= Math.abs(dy) ? (dx < 0 ? 'left' : 'right') : (dy < 0 ? 'back' : 'front');
        moved[b.char] = true;
      }
      facing[b.char] = this.face[b.char] || 'front';
      this.prev[b.char] = [b.x, b.y];
      // 시야·본 곳(캐릭터별)
      let v: Set<string>;
      if (b.alive && !b.won) v = sc.townVis ?? lineOfSight(grid, b.x, b.y, r.sight);
      else v = EMPTY_SET as Set<string>;
      vis[b.char] = v;
      let ss = sc.seenSet[b.char];
      if (!ss) { ss = new Set(); sc.seenSet[b.char] = ss; ls.seenList[b.char] = []; }
      const list = ls.seenList[b.char];
      for (const c of v) if (!ss.has(c)) { ss.add(c); const [x, y] = c.split(',').map(Number); list.push([x, y]); }
      // 사망 시점
      if (!b.alive && !(b.char in r.deathTurn)) r.deathTurn[b.char] = turn;
    }
    for (const c of Object.keys(ls.seenList)) seen[c] = ls.seenList[c].length;
    const f: Frame = {
      kind, idx: r.frames.length, turn, levelIdx: ls.idx, level: ls.line,
      bots, monsters, features, traps,
      events: t.events || [], decisions: t.decisions || {}, inbox: t.inbox || {},
      hails: t.hails, answers: t.answers, replies: t.replies,
      social_events: t.social_events, reactions: t.reactions, reaction_stats: t.reaction_stats,
      facing, moved, vis, seen, visited: ls.visitedList.length,
    };
    r.frames.push(f);
  }
}

/** 한 번에 파싱(테스트·단순 소비자용). */
export function parseStream(text: string): Run {
  const p = new StreamParser();
  p.feed(text);
  return p.run;
}
