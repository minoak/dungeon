// 초점 카드 — Phase B1 카드가 채운다(GAME_CLIENT_PLAN §3·§6).
// 입력: app.focus('change') · app.playback('frame') · frame.bots[].{hp,maxhp,status,potions,weapon,armor,relations}
//       · frame.decisions[char].{reason,say,relation} · 관계 뼈 라벨 사전(BONES — dungeon_gm.py 복사).
// 산출: app.dom.focusCard 안 DOM. 수용: 초점 전환 시 HP·상태·소지·속내·관계 뼈·관계 한 줄이 그 캐릭터로 바뀐다.
import type { App } from '../app';

export function installFocusCard(app: App): void {
  app.dom.focusCard.innerHTML = '<div class="dim">초점 카드 — 준비 중(B1)</div>';
}
