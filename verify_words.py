# -*- coding: utf-8 -*-
"""D100(2026-10-06) 말 파일 게이트 — 정의(entities/)의 말 칸은 prompts/world/<종류>/<id>.md 에 있고 entities.read() 가 합친다.
① 리포의 말 파일 전부가 읽힌다(밟은 양을 찍는다) ② 합친 정의에 표시가 안 남는다 · 값의 꼴 ③ 왕복(파싱→렌더→파싱) ④ 엔진까지 닿는다
⑤ 복사본 root 도 리포의 말로 읽힌다(게이트들의 복사 관행) ⑥ 거절 7종을 한 번에 나열 ⑦ 지침 로더가 `<!-- -->` 메모를 걷는다
⑧ 배선(게이트 목록 · tools/check_words.py). 실 LLM 0콜, 라이브 데이터 무접촉(임시 폴더만 쓴다)."""
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault('DUNGEON_BRAIN_BACKEND', 'dummy')
import entities as ENT
import words as WD
import brains

HERE = os.path.dirname(os.path.abspath(__file__))
checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


def parse_file(path):
    with open(path, encoding='utf-8') as f:
        return WD.parse(f.read())


# ① 리포의 말 파일 — 표시가 선 정의마다 말 파일 하나, 합친 말 칸 수 = 표시 수(말은 전부 말 파일에 — 정의에 인라인으로 남은 말이 없다)
defs = ENT.reload()
md_files = sorted(glob.glob(os.path.join(WD.WORDS_ROOT, '*', '*.md')))
json_files = sorted(glob.glob(os.path.join(ENT.ROOT, '*', '*.json')))
marked, marks = {}, 0
for p in json_files:
    with open(p, encoding='utf-8') as f:
        raw = json.load(f)
    ms = WD.mark_paths(raw.get('comps') or {})
    if ms:
        marked[(os.path.basename(os.path.dirname(p)), raw['id'])] = ms
        marks += len(ms)
md_keys = {(os.path.basename(os.path.dirname(p)), os.path.splitext(os.path.basename(p))[0]) for p in md_files}
cells = sum(len(WD.word_paths(d['comps'])) for d in defs.values())
print('  정의 %d장 · 표시가 선 정의 %d장 · 말 파일 %d장 · 표시 %d개 · 합친 말 칸 %d개' % (len(defs), len(marked), len(md_files), marks, cells))
check('① 표시가 선 정의마다 말 파일 하나 · 정의 없는 말 파일 0 · 합친 말 칸 수 = 표시 수(인라인 말 0) · 이전 규모(72장·283칸) 이상',
      set(marked) == md_keys and not WD.orphans(ENT.ROOT) and cells == marks and len(marked) >= 72 and marks >= 283)

# ② 합친 정의의 꼴
dump = json.dumps(defs, ensure_ascii=False)
shape = True
for (kind, eid), ms in marked.items():
    for p in ms:
        node = defs[eid]['comps']
        for k in p.split('.'):
            node = node[k]
        if WD.is_list_path(p):
            shape = shape and isinstance(node, list) and len(node) > 0 and all(isinstance(x, str) and x for x in node)
        else:
            shape = shape and isinstance(node, str) and bool(node.strip())
check('② 합친 정의에 "@prompts" 표시가 남지 않는다 · 목록 칸은 비지 않은 문자열 목록, 나머지는 비지 않은 문자열', WD.WORD_MARK not in dump and shape)

# ③ 왕복
rt = 0
for p in md_files:
    kind, eid = os.path.basename(os.path.dirname(p)), os.path.splitext(os.path.basename(p))[0]
    items, probs = parse_file(p)
    again, probs2 = WD.parse(WD.render(kind, eid, defs[eid]['name'], list(items.items())))
    rt += int(not probs and not probs2 and again == items)
check('③ 말 파일 전부 왕복(파싱→렌더→파싱)이 같다 · 문제 0 (%d장)' % rt, rt == len(md_files))

# ④ 엔진까지 닿는다 — 합친 값 = 말 파일의 글(문장을 고쳐도 성립한다 — 글자를 박지 않는다)
app = parse_file(WD.word_file(WD.WORDS_ROOT, 'npc', 'apprentice_adventurer'))[0]
bsm = parse_file(WD.word_file(WD.WORDS_ROOT, 'building', 'blacksmith'))[0]
gob = parse_file(WD.word_file(WD.WORDS_ROOT, 'monster', 'goblin'))[0]
lore = ENT.lore()['monster:고블린']
check('④ 엔진까지 닿는다 — 견습 모험자 대사·인사 · 대장간 life 진열품(목록) · 고블린 지식 본문(lore) = 말 파일의 글',
      defs['apprentice_adventurer']['comps']['npc']['line'] == app['npc.line'] and defs['apprentice_adventurer']['comps']['npc']['hail'] == app['npc.hail']
      and defs['blacksmith']['comps']['life']['use']['wares'] == bsm['life.use.wares'] and isinstance(bsm['life.use.wares'], list)
      and lore['lore'] == gob['knowledge.deep'] and lore.get('brief') == gob.get('knowledge.brief'))

# ⑤ 복사본 root
with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, 'entities')
    shutil.copytree(ENT.ROOT, root)
    check('⑤ 정의를 임시 폴더에 복사해 읽어도 리포의 말 파일로 합쳐진다(게이트들의 복사 관행 그대로)', ENT.read(root) == defs)


# ⑥ 거절 — 정의·말 파일 둘 다 임시 사본에서 깨뜨린다(리포 무접촉)
def rewrite(path, fn):
    with open(path, encoding='utf-8') as f:
        txt = f.read()
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(fn(txt))


with tempfile.TemporaryDirectory() as tmp:
    root, wroot = os.path.join(tmp, 'entities'), os.path.join(tmp, 'world')
    shutil.copytree(ENT.ROOT, root)
    shutil.copytree(WD.WORDS_ROOT, wroot)
    os.remove(WD.word_file(wroot, 'npc', 'apprentice_adventurer'))                                           # a 말 파일 없음
    rewrite(WD.word_file(wroot, 'npc', 'street_vendor'), lambda t: t.replace('## `npc.line`', '## `npc.lines`', 1))   # b 자리는 있는데 칸 없음 · c 칸은 있는데 자리 없음
    rewrite(WD.word_file(wroot, 'building', 'blacksmith'), lambda t: t.replace('- 벼린 낫', '벼린 낫', 1))         # e 목록 칸에 '- ' 없는 줄
    rewrite(WD.word_file(wroot, 'monster', 'goblin'), lambda t: t + '\n## `knowledge.deep`\n다시\n')                 # f 같은 칸 두 번
    rewrite(WD.word_file(wroot, 'trap', 'spike'), lambda t: t + '\n## 이름 없는 제목\n글\n')                          # g 백틱 없는 제목
    jp = os.path.join(root, 'map', 'town_alley.json')
    with open(jp, encoding='utf-8') as f:
        d = json.load(f)
    d['comps']['space']['role'] = WD.WORD_MARK                                                                  # d 말 칸이 아닌 자리
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    try:
        ENT.read(root, words_root=wroot)
        msg = ''
    except ENT.EntityError as e:
        msg = str(e)
    want = ('npc/apprentice_adventurer.md: 말 파일이 없다', '`npc.line` 칸이 말 파일에 없다', '칸 `npc.lines` 가 정의(entities/npc/street_vendor.json)',
            '`space.role` 는 말 칸이 아니다', '`life.use.wares` 은(는) 목록 칸이다', '`knowledge.deep` 칸이 두 번 나온다', '제목에 `칸 이름` 이 없다')
    check('⑥ 거절 7종을 한 번에 나열 — 말 파일 없음 · 자리는 있는데 칸 없음 · 칸은 있는데 자리 없음 · 말 칸이 아닌 자리 · 목록 줄 · 두 번 · 제목',
          all(t in msg for t in want))
check('⑥ 리포의 정의는 그대로다(임시 사본만 깨뜨렸다)', ENT.reload() == defs)

# ⑦ 지침 로더 — 메모는 걷고 PARTY/SOLO 는 갈린다
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, 'p.md')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# 머리\n<!-- 개발 메모: 비밀 -->\n공통\n<!--PARTY-->\n파티 줄\n<!--/PARTY-->\n<!--SOLO-->\n솔로 줄\n<!--/SOLO-->\n끝 <!-- 꼬리 -->글\n')
    party, solo = brains._load_prompt(p)
check('⑦ 지침 로더 — `<!-- -->` 메모는 어느 쪽에도 안 간다 · PARTY/SOLO 는 그대로 갈린다 · 줄 안의 메모도 걷는다',
      '비밀' not in party + solo and '<!--' not in party + solo and '공통' in party and '공통' in solo
      and '파티 줄' in party and '솔로 줄' not in party and '솔로 줄' in solo and '파티 줄' not in solo and '끝 글' in party and '끝 글' in solo)
npc_raw = brains._npc_prompt_raw()
check('⑦ 실제 지침 — NPC 지침의 개발 메모가 NPC 두뇌에 가지 않는다 · 자리 6개는 그대로 · 모험가·사교·맥락 지침에도 주석이 없다',
      '<!--' not in npc_raw and '임시 초안' not in npc_raw
      and all(k in npc_raw for k in ('{name}', '{role}', '{persona}', '{facts}', '{scene}', '{maxlen}'))
      and '<!--' not in brains.COMPOSE_PROMPT + brains.COMPOSE_PROMPT_SOLO + brains.SOCIAL_PROMPT + brains.SOCIAL_PROMPT_SOLO + brains.CONTEXT_LINE)

# ⑧ 배선
with open(os.path.join(HERE, '_run_gates.sh'), encoding='utf-8') as f:
    gates = f.read()
out = subprocess.run([sys.executable, os.path.join(HERE, 'tools', 'check_words.py')], capture_output=True, text=True, encoding='utf-8',
                     env=dict(os.environ, PYTHONUTF8='1'))
check('⑧ 배선 — 게이트 목록에 verify_words · tools/check_words.py 가 0 으로 끝나고 밟은 양(말 칸 %d개)을 찍는다' % cells,
      'verify_words' in gates and out.returncode == 0 and ('말 칸 %d개' % cells) in out.stdout and '합쳐 읽기 OK' in out.stdout)

print('ALL PASS — verify_words (%d checks, 실 LLM 0콜)' % checks)
