/* 원더랜드 파츠 스프라이트 합성기 (D37, 2026-09-06) — 뷰어·론처 공용, 외부 의존 0.
   sprites.json(16×16 팔레트 인덱스 행렬) 을 읽어 캔버스에서 합성한다:
     heads[id].frames[dir]{rear, front} · bodies[id].frames[dir] · bodies[id].walk[dir][phase]
     · palette · materials{hair,skin,top,bottom,leather} · animations.walk{frame_ms, head_offset_y}
   겹치기 순서 rear → body → front (같은 (0,0)). 걷기 프레임은 몸통만 바뀌고 머리는 y 로 0/1px 내려간다.
   색: 재질별 기본색(look.colors{hair,skin,top,bottom}) 을 주면 팔레트의 3단 음영이 "원본 × 기본색 / 원래 기본색"
   비율로 치환된다 — 원래 기본색은 팔레트의 재질 가운데 인덱스(materials[key][1]) 라 looks.json 없이도 합성된다.
   art/sprites-v1/preview.html 의 indices()/palette()/draw() 이식. 전역 WLSprites 하나만 만든다.
   합성 결과는 (머리|몸통|방향|프레임|색4) 키로 캐시 — 판 하나에 조합이 몇 개 안 된다. */
(function (root) {
  'use strict';
  const DIRS = ['front', 'left', 'back', 'right'];
  let DATA = null;
  const cache = new Map();

  function rgb(hex) { return String(hex).match(/[\da-f]{2}/gi).map(x => parseInt(x, 16)); }
  function hex(arr) {
    return '#' + arr.map(x => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0')).join('');
  }

  // 재질별 기본색 → 팔레트 사본. colors 에 없는 재질은 원본 그대로.
  function palette(colors) {
    const p = [...DATA.palette];
    for (const [key, ids] of Object.entries(DATA.materials)) {
      const base = colors && colors[key];
      if (!base || !/^#[\da-f]{6}$/i.test(base)) continue;
      const def = rgb(DATA.palette[ids[1]]), target = rgb(base);
      for (const i of ids) {
        const orig = rgb(DATA.palette[i]);
        p[i] = hex(orig.map((v, j) => v * target[j] / Math.max(1, def[j])));
      }
    }
    return p;
  }

  // 16×16 팔레트 인덱스 행렬 — phase<0 = 정지, 0..3 = 걷기 프레임
  function indices(head, body, dir, phase) {
    const h = DATA.heads[head].frames[dir], bd = DATA.bodies[body];
    const b = phase < 0 ? bd.frames[dir] : bd.walk[dir][phase];
    const dy = phase < 0 ? 0 : DATA.animations.walk.head_offset_y[phase];
    return b.map((row, y) => row.map((v, x) => {
      const sy = y - dy;
      return (sy >= 0 ? h.front[sy][x] : 0) || v || (sy >= 0 ? h.rear[sy][x] : 0);
    }));
  }

  // look={head, body, colors} → 16×16 캔버스(캐시). 모르는 파츠·미로드 = null (호출자가 폴백)
  function cell(look, dir, phase) {
    if (!DATA || !look || !DATA.heads[look.head] || !DATA.bodies[look.body]) return null;
    dir = DIRS.includes(dir) ? dir : 'front';
    phase = (phase == null || phase < 0) ? -1 : ((phase % 4) + 4) % 4;
    const colors = look.colors || {};
    const key = [look.head, look.body, dir, phase, colors.hair, colors.skin, colors.top, colors.bottom].join('|');
    let c = cache.get(key);
    if (c) return c;
    c = document.createElement('canvas'); c.width = c.height = 16;
    const ctx = c.getContext('2d'), im = ctx.createImageData(16, 16);
    const ids = indices(look.head, look.body, dir, phase), pal = palette(colors);
    for (let y = 0; y < 16; y++) {
      for (let x = 0; x < 16; x++) {
        const id = ids[y][x];
        if (!id) continue;
        const i = (y * 16 + x) * 4;
        im.data.set(rgb(pal[id]), i); im.data[i + 3] = 255;
      }
    }
    ctx.putImageData(im, 0, 0);
    cache.set(key, c);
    return c;
  }

  async function load(url) {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error('sprites.json ' + r.status);
    DATA = await r.json();
    cache.clear();
    return DATA;
  }

  root.WLSprites = {
    load, cell, palette, indices, DIRS,
    get data() { return DATA; },
    get ready() { return !!DATA; },
    frameMs() { return (DATA && DATA.animations && DATA.animations.walk && DATA.animations.walk.frame_ms) || 140; },
    // 파츠 목록(론처 칩용) — {heads:[{id,name,group}], bodies:[{id,name}]}
    parts() {
      if (!DATA) return { heads: [], bodies: [] };
      return { heads: Object.entries(DATA.heads).map(([id, h]) => ({ id, name: h.name, group: h.group })),
               bodies: Object.entries(DATA.bodies).map(([id, b]) => ({ id, name: b.name })) };
    },
  };
})(window);
