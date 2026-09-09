// 말풍선·지문·몸 돌리기 — 화자 머리 위 DOM 오버레이(app.dom.overlay), 카메라·트윈을 따라 매 rAF 재배치.
// 입력: app.playback('frame') · frame.decisions[char].{say,to,say_kind} · frame.events(bond done 의 form)
//       · app.scene.headOf/project/actorOf/turnToward · app.focus.
// 산출: #overlay .bubble[data-char](제안 .proposal + 꼬리표, 지목 "→ 이름", 초점 화자 .focus)
//       · #overlay .stage-dir[data-char]("*form*" — 테두리 없는 이탤릭, 말풍선 위).
// 규율: 화자당 말풍선 1개(새 말이 오면 교체). 수명 = max(tickMs×1.2, 900ms) — 재생 중일 때. 정지 상태(step/seek)에서
//       만든 것은 다음 프레임 변경까지 남긴다(스크럽하며 읽는 용도). seek 는 전부 걷어내고 현재 프레임의 말을 즉시 표시.
//       화자 스프라이트가 안 보이면(먼저 내려감) 표시하지 않는다. 텍스트는 전부 esc().
import type { App } from '../app';
import type { Char, Decision } from '../stream/types';
import type { FrameChange } from '../play/Playback';
import { esc } from '../ui/dom';
import { nameOf } from '../text/evline';

interface Rect { left: number; right: number; top: number; bottom: number }
interface Float { el: HTMLElement; expires: number; out: boolean; w: number; h: number; rect: Rect | null }

const FADE_MS = 160;                             // 사라질 때 투명해지는 시간(CSS transition 과 같다)
const LIFT = 24;                                 // 머리 위 이름표를 비켜 올리는 월드 px(줌 배율 적용)
const TAIL = 8;                                  // 말풍선 꼬리 높이(화면 px)
const GAP = 6;                                   // 겹친 말풍선을 위로 쌓을 때 사이 간격(화면 px)
const EDGE = 4;                                  // 무대 가장자리 여백(화면 px) — 넘치면 안으로 당긴다
const HUD_CLEARANCE = 84;                        // 무대 상단의 층·시점 표시 아래에 대사를 배치한다

const STYLE = `
#overlay .bubble, #overlay .stage-dir { position: absolute; left: 0; top: 0; max-width: 260px; box-sizing: border-box;
  will-change: transform; transition: opacity ${FADE_MS}ms; white-space: pre-wrap; word-break: keep-all; overflow-wrap: anywhere; }
#overlay .bubble { background: #fff; color: #111; border-radius: 9px; padding: 6px 10px; font-size: 13px; line-height: 1.35;
  box-shadow: 0 2px 6px rgba(0, 0, 0, .45); border: 1px solid #d8d8d8; }
#overlay .bubble::after { content: ''; position: absolute; left: 50%; bottom: -${TAIL}px; margin-left: -${TAIL}px;
  border: ${TAIL}px solid transparent; border-top-color: #fff; border-bottom: 0; }
#overlay .bubble.focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent), 0 2px 6px rgba(0, 0, 0, .45); }
#overlay .bubble.proposal { border-color: #d99a00; background: #fff8e6; }
#overlay .bubble.proposal::after { border-top-color: #fff8e6; }
#overlay .bubble .meta { display: flex; gap: 6px; align-items: center; margin-top: 3px; font-size: 11px; color: #666; }
#overlay .bubble .who { color: #444; font-weight: bold; display: inline-flex; align-items: center; gap: 4px; }
#overlay .bubble .who .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; border: 1px solid rgba(0, 0, 0, .35); }
#overlay .bubble .kind { color: #8a5d00; font-weight: bold; border: 1px solid #d99a00; border-radius: 3px; padding: 0 4px; background: #fff; }
#overlay .stage-dir { color: #f1e9ff; font-style: italic; font-size: 12.5px; line-height: 1.3; text-align: center; padding: 2px 6px;
  text-shadow: 0 1px 2px #000, 0 0 5px #000, 0 0 2px #000; }
#overlay .bubble.out, #overlay .stage-dir.out { opacity: 0; }
`;

export function installBubbles(app: App): void {
  if (!document.getElementById('style-bubbles')) {
    const st = document.createElement('style');
    st.id = 'style-bubbles'; st.textContent = STYLE;
    document.head.appendChild(st);
  }
  const overlay = app.dom.overlay;
  const bubbles = new Map<Char, Float>();
  const dirs = new Map<Char, Float>();
  let raf = 0;

  const life = (): number => Math.max(app.playback.tickMs * 1.2, 900);
  const speakerVisible = (c: Char): boolean => { const a = app.scene?.actorOf(c); return !!a && a.sprite.visible; };

  function clearAll(): void {
    for (const b of bubbles.values()) b.el.remove();
    for (const d of dirs.values()) d.el.remove();
    bubbles.clear(); dirs.clear();
  }

  /** 기존 것의 남은 수명을 life 로 조인다(정지 상태에서 무한이던 것도 다음 프레임부터는 흐른다). */
  function ageAll(now: number): void {
    const until = now + life();
    for (const b of bubbles.values()) b.expires = Math.min(b.expires, until);
    for (const d of dirs.values()) d.expires = Math.min(d.expires, until);
  }

  function upsert(map: Map<Char, Float>, c: Char, cls: string, html: string, expires: number): Float {
    let f = map.get(c);
    if (!f) {
      const el = document.createElement('div');
      el.dataset.char = c;
      overlay.appendChild(el);
      f = { el, expires, out: false, w: 0, h: 0, rect: null };
      map.set(c, f);
    }
    f.el.className = cls;
    f.el.innerHTML = html;
    f.el.style.visibility = 'hidden';            // 첫 배치 전 깜빡임 방지 — settle() 이 켠다
    f.expires = expires; f.out = false; f.rect = null;
    f.w = f.el.offsetWidth; f.h = f.el.offsetHeight;   // 내용이 바뀔 때만 잰다(매 rAF 레이아웃 읽기 금지)
    return f;
  }

  function showBubble(c: Char, d: Decision, expires: number): void {
    const run = app.run!;
    const proposal = d.say_kind === '제안';
    // 아래 줄 = 화자(색 점+이름 — 겹침을 피해 옆으로 비켜선 말풍선도 누구 말인지 보이게) · 제안 꼬리표 · 지목
    const bits: string[] = [`<span class="who"><i class="dot" style="background:${esc(run.colors[c] || '#fff')}"></i>${esc(nameOf(run, c))}</span>`];
    if (proposal) bits.push('<span class="kind">제안</span>');
    if (d.to) bits.push(`<span class="to">→ ${d.to === 'all' ? '모두' : esc(nameOf(run, d.to))}</span>`);
    const html = `<div class="bt">${esc(d.say)}</div><div class="meta">${bits.join('')}</div>`;
    const cls = 'bubble' + (proposal ? ' proposal' : '') + (app.focus.char === c ? ' focus' : '');
    upsert(bubbles, c, cls, html, expires);
  }

  function showDir(c: Char, form: string, expires: number): void {
    upsert(dirs, c, 'stage-dir', `*${esc(form)}*`, expires);
  }

  /** 프레임 반영 — 말(decisions.say)·지문(bond done)·몸 돌리기(to). */
  function onFrame({ cur, mode }: FrameChange): void {
    const run = app.run;
    if (!run || !app.scene) return;
    const now = performance.now();
    if (mode === 'seek') clearAll(); else ageAll(now);
    const persist = mode === 'seek' || !app.playback.playing;   // 정지 상태 = 다음 프레임까지 남긴다
    const expires = persist ? Infinity : now + life();
    for (const c of Object.keys(cur.decisions)) {
      const d = cur.decisions[c];
      if (!d.say || d.skipped || d.src === 'fallback') continue;
      if (!speakerVisible(c)) continue;          // 먼저 내려간 화자 — 무대에 없다
      showBubble(c, d, expires);
      if (d.to && d.to !== 'all' && d.to in run.names) app.scene.turnToward(c, d.to);
    }
    for (const e of cur.events) {
      if (e.type !== 'bond' || e.result !== 'done' || !e.char || !e.form) continue;
      if (!speakerVisible(e.char)) continue;
      showDir(e.char, String(e.form), expires);
      if (typeof e.to === 'string' && e.to in run.names) app.scene.turnToward(e.char, e.to);   // 몸짓도 상대를 향한다
    }
    ensureLoop();
  }

  /** 화자 머리 위 앵커(화면 px, 이름표 위) — 스프라이트가 없거나 안 보이면 null. */
  function anchor(c: Char, zoom: number): { x: number; y: number } | null {
    const scene = app.scene;
    const head = scene.headOf(c);
    if (!head || !speakerVisible(c)) return null;
    const p = scene.project(head.x, head.y);
    return { x: p.x, y: p.y - LIFT * zoom - TAIL };
  }

  const overlaps = (l: number, t: number, w: number, h: number, r: Rect): boolean =>
    l < r.right && l + w > r.left && t < r.bottom && t + h > r.top;
  const fits = (l: number, t: number, w: number, h: number, placed: Rect[]): boolean => !placed.some(r => overlaps(l, t, w, h, r));

  /** 앵커 위에 놓되, 먼저 놓인 것과 겹치면 그 위로 쌓고(가까이 선 화자들), 위가 모자라면 옆으로, 그래도 안 되면 위에 붙여 겹친다. */
  function settle(f: Float, a: { x: number; y: number }, placed: Rect[], W: number, H: number): void {
    const w = f.w, h = f.h;
    const topEdge = Math.min(HUD_CLEARANCE, Math.max(EDGE, H - h - EDGE));
    const clampX = (l: number): number => (W > w + EDGE * 2 ? Math.max(EDGE, Math.min(W - w - EDGE, l)) : l);
    let left = clampX(a.x - w / 2);
    let bottom = a.y;
    if (H > 0 && bottom > H - EDGE) bottom = H - EDGE;
    let top = bottom - h;
    if (top < topEdge) { top = topEdge; bottom = top + h; }   // 상단 표식 뒤에 대사가 가려지지 않도록 내린다
    if (!fits(left, top, w, h, placed)) {
      // ① 위로 쌓기
      let b2 = bottom;
      for (let guard = 0; guard < 16; guard++) {
        let bumped = false;
        for (const r of placed) if (overlaps(left, b2 - h, w, h, r)) { b2 = r.top - GAP; bumped = true; }
        if (!bumped) break;
      }
      if (b2 - h >= topEdge) { bottom = b2; top = b2 - h; }
      else {
        // ② 위가 모자라다 — 앵커 높이에서 옆(오른쪽 → 왼쪽)으로 비켜 선다
        const band = placed.filter(r => overlaps(left, top, w, h, r));
        const maxR = Math.max(...band.map(r => r.right)), minL = Math.min(...band.map(r => r.left));
        const rightL = maxR + GAP, leftL = minL - w - GAP;
        if (rightL + w <= W - EDGE && fits(rightL, top, w, h, placed)) left = rightL;
        else if (leftL >= EDGE && fits(leftL, top, w, h, placed)) left = leftL;
        else { top = Math.max(topEdge, b2 - h); bottom = top + h; }   // ③ 자리가 모자라도 상단 표식은 피한다
      }
    }
    f.rect = { left, right: left + w, top, bottom };
    placed.push(f.rect);
    f.el.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
    f.el.style.visibility = '';
  }

  function hide(f: Float): void { f.rect = null; f.el.style.visibility = 'hidden'; }

  function expire(map: Map<Char, Float>, now: number): void {
    for (const [c, f] of map) {
      if (now < f.expires) continue;
      if (!f.out) { f.out = true; f.el.classList.add('out'); f.expires = now + FADE_MS; }
      else { f.el.remove(); map.delete(c); }
    }
  }

  function loop(now: number): void {
    raf = 0;
    expire(bubbles, now); expire(dirs, now);
    if (!app.scene) { ensureLoop(); return; }
    const zoom = app.scene.zoom ?? 1;
    const W = overlay.clientWidth, H = overlay.clientHeight;
    const placed: Rect[] = [];
    // 말풍선 — 화면 아래쪽(앞에 선 화자)부터 제자리에, 뒤의 것은 겹치면 위로
    const order: { f: Float; a: { x: number; y: number } }[] = [];
    for (const [c, f] of bubbles) { const a = anchor(c, zoom); if (a) order.push({ f, a }); else hide(f); }
    order.sort((p, q) => q.a.y - p.a.y);
    for (const o of order) settle(o.f, o.a, placed, W, H);
    // 지문 — 제 말풍선 위(없으면 머리 위), 그 뒤 겹침 해소
    for (const [c, f] of dirs) {
      const a = anchor(c, zoom);
      if (!a) { hide(f); continue; }
      const b = bubbles.get(c);
      settle(f, b && !b.out && b.rect ? { x: a.x, y: b.rect.top - GAP } : a, placed, W, H);
    }
    if (bubbles.size || dirs.size) raf = requestAnimationFrame(loop);
  }
  function ensureLoop(): void { if (!raf && (bubbles.size || dirs.size)) raf = requestAnimationFrame(loop); }

  app.playback.on('frame', onFrame);
  app.bus.on('run', clearAll);
  app.focus.on('change', ({ char, prev }) => {
    bubbles.get(char)?.el.classList.add('focus');
    if (prev) bubbles.get(prev)?.el.classList.remove('focus');
  });
}
