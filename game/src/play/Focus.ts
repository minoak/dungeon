// 초점 캐릭터 스토어 — 카메라·칩 강조·초점 카드·말풍선 강조가 모두 이것을 본다.
import { Emitter } from '../util/Emitter';
import type { Char } from '../stream/types';

export interface FocusEvents extends Record<string, unknown> {
  change: { char: Char; prev: Char | null };
}

export class Focus extends Emitter<FocusEvents> {
  char: Char | null = null;

  /** force = 같은 캐릭터여도 이벤트를 낸다(새 판을 열 때 카메라를 다시 붙이기 위해). */
  set(char: Char, force = false): void {
    if (!force && char === this.char) return;
    const prev = this.char;
    this.char = char;
    this.emit('change', { char, prev });
  }
}
