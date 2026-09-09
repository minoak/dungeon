// 건네기 트윈 — Phase B3 카드가 채운다.
// 입력: app.playback('frame') 의 cur.events 중 {type:'give', result:'given', char, to, item, what}
//       · app.scene.feetOf(char) · app.scene.tileFrame('item:'+item) · DEPTH.fx. 산출: 물건 아이콘이 둘 사이를 건너가는
//       0.4s 트윈(+ 로그는 B2 가 "수나 → 유나: 가죽 갑옷" 로). mode==='seek' 이면 트윈 없이 건너뛴다.
import type { App } from '../app';

export function installHandoff(_app: App): void {
  /* B3 */
}
