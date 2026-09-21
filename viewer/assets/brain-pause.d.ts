export interface BrainPauseStatus {
  id: string; turn: number; retrying: boolean;
  errors: { char: string; name: string; input_error: string; reason: string }[];
}
/** D96(09-20) 멈춘 판의 요약(/api/status.resume) — 호출 한도로 멈춘 판을 화면이 알아보는 데 쓴다. */
export interface BrainPauseResume { stopped?: string | null; turn_last?: number | null; }
export function createBrainPause(options?: { budgetNotice?: boolean }): {
  update(status: { running: boolean; brain_pause?: BrainPauseStatus | null;
                   resume?: BrainPauseResume | null;
                   /** D98(09-21) 운영자 키 판이 멈춘 자리(/api/status.house_end) — 이어갈 수 없는 판의 '여기서 끝났다' 안내 */
                   house_end?: BrainPauseResume | null } | null): void;
};
