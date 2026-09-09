// 말풍선·지문·몸 돌리기 — Phase B2 카드가 채운다.
// 입력: app.playback('frame') · frame.decisions[char].{say,to,say_kind,form} · app.scene.headOf(char)/project()
//       · app.scene.turnToward(char, other). 산출: app.dom.overlay 안 DOM(카메라를 따라 매 프레임 재배치 — Phaser 씬의
//       update 대신 requestAnimationFrame 을 써도 된다). 초점 캐릭터 말풍선 강조, 제안(say_kind='제안') 표식.
import type { App } from '../app';

export function installBubbles(_app: App): void {
  /* B2 */
}
