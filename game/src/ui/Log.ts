// 하단 로그 — Phase B2 카드가 채운다(Bubbles 와 한 카드).
// 입력: app.playback('frame') · frame.decisions(say/to/say_kind/form/reason) · frame.events(evLine 사전 이식 — viewer/index.html)
//       · frame.descend · run.end. 산출: app.dom.log 안 DOM(시간순, 초점 관련 줄 강조 .focus).
import type { App } from '../app';

export function installLog(app: App): void {
  app.dom.log.innerHTML = '<div class="dim">로그 — 준비 중(B2)</div>';
}
