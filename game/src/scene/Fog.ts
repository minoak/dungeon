// 밝기(fog) 레이어 — Phase B4 카드가 채운다.
// 입력: app.playback('frame') · app.focus('change') · app.scene.visibleSet(char)/seenSet(char) · frame.level.grid
//       · run.levels[i].town · TILE · DEPTH.fog(60). 산출: 씬 안 오버레이(가 본 곳=보통·지금 시야=밝게·미지=어둡게,
//       마을 전체 밝음). 수용: 16× 재생에 프레임 드롭 없음(칸 단위 그래픽 갱신은 변한 칸만).
import type { App } from '../app';

export function installFog(_app: App): void {
  /* B4 */
}
