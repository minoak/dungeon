// 디버그 모드 — 관전 화면은 기본적으로 '초점 캐릭터가 보고 들은 것'만 보여 준다(세계 규칙과 같은 원칙).
// 개발 중에는 일행 전부를 봐야 한다: 이 스위치를 켜면 초점 필터가 풀린다.
//
// 켜는 법(둘 중 아무거나):
//   · 주소에 ?debug=1 을 붙인다  (?debug=0 이면 끈다)
//   · 관전 화면에서 Shift+D      (입력칸에 글자를 치는 중에는 듣지 않는다)
// 켜졌는지 보는 법: 기록 머리의 '이 사람만' 옆에 '· 디버그' 가 붙고, body[data-debug="1"] 이 선다.
// 한 번 켜면 이 브라우저에 남는다(localStorage 'wl-debug') — 끌 때까지 새 판에서도 켜져 있다.

const KEY = 'wl-debug';
const listeners: (() => void)[] = [];
let on = false;

function read(): boolean {
  try {
    const q = new URLSearchParams(location.search).get('debug');
    if (q === '1' || q === '0') { localStorage.setItem(KEY, q); return q === '1'; }
    return localStorage.getItem(KEY) === '1';
  } catch { return false; }                      // 저장이 막힌 브라우저(사생활 보호 창)에서도 화면은 뜬다
}

function paint(): void {
  on = read();
  if (typeof document !== 'undefined' && document.body) document.body.dataset.debug = on ? '1' : '0';
}

export function debugOn(): boolean { return on; }

/** 스위치가 바뀔 때 다시 그려야 하는 쪽이 등록한다(등록 즉시 한 번 부르지는 않는다 — 부르는 쪽이 이미 그린다). */
export function onDebugChange(fn: () => void): void { listeners.push(fn); }

export function installDebug(): void {
  paint();
  window.addEventListener('keydown', e => {
    if (!e.shiftKey || e.key !== 'D') return;
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    e.preventDefault();
    try { localStorage.setItem(KEY, on ? '0' : '1'); } catch { /* 저장이 막혀 있으면 이 창에서만 바뀐다 */ }
    const next = !on;
    on = next;
    if (document.body) document.body.dataset.debug = next ? '1' : '0';
    for (const fn of listeners) fn();
  });
}
