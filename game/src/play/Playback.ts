// 재생 클록 — 틱 속도(1×/4×/16×)·시킹·라이브 꽁무니 따라가기. Phaser 와 무관한 순수 TS.
// 'frame' 이벤트의 mode: 'seek' = 임의 점프(스냅으로 그려라) / 'step'·'play' = 바로 다음 프레임(트윈해도 된다).
import { Emitter } from '../util/Emitter';
import type { Frame } from '../stream/types';

export const SPEEDS = [1, 4, 16] as const;
export const BASE_MS = 700;                      // 1× 에서 틱 간격(뷰어와 같다)

export type FrameMode = 'seek' | 'step' | 'play';
export interface FrameChange { prev: Frame | null; cur: Frame; idx: number; mode: FrameMode }

export interface PlaybackEvents extends Record<string, unknown> {
  frame: FrameChange;                            // 현재 프레임이 바뀜
  play: boolean;                                 // 재생/정지
  speed: number;                                 // SPEEDS 인덱스
  frames: number;                                // 프레임 수 변화(라이브 성장·새 판)
  live: boolean;                                 // 꽁무니 따라가기 켜짐/꺼짐
}

export class Playback extends Emitter<PlaybackEvents> {
  frames: Frame[] = [];
  idx = -1;
  playing = false;
  speedIdx = 0;
  /** 라이브 판에서 꽁무니를 따라간다(새 틱이 붙으면 전진). 사용자가 뒤로 스크럽하면 꺼진다. */
  live = false;
  private timer: number | null = null;

  get cur(): Frame | null { return this.frames[this.idx] ?? null; }
  get last(): number { return this.frames.length - 1; }
  get atEnd(): boolean { return this.idx >= this.last; }
  get tickMs(): number { return BASE_MS / SPEEDS[this.speedIdx]; }
  get speed(): number { return SPEEDS[this.speedIdx]; }

  setFrames(frames: Frame[]): void {
    this.frames = frames;
    if (this.idx > this.last) this.idx = this.last;
    this.emit('frames', frames.length);
  }

  /** 프레임 이동. intent 가 step/play 라도 연속(+1)이 아니면 seek 로 강등된다. */
  setIdx(i: number, intent: FrameMode = 'seek'): void {
    if (!this.frames.length) return;
    const n = Math.max(0, Math.min(this.last, Math.floor(i)));
    const prevIdx = this.idx;
    this.idx = n;
    const mode: FrameMode = intent !== 'seek' && n === prevIdx + 1 ? intent : 'seek';
    if (this.live && n < this.last && intent === 'seek') this.setLive(false);   // 뒤로 스크럽 = 따라가기 해제
    this.emit('frame', { prev: mode === 'seek' ? null : this.frames[prevIdx], cur: this.frames[n], idx: n, mode });
  }

  step(d: number): void { this.setIdx(this.idx + d, d === 1 ? 'step' : 'seek'); }

  play(): void {
    if (this.playing) return;
    if (this.atEnd && !this.live) this.setIdx(0, 'seek');
    this.playing = true; this.emit('play', true); this.schedule();
  }

  pause(): void {
    if (!this.playing) return;
    this.playing = false; this.clear(); this.emit('play', false);
  }

  toggle(): void { this.playing ? this.pause() : this.play(); }

  setSpeed(i: number): void {
    this.speedIdx = Math.max(0, Math.min(SPEEDS.length - 1, i));
    this.emit('speed', this.speedIdx);
    if (this.playing) this.schedule();
  }

  setLive(on: boolean): void {
    if (this.live === on) return;
    this.live = on; this.emit('live', on);
    if (on && !this.playing) this.setIdx(this.last, 'seek');
  }

  /** 라이브: 새 프레임이 붙었다 — 따라가는 중이고 정지 상태면 붙은 만큼 전진(재생 중이면 클록이 알아서). */
  grew(added: number): void {
    if (!this.live || this.playing || added <= 0) return;
    const wasTail = this.idx === this.last - added;
    if (wasTail && added === 1) this.setIdx(this.last, 'step'); else this.setIdx(this.last, 'seek');
  }

  private clear(): void { if (this.timer !== null) { clearTimeout(this.timer); this.timer = null; } }

  private schedule(): void {
    this.clear();
    if (!this.playing) return;
    this.timer = window.setTimeout(() => {
      if (this.idx < this.last) { this.setIdx(this.idx + 1, 'play'); this.schedule(); }
      else if (this.live) { this.schedule(); }   // 꽁무니에서 새 틱 대기
      else { this.pause(); }
    }, this.tickMs);
  }
}
