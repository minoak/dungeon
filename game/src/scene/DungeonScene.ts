// 무대 — 타일맵·피처·함정·몹 + SD 캐릭터, 초점 캐릭터를 부드럽게 따라가는 카메라, 틱 사이 이동 트윈·걷기 애니.
// 정보 등급: 스트림은 관전자 진실이지만 화면은 캐릭터 편에 선다(계획 §3) — 숨은 함정·매복 몹은 드러나기 전엔
// 안 그리고, 몹·피처는 초점 캐릭터의 시야 안이거나(피처는) 본 적 있는 자리만. 마을은 전부. 초점이 없으면 전부(관전자).
// Phase B 카드가 쓰는 공개 API: feetOf/headOf/project/actorOf/turnToward/tileFrame/seenSet/visibleSet/DEPTH/TILE.
import Phaser from 'phaser';
import type { App } from '../app';
import type { Bot, Char, Dir, Frame, LevelState, Monster } from '../stream/types';
import type { FrameChange } from '../play/Playback';
import { TILE, tileIndex, type Tileset, type TilesCfg } from '../assets/tiles';
import { FOOT_Y, frameIndex, portraitCanvas, queueSdSheets, registerAnims, resolveMember, sheetKey,
         walkAnimKey, type SdAtlas } from '../assets/sd';
import { cellKey } from '../world/Sight';

/** 그리기 순서. stand 는 y(타일)마다 +0.01 — 아래 줄이 위에 그려진다. fog(60)는 B4, label 은 이름표. */
export const DEPTH = { ground: 0, footprint: 5, feature: 10, trap: 12, corpse: 15, focusRing: 19, stand: 20,
                       fx: 50, fog: 60, label: 70 } as const;
export const ZOOMS = [1, 1.5, 2] as const;

export interface Actor {
  char: Char;
  sprite: Phaser.GameObjects.Sprite;
  label: Phaser.GameObjects.Text;
  key: string;                                   // 텍스처 키(프리셋|헤어)
  dir: Dir;
  cell: [number, number];                        // 현재 프레임의 칸
  alive: boolean; won: boolean;
}

export interface SceneData { app: App; atlas: SdAtlas; tiles: TilesCfg }

export class DungeonScene extends Phaser.Scene {
  app!: App;
  atlas!: SdAtlas;
  ts!: Tileset;
  cols = 12;                                     // Kenney 시트 열 수(텍스처 폭/타일)
  map: Phaser.Tilemaps.Tilemap | null = null;
  ground: Phaser.Tilemaps.TilemapLayer | null = null;
  readonly actors = new Map<Char, Actor>();
  private mobs = new Map<number, Phaser.GameObjects.Sprite>();
  private feats = new Map<string, Phaser.GameObjects.Sprite>();
  private traps = new Map<string, Phaser.GameObjects.Sprite>();
  private levelObjs: Phaser.GameObjects.GameObject[] = [];   // 문·출구 표식 등 층 고정물
  private footprints!: Phaser.GameObjects.Graphics;
  private ring!: Phaser.GameObjects.Graphics;
  frame: Frame | null = null;
  levelIdx = -1;
  private visitedDrawn = 0;
  zoom: number = 1.5;
  followChar: Char | null = null;
  private seenCache: { levelIdx: number; char: Char; count: number; set: Set<string> } | null = null;

  constructor() { super('dungeon'); }

  init(d: SceneData): void {
    this.app = d.app; this.atlas = d.atlas;
    this.ts = d.tiles.tilesets[d.tiles.default];
  }

  preload(): void {
    this.load.spritesheet('tiny', '/viewer/' + this.ts.sheet, { frameWidth: this.ts.tile, frameHeight: this.ts.tile });
    queueSdSheets(this.load, this.atlas);
  }

  create(): void {
    const src = this.textures.get('tiny').getSourceImage() as HTMLImageElement;
    this.cols = Math.max(1, Math.floor(src.width / this.ts.tile));
    registerAnims(this.anims, this.atlas);
    this.footprints = this.add.graphics().setDepth(DEPTH.footprint);
    this.ring = this.add.graphics().setDepth(DEPTH.focusRing);
    const cam = this.cameras.main;
    cam.setBackgroundColor('#0a0b0e');
    cam.setRoundPixels(true);
    this.setZoom(this.pickZoom());
    this.scale.on('resize', (gs: Phaser.Structs.Size) => { cam.setSize(gs.width, gs.height); });
    this.app.playback.on('frame', ch => this.applyFrame(ch));
    this.app.focus.on('change', ({ char }) => this.follow(char, true));
    this.app.bus.emit('scene', this);
    const cur = this.app.playback.cur;
    if (cur) this.applyFrame({ prev: null, cur, idx: this.app.playback.idx, mode: 'seek' });
  }

  /* ───────────── 공개 API(Phase B 카드용) ───────────── */

  /** 칸 → 월드 px(발 위치: 칸 중앙, 바닥에서 4px 위). */
  worldOf(x: number, y: number): { x: number; y: number } { return { x: (x + 0.5) * TILE, y: (y + 1) * TILE - 4 }; }
  /** 칸 중앙(타일 오브젝트용). */
  centerOf(x: number, y: number): { x: number; y: number } { return { x: (x + 0.5) * TILE, y: (y + 0.5) * TILE }; }
  actorOf(char: Char): Actor | undefined { return this.actors.get(char); }
  /** 캐릭터의 발(월드 px) — 트윈 중이면 지금 스프라이트 자리. */
  feetOf(char: Char): { x: number; y: number } | null {
    const a = this.actors.get(char);
    return a ? { x: a.sprite.x, y: a.sprite.y } : null;
  }
  /** 캐릭터 머리 위(월드 px) — 말풍선 앵커. */
  headOf(char: Char): { x: number; y: number } | null {
    const a = this.actors.get(char);
    return a ? { x: a.sprite.x, y: a.sprite.y - FOOT_Y + 6 } : null;
  }
  /** 월드 px → #stage 안 화면 px(DOM 오버레이용). */
  project(wx: number, wy: number): { x: number; y: number } {
    const cam = this.cameras.main;
    return { x: (wx - cam.worldView.x) * cam.zoom, y: (wy - cam.worldView.y) * cam.zoom };
  }
  /** Kenney 타일 프레임 번호('item:potion' 'feat:chest' 'mob:고블린' …). */
  tileFrame(key: string): number { return tileIndex(this.ts, this.cols, key); }
  /** 현재 프레임에서 그 캐릭터가 보는 칸(마을=전부). 초점이 없으면 null(=전부). */
  visibleSet(char: Char | null): Set<string> | null {
    if (!char || !this.frame) return null;
    return this.frame.vis[char] ?? new Set();
  }
  /** 현재 프레임까지 그 캐릭터가 이 층에서 본 적 있는 칸(누적, 캐시). */
  seenSet(char: Char | null): Set<string> | null {
    const f = this.frame;
    if (!char || !f || !this.app.run) return null;
    const ls = this.app.run.levels[f.levelIdx];
    const list = ls.seenList[char] || [];
    const count = f.seen[char] ?? 0;
    const c = this.seenCache;
    if (c && c.levelIdx === f.levelIdx && c.char === char && c.count <= count) {
      for (let i = c.count; i < count; i++) c.set.add(cellKey(list[i][0], list[i][1]));
      c.count = count;
      return c.set;
    }
    const set = new Set<string>();
    for (let i = 0; i < count; i++) set.add(cellKey(list[i][0], list[i][1]));
    this.seenCache = { levelIdx: f.levelIdx, char, count, set };
    return set;
  }
  /** 몸 돌리기(B2): char 가 other 쪽을 본다(정지 프레임). 다음 걸음이 방향을 다시 정한다. */
  turnToward(char: Char, other: Char): void {
    const a = this.actors.get(char), b = this.actors.get(other);
    if (!a || !b || !a.alive) return;
    const dx = b.sprite.x - a.sprite.x, dy = b.sprite.y - a.sprite.y;
    if (!dx && !dy) return;
    const dir: Dir = Math.abs(dx) >= Math.abs(dy) ? (dx < 0 ? 'left' : 'right') : (dy < 0 ? 'back' : 'front');
    this.setDir(a, dir);
  }
  setDir(a: Actor, dir: Dir): void {
    a.dir = dir;
    if (!a.sprite.anims.isPlaying) a.sprite.setFrame(frameIndex(this.atlas, dir, -1));
  }
  /** 칩 초상(정면 정지 프레임 크롭). */
  portrait(char: Char, size = 56): HTMLCanvasElement | null {
    const run = this.app.run;
    const m = run?.party.find(p => p.char === char);
    const key = sheetKey(resolveMember(m, run?.jobs[char], this.atlas));
    return portraitCanvas(this.textures, this.atlas, key, size);
  }
  setZoom(z: number): void {
    this.zoom = z;
    this.cameras.main.setZoom(z);
  }
  pickZoom(): number { return this.scale.width >= 1100 ? 1.5 : 1; }

  /* ───────────── 층 ───────────── */

  private buildLevel(ls: LevelState): void {
    const L = ls.line, ts = this.ts;
    for (const o of this.levelObjs) o.destroy();
    this.levelObjs = [];
    for (const s of this.mobs.values()) s.destroy();
    this.mobs.clear();
    for (const s of this.feats.values()) s.destroy();
    this.feats.clear();
    for (const s of this.traps.values()) s.destroy();
    this.traps.clear();
    this.ground?.destroy(); this.map?.destroy();
    this.footprints.clear(); this.visitedDrawn = 0;
    this.seenCache = null;

    const floorI = this.tileFrame('floor'), wallI = this.tileFrame('wall');
    const isOpen = (x: number, y: number) => y >= 0 && y < L.h && x >= 0 && x < L.w && (L.grid[y][x] === '.' || L.grid[y][x] === '+');
    const data: number[][] = [];
    for (let y = 0; y < L.h; y++) {
      const row: number[] = [];
      for (let x = 0; x < L.w; x++) {
        const ch = L.grid[y][x];
        if (ch === '.' || ch === '+') { row.push(floorI); continue; }
        let edge = false;                        // 바닥에 접한 벽만 벽돌 — 나머지는 어둠(암반)
        for (let dy = -1; dy <= 1 && !edge; dy++) for (let dx = -1; dx <= 1 && !edge; dx++) if (isOpen(x + dx, y + dy)) edge = true;
        row.push(edge ? wallI : -1);
      }
      data.push(row);
    }
    this.map = this.make.tilemap({ data, tileWidth: ts.tile, tileHeight: ts.tile });
    const tileset = this.map.addTilesetImage('tiny', 'tiny', ts.tile, ts.tile, 0, 0);
    this.ground = this.map.createLayer(0, tileset!, 0, 0)!.setScale(TILE / ts.tile).setDepth(DEPTH.ground);

    // 문 타일 · 출구
    const doorI = this.tileFrame('door');
    for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) if (L.grid[y][x] === '+') {
      const c = this.centerOf(x, y);
      this.levelObjs.push(this.add.sprite(c.x, c.y, 'tiny', doorI).setScale(TILE / ts.tile).setDepth(DEPTH.feature));
    }
    const [ex, ey] = L.exit;
    const ec = this.centerOf(ex, ey);
    this.levelObjs.push(this.add.sprite(ec.x, ec.y, 'tiny', this.tileFrame('exit')).setScale(TILE / ts.tile).setDepth(DEPTH.feature));
    this.levelObjs.push(this.add.text(ec.x, ec.y, '>', { fontFamily: 'Consolas, monospace', fontSize: '26px', color: '#e8c268',
      stroke: '#000', strokeThickness: 4 }).setOrigin(0.5).setDepth(DEPTH.feature + 1).setResolution(2));

    const m = TILE * 2;
    this.cameras.main.setBounds(-m, -m, L.w * TILE + 2 * m, L.h * TILE + 2 * m);
  }

  /* ───────────── 프레임 ───────────── */

  applyFrame({ prev, cur, mode }: FrameChange): void {
    const run = this.app.run;
    if (!run) return;
    const ls = run.levels[cur.levelIdx];
    const newLevel = cur.levelIdx !== this.levelIdx;
    if (newLevel) { this.buildLevel(ls); this.levelIdx = cur.levelIdx; }
    const snap = mode === 'seek' || newLevel || !prev;
    this.frame = cur;
    const focus = this.app.focus.char;
    const town = ls.town;
    const vis = town ? null : this.visibleSet(focus);
    const seen = town ? null : this.seenSet(focus);
    const canSee = (x: number, y: number) => !vis || vis.has(cellKey(x, y));
    const known = (x: number, y: number) => !seen || canSee(x, y) || seen.has(cellKey(x, y));

    this.drawFootprints(ls, cur.visited);

    // 봇
    const present = new Set<Char>();
    for (const b of cur.bots) {
      present.add(b.char);
      this.updateActor(this.ensureActor(b), b, cur, snap);
    }
    for (const [c, a] of this.actors) if (!present.has(c)) { a.sprite.setVisible(false); a.label.setVisible(false); }

    // 몹 — 산 것은 시야 안·정체 드러난 것만, 시체는 아는 자리만
    const seenMobs = new Set<number>();
    for (const mob of cur.monsters) {
      const show = mob.alive ? (!mob.concealed && canSee(mob.x, mob.y)) : known(mob.x, mob.y);
      if (!show) continue;
      seenMobs.add(mob.id);
      this.updateMob(mob, prev, snap);
    }
    for (const [id, s] of this.mobs) if (!seenMobs.has(id)) { s.destroy(); this.mobs.delete(id); }

    // 피처(출구는 층 고정물) — 시야 안이거나 본 적 있는 자리, concealed 는 숨김
    const seenFeats = new Set<string>();
    for (const ft of cur.features) {
      if (ft.type === 'exit' || ft.concealed) continue;
      if (!known(ft.x, ft.y)) continue;
      const k = ft.type + '#' + ft.id;
      seenFeats.add(k);
      let s = this.feats.get(k);
      const c = this.centerOf(ft.x, ft.y);
      if (!s) {
        s = this.add.sprite(c.x, c.y, 'tiny', this.tileFrame('feat:' + ft.type)).setScale(TILE / this.ts.tile).setDepth(DEPTH.feature);
        this.feats.set(k, s);
      } else s.setPosition(c.x, c.y);
      s.setAlpha(canSee(ft.x, ft.y) ? 1 : 0.7);
    }
    for (const [k, s] of this.feats) if (!seenFeats.has(k)) { s.destroy(); this.feats.delete(k); }

    // 함정 — 드러난 것만(hidden 은 안 그린다), sprung 은 어둡게
    const seenTraps = new Set<string>();
    for (const tr of cur.traps) {
      if (tr.hidden || !known(tr.x, tr.y)) continue;
      const k = tr.x + ',' + tr.y;
      seenTraps.add(k);
      let s = this.traps.get(k);
      if (!s) {
        const c = this.centerOf(tr.x, tr.y);
        s = this.add.sprite(c.x, c.y, 'tiny', this.tileFrame('trap:' + tr.kind)).setScale(TILE / this.ts.tile).setDepth(DEPTH.trap);
        this.traps.set(k, s);
      }
      s.setAlpha(tr.sprung ? 0.55 : 0.95);
    }
    for (const [k, s] of this.traps) if (!seenTraps.has(k)) { s.destroy(); this.traps.delete(k); }

    // 카메라 — 시킹·새 층은 즉시 맞춘다(따라가기 lerp 가 지도를 가로지르지 않게)
    if (this.followChar && (snap || newLevel)) {
      const a = this.actors.get(this.followChar);
      if (a && !this.cameras.main.panEffect.isRunning) this.cameras.main.centerOn(a.sprite.x, a.sprite.y - TILE);
    }
    if (!this.followChar && focus) this.follow(focus, false);
  }

  private drawFootprints(ls: LevelState, count: number): void {
    if (count < this.visitedDrawn) { this.footprints.clear(); this.visitedDrawn = 0; }
    if (count === this.visitedDrawn) return;
    this.footprints.fillStyle(0xe8c268, 0.10);
    for (let i = this.visitedDrawn; i < count; i++) {
      const [x, y] = ls.visitedList[i];
      this.footprints.fillRect(x * TILE, y * TILE, TILE, TILE);
    }
    this.visitedDrawn = count;
  }

  private ensureActor(b: Bot): Actor {
    let a = this.actors.get(b.char);
    if (a) return a;
    const run = this.app.run!;
    const member = run.party.find(p => p.char === b.char);
    const key = sheetKey(resolveMember(member, b.job || run.jobs[b.char], this.atlas));
    const w = this.worldOf(b.x, b.y);
    const sprite = this.add.sprite(w.x, w.y, key, frameIndex(this.atlas, 'front', -1))
      .setOrigin(0.5, FOOT_Y / this.atlas.cell).setDepth(DEPTH.stand + b.y * 0.01);
    const label = this.add.text(w.x, w.y - FOOT_Y, run.names[b.char] || b.char, {
      fontFamily: '"Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif', fontSize: '12px',
      color: run.colors[b.char] || '#fff', stroke: '#000', strokeThickness: 3,
    }).setOrigin(0.5, 1).setDepth(DEPTH.label).setResolution(2);
    a = { char: b.char, sprite, label, key, dir: 'front', cell: [b.x, b.y], alive: true, won: false };
    this.actors.set(b.char, a);
    return a;
  }

  private updateActor(a: Actor, b: Bot, cur: Frame, snap: boolean): void {
    const s = a.sprite;
    const target = this.worldOf(b.x, b.y);
    a.cell = [b.x, b.y]; a.alive = b.alive; a.won = b.won;
    s.setDepth(DEPTH.stand + b.y * 0.01);
    if (!b.alive) {                              // 쓰러진 자리에 눕는다(카메라는 여기로 올 수 있다 — 묘 자리)
      this.tweens.killTweensOf(s);
      s.anims.stop();
      s.setPosition(target.x, target.y).setFrame(frameIndex(this.atlas, 'front', -1)).setAngle(90).setAlpha(0.6).setVisible(true);
      a.label.setVisible(true).setAlpha(0.6);
      return;
    }
    s.setAngle(0).setAlpha(1);
    a.label.setAlpha(1);
    if (b.won) {                                 // 먼저 내려갔다 — 이 층에 없다
      this.tweens.killTweensOf(s);
      s.anims.stop();
      s.setPosition(target.x, target.y).setVisible(false);
      a.label.setVisible(false);
      return;
    }
    s.setVisible(true); a.label.setVisible(true);
    const dir = cur.facing[b.char] || a.dir;
    a.dir = dir;
    const moved = !!cur.moved[b.char];
    if (!snap && moved) {
      this.tweens.killTweensOf(s);
      const ak = walkAnimKey(a.key, dir);
      if (!s.anims.isPlaying || s.anims.currentAnim?.key !== ak) s.play(ak);
      const dur = Math.min(320, this.app.playback.tickMs * 0.8);
      this.tweens.add({ targets: s, x: target.x, y: target.y, duration: dur, ease: 'Linear',
        // 트윈이 끝났는데 아직 같은 프레임이면(다음 걸음이 안 왔으면) 정지 프레임으로. 이어 걸으면 다음 프레임이 애니를 잇는다.
        onComplete: () => { if (this.frame === cur) { s.anims.stop(); s.setFrame(frameIndex(this.atlas, dir, -1)); } } });
    } else {
      this.tweens.killTweensOf(s);
      s.anims.stop();
      s.setPosition(target.x, target.y).setFrame(frameIndex(this.atlas, dir, -1));
    }
  }

  private updateMob(mob: Monster, prev: Frame | null, snap: boolean): void {
    const c = this.centerOf(mob.x, mob.y);
    let s = this.mobs.get(mob.id);
    if (!s) {
      s = this.add.sprite(c.x, c.y, 'tiny', this.tileFrame('mob:' + mob.kind)).setScale(TILE / this.ts.tile);
      this.mobs.set(mob.id, s);
      snap = true;
    }
    if (!mob.alive) {
      this.tweens.killTweensOf(s);
      s.setPosition(c.x, c.y).setAngle(90).setAlpha(0.4).setDepth(DEPTH.corpse);
      return;
    }
    s.setAngle(0).setAlpha(1).setDepth(DEPTH.stand + mob.y * 0.01 - 0.005);
    const pm = prev?.monsters.find(m => m.id === mob.id);
    const moved = !!pm && (pm.x !== mob.x || pm.y !== mob.y);
    if (!snap && moved) {
      this.tweens.killTweensOf(s);
      this.tweens.add({ targets: s, x: c.x, y: c.y, duration: Math.min(320, this.app.playback.tickMs * 0.8), ease: 'Linear' });
    } else { this.tweens.killTweensOf(s); s.setPosition(c.x, c.y); }
  }

  /* ───────────── 카메라 ───────────── */

  /** 초점 캐릭터를 따라간다. animate = 300ms 팬 뒤 부드러운 추적(lerp 0.1). */
  follow(char: Char, animate: boolean): void {
    this.followChar = char;
    const a = this.actors.get(char);
    if (!a) return;
    const cam = this.cameras.main;
    cam.stopFollow();
    if (animate) {
      cam.pan(a.sprite.x, a.sprite.y - TILE, 300, 'Sine.easeInOut', true, (_c, progress) => {
        if (progress >= 1 && this.followChar === char) cam.startFollow(a.sprite, true, 0.1, 0.1, 0, TILE);
      });
    } else {
      cam.startFollow(a.sprite, true, 0.1, 0.1, 0, TILE);
      cam.centerOn(a.sprite.x, a.sprite.y - TILE);
    }
  }

  update(): void {
    for (const a of this.actors.values()) {
      if (!a.label.visible) continue;
      a.label.setPosition(a.sprite.x, a.sprite.y - (a.alive ? FOOT_Y : 30) - 2);
    }
    this.ring.clear();
    const fc = this.app.focus.char;
    const a = fc ? this.actors.get(fc) : undefined;
    if (a && a.sprite.visible && a.alive) {
      const col = Phaser.Display.Color.HexStringToColor(this.app.run?.colors[a.char] || '#ffd166').color;
      this.ring.lineStyle(2, col, 0.9);
      this.ring.strokeEllipse(a.sprite.x, a.sprite.y - 2, TILE * 0.8, TILE * 0.36);
    }
  }
}
