# make_replay_viewer.py — 스트림(runs/*.jsonl) → 단일 HTML 리플레이 뷰어
#
# 사용: python make_replay_viewer.py runs/stream-XXXX.jsonl -o replay_viewer.html
#
# 산출물은 자기완결 HTML 하나다: 리플레이 데이터가 <script>const REPLAY=...</script>
# 로 인라인되어 더블클릭으로 열린다(fetch 없음 — file:// CORS 무관).
# 스트림 계약(STREAM_FORMAT.md)대로 tick 은 turn 이 아니라 파일 순서로 level 에 묶고,
# 모르는 필드·모르는 kind 는 조용히 무시한다.

import argparse
import json
import os

# ── 이벤트 → 사람 문장 (기계 크로니클의 미니판) ──────────────────────────
# 태그: say(대사)/think(속내)/fight(전투)/loot(획득·회복)/death(사망)/sys(관찰)/win(탈출)


def humanize(e, nm):
    """이벤트 하나 → (태그, 문장) 리스트. 소음(walking 등)은 빈 리스트."""
    out = []
    t = e.get('type')
    who = nm(e.get('char'))

    if t == 'attack' and e.get('result') == 'attack':
        tgt = e.get('target', '?')
        if e.get('hit'):
            s = f"{who} ⚔ {tgt} 명중 — {e.get('dmg', 0)} 피해"
            if e.get('crit'):
                s += " (치명타!)"
            out.append(('fight', s))
            if e.get('killed'):
                out.append(('fight', f"{who}, {tgt} 처치!"))
        else:
            out.append(('fight', f"{who} ⚔ {tgt} 빗나감"))

    elif t == 'monster_attack':
        mon = e.get('monster', '?')
        vic = nm(e.get('target'))
        if e.get('hit'):
            out.append(('fight', f"{mon} → {vic} — {e.get('dmg', 0)} 피해"))
            if e.get('down'):
                out.append(('death', f"💀 {vic}, 쓰러졌다"))
        # 몹의 빗나감은 소음 — 생략

    elif t == 'monster_notice':
        out.append(('sys', f"{e.get('monster', '?')}이(가) {nm(e.get('target'))}을(를) 발견 — 추적 시작"))
    elif t == 'monster_flee':
        out.append(('sys', f"{e.get('monster', '?')}, 달아난다"))
    elif t == 'monster_desperate':
        out.append(('sys', f"{e.get('monster', '?')}, 궁지에 몰려 이빨을 드러낸다"))

    elif t == 'walk':
        r = e.get('result')
        if r == 'encounter':
            mons = '·'.join(m.get('kind', '?') for m in e.get('monsters', []))
            out.append(('fight', f"{who}, {mons}과(와) 조우"))
        elif r == 'sighted':
            seen = '·'.join(dict.fromkeys(s.get('name', '?') for s in e.get('seen', [])))
            out.append(('sys', f"{who}, 걸음을 멈춤 — {seen} 발견"))
        elif r == 'treasure':
            out.append(('loot', f"{who}, 보물 획득"))
        elif r == 'potion':
            out.append(('loot', f"{who}, 회복 물약 획득"))
        elif r == 'at_exit':
            out.append(('sys', f"{who}, 계단 앞에 섰다"))
        elif r == 'reunion':
            out.append(('sys', f"{who}: 「낯익은 곳이다 — {e.get('name', '')}」"))
        elif r == 'wander':
            out.append(('sys', f"{who}, 같은 곳을 맴돌았음을 깨달았다 ({e.get('steps', '?')}걸음)"))
        elif r == 'wait_bored':
            out.append(('sys', f"{who}, 기다림에 지쳤다"))
        elif r == 'blocked' and e.get('monsters'):
            mons = '·'.join(m.get('kind', '?') for m in e.get('monsters', []))
            out.append(('sys', f"{who}, 길이 막혔다 — {mons}"))
        # 병기 필드(어느 result 에든 붙을 수 있음)
        if e.get('treasure') and r != 'treasure':
            out.append(('loot', f"{who}, 지나던 길에 보물 줍기"))
        if e.get('potion') and r != 'potion':
            out.append(('loot', f"{who}, 지나던 길에 물약 줍기"))
        tr = e.get('trap')
        if tr:
            if tr.get('safe'):
                out.append(('fight', f"{who}, {tr.get('name', '함정')} — 회피!"))
            else:
                s = f"{who}, {tr.get('name', '함정')}에 당함 — {tr.get('dmg', 0)} 피해"
                out.append(('fight', s))
                if tr.get('down'):
                    out.append(('death', f"💀 {who}, 쓰러졌다"))

    elif t == 'interact':
        r = e.get('result')
        if r == 'exit':
            out.append(('win', f"🚪 {who}, 계단을 내려간다 — 탈출!"))
        elif r == 'treasure':
            out.append(('loot', f"{who}, 보물 획득"))
        elif r == 'potion':
            out.append(('loot', f"{who}, 회복 물약 획득"))
        elif r == 'chest_loot':
            out.append(('loot', f"{who}, 상자를 열어 {e.get('loot', '전리품')} 획득"))
        elif r == 'chest_trap':
            out.append(('fight', f"{who}, 상자의 독침! — {e.get('dmg', 0)} 피해"))
        elif r == 'fountain_heal':
            out.append(('loot', f"{who}, 샘물을 마심 — {e.get('heal', 0)} 회복"))
        elif r == 'fountain_harm':
            out.append(('fight', f"{who}, 오염된 샘물 — {e.get('dmg', 0)} 피해"))
        elif r == 'equip':
            out.append(('loot', f"{who}, {e.get('item', '장비')} 착용"))
        elif r == 'npc_talk':
            out.append(('say', f"{e.get('npc', '?')}: 「{e.get('line', '')}」"))

    elif t == 'drink':
        if e.get('result') == 'drink_heal':
            out.append(('loot', f"{who}, 물약을 들이켠다 — {e.get('heal', 0)} 회복"))

    elif t == 'search':
        found = e.get('found', [])
        if found:
            names = '·'.join(f.get('name', '?') for f in found)
            out.append(('sys', f"{who}, 수색 — {names} 발견!"))
        else:
            out.append(('sys', f"{who}, 주변을 수색 — 허탕"))

    return out


def build_replay(path):
    party_names = {}   # char키 → 이름
    party = []
    meta = {}
    levels = []
    ticks = []
    outcome = {}

    def nm(c):
        return party_names.get(c, c if c is not None else '?')

    with open(path, encoding='utf-8') as fp:
        for ln in fp:
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except ValueError:
                continue  # tail 계약: 쓰다 만 라인은 무시
            k = o.get('kind')

            if k == 'run_meta':
                for p in o.get('party', []):
                    name = p.get('name') or p.get('job', '?')
                    party_names[p.get('char')] = name
                    party.append({'c': p.get('char'), 'name': name, 'job': p.get('job', '?')})
                meta = {'seed': o.get('seed'), 'w': o.get('w'), 'h': o.get('h'),
                        'solo': bool(o.get('solo')), 'backend': o.get('backend', '')}

            elif k == 'level':
                levels.append({'grid': o.get('grid', []), 'depth': o.get('depth')})
                # 층 개시 상태 = 프레임 0 (스폰 위치·초기 배치)
                ticks.append({
                    't': o.get('turn', 0), 'lv': len(levels) - 1,
                    'bots': [_bot(b) for b in o.get('party', [])],
                    'mons': [_mon(m) for m in o.get('monsters', []) if m.get('alive', True)],
                    'feats': [_feat(f) for f in o.get('features', [])],
                    'traps': [_trap(tr) for tr in o.get('traps', [])],
                    'log': [['sys', f"— {o.get('depth', '?')}층 진입 —"]],
                })

            elif k == 'tick':
                log = []
                for c, d in sorted((o.get('decisions') or {}).items()):
                    if d.get('skipped'):
                        continue
                    reason = d.get('reason', '')
                    if d.get('src') == 'haiku' and reason and not reason.startswith('['):
                        log.append(['think', f"{nm(c)} 💭 {reason}"])
                    if d.get('say'):
                        log.append(['say', f"{nm(c)} 「{d['say']}」"])
                for e in o.get('events', []):
                    log.extend([list(x) for x in humanize(e, nm)])
                ticks.append({
                    't': o.get('turn'), 'lv': len(levels) - 1,
                    'bots': [_bot(b) for b in o.get('bots', [])],
                    'mons': [_mon(m) for m in o.get('monsters', []) if m.get('alive', True)],
                    'feats': [_feat(f) for f in o.get('features', [])],
                    'traps': [_trap(tr) for tr in o.get('traps', [])],
                    'log': log,
                })

            elif k in ('descend', 'ascend'):
                pass  # 직후 level 라인이 프레임을 만든다

            elif k == 'end':
                word = {'escaped': '탈출 성공', 'wiped': '전멸', 'timeout': '시간 초과'}.get(
                    o.get('outcome'), o.get('outcome', '?'))
                outcome = {'outcome': o.get('outcome'), 'turns': o.get('turn'),
                           'survivors': [nm(c) for c in o.get('survivors', [])],
                           'fallen': [nm(c) for c in o.get('fallen', [])]}
                if ticks:
                    surv = '·'.join(outcome['survivors']) or '없음'
                    ticks[-1]['log'].append(['win', f"🏁 결말: {word} — 생존 {surv} ({o.get('turn')}틱)"])

    meta.update(outcome)
    meta['party'] = party
    meta['file'] = os.path.basename(path)
    return {'meta': meta, 'levels': levels, 'ticks': ticks}


def _bot(b):
    return {'c': b.get('char'), 'x': b.get('x'), 'y': b.get('y'),
            'hp': b.get('hp'), 'mh': b.get('maxhp'),
            'alive': b.get('alive', True), 'won': b.get('won', False)}


def _mon(m):
    return {'x': m.get('x'), 'y': m.get('y'), 'k': m.get('kind', '?')}


def _feat(f):
    return {'x': f.get('x'), 'y': f.get('y'), 'ty': f.get('type', '?'),
            'hid': bool(f.get('concealed'))}


def _trap(tr):
    return {'x': tr.get('x'), 'y': tr.get('y'),
            'hid': bool(tr.get('hidden')), 'sp': bool(tr.get('sprung'))}


# ── HTML 템플릿 (자기완결 — 외부 요청 0) ─────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>원더랜드 리플레이</title>
<style>
  :root { color-scheme: dark; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #15151d; color: #d8d8e0; font-family: 'Malgun Gothic', sans-serif;
         display: flex; flex-direction: column; align-items: center; padding: 16px; gap: 10px; }
  h1 { font-size: 18px; }
  .meta { font-size: 12px; color: #9a9aa8; }
  #wrap { max-width: 100%; overflow-x: auto; }
  canvas { display: block; background: #101018; border: 1px solid #2a2a3a; }
  #bar { display: flex; align-items: center; gap: 10px; width: 100%; max-width: 900px; }
  #play { width: 44px; height: 30px; font-size: 14px; background: #2a2a3e; color: #d8d8e0;
          border: 1px solid #44445a; border-radius: 4px; cursor: pointer; }
  #play:hover { background: #35354e; }
  #slider { flex: 1; }
  #turn { font-size: 12px; color: #9a9aa8; min-width: 70px; text-align: right;
          font-variant-numeric: tabular-nums; }
  #log { width: 100%; max-width: 900px; height: 220px; overflow-y: auto; background: #101016;
         border: 1px solid #2a2a3a; border-radius: 4px; padding: 8px 10px;
         font-size: 12px; line-height: 1.55; }
  #log div { white-space: pre-wrap; }
  .say   { color: #8ab4f8; }
  .think { color: #71718a; font-style: italic; }
  .fight { color: #e07a7a; }
  .loot  { color: #e0bd62; }
  .sys   { color: #8a8a99; }
  .death { color: #ff5555; font-weight: bold; }
  .win   { color: #6ae86a; font-weight: bold; }
  .tmark { color: #55556a; }
  .legend { font-size: 11px; color: #77778a; }
</style>
</head>
<body>
<h1>🏰 원더랜드 — 리플레이</h1>
<div class="meta" id="meta"></div>
<div id="wrap"><canvas id="cv"></canvas></div>
<div id="bar">
  <button id="play">▶</button>
  <input id="slider" type="range" min="0" value="0">
  <span id="turn"></span>
</div>
<div id="log"></div>
<div class="legend" id="legend"></div>
<script>const REPLAY = __REPLAY_JSON__;</script>
<script>
(function () {
  const R = REPLAY, M = R.meta;
  const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
  const slider = document.getElementById('slider'), playBtn = document.getElementById('play');
  const turnEl = document.getElementById('turn'), logEl = document.getElementById('log');

  const CELL = Math.max(10, Math.min(24, Math.floor(1200 / M.w), Math.floor(660 / M.h)));
  const DPR = window.devicePixelRatio || 1;
  cv.width = M.w * CELL * DPR; cv.height = M.h * CELL * DPR;
  cv.style.width = (M.w * CELL) + 'px'; cv.style.height = (M.h * CELL) + 'px';
  ctx.scale(DPR, DPR);

  const JOB_COLOR = { '전사': '#5b8dd9', '도적': '#58c470', '궁수': '#d9b84a',
                      '음유시인': '#d9b84a' };
  const MON_COLOR = { '고블린': '#d95b5b', '그림자거미': '#a45bd9' };
  const FEAT = { exit: ['▼', '#6ae86a'], treasure: ['$', '#e0bd62'], chest: ['▣', '#b08a5a'],
                 fountain: ['~', '#4ac4c4'], potion: ['!', '#e87ab0'], grave: ['†', '#8a8a99'] };
  const botName = {}, botJob = {};
  M.party.forEach(p => { botName[p.c] = p.name; botJob[p.c] = p.job; });

  // 메타 줄 + 범례
  const oc = { escaped: '탈출 성공', wiped: '전멸', timeout: '시간 초과' }[M.outcome] || M.outcome;
  document.getElementById('meta').textContent =
    M.file + ' · 시드 ' + M.seed + ' · ' + M.w + '×' + M.h +
    (M.solo ? ' · 솔로 판' : '') + ' · 결말: ' + oc + ' (' + M.turns + '틱)' +
    ' · ' + M.party.map(p => p.name + '(' + p.job + ')').join(' · ');
  document.getElementById('legend').textContent =
    M.party.map(p => p.name[0] + '=' + p.name).join(' ') +
    ' · 색 글자=몬스터 · $=보물 ▣=상자 ~=샘 !=물약 ▼=계단 · 반투명=숨은 것(관전자 시점)';

  function draw(i) {
    const f = R.ticks[i], grid = R.levels[f.lv].grid;
    ctx.clearRect(0, 0, M.w * CELL, M.h * CELL);
    // 지형
    for (let y = 0; y < grid.length; y++) {
      const row = grid[y];
      for (let x = 0; x < row.length; x++) {
        const ch = row[x];
        if (ch === '#') { ctx.fillStyle = '#33334a'; ctx.fillRect(x * CELL, y * CELL, CELL - 1, CELL - 1); }
        else if (ch === '+') { ctx.fillStyle = '#6a4a2a'; ctx.fillRect(x * CELL, y * CELL, CELL - 1, CELL - 1); }
        else if (ch === '.') { ctx.fillStyle = '#1a1a24'; ctx.fillRect(x * CELL, y * CELL, CELL - 1, CELL - 1); }
      }
    }
    ctx.font = 'bold ' + (CELL - 3) + 'px "Malgun Gothic", monospace';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const cx = x => x * CELL + CELL / 2, cy = y => y * CELL + CELL / 2 + 1;
    // 함정: 드러난 것만 진하게, 숨은 것은 관전자 특권으로 희미하게
    f.traps.forEach(t => {
      ctx.globalAlpha = t.hid ? 0.25 : 0.9;
      ctx.fillStyle = t.sp ? '#666' : '#e07a7a';
      ctx.fillText('^', cx(t.x), cy(t.y));
    });
    // 피처
    f.feats.forEach(ft => {
      const g = FEAT[ft.ty]; if (!g) return;
      ctx.globalAlpha = ft.hid ? 0.3 : 1;
      ctx.fillStyle = g[1];
      ctx.fillText(g[0], cx(ft.x), cy(ft.y));
    });
    ctx.globalAlpha = 1;
    // 몬스터 (살아있는 것만 스트림에 실림)
    f.mons.forEach(m => {
      ctx.fillStyle = MON_COLOR[m.k] || '#d97b5b';
      ctx.fillText(m.k[0], cx(m.x), cy(m.y));
    });
    // 봇
    f.bots.forEach(b => {
      if (b.won) return;                      // 탈출자는 판에 없다
      const name = botName[b.c] || b.c;
      if (!b.alive) { ctx.fillStyle = '#666'; ctx.fillText('✕', cx(b.x), cy(b.y)); return; }
      ctx.fillStyle = JOB_COLOR[botJob[b.c]] || '#8ab4f8';
      ctx.fillRect(b.x * CELL, b.y * CELL, CELL - 1, CELL - 1);
      ctx.fillStyle = '#0d0d12';
      ctx.fillText(name[0], cx(b.x), cy(b.y));
      // HP 바
      if (b.mh) {
        ctx.fillStyle = '#0d0d12';
        ctx.fillRect(b.x * CELL, b.y * CELL, CELL - 1, 3);
        ctx.fillStyle = b.hp / b.mh > 0.5 ? '#58c470' : (b.hp / b.mh > 0.25 ? '#e0bd62' : '#ff5555');
        ctx.fillRect(b.x * CELL, b.y * CELL, Math.max(0, (CELL - 1) * b.hp / b.mh), 3);
      }
    });
  }

  function renderLog(i) {
    const parts = [];
    for (let j = 0; j <= i; j++) {
      const f = R.ticks[j];
      f.log.forEach(([tag, text]) => {
        parts.push('<div class="' + tag + '"><span class="tmark">t' + f.t + '</span> ' +
                   text.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</div>');
      });
    }
    logEl.innerHTML = parts.join('');
    logEl.scrollTop = logEl.scrollHeight;
  }

  let cur = 0, timer = null;
  function show(i) {
    cur = Math.max(0, Math.min(R.ticks.length - 1, i));
    slider.value = cur;
    turnEl.textContent = 't ' + R.ticks[cur].t + ' / ' + M.turns;
    draw(cur); renderLog(cur);
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; playBtn.textContent = '▶'; } }
  playBtn.addEventListener('click', () => {
    if (timer) { stop(); return; }
    if (cur >= R.ticks.length - 1) cur = -1;
    playBtn.textContent = '⏸';
    timer = setInterval(() => {
      if (cur >= R.ticks.length - 1) { stop(); return; }
      show(cur + 1);
    }, 300);
  });
  slider.max = R.ticks.length - 1;
  slider.addEventListener('input', () => { stop(); show(+slider.value); });

  show(0);
  console.log('[replay] ready — frames=' + R.ticks.length + ' outcome=' + M.outcome);
})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description='스트림 JSONL → 단일 HTML 리플레이 뷰어')
    ap.add_argument('stream', help='runs/stream-*.jsonl 경로')
    ap.add_argument('-o', '--out', default='replay_viewer.html', help='출력 HTML (기본 replay_viewer.html)')
    args = ap.parse_args()

    replay = build_replay(args.stream)
    payload = json.dumps(replay, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('</', '<\\/')  # </script> 조기 종결 방지
    html = TEMPLATE.replace('__REPLAY_JSON__', payload)

    with open(args.out, 'w', encoding='utf-8') as fp:
        fp.write(html)

    n = len(replay['ticks'])
    kb = os.path.getsize(args.out) // 1024
    print(f"OK: {args.out} ({kb}KB, frames={n}, outcome={replay['meta'].get('outcome')})")


if __name__ == '__main__':
    main()
