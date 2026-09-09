// 판 파일 읽기 + 라이브 폴링 + 론처 상태 배지 (B5 라이브·배포, 2026-09-09).
// - fetchText   : 캐시 우회 GET(전체 텍스트 → 파서가 증분 처리)
// - RunSource   : 판 파일 폴링. 실패하면 지수 백오프(1.5→3→6s 상한), 성공하면 기본 간격으로 복귀
// - fetchStatus : 론처 /api/status (vite 개발·프리뷰 서버는 더미 {dev:true} — 론처 없음)
// - installLive : 라이브 판일 때 #hud 에 "LIVE · t{turn}" 배지. 러너가 죽었는데 end 가 없으면 "중단됨",
//                 dev 더미면 "론처 없음 — 라이브 아님". 라이브가 아니면 숨김. 새 판(파일이 줄어 파서 reset → bus 'run')이면
//                 배지도 초기화. 덤: state/ 경로를 보는 중에 판이 끝났거나 아직 없을 때 론처에서 새 판이 돌면 자동으로 다시 붙는다.
import type { App } from '../app';
import { el } from '../ui/dom';

export const POLL_MS = 1500;                     // 판 파일·상태 폴링 기본 간격
export const BACKOFF_MAX_MS = 6000;              // 실패 백오프 상한(1.5→3→6)
export const WATCH_MS = 3000;                    // 라이브가 아닐 때 새 판을 살피는 간격(state/ 경로만)

export async function fetchText(url: string): Promise<string> {
  const r = await fetch(url + (url.includes('?') ? '&' : '?') + '_=' + Date.now(), { cache: 'no-store' });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.text();
}

export interface LauncherStatus {
  running: boolean; pid?: number | null; started?: string | null; seed?: number | null;
  party?: { char: string; name: string; job: string }[]; turn?: number | null; outcome?: string | null;
  viewer?: string; game?: string;                // 론처가 주는 관전 주소(뷰어 / 게임 클라이언트)
  dev?: boolean;                                 // vite 서버의 더미 응답 — 론처가 없다
}

export async function fetchStatus(): Promise<LauncherStatus | null> {
  try {
    const r = await fetch('/api/status', { cache: 'no-store' });
    if (!r.ok) return null;
    return (await r.json()) as LauncherStatus;
  } catch { return null; }
}

/** 백오프 간격: 연속 실패 n 회 → base·2ⁿ, 상한 BACKOFF_MAX_MS(단, base 가 더 크면 base). */
export function backoffMs(base: number, failures: number): number {
  return failures <= 0 ? base : Math.min(base * 2 ** failures, Math.max(BACKOFF_MAX_MS, base));
}

export class RunSource {
  private timer: number | null = null;
  private busy = false;
  private polling = false;
  private base = POLL_MS;
  /** 현재 폴링 간격(백오프 반영) — 디버그용. */
  delay = POLL_MS;
  /** 연속 실패 수(성공하면 0). */
  failures = 0;
  stopped = false;

  constructor(public readonly path: string, private readonly onText: (text: string) => void) {}

  static isLivePath(path: string): boolean { return path.startsWith('state/'); }

  async load(): Promise<void> {
    const t = await fetchText('/' + this.path);
    if (!this.stopped) this.onText(t);
  }

  /** 폴링 시작(setTimeout 사슬 — 한 요청이 끝난 뒤에 다음을 잰다. 실패하면 간격이 늘고 성공하면 돌아온다). */
  startPolling(ms = POLL_MS): void {
    this.stopPolling();
    this.base = this.delay = ms; this.failures = 0; this.polling = true;
    this.schedule();
  }

  private schedule(): void {
    if (!this.polling || this.stopped || this.timer !== null) return;
    this.timer = window.setTimeout(() => { this.timer = null; void this.poll(); }, this.delay);
  }

  private async poll(): Promise<void> {
    if (this.busy || this.stopped) return;
    this.busy = true;
    try {
      const t = await fetchText('/' + this.path);
      if (!this.stopped) this.onText(t);
      this.failures = 0; this.delay = this.base;
    } catch (e) {
      this.failures++;
      this.delay = backoffMs(this.base, this.failures);
      if (this.failures === 1) console.warn('[live] 판 파일 폴링 실패 — 백오프', this.path, e);
    } finally {
      this.busy = false;
      this.schedule();                           // stopPolling 이 불렸으면 schedule 이 무시한다
    }
  }

  stopPolling(): void {
    this.polling = false;
    if (this.timer !== null) { clearTimeout(this.timer); this.timer = null; }
  }

  stop(): void { this.stopped = true; this.stopPolling(); }
}

// ───────────────────────── 라이브 배지(#hud .live-hud) ─────────────────────────

function injectStyle(): void {
  if (document.getElementById('style-live')) return;
  const s = document.createElement('style');
  s.id = 'style-live';
  s.textContent = `
#hud .live-hud { display: none; background: #3a1d22; color: #ef476f; border: 1px solid #ef476f; white-space: nowrap; }
#hud .live-hud.on { display: inline-flex; align-items: center; gap: 5px; }
#hud .live-hud[hidden] { display: none; }
#hud .live-hud.on::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: currentColor;
  animation: wl-live-blink 1.2s ease-in-out infinite; }
#hud .live-hud.stalled, #hud .live-hud.warn { color: #ffb347; border-color: #ffb347; background: #3a2a12; }
#hud .live-hud.dev { color: #9aa3b2; border-color: #4a5160; background: #1c2028; }
#hud .live-hud.stalled::before, #hud .live-hud.dev::before { animation: none; }
@keyframes wl-live-blink { 50% { opacity: .2; } }
`;
  document.head.appendChild(s);
}

/**
 * 라이브 배지 설치. 라이브 판(app.live)일 때 /api/status 를 POLL_MS 마다 읽어 #hud 의 배지를 갱신한다.
 *   LIVE · t{turn}                — 러너가 돌고 있다(turn = 론처가 읽은 틱과 붙은 프레임 중 큰 것)
 *   LIVE · t{turn} · 론처 응답 없음 — /api/status 가 안 읽힌다(백오프 중)
 *   중단됨 · t{turn}              — 러너는 죽었는데 end 라인이 없다
 *   론처 없음 — 라이브 아님        — vite 더미 상태(dev). 더는 묻지 않는다
 * 라이브가 아니면 숨긴다. 새 판(bus 'run')이면 지난 상태를 버리고 다시 그린다.
 * 덤: state/ 경로를 보고 있는데 라이브가 아니면(끝났거나 아직 판이 없음) WATCH_MS 마다 상태를 살펴, 론처에서 새 판이
 * 돌기 시작했으면(running · 틱 있음 · end 없음) 같은 경로를 다시 연다(loadRun) — 론처에서 시작 → 이 창이 알아서 붙는다.
 */
export function installLive(app: App): void {
  injectStyle();
  const hud = app.dom.hud;
  const badge = el('span', 'badge live-hud');
  badge.hidden = true;
  hud.appendChild(badge);

  let timer: number | null = null;
  let failures = 0;                              // 상태 폴링 연속 실패
  let last: LauncherStatus | null = null;        // 마지막으로 읽은 론처 상태(새 판이면 버린다)
  let lastReattach = 0;
  let reattaching = false;                       // 내가 loadRun 을 불렀다 — 성공(bus 'run')하면 지난 오류 문구를 걷어낸다
  let text = '';                                 // 마지막 렌더 문자열 — 변할 때만 DOM 을 만진다
  let cls = '';

  const lastTurn = (): number => { const f = app.playback.frames; return f.length ? f[f.length - 1].turn : -1; };
  const turnStr = (): string => { const t = Math.max(last?.turn ?? -1, lastTurn()); return t >= 0 ? 't' + t : 't?'; };

  function render(): void {
    if (badge.parentElement !== hud) hud.appendChild(badge);   // main.ts 의 오류 표시(hud.textContent=…)가 지웠으면 다시 붙인다
    let c = 'badge live-hud', t = '';
    if (app.live) {
      if (last?.dev) { t = '론처 없음 — 라이브 아님'; c += ' on dev'; }
      else if (last && !last.running && last.outcome == null && !app.run?.end) { t = `중단됨 · ${turnStr()}`; c += ' on stalled'; }
      else { t = `LIVE · ${turnStr()}` + (failures ? ' · 론처 응답 없음' : ''); c += ' on' + (failures ? ' warn' : ''); }
    }
    if (t !== text) { badge.textContent = t; text = t; }
    if (c !== cls) { badge.className = c; cls = c; }
    badge.hidden = !t;
  }

  const watching = (): boolean => RunSource.isLivePath(app.path) && !last?.dev;

  function schedule(): void {
    if (timer !== null || last?.dev) return;     // dev 더미는 바뀌지 않는다 — 폴링 종료
    const ms = app.live ? backoffMs(POLL_MS, failures) : (watching() ? Math.max(WATCH_MS, backoffMs(POLL_MS, failures)) : 0);
    if (!ms) return;
    timer = window.setTimeout(() => { timer = null; void tick(); }, ms);
  }

  async function tick(): Promise<void> {
    const st = await fetchStatus();
    if (st) { last = st; failures = 0; } else { failures++; }
    render();
    // 새 판 자동 재접속: 라이브가 아닌데(끝남·빈 판·404) 론처는 새 판을 돌리고 있고 파일에 틱이 있으며 end 가 없다
    if (st && !st.dev && st.running && !app.live && RunSource.isLivePath(app.path)
        && st.outcome == null && st.turn != null && Date.now() - lastReattach > WATCH_MS) {
      lastReattach = Date.now(); reattaching = true;
      void app.loadRun(app.path, { focus: app.focus.char });
    }
    schedule();
  }

  /** 재접속이 성공했다 — main.ts 가 #hud 에 남긴 "로드 실패 …" 텍스트 노드만 걷어낸다(요소는 안 건드린다). */
  function clearStaleError(): void {
    if (!reattaching) return;
    reattaching = false;
    for (const n of [...hud.childNodes]) if (n.nodeType === Node.TEXT_NODE) hud.removeChild(n);
  }

  function kick(): void {
    if (timer !== null) { clearTimeout(timer); timer = null; }
    render();
    schedule();
  }

  app.bus.on('live', kick);
  app.bus.on('run', () => { last = null; clearStaleError(); kick(); });   // 새 판 — 지난 판의 틱 수를 물려주지 않는다
  app.bus.on('error', kick);                                  // 빈 판·404 로 끝난 로드도 살피기 시작(새 판 대기)
  app.playback.on('frames', render);                          // 프레임이 붙으면 틱 수만 갱신(문자열이 같으면 무접촉)
  kick();                                                     // loadRun 뒤에 설치돼도(이벤트를 놓쳤어도) 지금 상태로 시작
}
