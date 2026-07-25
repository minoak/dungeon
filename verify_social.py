# -*- coding: utf-8 -*-
"""채널 분리(2026-07-26 파트너 발제) 검증 — 29번째 게이트.

왜: 콜이 '작정 없는 봇'에게만 열려서, 말을 들으려면 작정을 부수는 것 말고 길이 없었다(D24).
그 부작용이 목적 상실이다 — 07-26 부검에서 작정 파기 직후 follow 46% vs 평상시 29%.
카야가 문 너머 두란을 되찾으러 문턱을 되넘는 셔틀도 여기서 나왔다.

처방: 채널을 가른다.
  · **행동 콜**(think_all) = 세계가 요구하는 결단. 종전대로 작정 없는 봇에게만
  · **사교 콜**(social_all) = 캐릭터의 재량. 걷는 중에도 열리고, **행동을 못 바꾼다**
"대화는 행동을 방해할 권한이 없다"가 훈계가 아니라 구조가 된다.

프롬프트 판정(프로브 6콜): 판단 필드(need)를 **앞에** 두어야 캐릭터가 침묵을 고른다.
say 하나만 물으면 빈칸을 못 견뎌 100% 발화(카야 3/3 침묵 · 피른 3/3 발화 — 빈도는
병리가 아니라 시트다).

게이트:
  ① 스위치 기본 꺼짐(엔진·from_ascii) — 기존 판 비트 동일
  ② social=0: 말 걸림이 종전대로 작정을 부순다(D24 원본 동작 보존)
  ③ **social=1: 작정이 살아남는다** + hailed 표시가 선다(이 게이트의 존재 이유)
  ④ 대상 선별 — 작정 있고 말 들은 봇만. 작정 없는 봇은 행동 콜에서 say 를 받으므로 제외
     (콜 중복 금지)
  ⑤ **행동 불가침** — 사교 콜이 order·path·plan 을 한 글자도 안 건드린다
  ⑥ need 선행 — no 면 say 를 읽지 않는다(모델이 뒤에 말을 붙여도 침묵)
  ⑦ **_call_claude 경유** — 게이트 15개의 스텁이 사교 콜도 막는다(유출 차단)
  ⑧ 프롬프트 파일이 없으면 채널이 통째로 꺼진다(안전망)
(기존 verify 28종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""

import brains                                      # noqa: E402
import dungeon_gm as G                             # noqa: E402
from dungeon_gm import Dungeon                     # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


ROWS = ["############",
        "#.1..2.....#",
        "#.........>#",
        "############"]


def mkbot(char, x, y, name):
    return {'char': char, 'x': x, 'y': y, 'hp': 12, 'maxhp': 12, 'str': 2, 'dex': 2,
            'wdmg': 3, 'stealth': 1, 'search_r': 1, 'job': '모험가', 'sex': '-',
            'persona': '', 'name': name, 'bag': 0, 'alive': True, 'won': False,
            'order': None, 'path': [], 'aware_of': set(), 'plan': [], 'atk_range': 1}


def stage(social, hail=True):
    d, _ = Dungeon.from_ascii(ROWS, scan=True)
    d.social, d.hail = social, hail
    bots = [mkbot('1', 2, 1, '두란'), mkbot('2', 5, 1, '카야')]
    for b in bots:
        d.view(b, bots)
    return d, bots


print("== 채널 분리 검증 ==")

# ───────────────────── ① 기본 꺼짐 ─────────────────────
d0 = Dungeon(w=20, h=10, seed=7, n_monsters=0, n_traps=0, n_lurkers=0)
check("① 엔진 직생성 기본 꺼짐(기존 판 비트 동일)", d0.social is False)
d1, _ = Dungeon.from_ascii(ROWS, scan=True)
check("① from_ascii 기본 꺼짐 — __new__ 경유라 명시 초기화 필수", d1.social is False)

# ───────────────────── ②③ 작정 보존 ─────────────────────
d, bots = stage(social=False)
walker = bots[0]
walker['order'], walker['path'], walker['plan'] = 'exit', [(3, 1), (4, 1)], [{'type': 'search'}]
got = d.hail_stop(walker, ['2'])
check("② social=0: 말 걸림이 작정을 부순다(D24 원본 동작 보존)",
      got == ['2'] and walker['order'] is None and walker['path'] == []
      and walker['plan'] == [] and walker['last']['result'] == 'hailed')

d, bots = stage(social=True)
walker = bots[0]
walker['order'], walker['path'], walker['plan'] = 'exit', [(3, 1), (4, 1)], [{'type': 'search'}]
got = d.hail_stop(walker, ['2'])
check("③ **social=1: 작정이 살아남는다** — 걷던 몸은 계속 걷는다",
      got == ['2'] and walker['order'] == 'exit'
      and walker['path'] == [(3, 1), (4, 1)] and walker['plan'] == [{'type': 'search'}])
check("③ hailed 표시가 선다(사교 콜의 대상 표식) + last 는 heard",
      walker.get('hailed') == ['2'] and walker['last']['result'] == 'heard')

# ───────────────────── ④⑤⑦ 사교 콜 ─────────────────────
calls = {'n': 0}
_ORIG = brains._call_claude


def fake(prompt, model="haiku"):
    calls['n'] += 1
    calls['prompt'] = prompt
    return '{"need": "yes", "say": "알았어, 계속 간다."}', None


d, bots = stage(social=True)
a, b = bots
a['order'], a['path'] = 'exit', [(3, 1)]
a['hailed'] = ['2']
snap = (a['order'], list(a['path']), list(a['plan']))
brains._call_claude = fake
out = brains.social_all(d, bots, {'1': [{'from': '2', 'text': '두란, 조심해'}]})
brains._call_claude = _ORIG
check("④ 작정 있고 말 들은 봇만 대상 — 콜 1회(작정 없는 동료는 행동 콜에서 say 를 받는다)",
      calls['n'] == 1 and set(out) == {'1'})
check("⑤ **행동 불가침** — order·path·plan 이 한 글자도 안 바뀐다",
      (a['order'], a['path'], a['plan']) == snap)
check("⑤ say 만 나온다(160자 상한)", out.get('1') == '알았어, 계속 간다.')
check("⑦ 사교 콜도 _call_claude 를 거친다 — 게이트 스텁이 여기도 먹힌다(유출 차단)",
      '지금 이 상황에서' in calls.get('prompt', ''))

# ───────────────────── ⑥ need 선행 ─────────────────────
def fake_no(prompt, model="haiku"):
    return '{"need": "no", "say": "이건 읽히면 안 된다"}', None


d, bots = stage(social=True)
a = bots[0]
a['order'], a['path'], a['hailed'] = 'exit', [(3, 1)], ['2']
brains._call_claude = fake_no
out2 = brains.social_all(d, bots, {})
brains._call_claude = _ORIG
check("⑥ need=no 면 say 를 읽지 않는다 — 판단이 먼저다(뒤에 말이 붙어 있어도 침묵)",
      out2 == {})

# 실패도 침묵
def fake_fail(prompt, model="haiku"):
    return "", "타임아웃 60s"


d, bots = stage(social=True)
a = bots[0]
a['order'], a['path'], a['hailed'] = 'exit', [(3, 1)], ['2']
brains._call_claude = fake_fail
out3 = brains.social_all(d, bots, {})
brains._call_claude = _ORIG
check("⑥ 콜 실패도 침묵 — 폴백이 말을 지어내지 않는다(행동 폴백과 다른 자)", out3 == {})

# ───────────────────── ④' 작정 없는 봇은 제외 ─────────────────────
d, bots = stage(social=True)
bots[0]['hailed'] = ['2']              # 작정은 없다
brains._call_claude = fake
calls['n'] = 0
out4 = brains.social_all(d, bots, {})
brains._call_claude = _ORIG
check("④ 작정 없는 봇은 사교 콜 대상이 아니다 — 콜 0회(중복 금지)",
      calls['n'] == 0 and out4 == {})

# ───────────────────── ⑧ 안전망 ─────────────────────
_SP = brains.SOCIAL_PROMPT
brains.SOCIAL_PROMPT = ""
d, bots = stage(social=True)
bots[0]['order'], bots[0]['path'], bots[0]['hailed'] = 'exit', [(3, 1)], ['2']
brains._call_claude = fake
calls['n'] = 0
out5 = brains.social_all(d, bots, {})
brains._call_claude = _ORIG
brains.SOCIAL_PROMPT = _SP
check("⑧ 프롬프트 파일이 없으면 채널이 통째로 꺼진다(콜 0 — 안전망)",
      calls['n'] == 0 and out5 == {})

# social=0 이면 아예 안 돈다
d, bots = stage(social=False)
bots[0]['order'], bots[0]['path'], bots[0]['hailed'] = 'exit', [(3, 1)], ['2']
brains._call_claude = fake
calls['n'] = 0
out6 = brains.social_all(d, bots, {})
brains._call_claude = _ORIG
check("① 스위치가 꺼져 있으면 사교 콜은 한 번도 안 나간다", calls['n'] == 0 and out6 == {})

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_social (채널 분리: 작정 보존·행동 불가침·need 선행·유출 차단)")
