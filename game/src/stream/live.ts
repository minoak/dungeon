// 판 파일 읽기 + 라이브 폴링(1.5초 재요청, 전체 텍스트 → 파서가 증분 처리). Phase A 최소판 — B5 가 완성한다
// (론처 /api/status 연동·백오프·판 목록 갱신 등).
export async function fetchText(url: string): Promise<string> {
  const r = await fetch(url + (url.includes('?') ? '&' : '?') + '_=' + Date.now(), { cache: 'no-store' });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.text();
}

export interface LauncherStatus {
  running: boolean; pid?: number | null; started?: string | null; seed?: number | null;
  party?: { char: string; name: string; job: string }[]; turn?: number | null; outcome?: string | null; viewer?: string;
  dev?: boolean;
}

export async function fetchStatus(): Promise<LauncherStatus | null> {
  try {
    const r = await fetch('/api/status', { cache: 'no-store' });
    if (!r.ok) return null;
    return (await r.json()) as LauncherStatus;
  } catch { return null; }
}

export class RunSource {
  private timer: number | null = null;
  private busy = false;
  stopped = false;

  constructor(public readonly path: string, private readonly onText: (text: string) => void) {}

  static isLivePath(path: string): boolean { return path.startsWith('state/'); }

  async load(): Promise<void> {
    const t = await fetchText('/' + this.path);
    if (!this.stopped) this.onText(t);
  }

  startPolling(ms = 1500): void {
    this.stopPolling();
    this.timer = window.setInterval(() => { void this.poll(); }, ms);
  }

  private async poll(): Promise<void> {
    if (this.busy || this.stopped) return;
    this.busy = true;
    try { const t = await fetchText('/' + this.path); if (!this.stopped) this.onText(t); }
    catch { /* 다음 폴링에서 다시 */ }
    finally { this.busy = false; }
  }

  stopPolling(): void { if (this.timer !== null) { clearInterval(this.timer); this.timer = null; } }
  stop(): void { this.stopped = true; this.stopPolling(); }
}
