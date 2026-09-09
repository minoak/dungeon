// 건네기 트윈(B3) — give 틱에 물건 아이콘이 준 쪽에서 받는 쪽으로 0.4s 건너간다.
// 입력: app.playback('frame') 의 cur.events 중 {type:'give', result:'given', char, to, item, what}
//       · app.scene.feetOf(char) · app.scene.tileFrame('item:'+item) · DEPTH.fx.
// 규칙: mode==='seek' 면 아무것도 안 만든다(스냅). 씬이 없거나 좌표가 null 이면 조용히 건너뛴다.
//       받는 쪽이 이 틱에 걷는 중이면(스프라이트 트윈) 도착점은 매 프레임 feetOf 로 다시 읽어 따라간다.
//       placed(상대 슬롯이 차서 발밑에 놓임)여도 바닥 피처는 씬이 features 로 그리니 여기선 아이콘만 없앤다.
//       동시에 나는 아이콘 상한 8 — 넘치면 오래된 것부터 destroy. 층이 바뀌거나 새 판이 열리면 전부 정리.
// 훅: 아이콘 게임오브젝트 name='handoff'(라벨은 'handoff-label') — 스모크가 app.scene.children.getByName('handoff') 로 본다.
import type Phaser from 'phaser';
import type { App } from '../app';
import type { FrameChange } from '../play/Playback';
import type { Char, StreamEvent } from '../stream/types';
import { DEPTH } from '../scene/DungeonScene';
import { TILE } from '../assets/tiles';

const FLY_MS = 400;                              // 건너가는 시간(계획 §3 "0.4s")
const POP_MS = 120;                              // 도착 팝(커졌다 작아진다)
const LIFT = 40;                                 // 발치에서 띄우는 높이(px) — 가슴께
const ARC = TILE * 0.5;                          // 포물선 꼭대기 여유(px)
const MAX_FLYING = 8;
const FONT = '"Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif';

interface Flight {
  icon: Phaser.GameObjects.Image;
  label: Phaser.GameObjects.Text | null;
  tween: Phaser.Tweens.Tween | null;
  done: boolean;
}

/** give 이벤트의 받는 봇 번호 — to(봇 번호) 우선, 없으면 target 'b<char>' 에서. */
function receiverOf(e: StreamEvent): Char | null {
  if (e.to != null && typeof e.to !== 'object') return String(e.to);
  if (typeof e.target === 'string' && /^b\d+$/.test(e.target)) return e.target.slice(1);
  return null;
}

export function installHandoff(app: App): void {
  const flights: Flight[] = [];
  let levelIdx = -1;

  const destroy = (f: Flight): void => {
    if (f.done) return;
    f.done = true;
    f.tween?.remove();
    f.icon.destroy();
    f.label?.destroy();
    const i = flights.indexOf(f);
    if (i >= 0) flights.splice(i, 1);
  };
  const clearAll = (): void => { for (const f of [...flights]) destroy(f); };

  const launch = (e: StreamEvent): void => {
    const scene = app.scene;
    if (!scene || !scene.sys || !scene.add || !scene.tweens) return;
    const giver = e.char, taker = receiverOf(e);
    if (!giver || !taker) return;
    const from = scene.feetOf(giver);
    const first = scene.feetOf(taker);
    if (!from || !first) return;
    let to: { x: number; y: number } = first;

    const art = scene.visualOf('item:' + String(e.item ?? ''));
    const iconScale = art.texture === 'tiny' ? 2 : 1;
    const icon = scene.add.image(from.x, from.y - LIFT, art.texture, art.frame)
      .setOrigin(0.5, art.texture === 'tiny' ? 0.5 : 0.78)
      .setScale(iconScale).setDepth(DEPTH.fx).setName('handoff');
    const what = typeof e.what === 'string' ? e.what : '';
    const label = what
      ? scene.add.text(from.x, from.y - LIFT + 18, what, {
          fontFamily: FONT, fontSize: '11px', color: '#fff', stroke: '#000', strokeThickness: 3,
        }).setOrigin(0.5, 0).setDepth(DEPTH.fx + 1).setResolution(2).setName('handoff-label')
      : null;
    const f: Flight = { icon, label, tween: null, done: false };
    flights.push(f);
    while (flights.length > MAX_FLYING) destroy(flights[0]);    // 상한 — 오래된 것부터

    const start = { x: from.x, y: from.y - LIFT };
    const prog = { p: 0 };
    const place = (p: number): void => {
      const now = scene.feetOf(taker);           // 받는 쪽이 걷는 중이면 지금 자리를 따라간다
      if (now) to = now;
      const ex = to.x, ey = to.y - LIFT;
      const x = start.x + (ex - start.x) * p;                        // x 는 Linear
      const y = start.y + (ey - start.y) * p - ARC * Math.sin(Math.PI * p);   // y 는 살짝 떴다 내려온다
      icon.setPosition(x, y);
      label?.setPosition(x, y + 18);
    };
    f.tween = scene.tweens.add({
      targets: prog, p: 1, duration: FLY_MS, ease: 'Linear',
      onUpdate: () => place(prog.p),
      onComplete: () => {
        if (f.done) return;
        place(1);
        label?.destroy(); f.label = null;
        // 도착 팝 — 커졌다 작아진다(120ms) 뒤 사라진다. 바닥에 남는 것(placed)은 씬의 features 몫.
        f.tween = scene.tweens.add({
          targets: icon, scale: iconScale * 1.3, duration: POP_MS / 2, yoyo: true, ease: 'Sine.easeOut',
          onComplete: () => destroy(f),
        });
      },
    });
  };

  const onFrame = ({ cur, mode }: FrameChange): void => {
    if (cur.levelIdx !== levelIdx) { clearAll(); levelIdx = cur.levelIdx; }   // 층이 바뀌면 옛 좌표의 아이콘은 무의미
    if (mode === 'seek') return;                                               // 스냅 — 연출 없음
    for (const e of cur.events) {
      if (e.type === 'give' && e.result === 'given') launch(e);
    }
  };

  app.playback.on('frame', onFrame);
  app.bus.on('run', () => { clearAll(); levelIdx = -1; });
}
