# -*- coding: utf-8 -*-
"""D26 의미 기억(남길 한 줄 피기백, 2026-07-24 파트너 확정) 헤들리스 검증 — 24번째 게이트.
프레임 "사실=엔진(D22), 의미=에이전트(D26)": 결정 응답의 선택 필드 note 한 줄이 그 봇의 기억
로그(NOTE_MAX=5, FIFO)에 쌓여 이후 모든 결정 프롬프트에 재제시된다. 추가 콜 0(피기백)·엔진
판정 불가침(캐릭터 주관 — 틀린 기억도 그 캐릭터의 착각)·결정론 무사(스트림 decisions.note
additive 파생). t83~86 "뭉쳐서 나가자" 합의가 한 결정 만에 증발하던 것의 치료.
게이트:
  ① 파싱: 응답 JSON 의 note → 결정 dict 에 실림(메뉴·자유서술 두 경로), 길이 컷(NOTE_LEN)
  ② 스위치: DUNGEON_NOTES=0 이면 파싱서 제거(NOTES_ON 게이트)
  ③ 저장: think_all 경유 — 봇 notes 에 FIFO 누적, NOTE_MAX 넘치면 오래된 것부터 바램
  ④ 주입·렌더: obs.notes → wire "기억해두기로 한 것" 섹션(있을 때만), 없으면 섹션 없음
  ⑤ 엔진 불가침: note 실린 결정을 act() 에 줘도 판정 무변화(엔진은 note 를 읽지 않는다)
  ⑥ 빈 note("")=필드 생략(로그 무변화)
(기존 verify 23종은 별도 실행.)
"""
import json

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': []}


ROWS = ["##########",
        "#1.......#",
        "#........#",
        "####>#####"]


def think_once(reply, bot=None):
    """_call_claude 모킹(verify 선례) — 한 봇 한 결정."""
    d, _ = Dungeon.from_ascii(ROWS, scan=True)
    b = bot or mkbot('1', 1, 1)
    d.view(b, [b])
    orig = brains._call_claude
    brains._call_claude = lambda p, m: (reply, None)
    try:
        out = brains.think_all(d, [b])
    finally:
        brains._call_claude = orig
    return out.get('1') or {}, b


print("── ① 파싱(두 경로·길이 컷)")
R_FREE = '{"type": "search", "say": "", "reason": "r", "note": "뭉쳐서 출구로 가기로 했다 — 두란 뒤를 따른다"}'
dec1, b1 = think_once(R_FREE)
check("① 자유서술 경로: 결정 dict 에 note 실림",
      dec1.get('note') == '뭉쳐서 출구로 가기로 했다 — 두란 뒤를 따른다')
long = '가' * 200
decL, _ = think_once('{"type": "search", "say": "", "reason": "r", "note": "%s"}' % long)
check("① 길이 컷(NOTE_LEN=%d)" % brains.NOTE_LEN,
      decL.get('note') == '가' * brains.NOTE_LEN)

print("── ② 스위치")
old_on = brains.NOTES_ON
brains.NOTES_ON = False
dec2, _ = think_once(R_FREE)
brains.NOTES_ON = old_on
check("② NOTES_ON=0 이면 파싱서 제거", 'note' not in dec2)

print("── ③ 저장(FIFO)")
b3 = mkbot('1', 1, 1)
for i in range(brains.NOTE_MAX + 2):
    _, b3 = think_once('{"type": "search", "say": "", "reason": "r", "note": "기억 %d"}' % i,
                       bot=b3)
    b3['order'], b3['path'] = None, []          # 다음 결정 가능 상태로
check("③ NOTE_MAX(%d)줄 유지 — 오래된 것부터 바램" % brains.NOTE_MAX,
      b3.get('notes') == ['기억 %d' % i for i in range(2, brains.NOTE_MAX + 2)])

print("── ④ 주입·렌더")
w4 = brains._wire({'job': '전사', 'sex': '남', 'hp': 14, 'maxhp': 14, 'str': 3, 'dex': 0,
                   'inventory': 0, 'depth': 1, 'last': None,
                   'notes': ['뭉쳐서 출구로 가기로 했다']})
check("④ wire 렌더: '기억해두기로 한 것' 섹션+내용",
      '기억해두기로 한 것' in w4 and '뭉쳐서 출구로 가기로 했다' in w4)
w4b = brains._wire({'job': '전사', 'sex': '남', 'hp': 14, 'maxhp': 14, 'str': 3, 'dex': 0,
                    'inventory': 0, 'depth': 1, 'last': None})
check("④ notes 없으면 섹션 없음", '기억해두기로 한 것' not in w4b)
# think_all 주입 확인 — 모킹 프롬프트에 직전 note 가 실려 오는가
seen_prompt = {}
d5, _ = Dungeon.from_ascii(ROWS, scan=True)
b5 = mkbot('1', 1, 1)
b5['notes'] = ['두란을 믿기로 했다']
d5.view(b5, [b5])
orig = brains._call_claude
brains._call_claude = lambda p, m: (seen_prompt.setdefault('p', p) and '' or '{"type": "search", "say": "", "reason": "r"}', None)
try:
    brains.think_all(d5, [b5])
finally:
    brains._call_claude = orig
check("④ think_all 주입: 프롬프트에 남긴 한 줄 재제시",
      '두란을 믿기로 했다' in seen_prompt.get('p', ''))

print("── ⑤ 엔진 불가침")
d6, _ = Dungeon.from_ascii(ROWS, scan=True)
b6 = mkbot('1', 1, 1)
d6.view(b6, [b6])
r_with = d6.act(b6, {'type': 'search', 'note': '이 문장은 엔진이 읽으면 안 된다'}, [b6])
check("⑤ note 실린 결정도 판정 무변화(엔진은 note 를 모른다)",
      r_with.get('type') == 'search' and 'note' not in r_with)

print("── ⑥ 빈 note")
dec7, b7 = think_once('{"type": "search", "say": "", "reason": "r", "note": ""}')
check("⑥ 빈 note = 필드 생략·로그 무변화", 'note' not in dec7 and not b7.get('notes'))

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_notes (D26 의미 기억: 남길 한 줄·FIFO 5·엔진 불가침)")
