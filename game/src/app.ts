// 앱 컨텍스트 — 판(Run)·재생 클록(Playback)·초점(Focus)·씬(DungeonScene)·DOM 자리를 한 객체로 묶는다.
// Phase B 카드는 install(app) 한 함수로 붙는다: app.playback.on('frame') / app.focus.on('change') / app.bus.on('run').
// window.__wl = app (스모크·디버그 훅).
import type Phaser from 'phaser';
import { Emitter } from './util/Emitter';
import { Playback } from './play/Playback';
import { Focus } from './play/Focus';
import { StreamParser } from './stream/parse';
import { RunSource } from './stream/live';
import type { Char, Run } from './stream/types';
import type { DungeonScene } from './scene/DungeonScene';
import { $ } from './ui/dom';

export interface AppEvents extends Record<string, unknown> {
  run: Run;                                      // 새 판이 열림(프레임 교체) — UI 는 다시 만든다
  grow: { added: number };                       // 라이브: 프레임이 붙음
  live: boolean;                                 // 라이브 판 여부
  scene: DungeonScene;                           // 씬 준비됨(create 끝)
  error: string;                                 // 로드 실패 등
}

export interface LoadOpts { focus?: string | null; turn?: number | null }

export class App {
  readonly bus = new Emitter<AppEvents>();
  readonly playback = new Playback();
  readonly focus = new Focus();
  run: Run | null = null;
  scene!: DungeonScene;
  game!: Phaser.Game;
  path = '';
  live = false;
  private parser = new StreamParser();
  private source: RunSource | null = null;
  readonly dom = {
    stage: $('stage'), overlay: $('overlay'), hud: $('hud'), side: $('side'), chips: $('chips'),
    focusCard: $('focusCard'), bottom: $('bottom'), controls: $('controls'), log: $('log'),
  };

  name(c: Char): string { return this.run?.names[c] || c; }
  color(c: Char): string { return this.run?.colors[c] || '#fff'; }
  job(c: Char): string { return this.run?.jobs[c] || '?'; }

  /** turn 의 tick 프레임 번호(없으면 가장 가까운 앞 프레임). */
  frameOfTurn(turn: number): number {
    const fr = this.run?.frames || [];
    let best = 0;
    for (let i = 0; i < fr.length; i++) { if (fr[i].kind === 'tick' && fr[i].turn === turn) return i; if (fr[i].turn <= turn) best = i; }
    return best;
  }

  async loadRun(path: string, opts: LoadOpts = {}): Promise<void> {
    this.source?.stop();
    this.playback.pause();
    this.path = path;
    this.run = null;
    this.parser = new StreamParser();
    const src = new RunSource(path, text => this.onText(text));
    this.source = src;
    try { await src.load(); }
    catch (e) { this.bus.emit('error', '로드 실패: ' + (e instanceof Error ? e.message : String(e))); return; }
    const run = this.run as Run | null;
    if (!run || !run.frames.length) { this.bus.emit('error', '틱이 아직 없다 (빈 판)'); return; }
    // 초점 기본값 = 파티 1번(계획 §8 제안) · URL ?focus= 로 지정 · 새 판은 같은 번호여도 다시 붙인다
    const want = opts.focus && run.party.some(p => p.char === opts.focus) ? opts.focus : (run.party[0]?.char ?? null);
    this.live = RunSource.isLivePath(path) && !run.end;
    this.playback.live = this.live;
    this.bus.emit('live', this.live);
    const idx = opts.turn != null && !Number.isNaN(opts.turn) ? this.frameOfTurn(opts.turn) : (this.live ? this.playback.last : 0);
    this.playback.setIdx(idx, 'seek');
    if (want) { this.focus.set(want, true); this.scene?.follow(want, false); }
    if (this.live) src.startPolling(1500);
  }

  private onText(text: string): void {
    const first = !this.run;
    const { added, reset } = this.parser.feed(text);
    this.run = this.parser.run;
    if (first || reset) {
      this.playback.setFrames(this.run.frames);
      this.bus.emit('run', this.run);
      if (reset && this.run.frames.length) this.playback.setIdx(this.live ? this.playback.last : 0, 'seek');
    } else if (added) {
      this.playback.setFrames(this.run.frames);
      this.bus.emit('grow', { added });
      this.playback.grew(added);
    }
    if (this.live && this.run.end) {             // 판이 끝났다 — 폴링 종료
      this.live = false; this.playback.live = false; this.source?.stopPolling(); this.bus.emit('live', false);
    }
  }
}
