/* 원더랜드 파츠 스프라이트 합성기 (D37, 2026-09-06) — 뷰어·론처 공용, 외부 의존 0.
   sprites.json(16×16 팔레트 인덱스 행렬) 을 읽어 캔버스에서 합성한다:
     heads[id].frames[dir]{rear, front} · bodies[id].frames[dir] · bodies[id].walk[dir][phase]
     · palette · materials{hair,skin,top,bottom,leather} · animations.walk{frame_ms, head_offset_y}
   겹치기 순서 rear → body → front (같은 (0,0)). 걷기 프레임은 몸통만 바뀌고 머리는 y 로 0/1px 내려간다.
   색: 재질별 기본색(look.colors{hair,skin,top,bottom}) 을 주면 팔레트의 3단 음영이 "원본 × 기본색 / 원래 기본색"
   비율로 치환된다 — 원래 기본색은 팔레트의 재질 가운데 인덱스(materials[key][1]) 라 looks.json 없이도 합성된다.
   art/sprites-v1/preview.html 의 indices()/palette()/draw() 이식. 전역 WLSprites 하나만 만든다.
   합성 결과는 (머리|몸통|방향|프레임|색4) 키로 캐시 — 판 하나에 조합이 몇 개 안 된다.
   SD 외형은 sd/atlas.json의 96px 시트를 읽고 (외형|헤어스타일|방향|프레임)으로 별도 캐시한다. */
(function (root) {
  'use strict';
  const DIRS = ['front', 'left', 'back', 'right'];
  let DATA = null;
  let SD = null;
  let coreDone = false;               // 대표 시트(외형 1종당 한 장) 를 다 받았나 - 이때부터 고른 외형이 제 그림으로 보인다
  let coreReady = Promise.resolve();  // 그 첫 묶음이 끝나는 때
  let sheetsDone = false;             // 헤어 변형까지 다 받았나 - 받는 중에는 고를 목록을 시트 유무로 거르지 않는다
  let sheetsReady = Promise.resolve();  // 전부 끝나는 때(부르는 쪽은 이걸 기다렸다 그림만 다시 그린다)
  const sheets = new Map();
  const hairSheets = new Map();
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
    // 완성 외형은 시트에 저장된 id로 선택한다. 예전 파츠 외형은 그대로 합성한다.
    if (isSD(look)) {
      dir = DIRS.includes(dir) ? dir : 'front';
      const col = phase == null || phase < 0 ? 0 : 1 + ((Math.floor(phase) % 4) + 4) % 4;
      const key = ['sd', look.sprite, look.hairstyle || 'default', dir, col].join('|');
      if (cache.has(key)) return cache.get(key);
      const size = SD.presets[look.sprite].cell || SD.cell;
      const c = document.createElement('canvas'); c.width = c.height = size;
      c.getContext('2d').drawImage(sdSheet(look), col * size,
        SD.directions.indexOf(dir) * size, size, size, 0, 0, size, size);
      cache.set(key, c); return c;
    }
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
    SD = null; sheets.clear(); hairSheets.clear();
    // SD 묶음이 없거나 한 장이 실패해도 기존 파츠와 다른 외형은 표시한다.
    coreDone = sheetsDone = false;
    try {
      const base = new URL('sd/atlas.json', new URL(url, location.href));
      const response = await fetch(base, {cache:'no-store'});
      if (!response.ok) throw new Error('SD atlas ' + response.status);
      const config = await response.json();
      SD = config;                       // 목록(외형·헤어)은 시트보다 먼저 선다 - atlas 하나면 무엇을 고를 수 있는지 다 안다
      // 시트를 다 기다리면 부르는 쪽 화면이 그동안 멈춘다(124장 13.8MB, 원격에서 45초+).
      // 그래서 기다리지 않고 배경으로 받되, 두 묶음으로 나눈다:
      //   대표(외형 1종당 한 장, 12장 2.8MB) - 이것만 와도 고른 외형이 제 그림으로 보인다.
      //   헤어 변형(112장 10.9MB) - 헤어를 실제로 바꿀 때만 쓰이니 뒤로 미룬다.
      // 한 묶음씩 받는 건 일부러다 - 같이 받으면 대역폭을 나눠 써 대표가 그만큼 늦게 온다.
      // 도착 전에는 cell() 이 파츠 합성으로 폴백하고, 묶음이 끝날 때마다
      // coreReady/sheetsReady 가 풀려 부르는 쪽이 그림만 다시 그린다.
      const jobs = Object.entries(config.presets).flatMap(([id, preset]) =>
        Object.entries(preset.hairstyles || {default:{name:'기본 머리',sheet:preset.sheet}})
          .map(([style, art]) => ({id, preset, style, art})));
      const one = async ({id, preset, style, art}) => {
        const img = new Image();
        // ⚠️img.decode() 를 기다리지 않는다 - 크롬은 보이지 않는 탭(visibility hidden)에서 이 약속을 영영 풀지 않는다.
        // 그림을 열어 두고 다른 탭을 보다 돌아오면 시트가 하나도 안 들어와 있었다(2026-09-20 측정: 내려받기는
        // 30ms 에 끝났는데 decode 는 40초 뒤에도 pending). onload 는 그 탭에서도 정상으로 온다.
        const loaded = new Promise((res, rej) => {
          img.onload = res; img.onerror = () => rej(new Error('SD 시트 로드 실패: ' + art.sheet));
        });
        img.src = new URL(art.sheet, base).href;
        await loaded;
        const size = preset.cell || config.cell;
        if (img.width !== size * config.columns || img.height !== size * config.directions.length)
          throw new Error('SD 시트 크기 불일치: ' + id);
        hairSheets.set(id + '|' + style, img);
        if(style === 'default') sheets.set(id, img);
      };
      coreReady = Promise.allSettled(jobs.filter(j => j.style === 'default').map(one))
        .then(() => { coreDone = true; });
      sheetsReady = coreReady
        .then(() => Promise.allSettled(jobs.filter(j => j.style !== 'default').map(one)))
        .then(() => { sheetsDone = true; });
    } catch (e) { coreDone = sheetsDone = true; /* SD 미로드 = look 안의 기존 파츠로 폴백 */ }
    return DATA;
  }

  function sdSheet(look) {
    return look && (hairSheets.get(look.sprite + '|' + (look.hairstyle || 'default')) || sheets.get(look.sprite));
  }
  function isSD(look) { return !!(SD && sdSheet(look)); }

  root.WLSprites = {
    load, cell, palette, indices, DIRS, isSD,
    smooth(look) { return !!(isSD(look) && SD.presets[look.sprite].filter === 'linear'); },
    get data() { return DATA; },
    get ready() { return !!DATA; },
    get coreReady() { return coreReady; },       // 대표 시트가 온 때 - 이때 미리보기가 제 그림이 된다(부르는 쪽이 다시 그린다)
    get coreLoaded() { return coreDone; },
    get sheetsReady() { return sheetsReady; },   // 헤어 변형까지 다 온 때 - 헤어 목록이 이때 확정된다
    get sheetsLoaded() { return sheetsDone; },
    frameMs(look) { return isSD(look) ? SD.frame_ms :
      (DATA && DATA.animations && DATA.animations.walk && DATA.animations.walk.frame_ms) || 140; },
    displayScale(look) { return isSD(look) ? SD.display_scale : 1; },
    // 대표 시트가 오기 전이면 atlas 가 적은 대로 다 보여 준다(그림만 늦게 온다). 온 뒤엔 실제로 있는 것만.
    illustrations(look) { return SD ? Object.entries(SD.presets)
      .filter(([id,p]) => (!coreDone || sheets.has(id)) && (p.selectable !== false || id === look?.sprite))
      .map(([id, p]) => ({id, name:p.name, job:p.job, sex:p.sex})) : []; },
    defaultHair(look) { return SD?.presets[look?.sprite]?.defaultHair || 'default'; },
    // 새 바디는 동일한 공용 헤어 id를 쓴다. default는 저장 호환용 별칭이다.
    hairstyles(look) {
      const p = SD && look && SD.presets[look.sprite];
      return p ? Object.entries(p.hairstyles || {default:{name:'기본 머리'}})
        .filter(([id]) => (!p.sharedHair || id !== 'default') && (!sheetsDone || hairSheets.has(look.sprite + '|' + id))).map(([id,h]) => ({id,name:h.name})) : [];
    },
    // 파츠 목록(론처 칩용) — {heads:[{id,name,group}], bodies:[{id,name}]}
    parts() {
      if (!DATA) return { heads: [], bodies: [] };
      return { heads: Object.entries(DATA.heads).map(([id, h]) => ({ id, name: h.name, group: h.group })),
               bodies: Object.entries(DATA.bodies).map(([id, b]) => ({ id, name: b.name })) };
    },
  };
})(window);
