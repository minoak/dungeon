// 정수 픽셀 전투 연출. 틱·시킹·판 교체 시 이전 도형·피격 색·흔들림을 정리한다.
import type Phaser from 'phaser';
import type { App } from '../app';
import type { FrameChange } from '../play/Playback';
import type { Frame, StreamEvent } from '../stream/types';
import { DEPTH } from '../scene/DungeonScene';

type XY = [number, number];
type RecordValue = Record<string, unknown>;
interface Burst {
  g: Phaser.GameObjects.Graphics; popup?: Phaser.GameObjects.Graphics; age: number; life: number;
  draw: (p: number) => void; sprite?: Phaser.GameObjects.Sprite;
}
export interface CombatDebug {
  enabled: boolean; active: number; created: number; suppressed: number;
  kinds: Record<string, number>; setEnabled: (on: boolean) => void;
}
declare global { interface Window { __wlCombat?: CombatDebug } }

const TIMING = { lifeShare: 0.85, minLifeMs: 120, maxLifeMs: 700, flashMaxMs: 110,
  flashLifeDivisor: 3, projectileEnd: 0.48, projectileTravel: 0.4, projectileTail: 0.2 } as const;
const MAX_BURSTS = 64;
const SHAKE_INTENSITY = 0.0012;
const COLOR = { heal: 0x76ffab, poison: 0xbbf36b, critical: 0xffe27a, damage: 0xff7777,
  criticalFlash: 0xffe6a0, flash: 0xffffff, bleed: 0xff405c, slash: 0xd4eaff,
  trap: 0xffbd59, down: 0xc4c5dc, outline: 0x101019 } as const;
const PIXEL = { bodyLift: 22, popupLift: 25, popupRise: 22, lanes: 3, laneX: 6, laneY: 11,
  lineWidth: 2, heavyWidth: 3, normalFont: 2, criticalFont: 3, dotFont: 1,
  glyphWidth: 3, glyphHeight: 5, glyphGap: 1, glyphBorder: 1 } as const;
const SHAPE = { radius: 6, expansion: 16, crossHalf: 10, crossBarHalf: 3,
  cutFrom: [-12, 10], cutTo: [12, -12], arc: [[-12, 9], [-5, -5], [7, -12], [17, -10]],
  pushTravel: 14, pushLength: 10, trapHalf: 8, trapTip: 7,
  drop: [-3, 4, 4, 6], smallDrop: [4, 10, 3, 3], downSize: 3 } as const;

const GLYPHS: Record<string, string> = {
  '0': '111101101101111', '1': '010110010010111', '2': '111001111100111',
  '3': '111001111001111', '4': '101101111001001', '5': '111100111001111',
  '6': '111100111101111', '7': '111001010010010', '8': '111101111101111',
  '9': '111101111001111', '+': '000010111010000', '-': '000000111000000',
  '!': '010010010000010', M: '101111111101101', I: '111010010010111',
  S: '111100111001111',
};
const rec = (v: unknown): RecordValue => v && typeof v === 'object' ? v as RecordValue : {};
const xy = (v: unknown): XY | null => Array.isArray(v) && v.length === 2 && v.every(Number.isInteger) ? v as XY : null;
const positive = (v: unknown): number => typeof v === 'number' && Number.isFinite(v) ? Math.max(0, v) : 0;

// 글자도 사각 픽셀로 그린다. 벡터·글꼴 안티앨리어싱을 사용하지 않는다.
function line(g: Phaser.GameObjects.Graphics, x: number, y: number, ex: number, ey: number, size: number = PIXEL.lineWidth): void {
  const n = Math.max(1, Math.ceil(Math.max(Math.abs(ex - x), Math.abs(ey - y))));
  for (let i = 0; i <= n; i++) g.fillRect(Math.round(x + (ex - x) * i / n), Math.round(y + (ey - y) * i / n), size, size);
}
function label(g: Phaser.GameObjects.Graphics, text: string, x: number, y: number, color: number, size: number): void {
  const advance = PIXEL.glyphWidth + PIXEL.glyphGap;
  const start = Math.round(x - (text.length * advance - PIXEL.glyphGap) * size / 2);
  for (const [i, c] of [...text].entries()) {
    const bits = GLYPHS[c];
    if (!bits) continue;
    for (let k = 0; k < PIXEL.glyphWidth * PIXEL.glyphHeight; k++) if (bits[k] === '1') {
      const px = start + (i * advance + k % PIXEL.glyphWidth) * size, py = Math.round(y) + Math.floor(k / PIXEL.glyphWidth) * size;
      const border = PIXEL.glyphBorder;
      g.fillStyle(COLOR.outline).fillRect(px - border, py - border, size + border * 2, size + border * 2);
    }
    g.fillStyle(color);
    for (let k = 0; k < PIXEL.glyphWidth * PIXEL.glyphHeight; k++) if (bits[k] === '1') g.fillRect(start + (i * advance + k % PIXEL.glyphWidth) * size, Math.round(y) + Math.floor(k / PIXEL.glyphWidth) * size, size, size);
  }
}

export function installCombat(app: App): void {
  const scene = app.scene;
  const bursts: Burst[] = [];
  const flashes = new Map<Phaser.GameObjects.Sprite, { colors: number[]; fill: boolean }>();
  let last: Frame | null = null;
  const stats: CombatDebug = {
    enabled: new URLSearchParams(location.search).get('combatFx') !== '0',
    active: 0, created: 0, suppressed: 0, kinds: {},
    setEnabled(on) { stats.enabled = on; clear(); },
  };
  window.__wlCombat = stats;

  function destroy(b: Burst): void { b.g.destroy(); b.popup?.destroy(); }

  function restore(s: Phaser.GameObjects.Sprite): void {
    const old = flashes.get(s);
    if (!old) return;
    if (s.active) {
      const [tl, tr, bl, br] = old.colors;
      if (old.fill) s.setTintFill(tl, tr, bl, br); else s.setTint(tl, tr, bl, br);
    }
    flashes.delete(s);
  }
  function clear(): void {
    for (const b of bursts) destroy(b);
    bursts.length = 0;
    for (const s of flashes.keys()) restore(s);
    scene.cameras?.main?.shakeEffect.reset();
    stats.active = 0;
  }
  function cell(id: string, frame: Frame): XY | null {
    const entity = id.startsWith('m') ? frame.monsters.find(m => m.id === Number(id.slice(1)))
      : frame.bots.find(b => b.char === id.replace(/^b/, ''));
    return entity ? [entity.x, entity.y] : null;
  }
  function visible(id: string, at: XY, frame: Frame): boolean {
    const entity = id.startsWith('m') ? frame.monsters.find(m => m.id === Number(id.slice(1)))
      : frame.bots.find(b => b.char === id.replace(/^b/, ''));
    if (!entity || entity.concealed || entity.won) return false;
    const vis = app.run?.levels[frame.levelIdx].town ? null : scene.visibleSet(app.focus.char);
    // 발동 지점과 현재 대상 모두 보여야 한다. 과거에만 본 시체는 제외한다.
    return !vis || (vis.has(at.join(',')) && vis.has([entity.x, entity.y].join(',')));
  }
  function launch(e: StreamEvent, frame: Frame, ordinal: number): void {
    const skill = typeof e.skill_id === 'string' && e.skill_spent === true;
    const attack = e.type === 'monster_attack' || (e.type === 'attack' && e.result === 'attack');
    const status = e.type === 'monster_status';
    const trap = rec(e.trap), bleed = rec(e.bleed);
    const effects = Array.isArray(e.effects) ? e.effects.map(rec) : [];
    const owner = String(e.char ?? '');
    const target = e.type === 'monster_attack' ? 'b' + String(e.target ?? '')
      : e.type === 'monster_status' ? String(e.id ?? '')
      : attack ? String(e.target_id ?? '')
      : skill ? (e.target === 'self' ? 'b' + owner : String(e.target ?? ''))
      : e.result === 'healed' && /^[bm]\d+$/.test(String(e.target)) ? String(e.target) : 'b' + owner;
    const at = xy(e.target_xy) ?? cell(target, frame);
    if (!at || !visible(target, at, frame)) { stats.suppressed++; return; }
    const hit = e.hit !== false;
    const heal = positive(e.heal); // 휴식 시작·만피 휴식은 실제 회복을 뜻하지 않는다.
    const damage = positive(e.dmg);
    const crit = hit && (e.crit === true || rec(e.combat_roll).critical === true || rec(e.skill_roll).critical === true);
    const down = !!e.killed || !!e.down || !!bleed.down || !!trap.down || effects.some(r => r.killed || r.down);
    const dot = status || Object.keys(bleed).length > 0;
    const trapped = (Object.keys(trap).length > 0 && trap.safe === false) || e.result === 'chest_trap';
    const statusTag = String(e.status ?? trap.status ?? '');
    if (!attack && !skill && !heal && !damage && !dot && !trapped && !down) return;
    const kind = trapped ? 'trap' : dot ? 'status' : skill ? String(e.skill_id) : heal ? 'heal' : 'attack';
    const color = heal || e.skill_id === 'first_aid' ? COLOR.heal : dot && statusTag === '중독' ? COLOR.poison : crit ? COLOR.critical : COLOR.damage;
    const amount = heal || damage || positive(trap.dmg) || (Object.keys(bleed).length ? 1 : 0);
    const text = !hit ? 'MISS' : amount ? (heal ? '+' : '-') + Math.round(amount) + (crit ? '!' : '') : '';
    const world = scene.worldOf(...at);
    const x = Math.round(world.x), y = Math.round(world.y - PIXEL.bodyLift);
    const source = e.type === 'monster_attack' ? String(e.id ?? '') : 'b' + owner;
    const from = xy(e.source_xy) ?? cell(source, frame);
    const projectile = e.attack_mode === 'ranged' && from && visible(source, from, frame) ? scene.worldOf(...from) : null;
    const push = effects.find(r => r.type === 'push' && r.applied === true);
    const pushTo = xy(push?.to);
    const pushEnd = pushTo && visible(target, pushTo, frame) ? scene.worldOf(...pushTo) : null;
    const s = scene.combatSprite(target);
    if (!s?.active || !s.visible) { stats.suppressed++; return; }
    const g = scene.add.graphics().setDepth(DEPTH.fx + 1).setName('combat-fx');
    // 공간 도형은 안개 아래, 숫자·MISS는 이름표 위. 생성 전 대상 시야 검사는 공유한다.
    const popup = text ? scene.add.graphics().setDepth(DEPTH.label + 1).setName('combat-popup') : undefined;
    popup?.setData({ text, target, frame: frame.idx });
    g.setData({ kind, text, target, crit, projectile: !!projectile, down, frame: frame.idx, ordinal });
    if (hit && amount > 0 && !heal && s?.visible && !flashes.has(s)) {
      flashes.set(s, { colors: [s.tintTopLeft, s.tintTopRight, s.tintBottomLeft, s.tintBottomRight], fill: s.tintFill });
      s.setTintFill(crit ? COLOR.criticalFlash : COLOR.flash);
    }
    const life = Math.max(TIMING.minLifeMs, Math.min(TIMING.maxLifeMs, app.playback.paceMs * TIMING.lifeShare));
    if (crit) scene.cameras.main.shake(Math.min(TIMING.flashMaxMs, life / TIMING.flashLifeDivisor), SHAKE_INTENSITY, false);
    const draw = (p: number): void => {
      g.clear();
      popup?.clear();
      // 서서히 투명하게 만들지 않고 마지막에 지워 도트 색을 유지한다.
      g.fillStyle(color);
      const r = SHAPE.radius + Math.round(p * SHAPE.expansion);
      if (projectile && p < TIMING.projectileEnd) {
        const t = Math.min(1, p / TIMING.projectileTravel), tail = Math.max(0, t - TIMING.projectileTail);
        line(g, projectile.x + (x - projectile.x) * tail, projectile.y - PIXEL.bodyLift + (y - projectile.y + PIXEL.bodyLift) * tail,
          projectile.x + (x - projectile.x) * t, projectile.y - PIXEL.bodyLift + (y - projectile.y + PIXEL.bodyLift) * t);
      }
      if (hit && kind === 'first_aid') {
        const a = SHAPE.crossHalf, b = SHAPE.crossBarHalf;
        g.fillRect(x - b, y - a, b * 2, a * 2).fillRect(x - a, y - b, a * 2, b * 2);
      } else if (hit && kind === 'heavy_strike') {
        line(g, x, y - r, x + r, y); line(g, x + r, y, x, y + r);
        line(g, x, y + r, x - r, y); line(g, x - r, y, x, y - r);
      } else if (hit && (kind === 'push_slash' || kind === 'bleeding_cut')) {
        g.fillStyle(kind === 'bleeding_cut' ? COLOR.bleed : COLOR.slash);
        if (kind === 'bleeding_cut') line(g, x + SHAPE.cutFrom[0], y + SHAPE.cutFrom[1], x + SHAPE.cutTo[0], y + SHAPE.cutTo[1], PIXEL.heavyWidth);
        else {
          const points = SHAPE.arc;
          for (let i = 1; i < points.length; i++) line(g, x + points[i - 1][0], y + points[i - 1][1], x + points[i][0], y + points[i][1], PIXEL.heavyWidth);
          if (pushEnd) {
            const dx = Math.sign(pushEnd.x - x), dy = Math.sign(pushEnd.y - world.y), slide = Math.round(p * SHAPE.pushTravel);
            line(g, x + dx * slide, y + dy * slide, x + dx * (slide + SHAPE.pushLength), y + dy * (slide + SHAPE.pushLength), PIXEL.heavyWidth);
          }
        }
      }
      if (trapped) { g.fillStyle(COLOR.trap); line(g, x - SHAPE.trapHalf, y + SHAPE.trapHalf, x, y - SHAPE.trapTip); line(g, x, y - SHAPE.trapTip, x + SHAPE.trapHalf, y + SHAPE.trapHalf); }
      if (dot || statusTag === '중독') {
        g.fillStyle(statusTag === '중독' ? COLOR.poison : COLOR.bleed);
        for (const [dx, dy, w, h] of [SHAPE.drop, SHAPE.smallDrop]) g.fillRect(x + dx, y + dy, w, h);
      }
      if (down || bleed.down || trap.down) {
        g.fillStyle(COLOR.down);
        for (const dx of [-1, 1]) for (const dy of [-1, 1]) g.fillRect(x + dx * r, y + dy * Math.round(r / 2), SHAPE.downSize, SHAPE.downSize);
      }
      if (popup) label(popup, text, x + (ordinal % PIXEL.lanes - 1) * PIXEL.laneX,
        y - PIXEL.popupLift - Math.round(p * PIXEL.popupRise) - (ordinal % PIXEL.lanes) * PIXEL.laneY,
        color, crit ? PIXEL.criticalFont : dot ? PIXEL.dotFont : PIXEL.normalFont);
    };
    bursts.push({ g, popup, age: 0, life, draw, sprite: s });
    // 과밀하거나 잘못된 스트림에서도 생성 수를 제한한다.
    if (bursts.length > MAX_BURSTS) destroy(bursts.shift()!);
    draw(0);
    stats.active = bursts.length; stats.created++; stats.kinds[kind] = (stats.kinds[kind] ?? 0) + 1;
  }
  const onFrame = ({ cur, mode }: FrameChange): void => {
    const duplicate = cur === last;
    clear();
    const changedFloor = last !== null && cur.levelIdx !== last.levelIdx;
    last = cur;
    if (!stats.enabled || mode === 'seek' || duplicate || changedFloor || cur.kind !== 'tick' || scene.frame !== cur) return;
    cur.events.forEach((e, i) => launch(e, cur, i));
  };
  const onUpdate = (_time: number, delta: number): void => {
    for (let i = bursts.length - 1; i >= 0; i--) {
      const b = bursts[i]; b.age += delta;
      if (b.sprite && b.age > Math.min(TIMING.flashMaxMs, b.life / TIMING.flashLifeDivisor)) restore(b.sprite);
      if (b.age >= b.life) { destroy(b); bursts.splice(i, 1); } else b.draw(b.age / b.life);
    }
    // 상한 때문에 먼저 지운 도형의 피격 색도 복원한다.
    if (!bursts.length) for (const s of flashes.keys()) restore(s);
    stats.active = bursts.length;
  };
  scene.events.on('update', onUpdate);
  const off = [
    app.playback.on('frame', onFrame), app.playback.on('speed', clear),
    app.focus.on('change', clear), app.bus.on('run', () => { clear(); last = null; }),
  ];
  scene.events.once('shutdown', () => {
    clear();
    off.forEach(unsubscribe => unsubscribe());
    scene.events.off('update', onUpdate);
  });
}
