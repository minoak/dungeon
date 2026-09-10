export interface BrainPauseStatus {
  id: string; turn: number; retrying: boolean;
  errors: { char: string; name: string; input_error: string; reason: string }[];
}
export function createBrainPause(): {
  update(status: { running: boolean; brain_pause?: BrainPauseStatus | null } | null): void;
};
