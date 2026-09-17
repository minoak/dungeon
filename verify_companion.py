# -*- coding: utf-8 -*-
"""D81(2026-09-17) 동료 프리셋 저장소 · 론처의 동료 칸 · 마을 안내 게이트 — 실 LLM 0콜, 라이브 데이터 무접촉(론처는 임시 폴더·포트 0).

  ① 저장소: entities/companion/*.json 로드 · sheet 부품에 능력치가 없다(직업에서 온다) · 조립한 시트의 몸 = traits.json 직업 수치 ·
     말투·목표가 실린다 · 이름은 서로 다르다
  ② 검증기 거절: sheet 없음 · 모르는 직업 · sheet 의 모르는 칸(능력치를 적음) · 등재 안 된 키워드 · npc 부품에 line 없음 · walk 꼴 불량 ·
     동료 이름 중복을 한 번에 나열
  ③ 시트 → 러너: build_party 가 {"companion": id} 칸을 받아 조립 → write_party → show_runner.load_party 통과(말투·목표·사거리 보존) ·
     사전 없이 동료 칸을 주면 거절
  ④ 론처 API: /api/presets.companions · /api/party 동료 칸 200 · 없는 id 400 · 이름 중복 400 · 동료 칸에 지어낸 id 를 줘도 시트에 안 붙는다
  ⑤ 마을 안내: build_town(guide=True) 의 장소 줄 = 건물과 던전 입구의 정의 특징(story.trait) 그대로·입구가 끝 · 스폰 표식 → 첫 관측에만
     {places, allies} · 동료 구역 = 그 순간 실제로 선 구역 · 프롬프트 문단 · 기본(guide 끔)·던전 층·이름 없는 남남은 없음
  ⑥ 배선: 러너 스위치·run_meta · 귀환 마을엔 안내 없음 · 론처 화면의 한 장 구성(편집 카드 1·동료 칸·고급 접이식·출발 버튼이 파티 저장)
"""
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request

os.environ.setdefault('DUNGEON_BRAIN_BACKEND', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import entities as ENT
import sheetkit
import dungeon_gm as G
import brains
import show_runner
import launcher

checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


def src(*parts):
    with io.open(os.path.join(HERE, *parts), encoding='utf-8') as f:
        return f.read()


BODY = ('hp', 'str', 'dex', 'wdmg', 'stealth', 'search_r', 'atk_range')
data = sheetkit.load_traits()

# ① 저장소
comps = ENT.companions()
sheets = {cid: sheetkit.build_companion_sheet(d, data=data) for cid, d in comps.items()}
check('① 동료 프리셋 로드 — id 순 · kind=companion · 폴더=companion · 셋 이상',
      list(comps) == sorted(comps) and len(comps) >= 3 and all(d['kind'] == 'companion' for d in comps.values())
      and all(os.path.isfile(os.path.join(HERE, 'entities', 'companion', cid + '.json')) for cid in comps))
check('① sheet 부품에 능력치 칸이 없다(직업에서 온다) · 조립한 몸 = traits.json 직업 수치',
      all(not (set(d['comps']['sheet']) & set(BODY)) for d in comps.values())
      and all(sheets[cid][k] == data['jobs'][sheets[cid]['job']][k] for cid in comps for k in BODY))
check('① 시트에 이름·성격·말투·목표가 실린다 · 이름은 서로 다르다 · 정의에 적은 외형은 검증된 look 으로',
      all(s['name'] == comps[cid]['name'] and s['persona'] and s.get('speech') and s.get('goal') for cid, s in sheets.items())
      and len({s['name'] for s in sheets.values()}) == len(sheets)
      and all((s.get('look') is not None) == ('look' in comps[cid]['comps']['sheet']) for cid, s in sheets.items()))

# ② 검증기 거절 — 임시 폴더의 나쁜 정의들
with tempfile.TemporaryDirectory() as root:
    def good(cid, name, **over):
        sheet = {'job': '전사', 'sex': '남', 'traits': [], 'persona': '조용하다.'}
        sheet.update(over.pop('sheet', {}))
        return {'id': cid, 'name': name, 'kind': 'companion', 'tags': ['companion'], 'comps': {'sheet': sheet, **over}}
    bad = {
        'nosheet': {'id': 'nosheet', 'name': '가', 'kind': 'companion', 'tags': [], 'comps': {'story': {'trait': 'x'}}},
        'badjob': good('badjob', '나', sheet={'job': '마법사'}),
        'stats': good('stats', '다', sheet={'hp': 99}),
        'badtrait': good('badtrait', '라', sheet={'traits': ['없는 키워드']}),
        'noline': good('noline', '마', npc={'hail': '안녕'}),
        'badwalk': good('badwalk', '바', npc={'line': '…', 'walk': {'region': '', 'rate': 2}}),
        'twin_a': good('twin_a', '쌍둥이'),
        'twin_b': good('twin_b', '쌍둥이'),
    }
    os.makedirs(os.path.join(root, 'companion'))
    for cid, d in bad.items():
        with io.open(os.path.join(root, 'companion', cid + '.json'), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False)
    try:
        ENT.read(root)
        msg = ''
    except ENT.EntityError as e:
        msg = str(e)
    check('② 검증기 거절 — sheet 없음·모르는 직업·모르는 칸(능력치)·미등재 키워드·npc.line 없음·walk 불량·이름 중복을 한 번에',
          all(t in msg for t in ('nosheet.json: sheet', '직업은', '모르는 칸: hp', '등재되지 않은 성격 키워드', 'npc.line 필요',
                                 'npc.walk', "동료 이름 '쌍둥이' 중복")))
check('② 정본 폴더는 그대로 읽힌다(동료가 다른 종류의 검사를 흔들지 않는다)', set(ENT.reload()) >= set(comps))

# ③ 시트 → 러너
me = {'name': '미나', 'sex': '여', 'job': '도적', 'traits': ['신중한'], 'persona': '', 'background': ''}
two = sorted(comps)[-2:]
party = sheetkit.build_party([me] + [{'companion': c} for c in two], data=data, companions=comps)
with tempfile.TemporaryDirectory() as tmp:
    ppath = os.path.join(tmp, 'party.json')
    sheetkit.write_party(party, ppath)
    loaded = show_runner.load_party(ppath)
check('③ 동료 칸 → 시트 → 러너 load_party 통과 — 이름 순서·말투·목표·사거리 보존 · 내 캐릭터엔 말투가 없다(만들지 않는다)',
      [loaded[c]['name'] for c in sorted(loaded)] == ['미나'] + [comps[c]['name'] for c in two]
      and all(loaded[str(i + 2)].get(k) == sheets[c].get(k) for i, c in enumerate(two) for k in ('speech', 'goal', 'atk_range', 'persona'))
      and 'speech' not in loaded['1'])
for label, slots, kw, needle in (
        ('사전 없이 동료 칸', [me, {'companion': two[0]}], {}, '없는 동료 프리셋'),
        ('없는 id', [me, {'companion': 'nobody'}], {'companions': comps}, '없는 동료 프리셋'),
        ('같은 동료 둘', [me, {'companion': two[0]}, {'companion': two[0]}], {'companions': comps}, '이름 중복')):
    try:
        sheetkit.build_party(slots, data=data, **kw)
        err = ''
    except ValueError as e:
        err = str(e)
    check('③ 거절 — %s' % label, needle in err)

# ④ 론처 API — 임시 폴더·포트 0
tmp = tempfile.mkdtemp(prefix='wl_companion_')
srv = launcher.make_server('127.0.0.1', 0, party_path=os.path.join(tmp, 'party_custom.json'),
                           state_dir=os.path.join(tmp, 'state'), runs_dir=os.path.join(tmp, 'runs'), brain='dummy')
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:%d' % srv.server_port


def call(path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8') or '{}')


try:
    st, pl = call('/api/presets')
    check('④ /api/presets.companions — 저장소의 동료 전부(id·이름·직업·성격·소개 한 줄·글자 수) · 옛 키들은 그대로',
          st == 200 and [c['id'] for c in pl['companions']] == list(comps)
          and all(c['name'] == sheets[c['id']]['name'] and c['job'] == sheets[c['id']]['job'] and c['persona'] == sheets[c['id']]['persona']
                  and c['about'] == (comps[c['id']]['comps'].get('story') or {}).get('trait') and c['prompt_chars'] > 0 for c in pl['companions'])
          and all(k in pl for k in ('traits', 'jobs', 'default_party', 'model_ui_version', 'providers')) and pl.get('party_ui_version') == 1)
    st, res = call('/api/party', {'slots': [me, {'companion': two[0]}, {'companion': two[1]}], 'preset_ids': ['', 'made-up-id', '']})
    with io.open(os.path.join(tmp, 'party_custom.json'), encoding='utf-8') as f:
        doc = json.load(f)
    check('④ /api/party 동료 칸 200 — 파티 이름 · 시트에 말투 · 지어낸 id 는 안 붙는다(서버는 제 저장소의 id 만)',
          st == 200 and [p['name'] for p in res['party']] == ['미나'] + [comps[c]['name'] for c in two]
          and doc['2'].get('speech') == sheets[two[0]]['speech'] and not any('id' in doc[c] for c in ('1', '2', '3')))
    st1, r1 = call('/api/party', {'slots': [me, {'companion': 'nobody'}]})
    st2, r2 = call('/api/party', {'slots': [dict(me, name=comps[two[0]]['name']), {'companion': two[0]}]})
    st3, r3 = call('/api/party', {'slots': [me, {'companion': 7}]})
    check('④ 거절 400 — 없는 동료 · 내 캐릭터와 동료의 이름 중복 · 문자열 아닌 id',
          (st1, st2, st3) == (400, 400, 400) and '없는 동료 프리셋' in r1['error'] and '이름 중복' in r2['error'] and '없는 동료 프리셋' in r3['error'])
finally:
    srv.shutdown()
    srv.server_close()
    shutil.rmtree(tmp, ignore_errors=True)

# ⑤ 마을 안내
d5, starts5 = show_runner.build_town(apart=True, walkers=True, guide=True)
feat = {f.name: f for f in d5.features.values()}
check('⑤ 장소 줄 = 건물과 던전 입구의 정의 특징 그대로(새 문장 없음) · 구역 이름 · 던전 입구가 맨 끝',
      d5.town_guide and d5.town_guide[-1]['name'] == '던전 입구'
      and all(p['about'] == d5.place_story[feat[p['name']].id]['trait'] and p['zone'] == d5._town_zone(feat[p['name']].x, feat[p['name']].y)
              for p in d5.town_guide)
      and {feat[p['name']].type for p in d5.town_guide} == {'building', 'exit'}
      and len(d5.town_guide) == sum(1 for f in d5.features.values() if f.type in ('building', 'exit') and (d5.place_story.get(f.id) or {}).get('trait')))
psheets = show_runner.load_party(os.path.join(HERE, 'party.json'))
bots5 = []
for c in sorted(psheets):
    b = G.spawn(d5, c, bots5, sheet=psheets[c])
    if starts5.get(c):
        b['x'], b['y'] = starts5[c]
    bots5.append(b)
names5 = {b['char']: b['name'] for b in bots5}
check('⑤ 스폰이 표식을 심는다(안내를 켠 마을에서만)', all(b.get('town_guide') is True for b in bots5))
o5 = d5.view(bots5[0], bots5)
tg = o5.get('town_guide') or {}
check('⑤ 첫 관측에 {places, allies} — 장소 줄은 러너가 뽑은 그대로 · 동료 구역 = 그 순간 실제로 선 구역(흩어진 출발이라 서로 다르다)',
      tg.get('places') == d5.town_guide
      and tg.get('allies') == [{'char': b['char'], 'zone': d5._town_zone(b['x'], b['y'])} for b in bots5[1:]]
      and len({a['zone'] for a in tg['allies']} | {d5._town_zone(bots5[0]['x'], bots5[0]['y'])}) == 3)
w5 = brains._wire(o5, names5, compose=True)
check('⑤ 프롬프트 문단 — 머리말 · 장소마다 "이름 (구역) — 특징" · "동료의 위치" 줄 · 마을 진입 한마디 바로 뒤',
      '## 마을 안내 (처음 한 번만 들린다)' in w5
      and all(('- %s (%s) — %s' % (p['name'], p['zone'], p['about'])) in w5 for p in d5.town_guide)
      and ('- 동료의 위치: ' + ', '.join('%s — %s' % (names5[a['char']], a['zone']) for a in tg['allies'])) in w5
      and w5.index('## 마을에 들어서며') < w5.index('## 마을 안내') < w5.index('## 지금 보이는 것'))
o5b = d5.view(bots5[0], bots5)
check('⑤ 한 번뿐 — 두 번째 관측엔 없다(표식도 지워졌다) · 다른 캐릭터의 첫 관측엔 있다',
      'town_guide' not in o5b and 'town_guide' not in bots5[0] and '## 마을 안내' not in brains._wire(o5b, names5, compose=True)
      and 'town_guide' in d5.view(bots5[1], bots5))
w5solo = brains._wire(d5.view(bots5[2], bots5), {}, compose=True)
check('⑤ 이름을 모르는 남남(로스터 없음)이면 "동료의 위치" 줄은 없다 — 장소 줄만', '## 마을 안내' in w5solo and '동료의 위치' not in w5solo)
d5off, _ = show_runner.build_town(apart=True, walkers=True)
b5off = G.spawn(d5off, '1', [], sheet=psheets['1'])
dg5 = G.Dungeon(w=40, h=16, seed=7)
b5dg = G.spawn(dg5, '1', [], sheet=psheets['1'])
check('⑤ 기본은 끔 — build_town 직접 호출(게이트·귀환 마을)·던전 층에는 표식도 관측도 없다',
      getattr(d5off, 'town_guide', None) is None and 'town_guide' not in b5off and 'town_guide' not in d5off.view(b5off, [b5off])
      and 'town_guide' not in b5dg and 'town_guide' not in dg5.view(b5dg, [b5dg]))

# ⑥ 배선
rs = src('show_runner.py')
check('⑥ 러너: DUNGEON_TOWN_GUIDE 기본 1 · 시작 마을에만 넘긴다 · run_meta.town_guide · 귀환 마을(town_for_run(False, …))엔 안내 없음',
      'os.environ.get("DUNGEON_TOWN_GUIDE", "1") != "0"' in rs
      and 'town_for_run(TOWN_APART_ON, quests, TOWN_WALKERS_ON, TOWN_GUIDE_ON)' in rs
      and 'town_guide=bool(TOWN_ON and TOWN_GUIDE_ON)' in rs
      and 'town_for_run(False, quests, TOWN_WALKERS_ON)' in rs)
html = src('launcher', 'index.html')
check('⑥ 론처 화면 한 장 — 편집 카드는 1번 칸 하나·동료 칸·고급 접이식·마을이 출발의 기본·출발 버튼이 파티를 저장한다 · 옵션 화면은 없다',
      'slots.slice(0, 1).map(' in html and 'id="mates"' in html and '<details id="advanced"' in html and 'id="town" checked' in html
      and "await api('/api/party', partyPayload());" in html and "out.push({ companion: m.id })" in html
      and 'id="sOpts"' not in html and "$('bNext')" not in html and '마을로 출발' in html and 'presets.party_ui_version !== 1' in html)
check('⑥ 론처 서버: 동료 목록을 /api/presets 에 · 동료 칸을 저장소 정의로 조립',
      '"companions": companions_payload(p)' in src('launcher.py') and 'companions=comps' in src('launcher.py'))

print('ALL PASS — verify_companion (%d checks, 실 LLM 0콜)' % checks)
