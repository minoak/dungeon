# -*- coding: utf-8 -*-
"""
던전 GM 엔진 (레이어 1) — TRPG 코어
─────────────────────────────────────────────
이 파일은 '게임마스터 = 심판'이다. 전부 결정론적 코드.
규칙 집행·상태 관리·시야 계산·주사위 판정·턴 진행 = 신뢰할 수 있는 진실의 원천.

역할 삼분할:
  · 봇의 '두뇌'(brains.py) = 생각/의논/행동선언. act(obs)->action(dict) 으로만 들어온다.
  · GM의 '서사'(gm.py)      = 상황 연출. 이 파일이 준 events(진실)만 묘사한다.
  · 엔진(이 파일)           = 주사위(d20)를 굴리고 규칙으로 성패를 가른다.
      └ 주사위는 여기서만 굴린다. LLM은 난수를 못 만든다 — 진실은 코드가 쥔다.
      └ 몬스터·함정은 여기 좌표로 '실재'한다. GM이 무에서 지어내는 게 아니다.

봇과 엔진의 통신은 obs(dict) / action(dict) 으로만 오간다.
→ tmux 패널 분리(파일 IPC)로 가도 이 인터페이스가 그대로 경계가 된다.

[Stage 1 재설계] 칸격자 → 오브젝트/피처 토대:
  · Feature(출구·보물·…) = 칸이 아니라 이름붙은 객체. exit/treasures 를 흡수.
  · Room = id·타입(entrance/exit/standard)·인접 그래프를 가진 객체.
  · path_to() = BFS 길찾기(8연결, 코너컷 금지) — Stage 2 핑 자동보행의 토대.
  · 시드 RNG 스트림 일원화(self.rng) — 모든 굴림 경유, 마스터→깊이별 파생 = 재현성.
"""

import json                     # 사건 사전(D40) 폴백 — 모르는 결과 형태는 JSON 으로 정직 노출
import composed_actions as CA
import social_reactions as SR
import skill_core as SK
import skill_combat as SC
import entities as ENT           # 엔티티 저장소(D50, 09-11) — 몬스터·함정·오브젝트·NPC 정의(수치·이름·지식 본문)
import town_layout as TL         # 마을 layout(town-layout-v1, 맵 트랙 저작 원본) → 격자 컴파일(엔진 무의존 모듈)
import math
import os
import random
from collections import deque

WALL, FLOOR, EXIT, TREASURE, MONSTER, TRAP = '#', '.', '>', '$', 'M', '^'
DOOR = '+'                      # 문 타일(D19 정정 2026-07-15): 벽처럼 빛을 막고 바닥처럼 지나간다.
                                # 개폐 상태 없음(항상 불투명 MVP — 격자 불변=결정론·리플레이 무손상,
                                # 그 너머의 기억은 장부 몫). scan 판 전용 — 기본(scan=0) 격자엔 없다.
CHEST, FOUNTAIN = '=', '~'      # 방 콘텐츠(Stage 3): 상자(도박)·샘(회복 도박)
GRAVE = 'T'                     # 묘(D22): 쓰러진 자리의 표지판 — 시체가 아니다(운반·부패·부활 의미론
                                # 없음, D4 불가침). "누가 묻었나"는 묻지 않는 게임 문법(로그라이크 묘비).
POTION = '!'                    # 회복 물약(07-17, PD 문법): 주워 들고 다니는 확정 완전 회복 —
                                # 샘(그 자리 도박)과 대비되는 '보험'. 첫 소지 아이템(bot['potions'])
STAIRS_UP, NPC = '<', '&'       # 마을(D29, 2026-07-30): '<'=위로 오르는 계단(마을 복귀 — 하강 '>'와
                                # 대칭 문법), '&'=NPC(가게 앞에 서 있는 사람 — 몸이 있어 통과 불가,
                                # 말 걸면 한 줄. 거래·대화=다음 단계). 마을=0층, 던전=1층부터.
WEAPON, ARMOR = ')', '['        # 장비(2026-07-30, 뼈대): 슬롯 2(무기·방어구)+단순 보정. 착용=캐릭터
                                # 판단(interact — 자동 줍기 아님·보물/물약과 다른 문법). 스왑=헌 장비를
                                # 그 자리에 놓는다(인벤토리 없음 — 슬롯이 소지의 전부).
GEAR_KINDS = ENT.gear_kinds()   # ← entities/object/*.json equipment.bonus(D50)   # 이름→보정(피처는 이름만 들고
                                # 보정은 여기서 푼다 — Feature __slots__/스트림 계약 무접촉).
                                # 저주·미식별·강화=2차 서랍(07-30 합의).
GEAR_CYCLE = [('weapon', '단검'), ('armor', '가죽 갑옷'),             # 배치 순환(함정 kinds 선례 —
              ('weapon', '장검'), ('armor', '사슬 갑옷')]             # RNG 무소비 결정론)


def gear_bonus(bot, slot):
    """봇의 착용 보정(무기=피해·방어구=막기). 미착용/구판 봇 dict(키 없음)=0 — 하위호환.
    장비 뼈대(07-30)의 판정 접점은 이 함수 둘뿐: _attack 피해 · _monster_attack 방어."""
    g = bot.get(slot)
    return g['bonus'] if g else 0
LURKER, HIDDEN = 'm', '*'       # 관전자 전용(극적 아이러니): 숨은 적/숨은 보물. 봇 시야(view)엔 절대 안 나간다.
UNKNOWN_BEAST = '낯선 짐승'     # 도감(D9) 미등재 몬스터의 obs 표기 — 보이지만 정체를 모른다.


# (09-08 D45) 겉보기 부상 등급 `_wound_label`(D18 A-4, 멀쩡/가벼운 상처/다침/빈사)은 폐지 — 파트너 "상태 태그 + hp 를 보여주면
#   되잖아, 위급·부상 이렇게 나눌 필요가 없다". 동료도 몹·나와 같은 자(HP 숫자)로 읽는다. 몹 도주 경계 FLEE_FRAC 은 무관.


_UNLOCK_KR = {'encounter': '조우'}   # 해금 사건의 표시 어휘(⚠️임시 — 파트너 문장 대기). 메모 §2-6 [제안] "고블린 (심층: 승리 3/5)"


def _deep_sfx(m):
    """obs 몬스터 항목의 심층 진행도 → ' (심층: 조우 3/5)'. 없으면 ''(해금됐거나 조건 없는 종)."""
    pr = m.get('deep_progress') if isinstance(m, dict) else None
    if not pr:
        return ''
    return ' (심층: %s %d/%d)' % (_UNLOCK_KR.get(pr.get('event'), pr.get('event')), pr.get('n', 0), pr.get('need', 0))


def _mfact(m):
    """몹 한 줄 사실 문장 — 리모컨 라벨과 wire 직렬화(D17-3)가 같은 문구를 쓴다(단일 소스).
    state 코드의 한국어 번역이 여기 산다 — 프롬프트의 번역표는 폐기(obs 자기설명)."""
    st = {'SLEEPING': '잠듦(날 못 봄)', 'WANDERING': '배회(날 못 봄)',
          'FLEEING': '도주 중'}.get(m['state'])
    if m['state'] == 'HUNTING':
        # aware:false 라도 '동료를 추격'이라 단정하면 거짓이 될 수 있다(표적이 이미
        # 죽었거나 하강한 유예 구간) + 인접 몹은 표적 무관 아무나 무는 규칙이라 오도됨.
        st = ('나를 추격 중' if m['aware']
              else '추격 중(표적은 내가 아님 — 단 인접하면 누구든 물린다)')
    return '%s %s — %s, HP %d' % (m['kind'], m['id'], st, m['hp'])
# EXIT 글리프 = '>' (구 'E'는 이동방향 East와 충돌 → '>'로 분리). 봇은 'E'를 출구로 영영 안 본다.
VISITED = ','   # 시야에서 '이미 가본 바닥' 표시 (파티 공유 발자국). 단일폭 ASCII.
# 바닥은 '.'(ASCII 폭1) — 가운뎃점 '·'(U+00B7)은 ambiguous-width라 한글 폰트에서
# 전각으로 그려져 격자 정렬이 밀린다. 격자 문자는 전부 단일폭 ASCII로 유지한다.
MOVES = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0),
         'NE': (1, -1), 'NW': (-1, -1), 'SE': (1, 1), 'SW': (-1, 1)}   # 8방향(대각선 포함)

# ── Stage 2b 인식·기습 상수 (튜닝 가능 — 설계 검토 후 확정값) ─────────────
# 시야 반경 = 세계의 단일 물리량(봇 관측·봇 인지·몹 시야·목격 전부 이 한 자로 잰다 — 대칭).
# 기본 3→5 확장(2026-07-11 민옥 지시: "맵이 작아서 일부러 제한했는데 너무 좁다").
# 반경 5(11×11)면 생성기 방(5~9×3~5)이 거의 항상 한눈에 들어온다. env 노브로 실험 가능.
SIGHT = max(1, int(os.environ.get('DUNGEON_SIGHT', '5') or 5))
MON_SIGHT = SIGHT        # 몹 시야 반경 = 봇과 대칭(visible_cells 공유) — SIGHT 의 별칭
DETECT_DC_BASE = 13      # 발각굴림 기준 DC(+은신). 전사 DC13·도적 DC17. (DC10은 전사 기습 6%로 사실상 불가 → 13)
WANDER_DETECT_BONUS = 2  # WANDERING 몹은 발각 +2(SLEEPING보다 경계). (+4는 즉시추격 → +2로 완화)
LOSE_GRACE = 3           # HUNTING→WANDERING 강등: LOS 상실 연속 이만큼이면 추적 포기(숨바꼭질)
SURPRISE_DMG_BOT = 3     # 봇 기습 보너스 피해(crit 배수 밖 가산)
SURPRISE_DMG_MON = 2     # 몹 기습 보너스 피해

# ── Stage 3 직업 인지·함정 패밀리·도주·하강 상수 ────────────────
PASSIVE_DC = 14          # 수동 search-on-move: 자동보행 칸마다 d20+DEX ≥ 이 값이면 반경 내 숨은 것 발견
LURK_DC = 16             # 숨은(매복) 몹을 수동 인지로 알아채는 DC — 함정보다 어렵다(매복이 보통은 성립해야)
CAREFUL_BONUS = 3        # '드러난' 함정을 어쩔 수 없이 밟을 때 회피 보너스 — 알고 건너는 조심스러운 걸음
FLEE_FRAC = 3            # hp*FLEE_FRAC ≤ maxhp 면 도주 전환(≈1/3 이하). 궁지에 몰리면 필사 반격
FLEE_STAMINA = 8         # 봇에게 보이며 도주한 턴 누적이 이만큼이면 탈진 → 필사 반전(desperate HUNTING).
                         #   영구 술래잡기 livelock(도주몹이 봇 결정 틱마다 비껴가며 미방문 칸을 막아
                         #   explore 재시도 무한) 차단 — 어떤 두뇌가 와도 엔진이 종결을 보장한다.
EXIT_GATHER = 3          # 하강 조율: 살아있는 파티 전원이 계단 반경(체비셰프) 이내여야 내려간다(솔로탈출 방지)
SOLO_APART = 12          # 솔로 판 출발 간격 하한(맨해튼) — 시야 반경보다 한참 멀어 첫 조우가 우연이 되게.
                         #   실제 간격은 맵 크기로 키운다(아래 spawn) — 좁은 맵에선 단계적으로 완화한다.
PLAN_MAX = 2             # 작정(D16): 현재 행동에 이어 미리 정해둘 수 있는 수의 상한 —
                         # 귀머거리 창(작정 집행 중엔 inbox 를 다음 결정점까지 못 읽음) 억제
DETOUR_FACTOR = 2        # 사회적 대우회 감지(D18): 동료를 피해 깐 경로가 '동료 없다 치고'의 최단 대비
DETOUR_SLACK = 2         #   FACTOR배+SLACK칸을 넘고, 그 최단길 위에 동료가 서 있으면 → 말없는 행군
                         #   대신 blocked 보고(누가 막는지 allies 로) — 라이브 22틱 두란 서쪽 행군 부검.
                         #   지형이 원래 먼 것(free 도 길다)은 정당한 지리 — 감지 대상 아님.
FOLLOW_IDLE = 3          # 동행 고착 해약(D18): 곁 대기 중 대상이 이만큼 연속 틱 제자리면 동행 종료
CHASE_IDLE = 1           # D48 개정 2(09-12 파트너 "goto도 1턴 정도만 아군에게 follow처럼"): goto<아군>이 곁+대상 정지에서 붙어 서는 틱 수.
                         #   1 = 그 틱에 곁에 서고(0걸음) 다음 틱 재판단. 작정(then)이 딸려 있으면 횟수와 무관하게 닿는 즉시 잇는다.
                         #   (result=idle) → 재결정. 동행은 '따라 걷기'다 — 아무도 안 걸으면 성립하지
                         #   않는다. 상호 동행 삼각 고착(fellowsmoke 120틱 결정 5회 실측)=흡수 상태의
                         #   물리적 제거. 파트너 판정 2026-07-11: "셋이 서서 세 턴이면 어색해질 시간"
                         #   — K=3 고정(튜닝마라).
WANDER_N = 10            # 맴돎 자각(D21): 결정 없이 이만큼 박자를 보냈는데 새로 본 칸이 0이고
                         #   그 사이 밟았던 칸을 되밟고 있으면 → 정지+관찰 보고(판단은 두뇌 몫).
                         #   박자=걸음+작정 대기 틱(follow 곁 대기·paced 양보 — 07-24 수선: 큰 판
                         #   swap 셔틀은 걸음이 5틱에 1개꼴이라 10걸음=48틱 지연. 창의 의도 '한참'은
                         #   시간이지 걸음 수가 아니다). 정지 판정은 여전히 되밟는 걸음에서만.
                         #   되밟기 조건은 '아는 길 직행 관통'(출구 귀환·장부 goto — D19 직행 주파)을
                         #   맴돎으로 오인하지 않기 위한 최소 분별 — 직선 역행은 재방문이 없다.
                         #   3인 회전 셔틀(07-20 큰 판, 결정 0으로 ~50틱) 실측 t85 고착 기준 캘리브레이션.
                         #   튜닝은 큰 판 실측 후(튜닝마라).
DRY_K = 25               # 무발견 신호(층 1, 07-24 합의 — 파트너 발제): 마지막 새 목격 이후 이만큼
                         #   걸으면 다음 결정 obs 에 한 줄(도달 시점 1회만 — 상시 노출 금지=파트너
                         #   확정, 소음 방지). 탐색 커버리지 문제라 걸음만 센다(맴돎의 박자와 다른
                         #   자 — 제자리 틱은 탐색이 아니다). 셔틀(결정 0 구간)엔 안 닿는 보완층
                         #   (그쪽 그물=D21). 합의 초기값 25~30 중 하한 채택(1회성이라 소음 상한
                         #   이미 낮음). 튜닝은 큰 판 실측 후(튜닝마라).
WAIT_MAX = 15            # wait(D25) 지루함 상한: 이만큼 틱을 기다려도 아무 일 없으면 "한참을
                         #   기다렸다 — 아무도 오지 않는다" 관찰과 함께 재결정. 없으면 '기다려'
                         #   말한 이가 죽거나 길을 잃었을 때 영원히 서 있는 봇이 남는다. 숫자
                         #   인자는 안 둔다(사람은 틱을 세며 기다리지 않는다 — 파트너 확정안).
                         #   합의 15~20 중 하한 채택. 튜닝은 큰 판 실측 후(튜닝마라).
TRAIL_MAX = 12           # 자기 행동 궤적(D38, 09-06) 상한: 마지막 view() 이후 보존할 결과 수. 넘치면 앞을
                         #   버리고 생략 표식 한 칸(gap n) — 결정 사이가 보통 10틱 안이라 실전에선 안 찬다
OBJ_VERBS = {'npc': '말 걸어 봄',   # 오브젝트 태그(D39, 09-06): **쓰고도 남아 있는 오브젝트만**
             'weapon': '착용해 봄', 'armor': '착용해 봄'}   # D57(09-12): 장비는 개체(번호 유지)라 내려놓아도 태그가 남는다
                                    #   (샘·상자·보물·물약·장비는 쓰면 사라져 "×N"이 뜻이 없다. 문·몹은 서랍)


def _obj_note(res):
    """오브젝트 태그의 마지막 사실 한 마디(D39) — 상호작용 결과에서. 해석 없음(사실만). None=이전 note 유지."""
    if res.get('result') == 'npc_gift':
        return '%s 받음' % res.get('item', '?')
    return None


def _tagsfx(f):
    """오브젝트 태그 접미(D39) — ' — 말 걸어 봄 ×2 (물약 받음)'. 리모컨 라벨과 wire 시야 줄의 단일 소스(_mfact 선례).
    태그 없으면 빈 문자열(구판 문자열 그대로)."""
    t = f.get('tag') if isinstance(f, dict) else None
    if not t:
        return ''
    return ' — %s ×%d%s' % (t.get('verb', '?'), int(t.get('n', 0)),
                             (' (%s)' % t['note']) if t.get('note') else '')


# ── 사건 사전(D40, 2026-09-06 파트너 확정 "꼬리표식으로 바꾸자·픽셀 던전 방식·위급은 4분의 1") ──
# 픽셀 던전의 GLog 처럼 사건마다 짧은 꼬리표 하나 — "[발견] 고블린 m3", "[피격] 고블린(m3) −2 (HP 8)", "[출혈] 걸림".
# 궤적(D38)·층 집계·결산이 **같은 사전**을 센다(STATUS_KINDS·BONES 선례 — 사전 하나). 값=(집계 여부).
# 문장형 서술(_last_prose·act_summary·_witness_prose)은 관전·스트림·목격 줄에 남는다 — 캐릭터 자기 궤적만 꼬리표다.
BOSS_KIND = '고블린 대장'   # D65(09-13) 보스층의 보스 — 정의 entities/monster/goblin_chief.json(수치·습성·지식). 랜덤 몹 풀엔 안 든다
EVENT_KINDS = {
    'spot': True, 'hit': True, 'kill': True, 'miss': True, 'hurt': True, 'status': True,
    'critical': True, 'recovered': True, 'trap': True, 'trap_safe': True, 'loot': True, 'use': True,
    'door': True, 'talk': True, 'rest_done': True, 'hail': True, 'lost': True, 'reunion': True,
    'wander': True, 'enter': True, 'descend': True, 'ascend': True, 'plan_broken': True,
    'wait_allies': True, 'search': True, 'exhausted': True,
    'give': True, 'bond': True, 'received': True, 'bonded': True,   # D47 ② 건네기·친목(한 쪽·받은 쪽)
    'move': False, 'start': False, 'arrive': False, 'blocked': False, 'swap': False, 'misc': False,
}
WITNESS_LABELS = {              # 목격 사건(witnessed kind) → 집계 라벨. 문장은 brains._witness_prose 그대로
    'ally_hurt': '동료 피격', 'ally_down': '동료 전사', 'ally_hit': '동료 명중', 'ally_kill': '동료 처치',
    'ally_trap': '동료 함정', 'ally_heal': '동료 회복', 'ally_loot': '동료 획득', 'ally_spot': '동료 발견',
    'ally_mishap': '동료 사고', 'ally_use': '동료 사용', 'mon_use': '몹 문 사용', 'ally_status': '동료 상태',
    'ally_give': '동료 건넴', 'ally_bond': '동료 친목',   # D47 ②(09-09) 건네기·친목 목격
}
_RUN_RESULTS = {'walking': '걸음', 'following': '틱 동행', 'beside': '틱 곁',   # beside = D48 개정 goto<아군> 추적의 곁 유지 틱
                'waiting': '틱 대기', 'resting': '틱 휴식'}


def is_moving(bot):
    """D48 개정(09-11 메모 §2-4) '대상이 멈추면'의 판정 — 마지막 틱 경계(monster_turn 진입, _record_positions) 이후
    자리를 옮겼거나 직전 완료 틱에 옮겼으면 움직이는 중. 경계 기록이 없으면(첫 틱·경계 없는 하니스) 멈춘 것으로 본다.
    봇 내부 키(_xy_end·_xy_end_prev)만 읽는다 — 스냅샷·관측에 안 나간다(verify_skill_off 기준선 무접촉)."""
    end = bot.get('_xy_end')
    if end is None:
        return False
    end = tuple(end)
    return (bot['x'], bot['y']) != end or end != tuple(bot.get('_xy_end_prev') or end)


def _followed_char(order):
    """'follow:b2'(동행 D18)·'chase:b2'(추적 D48 개정) → '2'(따라가는 상대). 아니면 None."""
    s = str(order or '')
    if s.startswith('follow:b'):
        return s[8:]
    if s.startswith('chase:b'):
        return s[7:]
    return None


def place_word(tgt, ctx='walk'):
    """칸 핑 '@x,y' → 사람 말(09-08, 파트너 발제 "좌표가 없어도 위치 판단은 된다" → D17-4 pos 판정과 한 묶음).
    생좌표는 엔진 내부 id 다 — 프롬프트에 새면 캐릭터가 자기 세계에 없는 숫자를 읽는다(_tgt_name 의 'follow:'
    선례). 결정 문맥(이동 시작·최근 판단·직전 판단·작정)의 '@'는 리모컨 '마지막 본 자리로'뿐이라 "마지막 본
    자리", 걷기 문맥(자동보행 도착)의 '@'는 탐색 종점이거나 그 칸 핑이라 "가려던 자리". '@'가 아니면 그대로.
    ⚠️ 두 문구는 임시 가정(파트너 문장 대기). 관전 로그(act_summary)는 사람용이라 좌표 그대로 둔다."""
    s = str(tgt or '')
    if s[:1] != '@':
        return s
    return '마지막 본 자리' if ctx == 'decide' else '가려던 자리'


def event_tags(rec, names=None):
    """사건 사전 투영(D40): 엔진 결과 dict 하나 → [(키, 라벨, 짧은 사실)]. 한 결과가 여러 사실을 담으면
    (조우: 적 여럿+함정+발견) 여러 꼬리표. 사실만·해석 없음·조향 없음. 모르는 형태=('misc','기타',JSON).
    어휘 전거는 STREAM_FORMAT 이벤트 표 — _last_prose 와 같은 결과를 읽되 문장 대신 꼬리표를 낸다."""
    if not isinstance(rec, dict):
        return [('misc', '기타', str(rec))]
    t, r = rec.get('type'), rec.get('result')
    tgt = str(rec.get('target') or '')
    nm = lambda c: (names or {}).get(c, '동료')
    out = []
    if rec.get('skill_id'):
        return [('skill', '스킬', SK.summary(rec))]
    if t == 'pushed':
        return [('hurt', '밀림', '스킬에 의해 한 칸 밀려났다')]
    if r == 'approaching':
        return [('start', '접근 시작', '%s %s' % (t, place_word(tgt, 'decide')))]
    if r == 'no_path' and rec.get('parent_action_id'):
        return [('misc', '접근 불가', place_word(tgt, 'decide'))]
    if r == 'no_effect':
        return [('misc', '변화 없음', '%s %s' % (t, tgt))]
    if t == 'healed' or (t == 'use' and r == 'healed'):
        return [('heal', '회복', '%s +%d (HP %d)' % (tgt, rec.get('heal', 0), rec.get('hp', 0)))]
    if t == 'use' and rec.get('effect_type'):
        return event_tags({**rec, 'type': rec['effect_type']}, names)
    if t == 'use':
        return [('misc', '사용 실패', '%s (%s)' % (tgt, r))]
    if t == 'state':
        k = 'critical' if r == 'critical' else 'recovered'
        return [(k, '위급' if k == 'critical' else '위급 해제', 'HP %d/%d' % (rec.get('hp', 0), rec.get('maxhp', 0)))]
    if t == 'hurt':
        s = '%s(%s) −%d (HP %d)%s' % (rec.get('by', '?'), rec.get('by_id', '?'), rec.get('dmg', 0),
                                      rec.get('hp', 0), ' 기습' if rec.get('surprise') else '')
        out.append(('hurt', '피격', s))
        if rec.get('status'):
            out.append(('status', rec['status'], '걸림'))
        return out
    if t == 'hail':
        who = ', '.join(nm(c) for c in rec.get('froms', [])) or '동료'
        return [('hail', '부름', '%s의 말에 멈춤' % who)]
    if t == 'plan_broken':
        st = rec.get('step') or {}
        return [('plan_broken', '작정 깨짐', '%s %s — %s' % (st.get('type', '?'), place_word(st.get('target', ''), 'decide'), rec.get('why', '?')))]
    if t == 'attack':
        if r != 'attack':
            return [('miss', '헛침', '대상 없음' if r == 'no_target' else '사거리 밖')]
        who = '%s(%s)' % (rec.get('target', '?'), rec.get('target_id', '?'))
        if rec.get('killed'):
            return [('kill', '처치', who)]
        if rec.get('hit'):
            return [('hit', '명중', '%s −%d%s' % (who, rec.get('dmg', 0), ' 회심' if rec.get('crit') else ''))]
        return [('miss', '빗나감', who)]
    if t == 'drink':
        return [('use', '사용', '물약 (HP %d, 남은 %d)' % (rec.get('hp', 0), rec.get('potions', 0)))] \
            if r == 'drink_heal' else [('misc', '기타', '물약 없음')]
    if t == 'search':
        f = rec.get('found') or []
        return [('search', '수색', ('발견 ' + ', '.join(x.get('name', '?') for x in f)) if f else '허탕')]
    if t == 'wait':
        return [('start', '대기 시작', '')]
    if t == 'rest':
        return [('start', '휴식 시작', '')]
    if t == 'interact':
        if r == 'exit':
            return [('descend', '하강', '함께' if len(rec.get('party') or []) > 1 else '혼자')]
        if r == 'ascend':
            return [('ascend', '상행', '워프게이트로 마을로' if rec.get('gate') else '마을로')]
        if r == 'locked':                                     # D65 봉인된 워프게이트 — 사실만
            return [('blocked', '봉인', '워프게이트 — 닫혀 있다')]
        if r == 'wait_allies':
            bits = []
            if rec.get('missing'):
                bits.append('빠짐 ' + ','.join(nm(c) for c in rec['missing']))
            if rec.get('busy'):
                bits.append('딴 일 ' + ','.join(nm(c) for c in rec['busy']))
            return [('wait_allies', '동료 대기', ' · '.join(bits))]
        if r == 'treasure':
            return [('loot', '획득', '보물')]
        if r == 'potion':
            return [('loot', '획득', '물약 (소지 %d)' % rec.get('potions', 0))]
        if r == 'chest_loot':
            return [('loot', '획득', '상자 → 보물 %d' % rec.get('loot', 0))]
        if r == 'chest_trap':
            out.append(('trap', '함정', '상자 독침 −%d (HP %d)' % (rec.get('dmg', 0), rec.get('hp', 0))))
        elif r == 'fountain_heal':
            return [('use', '사용', '샘 +%d (HP %d)' % (rec.get('heal', 0), rec.get('hp', 0)))]
        elif r == 'fountain_harm':
            out.append(('trap', '함정', '오염된 샘 −1 (HP %d)' % rec.get('hp', 0)))
        elif r == 'equip':
            return [('use', '착용', '%s%s%s' % (rec.get('item', '?'), (' ' + rec['id']) if rec.get('id') else '',   # D57 번호
                                               (' (헌것 %s%s 내려놓음)' % (rec['dropped'], (' ' + rec['dropped_id']) if rec.get('dropped_id') else ''))
                                               if rec.get('dropped') else ''))]
        elif r == 'no_effect' and rec.get('slot'):        # D56: 같거나 못한 장비 — 그대로 둠
            return [('misc', '그대로', '%s — 지금 것과 %s' % (rec.get('item', '?'), '같다' if rec.get('why') == 'same' else '못하다'))]
        elif r == 'npc_gift':
            return [('talk', '대화', '%s: %s 받음' % (rec.get('npc', '?'), rec.get('item', '?')))]
        elif r == 'npc_talk':
            return [('talk', '대화', '%s "%s"' % (rec.get('npc', '?'), (rec.get('line') or '')[:30]))]
        elif r in ('nothing', 'too_far', 'no_target'):
            return [('misc', '헛손질', r)]
        if out:
            if rec.get('status'):
                out.append(('status', rec['status'], '걸림'))
            return out
        return [('misc', '기타', json.dumps(rec, ensure_ascii=False))]
    if t == 'give':                                   # D47 ②(09-09) 건네기 — 한 쪽의 자기 사건
        if r == 'given':
            return [('give', '건넴', '%s → %s%s' % (rec.get('what', '?'), nm(rec.get('to')),
                                                  ' (그의 발밑에 놓임)' if rec.get('placed') else ''))]
        return [('misc', '헛손질', {'too_far': '곁에 없음', 'nothing': '줄 것 없음', 'no_room': '놓을 자리 없음'}.get(r, r))]
    if t == 'bond':                                   # D47 ② 친목 — 한 쪽의 자기 사건(형태=자유 문구)
        if r == 'done':
            return [('bond', '친목', '%s → %s' % (rec.get('form', '몸짓'), nm(rec.get('to'))))]
        return [('misc', '헛손질', {'too_far': '곁에 없음'}.get(r, r))]
    if t == 'received':                               # D47 ② 받은 쪽의 자기 사건(hurt 문법 — 남이 내게 한 일)
        return [('received', '받음', '%s (%s)%s' % (rec.get('what', '?'), nm(rec.get('from')),
                                                   ' — 발밑에 놓임' if rec.get('placed') else ''))]
    if t == 'bonded':
        return [('bonded', '친목 받음', '%s: %s' % (nm(rec.get('from')), rec.get('form', '몸짓')))]
    if t in ('goto', 'explore', 'follow'):
        who = nm(tgt[1:]) if (tgt[:1] == 'b' and tgt[1:].isdigit()) else place_word(tgt, 'decide')   # 사람 대상 goto(D48 개정)=이름
        if r == 'pathed':
            return [('start', '이동 시작', (who + ' 쪽') if tgt and tgt != 'auto' else '새 길')]
        if r == 'already_beside':                          # 옛 판(D48 개정 1) 스트림 호환
            return [('misc', '이미 곁', who + ' — 멈춰 있다, 갈 곳 없음')]
        if r == 'beside':                                  # D48 개정 2: 곁에 붙어 선다(CHASE_IDLE 틱)
            return [('start', '곁에 섬', who + ' — 붙어 있는다')]
        if r == 'following':
            return [('start', '동행 시작', nm(tgt[1:]) if tgt.startswith('b') else tgt)]
        if r == 'arrived':
            return [('arrive', '도착', who + ' — 이미 곁')]
        if r == 'no_path':
            return [('exhausted', '막다름', '새 길 없음' if rec.get('exhausted') else '지금 갈 길 없음')]
        if r == 'blocked':
            return [('blocked', '길 막힘', ', '.join(a.get('name', '?') for a in (rec.get('allies') or [])) or '동료')]
    if t == 'walk':
        extras = []
        if rec.get('door') and r != 'arrived':
            extras.append(('door', '문 사용', str(rec['door'])))
        if rec.get('treasure'):
            extras.append(('loot', '획득', '보물'))
        if rec.get('potion'):
            extras.append(('loot', '획득', '물약'))
        if rec.get('bleed'):
            b = rec['bleed']
            extras.append(('status', '출혈', '−1 (HP %d)%s' % (b.get('hp', 0), ' — 쓰러짐' if b.get('down') else '')))
        if r in _RUN_RESULTS:
            return [('move', r, '')] + extras
        if r == 'arrived':
            if tgt[:1] == 'd' and tgt[1:].isdigit():
                return [('door', '문 사용', tgt)] + extras
            return [('arrive', '도착', (place_word(tgt) or '목적지') + ' 곁')] + extras
        if r == 'at_exit':
            return [('arrive', '도착', '계단')] + extras
        if r == 'treasure':
            return [('loot', '획득', '보물')] + [e for e in extras if e[0] != 'loot']
        if r == 'potion':
            return [('loot', '획득', '물약')] + [e for e in extras if e[0] != 'loot']
        if r == 'encounter':
            for m in rec.get('monsters') or []:
                out.append(('spot', '발견', '%s(%s)' % (m.get('kind', '?'), m.get('id', '?'))))
            tr = rec.get('trap')
            if tr:
                if tr.get('safe'):
                    out.append(('trap_safe', '함정 회피', tr.get('name', '함정')))
                elif tr.get('alarm') is not None:
                    out.append(('trap', '함정', '%s 울림' % tr.get('name', '경보')))
                else:
                    hp = rec.get('hp', tr.get('hp'))
                    out.append(('trap', '함정', '%s −%d%s' % (tr.get('name', '함정'), tr.get('dmg', 0),
                                                            (' (HP %d)' % hp) if hp is not None else '')))
                    if tr.get('status'):
                        out.append(('status', tr['status'], '걸림'))
            for f in rec.get('found') or []:
                out.append(('spot', '발견', f.get('name', '?')))
            if rec.get('woke') == 'rest':
                out.insert(0, ('arrive', '휴식 중단', '새 몹'))
            return (out or [('spot', '발견', '새로운 것')]) + extras
        if r == 'blocked':
            who = ', '.join(a.get('name', '?') for a in (rec.get('allies') or [])) or \
                  ', '.join(m.get('kind', '?') for m in (rec.get('monsters') or [])) or '길'
            return [('blocked', '길 막힘', who)] + extras
        if r == 'lost':
            return [('lost', '놓침', nm(tgt[1:]) if tgt.startswith('b') else tgt)] + extras
        if r == 'idle':
            return [('arrive', '동행 끝', nm(tgt[1:]) if tgt.startswith('b') else tgt)] + extras
        if r == 'reunion':
            return [('reunion', '낯익은 곳', rec.get('name', '와 본 곳'))] + extras
        if r == 'wander':
            return [('wander', '맴돎', '새로 본 것 없음')] + extras
        if r in ('wait_met', 'rest_met'):
            return [('arrive', '동료 도착', ', '.join(nm(c) for c in rec.get('allies', [])) or '동료')] + extras
        if r == 'wait_bored':
            return [('arrive', '기다림 끝', '아무도 안 옴')] + extras
        if r == 'rested':
            cl = rec.get('cleared') or []
            return [('rest_done', '휴식 완료', 'HP +%d%s' % (rec.get('healed', 0), (', 나음: ' + '·'.join(cl)) if cl else ''))] + extras
        if r == 'swapped':
            return [('swap', '자리 교대', rec.get('with', '동료'))] + extras
        if r == 'entered':
            zz = rec.get('zone') or {}
            return [('enter', '새 방', '%s %s' % (zz.get('kind', '공간'), zz.get('id', '')))] + extras
        if r == 'sighted':
            return [('spot', '발견', ', '.join(x.get('name', '?') for x in (rec.get('seen') or [])))] + extras
    return [('misc', '기타', json.dumps(rec, ensure_ascii=False))]


def addressed_to(msg, char):
    """지목(D41, 2026-09-06 파트너 발제 "말 걸림에 say 대상을 넣자"): 이 말이 나(char)에게 한 말인가 —
    `to` 가 내 번호이거나 'all'. 대상 없는 말 = 혼잣말·방송(들리긴 하지만 나를 부른 게 아니다).
    배달(들림)은 러너가 시야로 정하고, 정지(말 걸림)·대화 뼈는 이 판정을 지난 말만 센다."""
    to = (msg or {}).get('to')
    return to == 'all' or (to is not None and str(to) == str(char))


def floor_freeze(bot, depth, turn):
    """결산(D40 ②, 파트너 확정 "층이 끝나면 결산"): 층을 떠나는 순간 그 층의 집계를 얼려 지난 층 목록에 붙인 것을
    돌려준다(러너가 재스폰 직전에 부른다 — 마을↔던전 왕복 모두). 뼈=기계가 센 횟수, 살=캐릭터가 다음 층 첫 결정에서
    남기는 한 줄(`floor_line`, D26/D36 피기백 — 추가 콜 0, invite 는 그 결정 1회). 시스템 LLM 요약은 안 한다(요약자가
    해석을 섞는다 — D15 저작권 원칙). 봇 dict 는 안 건드린다(순수 함수)."""
    fl = bot.get('floor') or {}
    entry = {'depth': int(depth), 't0': int(fl.get('since') or 0), 't1': int(turn),
             'n': dict(fl.get('n') or {}), 'w': dict(fl.get('w') or {}), 'line': None, 'invite': True}
    return [dict(x) for x in (bot.get('floors') or [])] + [entry]
HAIL_CD = 3              # 말 걸림 정지(07-24 D24) 쿨다운: 같은 발화자는 이 턴 수 안에 다시 말해도
                         #   재정지 없음(메시지 배달은 그대로 — 다음 자연 결정에 읽음). 수다 루프
                         #   (마주 서서 무한 핑퐁) 방어는 내용 아닌 구조로. D23 회의 서랍행으로
                         #   쿨다운이 유일한 대화 조절기 — 관대하게, 즉시 재정지만 막는 몇 틱
                         #   ("셋이 서서 세 턴이면 어색해질 시간" D14 K=3 과 같은 자). 튜닝마라.

# ── 상태 태그(D34, 2026-09-06 파트너 확정 "HP 는 그대로, 몹·함정이 특수공격으로 태그를 붙인다") ──
# 태그 = 몸에 붙는 상태. 효과는 몸(굴림·걸음)에만 닿고 판단은 강제하지 않는다(D14 — 정신 붕괴류
# 없음). 지우는 길은 휴식(D35)뿐 — 저절로 사라지는 태그를 만들면 지우는 규칙이 둘이 되고 쉴 이유가
# 사라진다. 라벨 문장은 여기가 단일 소스(_mfact 선례) — 리모컨·wire·act_summary 가 같은 말을 한다.
# 사실만: 효과를 그대로 말한다("세계가 말하는 것=규칙이 하는 것", 07-29 거짓 규칙 계보).
# 같은 태그 재발 = n 만 는다(×N 표시 — 효과 불변, 첫 판 관찰 뒤 재론). 물약은 HP 만(태그 불변).
STATUS_KINDS = {
    '출혈': '{steps}걸음마다 피가 1 난다 (제자리·전투 중엔 안 난다) — 쉬면 멎는다',
    '둔화': '{every}틱에 한 칸밖에 못 걷는다 (붙은 몹을 떨어뜨릴 수 없다) — 쉬면 풀린다',
    '중독': '명중과 회피가 {mod} 깎인다 — 쉬면 빠진다',
}
BLEED_STEPS = 3          # 출혈: 이만큼 걸을 때마다 HP 1 (첫 판 관찰값 — 튜닝은 판 뒤)
SLOW_EVERY = 2           # 둔화: 자동보행 이 틱마다 한 칸(=한 틱 걷고 한 틱 쉼)
POISON_MOD = 2           # 중독: 명중(_attack mod)·회피(_monster_attack ac) 감산
MON_STATUS = ENT.mon_status()   # ← entities/monster combat.on_hit(D50)   # 몹의 특수 = 태그(명중 시). 고블린=무태그(기준선 몹 — 대비의 자)
REST_HP = 1              # 휴식(D35): 틱마다 차는 HP (hp 2 → 만피 14 가 열두 틱쯤 = WAIT_MAX 눈금)
REST_MIN = 5             # 휴식 완료 하한: 만피여도 이만큼은 쉬어야 몸 상태가 낫는다("푹 쉬어야 낫는다")

# ── 관계 장부(D36, 2026-09-06 파트너 확정 "뼈는 기계가 세고, 살은 문턱에서만 캐릭터가 쓴다") ──
# 림월드의 관계는 게임이 라벨과 숫자를 적고 플레이어가 서사로 읽는다 — 우리는 읽는 사람이 캐릭터
# 자신이다. 뼈 = 말 내용 없이 구조(스트림 어휘)에서 나오는 사실만(say 해석 0 — D5). 살 = 캐릭터가
# 문턱에서만 쓰는 한 줄(겹쳐쓰기, 엔진 불가침 — D15② 뼈/살). 호감도 숫자 없음(가중치=튜닝 축).
RELATION_K = 10          # 약한 뼈 합계가 이 배수를 넘는 결정에 한 줄을 청한다(매 스텝 평가 방지)
FOUGHT_WINDOW = 5        # 같은 몹을 이 틱 안에 둘이 치면 '함께 싸움'(쌍·몹당 1회)
BONES = {'talk': '이야기를 나눔', 'fought': '함께 싸움', 'waited': '나를 기다려 줌',
         'rescued': '나를 구함', 'at_death': '죽을 때 곁에 있었음',
         # D47(2026-09-08, 파트너 "'말한다'를 목적에 맞게 쪼갠다 — 집계는 종류별로"): 제안은 잡담(talk)과 따로 센다.
         # 시도와 반응이 짝 — proposed(내가 그에게 제안) ↔ asked(그가 내게 제안) / answered(그가 내 제안에 답함) ↔
         # replied(내가 그의 제안에 답함). '답함'은 다음 결정에서 그 사람에게 말을 했다는 구조적 사실뿐(수락·거절은 안 읽는다).
         # ⚠️ 라벨 문구는 세션 임시안 — 파트너 문장 대기.
         'proposed': '제안함', 'asked': '제안받음', 'answered': '내 제안에 답함', 'replied': '제안에 답해 줌',
         # D47 ②(2026-09-09, 파트너 "건네기를 만들려면 아이템 거래를 넣어야 해" · "['대화' '친목' '머리를 쓰다듬기'] — 친목 행위라
         # 일반 대화와는 별개"): 건네기는 방향이 있고(gave/received), 친목은 쌍이 같이 센다(파트너 초안 §A-5 "두란과 친목행위 3회"
         # — 묶어 표시, 상세는 acts 기록에). ⚠️ 라벨 문구는 세션 임시안 — 파트너 문장 대기.
         'gave': '물건을 건넴', 'received': '물건을 받음', 'bond': '친목행위'}
STRONG_BONES = ('rescued', 'at_death')   # 즉시 청한다 — 한 번이 열 번의 잡담보다 무겁다
ACTS_MAX = 8             # 관계 장부의 상세 기록(D47 ②: 친목·건네기 한 건=형태+상대 반응) 보존 상한 — 상대별
ACTS_SHOW = 4            # 결정 obs 에 되돌려주는 최근 기록 수(상대별)
BOND_LEN = 120           # 친목 서술(응답 form) 한 줄 상한 — 행동의 맥락을 보존한다. 관계 평가는 캐릭터의 요약 몫.
ITEM_KR = {'potion': '회복 물약', 'weapon': '무기', 'armor': '방어구'}   # 건네기 item 키 → 사람 말(메뉴·장부·궤적 공용)


def status_prose(tag):
    """태그 한 줄 사실 문장(효과) — 리모컨·wire·목격 문장의 단일 소스. 미등록 태그는 정직하게 흘린다."""
    s = STATUS_KINDS.get(tag, '%s — 정체 모를 상태' % tag)
    return s.format(steps=BLEED_STEPS, every=SLOW_EVERY, mod=POISON_MOD)


# ── 캐릭터 시트 (영웅) ───────────────────────────────────────────
# d20 + 능력보정 vs 목표(AC/DC). 전사=힘·HP, 도적=민첩(함정 회피·기습).
# stealth = 발각 DC 가산(은신). 전사 0(시끄러움→잘 들킴), 도적 4(은신→매복 주력).
# search_r = 인지 반경(Stage 3): 도적 2(5×5)·전사 1(3×3). 수동(걸으며 d20+DEX)·능동(search 액션=확정) 공용.
#   → 직업 대비의 몸통: 도적은 넓게+민첩 보정으로 숨은 함정·매복·보물을 압도적으로 잘 찾는다.
HEROES = {
    '1': {'job': '전사', 'sex': '남', 'hp': 14, 'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0, 'search_r': 1,
          'persona': '용맹하고 정면돌파를 즐긴다. 동료를 지키려 앞장서지만 다소 무모하다.'},
    '2': {'job': '도적', 'sex': '여', 'hp': 10, 'str': 0, 'dex': 3, 'wdmg': 3, 'stealth': 4, 'search_r': 2,
          'persona': '신중하고 함정·기습에 능하다. 위험을 먼저 재고 약은 수를 쓴다.'},
}


class Monster:
    """던전에 실재하는 적. GM이 지어내는 게 아니라 여기 좌표로 존재한다.
    state(2b): SLEEPING(잠·발각굴림만) / WANDERING(배회·발각 +2) / HUNTING(추격). LOS 발각으로 전이.
    target/last_seen/lost: HUNTING 추격·강등용. skip_turns: 기습당해 행동 스킵(대상 턴 스킵).
    concealed: 숨은 적(Stage 3 인지판정). id: 핑 대상.
    수치(hp·atk·dmg·ac)·도주 파라미터는 엔티티 정의(entities/monster, D50)가 기본값 — 명시 인자가 우선(장면 저작·게이트)."""
    def __init__(self, x, y, kind='고블린', hp=None, atk=None, dmg=None, ac=None, mid=0):
        spec = ENT.monster_stats(kind)       # 모르는 종은 기준선 몹(고블린)의 몸
        hp = spec['hp'] if hp is None else hp
        atk = spec['atk'] if atk is None else atk
        dmg = spec['dmg'] if dmg is None else dmg
        ac = spec['ac'] if ac is None else ac
        self.x, self.y, self.kind = x, y, kind
        self.hp, self.maxhp = hp, hp
        self.atk, self.dmg, self.ac = atk, dmg, ac
        self.flee_frac, self.flee_stamina = ENT.monster_flee(kind)   # ai.flee — 없으면 (None, None)=도주 안 함
        self.flee_to, self.flee_join_range = ENT.monster_flee_mode(kind)   # D51: 'ally'=근처 다른 몹에게 붙어 같이 싸운다
        self.alive = True
        self.id = mid
        self.state = 'SLEEPING'      # 2b: 발각굴림으로 HUNTING 전이, LOS 상실로 WANDERING 강등. 3: 저HP→FLEEING
        self.target = None           # HUNTING 중 추격하는 봇 char
        self.last_seen = None        # 타겟 마지막 목격 좌표(LOS 잃어도 그리로 추격)
        self.lost = 0                # HUNTING/FLEEING 중 LOS 상실 연속 턴(LOSE_GRACE 넘으면 강등)
        self.skip_turns = 0          # 기습당함 → 이번 턴(들) 행동 스킵. _attack이 set, monster_turn이 소비
        self.waking = 0              # TIME_TO_WAKE_UP=1: 막 깬(발각 직후) 1턴은 아직 기습 가능(취약창)
        self.concealed = False       # 매복몹(Stage 3): 인지판정/일격으로만 드러남. 봇 obs·맵에 안 나감
        self.flee_turns = 0          # 봇에게 보이며 도주한 턴 누적(FLEE_STAMINA 넘으면 필사 반전)
        self.desperate = False       # 필사 반전됨 — 다시는 도주하지 않는다(죽을 때까지 문다)
        self.last_hits = {}          # 관계 장부(D36): char → 마지막으로 이 몹을 친 틱('함께 싸움' 재료)
        self.fought = set()          # 이 몹을 두고 이미 '함께 싸움'이 적힌 쌍(frozenset) — 몹당 1회
        self.boss = False            # D65(09-13): 보스층의 보스 개체 — 죽으면 워프게이트 봉인이 풀린다(스트림 'boss': true)

    def as_dict(self):
        """스트림(JSONL) 직렬화 — 관전자/웹 데이터 계약(STREAM_FORMAT.md).
        AI 내부 장부(last_seen/lost/skip_turns/waking/flee_turns)는 제외 —
        resume 은 시드+decisions 리플레이로 하지, 스냅샷 복원으로 하지 않는다."""
        return {'id': self.id, 'kind': self.kind, 'x': self.x, 'y': self.y,
                'hp': self.hp, 'maxhp': self.maxhp, 'ac': self.ac,
                'atk': self.atk, 'dmg': self.dmg, 'alive': self.alive,
                'state': self.state, 'concealed': self.concealed,
                'target': self.target, 'desperate': self.desperate,
                **({'boss': True} if getattr(self, 'boss', False) else {}),   # D65 additive — 보스층의 보스
                **({'status': sorted(self.skill_status)} if getattr(self, 'skill_status', None) else {})}


# 함정 패밀리(Stage 3, SPD 33종→3종 린 스타터): 베이스 클래스 1개 + kind 테이블.
#   spike = 기본 피해 / dart = 독침(가벼운 피해·회피 어려움) / alarm = 경보(피해 0, 층의 몹 일제 각성
#   = justAlerted 굴림 우회 → 함정이 인식 시스템에 결합되는 지점. 줄당 연출 최고).
TRAP_KINDS = ENT.trap_kinds()    # ← entities/trap/*.json(D50): spike 13/3 출혈 · dart 14/2 중독 · alarm 13/0 — status(D34)=피해와 별개 태그


class Trap:
    """숨은 함정. 밟으면 DEX 판정. 도적은 잘 피하고 전사는 잘 당한다.
    kind 로 종류 분기(dc/dmg 명시하면 덮어씀 — 구 시그니처 호환)."""
    def __init__(self, x, y, dc=None, dmg=None, kind='spike'):
        spec = TRAP_KINDS[kind]
        self.x, self.y, self.kind, self.name = x, y, kind, spec['name']
        self.dc = spec['dc'] if dc is None else dc
        self.dmg = spec['dmg'] if dmg is None else dmg
        self.hidden = True    # 아직 안 드러남(바닥처럼 보인다)
        self.sprung = False   # 한 번 발동됨

    def as_dict(self):
        """스트림(JSONL) 직렬화 — 관전자/웹 데이터 계약(STREAM_FORMAT.md)."""
        return {'x': self.x, 'y': self.y, 'kind': self.kind, 'name': self.name,
                'dc': self.dc, 'dmg': self.dmg,
                'hidden': self.hidden, 'sprung': self.sprung}


class Feature:
    """던전의 '오브젝트/피처' — 출구·보물·문·가구·발판 등. 칸이 아니라 이름붙은 객체.
    봇은 칸이 아니라 *보이는 피처*를 핑한다(Stage 2). 칸격자 substrate 탈출의 핵심 표현.
    concealed=숨김(인지 판정으로만 드러남), perception_gate=드러내는 데 필요한 인지 난도(0=자동)."""
    __slots__ = ('id', 'type', 'name', 'x', 'y', 'room_id', 'concealed', 'perception_gate', 'worn')

    def __init__(self, fid, ftype, name, x, y, room_id=None,
                 concealed=False, perception_gate=0):
        self.id, self.type, self.name = fid, ftype, name
        self.x, self.y, self.room_id = x, y, room_id
        self.concealed, self.perception_gate = concealed, perception_gate
        self.worn = set()      # D56(09-12): 이 장비를 착용해 본 캐릭터들 — 내려놓거나 건네져 바닥에 놓일 때 이어받는다.
                               #   obs 에서 '착용한 적 없음'(new) 표시의 근거(파트너 "진짜 착용한 적이 없는 장비만 new").

    def as_dict(self):
        return {'id': self.id, 'type': self.type, 'name': self.name,
                'x': self.x, 'y': self.y, 'room_id': self.room_id,
                'concealed': self.concealed, 'perception_gate': self.perception_gate}


class Room:
    """방 = id·타입(entrance/exit/standard)·인접그래프를 가진 객체.
    기존 코드 호환: `rx, ry, rw, rh = room` 으로 그대로 언패킹된다(__iter__)."""
    __slots__ = ('id', 'x', 'y', 'w', 'h', 'type', 'neighbours')

    def __init__(self, rid, x, y, w, h, rtype='standard'):
        self.id, self.x, self.y, self.w, self.h = rid, x, y, w, h
        self.type = rtype
        self.neighbours = []          # 인접 방 id들 (connect 그래프)

    def __iter__(self):               # rx,ry,rw,rh 언패킹 호환
        return iter((self.x, self.y, self.w, self.h))

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    def contains(self, x, y):
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h


class Zone:
    """기하 구역(D19 델타①) — 격자에서 읽어낸 공간 단위(방/통로). 출생기록(self.rooms)과 별개:
    rooms=생성기의 내부 골격(배치·스폰·구판 어휘용 존치), zones=스캐너가 **격자만 보고** 재구성한
    세계의 실제 짜임 — 손그림(from_ascii)·생성·미래 UGC 맵을 동일 취급(D20 빌더의 접속면).
    분류 규칙: 2×2 바닥 블록에 속한 칸=방, 나머지 바닥=통로(폭 1 길). 직교 연결 컴포넌트가 구역.
    scan 스위치 켠 판만 만들어진다(기존 게이트 무수정 통과 — D17 장부 스위치 선례)."""
    __slots__ = ('id', 'kind', 'cells', 'x', 'y', 'w', 'h', 'doors', 'junctions', 'deadends')

    def __init__(self, zid, kind, cells):
        self.id, self.kind, self.cells = zid, kind, cells
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        self.x, self.y = min(xs), min(ys)
        self.w, self.h = max(xs) - self.x + 1, max(ys) - self.y + 1
        self.doors = []       # 이 구역에 접한 문 id들
        self.junctions = []   # 갈림길 칸(통로 전용: 직교 이웃 바닥 3+)
        self.deadends = []    # 막다른 칸(통로 전용: 직교 이웃 바닥 1)


BEAR_KR = {'N': '북쪽', 'NE': '북동쪽', 'E': '동쪽', 'SE': '남동쪽',
           'S': '남쪽', 'SW': '남서쪽', 'W': '서쪽', 'NW': '북서쪽'}   # 라벨의 방위 한국어 — brains wire 와 같은 표
BEAR_ORDER = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')   # 열거 순서(시계 방향) — wire 방향 절(order8)과 같은 순서


class Door:
    """문(D19) = 구역과 구역의 경계. 두 형태(D19 정정 2026-07-15):
    ① cell 있는 문 = 격자에 실재하는 문 타일(+) — 벽처럼 빛을 막는다(광학).
    ② cell 없는 문 = 접경 바닥 칸쌍의 트임(개방 아치·손그림 맵 하위호환) — 빛을 안 막는다.
    핑 종점: 봇이 문을 핑하면 '지나 들어서는' 쪽 칸(sides[반대 구역])으로 간다 — 문 하나에
    결정 하나(콜 인플레 방지). 좌표는 엔진만 쥔다(obs 무노출)."""
    __slots__ = ('id', 'zones', 'sides', 'cell')

    def __init__(self, did, za, zb, side_a, side_b, cell=None):
        self.id = did                    # 'd<n>'
        self.zones = (za, zb)            # 잇는 두 구역 id
        self.sides = {za: side_a, zb: side_b}   # 구역별 문턱 대표칸
        self.cell = cell                 # 문 타일 칸(격자 실재) — None=문 없는 트임


class Dungeon:
    def __init__(self, seed=7, depth=1, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1,
                 scan=False, n_potions=0, loops=False, selfstop=False,
                 graves=False, events=False, dry_signal=False, hail=False, wait_verb=False,
                 motion=False, ally_sight=False, social=False, solo=False, n_gear=0,
                 town=False, status=False, rest_verb=False, relations=False, trail=False,
                 objtags=False, floor=False, explore_dirs=False, give_verb=False, bond_verb=False,
                 auto_approach=False, composed_actions=False, skills=False, trpg_combat=False, random_skill=False,
                 ally_doing=False, boss=False):
        # 시드 RNG 스트림 일원화 — 전역 random 대신 전용 인스턴스. 모든 '굴림'은 여기 경유.
        # 마스터 시드 → 깊이별 파생 시드(단층=depth1, 다층 솔기). 같은 시드 → 같은 판.
        # 시그니처 = 계획서 솔기① `Dungeon(master_seed, depth=1)` 와 위치 일치(seed=master_seed).
        self.master_seed, self.depth = seed, depth
        self.rng = random.Random(self._derive_seed(seed, depth))
        self.w, self.h = w, h
        self.turn = 0              # 현재 틱 — 러너가 매 틱 갱신(장부 목격 시점 스탬프용. 판정 무관여)
        self.grid = [[WALL] * w for _ in range(h)]
        self.features = {}         # id -> Feature (출구·보물·… 단일 진실원천). exit/treasures 흡수.
        self.lore = {}             # 로어 DB(D9 '본문') — 러너가 lore.json 로드해 꽂는다. 판정 무접촉(obs 전용).
        self._next_fid = 0
        self._exit_fid = None
        self.monsters = []
        self.traps = []
        self.visited = set()       # 파티가 밟은 칸 (공유 발자국 — 두 영웅 모두의 발걸음)
        self.scan = bool(scan)     # D19 스캐너 스위치 — 기본 꺼짐(기존 게이트 무수정 통과.
                                   #   러너·시나리오가 DUNGEON_SCAN 으로 켠다 — 채택 판정 전 실험층)
        self.loops = bool(loops)   # D20 빌더 스위치 — 기본 꺼짐(기존 verify 비트 동일).
                                   #   러너가 DUNGEON_LOOPS(기본 1)로 켠다(물약 선례) —
                                   #   사슬(외길) 대신 주 고리+막다른 가지(SPD LoopBuilder식 재구현)
        self.selfstop = bool(selfstop)   # D21 자기 관찰 정지 스위치(재회·맴돎) — 기본 꺼짐(기존
                                   #   verify 비트 동일). 러너가 DUNGEON_SELFSTOP(기본 1)로 켠다.
                                   #   scan 장부(zone·seen_cells)가 재료라 scan 판에서만 발화.
        self.dry_signal = bool(dry_signal)   # 무발견 신호(07-24) — 기본 꺼짐(기존 verify 비트
                                   #   동일). 러너가 DUNGEON_DRY(기본 1)로 켠다. scan 장부가 재료.
        self.hail = bool(hail)     # 말 걸림 정지(07-24 D24) — 기본 꺼짐(기존 verify 비트 동일).
                                   #   러너가 DUNGEON_HAIL(기본 1)로 켠다. 배달 규칙은 러너 소유.
        self.wait_verb = bool(wait_verb)   # wait 동사(07-24 D25) — 기본 꺼짐(기존 verify 비트
                                   #   동일). 러너가 DUNGEON_WAIT(기본 1)로 켠다.
        self.motion = bool(motion) # 이동중 표시(07-24 D27, 파트너 발제·간소화) — 기본 꺼짐.
                                   #   러너가 DUNGEON_MOTION(기본 1)로 켠다. 보이는 동료가 걷는
                                   #   중이면 moving 한 깃발만(방향·상태 구분 없음 — 파트너 교정
                                   #   "간단히 (이동중) 하나만". 방향 노출은 다음 판 데이터 보고).
        self.social = bool(social) # 채널 분리(2026-07-26) — 기본 꺼짐. 켜면 말 걸림이 작정을
                                   #   부수지 않고 사교 콜만 연다(걸으면서 대답). 행동 콜은
                                   #   종전대로 '작정 없는 봇'에게만 — 두 채널이 갈린다.
        self.ally_sight = bool(ally_sight)   # 동료 시야 면제(2026-07-26 파트너 발제) — 기본 꺼짐.
                                   #   켜면 **동료만** 시야 반경 안에서 장애물(벽·문)을 무시하고 보인다.
                                   #   왜: 파티가 서로를 못 보는 시간이 44%였고 그중 압도적 다수가
                                   #   거리 2칸(=벽 모퉁이·문 하나 차이)이었다. 문을 넘는 순간 선두가
                                   #   증발해 follow 가 유령 추적→lost→되찾기 셔틀로 굴렀다(실측:
                                   #   문 낀 이동의 단절률 28% vs 그 외 2%, 결정의 50%가 동료 찾기).
                                   #   사람의 인지에 맞춘 것 — 벽 하나 돌아섰다고 일행 위치를 통째로
                                   #   잃지는 않는다(발소리·기척·직전 기억). 09-06 D18 개정으로 옛
                                   #   '파티 감각'(안 보여도 b<char> 핑)은 폐지 — 이 반경 면제만 남는다:
                                   #   반경 안=보임, 밖=말 그대로 사라짐(파트너 지시).
                                   #   ⚠️ **동료 한정** — 몹·피처·구조는 LOS 그대로다(D19 문 광학·
                                   #   매복·인식 매트릭스 대칭 전부 무손상). 반경 밖은 여전히 안 보인다.
        self.solo = bool(solo)     # 솔로 판(2026-07-29 파트너 발제) — 기본 꺼짐. 켜면 **파티라는
                                   #   전제 자체가 빠진다**: 셋은 서로 모르는 별개의 인물로 흩어져
                                   #   출발하고(spawn apart), 서로의 명단을 obs 로 받지 않으며(안 보이는
                                   #   사람 핑 불가 — 09-06 D18 개정 뒤엔 파티도 같다), 각자 계단에 닿으면 혼자
                                   #   내려간다(EXIT_GATHER 면제). 마주치면 그 다음은 자유 — 동행하든
                                   #   갈라서든 엔진이 규정하지 않는다(말·hail·say 는 그대로 열려 있다).
                                   #   왜: 파티 판에서 follow 가 결정의 36~39%(궁수는 67%)를 먹었는데,
                                   #   승리 조건이 '전원 계단에 모이기'라 뭉치는 게 규칙상 최적해였다.
                                   #   혼자면 그 최적해가 사라진다 — 각 캐릭터에게 주관이 있는지를
                                   #   재는 판. 공유 던전(월드 러너)에서 남의 에이전트와 마주치는
                                   #   상황과 같은 모양이라, 여기서 잰 것이 그대로 쓰인다.
                                   #   ⚠️ 서로 공격은 아직 물리적으로 불가(_attack 이 몹만 해소) —
                                   #   '자유'의 범위에서 이것만 빠져 있다는 걸 판 해석 때 감안할 것.
        self.town = bool(town)     # 마을 층(D29, 2026-07-30) — 기본 꺼짐. 켜면 ①전체가 보인다
                                   #   (visible_cells=맵 전부 — 고향은 다 아는 곳, 시야 엔진은 던전
                                   #   전용 긴장 장치) ②계단 어휘가 마을 문맥(던전 입구/복귀).
                                   #   실전은 러너 build_town(from_ascii 손그림)이 켠다.
        self.grave_of = {}         # 묘 피처 id → {char, name}(D22 개정 09-06: 묘 발견=죽음의 사실 태그 재료)
        self.npc_lines = {}        # NPC 이름→인사 한 줄(town.json 데이터 — lore 선례. 판정 무접촉)
        self.npc_gifts = {}        # D32(09-05) 상점 v0: NPC 이름→선물({'potions':1}|{'weapon':'단검'}) — build_town 이 채운다
        self.npc_lines_again = {}  #   두 번째 이후(또는 줄 게 없을 때) 대사 — 정해진 문장만(파트너 확정)
        self.graves = bool(graves) # D22 묘 스위치 — 기본 꺼짐(기존 verify 비트 동일). 러너가
                                   #   DUNGEON_GRAVES(기본 1)로 켠다. 쓰러진 자리에 '~의 묘' 피처.
        self.events = bool(events) # D22 사건층 스위치 — 기본 꺼짐. 러너가 DUNGEON_EVENTS(기본 1).
                                   #   전달층(시야 내 사건 목격 주입, A-3 어휘 확장 — 휘발=다음 결정
                                   #   1회)+기억층(목격한 전사=지속 기억 fallen, 휘발 0).
        self.ally_doing = bool(ally_doing)   # 동료 행동 표시(D27 개정 09-12, 파트너 "동료의 현재 어떤 행동을
                                   #   선택했는지에 대한 상태를 보여주면") — 기본 꺼짐. 러너가 DUNGEON_ALLY_DOING
                                   #   (기본 1)로 켠다. 보이는 동료의 order 를 종류로(doing) — 좌표는 비노출.
        self.status = bool(status) # 상태 태그(D34, 09-06) — 기본 꺼짐(기존 verify 비트 동일). 러너가
                                   #   DUNGEON_STATUS(기본 1)로 켠다. 몹·함정의 특수가 태그를 붙이고
                                   #   (출혈·둔화·중독) 효과는 걸음·굴림에만, 지우기는 휴식(D35)뿐.
        self.rest_verb = bool(rest_verb)   # 휴식(D35, 09-06) — 기본 꺼짐(기존 verify 비트 동일). 러너가
                                   #   DUNGEON_REST(기본 1)로 켠다. 회복이 붙은 wait: 틱마다 HP, 완료 시
                                   #   상태 태그 소거. 파트너 확정 "지우는 조건은 캐릭터 선택지 — 휴식".
        self.relations = bool(relations)   # 관계 장부(D36, 09-06) — 기본 꺼짐(기존 verify 비트 동일).
                                   #   러너가 DUNGEON_RELATIONS(기본 1)로 켠다. 뼈 5종(대화·함께 싸움·
                                   #   기다려 줌·나를 구함·죽을 때 곁)+문턱 초대. 엔진은 살(line)을 안 읽는다.
        self.trail_on = bool(trail)   # 자기 행동 궤적(D38, 09-06) — 기본 꺼짐(기존 verify 비트 동일). 러너가
                                   #   DUNGEON_TRAIL(기본 1)로 켠다. 마지막 view() 이후 일어난 결과를 순서대로
                                   #   다음 결정에 노출(_trail_add). 판정 무접촉 — 자기 경험의 기록·노출뿐.
        self.objtags = bool(objtags)   # 오브젝트 태그(D39, 09-06) — 기본 꺼짐. 러너가 DUNGEON_OBJTAGS(기본 1)로 켠다.
                                   #   나↔오브젝트 상호작용 횟수·마지막 사실을 시야 줄·라벨 접미로(_obj_tag). 판정 무접촉.
        self.explore_dirs = bool(explore_dirs)   # 방향 탐색 열거(D19 개정 4, 09-07) — 기본 꺼짐(기존 verify 비트 동일).
                                   #   러너가 DUNGEON_EXPLORE_DIRS(기본 1)로 켠다. scan 판 메뉴에 트인 방위마다
                                   #   '탐색' 한 줄(target=방위) — 갈 방향의 선택은 에이전트가(D19 ② 원문 복원).
                                   #   목록은 계획기(_explore_ways)와 같은 논리 한 벌(라벨=사실).
        self.floor_on = bool(floor)    # 층 집계·결산(D40 ②, 09-06) — 기본 꺼짐. 러너가 DUNGEON_FLOOR(기본 1)로 켠다.
                                   #   사건 사전으로 자기·목격 사건을 층 단위로 세고(bot['floor']) 층을 떠날 때 얼린다(floors).
        self.give_verb = bool(give_verb)   # 건네기(D47 ②, 09-09) — 기본 꺼짐(기존 verify 비트 동일). 러너가 DUNGEON_GIVE(기본 1)로
                                   #   켠다. 곁(체비셰프≤1)의 동료에게 물약·무기·방어구를 넘기는 즉시 동사 — 메뉴 열거+_give.
        self.bond_verb = bool(bond_verb)   # 친목(D47 ②, 09-09) — 기본 꺼짐. 러너가 DUNGEON_BOND(기본 1)로 켠다. 곁의 동료에게 하는
                                   #   몸짓(형태=응답 form 자유 문구) — 물리 없음, 기록·목격·관계 뼈만. 상대는 안 선다.
        self.auto_approach = bool(auto_approach)   # 조합형: 실행 거리까지 걷고 원래 행동을 한 번 실행
        self.composed_actions = bool(composed_actions)
        self.skills = bool(skills and composed_actions)
        self.trpg_combat = bool(trpg_combat)
        self.random_skill = bool(random_skill)
        self._action_serial = 0
        self._talked = set()       # (쌍, 틱) — 같은 틱 양방향 대화를 한 번으로(note_talk 중복 방지)
        self._ring_target = 0      # loops 판에서 주 고리에 배속할 방 수(_carve_rooms 가 굴림)
        self.rooms = self._carve_rooms()
        self._connect(self.rooms)
        if self.scan:
            self._stamp_doors()    # D19 정정: 관통점에 문 타일(+) — scan 판 전용(기본 격자 무변경)
        self._build_room_graph()   # 방 인접 그래프(connect 체인) — BFS·'방 핑'의 토대
        self._place_targets(n_monsters, n_traps, n_lurkers,   # floors=FLOOR만 → 문 위 배치 자동 회피
                            n_potions,   # 물약 기본 0 = 엔진 직생성 판(기존 verify) 비트 동일.
                                         #   러너가 DUNGEON_POTIONS(기본 1)로 켠다(scan 승격 전 선례)
                            n_gear)      # 장비(07-30)도 같은 규율 — 개수 파라미터·엔진 기본 0
                                         #   (스위치 아님 = from_ascii 명시 초기화 함정 자체가 없다)
        self._assign_room_types()  # entrance/exit/standard 타입 부여 (출구 배치 후)
        self.boss_on = bool(boss)  # D65(09-13): 최심층 보스·워프게이트 — 러너가 depth == DEPTHS 일 때 켠다. 엔진 기본 0(기존 판 비트 동일)
        self.boss = None           #   보스 개체(Monster) — 출구 방(보스룸)에 선다
        self.sealed = False        #   출구(=워프게이트)의 봉인 — 보스가 살아 있는 동안 True(사용하면 result 'locked')
        if self.boss_on:
            self._place_boss()
        self._classify_tiles()     # 각 바닥 칸에 'room'/'corridor' 속성 부여
        self.zones = None
        self.zone_at = {}
        self.doors = {}
        if self.scan:
            self._scan_zones()     # 격자→구역/문 재구성(출생기록 안 읽음 — 델타①)

    @staticmethod
    def _derive_seed(master_seed, depth):
        """마스터 시드 → 깊이별 파생 시드 (결정론적 정수 믹스; hash()/PYTHONHASHSEED 비의존).
        SPD의 master push→derive→pop 패턴을 정수 해시 한 줄로 단순화.
        64비트로 접어 >32비트·음수 시드도 서로 다른 판으로 분산(상위비트 안 버림)."""
        m = master_seed & 0xFFFFFFFFFFFFFFFF       # 음수 → 2의보수 64비트
        m ^= (m >> 32)                             # 상위 32비트를 하위로 폴딩(충돌·앨리어싱 방지)
        x = (m & 0xFFFFFFFF) ^ ((depth + 1) * 0x9E3779B9 & 0xFFFFFFFF)
        x = ((x ^ (x >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
        x = ((x ^ (x >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
        return (x ^ (x >> 16)) & 0x7FFFFFFF

    @classmethod
    def from_layout(cls, layout, seed=7, depth=0):
        """마을 layout(town-layout-v1 — 맵 트랙의 저작 원본, 09-11 파트너 결정 "아스키를 손으로 그릴 필요는 없다, 격자는 있어야 한다")
        → 격자. town_layout.compile_layout 이 제작자가 적은 다섯 필드(막힌 사각형·출입구·출발·던전 입구·NPC id/칸)로 아스키 행을
        만들고(그림에서 벽을 추측하지 않는다), 여기서는 그 행을 from_ascii 에 그대로 넘긴다 — 판정·시야·보행이 손그림 장면과 같다.
        반환 (d, starts). d.layout_result 에 컴파일 결과(npcs id·좌표, dungeon_entry, entrances — border 적용 좌표)를 남긴다."""
        res = TL.compile_layout(layout)
        d, starts = cls.from_ascii(res['map'], seed=seed, depth=depth)
        d.layout_result = res
        d.visual = TL.visual_layer(layout, res)      # 마을 v1 시각 레이어 — level 라인에 실린다(엔진 무시, 클라이언트가 그린다)
        return d, starts

    @classmethod
    def from_ascii(cls, rows, seed=7, depth=1, monsters=None, traps=None, scan=False):
        """디버깅/시나리오 모드(장면 저작, scenario.py 소비): 생성기 대신 손으로 그린
        문자 맵으로 층을 짓는다. 판정·시야·자동보행·스트림은 생성 층과 완전 동일(같은 코드) —
        조립되는 건 세계가 아니라 '장면'이다.
        기호: '#'/공백=벽 · '.'=바닥 · '>'=출구(필수) · '$'보물 · '='상자 · '~'샘 · '!'회복 물약 ·
        ')'=무기(단검) · '['=방어구(가죽 갑옷) ·
        '^'=함정(traps 리스트를 (y,x) 순서로 적용, 기본 spike·hidden) ·
        소문자=몬스터 슬롯(monsters[문자] 템플릿: kind/hp/atk/dmg/ac/state/concealed/target —
        state HUNTING 이면 호출측이 봇 배치 후 last_seen 을 채울 것) ·
        숫자 1~9=봇 출발 자리(맵에선 바닥 — 배치는 호출측, 반환 starts 로 알려줌).
        반환: (dungeon, starts) — starts = {char: (x, y)}."""
        rows = [str(r) for r in rows]
        w, h = max(len(r) for r in rows), len(rows)
        d = cls.__new__(cls)
        d.master_seed, d.depth = seed, depth
        d.rng = random.Random(cls._derive_seed(seed, depth))
        d.w, d.h = w, h
        d.turn = 0
        d.grid = [[WALL] * w for _ in range(h)]
        d.features, d.lore = {}, {}
        d._next_fid, d._exit_fid = 0, None
        d.monsters, d.traps = [], []
        d.visited = set()
        d.rooms = [Room(0, 1, 1, w - 2, h - 2)]   # 단일 방(장면=한 무대) — 그래프 불요
        d.rooms[0].neighbours = []
        d.loops, d._ring_target, d._edges = False, 0, []   # 손그림 맵=생성기 미경유
        d.selfstop = False         # D21 스위치 — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.dry_signal = False       # 무발견 신호 — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.hail = False             # 말 걸림 정지(D24) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.wait_verb = False        # wait 동사(D25) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.motion = False           # 이동중 표시(D27) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.ally_doing = False       # 동료 행동 표시(D27 개정 09-12) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.graves = d.events = False   # D22 스위치(묘·사건층) — 같은 규율(기존 장면 비트 동일)
        d.social = False           # 채널 분리 — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.ally_sight = False       # 동료 시야 면제 — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.solo = False             # 솔로 판(07-29) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.town = False             # 마을 층(D29) — 기본 꺼짐(러너 build_town 이 켠다)
        d.status = False           # 상태 태그(D34) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.rest_verb = False        # 휴식(D35) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.relations = False        # 관계 장부(D36) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.trail_on = False         # 자기 행동 궤적(D38) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.objtags = False          # 오브젝트 태그(D39) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.floor_on = False         # 층 집계·결산(D40) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.explore_dirs = False     # 방향 탐색 열거(D19 개정 4) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.give_verb = d.bond_verb = False   # 건네기·친목(D47 ②, 09-09) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.boss_on, d.boss, d.sealed = False, None, False   # 보스층·워프게이트(D65, 09-13) — 손그림 장면도 기본 꺼짐(호출측이 켠다)
        d.auto_approach = False
        d.composed_actions = False
        d.skills = d.trpg_combat = d.random_skill = False
        d._action_serial = 0
        d._talked = set()
        d.grave_of = {}            # 묘→캐릭터(D22 개정) — __new__ 경유라 명시 초기화
        d.npc_lines = {}           # NPC 인사 사전 — build_town 이 채운다(데이터, 판정 무접촉)
        d.npc_gifts = {}           # D32 상점 v0 — from_ascii 는 __new__ 경유라 여기서도 명시 초기화(함정 계보)
        d.npc_lines_again = {}
                                   #   ⚠️ from_ascii 는 __new__ 경유라 __init__ 을 안 탄다 —
                                   #   새 스위치는 여기 명시 초기화가 필수(D21·D22·솔로 때 밟은 함정.
                                   #   빼먹으면 AttributeError 로 게이트 15개가 한꺼번에 붉어진다)
        starts, mslots, tslots = {}, [], []
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in (WALL, ' '):
                    continue
                if ch == DOOR:             # 문 타일(D19 정정) — 손그림 맵도 문을 그릴 수 있다
                    d.grid[y][x] = DOOR
                    continue
                d.grid[y][x] = FLOOR
                if ch == EXIT:
                    d._exit_fid = d._add_feature('exit', ENT.object_name('exit'), x, y)
                elif ch == TREASURE:
                    d._add_feature('treasure', ENT.object_name('treasure'), x, y)
                elif ch == '=':
                    d._add_feature('chest', ENT.object_name('chest'), x, y)
                elif ch == '~':
                    d._add_feature('fountain', ENT.object_name('fountain'), x, y)
                elif ch == POTION:
                    d._add_feature('potion', ENT.object_name('potion'), x, y)
                elif ch == WEAPON:         # 장비(07-30) — 장면 저작용은 1티어 고정(단검·가죽 갑옷).
                    d._add_feature('weapon', ENT.object_name('dagger'), x, y)     # 상위 티어 장면은 호출측이
                elif ch == ARMOR:                              # _add_feature('weapon','장검',…)로 직접
                    d._add_feature('armor', ENT.object_name('leather_armor'), x, y)
                elif ch == STAIRS_UP:      # 마을(D29) — 위로 오르는 계단(복귀. 하강 '>'와 대칭)
                    d._add_feature('stairs_up', '위로 오르는 계단', x, y)
                elif ch == TRAP:
                    tslots.append((x, y))
                elif ch.isdigit():
                    starts[ch] = (x, y)
                elif ch.islower():
                    mslots.append((ch, x, y))
        if d._exit_fid is None:
            raise ValueError("장면 맵에 출구('>')가 없다 — 층의 필수 피처")
        for i, (sym, x, y) in enumerate(mslots):
            t = dict((monsters or {}).get(sym) or {})
            m = Monster(x, y, kind=t.get('kind', '고블린'), hp=t.get('hp'),      # 장면이 안 준 수치는 정의 기본값(D50)
                        atk=t.get('atk'), dmg=t.get('dmg'),
                        ac=t.get('ac'), mid=i)
            m.state = t.get('state', 'SLEEPING')
            m.concealed = bool(t.get('concealed'))
            m.target = t.get('target')
            d.monsters.append(m)
        tspecs = list(traps or [])
        for i, (x, y) in enumerate(sorted(tslots, key=lambda c: (c[1], c[0]))):
            t = tspecs[i] if i < len(tspecs) else {}
            tr = Trap(x, y, kind=t.get('kind', 'spike'))
            tr.hidden = bool(t.get('hidden', True))
            d.traps.append(tr)
        d._classify_tiles()
        d.scan = bool(scan)        # 스캐너(D19) — 켜면 손그림 맵도 격자에서 방/통로를 읽는다
        d.zones, d.zone_at, d.doors = None, {}, {}   # (단일 방 r0 뭉개짐의 치료 — 델타①)
        if d.scan:
            d._scan_zones()
        return d, starts

    # ── 맵 생성 (로그라이크식 방+통로. loops=D20 고리+가지, 기본=기존 사슬 그대로) ──
    def _carve_rooms(self, n=5):
        if self.loops:
            # D20: 방 수 = 주 고리(6~8) + 가지(4~6). 작은 격자면 들어가는 만큼(고리 우선 배속).
            self._ring_target = self.rng.randint(6, 8)
            n = self._ring_target + self.rng.randint(4, 6)
        rooms = []
        attempts = 0
        while len(rooms) < n and attempts < max(60, n * 15):
            attempts += 1
            rw, rh = self.rng.randint(5, 9), self.rng.randint(3, 5)
            rx = self.rng.randint(1, self.w - rw - 1)
            ry = self.rng.randint(1, self.h - rh - 1)
            # AABB(1칸 간격) 겹침 검사 — 두 방의 폭/높이를 모두 반영(양축 모두 겹쳐야 겹침).
            # (구버전은 기존 방의 w/h만 써서 새 방이 더 크면 겹침을 놓쳤다 → 방 중첩 버그.)
            if any(rx < r.x + r.w + 1 and r.x < rx + rw + 1
                   and ry < r.y + r.h + 1 and r.y < ry + rh + 1 for r in rooms):
                continue
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    self.grid[y][x] = FLOOR
            rooms.append(Room(len(rooms), rx, ry, rw, rh))   # id = 생성 순서(=인덱스)
        return rooms

    def _connect(self, rooms):
        """에지 계획(_plan_edges)을 따라 L자 통로를 조각한다. 에지 = 방 그래프의 단일 진실원천
        (self._edges — _build_room_graph 가 이걸 읽는다. 사슬/고리 공용)."""
        self._edges = self._plan_edges(rooms)
        for a, b in self._edges:
            (x1, y1), (x2, y2) = rooms[a].center, rooms[b].center
            for x in range(min(x1, x2), max(x1, x2) + 1):
                self.grid[y1][x] = FLOOR
            for y in range(min(y1, y2), max(y1, y2) + 1):
                self.grid[y][x2] = FLOOR

    def _plan_edges(self, rooms):
        """어느 방을 어느 방과 이을지(방 id 쌍 목록). 결정론 — rng 무소비.
        기본(사슬): 배치 순 연속쌍 — 기존 판 비트 동일.
        loops(D20, SPD LoopBuilder식 메커니즘 재구현 — 코드 복붙 아님): 처음 배치된
        _ring_target 개 = 주 고리(무게중심 기준 각도 정렬 원환 — 교차 최소의 자연 순서),
        나머지 = 가지(최근접 고리 방에 접속 = 막다른 곁방). 통로가 다른 방을 관통해 생기는
        추가 트임은 허용 — 격자가 유일 인터페이스, 스캐너는 결과만 읽는다(D20 계약)."""
        ring_n = min(self._ring_target, len(rooms)) if self.loops else 0
        if ring_n < 3:                                 # 사슬(기존): 고리가 못 서는 판 포함
            return [(a.id, b.id) for a, b in zip(rooms, rooms[1:])]
        ring = rooms[:ring_n]
        cx = sum(r.center[0] for r in ring) / ring_n
        cy = sum(r.center[1] for r in ring) / ring_n
        order = sorted(ring, key=lambda r: (math.atan2(r.center[1] - cy,
                                                       r.center[0] - cx), r.id))
        edges = [(order[i].id, order[(i + 1) % ring_n].id) for i in range(ring_n)]
        for br in rooms[ring_n:]:                      # 가지: 최근접 고리 방(동률=낮은 id)
            host = min(ring, key=lambda h: (abs(h.center[0] - br.center[0])
                                            + abs(h.center[1] - br.center[1]), h.id))
            edges.append((host.id, br.id))
        return edges

    def _build_room_graph(self):
        """_connect 가 기록한 에지(self._edges)를 양방향 neighbours 로 옮긴다.
        사슬 판=경로(트리), loops 판=고리+가지(사이클 있는 그래프) — 모든 방 연결은 공통."""
        for r in self.rooms:
            r.neighbours = []
        byid = {r.id: r for r in self.rooms}
        for aid, bid in self._edges:
            a, b = byid[aid], byid[bid]
            if b.id not in a.neighbours:
                a.neighbours.append(b.id)
            if a.id not in b.neighbours:
                b.neighbours.append(a.id)

    def _place_targets(self, n_monsters, n_traps, n_lurkers=0, n_potions=0, n_gear=0):
        """출구·보물·몬스터·함정·방콘텐츠를 겹치지 않게 흩뿌린다. 출구·보물 = Feature 로 흡수.
        출구는 가능하면 '방 안'에 둔다(ExitRoom 성립 → Stage 2 기본 핑 목표).
        Stage 3 추가: 매복몹(concealed)·함정 종류 순환(경보 포함)·상자/샘·숨은 보물(도적 인지의 보상)."""
        floors = [(x, y) for y in range(self.h) for x in range(self.w)
                  if self.grid[y][x] == FLOOR]
        self.rng.shuffle(floors)
        room_floors = [c for c in floors if self._room_id_at(*c) is not None]
        ex, ey = room_floors[0] if room_floors else floors[-1]
        self._exit_fid = self._add_feature('exit', ENT.object_name('exit'), ex, ey)
        used = {(ex, ey)}
        pool = [c for c in floors if c not in used]
        for _ in range(min(3, len(pool))):
            x, y = pool.pop()
            self._add_feature('treasure', ENT.object_name('treasure'), x, y)
        for i in range(n_monsters):
            if pool:
                x, y = pool.pop()
                self.monsters.append(Monster(x, y, mid=i))
        for i in range(n_lurkers):            # 매복몹: 봇 obs·맵(봇시야)에 안 나감 → they-ambush 의 몸통
            if pool:
                x, y = pool.pop()
                lurk = Monster(x, y, kind='그림자거미', mid=n_monsters + i)   # 수치 = 정의(D50)
                lurk.concealed = True
                self.monsters.append(lurk)
        kinds = ['spike', 'alarm', 'dart']    # 종류 순환 — 함정 2개 이상이면 경보가 반드시 들어간다
        for i in range(n_traps):
            if pool:
                x, y = pool.pop()
                self.traps.append(Trap(x, y, kind=kinds[i % len(kinds)]))
        if pool:                              # 상자: 열면 보물 2개 or 독침(리스크/보상 도박)
            x, y = pool.pop()
            self._add_feature('chest', ENT.object_name('chest'), x, y)
        if pool:                              # 샘: 마시면 회복 or 오염(가벼운 도박, 대체로 이득)
            x, y = pool.pop()
            self._add_feature('fountain', ENT.object_name('fountain'), x, y)
        if pool:                              # 숨은 보물: 인지(도적)로만 드러난다 — 직업 보상의 몸통
            x, y = pool.pop()
            self._add_feature('treasure', '숨은 보물', x, y,
                              concealed=True, perception_gate=PASSIVE_DC)
        for _ in range(n_potions):            # 회복 물약(07-17): 들고 다니는 확정 회복(PD 문법).
            if pool:                          #   맨 마지막 배치 = 같은 시드의 기존 배치 전부 불변
                x, y = pool.pop()             #   (pool.pop 은 RNG 무소비 — additive 재현성)
                self._add_feature('potion', ENT.object_name('potion'), x, y)
        for i in range(n_gear):               # 장비(07-30): 물약 뒤 = 같은 additive 규율.
            if pool:                          #   순환 배치(RNG 무소비) — 기본 3개면 단검·가죽 갑옷·
                x, y = pool.pop()             #   장검이 깔려 한 층 안에서 '더 좋은 것' 비교가 생긴다
                slot, name = GEAR_CYCLE[i % len(GEAR_CYCLE)]
                self._add_feature(slot, name, x, y)

    def _place_boss(self):
        """D65(2026-09-13 파트너 "5층에 보스몹을 두고 클리어 시 보스룸 뒤로 보물상자와 워프게이트를 설치해서 마을로 이동" →
        "보스를 잡고 워프게이트를 타고 돌아가는 것까지 관찰"): 관찰용 첫 판.
        출구 방 = 보스룸 — 보스(BOSS_KIND)가 출구 바로 곁에 서고, 출구는 **워프게이트**(봉인)가 된다. 보스가 죽으면 봉인이 풀리고
        (_attack → sealed=False, res.unsealed), 게이트 사용 = 마을로 상행(result 'ascend', to_depth 0 — 러너가 0층을 만든다).
        보물상자 하나를 게이트 곁에 둔다(기존 상자 판정: 보물 2 / 독침). ⚠️임시 가정: '보스룸 뒤 별도 방' 규칙은 다음(방 그래프 규칙 필요) ·
        보스는 잠든 채 시작(기습 가능) · 상자는 기존 상자 규칙 그대로."""
        ex, ey = self.exit
        rid = self._room_id_at(ex, ey)
        room = self.rooms[rid] if rid is not None else None
        taken = ({(f.x, f.y) for f in self.features.values()} | {(m.x, m.y) for m in self.monsters}
                 | {(t.x, t.y) for t in self.traps} | {(ex, ey)})
        if room is not None:
            cells = [(x, y) for y in range(room.y, room.y + room.h) for x in range(room.x, room.x + room.w)
                     if self.grid[y][x] == FLOOR and (x, y) not in taken]
        else:
            cells = [(x, y) for y in range(self.h) for x in range(self.w)
                     if self.grid[y][x] == FLOOR and (x, y) not in taken]
        cells.sort(key=lambda c: (max(abs(c[0] - ex), abs(c[1] - ey)), c[1], c[0]))   # 게이트에 가까운 순(결정론)
        if not cells:
            return
        bx, by = cells[0]                                   # 게이트 바로 곁 — 게이트로 가려면 마주친다
        boss = Monster(bx, by, kind=BOSS_KIND, mid=len(self.monsters))
        boss.boss = True
        self.monsters.append(boss)
        rest = [c for c in cells[1:]]
        if rest:
            cx, cy = rest[0]
            self._add_feature('chest', ENT.object_name('chest'), cx, cy)   # 보물상자 — 게이트 곁
        self.boss, self.sealed = boss, True

    def _assign_room_types(self):
        """출구 든 방 = exit, 출구에서 가장 먼 방 = entrance, 나머지 standard.
        (Stage 2: entrance=파티 출발, exit=기본 핑 목표 → 리더 없는 파티 응집.)"""
        for r in self.rooms:
            r.type = 'standard'
        ex, ey = self.exit
        exit_rid = self._room_id_at(ex, ey)
        if exit_rid is not None:
            self.rooms[exit_rid].type = 'exit'
        cands = [r for r in self.rooms if r.id != exit_rid]
        if cands:
            far = max(cands, key=lambda r: abs(r.center[0] - ex) + abs(r.center[1] - ey))
            far.type = 'entrance'

    def _classify_tiles(self):
        """각 바닥 칸을 'room'/'corridor'로 분류 — 엔진이 생성 때 이미 아는 방/통로
        구조를 봇에게 알려주기 위함. _carve_rooms가 만든 방 영역=room, 나머지 바닥
        (_connect가 뚫은 길)=corridor. 봇은 이걸로 '나가는 길(통로)'을 알아본다."""
        room_cells = set()
        for rx, ry, rw, rh in self.rooms:
            for yy in range(ry, ry + rh):
                for xx in range(rx, rx + rw):
                    room_cells.add((xx, yy))
        self.tiletype = {}
        for y in range(self.h):
            for x in range(self.w):
                if self.grid[y][x] == FLOOR:
                    self.tiletype[(x, y)] = 'room' if (x, y) in room_cells else 'corridor'

    # ── 기하 스캐너 (D19 델타① — 격자→구역/문. 출생기록 안 읽음) ──
    def _zone_components(self):
        """격자의 바닥(FLOOR)을 방(2×2 블록)/통로(폭1)로 나눠 직교 연결 컴포넌트로 묶는다 —
        _scan_zones 와 _stamp_doors 가 같은 눈으로 격자를 읽는 공통 심장. 문 타일(+)은 바닥이
        아니므로 컴포넌트가 문에서 끊긴다(문=구역의 경계라는 정의가 격자에서 그대로 성립).
        반환: (comp_at: 칸→컴포넌트 번호, room_cells, comps: [(kind, cells), ...]) — 행 우선 결정론."""
        floors = [(x, y) for y in range(self.h) for x in range(self.w)
                  if self.grid[y][x] == FLOOR]
        fset = set(floors)
        room_cells = set()
        for (x, y) in floors:          # 2×2 블록 소속 검사 — 넉넉한 공간=방, 외길=통로
            for ox, oy in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
                bx, by = x + ox, y + oy
                if {(bx, by), (bx + 1, by), (bx, by + 1), (bx + 1, by + 1)} <= fset:
                    room_cells.add((x, y))
                    break
        comp_at, comps = {}, []
        for c in floors:               # 행 우선 스캔 → 컴포넌트 번호 결정론
            if c in comp_at:
                continue
            comp, queue = {c}, deque([c])
            while queue:               # 같은 분류끼리만 잇는다(방↔통로 경계=문 후보)
                px, py = queue.popleft()
                for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                    n = (px + dx, py + dy)
                    if (n in fset and n not in comp
                            and ((n in room_cells) == (c in room_cells))):
                        comp.add(n)
                        queue.append(n)
            idx = len(comps)
            comps.append(('방' if c in room_cells else '통로', comp))
            for cc in comp:
                comp_at[cc] = idx
        return comp_at, room_cells, comps

    def _stamp_doors(self):
        """D19 정정(2026-07-15): 방↔통로 폭1 관통점에 문 타일(+)을 찍는다 — 문=격자의 실재.
        문은 벽처럼 빛을 막고(_sight_blocked) 바닥처럼 지나간다(walkable) — 개폐 상태 없음.
        찍는 쪽=통로 쪽 칸(문은 방 안 가구가 아니라 벽 구멍을 메우는 물건). 넓은 접경(여러 칸
        트임)은 문이 아니라 개방 아치 — 안 찍는다. 생성 단계(_connect 직후·배치 전)에만 호출 —
        피처·몹은 FLOOR 에만 놓이므로 문 위 배치가 원천 차단된다. scan 판 전용."""
        comp_at, room_cells, _ = self._zone_components()
        pairs = []                     # 서로 다른 컴포넌트의 직교 접경 칸쌍 — 행 우선 결정론
        for y in range(self.h):
            for x in range(self.w):
                if (x, y) not in comp_at:
                    continue
                for dx, dy in ((1, 0), (0, 1)):
                    n = (x + dx, y + dy)
                    if n in comp_at and comp_at[n] != comp_at[(x, y)]:
                        pairs.append((((x, y)), n))
        used = set()
        for i, (a, b) in enumerate(pairs):
            if i in used:
                continue
            key = frozenset((comp_at[a], comp_at[b]))
            cluster, frontier = [i], [i]
            while frontier:            # 같은 컴포넌트쌍 + 체비셰프 인접 = 같은 접경(스캐너와 같은 눈)
                cur = frontier.pop()
                ca, cb = pairs[cur]
                for j, (pa, pb) in enumerate(pairs):
                    if (j in used or j in cluster
                            or frozenset((comp_at[pa], comp_at[pb])) != key):
                        continue
                    if (max(abs(pa[0] - ca[0]), abs(pa[1] - ca[1])) <= 1
                            and max(abs(pb[0] - cb[0]), abs(pb[1] - cb[1])) <= 1):
                        cluster.append(j)
                        frontier.append(j)
            used.update(cluster)
            if len(cluster) != 1:
                continue               # 넓은 트임 = 개방 아치(문 없음 — 빛이 지나간다)
            a, b = pairs[cluster[0]]
            cell = a if a not in room_cells else (b if b not in room_cells else None)
            if cell is None:
                continue
            # 문 배치 규율(D20 — 짧은 통로·삼거리가 흔한 고리 지형에서 필수가 된 규칙 2):
            # ① 문은 문과 어깨를 맞대지 않는다 — 두 칸 통로의 양 끝을 다 찍으면 통로 바닥이
            #    소멸해 스캐너(문=바닥 이웃 정확히 두 구역)가 연결을 못 읽는다(세계가 끊겨 보임).
            # ② 문은 정확히 두 구역 사이에만 선다 — 세 구역이 만나는 관통점은 문이 아니라
            #    통로 바닥으로 남긴다(접경 트임이 연결을 말한다). 스캔 결과를 미리 내다보는
            #    같은 눈의 규칙 — 격자=유일 인터페이스 계약 유지.
            px, py = cell
            neigh = [(px + dx, py + dy) for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))]
            if any(0 <= nx < self.w and 0 <= ny < self.h
                   and self.grid[ny][nx] == DOOR for nx, ny in neigh):
                continue
            comps = {comp_at[n] for n in neigh
                     if n in comp_at and self.grid[n[1]][n[0]] == FLOOR}
            if len(comps) != 2:
                continue
            self.grid[py][px] = DOOR
        # 정착 루프(D20): 스탬프가 통로를 조각내면 구역 구성이 스탬프 시점과 달라질 수 있다
        # (연쇄 효과 — 위 규율 2는 시점 예측이라 전부는 못 막는다). 스캔과 같은 눈으로 재검해
        # '정확히 두 구역 사이'가 깨진 문을 바닥으로 되돌린다. 되돌리기만 하므로 수렴 보장,
        # 종료 상태 = 남은 문 전부가 스캐너에게 유효한 문 → 존 그래프 연결성 = 지형 연결성.
        while True:
            comp_now, _, _ = self._zone_components()
            reverted = False
            for y in range(self.h):
                for x in range(self.w):
                    if self.grid[y][x] != DOOR:
                        continue
                    zs = {comp_now.get((x + dx, y + dy))
                          for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))} - {None}
                    if len(zs) != 2:
                        self.grid[y][x] = FLOOR
                        reverted = True
            if not reverted:
                break

    def _scan_zones(self):
        """격자만 읽어 구역(Zone)·문(Door)을 재구성한다 — 스캐너의 토대.
        ① 분류: 2×2 바닥 블록에 속한 칸=방 후보, 나머지 바닥=통로(폭 1 길).
        ② 구역: 같은 분류의 직교 연결 컴포넌트. id=스캔 순서(행 우선) — 방 r0.., 통로 c0..
        ③ 문: (a) 문 타일(+) — 직교 이웃 바닥이 정확히 두 구역이면 그 사이의 문(격자 실재, 광학 차단)
              (b) 서로 다른 구역의 바닥이 직교로 맞닿는 접경 칸쌍의 묶음(문 없는 트임 —
                 개방 아치·손그림 맵 하위호환. 빛은 안 막는다)
        ④ 통로 사건: 갈림길(직교 바닥 이웃 3+)·막다른 곳(이웃 1).
        전부 결정론(굴림 없음)·읽기 전용 — 세계를 바꾸지 않는다(시야 엔진 파이프라인 ②구조 조회의 재료)."""
        comp_at, room_cells, comps = self._zone_components()
        fset = set(comp_at)
        self.zones, self.zone_at, self.doors = {}, {}, {}
        nr = nc = 0
        for kind, comp in comps:
            if kind == '방':
                zid, nr = 'r%d' % nr, nr + 1
            else:
                zid, nc = 'c%d' % nc, nc + 1
            z = Zone(zid, kind, frozenset(comp))
            self.zones[zid] = z
            for cc in comp:
                self.zone_at[cc] = zid
        nd = 0
        # 문(a) = 문 타일(+): 직교 이웃 바닥의 구역이 정확히 둘이면 그 둘을 잇는 문.
        # 외짝(+한쪽뿐)·삼거리 문은 구조 명사 없이 광학·통행만 남는다(손그림 맵 관용).
        for y in range(self.h):
            for x in range(self.w):
                if self.grid[y][x] != DOOR:
                    continue
                sides = {}
                for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                    zn = self.zone_at.get((x + dx, y + dy))
                    if zn is not None:
                        sides.setdefault(zn, []).append((x + dx, y + dy))
                if len(sides) != 2:
                    continue
                za, zb = sorted(sides)
                door = Door('d%d' % nd, za, zb, min(sides[za]), min(sides[zb]),
                            cell=(x, y))
                nd += 1
                self.doors[door.id] = door
                self.zones[za].doors.append(door.id)
                self.zones[zb].doors.append(door.id)
        # 문(b) = 구역 접경 칸쌍 → (구역쌍)별로 인접 묶음(넓은 문턱=한 문, 두 군데 접점=문 둘)
        pairs = []                     # (칸A, 칸B, 구역A, 구역B) — 행 우선 발견 순서
        for y in range(self.h):        # 행 우선 유지 — 문 번호가 구판(문 타일 없는 맵)과 동일해야
            for x in range(self.w):    #   사전등록 미로의 문 id(d0..d4)가 흔들리지 않는다
                if (x, y) not in fset:
                    continue
                for dx, dy in ((1, 0), (0, 1)):
                    n = (x + dx, y + dy)
                    if n in fset and self.zone_at[n] != self.zone_at[(x, y)]:
                        a, b = (x, y), n
                        pairs.append((a, b, self.zone_at[a], self.zone_at[b]))
        used = set()
        for i, (a, b, za, zb) in enumerate(pairs):
            if i in used:
                continue
            cluster, frontier = [i], [i]
            while frontier:            # 같은 구역쌍 + 양쪽 다 체비셰프 인접이면 같은 문턱
                cur = frontier.pop()
                ca, cb = pairs[cur][0], pairs[cur][1]
                for j, (pa, pb, pza, pzb) in enumerate(pairs):
                    if j in used or j in cluster or {pza, pzb} != {za, zb}:
                        continue
                    if (max(abs(pa[0] - ca[0]), abs(pa[1] - ca[1])) <= 1
                            and max(abs(pb[0] - cb[0]), abs(pb[1] - cb[1])) <= 1):
                        cluster.append(j)
                        frontier.append(j)
            used.update(cluster)
            side_a = min(pairs[j][0] for j in cluster)   # 구역별 문턱 대표칸(결정론)
            side_b = min(pairs[j][1] for j in cluster)
            door = Door('d%d' % nd, za, zb, side_a, side_b)
            nd += 1
            self.doors[door.id] = door
            self.zones[za].doors.append(door.id)
            self.zones[zb].doors.append(door.id)
        for z in self.zones.values():  # 통로 사건: 갈림길·막다른 곳(이동 결정이 흐려지는 명사만)
            if z.kind != '통로':
                continue
            for (x, y) in sorted(z.cells):
                deg = sum(1 for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))
                          if (x + dx, y + dy) in fset)
                if deg >= 3:
                    z.junctions.append((x, y))
                elif deg == 1:
                    z.deadends.append((x, y))

    @staticmethod
    def _at_label(z, x, y):
        """구역 안 상대 위치 — 사람의 공간 언어("서쪽 가장자리", 방위각 아님). bbox 3등분."""
        bx = 1 if z.w < 3 else (0 if (x - z.x) * 3 < z.w else (2 if (x - z.x) * 3 >= 2 * z.w else 1))
        by = 1 if z.h < 3 else (0 if (y - z.y) * 3 < z.h else (2 if (y - z.y) * 3 >= 2 * z.h else 1))
        v = ('북', '', '남')[by]
        h = ('서', '', '동')[bx]
        if v and h:
            return '%s%s 구석' % (v, h)
        if v or h:
            return '%s쪽 가장자리' % (v or h)
        return '중앙'

    # ── 피처 / 방 그래프 헬퍼 ───────────────────────────────────
    def _add_feature(self, ftype, name, x, y, concealed=False, perception_gate=0):
        fid = self._next_fid
        self._next_fid += 1
        self.features[fid] = Feature(fid, ftype, name, x, y,
                                     room_id=self._room_id_at(x, y),
                                     concealed=concealed, perception_gate=perception_gate)
        return fid

    def _alloc_fid(self):
        """D57(09-12 파트너 "단검을 엔티티화하면"): 장비 개체 번호 — 손에서 태어나는 장비(NPC 선물)·층 전이 입양도 여기서."""
        fid = self._next_fid
        self._next_fid += 1
        return fid

    def _put_gear(self, slot, g, x, y, wearer=None):
        """슬롯의 장비 개체를 **같은 번호**로 바닥에 되돌린다(D57). 번호 없는 옛 dict·충돌이면 새 번호. 착용 이력(worn) 이어받음.
        판 51828: 내려놓을 때마다 새 번호(f13→f64)가 붙어 캐릭터가 '새 단검'으로 읽었다 — 세계가 개체를 새로 찍은 것이 뿌리."""
        fid = g.get('id')
        if fid is None or fid in self.features:
            fid = self._alloc_fid()
        f = Feature(fid, slot, g['name'], x, y, room_id=self._room_id_at(x, y))
        f.worn = set(g.get('worn') or ()) | ({wearer} if wearer else set())   # 내려놓는 이는 입고 있었다
        self.features[fid] = f
        return fid

    def adopt_gear(self, bot):
        """이 던전 밖에서 온 슬롯 장비(층 전이 이월·외부 시트)에 이 층의 새 번호를 준다(D57 — 번호는 층-로컬, 몹·피처와 같은 자)."""
        for slot in ('weapon', 'armor'):
            g = bot.get(slot)
            if g:
                g['id'] = self._alloc_fid()

    def _room_id_at(self, x, y):
        for r in self.rooms:
            if r.contains(x, y):
                return r.id
        return None

    # ── 피처 조회 / 호환 접근자 (exit·treasures = features 파생) ──
    @property
    def exit(self):
        f = self.features.get(self._exit_fid)
        return (f.x, f.y) if f else None

    @property
    def treasures(self):
        return {(f.x, f.y) for f in self.features.values() if f.type == 'treasure'}

    def feature_at(self, x, y, ftype=None):
        for f in self.features.values():
            if f.x == x and f.y == y and (ftype is None or f.type == ftype):
                return f
        return None

    # ── 점유/지형 조회 ──────────────────────────────────────────
    def monster_at(self, x, y):
        return next((m for m in self.monsters if m.alive and m.x == x and m.y == y), None)

    def room_of(self, x, y):
        """(x,y)가 속한 방 객체를 돌려준다(없으면 None = 통로/교차로). 봇 '방 한눈 인식'용."""
        rid = self._room_id_at(x, y)
        return self.rooms[rid] if rid is not None else None

    def room_info(self, cx, cy):
        """봇이 선 방을 '한눈에' 요약한다 — 사람이 방에 들어서면 즉시 보듯이.
        방 안 보물/출구/몬스터 유무 + 출입구(방 밖으로 통하는 바닥)의 방향·방문 여부."""
        room = self.room_of(cx, cy)
        if not room:
            return {'in_room': False}
        rx, ry, rw, rh = room
        treasures = self.treasures
        ex, ey = self.exit

        def bearing(tx, ty):
            h = 'E' if tx > cx else ('W' if tx < cx else '')
            v = 'S' if ty > cy else ('N' if ty < cy else '')
            return (v + h) or '-'

        has_t = any((x, y) in treasures
                    for y in range(ry, ry + rh) for x in range(rx, rx + rw))
        has_e = (rx <= ex < rx + rw and ry <= ey < ry + rh)
        has_m = any(m.alive and rx <= m.x < rx + rw and ry <= m.y < ry + rh
                    for m in self.monsters)
        # 출입구 = 방 경계 바로 밖의 바닥 칸 (방을 나가는 길)
        doors, seen = [], set()
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                for ddx, ddy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                    ox, oy = x + ddx, y + ddy
                    if rx <= ox < rx + rw and ry <= oy < ry + rh:
                        continue                       # 아직 방 안
                    if not (0 <= ox < self.w and 0 <= oy < self.h):
                        continue
                    if self.grid[oy][ox] != FLOOR or (ox, oy) in seen:
                        continue
                    seen.add((ox, oy))
                    doors.append({'dir': bearing(ox, oy), 'new': (ox, oy) not in self.visited})
        return {'in_room': True, 'size': '%dx%d' % (rw, rh),
                'has_treasure': has_t, 'has_exit': has_e, 'has_monster': has_m,
                'doors': doors}

    def walkable(self, x, y, bots, ally_pass=False):
        """봇이 들어갈 수 있나. 벽·다른 봇·몬스터가 막으면 못 간다(몬스터는 공격 대상).
        탈출(won)한 봇은 던전을 떠났으므로 아무것도 막지 않는다(출구 칸 막힘 방지).
        설계 결정: concealed(매복) 몹도 막는다 — 그 칸에 뭔가 '물리적으로 실재'하므로 경로가 막히는 건
        세계의 사실이다(시야-온리는 obs 층의 계약). 외길 봉쇄는 explore→출구 best_effort가 봇을 몹
        직전 칸까지 안내→매복 일격 발화로 자연 해소된다(verify_stage3 300시드 무교착 실측).
        ally_pass(D18 개정 07-17, 교대): 동료는 길을 막지 않는다 — 걸어 들어가면 서로 자리를
        바꾸므로(PD 문법, _step_order) 경로 계산에선 통과 가능. 몹 차단은 불변(교대는 파티의 예의)."""
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False
        if self.grid[y][x] == WALL:
            return False
        if not ally_pass and any(b['x'] == x and b['y'] == y
                                 and b['alive'] and not b['won'] for b in bots):
            return False
        if self.monster_at(x, y):
            return False
        f = self.feature_at(x, y)
        if f and f.type == 'npc':          # NPC(D29) — 사람이 서 있는 칸은 몸이 막는다(밟고 지나갈
            return False                   #   수 없다). 말은 곁에서(interact 맨해튼 1) 건넨다
        return True

    def tile(self, x, y, spectator=False):
        """칸 글리프. 봇 시야(기본): 숨은 것(concealed 몹·피처, hidden 함정)은 바닥처럼 보인다.
        관전자(spectator=True, render 전용): 숨은 적 'm'·숨은 보물 '*' 로 노출 = 극적 아이러니
        (봇은 모르는 걸 관객은 안다 — 매복을 지켜보는 재미)."""
        m = self.monster_at(x, y)
        if m:
            if not m.concealed:
                return MONSTER
            if spectator:
                return LURKER
        if (x, y) == self.exit:
            return EXIT
        f = self.feature_at(x, y)
        if f and f.type == 'treasure':
            if not f.concealed:
                return TREASURE
            if spectator:
                return HIDDEN
        if f and f.type == 'chest' and not f.concealed:
            return CHEST
        if f and f.type == 'fountain' and not f.concealed:
            return FOUNTAIN
        if f and f.type == 'potion' and not f.concealed:
            return POTION
        if f and f.type == 'weapon' and not f.concealed:   # 장비(07-30): 바닥의 무기/방어구
            return WEAPON
        if f and f.type == 'armor' and not f.concealed:
            return ARMOR
        if f and f.type == 'stairs_up':           # 마을(D29): 위로 오르는 계단·NPC — 숨김 개념 없음
            return STAIRS_UP
        if f and f.type == 'npc':
            return NPC
        if f and f.type == 'grave':               # 묘(D22) — 숨김 개념 없음(죽음은 공공연한 사실)
            return GRAVE
        for t in self.traps:
            if (t.x, t.y) == (x, y) and not t.hidden:
                return TRAP            # 드러난 함정만 보인다. 숨은 것은 바닥처럼.
        return self.grid[y][x]

    # ── 길찾기 (BFS, 8연결, 대각선 코너컷 금지) ─────────────────
    def _terrain_dist_from(self, tx, ty):
        """목표(tx,ty)에서 *지형만*(벽만 막고 몹/봇은 통과) BFS한 거리맵. best_effort 근접 판단용 —
        외길을 몹이 막아 못 가도, 봇을 '봉쇄 직전 칸'(몹과 직교 인접)으로 안내해 교전을 유발한다.
        ⚠️ 대각 코너컷 금지는 여기도 동일 적용 — 이동 규칙과 거리맵 규칙이 어긋나면 벽 모서리
        X자 틈으로 '지형상 가깝다'는 불가능 거리가 나와 best_effort가 거짓 제자리([])를 낸다(seed242 실측)."""
        def open_(x, y):
            return 0 <= x < self.w and 0 <= y < self.h and self.grid[y][x] != WALL
        if open_(tx, ty):
            starts = [(tx, ty)]
        else:                                       # 목표가 벽/맵밖이면 직교 인접 floor에서 시작
            starts = [(tx + dx, ty + dy) for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))
                      if open_(tx + dx, ty + dy)]
        dist = {s: 0 for s in starts}
        q = deque(starts)
        while q:
            cx, cy = q.popleft()
            for dx, dy in MOVES.values():
                nx, ny = cx + dx, cy + dy
                if not open_(nx, ny) or (nx, ny) in dist:
                    continue
                if dx and dy and not (open_(cx + dx, cy) and open_(cx, cy + dy)):
                    continue                        # 대각 코너컷 금지(이동 규칙과 일치)
                dist[(nx, ny)] = dist[(cx, cy)] + 1
                q.append((nx, ny))
        return dist

    def path_to(self, sx, sy, tx, ty, bots, best_effort=False, avoid_traps=True, goals=None):
        """(sx,sy)→(tx,ty) 최단 경로. 이동=8연결(대각선 코너컷 금지), walkable 재사용.
        동료는 장애물이 아니다(D18 개정 07-17, ally_pass): 경로가 동료 칸을 지나면 실행 때
        서로 자리를 바꾼다(교대, _step_order) — 외길의 동료가 '이동 선택지 소멸'을 만들던 결함 치료.
        목표가 못 들어가는 칸(몹·가구)이면 → 목표의 **직교 인접** walkable 칸들을
        목표집합으로 BFS, 그중 *도달 가능한 가장 가까운* 칸까지 길을 낸다.
          · 직교 인접만: 전투·상호작용은 맨해튼 1(직교)이라(_attack/monster_turn) 대각 접근은 무용.
          · '도달 가능한' 가장 가까운 칸: 맨해튼 최단 한 칸만 고르면 그 칸이 막혔을 때 거짓 '도달불가'.
          · avoid_traps(Stage 3): '드러난' 미발동 함정 칸은 피해서 길을 낸다(인지의 보상 = 우회).
            우회로가 없으면 함정 경유 허용으로 1회 재시도(외길 봉쇄 방지) — 그 땐 알고 건너니
            _enter_cell 에서 조심 보너스(CAREFUL_BONUS)를 받는다.
        반환: 시작 제외, 밟을 칸 목록(목표/접근칸=마지막). 도달불가/이미도착이면 []. (Stage2 자동보행용)"""
        tblock = ({(t.x, t.y) for t in self.traps if not t.hidden and not t.sprung}
                  if avoid_traps else set())
        supplied_goals = goals
        if goals is not None:                    # 자동 접근: 행동을 실행할 수 있는 칸 집합까지 최단 보행
            goals = set(goals)
        elif self.walkable(tx, ty, bots):           # 종점만은 ally_pass 없이 — 동료가 선 칸을 '목적지'로
            goals = {(tx, ty)}                    #   삼지 않는다(교대는 지나가는 예의지 도착지가 아니다.
        else:                                     #   동행 목표 칸까지 파고들면 리더와 교대하는 헛짓).
            goals = {(tx + dx, ty + dy) for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))
                     if self.walkable(tx + dx, ty + dy, bots)}
        if not goals or (sx, sy) in goals:
            return []
        prev = {(sx, sy): None}
        q = deque([(sx, sy)])
        reached = None
        while q:
            cx, cy = q.popleft()
            if (cx, cy) in goals:                 # BFS=거리순 → 첫 도달이 가장 가까운 '도달가능' 목표
                reached = (cx, cy); break
            for dx, dy in MOVES.values():         # 결정론 순서(삽입순) → 재현 가능 경로
                nx, ny = cx + dx, cy + dy
                if (nx, ny) in prev or not self.walkable(nx, ny, bots, ally_pass=True):
                    continue
                if (nx, ny) in tblock and (nx, ny) not in goals:
                    continue                      # 드러난 함정은 밟지 않는 경로로(목표 자신이면 허용)
                if dx and dy and not (self.walkable(cx + dx, cy, bots, ally_pass=True)
                                      and self.walkable(cx, cy + dy, bots, ally_pass=True)):
                    continue                      # 대각선 코너컷 금지(양 직교칸 둘 다 뚫려야)
                prev[(nx, ny)] = (cx, cy)
                q.append((nx, ny))
        if reached is None:
            if tblock:                            # 함정 우회로가 없다 → 함정 경유 허용으로 재시도(외길 봉쇄 방지)
                return self.path_to(sx, sy, tx, ty, bots,
                                    best_effort=best_effort, avoid_traps=False, goals=supplied_goals)
            if best_effort:                       # 도달불가(몹 봉쇄 등) → 목표에 *지형상* 가장 가까운 도달가능 칸까지
                gdist = self._terrain_dist_from(tx, ty)   # 벽만 막는 거리맵(몹 무시) → 봉쇄몹 직전까지 안내
                cand = [c for c in prev if c in gdist]
                if not cand:                      # 목표가 벽으로 진짜 단절(접근 무의미) → 제자리
                    return []
                reached = min(cand, key=lambda c: (gdist[c], c))
                if reached == (sx, sy):           # 시작칸이 이미 가장 가까움 → 제자리(헛걸음/진동 방지)
                    return []
            else:
                return []
        path, cur = [], reached
        while cur != (sx, sy):
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    # ── 관측 (봇에게 줄 obs) ────────────────────────────────────
    def _can_hit(self, bot, mon):
        """지금 이 몹을 칠 수 있는가 — obs 의 in_range 와 _attack 판정의 **단일 진실원천**.
        (두 곳이 갈리면 '메뉴에 떴는데 too_far' 같은 거짓말이 캐릭터에게 간다.)

        · 사거리 = 시트 atk_range(맨해튼). 근접 1 = 직교 인접(종전 그대로), 궁수 2 = 직교 2칸
          + 대각 1칸. 8방향 이동 vs 4방향 전투의 기존 비대칭은 건드리지 않는다.
        · 인접(1)은 사선을 안 본다 — 붙어 있는데 벽이 가릴 수는 없다.
        · 2칸 이상은 사선이 필요하다: 벽·문이 막으면 못 쏜다(문 뒤 몹 저격 금지 — D19 광학과
          같은 눈). **동료는 사선을 막지 않는다**(파트너 확정: "동료 뒤에서 공격해도 좋다")
          — _sight_blocked 가 원래 벽·문만 보므로 따로 할 일이 없다."""
        d = abs(mon.x - bot['x']) + abs(mon.y - bot['y'])
        if d < 1 or d > int(bot.get('atk_range') or 1):
            return False
        if d == 1:
            return True
        return not self._sight_blocked(bot['x'], bot['y'], mon.x, mon.y)

    def _ally_seen(self, bot, other, seen):
        """동료가 보이는가 — sights.bots 와 party.visible 의 **단일 판정처**(두 곳이 갈리면
        '목록엔 있는데 명단엔 안 보임' 같은 모순이 obs 에 실린다).

        기본(ally_sight=False): 시야 격자 그대로 — 벽·문이 막으면 안 보인다.
        켜면: 시야 **반경** 안이면 장애물 무관하게 보인다. 동료 한정이며 몹·피처는 그대로다.
        근거는 실측 — 파티가 서로 못 보는 시간이 44%였고 그 압도적 다수가 거리 2칸이었다.
        벽 하나 돌아섰다고 일행을 통째로 잃는 건 사람의 인지가 아니다(발소리·기척·직전 기억).
        반경 밖은 여전히 잃는다 — '흩어짐의 비용'은 거리로 남는다."""
        if (other['x'], other['y']) in seen:
            return True
        if not self.ally_sight:
            return False
        return max(abs(other['x'] - bot['x']), abs(other['y'] - bot['y'])) <= SIGHT

    def _sight_blocked(self, cx, cy, tx, ty):
        """(cx,cy)↔(tx,ty) 직선 '중간'에 벽·문이 있으면 시야가 가린다. 타겟 자신이 벽/문이면 보인다(중간만 막는다).
        문(+)=벽과 같은 불투명(D19 정정 — SPD 닫힌 문 광학). 문 '위'에 서면 중간에 문이 없으므로
        양쪽이 다 보인다 — 문턱에 올라서는 순간이 곧 다음 공간의 개시(별도 특례 없이 성립).
        ⚠️ 끝점 정규화로 *대칭* 보장: Bresenham 한 방향 추적은 코너 근처 err 타이브레이크로
        _sight_blocked(A,B)≠_sight_blocked(B,A)가 될 수 있다(80시드서 2.53% 실측). 항상 같은 방향으로
        추적해 대칭화 — 인식 매트릭스 공정성('몹이 봇 봄 ⟺ 봇이 몹 봄')의 토대."""
        if (cx, cy) > (tx, ty):                  # 끝점 순서 정규화 → 인자 순서 무관 동일 경로
            cx, cy, tx, ty = tx, ty, cx, cy
        x, y = cx, cy
        dx, dy = abs(tx - cx), abs(ty - cy)
        sx = 1 if cx < tx else -1
        sy = 1 if cy < ty else -1
        err = dx - dy
        while (x, y) != (tx, ty):
            e2 = 2 * err
            if e2 > -dy:
                err -= dy; x += sx
            if e2 < dx:
                err += dx; y += sy
            if (x, y) == (tx, ty):
                break                       # 타겟 도달 — 타겟(첫 벽/문 가능)은 보인다
            if self.grid[y][x] in (WALL, DOOR):
                return True                 # 중간에 벽·문 → 그 너머는 가려짐
        return False

    def _bearing(self, dx, dy):
        """8방위 — **각도 기준**(09-08 D45, 파트너 "방위를 좀 더 세부적으로 잡자"): 45° 부채꼴, 경계 22.5°. 옛 부호 기준은
        동쪽 10칸·북쪽 1칸(거의 정동)도 'NE' 였다. 0·0 은 '-'(발밑). 시야·장부·문·트인 길·탐색 방위·리모컨·목격이 전부
        이 한 함수를 쓴다(문장↔메뉴 1:1 은 그대로). 화면 y 는 아래로 자라므로 북 = −dy."""
        if dx == 0 and dy == 0:
            return '-'
        ang = math.degrees(math.atan2(-dy, dx)) % 360.0
        return ('E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE')[int(((ang + 22.5) % 360.0) // 45)]

    def visible_cells(self, cx, cy, r=SIGHT):
        """(cx,cy)이 지금 보는 칸 집합 — (2r+1)² 중 벽에 안 가린 칸(LOS). 대칭(A↔B).
        마을(D29): 전체가 보인다 — 고향은 다 아는 곳(파트너 확정 07-30). 여기가 유일한 조임목이라
        obs·메뉴·목격·say 배달·정지 전부가 한 줄로 따라온다. 시야 엔진=던전 전용 긴장 장치."""
        if self.town:
            return {(x, y) for y in range(self.h) for x in range(self.w)}
        cells = set()
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < self.w and 0 <= y < self.h and not self._sight_blocked(cx, cy, x, y):
                    cells.add((x, y))
        return cells

    def view(self, bot, bots, r=SIGHT):
        """봇 obs = '지각된 오브젝트 목록'(시야-온리). 칸 운전 어휘(frontier/directions/room_info) 폐기.
        v3: 출구도 beacon 아님 — 보일 때만 등장(안 보이면 sights['exit']=None).
        ways = 지금 보이는 '미지로 트인 출입구'(탐색 폴백 대상). ascii_view 는 관전/그라운딩용.
        2b: 관측 시점에 _perceive(=FOV 내 비은닉 몹을 aware_of에 등록) — think-tick에도 봇 인지가
        최신이라야 매트릭스(몹이 봇 매복했나)가 공정. 인지=시야(굴림 아님)."""
        self._perceive(bot, r)
        cx, cy = bot['x'], bot['y']
        seen = self.visible_cells(cx, cy, r)
        if self.scan:                          # D19: 결정 시점의 내 구역 = '들어와 본 곳'(스폰 방 포함)
            zid0 = self.zone_at.get((cx, cy))  #   — 처음 방 정지(step_order)의 기준 장부
            if zid0 is not None:
                bot.setdefault('zones_entered', set()).add(zid0)
        rows = []
        for dy in range(-r, r + 1):
            line = ''
            for dx in range(-r, r + 1):
                x, y = cx + dx, cy + dy
                if dx == 0 and dy == 0:
                    line += '@'
                elif (x, y) not in seen:
                    line += ' '                      # 미지(맵밖·벽뒤)
                elif self.monster_at(x, y) and not self.monster_at(x, y).concealed:
                    line += MONSTER                  # 숨은(매복) 몹은 봇 눈에 안 보인다 — tile()도 바닥 처리
                else:
                    other = next((b for b in bots if b['x'] == x and b['y'] == y
                                  and b['alive'] and not b['won']), None)
                    line += other['char'] if other else self.tile(x, y)
            rows.append(line)

        def bear(ox, oy):
            return {'bearing': self._bearing(ox - cx, oy - cy),
                    'dist': max(abs(ox - cx), abs(oy - cy)),
                    'adj': abs(ox - cx) + abs(oy - cy) <= 1}     # adj=직교인접 or 발밑(dist0) — 봇은 계단·
                    # 상자 '위'에 서기도 한다(_interact도 dist≤1 허용). ==1이면 발밑 피처를 못 만지는 모순.
        known = bot.get('known')   # 도감 게이팅(D9 '주입'=obs 조인). None=끄기(하위호환 솔기 —
                                   #   기존 verify/헤들리스 하네스 무변경 통과). 러너가 set 을 꽂아 켠다.
        book = bot.get('book')     # D53 원장 기록 {종키: {n, deep?}} — 러너가 발급기의 dict 를 공유로 꽂는다.
                                   #   None(옛 하네스·게이트) = 옛 2층(모름/앎): 등재 즉시 본문 전체.

        def _knowledge(kind_key, entry):
            """아는 종 = lore 주입, 모르는 몹 = 정체 은닉(낯선 짐승). 시야-온리 불변 —
            무엇이 '보이는가'는 그대로, 바뀌는 건 그것을 '무엇이라 아는가'뿐.
            획득은 발급기(bestiary.py, 스트림 소비자) 소관 — 도감에 있어도 매복은 당한다(D9).
            D53(09-12, 메모 §2-2·§2-5·§2-6): 해금 조건(정의 knowledge.unlock)이 있는 종은 심층 전엔 brief 한 줄 +
            진행도(deep_progress{event, n, need})만, 해금 뒤 본문(lore). 조건 없는 종(함정·상자·샘)은 옛 2층 그대로."""
            if known is None:
                return entry
            if kind_key not in known:
                if kind_key.startswith('monster:'):
                    entry['kind'] = UNKNOWN_BEAST          # 처음 겪는 종 — 이름·습성 미상
                return entry
            info = self.lore.get(kind_key) or {}
            rule = info.get('unlock')
            rec = (book or {}).get(kind_key) or {}
            if rule and book is not None and not rec.get('deep'):
                if info.get('brief'):
                    entry['lore'] = info['brief']          # 처음 알게 된 한 줄(메모 §2-2 [제안] "고블린: 겁 많은 소형 마물")
                entry['deep_progress'] = {'event': rule['event'], 'n': int(rec.get('n', 1)), 'need': int(rule['count'])}
            elif info.get('lore'):
                entry['lore'] = info['lore']
            note = (rec.get('note') or {}).get('text') if isinstance(rec.get('note'), dict) else None
            if note:                                       # D55 캐릭터 인식 — 사실(lore)과 다른 칸(메모 §2-5 [제안] "도감: / 생각:")
                entry['note'] = note
            return entry

        def _book_invite():
            """D55 대기 중인 인식 초대 — 원장 항목의 due(발급기가 해금·갱신 문턱에 붙임). 결정당 하나(종키 순).
            {key, name, why: deep|review, n, line?} — line 은 기존 인식(갱신 초대 때 보여주고 고칠 기회)."""
            if not book:
                return None
            for key in sorted(book):
                rec = book[key]
                if isinstance(rec, dict) and rec.get('due') in ('deep', 'review'):
                    info = self.lore.get(key) or {}
                    inv = {'key': key, 'name': info.get('name') or key.split(':', 1)[-1],
                           'why': rec['due'], 'n': int(rec.get('n', 1))}
                    line = (rec.get('note') or {}).get('text') if isinstance(rec.get('note'), dict) else None
                    if line:
                        inv['line'] = line
                    return inv
            return None
        binv = _book_invite()

        mons = [_knowledge('monster:' + m.kind,
                           {'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state,
                            'aware': (m.state == 'HUNTING' and m.target == bot['char']),  # 이 몹이 *날* 노린다(매트릭스 신호)
                            'hp': m.hp, **bear(m.x, m.y),
                            **({'status': sorted(m.skill_status)} if self.skills and getattr(m, 'skill_status', None) else {}),
                            # 지금 칠 수 있는가(2026-07-26). adj(맨해튼≤1)와 **다른 자**다 —
                            # adj 는 계단·상자 접촉에도 쓰이는 공용 필드라 사거리를 얹으면 안 된다.
                            **({'in_range': True} if self._can_hit(bot, m) else {})})
                for m in self.monsters
                if m.alive and not m.concealed and (m.x, m.y) in seen]
        feats = [_knowledge('feature:' + f.type,
                            {'id': 'f%d' % f.id, 'type': f.type, 'name': f.name,
                             'visited': (f.x, f.y) in self.visited, **bear(f.x, f.y),
                             **self._obj_tag_obs(bot, f),       # D39 오브젝트 태그(있을 때만)
                             **({'new': True} if (f.type in ('weapon', 'armor')            # D57: 아무도 착용한 적 없는 장비(객체 사실,
                                                 and not getattr(f, 'worn', None)) else {})})   #   파트너 "진짜 착용한 적이 없는 것만 new")
                 for f in self.features.values()
                 if f.type != 'exit' and not f.concealed and (f.x, f.y) in seen]
        if self.events:                        # D22 개정(09-06 파트너 발제 "두란의 묘지를 발견한다면
            for f in self.features.values():   #   [두란의 죽음을 발견] 한 줄"): 묘는 공공연한 표지판 —
                if (f.type == 'grave' and (f.x, f.y) in seen   # 죽음을 못 본 동료도 묘를 본 순간 안다
                        and f.id in self.grave_of):            #   (시야-온리 그대로: 묘가 눈에 들 때만)
                    self._remember_grave(bot, f)
        ex, ey = self.exit                                       # v3: 출구 = beacon 아님 → 보일 때만
        gate_on = bool(getattr(self, 'boss_on', False))          # D65: 보스층의 출구 = 워프게이트(봉인 상태도 사실로)
        exit_obj = ({'id': 'exit', 'type': 'exit',
                     'name': '던전 입구' if self.town else ('워프게이트' if gate_on else '출구'),   # 마을(D29): 같은 '>'라도 입구다
                     **({'gate': True, 'sealed': bool(getattr(self, 'sealed', False))} if gate_on else {}),
                     **bear(ex, ey)}
                    if (ex, ey) in seen else None)
        led = bot.get('ledger')            # D17 스위치: 장부 켠 판만 구역 어휘·known 노출
                                           # (끈 판 obs 는 구판과 자구까지 동일 — 게이트 무수정 통과)
        way_keys = (('bearing', 'dist', 'visited', 'zone') if led is not None
                    else ('bearing', 'dist', 'visited'))
        ways = [{k: w[k] for k in way_keys}            # 미지로 트인 출입구(셀좌표는 엔진만 보유.
                for w in self._ways(cx, cy, seen)]     #  zone=어느 구역으로 트였나, D17-2)
        allies = [{'id': 'b%s' % b['char'], 'char': b['char'],
                   'hp': b['hp'], 'maxhp': b['maxhp'],              # HP 숫자(09-08 D45 — 겉보기 4단 폐지) —
                   **bear(b['x'], b['y']),                           #   보이는 동료만(시야-온리)
                   **({'moving': True} if (self.motion and b.get('order')   # 이동중(D27) — 몸짓도
                       and b.get('path')) else {}),                  #   시야를 탄다. 깃발 하나뿐
                   **({'status': sorted(b['status'])}                # 상태 태그(D34) — 겉으로 드러난다
                      if ((self.status or self.skills) and b.get('status')) else {}),   #   (파트너 확정: 같은 단어)
                   **({'resting': True} if (self.rest_verb            # 휴식중(D35) — 쉬는 몸도 보인다
                       and b.get('order') == 'rest') else {}),
                   **({'waiting': True} if (self.wait_verb            # 대기중(D25 개정 09-12) — 서 있는 몸도 보인다
                       and b.get('order') == 'wait') else {}),        #   (파트너 "대기중이라는 걸 추가해볼까? 하나씩")
                   **({'doing': dd} if (self.ally_doing                # 고른 행동(D27 개정 09-12) — 몸짓 깃발은 그대로,
                       and (dd := self._ally_doing(b))) else {})}      #   뜻(무엇을 하러 가는지)을 더한다. 좌표 비노출
                  for b in bots
                  if b['alive'] and not b['won'] and b['char'] != bot['char']
                  and self._ally_seen(bot, b, seen)]
        # party = 파티 명단(좌표 없음 — 시야-온리 유지). 누가 살았고 내려갔나의 사실뿐이다.
        # D18 개정(09-06): 옛 '파티 감각'(안 보여도 'b<char>' 핑 허용=산 좌표로 홈잉)은 폐지 —
        # 파트너 "시야 밖에서 사라지면 말 그대로 사라지는 거야". 안 보이는 동료를 향하는 길은
        # 리모컨 '마지막 본 자리로'(장부 last_seen 칸 핑)뿐이고, 'b<char>' 핑은 보일 때만 해석된다.
        # 솔로 판(self.solo)에서는 명단 자체가 없다 — 남남끼리는 서로 몇이고 누가 살았는지
        # 모른다. 보이는 사람은 sights.bots 로 여전히 나가고 핑도 된다 — 눈에 보이면 지칭할 수 있다.
        party = [] if self.solo else [
                 {'char': o['char'], 'job': o['job'], 'alive': o['alive'],
                  'won': o['won'], 'visible': self._ally_seen(bot, o, seen)}
                 for o in bots if o['char'] != bot['char']]

        # ── 공간 장부(D17-1) obs 투영: '네가 아는 것' — 시야(sights)와 분리. 좌표는 안 나간다:
        # 항목은 {id?, 종류, 이름, 구역, 목격 turn} 뿐 — 봇은 id 로 지칭하고 좌표 운전은 엔진 몫.
        # obs 키 'known' = 장부 투영(도감 bot['known'] 과는 딴 물건 — 도감은 sights 조인으로 스며든다).
        self._ledger_note(bot, seen, bots)             # 동료 last_seen 보강(멱등 — _perceive 재부기)
        known_obs = None
        if led is not None:
            vis_ids = ({m['id'] for m in mons} | {a['id'] for a in allies}
                       | {f['id'] for f in feats} | ({'exit'} if exit_obj else set()))
            ks, last_ms = [], []
            for e in led['statics'].values():
                if (e['x'], e['y']) in seen and (e['type'] != 'trap' or self.scan):
                    continue                           # 지금 보이는 건 sights 소관(중복 금지).
                                                       # 함정만 예외 — sights 에 함정 어휘가 없어
                                                       # 시야에 들면 구조화 obs 에서 증발하는
                                                       # 비대칭 방지(리뷰 픽스): 중복이 아니다
                                                       # (D19 scan 판은 sights.traps 가 생겨 예외 불요)
                ent = {'type': e['type'], 'name': e['name'],
                       'zone': e['zone'], 'turn': e['turn'],
                       # 09-06 파트너 관찰 "기억 속 사물로 길을 고르는데 가끔 한참 먼 곳을 핑" → 방위+직선 거리
                       # (좌표 아님 — 문의 D19 문법과 같은 자. 걸음 수(경로)는 안 본 칸을 지나므로 안 준다)
                       'bearing': self._bearing(e['x'] - cx, e['y'] - cy),
                       'dist': max(abs(e['x'] - cx), abs(e['y'] - cy))}
                if 'id' in e:
                    ent['id'] = e['id']                # id 있는 것만 '돌아가기' 핑 대상
                ks.append(ent)
            for e in led['moving'].values():
                if e['id'] in vis_ids:
                    continue                           # 지금 보이는 몹·동료는 sights 소관
                if 'char' in e:                        # 죽음·하강은 party 가 이미 알려준다(파티
                    o = next((o for o in bots if o['char'] == e['char']), None)   # 감각) — 같은
                    if not (o and o['alive'] and not o['won']):   # obs 안 모순 신호 제거(리뷰 픽스)
                        continue
                ent = {'id': e['id'], 'zone': e['zone'], 'turn': e['turn'],
                       'bearing': self._bearing(e['x'] - cx, e['y'] - cy),   # 마지막 본 자리까지 방위+직선 거리
                       'dist': max(abs(e['x'] - cx), abs(e['y'] - cy))}      # (09-06 — statics 와 같은 자)
                if 'kind' in e:
                    kk = e['kind']                     # 도감 마스킹 — sights 와 같은 규칙(D9 정합)
                    if known is not None and ('monster:' + kk) not in known:
                        kk = UNKNOWN_BEAST
                    ent['kind'] = kk
                if 'char' in e:
                    ent['char'] = e['char']
                    ent['name'] = next((o.get('name') or o['job'] for o in bots
                                        if o['char'] == e['char']), '동료')
                last_ms.append(ent)
            known_obs = {'statics': ks, 'last_seen': last_ms,
                         'zones': [dict(z) for _, z in sorted(led['zones'].items())]}

        # ── D19 구조 조회(2026-07-15 정정): 스캐너 = "시야에 들어온 격자의 번역기" — 전지성 제거 ──
        # "구조는 훤히"는 과독이었다(파트너 교정: 의도는 "시야 범위 내에서라면 인정" — 전부 알면
        # 맵이 핑 메뉴가 된다, 미지가 곧 콘텐츠). 구조 지식 = 지금 보이는 것 + 본 적 있는 것(내 경험):
        # 문·갈림길·막다른 곳은 눈에 든 적 있어야 어휘가 되고(doors_seen·zone_seen), 크기·상대위치는
        # 다 본 공간에서만. 계단은 내용물(2026-07-12 정정 유지). 좌표는 안 나간다(방위+거리+딱지 — known 선례).
        zone_obs = None
        traps_vis = None
        if self.scan:
            entset = bot.get('zones_entered') or set()
            ds = bot.get('doors_seen') or set()
            zid0 = self.zone_at.get((cx, cy))

            def _door_entry(did, home):
                dr = self.doors[did]
                other = dr.zones[1] if home == dr.zones[0] else dr.zones[0]
                px, py = dr.cell if dr.cell else dr.sides[home]
                vis = (((px, py) in seen) if dr.cell
                       else any(s in seen for s in dr.sides.values()))
                out = {'id': did, 'bearing': self._bearing(px - cx, py - cy),
                       'dist': max(abs(px - cx), abs(py - cy)),
                       'seen': vis,                   # 지금 눈에 보이나 / False=본 적 있는 기억
                       'been': other in entset}       # 너머에 들어가 봤나(내 경험 — 누설 아님)
                if out['been'] and self.selfstop:     # D21 재회 표기: 아는 너머는 이름으로 부른다
                    out['to'] = self._zone_name(bot, other)   # ("샘 있던 방으로 이어짐" — 하위 전개 없음)
                return out

            if zid0 is None:                   # 문턱(문 타일) 위 — 문에 서면 양쪽이 다 보인다(광학)
                d0 = next((dd for dd in self.doors.values() if dd.cell == (cx, cy)), None)
                zone_obs = {'id': d0.id if d0 else None, 'kind': '문턱',
                            'checked': {'full': True}, 'doors': []}
            else:
                zh = self.zones[zid0]
                zseen = (bot.get('zone_seen') or {}).get(zid0, set())   # _perceive 가 방금 갱신
                full = zh.cells <= zseen
                checked = {'full': full}
                if not full:                   # 미답 방위 = 내 눈이 본 가장자리 너머(정직한 파생 —
                    fr = [c for c in zseen     #   안 본 칸의 중심 같은 전지적 계산은 쓰지 않는다)
                          if any((c[0] + dx, c[1] + dy) in zh.cells
                                 and (c[0] + dx, c[1] + dy) not in zseen
                                 for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)))]
                    if fr:
                        ux = sum(c[0] for c in fr) / len(fr)
                        uy = sum(c[1] for c in fr) / len(fr)
                        brg = self._bearing(int(round(ux)) - cx, int(round(uy)) - cy)
                        if brg != '-':
                            checked['todo'] = brg
                zdoors = [_door_entry(did, zid0) for did in zh.doors if did in ds]
                zone_obs = {'id': zh.id, 'kind': zh.kind, 'checked': checked, 'doors': zdoors}
                if full and zh.kind == '방':   # 크기·상대위치 = 다 본 방에서만("일부만 봤으면
                    zone_obs['size'] = [zh.w, zh.h]   # 크기를 모른다"가 정직 — 장소 딱지 3단의 정신)
                    zone_obs['at'] = self._at_label(zh, cx, cy)
                if zh.kind == '통로':          # 통로: 길이=다 본 것만, 사건=눈에 든 칸만
                    if full:
                        zone_obs['len'] = len(zh.cells)
                    zone_obs['ends'] = (
                        [{'kind': '갈림길', 'bearing': self._bearing(x - cx, y - cy),
                          'dist': max(abs(x - cx), abs(y - cy)), 'been': (x, y) in self.visited}
                         for (x, y) in zh.junctions if (x, y) in zseen]
                        + [{'kind': '막다른 곳', 'bearing': self._bearing(x - cx, y - cy),
                            'dist': max(abs(x - cx), abs(y - cy)), 'been': (x, y) in self.visited}
                           for (x, y) in zh.deadends if (x, y) in zseen])
            traps_vis = [{'name': t.name, 'kind': t.kind, **bear(t.x, t.y)}
                         for t in self.traps
                         if not t.hidden and not t.sprung and (t.x, t.y) in seen]
            # 정지 신호(D19 정정)의 기준 장부 — 결정 시점에 보이는 오브젝트는 전부 '본 것'이 된다
            bot.setdefault('seen_keys', set()).update(self._content_keys(bot))

        # ── 리모컨(options): 이번 턴 가능한 행동의 전수 열거 — 유효성을 아는 엔진이 곧 메뉴다 ──
        # 원칙: 유효 옵션 전부 / 고정 스키마 순서(즉시행동→이동→수색→탐색) / 주석은 사실만 —
        # 큐레이션이 의지를 조향하지 않는다. 새 동사(거래·상점…)가 생기면 여기 한 블록 추가 =
        # 메뉴·BYO 계약 자동 확장(프롬프트·파서 무수정). 시야-온리: 집결 여부 등 안 보이는
        # 상태는 주석에 싣지 않는다(규칙 문구만). 위에서 만든 지각 목록의 순수 파생 — 굴림 없음.
        options = []

        def _add(typ, target, label):
            o = {'n': len(options) + 1, 'type': typ, 'label': label}
            if target is not None:
                o['target'] = target
            options.append(o)

        # _mfact = 모듈 함수(D17-3에서 승격) — 리모컨 라벨과 wire 직렬화의 문구 단일 소스.
        for m in mons:
            if m.get('in_range'):          # adj 아님 — 사거리(궁수 2칸)로 판정한다
                _add('attack', m['id'], '공격: %s (%s)'
                     % (_mfact(m), '인접' if m['adj'] else '%d칸 거리' % m['dist']))
        if exit_obj and exit_obj['adj']:
            # ⚠️ 라벨이 규칙을 말한다 — 그리고 이건 '고르라고 열거된 선택지 본문'이라
            #    프롬프트 설명문보다 무겁게 읽힌다. 솔로 판에서 파티 규칙을 그대로 띄우면
            #    엔진은 혼자 내려보내면서 메뉴는 모이라고 하는 모순이 된다(07-29 실측:
            #    두란이 계단 확보 후 54틱을 없는 동료 찾기에 썼다). 규칙 문구는 판을 탄다.
            if self.town:                      # 마을(D29): 같은 계단이라도 문맥이 다르다 — 여기의
                _add('interact', 'exit',      #   하강은 '탈출'이 아니라 '모험의 시작'이다
                     '던전 입구로 내려간다 (규칙: 너 혼자 내려간다)'
                     if self.solo else
                     '던전 입구로 내려간다 (규칙: 살아있는 일행 전원이 입구 근처에 모이고 저마다 하던 일이 없어야 내려간다)')
            else:
                _add('interact', 'exit',
                     '계단에서 하강 시도 (규칙: 너 혼자 내려간다 — 기다릴 일행이 없다)'
                     if self.solo else
                     '계단에서 하강 시도 (규칙: 살아있는 파티 전원이 계단 근처에 모이고 저마다 하던 일이 없어야 내려간다)')
        for f in feats:
            if f['adj']:
                if f['type'] == 'building':    # D60(09-12) 마을 관측: 건물은 문턱까지(goto)만 — 안으로 드는 동사는 없다(실내는 후속)
                    continue
                if f['type'] == 'stairs_up':   # 마을 복귀(D29) — 라벨이 규칙을 말한다(하강 라벨 대칭)
                    _add('interact', f['id'],
                         '계단을 올라 마을로 돌아간다 (규칙: 너 혼자 올라간다)'
                         if self.solo else
                         '계단을 올라 마을로 돌아간다 (규칙: 살아있는 일행 전원이 계단 근처에 모이고 저마다 하던 일이 없어야 올라간다)')
                elif f['type'] == 'npc':       # NPC(D29) — 말 걸기(거래 아님. 사실만)
                    _add('interact', f['id'], '말 걸기: %s %s (곁)%s' % (f['name'], f['id'], _tagsfx(f)))   # D39 접미
                elif f['type'] in ('weapon', 'armor'):
                    # 장비 비교(07-30 파트너 설계): 착용 정보는 시트에 상주(캐싱)하고, **비교는
                    # 입수 결정 시점에만** 여기 라벨로 나온다. 라벨=사실만(수치·지금 착용·스왑 물리).
                    word = '피해' if f['type'] == 'weapon' else '막기'
                    cur = bot.get(f['type'])
                    now = ('%s %s +%d — 바꾸면 헌것은 그 자리에 놓는다'
                           % (cur['name'], word, cur['bonus'])) if cur else '기본 무장'
                    _add('interact', f['id'], '장비: %s %s (발밑/인접) — 걸치면 %s +%d (지금: %s)'   # D57: 결론 없이 사실만
                         % (f['name'], f['id'], word, GEAR_KINDS.get(f['name'], 0), now))
                else:
                    _add('interact', f['id'], '상호작용: %s %s (발밑/인접)%s' % (f['name'], f['id'], _tagsfx(f)))
        if bot.get('potions'):                 # 물약(07-17): 소지 중일 때만 어휘가 된다 — 즉시행동군.
            _add('drink', None,                #   주석=사실만(만피 낭비 경고는 '이미 살폈다' 선례)
                 '회복 물약을 마신다 — 상처가 전부 아문다 (한 턴 소모, 소지 %d병)%s'
                 % (bot['potions'],
                    ' ※ 지금은 상처가 없다' if bot['hp'] >= bot['maxhp'] else ''))
        # D47 ②(2026-09-09 파트너 "제안은 열리게 하는 대신 응답에서 제안 승낙 시 선택지 안에서 행동할 수 있게"): 건네기·친목은
        # **곁(체비셰프≤1 — 동행의 '곁'과 같은 자)의 동료에게 늘 열리는 즉시 행동**이다 — 제안이 있어서 생기는 줄이 아니다(파트너
        # 초안 §A-1 "관계가 동료라는 이유만으로 행동을 숨기지는 않는다"). 승낙 = 이 줄을 고르는 것(엔진은 제안 내용을 안 읽는다).
        # 라벨=사실만(무엇을·누구에게·물리). 친목의 형태는 응답 form 자유 서술이며 예시 목록으로 한정하지 않는다.
        if (self.give_verb or self.bond_verb) and not self.solo:
            _anm = {o['char']: (o.get('name') or o['job']) for o in bots}
            for a in allies:
                if a['dist'] > 1:
                    continue                           # 곁이 아니면 어휘가 안 된다(다가가는 건 '합류'가 담당)
                who_ = '%s(봇%s)' % (_anm.get(a['char'], '동료'), a['char'])
                if self.give_verb:
                    ob = next(o for o in bots if o['char'] == a['char'])
                    if bot.get('potions'):
                        _add('give', a['id'], '건네기: 회복 물약 → %s (곁, 소지 %d병)' % (who_, bot['potions']))
                        options[-1]['item'] = 'potion'
                    for slot in ('weapon', 'armor'):
                        g = bot.get(slot)
                        if g:
                            _add('give', a['id'], '건네기: %s → %s (곁 — 벗어 건넨다%s)'
                                 % (g['name'], who_,
                                    ', 그의 %s 자리가 차 있어 발밑에 놓인다' % ITEM_KR[slot] if ob.get(slot) else ', 그가 바로 걸친다'))
                            options[-1]['item'] = slot
                if self.bond_verb:
                    _add('bond', a['id'], '친목: %s에게 곁에서 하는 행동 — 내용은 응답 `form`에 자유롭게 (한 턴 소모)' % who_)
        if exit_obj and not exit_obj['adj']:
            _add('goto', 'exit', '이동: %s exit — %s, 거리 %d'
                 % ('던전 입구' if self.town else '계단',
                    exit_obj['bearing'], exit_obj['dist']))
        for f in feats:
            if not f['adj']:
                _add('goto', f['id'], '이동: %s %s — %s, 거리 %d%s'
                     % (f['name'], f['id'], f['bearing'], f['dist'], _tagsfx(f)))   # D39 접미
        if zone_obs is not None:               # D19 정정: 문 = 본 적 있는 것만 어휘가 된다(시야+기억)
            for dr in zone_obs['doors']:       # 출처 딱지=사실만(어디로 이어지는지는 안 준다 — 층 지도 아님)
                tag = (' (문 너머는 가 본 곳)' if dr['been']
                       else ('' if dr['seen'] else ' (본 적 있음, 지금 시야 밖)'))
                where = ('발밑(지금 선 문턱)' if dr['dist'] == 0
                         else '%s, %dm' % (dr['bearing'], dr['dist']))
                _add('goto', dr['id'], '이동: 문 %s — %s%s — 지나면 건너편 공간'
                     % (dr['id'], where, tag))
        for m in mons:
            if not m['adj']:
                _add('goto', m['id'], '접근: %s — %s, 거리 %d'
                     % (_mfact(m), m['bearing'], m['dist']))
        # 솔로 판에서는 이름을 모른다 — 통성명한 적이 없다. brains 의 wire 가 '낯선 사람'
        # 이라고 쓰는데 엔진 메뉴만 '카야(봇2)'라고 부르면 두 층이 서로 다른 말을 한다
        # (선택지 라벨이 더 무겁게 읽히므로 이쪽이 이긴다). 표기의 단일 진실원천을 지킨다.
        # id(봇2)는 그대로 남는다 — 지칭은 돼야 핑을 건다. 모르는 건 이름뿐이다.
        names = ({} if self.solo
                 else {o['char']: (o.get('name') or o['job']) for o in bots})
        _unknown = '낯선 사람' if self.solo else '동료'
        vis_allies = {a['char'] for a in allies}
        for a in allies:
            if a['adj']:
                continue        # 이미 곁(직교 인접)의 동료 '합류'는 no-op — 다른 adj 분기와 대칭
            _add('goto', a['id'], '합류: %s(봇%s) — HP %d/%d%s, %s, 거리 %d'
                 % (names.get(a['char'], _unknown), a['char'], a['hp'], a['maxhp'],
                    (' · ' + ' · '.join(a['status'])) if a.get('status') else '',   # 09-08 D45: 숫자+태그 병기(겉보기 4단 폐지)
                    a['bearing'], a['dist']))
        # D18 개정(09-06 파트너 "시야 밖에서 사라지면 말 그대로 사라지는 거야"): 옛 '찾아가기
        # (파티 감각으로 접근)'=안 보이는 동료의 산 좌표로 걷는 홈잉 — 폐지. 남는 길은 **장부의
        # 마지막 본 자리**(이 층에서 본 적 있을 때만) — 칸 핑(@x,y)이라 걸어가 봐도 거기 있단
        # 보장이 없다(가서야 안다 = 돌아가기·lost 와 같은 진실). 본 적 없으면 항목 자체가 없다.
        led_mv = (bot.get('ledger') or {}).get('moving') or {}
        for p in party:
            if p['alive'] and not p['won'] and p['char'] not in vis_allies:
                e = led_mv.get('b%s' % p['char'])
                if not e:
                    continue                           # 이 층에서 본 적 없는 동료 = 갈 곳을 모른다
                ago = self.turn - e['turn']
                _add('goto', '@%d,%d' % (e['x'], e['y']),
                     '마지막 본 자리로: %s(봇%s) — %s에서 봄(%s), %s %d칸 (지금도 거기 있단 보장은 없다)'
                     % (names.get(p['char'], _unknown), p['char'], e['zone'],
                        ('%d턴 전' % ago) if ago > 0 else '방금',
                        self._bearing(e['x'] - bot['x'], e['y'] - bot['y']),
                        max(abs(e['x'] - bot['x']), abs(e['y'] - bot['y']))))
        for a in allies:                               # 동행(D18 A-5) — 보이는 동료마다 지속 order
            ob = next(o for o in bots if o['char'] == a['char'])
            mutual = str(ob.get('order') or '') == 'follow:b%s' % bot['char']
            _add('follow', a['id'],                    # ※주석=사실만(수색 '이미 살폈다' 선례).
                 '동행: %s(봇%s) 곁을 따라 걷는다 — 새 일이 생기면 멈추고 묻는다%s'
                 % (names.get(a['char'], _unknown), a['char'],
                    ' ※ 그는 지금 너를 따르는 중이다 — 서로 따르면 아무도 못 움직인다'
                    if mutual else ''))                # 곁에서 나를 계속 따르는 행동은 눈에 보인다
                                                       # (보이는 동료 한정=allies 루프 — 시야-온리)
        if self.rest_verb and (bot['hp'] < bot['maxhp'] or bot.get('status')):
            # 휴식(D35) — 다쳤거나 몸 상태가 있을 때만 어휘가 된다(성한 몸은 '기다린다'가 서 있기를
            # 담당). 라벨=사실만: 회복량·완료 조건·깨는 사건. 안전은 약속하지 않는다.
            _add('rest', None,
                 '쉰다: 이 자리에서 — 틱마다 HP %d 회복, 다 나으면 몸 상태(출혈·둔화·중독)가 낫는다.'
                 ' 맞거나 새것을 보거나 말을 걸어오면 깬다' % REST_HP)
        if self.wait_verb:                             # wait(D25) — 제자리 대기(사건 기반, 숫자 없음)
            _add('wait', None, '기다린다: 이 자리에서 — 동료가 오거나 새 일이 생기면 깨어난다')
        # 돌아가기(D17-1 귀환 핑) — 장부의 제자리 물건(id 있는 것)로 시야 밖 복귀. 라벨=사실만
        # (어디서·언제 봤나). '그 사이 없어졌을 수 있다'는 세계의 진실 — 가서야 안다(lost 드라마).
        if known_obs is not None:
            for e in known_obs['statics']:             # 이미 '지금 안 보이는 것'만 담겨 있다
                if 'id' not in e:
                    continue                           # 함정 항목(정보만) — 핑 대상 아님
                ago = self.turn - e['turn']
                _add('goto', e['id'], '돌아가기: %s — %s에서 봄(%s), %s %d칸, 지금은 시야 밖'
                     % (e['name'], e['zone'],       # '안 보임'은 '사라짐'으로 오독됨(프로브 실측)
                        ('%d턴 전' % ago) if ago > 0 else '방금',
                        e['bearing'], e['dist']))   # 09-06: 얼마나 먼지(직선 칸) — 먼 핑을 알고 고르게
        # 수색 라벨 — 지금 살필 반경이 전부 '이미 살핀 곳'이면 그 사실을 붙인다(자기 행동 기억).
        # A/B 실측에서 이 주석 없이는 같은 자리 수색 반복 평균 70회(수색 합창 루프)로 판이 죽었다.
        # 마을(D29)에선 수색·탐색 동사가 안 열린다 — 전부 보이는 곳에서 "벽 뒤·시야 밖" 라벨은
        # 거짓이 된다(세계가 말하는 것=규칙이 하는 것). 숨을 것도, 못 본 길도 없다.
        if not self.town:
            s_seen = self.visible_cells(cx, cy, bot.get('search_r', 1))
            already = s_seen <= bot.get('searched', set())
            _add('search', None,
                 '수색: 반경 %d 안 보이는 범위의 숨은 함정·매복·보물을 드러낸다 (벽 뒤는 못 본다 — 한 턴 소모)%s'
                 % (bot.get('search_r', 1),
                    ' ※ 이 반경은 이미 샅샅이 살폈다 — 반복해도 새로 나올 게 없다' if already else ''))
        exhausted = False
        if self.town:
            pass                               # 마을: explore 옵션군 전체 생략(위 사유)
        elif zone_obs is not None:             # D19: 탐색 종점=명사(막다른 곳) — 시야 가장자리 폐기.
            for e in zone_obs.get('ends', []):   # 문은 위 goto 가 전담(중복 옵션 금지 — 1:1 원칙)
                if e['kind'] == '막다른 곳' and not e['been']:
                    _add('explore', e['bearing'], '탐색: %s쪽 막다른 곳까지 가 본다 — %dm'
                         % (e['bearing'], e['dist']))
            listed = 0
            if self.explore_dirs:
                # D19 개정 4(2026-09-07, 파트너 "탐색 방향을 주는 정보가 비대칭"): D19 ② 원문 "방향 탐색"의 복원 —
                # 문장이 '트여 있다'고 말하는 방위마다 '탐색' 한 줄(target=방위). 갈 방향의 선택은 에이전트가.
                # 제외 = 이미 다른 줄이 그 방위를 대표하는 것(1:1 원칙): 막다른 곳(위 explore) · 보이는 문(위 goto —
                # 그 방위의 문장도 '문'이지 '트여 있다'가 아니다) · 종점이 문 칸인 길. 목록·종점은 계획기와 한 벌.
                covered = {o['target'] for o in options if o['type'] == 'explore'}
                covered |= {dr['bearing'] for dr in zone_obs['doors'] if dr['seen'] and dr['dist'] > 0}
                doorc = {dr.cell for dr in self.doors.values() if dr.cell}
                doorc |= {c for dr in self.doors.values() for c in dr.sides.values()}
                for w, p in sorted(self._explore_ways(bot, bots),          # 시계 방향 — 문장과 같은 순서로 읽힌다
                                   key=lambda wp: BEAR_ORDER.index(wp[0]['bearing'])):
                    if w['bearing'] in covered or p[-1] in doorc:
                        continue
                    _add('explore', w['bearing'], '탐색: %s — 트여 있다, 너머는 안 보인다 — 약 %d칸'
                         % (BEAR_KR.get(w['bearing'], w['bearing']), len(p)))
                    covered.add(w['bearing'])
                    listed += 1
            plan = None if listed else self._explore_plan(bot, None, bots)   # D19 개정: 갈 곳이 있을 때만 어휘가 된다
            if plan is not None:                   #   (열거가 있으면 '엔진에 맡긴다' 줄은 중복 — 뺀다)
                _o, _p, _r = plan              # 09-06 파트너: 엔진이 고를 종점이 어디쯤·얼마나 먼지 라벨에(먼 핑을 알고 고른다)
                whither = ('%s쪽 새 길' % _r['bearing'] if _r.get('bearing')
                           else '기억 속 계단 쪽' if _r.get('to_exit')
                           else '기억 속 안 가 본 문 쪽' if _r.get('door')
                           else '기억 속 안 본 가장자리 쪽' if _r.get('frontier')
                           else '새 길')
                _add('explore', None, '탐색: 아직 못 본 곳/새 길을 찾아 나선다 — %s, 약 %d칸 (엔진에 맡긴다)'
                     % (whither, len(_p)))
            elif not listed:
                exhausted = True               #   없으면 라벨 대신 사실 한 줄(obs.exhausted — 조향 없음)
        else:
            fresh_ways = [w for w in ways if not w['visited']]
            for w in fresh_ways:
                _add('explore', w['bearing'], '탐색: %s쪽 안 가본 길 — 거리 %d'
                     % (w['bearing'], w['dist']))
            if not fresh_ways:
                if self._explore_plan(bot, None, bots) is not None:
                    _add('explore', None, '탐색: 새 길을 찾아 나선다 (시야 밖 — 엔진에 맡긴다)')
                else:
                    exhausted = True

        # A-3(D18)+D22 전달층: 목격 — 내 눈으로 본 동료의 사건(피격·전사·명중·처치·함정·회복).
        # 1회성: 이번 결정에 한 번 전달하고 비운다(휘발=다음 결정 1회 — D22).
        # 자기 사건은 last 가 담당(중복 없음). 종 표기는 내 도감 기준(모르는 종=낯선 짐승 — D9 정합).
        def _mask(w):                          # 도감 게이트 — 몹 이름만 가린다(함정·샘은 by_kind 로 면제)
            out = {**w, **({'name': names.get(w['char'], _unknown)} if 'char' in w else {}),
                   **({'to_name': '%s(봇%s)' % (names.get(w['to'], _unknown), w['to'])} if 'to' in w else {})}
            #   ↑ D47 ②(09-09) 건네기·친목 목격의 상대(to) — 사람 사건이라 이름으로(솔로 판은 '낯선 사람')
            #   ↑ 몹 주어 사실(mon_use — D30 확장 2차)은 char 가 없다: 이름 풀이는 사람 사건에만
            if known is not None:
                if 'by' in out and out.get('by_kind', 'monster') == 'monster' \
                        and 'monster:' + out['by'] not in known:
                    out['by'] = UNKNOWN_BEAST
                if 'mon' in out and 'monster:' + out['mon'] not in known:
                    out['mon'] = UNKNOWN_BEAST
            return out
        wit = bot.get('witnessed') or []
        if wit:
            bot['witnessed'] = []
            wit = [_mask(w) for w in wit]
        trail = list(bot.get('trail') or [])     # D38 궤적 — 노출 후 소거(witnessed 문법: 다음 결정 1회)
        gap = int(bot.get('trail_gap') or 0)
        if trail or gap:
            bot['trail'], bot['trail_gap'] = [], 0
        if gap:
            trail = [{'type': 'gap', 'n': gap}] + trail   # 상한에 잘린 앞부분 — 생략 표식 한 칸
        dry_out = bot.get('dry', 0) if bot.get('dry_hit') else 0
        if dry_out:
            bot['dry_hit'] = False    # 1회성 배달(witnessed 문법 — 이번 결정에 한 번, 비운다)
        # D22 기억층: 목격한 중대사(v0=fallen)는 휘발하지 않는다 — 매 결정 재제시(비우지 않음).
        mem = [_mask(e) for e in (bot.get('memories') or [])]

        rel_obs = []
        if self.relations and not self.solo:       # 관계 장부(D36) — 솔로 판은 로스터가 없다(남남)
            invited = False
            for oc in sorted(bot.get('relations') or {}):
                e = bot['relations'][oc]
                ob = next((o for o in bots if o['char'] == oc), None)
                if ob is None:
                    continue                       # 로스터 밖 상대(시트 잔재) — 침묵
                order = list(BONES) + sorted(k for k in e['bones'] if k not in BONES)   # 사전 순서(의미순)
                bones = [{'kind': k, 'label': BONES.get(k, k), 'n': e['bones'][k]['n'],
                          'last': e['bones'][k]['last']}
                         for k in order if e['bones'].get(k, {}).get('n')]
                ent = {'char': oc, 'name': ob.get('name') or ob['job'], 'bones': bones,
                       'line': e.get('line'), 'line_turn': e.get('line_turn'),
                       'line_src': e.get('line_src')}
                if e.get('acts'):                      # D47 ② 상세 기록(친목·건네기 형태+상대 반응) — 최근 ACTS_SHOW 건
                    ent['acts'] = [dict(a) for a in e['acts'][-ACTS_SHOW:]]
                if not invited and e.get('queue'):
                    ent['invite'] = e['queue'].pop(0)   # 결정당 초대 1개 — 나머지는 다음 결정
                    invited = True
                if bones or ent.get('invite') or e.get('line'):
                    rel_obs.append(ent)
        rid_here = self._room_id_at(cx, cy)
        obs = {'pos': [cx, cy], 'hp': bot['hp'], 'maxhp': bot['maxhp'],
                'job': bot['job'], 'sex': bot['sex'],
                'str': bot['str'], 'dex': bot['dex'], 'inventory': bot['bag'],
                'potions': bot.get('potions', 0),   # 소지 회복 물약(07-17) — 자기 몸의 사실
                'gear': {'weapon': bot.get('weapon'), 'armor': bot.get('armor')},
                **({'town': True} if self.town else {}),   # 마을(D29) — 층의 사실(던전 obs 무변경)
                **({'town_zone': tz} if (self.town and (tz := self._town_zone(bot['x'], bot['y'])))   # D60(09-12) 지금 있는 구역 이름
                   else {}),
                **({'notices': nts_} if (self.town and (nts_ := self._notices(bot))) else {}),   # D61 게시판·신의 요청(문턱 근처만)
                                      # 장비(07-30) — 자기 몸의 사실(더미·BYO 소비용 데이터).
                                      # ⚠️ 프롬프트 상시 노출은 금지 계약: 착용 정보는 시트(불변
                                      # 프리픽스=캐싱)에 살고, 비교는 입수 메뉴 라벨에만 나온다
                'depth': self.depth,
                **({'zone': zone_obs} if zone_obs is not None else
                   ({'zone': {'id': ('r%d' % rid_here) if rid_here is not None else None,
                              'kind': '방' if rid_here is not None else '통로'}}
                    if led is not None else {})),      # 구역 어휘: D19 scan=구조 조회 / D17=주소만
                **({'turn': self.turn} if led is not None else {}),   # 장부 turn 스탬프의 '지금'
                                                       # — wire 가 'N턴 전'을 셈(D17-3). 장부와 한 몸
                **({'known': known_obs} if known_obs is not None else {}),   # 공간 장부(D17-1)
                **({'witnessed': wit} if wit else {}),   # 목격(A-3) — 있을 때만 실림(intent 선례)
                **({'dry': dry_out} if dry_out else {}),   # 무발견 신호(07-24) — 도달 시점 1회
                **({'memories': mem} if mem else {}),    # 기억(D22 fallen) — 휘발 0, 있을 때만 실림
                **({'status': [{'tag': t, **e} for t, e in sorted(bot['status'].items())]}
                   if ((self.status or self.skills) and bot.get('status')) else {}),   # 상태 태그(D34) — 자기 몸의 사실
                **({'relations': rel_obs} if rel_obs else {}),   # 관계 장부(D36) — 뼈 횟수·살·초대
                **({'exhausted': True} if exhausted else {}),   # 탐색 소진(D19 개정) — 새 길·기억의 계단·안 가 본 문 없음
                **({'trail': trail} if (getattr(self, 'trail_on', False) and trail) else {}),
                                              # 자기 행동 궤적(D38, 09-06) — 마지막 결정 이후 일어난 일의 순서,
                                              #   있을 때만(intent 선례). last 는 그 마지막 항목과 같다
                **self._floor_obs(bot),       # 층 집계·지난 층 결산(D40 ②) — 있을 때만
                **({'book_invite': binv} if binv else {}),   # D55 인식 초대 — 대기 중일 때만(결정당 하나)
                'last': bot.get('last'),      # 직전 행동/피격의 결과(D1 개정) — "봇은 자기 행동의
                                              #   결과를 관측할 수 있어야 한다". 자기 경험=시야-온리 무위반
                'order': ('explore' if str(bot.get('order') or '')[:1] == '@'
                          else bot.get('order')),        # 진행중 핑(자동보행). '@x,y' 생좌표는 봇에 노출X
                'ascii_view': rows,
                'sights': {'exit': exit_obj, 'features': feats, 'monsters': mons,
                           'ways': ways, 'bots': allies,
                           **({'traps': traps_vis} if traps_vis is not None else {})},
                'party': party,
                'options': options,   # 리모컨 — 엔진 열거 유효 행동(additive. BYO 계약: 번호+한마디)
                'legend': {'@': 'you', '#': 'wall', '.': 'floor', '+': 'door',
                           '$': 'treasure', '>': 'stairs/exit', 'M': 'monster',
                           '^': 'trap', '=': 'chest', '~': 'fountain', '!': 'potion',
                           ')': 'weapon', '[': 'armor',
                            'T': 'grave', ' ': 'unknown'}}
        return CA.observe(self, bot, bots, obs) if self.composed_actions else obs

    # ── 탐색 프런티어 (explore = 미지로 트인 출입구) ─────────────
    def _frontier_cells(self, cx, cy, seen):
        """시야 내 '미지로 트인' 바닥칸 — 보이는 floor 중 직교 이웃에 미지(시야밖)가 있는 칸.
        = 지금 보이는 '더 갈 수 있는 가장자리'. 방이면 출입구, 통로면 진행 방향이 잡힌다.
        문 타일(+)도 포함(D19 정정) — 문은 불투명이라 그 너머가 늘 미지: 보이는 문 자체가
        프런티어가 되어 탐색 폴백이 문으로 걸어간다(종결 보장이 문에서 끊기지 않게)."""
        out = []
        for (x, y) in seen:
            if (x, y) == (cx, cy) or self.grid[y][x] not in (FLOOR, DOOR):
                continue
            for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.w and 0 <= ny < self.h and (nx, ny) not in seen:
                    out.append((x, y)); break
        return out

    def _ways(self, cx, cy, seen):
        """프런티어 칸을 방위 8방향으로 묶어 대표 '출입구(way)' 목록으로. 각 way = 그 방위에서
        (안 밟은 것 우선·가까운 것 우선) 대표 칸. visited=대표칸에 보이는 발자국(이미 지난 길)."""
        buckets = {}
        for (x, y) in self._frontier_cells(cx, cy, seen):
            buckets.setdefault(self._bearing(x - cx, y - cy), []).append((x, y))
        ways = []
        for b, cells in buckets.items():
            rep = min(cells, key=lambda c: (c in self.visited,
                                            max(abs(c[0] - cx), abs(c[1] - cy)), c))
            ways.append({'bearing': b, 'cell': rep,
                         'dist': max(abs(rep[0] - cx), abs(rep[1] - cy)),
                         'visited': rep in self.visited,
                         'zone': self._zone_label(*rep)})   # 어느 구역으로 트였나(D17-2)
        ways.sort(key=lambda w: (w['visited'], w['dist'], w['bearing']))
        return ways

    # ── 주사위 ──────────────────────────────────────────────────
    def d20(self):
        return self.rng.randint(1, 20)

    # ── 행동 판정 = 심판 (핑 + 자동보행) ────────────────────────
    def act(self, bot, action, bots):
        """action(dict): {'type':'goto'|'attack'|'interact'|'search', 'target': id, ['then': [...]]}
        goto = 핑(보이는 오브젝트 id) → order+path 세팅(이동은 step_order가 틱마다 한 칸씩).
        attack/interact/search = 즉시 판정. 반환: 결과 dict — GM 서사·로그가 읽을 '진실'.
        then(D16 작정) = 이어질 행동 최대 PLAN_MAX수 — 에이전트가 품는 계획이지 세계에 거는
        예약이 아니다: 인터럽트(피격·새 발견·길막힘·lost)가 남은 작정을 찢는다."""
        if self.composed_actions:
            CA.normalize(bot, action)
            if bot.get('order'):
                bot['order'], bot['path'], bot['plan'] = None, [], []
            bot.pop('_active_action', None)
            bot['_execution_refs'] = CA.copy.deepcopy(bot.get('_plan_refs' if action.get('src') == 'plan' else '_target_refs', {}))
            if 'then' in action:
                bot['_plan_refs'] = CA.copy.deepcopy(bot['_execution_refs'])
        typ = (action or {}).get('type', 'goto')
        tgt = (action or {}).get('target')
        if bot.pop('approach', None):             # 새 판단은 예전 접근 요청을 이어 실행하지 않는다
            bot['order'], bot['path'], bot['plan'] = None, [], []
        bot['wander'] = None                      # 새 결정 = '계속 이동'의 단절(D21 맴돎 창 리셋)
        bot['exit_seen_at_order'] = self.exit in self.visible_cells(bot['x'], bot['y'])
        #   ↑ 09-08 D45 부검: 결정 순간 계단이 눈에 있었나 — at_exit 정지의 dedupe 재료(아래 step_order). 시드 217 livelock:
        #   f3 가 계단 너머라 goto f3 마다 계단 칸에서 at_exit 로 서고, 계단 위 동료는 자리 교대로 밀려나 다시 goto f3 — 무한.
        #   D19 '개시 때 이미 보이던 계단은 새것이 아니다'와 같은 규율: 알고 지나는 계단은 안 세운다(goto exit 는 도착이라 선다).
        if 'then' in (action or {}):              # 작정 접수 — 저작 검증(시야-온리)은 brains 소관,
            bot['plan'] = ([] if typ in ('follow', 'wait', 'rest')   # 동행·대기·휴식=열린 결말 — 뒤수 부적합
                           else [dict(s) for s in (action.get('then') or [])
                                 if isinstance(s, dict) and s.get('type')][:PLAN_MAX])
        aid = None
        if self.composed_actions or (self.auto_approach and typ in ('attack', 'interact', 'give', 'bond')):
            self._action_serial += 1
            aid = 'd%s:t%s:a%s' % (self.depth, self.turn, self._action_serial)
            action['action_id'] = aid             # 실제 접수된 결정에만 부여. 모델이 만드는 값이 아니다
            res = (self._begin_approach(bot, action, bots)
                   if self.auto_approach and (typ in (CA.DISTANCE_ACTIONS if self.composed_actions else ('attack', 'interact', 'give', 'bond')) or (self.skills and typ not in CA.COMMON))
                   else None)
        else:
            res = None
        if res is None:
            res = self._execute_action(bot, action, bots)
        if aid:
            res['parent_action_id'] = aid
        if self.composed_actions:
            CA.decorate(bot, action, res)
            SK.complete(self, bot, action, res)
            if bot.get('order'):
                bot['_active_action'] = {k: v for k, v in action.items() if k in ('type', 'target', 'item', 'form', 'action_id')}
            else:
                bot.pop('_active_action', None)
                bot.pop('_execution_refs', None)
        self._note_last(bot, res, plan=(action.get('src') == 'plan'))
        return res

    def _execute_action(self, bot, action, bots):
        """현재 자리에서 원래 행동의 효과를 한 번 판정한다. 접근 완료도 같은 실행 경로를 쓴다."""
        if not self.composed_actions:
            return self._execute_legacy_action(bot, action, bots)
        result = (SK.execute(self, bot, action, bots)
                  if self.skills and action.get('type') not in CA.COMMON
                  else CA.execute(self, bot, action, bots))
        SR.physical(self, bot, action, result, bots)
        return result

    def _execute_legacy_action(self, bot, action, bots):
        typ, tgt = action.get('type', 'goto'), action.get('target')
        if typ == 'attack':
            res = self._attack(bot, tgt, bots)
        elif typ == 'interact':
            f_pre = self._feature_by_target(tgt)      # D39: 상호작용 전에 피처를 잡는다(상자는 열리며 사라진다)
            res = self._interact(bot, tgt, bots)
            self._obj_tag(bot, f_pre, res)             # D39 오브젝트 태그(횟수·마지막 사실) — 판정 무접촉
        elif typ == 'search':
            res = self._search(bot, bots)
        elif typ == 'drink':
            res = self._drink(bot, bots)              # 회복 물약(07-17) — 무대상 즉시 동사(search 선례)
        elif typ == 'wait':
            res = self._set_wait(bot, bots)           # 제자리 대기(D25) — 사건 기반, 숫자 없음
        elif typ == 'rest':
            res = self._set_rest(bot, bots)           # 휴식(D35) — 회복이 붙은 wait
        elif typ == 'explore':
            res = self._set_explore(bot, tgt, bots)   # 탐색(선택적 방위 tgt)
        elif typ == 'follow':
            res = self._set_follow(bot, tgt, bots)    # 동행(D18 A-5) — 곁 유지 지속 order
        elif typ == 'give':
            res = self._give(bot, tgt, (action or {}).get('item'), bots)   # 건네기(D47 ②) — 곁의 동료에게 소지품
        elif typ == 'bond':
            res = self._bond(bot, tgt, (action or {}).get('form'), bots)   # 친목(D47 ②) — 곁의 동료에게 몸짓
        else:
            res = self._set_order(bot, tgt, bots)     # goto(기본)
        return res

    def _approach_target(self, bot, action, bots):
        """접근은 지금 보이는 실물만 해소한다. 기억의 좌표나 숨은 실물로 재조준하지 않는다."""
        if self.composed_actions:
            return CA.entity(self, bot, action.get('target'), bots)
        typ, tgt = action['type'], action.get('target')
        res = self._resolve_target(tgt, bots, bot)
        if not res:
            return None
        kind, xy = res
        if typ in ('give', 'bond'):
            return res if kind == 'bot' and str(tgt) != 'b%s' % bot['char'] else None
        if xy not in self.visible_cells(bot['x'], bot['y']):
            return None
        if typ == 'attack':
            m = self.monster_at(*xy) if kind == 'monster' else None
            return res if m and m.alive and not m.concealed else None
        if kind == 'exit':
            return res
        f = self._feature_by_target(tgt)
        return res if kind in ('exit', 'feature') and f and not f.concealed else None

    def _action_in_range(self, bot, action, target, at=None):
        if self.composed_actions:
            return CA.in_range(self, bot, action, target, at)
        x, y = at if at is not None else (bot['x'], bot['y'])
        tx, ty = target[1]
        if action['type'] == 'attack':
            mon = self.monster_at(tx, ty)
            return bool(mon and self._can_hit({**bot, 'x': x, 'y': y}, mon))
        if action['type'] in ('give', 'bond'):
            return self._beside_xy(x, y, tx, ty, 'bot')
        return abs(x - tx) + abs(y - ty) <= 1

    def _approach_path(self, bot, action, target, bots):
        """기존 BFS·함정 회피·교대 규칙에 실행 가능한 도착 칸만 넘긴다."""
        tx, ty = target[1]
        radius = SK.required_range(self, bot, action)
        goals = {(x, y) for y in range(max(0, ty - radius), min(self.h, ty + radius + 1))
                 for x in range(max(0, tx - radius), min(self.w, tx + radius + 1))
                 if self.walkable(x, y, bots) and self._action_in_range(bot, action, target, (x, y))}
        return self.path_to(bot['x'], bot['y'], tx, ty, bots, goals=goals)

    def _begin_approach(self, bot, action, bots):
        typ = action['type']
        if (typ == 'give' and not self.give_verb) or (typ == 'bond' and not self.bond_verb):
            return None
        if typ == 'attack' and not action.get('target'):
            return None                           # 기존 무대상 공격 API는 현재 사거리 판정 유지
        base = {'char': bot['char'], **{k: action[k] for k in ('type', 'target', 'item', 'form') if k in action}}
        target = self._approach_target(bot, action, bots)
        if self.skills and typ not in CA.COMMON:
            why = SK.preflight(self, bot, SK.lookup(self, bot, typ), target)
            if why:
                return SK.failure(bot, action, why)
        if not target:
            bot['plan'] = []
            return {**base, 'result': 'no_target'}
        if typ == 'give' and not self.composed_actions:
            item = action.get('item')
            if not bot.get('potions' if item == 'potion' else item or ''):
                return {**base, 'result': 'nothing'}
        if self._action_in_range(bot, action, target):
            return None
        path = self._approach_path(bot, action, target, bots)
        if not path:
            bot['order'], bot['path'], bot['plan'] = None, [], []
            return {**base, 'result': 'no_path'}
        pending = {k: action[k] for k in ('type', 'target', 'item', 'form', 'action_id') if k in action}
        bot['approach'] = pending
        bot['order'], bot['path'] = action['target'], path
        return {**base, 'result': 'approaching', 'len': len(path),
                'required_range': SK.required_range(self, bot, action)}

    def _cancel_approach(self, bot):
        """중단한 원래 의도를 표시한다. 피격/제안 등은 그 행동의 성공이나 하위 행동이 아니다."""
        action = bot.pop('approach', None) or bot.get('_active_action')
        bot.pop('_active_action', None)
        bot.pop('_execution_refs', None)
        return {'interrupted_action_id': action['action_id']} if action else {}

    def _step_approach(self, bot, bots):
        action = bot['approach']
        base = {'char': bot['char'], 'type': 'walk', 'target': action['target'],
                'parent_action_id': action['action_id'], 'action_type': action['type']}
        target = self._approach_target(bot, action, bots)
        if not target:
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot.pop('approach', None)
            return {**base, 'result': 'lost', 'approach_status': 'interrupted'}
        if self._action_in_range(bot, action, target):
            newly = self._perceive(bot)
            if newly:
                bot['order'], bot['path'], bot['plan'] = None, [], []
                bot.pop('approach', None)
                return {**base, 'result': 'encounter', 'approach_status': 'interrupted',
                        'monsters': [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state} for m in newly]}
            sres = self._sighted_stop(bot, base)
            if sres:
                bot.pop('approach', None)
                return {**sres, 'approach_status': 'interrupted'}
            bot.pop('approach', None)
            bot['order'], bot['path'] = None, []
            # 이동한 틱에는 효과를 더하지 않는다. 다음 틱 시작에 재검증 후 원래 행동을 실행.
            res = self._execute_action(bot, action, bots)
            return {**res, 'parent_action_id': action['action_id'], 'approach_status': 'completed'}
        end = bot['path'][-1] if bot.get('path') else (bot['x'], bot['y'])
        if not self._action_in_range(bot, action, target, end):
            bot['path'] = self._approach_path(bot, action, target, bots)
        if not bot.get('path'):
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot.pop('approach', None)
            return {**base, 'result': 'blocked', 'approach_status': 'interrupted'}
        res = self._step_order(bot, bots, approaching=True)
        res.update(parent_action_id=action['action_id'], action_type=action['type'])
        if not bot.get('order'):
            bot.pop('approach', None)
            res['approach_status'] = 'interrupted'
        return res

    def _note_last(self, bot, res, plan=False):
        """봇 자기 행동의 최신 결과 메모 — 원칙 "봇은 자기 행동의 결과를 관측할 수 있어야 한다".
        view()가 obs['last']로 노출. 자기 경험만 담으므로 시야-온리 무위반(세계 정보 아님).
        D38(09-06): 같은 줄을 궤적(bot['trail'])에도 잇는다 — _trail_add 참조(기록은 한 번, 보기 둘)."""
        bot['last'] = {k: v for k, v in res.items() if k != 'char'}
        self._trail_add(bot, bot['last'], plan=plan)

    def _trail_add(self, bot, rec, plan=False):
        """자기 행동 궤적(D38, 2026-09-06 파트너 확정 "자기 행동에 대한 정보가 많이 부족했던 거네"):
        **마지막 view() 이후** 이 봇에게 일어난 결과를 순서대로 보존한다. last 는 한 칸이라 작정(D16)이
        붙은 결정은 다음 틱의 plan goto·걸음이 상인 대사·전투 결과를 덮었다(09-06 마을 판: 미나가 상인의
        '이미 줬어'를 결정 시점에 0/7 봄). view() 가 노출 후 비운다(witnessed 선례 — 휘발=다음 결정 1회).
        작정 집행 틱은 view() 가 없으니 자연히 쌓인다 = 구멍을 메우는 원리. 기록자는 여기 한 곳
        (act·자동보행 걸음·plan_broken·교대·말 걸림·피격 전부 경유). 항목 = {…res, turn, plan?}.
        엔진 판정은 절대 안 읽는다(자기 경험의 기록·노출뿐). 상한 TRAIL_MAX — 넘치면 앞을 버리고 gap 누적."""
        self._trail_push(bot, rec, plan)
        self._floor_count(bot, rec)
        self._hp_watch(bot)

    def _floor_count(self, bot, rec):
        """층 집계(D40 ②): 같은 사전(event_tags)으로 자기 사건을 센다 — 집계 여부 True 인 키만(걸음·이동 시작·도착
        제외). 라벨이 키(표시용). 숫자만 늘지 줄은 안 는다(파트너 "나열 말고 집계")."""
        if not getattr(self, 'floor_on', False):
            return
        fl = bot.setdefault('floor', {'since': self.turn, 'n': {}, 'w': {}})
        for k, label, _ in event_tags(rec):
            if EVENT_KINDS.get(k):
                fl['n'][label] = fl['n'].get(label, 0) + 1

    def _floor_count_w(self, bot, fact):
        """층 집계(D40 ②) — 목격 사건(witnessed kind)을 WITNESS_LABELS 로 w 에 센다."""
        if not getattr(self, 'floor_on', False):
            return
        label = WITNESS_LABELS.get(fact.get('kind'))
        if not label:
            return
        fl = bot.setdefault('floor', {'since': self.turn, 'n': {}, 'w': {}})
        fl['w'][label] = fl['w'].get(label, 0) + 1

    def _trail_push(self, bot, rec, plan=False):
        """궤적 한 칸 추가(상한·gap 부기). _trail_add 와 _hp_watch 가 쓴다 — 여기선 HP 감시 안 함(재귀 방지)."""
        if not getattr(self, 'trail_on', False):
            return
        tr = bot.setdefault('trail', [])
        tr.append({**{k: v for k, v in rec.items() if k != 'char'}, 'turn': self.turn,
                   **({'plan': True} if plan else {})})
        if len(tr) > TRAIL_MAX:
            bot['trail_gap'] = int(bot.get('trail_gap') or 0) + (len(tr) - TRAIL_MAX)
            del tr[:len(tr) - TRAIL_MAX]

    def _hp_watch(self, bot):
        """위급(D40, 2026-09-06 파트너 확정 "위급은 4분의 1") — 상태 전이 사건: HP 가 최대의 1/4 이하로 내려가는
        순간 1회 [위급], 다시 위로 올라오면 1회 [위급 해제]. 매 틱 반복 없음(넘는 순간만) — 사실만, 조향 없음
        (픽셀 던전이 상태를 사건으로 찍는 방식). 자기 결과가 궤적에 실릴 때마다 살핀다 = HP 를 바꾸는 모든 경로
        (피격·함정·출혈·물약·샘·휴식)가 _note_last/_trail_add 를 지나므로 빠지지 않는다."""
        if not (getattr(self, 'trail_on', False) or getattr(self, 'floor_on', False)) or not bot.get('alive', True):
            return
        crit = bot['hp'] * 4 <= bot['maxhp']
        if crit == bool(bot.get('critical')):
            return
        bot['critical'] = crit
        rec = {'type': 'state', 'result': 'critical' if crit else 'recovered',
               'hp': bot['hp'], 'maxhp': bot['maxhp']}
        self._trail_push(bot, rec)
        self._floor_count(bot, rec)

    def _feature_by_target(self, target_id):
        """'f<n>' → Feature(없으면 None). D39: 상호작용 전에 잡는다(상자는 열리며 사라진다)."""
        s = str(target_id or '')
        if s[:1] == 'f' and s[1:].isdigit():
            return self.features.get(int(s[1:]))
        return None

    def _obj_tag(self, bot, f, res):
        """오브젝트 태그(D39, 2026-09-06 파트너 발제 "태그 시스템에 궤적을 쌓자" → 합의 "궤적의 짝 —
        태그=지금 참인 사실과 횟수, 궤적=순서"): 이 봇이 그 오브젝트와 상호작용한 횟수와 마지막 사실
        한 마디를 기계가 센다(나↔오브젝트 사이의 사실 — D36 뼈의 오브젝트판. 몸 태그 D34 는 몸 상태로).
        수명=봇 dict(층 재스폰이면 초기화 — shop_served 리듬). 엔진 판정은 절대 안 읽는다(시야 줄·라벨 접미뿐)."""
        if not getattr(self, 'objtags', False) or f is None or f.type not in OBJ_VERBS:
            return
        if res.get('result') in ('no_target', 'too_far'):
            return                                  # 닿지 않은 시도는 상호작용이 아니다
        e = bot.setdefault('obj_tags', {}).setdefault(f.id, {'n': 0})
        e['n'] += 1
        note = _obj_note(res)
        if note:
            e['note'] = note

    def _floor_obs(self, bot):
        """view() 용(D40 ②): {'floor': {since, turns, n, w, rooms}}(이 층 집계 — 셀 게 있을 때만) +
        {'floors': [...]}(지난 층 결산 — 있을 때만). 꺼진 판엔 키 자체가 없다."""
        if not getattr(self, 'floor_on', False):
            return {}
        out = {}
        fl = bot.get('floor') or {}
        if fl.get('n') or fl.get('w'):
            since = int(fl.get('since') or 0)
            out['floor'] = {'since': since, 'turns': max(0, self.turn - since),
                            'n': dict(fl.get('n') or {}), 'w': dict(fl.get('w') or {}),
                            'rooms': len(bot.get('zones_entered') or ())}
        if bot.get('floors'):
            out['floors'] = [dict(x) for x in bot['floors']]
        return out

    def _obj_tag_obs(self, bot, f):
        """view() 용(D39): 피처 항목에 얹을 {'tag': {verb, n, note?}} — 태그 없으면 {} (구판 obs 그대로)."""
        if not getattr(self, 'objtags', False) or f.type not in OBJ_VERBS:
            return {}
        e = (bot.get('obj_tags') or {}).get(f.id)
        if not e or not e.get('n'):
            return {}
        return {'tag': {'verb': OBJ_VERBS[f.type], 'n': int(e['n']),
                        **({'note': e['note']} if e.get('note') else {})}}

    def plan_step(self, bot, bots):
        """작정(D16)의 다음 수 활성화 — **착수 시점 재검증**(D16 유일한 신규 규칙).
        유효하면 그 수(action dict)를 반환 = 두뇌 호출 없이 집행될 결정(src='plan').
        깨졌으면 계획 파기 + last=plan_broken(사유) + None 반환 → 호출측(think_all)이 같은 틱에
        LLM 재결정으로 넘어가고, 봇은 obs.last 로 '왜 깨졌는지'를 본다(조용한 건너뛰기 금지 —
        "봇은 자기 행동의 결과를 관측할 수 있어야 한다").
        검증은 '그 순간의 세계'로: goto=대상 실재 / attack=직교 인접 / interact=인접·발밑.
        explore·search 는 열린 동사 — 발동 시점 자리에서 해석되므로 언제나 유효(시야-온리 정합:
        못 본 것을 향한 작정은 좌표가 아니라 이 동사들로 표현된다)."""
        plan = bot.get('plan') or []
        if not plan:
            return None
        step = plan.pop(0)
        if self.composed_actions:
            return CA.plan_step(self, bot, step, bots)
        typ = str(step.get('type') or '')
        tgt = step.get('target')
        why = None
        if typ in ('search', 'explore', 'drink', 'wait', 'rest'):
            pass                                      # 열린 동사 — drink 유무는 발동 시점 판정(no_potion
                                                      #   이 정직 보고. 시야-온리 정합: search 선례)
        elif typ == 'goto':
            e = ((bot.get('ledger') or {}).get('statics') or {}).get(str(tgt))
            if self._resolve_target(tgt, bots, bot) is None and not (e and e.get('id')):
                why = '대상 소멸'                 # 작정의 goto 는 explore 폴백 안 탄다 —
                # (장부 귀환 목표(id 있는 것만 — trap@ 정보 항목 제외, 리뷰 픽스)는 통과:
                #  '없다'는 보지 않고는 모른다 — 가서 lost 로 확인(D17).
                #  여기서 '대상 소멸'을 알려주면 안 본 사실의 누설이다)
        elif typ == 'attack':                     #   대상이 사라졌으면 그건 새 정보다(재결정)
            res = self._resolve_target(tgt, bots, bot)
            if res is None or res[0] != 'monster':
                why = '대상 소멸'
            elif self.auto_approach:
                if self._approach_target(bot, step, bots) is None:
                    why = '대상 소멸'
            elif abs(bot['x'] - res[1][0]) + abs(bot['y'] - res[1][1]) != 1:
                why = '인접 아님'
        elif typ == 'interact':
            res = self._resolve_target(tgt, bots, bot)
            if res is None:
                why = '대상 소멸'
            elif self.auto_approach:
                if self._approach_target(bot, step, bots) is None:
                    why = '대상 소멸'
            elif abs(bot['x'] - res[1][0]) + abs(bot['y'] - res[1][1]) > 1:
                why = '인접 아님'
        else:
            why = '알 수 없는 동사'
        if why:
            bot['plan'] = []
            self._note_last(bot, {'char': bot['char'], 'type': 'plan_broken',
                                  'step': {'type': typ,
                                           **({'target': tgt} if tgt is not None else {})},
                                  'why': why})
            return None
        out = {'type': typ}
        if tgt is not None:
            out['target'] = tgt
        return out

    def _notices(self, bot):
        """D61(2026-09-12) 건물 역할 부품(메모 §4-4 [제안] "건물에 역할 부품을 붙인다") — 문턱 근처(부품 range, 기본 2칸)에
        서면 그 건물의 글이 관측에 들어간다. board(길드 게시판) = entities/quest 정의의 제목·목표·보상 문장(정보만 — 맡음·
        완료·보상 판정 없음). oracle(신전 신탁) = 러너가 state/oracle.json 에서 읽어 둔 사용자 한 줄(self.oracle) — 요청이지
        명령이 아니다, 이 캐릭터가 이미 답했으면 그 답(replied) 동봉. building_defs(피처 id → 건물 정의 id)는 build_town 이 둔다."""
        out = []
        defs = getattr(self, 'building_defs', None) or {}
        if not defs:
            return out
        orc = getattr(self, 'oracle', None)
        for fid, eid in defs.items():
            f = self.features.get(fid)
            if not f or not eid:
                continue
            try:
                comps = ENT.get(eid).get('comps') or {}
            except Exception:
                continue
            board, oracle = comps.get('board'), comps.get('oracle')
            if not (board or oracle):
                continue
            dist = max(abs(bot['x'] - f.x), abs(bot['y'] - f.y))
            if board and dist <= int(board.get('range', 2) or 2):
                items = []
                for qid in board.get('quests') or []:
                    try:
                        q = ENT.get(qid)
                    except Exception:
                        continue
                    qc = (q.get('comps') or {}).get('quest') or {}
                    items.append({'id': qid, 'title': q.get('name'), 'goal': qc.get('goal'),
                                  **({'reward': qc['reward']} if qc.get('reward') else {}),
                                  **({'client': qc['client']} if qc.get('client') else {})})
                out.append({'kind': 'board', 'building': 'f%d' % fid, 'name': f.name, 'quests': items})
            if oracle and orc and orc.get('text') and dist <= int(oracle.get('range', 2) or 2):
                mine = (bot.get('oracle_replies') or {}).get(orc.get('id'))
                out.append({'kind': 'oracle', 'building': 'f%d' % fid, 'name': f.name,
                            'id': orc.get('id'), 'text': orc['text'], 'turn': orc.get('turn'),
                            **({'replied': mine} if mine else {})})
        return out

    def _town_zone(self, x, y):
        """마을 관측(D60, 2026-09-12 파트너 "마을에서는 시야나 관측 정보를 느슨하게 줘도 될 것 같다"):
        이 칸이 속한 구역 이름(entities/map 정의의 name — 번화가·신전 지구·샛길…). layout 으로 지은 마을에만 있다
        (layout_result.spaces, 좌표는 테두리 pad 만큼 되돌려 비교). 구역이 없으면 None(옛 손그림 마을·던전)."""
        res = getattr(self, 'layout_result', None) or {}
        sp = res.get('spaces')
        if not sp:
            return None
        pad = int(res.get('pad', 0) or 0)
        lx, ly = x - pad, y - pad
        for r in sp.get('regions', []):
            for rx, ry, rw_, rh in r.get('rects', []):
                if rx <= lx < rx + rw_ and ry <= ly < ry + rh:
                    return r.get('name')
        return None

    def _ally_doing(self, b):
        """보이는 동료가 지금 고른 행동(D27 개정 2026-09-12, 파트너 "동료의 현재 어떤 행동을 선택했는지에 대한
        상태를 보여주면 될 것 같아"). 엔진이 세운 order 를 종류로 옮긴다 — 좌표('@x,y')는 '탐색'으로만(D17-4 좌표
        비노출), 사람은 char, 사물·몹은 이름+id. order 가 없으면 None(막 결정 전·서 있음). 몸짓 깃발(moving/resting/
        waiting)은 그대로 두고 이 항목이 뜻을 더한다. 발단: 재촉 발화 부검 — 이미 오는 중·곁에 선 동료에게 "빨리 와"
        (판 953220 48회 중 22, 949625 계단 장면 20+회) = 정보 제공 부족(파트너)."""
        s = str(b.get('order') or '')
        if not s:
            return None
        if s == 'wait':
            return {'act': 'wait'}
        if s == 'rest':
            return {'act': 'rest'}
        if s.startswith('follow:b'):
            return {'act': 'follow', 'target': s[len('follow:b'):]}
        if s.startswith('chase:b'):
            return {'act': 'chase', 'target': s[len('chase:b'):]}
        if s[:1] == 'b' and s[1:]:                       # 메뉴형 goto 사람(order 'b<char>' 그대로) — 같은 뜻
            return {'act': 'chase', 'target': s[1:]}
        if s[:1] == '@':
            return {'act': 'explore'}
        if s == 'exit':
            return {'act': 'goto', 'target': 'exit', 'name': '던전 입구' if self.town else '출구'}
        if self.scan and s in self.doors:
            return {'act': 'goto', 'target': s, 'name': '문'}
        if s[:1] == 'f' and s[1:].isdigit():
            f = self.features.get(int(s[1:]))
            return {'act': 'goto', 'target': s, 'name': (f.name if f else '어딘가')}
        if s[:1] == 'm' and s[1:].isdigit():
            m = next((m for m in self.monsters if m.id == int(s[1:])), None)
            return {'act': 'goto', 'target': s, 'name': (m.kind if m else '적')}   # Monster 는 kind 가 이름
        return {'act': 'goto', 'target': s}

    def _resolve_target(self, target_id, bots=None, bot=None):
        """핑 id → (kind, (x,y)). 'exit' / 'f<n>' 피처 / 'm<n>' 몹 / '@x,y' 셀(explore) / 'b<char>' 동료
        / 'd<n>' 문(D19, scan). 문은 '지나 들어서는' 쪽을 고른다 — bot(선택 인자)이 문의 한쪽 구역에
        서 있으면 반대쪽 문턱이 목표(들어서는 걸음이 처음 방 정지와 맞물려 결정 하나로 끝난다).
        엔진은 출구 위치를 늘 안다(해석은 무조건) — '보일 때만'은 obs/_valid_targets 층에서 막는다."""
        if target_id == 'exit':
            return ('exit', self.exit)
        s = str(target_id or '')
        if self.scan and s in self.doors:
            door = self.doors[s]
            here = self.zone_at.get((bot['x'], bot['y'])) if bot else None
            if here == door.zones[0]:
                return ('door', door.sides[door.zones[1]])
            if here == door.zones[1]:
                return ('door', door.sides[door.zones[0]])
            return ('door', door.sides[door.zones[0]])   # 구역 밖에서 부르면 첫쪽 문턱(결정론)
        if s[:1] == 'f' and s[1:].isdigit():
            f = self.features.get(int(s[1:]))
            return ('feature', (f.x, f.y)) if f else None
        if s[:1] == 'm' and s[1:].isdigit():
            m = next((m for m in self.monsters if m.id == int(s[1:]) and m.alive), None)
            return ('monster', (m.x, m.y)) if m else None
        if s[:1] == '@':                                   # explore 자동보행 목표(좌표 인코딩 → 재해석 가능)
            try:
                x, y = (int(v) for v in s[1:].split(','))
            except Exception:
                return None
            return ('cell', (x, y))
        if s[:1] == 'b' and bots is not None:              # 동료 핑(합류) — bots 필요
            o = next((o for o in bots if o['char'] == s[1:] and o['alive'] and not o['won']), None)
            if o is None:
                return None
            if bot is not None and not self._ally_seen(bot, o, self.visible_cells(bot['x'], bot['y'])):
                return None                                # D18 개정(09-06): 시야 밖 동료 = 사라진 것.
                # 파트너 "거리를 무시하고 동료에게 돌아가도록 한 건 내 의도가 아니야 — 시야 밖에서
                # 사라지면 말 그대로 사라지는 거야". 옛 '파티 감각'(안 보여도 산 좌표 해석)은 폐지 —
                # 남는 길은 장부의 마지막 본 자리(리모컨 '마지막 본 자리로', @x,y 칸 핑)뿐이다.
                # bot 없이 부르는 곳(자동보행 재조준·장부 소비 판정)은 엔진 내부 좌표 해석 — 그대로.
            return ('bot', (o['x'], o['y']))
        return None

    @staticmethod
    def _beside_xy(x, y, tx, ty, kind):
        """'곁' 판정(D18 A-1): 동료(bot)=체비셰프≤1(대각 포함 — 식탁 모서리도 곁이다),
        그 외(몹 등)=직교 1 유지(몹 공격창이 직교 — 대각 도착이면 못 때리는 모순 방지)."""
        ddx, ddy = abs(x - tx), abs(y - ty)
        return max(ddx, ddy) <= 1 if kind == 'bot' else ddx + ddy == 1

    def _beside(self, bot, txy, kind):
        return self._beside_xy(bot['x'], bot['y'], txy[0], txy[1], kind)

    def _swap_displaced(self, ally, mover, bots):
        """교대(D18 개정 07-17)로 밀려난 동료의 뒷정리. 좌표는 호출측(_step_order)이 이미 옮겼다.
        경로: 종점은 그대로 두고 새 자리에서 다시 깐다 — 밀려난 건 한 걸음이지 마음(order·작정)이
        아니다. 길이 사라졌으면 비워 두고, 다음 틱 _order_done/재결정이 정직하게 마감한다.
        함정·보물 재판정은 없다: 서로가 방금 서 있던 칸 = 이번 판에 밟아 확인된 땅(함정은 진입
        시점에 이미 소모(sprung), 보물은 선점됨). 자리 바뀜은 밀려난 쪽 last 에 남는다 —
        "봇은 자기 행동의 결과를 관측할 수 있어야 한다"(D1-4)의 수동태."""
        path = ally.get('path') or []
        if path:
            ex, ey = path[-1]
            ally['path'] = self.path_to(ally['x'], ally['y'], ex, ey, bots)
        self._note_last(ally, {'char': ally['char'], 'type': 'walk', 'result': 'swapped',
                               'with': mover.get('name') or mover['job']})

    def _ally_jam(self, bot, tx, ty, path, bots):
        """사회적 대우회 감지(D18) — 교대(07-17 개정) 후 역할 축소: 경로 *통과*는 동료가 못 막지만
        (ally_pass), 경로 *종점*은 동료 칸이 될 수 없어서(path_to 목표 선택) '동료가 목표의 유일
        접근칸을 점유'한 경우만 잔존 발화한다 — 그때 blocked 보고("비켜달라 말하든, 돌아가길
        택하든")는 여전히 옳은 대화 소재다(verify_fellow ⑥ 문간 장면이 정확히 이 잔존 사례).
        방금 깐 path 가 '동료 때문에' 폭증했는지 판정.
        동료 없다 치고의 최단(free)과 비교해 path 가 FACTOR배+SLACK 을 넘고, 그 free 길 위에
        살아있는 동료가 서 있으면 막는 동료 명단 반환 — 아니면 None.
        지형이 원래 먼 것(free 도 길다)·몹이 막는 것(경로 경합 규칙 별도)은 감지 대상 아님.
        부검: 라이브 22틱 — 카야가 좁은 통로 거미의 유일 접근칸을 점유 → path_to 가 19칸 서쪽
        대우회를 말없이 깔아 두란이 전장 반대편으로 행군, 그 사이 카야 사망(무목격)."""
        if not path:
            return None
        free = self.path_to(bot['x'], bot['y'], tx, ty, [])
        if not free or len(path) <= DETOUR_FACTOR * len(free) + DETOUR_SLACK:
            return None
        cells = set(free)
        jam = [o for o in bots if o is not bot and o['alive'] and not o['won']
               and (o['x'], o['y']) in cells]
        return jam or None

    def _set_order(self, bot, target_id, bots):
        """핑 목표로 BFS 경로(path_to)를 깐다 = 자동보행 준비. 목표 무효면 explore 폴백(헤맴 방지·v3).
        D18: 동료가 길목을 막아 경로가 폭증하면 말없이 행군하지 않고 blocked 로 묻는다(_ally_jam)."""
        resolved = self._resolve_target(target_id, bots, bot)   # bot=문 핑의 '들어서는 쪽' 선택(D19)
        ghost = False
        if resolved is None:
            e = ((bot.get('ledger') or {}).get('statics') or {}).get(str(target_id))
            if e and e.get('id'):       # 장부 귀환(D17)의 소비된 대상 — '기억의 좌표'로 간다.
                resolved = ('feature', (e['x'], e['y']))   # 갔더니 없으면 _order_done 이 lost 로
                ghost = True            #   정직 보고(+장부 교정) — 조용한 explore 강등 금지.
                                        #   id 없는 항목(trap@)은 핑 대상 아님(리뷰 픽스) → 아래 폴백
            else:
                if self.composed_actions:
                    bot['order'], bot['path'], bot['plan'] = None, [], []
                    return {'char': bot['char'], 'type': 'goto', 'target': target_id, 'result': 'no_target'}
                return self._set_explore(bot, None, bots)    # 무효 핑 → 탐색(출구 떠먹이기 폐기)
        tx, ty = resolved[1]
        if ghost and ((bot['x'], bot['y']) == (tx, ty)
                      or self._beside(bot, (tx, ty), resolved[0])):
            # 기억의 곁에 이미 서 있다 — 빈 자리가 눈에 보이는 거리면 걷지 않는다(lost+교정).
            # 교대(07-17) 전엔 '도달불가' 분기가 이 장면을 받았지만, 동료 통과로가 생기며
            # 헛걸음 경로가 잡히게 됐다 — 의미론을 경로 유무보다 앞세운다(verify_ledger ⑬ 계약).
            bot['ledger']['statics'].pop(str(target_id), None)
            bot['order'], bot['plan'] = None, []
            return {'char': bot['char'], 'type': 'goto', 'target': target_id,
                    'result': 'lost'}
        path = self.path_to(bot['x'], bot['y'], tx, ty, bots)
        bot['order'], bot['path'] = target_id, path
        base = {'char': bot['char'], 'type': 'goto', 'target': target_id}
        if not path:
            arrived = ((bot['x'], bot['y']) == (tx, ty)
                       or self._beside(bot, (tx, ty), resolved[0]))   # 동료만 대각 곁 인정(A-1)
            if arrived:
                bot['order'] = None
                if ghost:               # 기억의 곁까지 왔는데 실물이 없다 — 빈 자리가 눈에 보이는
                    bot['ledger']['statics'].pop(str(target_id), None)   # 거리다: lost + 교정
                    bot['plan'] = []    #   (거짓 arrived 는 D1-4 위반 + 다음 작정의 거짓 전제 — 리뷰 픽스)
                    return {**base, 'result': 'lost'}
                return {**base, 'result': 'arrived'}
            if self.composed_actions:
                bot['order'], bot['path'], bot['plan'] = None, [], []
                return {**base, 'result': 'no_path'}
            return self._set_explore(bot, None, bots)    # 도달불가 핑 → 탐색 폴백(무효핑과 대칭·재핑 livelock 차단)
        jam = self._ally_jam(bot, tx, ty, path, bots)
        if jam:                                          # 동료가 길목 점유 = 새 정보 — 멈춰 보고, 에이전트가 정한다
            bot['order'], bot['path'], bot['plan'] = None, [], []   # (비켜달라 말하든, 돌아가길 택하든)
            self._perceive(bot)                          # 멈춘 자리에서도 눈은 뜨고 — 거짓 매복 방지
            return {**base, 'result': 'blocked',
                    'allies': [{'char': o['char'], 'name': o.get('name') or o['job']}
                               for o in jam]}
        return {**base, 'result': 'pathed', 'len': len(path)}

    def _set_follow(self, bot, target_id, bots, chase=False):
        """동행(D18 A-5) 개시: order='follow:b<char>' — 곁(체비셰프≤1)을 유지하며 따라 걷는
        지속 order(도착 개념 없음 — 열린 결말이라 작정(then)을 못 잇는다, act 가 비운다).
        곁이면 이 틱은 대기부터(following), 아니면 대상 현재 좌표로 경로. 매 틱 재경로는
        _step_order 의 A-2 블록이 공유 담당. 무효/도달불가 대상은 goto 와 대칭(explore 폴백).
        · 곁 대기 중 대상이 모퉁이 너머로 사라지면(잔여 path 없음) 즉시 lost — 정직 보고.
          재개는 에이전트의 몫 — D18 개정(09-06) 뒤엔 '마지막 본 자리로'(장부 칸 핑)뿐이다.
          파티 감각(안 보여도 찾아감)은 폐지 — 시야 밖 동료는 사라진 것.
        · 상호 동행(둘이 서로 follow)은 제자리 대기 고착 — 인터럽트(몹 출현·피격)와 max_turns 가
          종결을 보장하나, 관찰되면 재론 카드(사회층에서 '누가 이끄나'로 풀 문제)."""
        s = str(target_id or '')
        tid = s if s[:1] == 'b' else 'b%s' % s           # 'b2'/'2' 관용(자유서술 흔들림 흡수)
        typ, prefix = ('goto', 'chase:') if chase else ('follow', 'follow:')   # chase = D48 개정(09-11 메모 §2-4) goto<아군> 추적
        resolved = self._resolve_target(tid, bots, bot)  # bot=시야 밖 동료면 None(D18 개정)
        if resolved is None or resolved[0] != 'bot':
            if self.composed_actions:
                return {'char': bot['char'], 'type': typ, 'target': tid, 'result': 'no_target'}
            return self._set_explore(bot, None, bots)    # 무효 대상 → 탐색(무효 핑과 대칭)
        tx, ty = resolved[1]
        base = {'char': bot['char'], 'type': typ, 'target': tid}
        bot['follow_idle'] = None                        # 개시 = 제자리 카운터 리셋(FOLLOW_IDLE)
        if self._beside(bot, (tx, ty), 'bot'):
            if chase:                                    # D48 개정 2(09-12): 곁 + 대상 정지 = 곁에 선다(이 틱 0걸음, 오류 아님)
                other = next((o for o in bots if o['char'] == tid[1:]), None)
                if other is None or not is_moving(other):
                    if bot.get('plan') or CHASE_IDLE <= 1:   # 작정이 있으면 바로 잇고, 1턴이면 이 틱만 서고 다음 틱 재판단
                        return {**base, 'result': 'arrived'}
                    bot['order'], bot['path'], bot['follow_idle'] = prefix + tid, [], (tx, ty, 1)
                    return {**base, 'result': 'beside'}
                bot['order'], bot['path'] = prefix + tid, []   # 곁인데 움직이는 중 — 붙어서 따라 걷는다
                return {**base, 'result': 'pathed', 'len': 0}
            bot['order'], bot['path'] = 'follow:' + tid, []
            return {**base, 'result': 'following'}
        path = self.path_to(bot['x'], bot['y'], tx, ty, bots)
        if not path:
            if self.composed_actions:
                bot['order'], bot['path'], bot['plan'] = None, [], []
                return {**base, 'result': 'no_path'}
            return self._set_explore(bot, None, bots)    # 도달불가 → 탐색 폴백(재핑 livelock 차단)
        jam = self._ally_jam(bot, tx, ty, path, bots)
        if jam:                                          # 동료發 대우회 — A-0과 동형 blocked
            bot['order'], bot['path'], bot['plan'] = None, [], []
            self._perceive(bot)
            return {**base, 'result': 'blocked',
                    'allies': [{'char': o['char'], 'name': o.get('name') or o['job']}
                               for o in jam]}
        bot['order'], bot['path'] = prefix + tid, path
        return {**base, 'result': 'pathed', 'len': len(path)}

    def _set_wait(self, bot, bots):
        """wait(D25, 07-24 파트너 확정 "그대로 가자"): 제자리에 있는다 — 대기 중 LLM 0콜.
        깨어남은 숫자가 아니라 사건: ①말 걸림(D24 hail 이 order 를 끊는다) ②시야에 새 존재 —
        새 몹(인카운터 문법)·새 오브젝트(sighted 문법)·동료 시야 진입(기다리던 보람)
        ③피격(기존 인터럽트) ④지루함 상한(WAIT_MAX — 아무도 오지 않는다).
        의미: 회전 셔틀의 뿌리를 뽑는 고정점 — 한 명이 서면 나머지 goto 가 움직이지 않는
        목표를 얻어 집결이 수렴한다. 숫자 인자 없음(사람은 틱을 세며 기다리지 않는다)."""
        if not self.wait_verb:
            return self._set_explore(bot, None, bots)   # 꺼진 판 — 미노출 동사(환각 방어=탐색 폴백)
        bot['order'], bot['path'] = 'wait', []
        bot['wait'] = {'n': 0,
                       'allies': {o['char'] for o in bots if o is not bot
                                  and o['alive'] and not o['won']
                                  and (o['x'], o['y']) in self.visible_cells(bot['x'], bot['y'])}}
        self._perceive(bot)                             # 서기 시작한 자리에서도 눈은 뜨고 있다
        return {'char': bot['char'], 'type': 'wait', 'result': 'waiting'}

    def _set_rest(self, bot, bots):
        """휴식(D35, 2026-09-06 파트너 확정 "지우는 조건은 캐릭터 선택지로 — 휴식. 덤으로 피가 차고
        캐릭터 간 상호작용도 가능"): **회복이 붙은 wait.** 틱마다 HP +REST_HP, 완료 = 만피 && REST_MIN 틱
        → 상태 태그(D34) 전부 소거(rested). 깨어남 = wait 와 같은 사건(말 걸림·새 몹·새 오브젝트·동료
        진입·피격) — 지루함 상한 대신 완료가 있다. 깨면 진행 리셋(다시 쉬면 처음부터). 어디서나 쉴 수
        있고 안전은 보장하지 않는다 — 시간(상한)과 노출이 세계가 청구하는 비용(PD 셈법).
        쉬는 동안 말이 오가면 hail 이 깨우고 대답한 뒤 다시 '쉰다'를 고를 수 있다 — 걷는 중엔 말이
        이동 계획을 찢었지만 쉬는 중엔 찢을 계획이 없다(D23 회의가 앉을 자연 무대)."""
        if not self.rest_verb:                          # 꺼진 판 — 미노출 동사(환각 방어=대기/탐색 폴백)
            return self._set_wait(bot, bots) if self.wait_verb else self._set_explore(bot, None, bots)
        bot['order'], bot['path'] = 'rest', []
        bot['rest'] = {'n': 0, 'healed': 0,
                       'allies': {o['char'] for o in bots if o is not bot
                                  and o['alive'] and not o['won']
                                  and (o['x'], o['y']) in self.visible_cells(bot['x'], bot['y'])}}
        self._perceive(bot)                             # 눕는 자리에서도 눈은 뜨고 있다
        return {'char': bot['char'], 'type': 'rest', 'result': 'resting', 'hp': bot['hp']}

    def _rest_tick(self, bot, bots, base):
        """휴식 틱(D35) — wait 틱 문법(시야 사건이 깨운다) + 회복 + 완료 판정. 출혈은 걸음이
        아니라 안 난다(라벨 그대로 '쉬면 멎는다'). 말 걸림·피격은 각자의 인터럽트가 order 를 끊는다."""
        newly = self._perceive(bot)
        if newly:                                     # 새 몹 — 인카운터 문법(쉬다 눈을 떴다)
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot['rest'] = None
            return {**base, 'result': 'encounter', 'woke': 'rest',
                    'monsters': [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state}
                                 for m in newly]}
        sres = self._sighted_stop(bot, base)          # 새 오브젝트도 새 일
        if sres:
            bot['rest'] = None
            return sres
        w = bot.get('rest') or {'n': 0, 'healed': 0, 'allies': set()}
        bot['rest'] = w
        here = {o['char'] for o in bots if o is not bot and o['alive'] and not o['won']
                and (o['x'], o['y']) in self.visible_cells(bot['x'], bot['y'])}
        came = here - set(w.get('allies') or ())
        if came:                                      # 동료가 시야에 — 새 존재(wait_met 문법)
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot['rest'] = None
            for o in bots:                        # 나를 기다려 줌(D36) — 도착한 쪽의 장부에
                if o['char'] in came:
                    self._bone(o, bot['char'], 'waited')
            return {**base, 'result': 'rest_met', 'allies': sorted(came)}
        w['allies'] = here
        heal = min(REST_HP, bot['maxhp'] - bot['hp'])
        if heal > 0:
            bot['hp'] += heal; w['healed'] += heal
        w['n'] += 1
        if bot['hp'] >= bot['maxhp'] and w['n'] >= REST_MIN:   # 푹 쉬었다 — 몸 상태가 낫는다
            cleared = sorted(bot.get('status') or {})
            bot['status'], bot['bleed_steps'], bot['slow_beat'] = {}, 0, 0
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot['rest'] = None
            return {**base, 'result': 'rested', 'ticks': w['n'], 'healed': w['healed'],
                    'cleared': cleared}
        return {**base, 'result': 'resting', 'hp': bot['hp']}

    def _wait_tick(self, bot, bots, base):
        """대기 틱(D25) — 제자리에서 눈만 뜨고 있는다(걸음이 아니라 사건을 본다: 맴돎 박자·
        무발견 걸음 어느 창에도 안 쌓인다 — 자연 배타). 말 걸림·피격은 각자의 인터럽트
        (hail_stop·몬스터 공격)가 order 를 끊어 깨운다 — 여기는 시야 사건과 지루함만."""
        newly = self._perceive(bot)
        if newly:                                     # 새 몹이 시야에 — 인카운터 문법 그대로
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot['wait'] = None
            return {**base, 'result': 'encounter',
                    'monsters': [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state}
                                 for m in newly]}
        sres = self._sighted_stop(bot, base)          # 새 오브젝트(드러난 함정 따위)도 새 일
        if sres:
            bot['wait'] = None
            return sres
        w = bot.setdefault('wait', {'n': 0, 'allies': set()})
        here = {o['char'] for o in bots if o is not bot and o['alive'] and not o['won']
                and (o['x'], o['y']) in self.visible_cells(bot['x'], bot['y'])}
        came = here - set(w.get('allies') or ())
        if came:                                      # 기다리던 보람 — 동료가 시야에 들어왔다
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot['wait'] = None
            for o in bots:                        # 나를 기다려 줌(D36) — 도착한 쪽의 장부에
                if o['char'] in came:
                    self._bone(o, bot['char'], 'waited')
            return {**base, 'result': 'wait_met', 'allies': sorted(came)}
        w['allies'] = here                            # 떠난 동료는 장부에서 내림 — 재진입도 새 존재
        w['n'] += 1
        if w['n'] >= WAIT_MAX:                        # 지루함 상한 — 아무도 오지 않는다
            bot['order'], bot['path'], bot['plan'] = None, [], []
            bot['wait'] = None
            return {**base, 'result': 'wait_bored', 'ticks': WAIT_MAX}
        return {**base, 'result': 'waiting'}

    def _content_keys(self, bot):
        """지금 보이는 '오브젝트' 열쇠 집합 — D19 정정 정지 신호("새 오브젝트가 시야에 들면
        멈춤, 벽·바닥 제외" — 파트너 확정)의 재료. 피처·계단·드러난 함정·문(전지성 제거로
        문도 목격 대상이 됐다). 몹은 기존 newly 인카운터 채널이 담당. 좌표는 열쇠 내부용 —
        이벤트론 이름만 나간다."""
        seen = self.visible_cells(bot['x'], bot['y'])
        ks = {('f%d' % f.id) for f in self.features.values()
              if f.type != 'exit' and not f.concealed and (f.x, f.y) in seen}
        if self.exit in seen:
            ks.add('exit')
        ks |= {('t@%d,%d' % (t.x, t.y)) for t in self.traps
               if not t.hidden and not t.sprung and (t.x, t.y) in seen}
        ks |= {did for did, dr in self.doors.items()
               if ((dr.cell in seen) if dr.cell
                   else any(s in seen for s in dr.sides.values()))}
        return ks

    def _explore_scan_plan(self, bot, direction, bots, base):
        """D19 탐색: 종점은 시야 가장자리 칸이 아니라 **명사** — 현 구역의 문(너머 안 가 본 것)과
        막다른 곳(발자국 없는 것). 단 **눈에 든 적 있는 명사만**(D19 정정 — 못 본 문은 어휘가
        아니다). 문 목표는 '지나 들어서는' 칸이라 도착이 곧 새 구역(빈 복도는 끝까지 걷는다 —
        콜은 갈림길당 하나). 후보 없으면 None 반환 → 구판 프런티어 폴백(부분 관측 공간의 안
        본 가장자리 훑기 — 전지성 제거 후 이 폴백이 수색의 몸통이다. 종결 보장도 그쪽이 진다)."""
        zid = self.zone_at.get((bot['x'], bot['y']))
        if zid is None:
            return None
        z = self.zones[zid]
        entset = bot.setdefault('zones_entered', set())
        ds = bot.get('doors_seen') or set()
        zseen = (bot.get('zone_seen') or {}).get(zid, set())
        cands = []                                    # (목표칸, 내쪽 방위)
        for did in z.doors:
            if did not in ds:
                continue                              # 못 본 문 = 모르는 문(전지성 제거)
            door = self.doors[did]
            other = door.zones[1] if door.zones[0] == zid else door.zones[0]
            if other in entset:
                continue                              # 너머를 아는 문은 '새 발견'이 아니다(발자국 계보)
            mx, my = door.cell if door.cell else door.sides[zid]
            cands.append((door.sides[other],
                          self._bearing(mx - bot['x'], my - bot['y'])))
        for (x, y) in z.deadends:
            if (x, y) in zseen and (x, y) not in self.visited:
                cands.append(((x, y), self._bearing(x - bot['x'], y - bot['y'])))
        if not cands:
            return None
        if direction:
            d = str(direction).upper()                # 방위 존중 규칙은 구판과 동일(정확 일치 우선)
            exact = [c for c in cands if c[1] == d]
            dirmatch = exact or [c for c in cands if set(d) & set(c[1])]
            if dirmatch:
                cands = dirmatch
        routed = []
        for (t, b) in cands:
            p = self.path_to(bot['x'], bot['y'], t[0], t[1], bots)
            if p:
                routed.append((t, b, p))
        if not routed:
            return None
        t, b, path = min(routed, key=lambda r: (len(r[2]), r[0]))
        return '@%d,%d' % t, path, {**base, 'result': 'pathed', 'len': len(path), 'bearing': b}

    def _remembers_exit(self, bot):
        """계단을 본 적 있나 — 평생 목격 장부(scan seen_keys) 또는 공간 장부(ledger statics 'exit')."""
        return ('exit' in (bot.get('seen_keys') or ())
                or 'exit' in (((bot.get('ledger') or {}).get('statics')) or {}))

    def _explore_door_plan(self, bot, bots, base):
        """기억 속 '너머를 안 가 본 문'(D19 개정 2026-09-06) — 본 적 있는 문(doors_seen) 가운데 건너편
        구역에 들어가 본 적 없는 것으로, 가장 가까운 문의 건너편 칸까지. 캐릭터가 아는 정보만으로 걷는
        탐색의 마지막 발 — 안 본 계단 대신 이것이 폴백이다. 반환 (order, path, res) 또는 None."""
        ent = bot.get('zones_entered') or set()
        cands = []
        for did in sorted(bot.get('doors_seen') or ()):
            door = self.doors.get(did)
            if door is None:
                continue
            for other in door.zones:
                if other in ent:
                    continue                          # 너머를 아는 문은 새 발견이 아니다
                tgt = door.sides[other]
                p = self.path_to(bot['x'], bot['y'], tgt[0], tgt[1], bots)
                if p:
                    cands.append((len(p), did, tgt, p))
        if not cands:
            return None
        _, did, tgt, path = min(cands)
        return '@%d,%d' % tgt, path, {**base, 'result': 'pathed', 'len': len(path), 'door': did}

    def _explore_frontier_plan(self, bot, bots, base):
        """기억 속 안 본 가장자리(D19 개정) — 본 바닥 칸 가운데 직교 이웃에 한 번도 못 본 칸이 있는 곳(시야
        끝에서 봤던 '저 너머'). 현 시야의 프런티어(_ways)를 봇의 평생 시야(seen_cells)로 일반화한 것 —
        캐릭터가 아는 정보만으로 걷는 마지막 발이자 종결 보장(갈 때마다 본 칸이 늘어 언젠가 소진된다).
        가까운 순(체비셰프·좌표 — 결정론)으로 첫 도달 가능 칸. 반환 (order, path, res) 또는 None."""
        scells = bot.get('seen_cells')
        if not scells:
            return None
        cx, cy = bot['x'], bot['y']
        cands = []
        for (x, y) in scells:
            if (x, y) == (cx, cy) or not (0 <= x < self.w and 0 <= y < self.h) or self.grid[y][x] == WALL:
                continue
            if any(0 <= x + dx < self.w and 0 <= y + dy < self.h and (x + dx, y + dy) not in scells
                   for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))):
                cands.append((max(abs(x - cx), abs(y - cy)), x, y))
        for _, x, y in sorted(cands):
            p = self.path_to(cx, cy, x, y, bots)
            if p:
                return '@%d,%d' % (x, y), p, {**base, 'result': 'pathed', 'len': len(p), 'frontier': True}
        return None

    def _explore_ways(self, bot, bots):
        """보이는 새 길 목록 — [(way, path)] 방위별 한 줄(D19 ②·개정 3의 종점 규칙 그대로, `_explore_plan` ②에서
        추출 — 순수 리팩터). 메뉴(D19 개정 4 방향 탐색 열거)와 계획기가 같은 목록을 본다(라벨=사실). 순수: 봇·세계 무변경."""
        seen = self.visible_cells(bot['x'], bot['y'])
        scells = bot.get('seen_cells') if self.scan else None
        bx, by = bot['x'], bot['y']

        def _unseen_edge(c):
            # D19 델타: '새 길'의 기준은 발자국이 아니라 기억 — 너머에 *한 번도 본 적 없는*
            # 칸이 있어야 발견이다. 발자국 기준은 '봤지만 안 밟은' 다 본 방 구석을 영원히
            # 새 길로 남겨 문을 나가고도 되밟으러 온다(미로 v3 육안 재론, 스폰 방 30/30 실측)
            x, y = c
            return any(0 <= x + dx < self.w and 0 <= y + dy < self.h
                       and (x + dx, y + dy) not in scells
                       for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)))
        buckets = {}                                  # 방위 → 프런티어 칸들(종점 후보 — D19 개정 3)
        for c in self._frontier_cells(bx, by, seen):
            buckets.setdefault(self._bearing(c[0] - bx, c[1] - by), []).append(c)
        fresh = []
        for w in self._ways(bx, by, seen):
            if w['visited']:
                continue                              # 발자국 있는 길은 '새 발견'이 아니다(왕복/진동 차단)
            if scells is not None and not _unseen_edge(w['cell']):
                continue
            # D19 개정 3(2026-09-06, 파트너 "탐색은 좀 더 길게 해도 될 것 같고"): 종점 = 그 방위의 **보이는
            # 가장 먼** 안 밟은 프런티어 칸("빈 복도는 끝까지 걷는다"의 열린 공간판). 구판은 방위 대표칸
            # (가장 가까운 것)이라 큰 방에선 시야 6칸에 2~3칸씩 종종걸음(실측 536184 판: 탐색 경로 중앙
            # 2칸·콜당 1칸). 새것이 보이면 D19 정지가 세우므로 멀리 잡아도 안 본 곳으로 뛰어들진 않는다.
            # 방향 선택은 그대로(_ways 순서=안 밟은 것·가까운 길 우선), 먼 칸이 못 가는 칸이면 차선·대표칸.
            far = [c for c in buckets.get(w['bearing'], [])
                   if c not in self.visited and (scells is None or _unseen_edge(c))]
            far.sort(key=lambda c: (-max(abs(c[0] - bx), abs(c[1] - by)), c))
            p = None
            for c in far[:3] + [w['cell']]:
                p = self.path_to(bx, by, c[0], c[1], bots)
                if p:
                    break
            if p:
                fresh.append((w, p))
        return fresh

    def _explore_plan(self, bot, direction, bots):
        """탐색 계획(순수 — 봇 order 무변경): (order, path, res) 또는 None(갈 곳 없음). _set_explore 가
        집행하고 view() 가 '탐색' 어휘의 유무를 이걸로 정한다(같은 논리 한 벌 — 라벨=사실).
        순서: ①D19 명사 종점(현 구역의 안 가 본 문·막다른 곳) ②보이는 새 길(프런티어) ③**계단은 본 적
        있을 때만**(기억의 계단) ④기억 속 안 가 본 문 ⑤기억 속 안 본 가장자리 ⑥없음. **D19 개정(2026-09-06, 파트너 확정 "계단을
        찾는 게 목적인데 이미 핑이 찍혀서 계속 가게 된다")**: 구판은 ②가 비면 안 본 계단으로 best-effort
        행군했다 — 머리는 모르는데 발이 아는 떠먹임(09-05 판 실측: 반경 안에 든 적 없는 계단 좌표가 order 로
        46·52틱, 뷰어엔 계단 핑으로 보임). scan 없는 판(평생 시야 장부 없음 — 구판 장부만·더미 장면)만
        구 폴백 유지(프런티어 소진=종결을 표현할 장부가 없다; 러너는 scan 기본 1)."""
        base = {'char': bot['char'], 'type': 'explore', 'target': direction or 'auto'}
        if self.explore_dirs and direction:           # D19 개정 4(09-07): 메뉴가 열거한 방위 = 그 방위의 트인 길이
            d = str(direction).upper()                #   정확히 있으면 그것이 종점(라벨=사실 — 명사 종점의 성분
            exact = [rp for rp in self._explore_ways(bot, bots) if rp[0]['bearing'] == d]   # 겹침(N→NW)에 뺏기지 않게).
            if exact:                                 #   없으면 구판 순서 그대로(명사 종점 → 새 길 → 기억).
                w, path = exact[0]
                tx, ty = path[-1]
                return '@%d,%d' % (tx, ty), path, {**base, 'result': 'pathed', 'len': len(path),
                                                   'bearing': w['bearing']}
        if self.scan:                                 # '새로 등장' 판정은 이제 order 종류 무관 —
            plan = self._explore_scan_plan(bot, direction, bots, base)   # _sighted_stop(봇 평생 장부)
            if plan is not None:
                return plan
        fresh = self._explore_ways(bot, bots)
        if fresh:
            if direction:
                d = str(direction).upper()
                # 정확 일치 우선 — 리모컨 메뉴가 준 방위(way bearing 원문)는 그대로 존중해야
                # 번호=그 행동(1:1)이 성립한다. 성분 겹침(N→N/NE/NW)은 자유서술 단문자 관용의
                # 폴백으로만(안 그러면 NE를 골라도 더 가까운 N길이 min에 이겨 의지가 전복된다).
                exact = [rp for rp in fresh if rp[0]['bearing'] == d]
                dirmatch = exact or [rp for rp in fresh if set(d) & set(rp[0]['bearing'])]
                if dirmatch:
                    fresh = dirmatch
            w, path = fresh[0]                        # _ways 순서(안 밟은 것·가까운 길 우선) = 구판 방향 선호 유지
            tx, ty = path[-1]                         # 종점 = 실제 경로 끝(먼 프런티어 칸 또는 물러선 칸)
            return '@%d,%d' % (tx, ty), path, {**base, 'result': 'pathed', 'len': len(path),
                                               'bearing': w['bearing']}
        # 새로 트인 길이 (도달 가능하겐) 없다 — 걷는 곳은 캐릭터가 아는 곳뿐(D19 개정).
        # 정직한 폴백은 평생 시야 장부(scan seen_cells)가 있어야 종결(프런티어 소진)을 보장한다 —
        # scan 없는 판(구판 장부만·더미 장면)은 그 장부가 없어 구 폴백(안 본 계단 행군)을 유지한다.
        memoryless = not self.scan
        remembered = self._remembers_exit(bot)
        if remembered or memoryless:                  # 기억의 계단(또는 기억 장치 없는 봇의 구 폴백)
            ex, ey = self.exit
            path = self.path_to(bot['x'], bot['y'], ex, ey, bots, best_effort=True)
            if path:
                tx, ty = path[-1]
                return '@%d,%d' % (tx, ty), path, {**base, 'result': 'pathed', 'len': len(path),
                                                   'to_exit': True,
                                                   **({'remembered': True} if remembered else {})}
        if self.scan:                                 # 기억 속 안 가 본 문 → 기억 속 안 본 가장자리
            return (self._explore_door_plan(bot, bots, base)
                    or self._explore_frontier_plan(bot, bots, base))
        return None

    def _set_explore(self, bot, direction, bots):
        """탐색 집행 — _explore_plan 의 계획을 봇에 싣는다. 계획이 없으면 no_path 정직 보고(+exhausted:
        보이는 새 길·기억의 계단·기억 속 안 가 본 문이 전부 없다 — 판단은 두뇌에게: 돌아가기·동료·기다리기)."""
        base = {'char': bot['char'], 'type': 'explore', 'target': direction or 'auto'}
        plan = self._explore_plan(bot, direction, bots)
        if plan is None:
            bot['order'], bot['path'], bot['plan'] = None, [], []   # 발 디딜 곳 없음 — 작정 진행 불가(D16)
            return {**base, 'result': 'no_path', **({'exhausted': True} if self.scan else {})}
        order, path, res = plan
        bot['order'], bot['path'] = order, path
        return res

    def _sighted_stop(self, bot, base, treasure=False, potion=False):
        """정지 신호(D19 정정 2026-07-15, 파트너 확정): "새 오브젝트가 시야에 들어올 때 멈춰
        판단을 구한다"(벽·바닥 제외) — order 종류 무관(goto·explore·follow 전부). 기준=봇 평생
        목격 장부 seen_keys(결정 시점 view 가 미리 채움 — 개시 때 보이던 건 '새것'이 아니다).
        몹은 encounter 채널(aware_of)이 따로 받는다. '처음 방 무조건 정지'는 폐지: 근거였던
        "진입 순간 구조가 열린다"가 전지성 제거로 소멸 — 이미 다 본 것뿐인 방은 관통한다
        (볼 게 없으면 멈출 이유도 없다). 반환: sighted 결과 dict 또는 None(새것 없음)."""
        if not self.scan:
            return None
        sk = bot.setdefault('seen_keys', set())
        fresh = self._content_keys(bot) - sk
        if not fresh:
            return None
        sk |= fresh
        bot['order'], bot['path'], bot['plan'] = None, [], []   # 새 정보 = 남은 작정 파기(D16)
        stuff = []
        for k in sorted(fresh):
            if k == 'exit':
                stuff.append({'kind': 'exit', 'name': '계단'})
            elif k[:1] == 'f':
                f = self.features.get(int(k[1:]))
                if f:
                    stuff.append({'kind': f.type, 'name': f.name, 'id': k})
            elif k[:1] == 'd':
                stuff.append({'kind': 'door', 'name': '문', 'id': k})
            else:
                stuff.append({'kind': 'trap', 'name': '함정'})
        res = {**base, 'result': 'sighted', 'seen': stuff}
        if treasure:
            res['treasure'] = True
        if potion:
            res['potion'] = True
        return res

    def step_order(self, bot, bots):
        action = bot.get('_active_action')
        res = (self._step_approach(bot, bots) if bot.get('approach') and bot.get('order')
               else self._step_order(bot, bots))
        if self.composed_actions and action:
            res['parent_action_id'] = action['action_id']
            CA.decorate(bot, action, res)
            SK.complete(self, bot, action, res)
            if not bot.get('order'):
                bot.pop('_active_action', None)
                bot.pop('_execution_refs', None)
        self._note_last(bot, res)             # 자동보행 결과도 봇의 '직전 결과'(obs.last)에 남는다
        return res

    def _step_order(self, bot, bots, approaching=False):
        """order 가 있으면 path 한 칸 전진(틱당 1칸·화면에 보임 = 스타크래프트 핑 자동보행).
        각 칸 후 인카운터 점검(전부 에지 트리거 — D2): *새로* 본 몹 / 함정 발동·발견 / 출구·도착
        → 보행 정지 + 이벤트, order 비움.
        D1 대개정("핑은 언제나, 피격은 묻는다"): 이미 알던 몹의 지속·인접은 정지 사유가 아니다 —
        알던 몹에게서 걸어 나가는 것도, 알던 몹 곁을 지나는 것도 봇의 의지대로 실행된다.
        곁의 몹이 실제로 물면 그때 피격 인터럽트(_monster_attack)가 order 를 끊고 묻는다.
        (구 pre_adj/adj_mon 정지 = 레벨 트리거 → 피른 10틱 제자리 사망의 원인. 2a 대각 셔틀의
        원 문제(교전 불발 진동)는 '봇이 멈추는 순간 몹이 물어 교전 개시'로 대체 — 스윕 실증.)
        반환: {result: walking|arrived|encounter|blocked|at_exit|treasure, ...}."""
        base = {'char': bot['char'], 'type': 'walk', 'target': bot.get('order')}
        # 움직이는 목표(몹 추격·동료 합류)의 완료 = '직교 인접 도달'. path 소진만으로는 영원히
        # 안 끝난다(목표가 매 턴 움직여 경로가 계속 갱신) — 봇이 못 멈추면 재결정이 없고, 재결정이
        # 없으면 공격도 없다: 구 정지 규칙 삭제 후 '전사 돌격 vs 추격몹'이 서로 한 대도 못 때리는
        # 위상잠금 궤도 실측(seed2, 39,5↔40,5 진동). 도착=목표상태변화 인터럽트의 한 형태(D2 정합).
        order_s = str(bot.get('order') or '')
        if order_s == 'wait':                             # wait(D25): 걸음이 아니라 사건을 본다
            return self._wait_tick(bot, bots, base)
        if order_s == 'rest':                             # 휴식(D35): 회복이 붙은 wait
            return self._rest_tick(bot, bots, base)
        follow = order_s.startswith('follow:')            # 동행(A-5): 'follow:b<char>' 지속 order
        chase = order_s.startswith('chase:')              # 추적(D48 개정, 09-11 메모 §2-4): goto<아군> — 곁+대상 정지면 해제
        tid = order_s[7:] if follow else order_s[6:] if chase else bot.get('order')
        res0 = self._resolve_target(tid, bots)
        if (follow or chase) and (res0 is None or res0[0] != 'bot'):
            bot['order'], bot['path'], bot['plan'] = None, [], []
            self._perceive(bot)               # 동행 대상 사망/하강 — 해석 실패 = lost(허탕 의미론)
            return {**base, 'result': 'lost'}
        if (not approaching and res0 and res0[0] in ('monster', 'bot')
                and self._beside(bot, res0[1], res0[0])):
            if follow or chase:               # 곁 유지 — 이 틱은 대기, order 지속(도착 개념 없음)
                bot['path'] = []
                newly = self._perceive(bot)   # 대기 중에도 눈은 뜨고 — 새 것이 보이면 멈춰 묻는다
                if newly:
                    bot['order'], bot['path'], bot['plan'] = None, [], []
                    return {**base, 'result': 'encounter',
                            'monsters': [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state}
                                         for m in newly]}
                sres = self._sighted_stop(bot, base)     # "새 일이 생기면 멈추고 묻는다"(동행 라벨
                if sres:                                 #   문구 그대로 — 몹 아닌 오브젝트도 새 일)
                    return sres
                if chase:                                # D48 개정 2: 곁 + 대상 정지 = CHASE_IDLE 틱 붙어 서다 도착(해제·재결정) / 움직이면 붙어 간다
                    other = next((o for o in bots if o['char'] == tid[1:]), None)
                    if other is None or not is_moving(other):
                        prev = bot.get('follow_idle')
                        n = (prev[2] + 1 if prev and (prev[0], prev[1]) == res0[1] else 1)
                        if bot.get('plan') or n >= CHASE_IDLE:
                            bot['order'], bot['path'], bot['follow_idle'] = None, [], None
                            return {**base, 'result': 'arrived'}
                        bot['follow_idle'] = (res0[1][0], res0[1][1], n)
                    else:
                        bot['follow_idle'] = None
                    self._wander_beat(bot)               # 곁 유지 틱도 맴돎 박자(동행과 같이)
                    return {**base, 'result': 'beside'}
                prev = bot.get('follow_idle')            # 고착 해약(FOLLOW_IDLE): 대상이 연속
                n = (prev[2] + 1 if prev and (prev[0], prev[1]) == res0[1]
                     else 1)                             #   제자리면 카운트, 움직이면 리셋
                if n >= FOLLOW_IDLE:
                    bot['order'], bot['follow_idle'] = None, None
                    return {**base, 'result': 'idle'}    # "계속 서 있네?" — 재결정으로 반환
                bot['follow_idle'] = (res0[1][0], res0[1][1], n)
                self._wander_beat(bot)                   # 곁 대기 틱도 맴돎 박자 — 회전 셔틀의 간헐 대기
                return {**base, 'result': 'following'}
            bot['order'], bot['path'] = None, []
            self._perceive(bot)               # 교전/합류 거리 도달 — 눈뜨고 재결정(거짓 매복 방지)
            return {**base, 'result': 'arrived'}
        if follow or chase:
            bot['follow_idle'] = None         # 곁 아님 = 걷는 틱 — 제자리 카운터 리셋(FOLLOW_IDLE·CHASE_IDLE)
        # A-2(D18): 시야 내 실물 재경로 — 움직이는 목표(m/b)가 지금 눈에 보이는데 경로 종점이
        # 낡았으면(현 좌표 곁이 아님) 현재 좌표로 재계산. 매 틱이어도 결정론 BFS라 비용 미미.
        # 시야 밖=마지막 본 자리 스냅샷 유지(유령 추적 정당 — 07-05 판정). 경로 소진+시야 내도
        # 재경로 대상(아니면 FLEEING 추격이 한 틱 걸러 lost 나는 술래잡기). concealed 몹 좌표로는
        # 재조준 금지(시야-온리) — 사실상 order 대상 몹은 비은닉이지만 불변식은 코드로 지킨다.
        if not approaching and res0 and res0[0] in ('monster', 'bot'):
            tx, ty = res0[1]
            mon = self.monster_at(tx, ty) if res0[0] == 'monster' else None
            # 동료 시야 면제(07-26)를 켠 판은 **여기도 같은 눈을 써야 한다**: obs 로는 동료가
            # 보이는데 재경로는 옛 시야를 보면, 눈에는 보이는데 발이 못 따라가서 마지막 본
            # 자리로 걸어가 lost 가 난다(A/B 3차 실측: 켠 판도 lost 2회로 동일했던 원인).
            _vis = self.visible_cells(bot['x'], bot['y'])
            if res0[0] == 'bot' and self.ally_sight:
                other = next((o for o in bots if (o['x'], o['y']) == (tx, ty)), None)
                seen_now = self._ally_seen(bot, other, _vis) if other else (tx, ty) in _vis
            else:
                seen_now = (tx, ty) in _vis      # 몹은 시야 그대로(인식 매트릭스 무손상)
            if seen_now and not (mon and mon.concealed):
                ex, ey = bot['path'][-1] if bot.get('path') else (bot['x'], bot['y'])
                if not self._beside_xy(ex, ey, tx, ty, res0[0]):   # 종점이 낡았다 — 실물로 재조준
                    newp = self.path_to(bot['x'], bot['y'], tx, ty, bots)
                    jam = self._ally_jam(bot, tx, ty, newp, bots)
                    if jam:                   # 재조준 경로가 동료發 대우회 — 멈춰 묻는다(A-0과 동형)
                        bot['order'], bot['path'], bot['plan'] = None, [], []
                        self._perceive(bot)
                        return {**base, 'result': 'blocked',
                                'allies': [{'char': o['char'], 'name': o.get('name') or o['job']}
                                           for o in jam]}
                    if newp:
                        bot['path'] = newp    # 재경로 실패(일시 봉쇄)면 낡은 경로 유지 — 다음 틱 재시도
        if not bot.get('path'):
            self._perceive(bot)               # 멈춘 자리에서도 눈은 뜨고 있다 — 곁의 몹을 못 본 채
            return self._order_done(bot, bots, base)  #   맞으면 거짓 매복(they-ambush)이 되므로
        if (self.status or self.skills) and '둔화' in (bot.get('status') or {}):   # 둔화(D34): SLOW_EVERY 틱에 한 칸 —
            beat = (bot.get('slow_beat') or 0) + 1                 #   나머지 틱은 제자리(몹은 따라붙는다)
            bot['slow_beat'] = beat % SLOW_EVERY
            if bot['slow_beat'] != 0:
                newly = self._perceive(bot)       # 쉬는 틱에도 눈은 뜨고 — 새 몹이면 멈춰 묻는다(D2)
                if newly:
                    bot['order'], bot['path'], bot['plan'] = None, [], []
                    return {**base, 'result': 'encounter',
                            'monsters': [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state}
                                         for m in newly]}
                sres = self._sighted_stop(bot, base)
                if sres:
                    return sres
                self._wander_beat(bot)            # 제자리 틱도 맴돎 박자(양보 틱 선례)
                return {**base, 'result': 'walking', 'slowed': True}
        nx, ny = bot['path'][0]
        ally = next((o for o in bots if o is not bot and o['alive'] and not o['won']
                     and (o['x'], o['y']) == (nx, ny)), None)
        if ally:                                      # 교대(D18 개정 07-17): 동료 칸으로 걸어 들어가면
            apath = ally.get('path') or []            # 서로 자리를 바꾼다(PD 문법) — 동료=장애물이던
            marching = (ally.get('order') and apath   # 시절의 '외길 선택지 소멸' 치료.
                        and tuple(apath[0]) != (bot['x'], bot['y']))
            memo = (ally['char'], nx, ny)
            if marching and bot.get('paced') != memo:
                bot['paced'] = memo                   # 같은 방향 행군 중인 동료 — 한 박자 양보(일렬
                self._wander_beat(bot)                #   행군). 양보 틱도 맴돎 박자(걸음 아님 — 07-24).
                return {**base, 'result': 'walking',  # 맞교대 셔틀(밀린 쪽이 되밀어 무한 왕복,
                        'paced': ally['char']}        # 50시드 실측 10판 비종결)의 치료. 같은 상황이
            bot['paced'] = None                       # 두 틱 이어지면 그때 교대 — 끼인 동료 추월 보장
                                                      # (순환 대기 고리도 한 틱 뒤 반드시 풀림).
            ally['x'], ally['y'] = bot['x'], bot['y']
            self._swap_displaced(ally, bot, bots)     # 밀려난 쪽 경로 재계산+자기 관측(last). 아래
            base['swap'] = {'char': ally['char'],     # _enter_cell 이 내 이동을 마저 처리.
                            'name': ally.get('name') or ally['job']}
        if not self.walkable(nx, ny, bots):           # 길이 막힘(몹 끼어듦 — 동료는 위 교대가 소화)
            blocker = self.monster_at(nx, ny)
            if blocker and blocker.alive and not blocker.concealed:
                # 다음 칸을 *보이는 몹*이 점거 = 경로 경합. 새 정보이므로 멈춰 보고하고 에이전트가
                # 정한다(싸울지 돌아갈지). 구식 '조용한 재경로'는 정보 은폐(D1-4 위반)였고, 춤추는
                # 몹과의 재경로 술래잡기 livelock 실측(seed4: 그림자거미 문간 댄스 — 봇이 못 멈추면
                # 몹도 못 문다). concealed 몹 점거는 아래 재경로로 폴스루(멈추면 존재 누설).
                bot['order'], bot['path'], bot['plan'] = None, [], []   # 경로 경합=새 정보 — 작정 파기
                self._perceive(bot)           # 길을 막은 몹을 봤다 — 거짓 매복 방지
                return {**base, 'result': 'blocked',
                        'monsters': [{'id': 'm%d' % blocker.id, 'kind': blocker.kind,
                                      'state': blocker.state}]}
            res = self._resolve_target(tid, bots, bot)         # 은닉몹 점거 → 재경로 1회
                                                               #   (동행이면 tid='b<char>' — 원 대상.
                                                               #    bot=문 핑의 들어서는 쪽 유지, D19)
            if approaching:
                bot['path'] = self._approach_path(bot, bot['approach'], res, bots) if res else []
            else:
                bot['path'] = self.path_to(bot['x'], bot['y'], res[1][0], res[1][1], bots) if res else []
            jam = (self._ally_jam(bot, res[1][0], res[1][1], bot['path'], bots)
                   if res else None)          # 교대(07-17) 후 동료發 대우회는 발화 불능 — 은퇴 코드
            if (not bot['path'] or jam
                    or not self.walkable(*bot['path'][0], bots, ally_pass=True)):
                bot['order'], bot['path'], bot['plan'] = None, [], []   # 막힘=새 정보 — 작정 파기
                self._perceive(bot)           # blocked 정지도 눈은 뜨고 — 거짓 매복 방지(위와 동일)
                out = {**base, 'result': 'blocked'}
                if jam:
                    out['allies'] = [{'char': o['char'], 'name': o.get('name') or o['job']}
                                     for o in jam]
                return out
            nx, ny = bot['path'][0]
        d21 = self.scan and self.selfstop             # D21 자기 관찰(재회·맴돎) — scan 장부가 재료
        dry_on = self.scan and self.dry_signal        # 무발견 신호(07-24) — 같은 장부가 재료
        pre_seen = len(bot.get('seen_cells') or ()) if (d21 or dry_on) else 0
        bot['path'].pop(0)
        enter = self._enter_cell(bot, nx, ny, bots)   # 이동 + 보물/계단/함정 처리
        base.update(to=[nx, ny])
        if enter.get('bleed'):
            base['bleed'] = enter['bleed']            # 출혈(D34) 걸음 — 이 걸음의 어떤 결과에도 병기
        if enter.get('door'):
            base['door'] = enter['door']              # 문 사용(D40) — 이 걸음이 문 타일을 밟았다(스트림 additive)
        if not bot['alive']:                          # 함정 즉사·출혈사 — 시체는 지각하지 않는다(사후 인지굴림 금지:
            bot['order'], bot['path'], bot['plan'] = None, [], []   # 죽은 자의 주사위가 숨은 것을 드러내
                                                      #   산 자 경로를 바꿈. 작정도 죽음과 함께 소멸
            res = {**base, 'result': 'encounter'}
            if enter.get('trap'):
                res['trap'] = enter['trap']
            if enter.get('treasure'):                 # 죽으며 주운 보물도 진실(원장)에 남긴다 — 지금은 보물·함정
                res['treasure'] = True                #   동칸 배치가 없어 dormant이나, 배치 규칙 변경 즉시 발화
            if enter.get('potion'):
                res['potion'] = True
            return res
        if enter.get('at_exit') and (str(bot.get('order') or '') == 'exit'      # 계단 도착 — 하강/탈출은 interact(파티 조율)로.
                                     or not bot.get('exit_seen_at_order')):   #   09-08 D45: 결정 때 보이던 계단을 딴 목표로 지나는 건 안 선다
            self._perceive(bot)                       # 계단 위에서도 눈은 뜨고 있다(생략하면 뻔히 보이는
            bot['order'], bot['path'] = None, []      #   적의 공격이 '매복' 판정되는 거짓 they-ambush)
            return {**base, 'result': 'at_exit'}
        newly = self._perceive(bot)                   # 이동으로 새로 보인 몹 = aware_of 등록(처음 본 것만)
        found = self._passive_search(bot, bots)       # 직업 인지 스윕(수동 search-on-move) — 숨은 것 발견
        reunion = None
        if self.scan:                                 # 구역 발자국(been 어휘·장부 재료 — 정지와 무관.
            zid = self.zone_at.get((nx, ny))          #   D19 정정: '처음 방 무조건 정지'는 폐지 —
            if zid is not None:                       #   정지는 _sighted_stop 이 오브젝트 목격으로 판단)
                ent = bot.setdefault('zones_entered', set())
                if d21:                               # 재회(D21①): 아는 구역에 *새 연결*로 들어섰다 —
                    ctx = bot.get('zone_ctx')         #   고리의 정보 가치=연결의 발견을 사건으로 승격.
                    if ctx is not None and ctx != zid:
                        edge = frozenset((ctx, zid))  #   에지=무방향 구역쌍. 같은 문 왕복(정당한 재방문 —
                        known = bot.setdefault('zone_edges', set())   #   과제약 금지)은 첫 통과 때
                        if edge not in known:         #   적혀 다시 안 울린다. 새 에지+가 본 구역=재회.
                            known.add(edge)
                            if zid in ent:
                                reunion = self._zone_name(bot, zid)
                    bot['zone_ctx'] = zid             # 문턱(구역 없음) 체류 중엔 직전 구역이 유지된다
                ent.add(zid)
        wander_hit = False
        if d21:                                       # 맴돎(D21②) 창 부기: 결정 없이 이어 걸은 걸음들.
            run = bot.get('wander')                   #   새로 본 칸이 생기면 창이 접히고(발견=맴돎 아님),
            if len(bot.get('seen_cells') or ()) > pre_seen:   #   act()의 새 결정도 창을 접는다.
                bot['wander'] = None
            else:
                if not run:
                    run = bot['wander'] = {'cells': set(), 'n': 0}
                wander_hit = (nx, ny) in run['cells']  # 이 걸음이 '되밟기'인가 — 직행 관통과의 분별
                run['cells'].add((nx, ny))
                run['n'] += 1
        if dry_on:                                    # 무발견 신호: 마지막 새 목격 이후 걸음 수 —
            if len(bot.get('seen_cells') or ()) > pre_seen:   #   결정(act)은 리셋 안 함(맴돎과 다름,
                bot['dry'] = 0                        #   "마지막 새 목격 이후"가 자의 전부).
                bot['dry_hit'] = False                # 새 목격 = 리셋 + 미배달 신호 파기(그 사이
            else:                                     #   발견이 생겼으면 낡은 사실 — 배달 금지)
                bot['dry'] = bot.get('dry', 0) + 1
                if bot['dry'] == DRY_K:               # 도달 '시점'만(== — 축적·연사 없음). 재무장은
                    bot['dry_hit'] = True             #   리셋 뒤 다시 K걸음
                    base['dry'] = bot['dry']          # 계측: 이 걸음 결과 이벤트에 실림(부검 열)
        if enter.get('trap') or newly or found:       # 인카운터 = *새 정보*만(에지) — 알던 몹 인접은
            bot['order'], bot['path'], bot['plan'] = None, [], []   # 정지 사유 아님(D1 개정: 물리면
                                                      #   그때 묻는다). 새 정보 = 남은 작정 파기(D16)
            res = {**base, 'result': 'encounter'}
            if enter.get('trap'):
                res['trap'] = enter['trap']
            if enter.get('treasure'):
                res['treasure'] = True                # 같은 걸음의 보물 획득도 진실에 남긴다(GM 서사용)
            if enter.get('potion'):
                res['potion'] = True
            if found:
                res['found'] = found                  # 인지로 드러난 것들("잠깐, 함정이야!")
            if newly:
                res['monsters'] = [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state}
                                   for m in newly]
            if self.scan:                             # 같은 걸음의 목격도 장부에 — 인카운터가 삼킨
                bot.setdefault('seen_keys', set()).update(self._content_keys(bot))   # 새것이 다음
            return res                                #   걸음에 유령 sighted 로 재발화하지 않게
        sres = self._sighted_stop(bot, base, treasure=bool(enter.get('treasure')),
                                  potion=bool(enter.get('potion')))
        if sres:                                      # D19 정정: "새 오브젝트가 시야에 들면 멈춤"
            return sres                               #   (벽·바닥 제외) — order 종류 무관 단일 원칙
        if reunion:                                   # 재회 정지(D21①) — 새 오브젝트가 우선(sighted 가
            bot['order'], bot['path'], bot['plan'] = None, [], []   # 먼저 물으면 에지만 적고 양보),
            bot['wander'] = None                      # 정지=재결정이 온다 — 맴돎 창도 접는다
            res = {**base, 'result': 'reunion', 'name': reunion}
            if enter.get('treasure'):
                res['treasure'] = True
            if enter.get('potion'):
                res['potion'] = True
            return res
        if enter.get('treasure'):
            if not bot['path']:                       # 목표 칸의 보물을 주움 = 이 order 의 완결(자기 소비).
                bot['order'] = None                   #   남겨두면 다음 틱 빈 자리에 lost/arrived 거짓 보고
            return {**base, 'result': 'treasure'}     # 보물은 줍고 계속 자동보행(안 멈춤)
        if enter.get('potion'):                       # 물약도 보물 문법 그대로 — 줍고 계속(자기 소비 완결)
            if not bot['path']:
                bot['order'] = None
            return {**base, 'result': 'potion'}
        run = bot.get('wander')                       # 맴돎 정지(D21②) — 관찰 사실만 보고,
        ripe = bool(run and wander_hit and run['n'] >= WANDER_N)   # 판단은 두뇌 몫(질문·조향 금지)
        if not bot['path']:
            res = self._order_done(bot, bots, base)
            if ripe and res.get('result') in ('following', 'beside'):   # 곁 도달로 경로가 끝나도 follow/chase 는
                bot['order'], bot['path'], bot['plan'] = None, [], []   # 무결정 지속 — 이 걸음이
                steps = run['n']                      #   되밟기+N이면 맴돎이 우선(07-24 둘째 구멍:
                bot['wander'] = None                  #   한 칸 추격의 마지막 걸음이 관문을 건너뜀).
                return {**base, 'result': 'wander', 'steps': steps}   # arrived/lost=재결정이라 그대로
            return res
        if ripe:                                      # 3인 회전 셔틀(07-20, 결정 0 ~50틱)의 그물 —
            bot['order'], bot['path'], bot['plan'] = None, [], []   # 금지가 아니라 정지+사실 제시
            steps = run['n']
            bot['wander'] = None
            return {**base, 'result': 'wander', 'steps': steps}
        return {**base, 'result': 'walking'}

    def _wander_beat(self, bot):
        """맴돎 창(D21②)의 시간 부기 — 걸음 없이 지나가는 작정 틱(follow 곁 대기·paced 양보)도
        박자로 센다(07-24 수선, 큰 판 부검: swap 셔틀=걸음이 5틱에 1개꼴 → N=10걸음이 48틱 지연).
        제자리 틱은 이동이 없어 새 목격이 생길 수 없으므로 무조건 쌓인다 — 정지 판정
        (되밟기 + n>=WANDER_N)은 여전히 실제 걸음에서만 일어난다."""
        if not (self.scan and self.selfstop):
            return
        run = bot.get('wander')
        if not run:
            run = bot['wander'] = {'cells': set(), 'n': 0}
        run['n'] += 1

    def hail_stop(self, bot, froms):
        """말 걸림 정지(07-24 파트너 확정 — 여섯 번째 정지 신호, D24): 시야 안 동료의 말이
        들리면 걷던 작정을 멈추고 결정권을 받는다 — 걷다가 누가 부르면 멈춰 돌아보는 것.
        강제 응답 아님(관찰 제시+판단 위임, 처방 사다리 ③ — 답할지 무시할지는 두뇌 몫).
        누가 듣나(배달 규칙)는 러너 inbox 가 소유 — 여기는 '들렸으니 멈춘다'의 물리만.
        수다 루프 방어 = 같은 발화자 쿨다운(HAIL_CD, 쌍 단위·내용 아닌 구조 — 자유 텍스트를
        엔진이 읽는 이름 파싱은 뒷문이라 기각·파트너 확정). 쿨다운 중엔 정지만 없을 뿐 메시지는
        기존대로 배달된다. 반환 = 정지 성사 시 froms(계측·관전), 아니면 []."""
        if not (self.hail and bot.get('order') and bot['alive'] and not bot['won']):
            return []
        cd = bot.setdefault('hail_cd', {})
        fresh = [c for c in froms if self.turn >= cd.get(c, 0)]
        if not fresh:
            return []
        for c in froms:                    # 정지 성사 = 이번에 들린 발화자 전원 쿨다운 갱신
            cd[c] = self.turn + HAIL_CD
        if self.social:
            # 채널 분리(2026-07-26): **작정을 부수지 않는다.** 걷던 몸은 계속 걷고, 다음 틱에
            # 사교 콜만 열린다 — 걸으면서 대답하는 것이 사람이다.
            # 왜 파괴가 있었나: 콜이 '작정 없는 봇'에게만 열려서, 말을 들으려면 작정을 부수는
            # 것 말고 길이 없었다(D24). 그 부작용이 목적 상실이었다 — 07-26 부검에서
            # 작정 파기 직후 follow 46% vs 평상시 29%. 사교 콜이 그 결합을 푼다.
            bot['hailed'] = list(froms)
            bot['last'] = {'type': 'hail', 'result': 'heard', 'froms': list(froms)}
            self._trail_add(bot, bot['last'])   # D38 궤적 — 말 걸림도 자기 경험
            return fresh
        bot['order'], bot['path'], bot['plan'] = None, [], []   # 인터럽트 문법(D16) — 작정 파기
        bot['last'] = {'type': 'hail', 'result': 'hailed', 'froms': list(froms),
                       **self._cancel_approach(bot)}
        self._trail_add(bot, bot['last'])       # D38 궤적 — 말 걸림도 자기 경험
        return fresh

    def _order_done(self, bot, bots, base):
        """경로 소진 마감 보고. 움직이는 목표(몹 m·동료 b)는 '지금 정말 곁에 있나'로, 소모성
        피처(f — 동료가 먼저 주울/열 수 있다)는 '아직 실재하나'로 정직 판정 — 마지막 본
        자리(유령 좌표)까지 갔는데 대상이 없으면 arrived 가 아니라 **lost** 다.
        (07-05 부검 → 파트너 판정: 스냅샷 좌표 추적 자체는 사람의 추적과 같아 옳다. 결함은
        허탕을 성공처럼 보고하던 의미론뿐 — D1-4 "봇은 자기 행동의 결과를 관측할 수 있어야 한다".
        대상이 죽었거나 층을 떠난 경우도 해석 실패 → lost. lost 의 뜻은 '곁에 없다'까지다 —
        곁 = 몹은 직교 1(공격창), 동료는 체비셰프 1(대각 포함 — D18 A-1, _beside).
        구판(07-05~07-10)은 동료도 직교만 곁으로 쳐서 대각 비껴섬이 lost 로 났다.
        exit·탐색 셀(@)은 자리 자체가 목표라 무조건 arrived. 자기가 주운 보물은 여기 안 온다 —
        step_order 의 treasure 분기가 path 소진 시 order 를 그 자리에서 완결한다.)"""
        if bot.get('approach'):
            # 접근 경로 끝은 LLM 재결정점이 아니다. 다음 틱에 거리·대상·새 사건을 다시 확인한다.
            return {**base, 'result': 'arrived', 'approach_status': 'ready'}
        s = str(base.get('target') or '')
        if s.startswith('follow:') or s.startswith('chase:'):   # 동행(A-5)·추적(D48 개정): 경로 소진은 완결이 아니다 —
            chase = s.startswith('chase:')
            tid = s[6:] if chase else s[7:]
            res = self._resolve_target(tid, bots)
            if res and self._beside(bot, res[1], 'bot'):
                if chase:                             #   추적(D48 개정 2): 곁 + 대상 정지 = CHASE_IDLE 틱 붙어 서다 도착, 움직이면 붙어 간다
                    other = next((o for o in bots if o['char'] == tid[1:]), None)
                    if other is None or not is_moving(other):
                        prev = bot.get('follow_idle')
                        n = (prev[2] + 1 if prev and (prev[0], prev[1]) == res[1] else 1)
                        if bot.get('plan') or n >= CHASE_IDLE:
                            bot['order'], bot['path'], bot['follow_idle'] = None, [], None
                            return {**base, 'result': 'arrived'}
                        bot['follow_idle'] = (res[1][0], res[1][1], n)
                bot['path'] = []                      #   곁이면 지속(다음 틱 대기/재경로)
                return {**base, 'result': 'beside' if chase else 'following'}
            bot['order'], bot['path'], bot['plan'] = None, [], []
            return {**base, 'result': 'lost'}         #   유령 좌표 허탕/대상 소멸 — 동행 끝
        bot['order'], bot['path'] = None, []
        if s[:1] in ('m', 'b') and s[1:]:
            res = self._resolve_target(base['target'], bots)
            if not (res and self._beside(bot, res[1], res[0])):
                bot['plan'] = []                      # 허탕 = 세계가 변했다 — 남은 작정도 근거 상실(D16)
                return {**base, 'result': 'lost'}
        elif s[:1] == 'f' and s[1:].isdigit():
            if self._resolve_target(base['target'], bots) is None:   # 삭제(동료 소비) = 빈 자리
                bot['plan'] = []
                if bot.get('ledger') is not None:     # 갔더니 없다 — 장부도 경험으로 교정(D17,
                    bot['ledger']['statics'].pop(s, None)   # 재유혹 방지. _ledger_note 교정의 앵커)
                return {**base, 'result': 'lost'}
        return {**base, 'result': 'arrived'}          # arrived 는 작정 존속 — 다음 수가 이어진다

    def _enter_cell(self, bot, nx, ny, bots=()):
        """한 칸 진입 = 좌표 갱신 + (보이는) 보물 줍기 + 계단 도착 + 숨은 함정 DEX 판정. 플래그 dict 반환.
        Stage 4: 출구 밟기 = 즉시탈출 아님(at_exit 만) — 하강/탈출은 interact + 파티 조율(_interact)로.
        Stage 3: 드러난 함정을 알고 밟으면 조심 보너스(CAREFUL_BONUS). 경보 함정은 층의 몹을 깨운다."""
        bot['x'], bot['y'] = nx, ny
        self.visited.add((nx, ny))
        out = {}
        if (self.status or self.skills) and '출혈' in (bot.get('status') or {}):   # 출혈(D34): 걸음이 피를 낸다 —
            bot['bleed_steps'] = bot.get('bleed_steps', 0) + 1     #   제자리·전투·휴식은 안 낸다(라벨 그대로).
            if bot['bleed_steps'] % BLEED_STEPS == 0:              #   인터럽트 아님(D2 — 태그가 붙던 순간의
                bot['hp'] -= 1                                     #   함정/피격이 이미 멈춰 물었다)
                out['bleed'] = {'hp': bot['hp']}
                if bot['hp'] <= 0:                                 # 걷다 쓰러짐 — 묘·목격 문법 그대로
                    bot['alive'] = False; out['bleed']['down'] = True
                    g = self._on_down(bot, bots, by='출혈', by_kind='status')
                    if g:
                        out['bleed']['grave'] = g
                    return out                                     # 죽은 자는 줍지도 밟지도 않는다
        if self.scan:                             # D30(09-05) 오브젝트 사용 목격 — 첫 사례=문 타일(+).
            dr = next((dd for dd in self.doors.values() if dd.cell == (nx, ny)), None)
            if dr is not None:                    # 밟는 순간 1회(너머로 내려서는 걸음은 안 온다). 트임
                out['door'] = dr.id               # D40(09-06): 자기 자신의 문 사용도 같은 순간 — 걸음 결과에 병기
                self._witness(bots, nx, ny,       #   (cell 없는 문)은 빛을 안 막아 동료가 사라지지 않으니
                              {'kind': 'ally_use', 'char': bot['char'],   # 대상 아님. 교대(swap)로 밀려난
                               'what': '문', 'id': dr.id},                 # 동료는 여기 안 온다(지나간 게
                              exclude=(bot['char'],))                      # 아니다). 문장은 brains 가 쓴다.
        tf = self.feature_at(nx, ny, 'treasure')
        if tf and not tf.concealed:               # 숨은 보물은 밟아도 모른다 — 인지로 드러나야 줍는다
            del self.features[tf.id]; bot['bag'] += 1; out['treasure'] = True
            self._witness(bots, nx, ny,           # 전달층(D22 확장 07-29): 획득도 목격 — 보물이 눈앞에서
                          {'kind': 'ally_loot', 'char': bot['char'], 'what': '보물'},
                          exclude=(bot['char'],))  # 사라지는 걸 본 사람은 누가 가져갔는지도 본 사람이다
        pf = self.feature_at(nx, ny, 'potion')
        if pf and not pf.concealed:               # 회복 물약(07-17): 보물과 같은 줍기 문법(밟으면 소지)
            del self.features[pf.id]
            bot['potions'] = bot.get('potions', 0) + 1
            out['potion'] = True
            self._witness(bots, nx, ny,
                          {'kind': 'ally_loot', 'char': bot['char'], 'what': '물약'},
                          exclude=(bot['char'],))
        if (nx, ny) == self.exit:
            out['at_exit'] = True
        trap = next((t for t in self.traps if t.x == nx and t.y == ny and not t.sprung), None)
        if trap:
            careful = 0 if trap.hidden else CAREFUL_BONUS   # 아는 함정을 어쩔 수 없이 건널 땐 조심조심
            r = self.d20(); total = r + bot['dex'] + careful; safe = total >= trap.dc
            trap.hidden = False; trap.sprung = True
            tr = {'kind': trap.kind, 'name': trap.name,
                  'roll': r, 'mod': bot['dex'] + careful, 'total': total, 'dc': trap.dc, 'safe': safe}
            if not safe:
                if trap.kind == 'alarm':          # 경보! 층의 몹 일제 각성(justAlerted = 굴림 우회)
                    tr['alarm'] = self._ring_alarm(bot)
                if trap.dmg:
                    bot['hp'] -= trap.dmg; tr['dmg'] = trap.dmg; tr['hp'] = bot['hp']
                    if bot['hp'] <= 0:
                        bot['alive'] = False; tr['down'] = True
                        g = self._on_down(bot, bots, by=trap.name, by_kind='trap')
                        if g:
                            tr['grave'] = g
                st = TRAP_KINDS.get(trap.kind, {}).get('status')
                if st and bot['alive']:           # 함정의 특수(D34): 가시=출혈·독침=중독 — 피해와 별개
                    if self._apply_status(bot, st, trap.name, bots, by_kind='trap'):
                        tr['status'] = st
            if bot['alive']:                      # 전달층(D22): 함정 장면 목격 — 전사면 ally_down 이 담당
                self._witness(bots, nx, ny,
                              {'kind': 'ally_trap', 'char': bot['char'], 'trap': trap.name,
                               'safe': safe, **({'dmg': trap.dmg} if not safe and trap.dmg else {})},
                              exclude=(bot['char'],))
            out['trap'] = tr
        return out

    def _ring_alarm(self, bot):
        """경보 함정: 층의 모든 비은닉 몹이 굴림 없이(justAlerted) HUNTING — 발원지로 몰려온다.
        함정이 인식 시스템에 결합되는 지점. 매복몹(concealed)은 원래 도사린 채이므로 제외."""
        woken = 0
        for m in self.monsters:
            if not m.alive or m.concealed:
                continue
            if m.state in ('SLEEPING', 'WANDERING'):      # 자던/배회하던 놈만 '각성'으로 센다
                m.state, m.waking = 'HUNTING', 0          # 경보로 깬 몹은 완전 각성(취약창 없음)
                m.target, m.last_seen, m.lost = bot['char'], (bot['x'], bot['y']), 0
                woken += 1
            elif m.state == 'HUNTING':                    # 이미 추격중 → 발원지로 방향만 갱신
                m.target, m.last_seen, m.lost = bot['char'], (bot['x'], bot['y']), 0
            # FLEEING/desperate 는 안 건드린다 — 도주 시계(flee_turns) 리셋·중복 연출 방지
        return woken

    def _passive_search(self, bot, bots=()):
        """수동 search-on-move(SPD 능동/수동 분리의 수동쪽): 자동보행 칸마다 인지 반경(search_r) 내
        '보이는' 숨은 것들에 d20+DEX ≥ DC 굴림. 도적(반경2·DEX+3)이 압도적 = 직업 인지의 몸통.
        드러난 것 목록 반환(step_order 가 인카운터로 정지 → "잠깐, 함정이야!" 장면)."""
        r = bot.get('search_r', 1)
        seen = self.visible_cells(bot['x'], bot['y'], r)
        bot.setdefault('searched', set()).update(seen)   # 자기 행동 기억(리모컨 라벨 근거)
        cx, cy = bot['x'], bot['y']
        found = []
        for t in self.traps:
            if t.hidden and not t.sprung and (t.x, t.y) in seen:
                if self.d20() + bot['dex'] >= PASSIVE_DC:
                    t.hidden = False
                    found.append({'kind': 'trap', 'name': t.name,
                                  'bearing': self._bearing(t.x - cx, t.y - cy)})
                    self._witness(bots, t.x, t.y,   # 전달층(D22 확장 07-29): 발견도 목격 — 갑자기
                                  {'kind': 'ally_spot', 'char': bot['char'],   # 나타난 함정의 사연.
                                   'what': t.name},                # 판정 칸=드러난 물건의 자리(변화가
                                  exclude=(bot['char'],))          # 일어난 칸을 본 사람이 이유를 안다)
        for f in list(self.features.values()):
            if f.concealed and (f.x, f.y) in seen:
                if self.d20() + bot['dex'] >= (f.perception_gate or PASSIVE_DC):
                    f.concealed = False
                    found.append({'kind': f.type, 'name': f.name,
                                  'bearing': self._bearing(f.x - cx, f.y - cy)})
                    self._witness(bots, f.x, f.y,
                                  {'kind': 'ally_spot', 'char': bot['char'], 'what': f.name},
                                  exclude=(bot['char'],))
        for m in self.monsters:
            if m.alive and m.concealed and (m.x, m.y) in seen:
                if self.d20() + bot['dex'] >= LURK_DC:
                    m.concealed = False
                    bot['aware_of'].add(m.id)     # 정체를 봤다 → 매트릭스 봇쪽 비트 = we-ambush 가능
                    found.append({'kind': 'monster', 'name': m.kind, 'id': 'm%d' % m.id,
                                  'bearing': self._bearing(m.x - cx, m.y - cy)})
                    self._witness(bots, m.x, m.y,   # 몹 이름은 mon 필드 — 목격자 도감 게이트를 탄다
                                  {'kind': 'ally_spot', 'char': bot['char'], 'mon': m.kind},
                                  exclude=(bot['char'],))
        return found

    def _zone_label(self, x, y):
        """구역 어휘(D17-2) — 좌표의 '주소'. 방=안정 id(생성 순서), 그 외 바닥=통로.
        방 타입(entrance/exit)은 안 싣는다 — '계단 방' 라벨은 안 본 계단의 존재를 누설(시야-온리).
        D19(scan): 주소도 스캐너의 기하 구역으로 — 출생기록 주소(from_ascii=전부 '방 r0')의 치료.
        통로도 id 를 얻는다('통로 c1') — 격자가 준 정체성이라 장부 지칭이 또렷해진다."""
        if self.scan:
            zid = self.zone_at.get((x, y))
            if zid is None:                         # 구역 밖 = 문턱(문 타일) 또는 방어적 기본
                return '문턱' if self.grid[y][x] == DOOR else '통로'
            z = self.zones[zid]
            return ('%s %s' % (z.kind, zid)) if z.kind == '방' else ('통로 %s' % zid)
        rid = self._room_id_at(x, y)
        return ('방 r%d' % rid) if rid is not None else '통로'

    def _zone_name(self, bot, zid):
        """구역의 사람말 이름(D21) — "샘 있던 방"처럼 *그 봇의 기억(장부)*으로 부른다.
        내용물(내가 본 정적 목격물) 우선, 없으면 크기(다 본 공간만 — D19 정직 규율),
        그도 없으면 종류만. 좌표·번호 id 금지(이름=사람의 공간 언어 — 정본 D21).
        장부 없음(DUNGEON_LEDGER=0)이면 종류 폴백 — 굴림 없음, 읽기 전용."""
        z = self.zones[zid]
        label = ('%s %s' % (z.kind, zid)) if z.kind == '방' else ('통로 %s' % zid)
        led = bot.get('ledger') or {}
        for e in (led.get('statics') or {}).values():   # 가장 먼저 목격한 지물 하나로 부른다
            if e.get('zone') == label and e.get('name'):   # ("샘 있던 방" — 목록 나열은 사람말이 아니다)
                return '%s 있던 %s' % (e['name'], z.kind)
        zseen = (bot.get('zone_seen') or {}).get(zid, set())
        if z.cells <= zseen:                        # 다 본 공간만 크기를 안다("일부만 봤으면 모른다")
            if z.kind == '방':
                area = z.w * z.h
                return '넓은 방' if area >= 30 else ('작은 방' if area <= 12 else '방')
            return '긴 통로' if len(z.cells) >= 10 else '통로'
        return z.kind

    def _ledger_note(self, bot, seen, bots=None):
        """공간 장부(D17-1) 갱신 — 시야에 든 것을 엔진이 캐릭터 명의로 받아 적는다.
        '본 것만' 등재(시야-온리의 기억판 — 림월드 전지적 인지 불수입). bot['ledger'] 가
        None(기본)이면 무동작 = 하위호환 솔기(도감 known=None 선례). 굴림 없음(순수 파생)·멱등.
        · statics: 제자리 물건(피처·계단·드러난 함정) — 최초 목격 turn 고정. **교정**: 그 자리가
          다시 보이는데 물건이 없으면 잊는다(기억은 경험으로 고쳐진다 — 동료가 먼저 소비한 상자).
          함정은 id 가 없어 정보 항목만(핑 불가). 계단(exit)은 소멸하지 않아 교정 제외.
        · moving: 움직이는 것(몹·동료)의 마지막 목격 — 갱신형. 시야 밖 이동은 안 따라간다
          (현재 좌표 추적=월핵). 낡은 기억의 허탕은 lost 정직화가 받는다("갔더니 없음=드라마").
        · zones: 방문 구역(내가 선 방). 장부의 좌표(x,y)는 엔진만 쥔다 — obs 로는 구역·때만
          나간다(D17 정식화: 6/29에 죽인 건 LLM 좌표 운전이지 기억이 아니다)."""
        led = bot.get('ledger')
        if led is None:
            return
        t = self.turn
        for k, e in list(led['statics'].items()):     # 교정 먼저 — 이번 시야가 기억을 반증하면 삭제
            if (e['x'], e['y']) not in seen or e['type'] == 'exit':
                continue
            if e['type'] == 'trap':
                tr = next((x for x in self.traps if (x.x, x.y) == (e['x'], e['y'])), None)
                if tr is None or tr.sprung:           # 발동돼 소진된 함정은 더는 위협이 아니다
                    del led['statics'][k]
            elif self.feature_at(e['x'], e['y']) is None:
                del led['statics'][k]
        for f in self.features.values():              # 정적 목격물 — 시야에 든 순간 등재
            if not f.concealed and (f.x, f.y) in seen:
                k = 'exit' if f.type == 'exit' else 'f%d' % f.id
                if k not in led['statics']:
                    led['statics'][k] = {'id': k, 'type': f.type, 'name': f.name,
                                         'x': f.x, 'y': f.y,
                                         'zone': self._zone_label(f.x, f.y), 'turn': t}
        for tr in self.traps:                         # 드러난(미발동) 함정 — id 없음: 정보 항목
            if not tr.hidden and not tr.sprung and (tr.x, tr.y) in seen:
                k = 'trap@%d,%d' % (tr.x, tr.y)
                if k not in led['statics']:
                    led['statics'][k] = {'type': 'trap', 'name': tr.name,
                                         'x': tr.x, 'y': tr.y,
                                         'zone': self._zone_label(tr.x, tr.y), 'turn': t}
        for m in self.monsters:                       # 마지막 목격(몹) — 봐야 적힌다(concealed 제외)
            if m.alive and not m.concealed and (m.x, m.y) in seen:
                led['moving']['m%d' % m.id] = {'id': 'm%d' % m.id, 'kind': m.kind,
                                               'x': m.x, 'y': m.y,
                                               'zone': self._zone_label(m.x, m.y), 'turn': t}
        for o in (bots or []):                        # 마지막 목격(동료) — bots 는 view() 가 준다
            if (o.get('char') != bot.get('char') and o.get('alive') and not o.get('won')
                    and (o['x'], o['y']) in seen):
                led['moving']['b%s' % o['char']] = {'id': 'b%s' % o['char'], 'char': o['char'],
                                                    'x': o['x'], 'y': o['y'],
                                                    'zone': self._zone_label(o['x'], o['y']),
                                                    'turn': t}
        if self.scan:                                 # D19: 방문 구역도 기하 구역 명의로
            zid = self.zone_at.get((bot['x'], bot['y']))
            if zid is not None and self.zones[zid].kind == '방' and zid not in led['zones']:
                led['zones'][zid] = {'id': zid, 'turn': t}
            return
        rid = self._room_id_at(bot['x'], bot['y'])    # 방문 구역 — "내가 어느 방에 있(었)다" 감각
        if rid is not None and rid not in led['zones']:
            led['zones'][rid] = {'id': 'r%d' % rid, 'turn': t}

    def _perceive(self, bot, r=MON_SIGHT):
        """봇 FOV 내 *비은닉(non-concealed)* 몹을 aware_of에 등록(처음 보는 것만). 반환 = 새로 본 Monster 목록.
        인지=시야(굴림 아님 — 관전자 방향감). step_order(자동보행)·view(think-tick)가 *같은 훅*을 써
        '봇이 몹을 인지'의 단일 소스를 만든다 = 인식 매트릭스의 봇쪽 비트.
          · ⚠️ concealed 몹은 여기서 영영 안 걸림 → aware_of에 없음 → 그 몹의 일격은 _monster_attack에서
            매복(they-ambush)으로 처리된다. = '투명/매복몹'(Stage3) 솔기가 자동으로 매트릭스에 합류.
          · (Stage3 search-on-move 수동 인지도 이 훅에 additive로 얹힌다.)"""
        seen = self.visible_cells(bot['x'], bot['y'], r)
        self._ledger_note(bot, seen)      # 공간 장부(D17) — 지각과 같은 훅(단일 소스): 자동보행
                                          #   스텝에도 '지나오며 본 것'이 적힌다(동료는 view 가 보강)
        if self.scan:                     # D19 확인 딱지 재료: 구역별 '눈으로 본 칸' 누적(봇 명의).
            zsd = bot.setdefault('zone_seen', {})   # 구조를 아는 것 ≠ 내용물을 본 것 — 이 구분의 장부
            for c in seen:
                zc = self.zone_at.get(c)
                if zc is not None:
                    zsd.setdefault(zc, set()).add(c)
            bot.setdefault('seen_cells', set()).update(seen)   # 평생 시야 장부(벽 포함, 봇 명의) —
                                          #   explore 폴백의 '새 길' 재료. 세계 공개 아님: 눈에 든
                                          #   칸만 한 방향으로 쌓인다(LLM 무노출 — 엔진 내부 전용)
            ds = bot.setdefault('doors_seen', set())   # D19 정정: 문도 눈에 들어야 어휘가 된다
            for did, dr in self.doors.items():         #   (전지성 제거 — 구조 지식=시야+기억)
                if did not in ds and (
                        (dr.cell in seen) if dr.cell
                        else any(s in seen for s in dr.sides.values())):
                    ds.add(did)
        newly = [m for m in self.monsters
                 if m.alive and not m.concealed and (m.x, m.y) in seen
                 and m.id not in bot['aware_of']]
        for m in newly:
            bot['aware_of'].add(m.id)
        return newly

    def _gather_busy(self, leader, near, target_id):
        """모임 '동의'는 위치가 아니라 의사(08-09 왕복 셔틀 부검) — 반경 안이어도 딴 작정
        (탐색·다른 목표·대기)이 살아 있으면 안 모인 것으로 센다.
        왜: D29 가 도착 지점을 계단 곁으로 정하면서 '반경 안'은 엔진이 스스로 만든 상태가
        됐다 — 위치만 세면 한 명의 변심이 탐색을 고른 동료까지 끌고 가 마을↔1층 셔틀이
        된다(08-09 실측: 층 전이 18회, 탐색 선택 봇이 같은 턴에 마을로 끌려감).
        동의로 치는 것: 작정 소진(None) / 이 계단이 목표 / 동행 — 따라가는 상대가 동의
        무리 안이면 함께 간다(연쇄 포함. follow:b1←b2←b3 도 한 무리)."""
        group = {leader['char']}
        group |= {o['char'] for o in near
                  if not o.get('order') or o['order'] == target_id}
        while True:
            add = [o for o in near if o['char'] not in group
                   and _followed_char(o.get('order')) in group]   # follow:b·chase:b(D48 개정) 둘 다 한 무리
            if not add:
                return [o for o in near if o['char'] not in group]
            group |= {o['char'] for o in add}

    def _interact(self, bot, target_id, bots=None):
        """인접/현재 칸의 피처와 상호작용.
        출구(계단) = **파티 조율 하강**(Stage 4): 살아있는 파티 전원이 계단 반경 EXIT_GATHER 안에
          모이고 저마다 딴 작정이 없어야(_gather_busy) 함께 내려간다(솔로탈출 방지 + 의사 존중).
          안 모였으면 wait_allies — 동료를 부르거나 데리러 가거나, 볼일이 끝나길 기다려라.
        상자/샘(Stage 3) = 도박: 상자 d20+DEX≥10 → 보물2 / 실패 → 독침 2피해. 샘 d20≥8 → 회복3 / 오염 1피해."""
        base = {'char': bot['char'], 'type': 'interact', 'target': target_id}
        res = self._resolve_target(target_id, bots)
        if not res:
            return {**base, 'result': 'no_target'}
        kind, (tx, ty) = res
        if abs(bot['x'] - tx) + abs(bot['y'] - ty) > 1:
            return {**base, 'result': 'too_far'}
        if kind == 'exit':
            gate = bool(getattr(self, 'boss_on', False))   # D65(09-13): 최심층의 출구 = 워프게이트(마을로 상행)
            if gate and getattr(self, 'sealed', False):    #   봉인 — 보스가 살아 있는 동안 열리지 않는다(사실만 돌려준다)
                return {**base, 'result': 'locked', 'what': '워프게이트'}
            what = ('던전 입구' if self.town else ('워프게이트' if gate else '계단')) + '(exit)'
            went, result = ('up', 'ascend') if gate else ('down', 'exit')
            extra = {'to_depth': 0, 'gate': True} if gate else {}
            others = [o for o in (bots or []) if o['alive'] and not o['won']
                      and o['char'] != bot['char']]
            if self.solo:                        # 솔로 판: 각자 계단에 닿으면 혼자 내려간다.
                bot['won'] = True                #   기다릴 일행이 없다 — 모임 조건을 그대로 두면
                bot['went'] = went               #   (D29: 방향 기록 — 왕복 러너가 행선지를 읽는다)
                if gate:
                    bot['warp'] = True           #   D65: 러너가 0층(마을)으로 데려간다
                bot['order'], bot['path'], bot['plan'] = None, [], []   # 남남끼리 서로를 찾아
                self._witness_use(bots, tx, ty, [bot],   # D30(09-05): 남는 사람이 본다 — "낯선 사람이 계단을 사용"
                                  what, 'exit')
                return {**base, 'result': result, 'party': [bot['char']], **extra}  # 다녀야 해서 없애려던
                                                 #   그 뭉침이 규칙으로 강제된다. 판은 안 끝난다 —
                                                 #   러너가 전원 won/사망까지 돈다(전부 관찰).
            far = [o for o in others if self._cheb(o['x'], o['y'], tx, ty) > EXIT_GATHER]
            busy = self._gather_busy(bot, [o for o in others if o not in far], target_id)
            if far or busy:                      # 아직 안 모임(멀거나·딴 작정) — 혼자 안 내려간다
                return {**base, 'result': 'wait_allies', 'dir': went,
                        'missing': sorted(o['char'] for o in far),
                        'busy': sorted(o['char'] for o in busy)}
            group = [bot] + others
            for o in group:                      # 모인 전원이 함께 하강/탈출(보스층: 함께 귀환) — 이 층의 작정도 끝
                o['won'] = True
                o['went'] = went                 # D29: 방향 기록(왕복 러너용 — 기존 판은 안 읽음)
                if gate:
                    o['warp'] = True
                o['order'], o['path'], o['plan'] = None, [], []
            self._witness_use(bots, tx, ty, group,    # D30: 전원 하강이라 남는 목격자 없음(부분 하강 규칙이
                              what, 'exit')          # 생기면 그대로 발화)
            return {**base, 'result': result, 'party': sorted(o['char'] for o in group), **extra}
        f = self.feature_at(tx, ty)
        if f and f.concealed:                    # 숨은 건 아직 '없는' 것 — 드러나야 만질 수 있다
            return {**base, 'result': 'nothing'}
        if f and f.type == 'stairs_up':          # 마을 복귀(D29) — 하강과 대칭 문법(모임 규칙 동일:
            others = [o for o in (bots or []) if o['alive'] and not o['won']   # 함께 왔으면
                      and o['char'] != bot['char']]                            # 함께 돌아간다)
            if self.solo:
                bot['won'], bot['went'] = True, 'up'
                bot['order'], bot['path'], bot['plan'] = None, [], []
                self._witness_use(bots, tx, ty, [bot], f.name, 'f%d' % f.id)   # D30 — 하강과 대칭
                return {**base, 'result': 'ascend', 'party': [bot['char']]}
            far = [o for o in others if self._cheb(o['x'], o['y'], tx, ty) > EXIT_GATHER]
            busy = self._gather_busy(bot, [o for o in others if o not in far], target_id)
            if far or busy:
                return {**base, 'result': 'wait_allies', 'dir': 'up',
                        'missing': sorted(o['char'] for o in far),
                        'busy': sorted(o['char'] for o in busy)}
            group = [bot] + others
            for o in group:
                o['won'], o['went'] = True, 'up'
                o['order'], o['path'], o['plan'] = None, [], []
            self._witness_use(bots, tx, ty, group, f.name, 'f%d' % f.id)      # D30 — 하강과 대칭
            return {**base, 'result': 'ascend', 'party': sorted(o['char'] for o in group)}
        if f and f.type == 'npc':                # NPC(D29) 말 걸기 + D32(09-05) 상점 v0: 정해진 대사 + 선물
            gift = (getattr(self, 'npc_gifts', None) or {}).get(f.name) or {}
            served = bot.setdefault('shop_served', set())   # 방문 단위 — 층 전이의 재스폰이 새 봇 dict 를
            met = bot.setdefault('npc_met', set())          #   만들므로 마을에 다시 오면 자동으로 비어 있다
            again = f.name in met                            #   ("살아 돌아오면 또 하나" — 후퇴→재정비 고리)
            met.add(f.name)                                  # D32 개정(09-06 파트너 확정): 두 번째부터는 '아까 왔잖아'
            given = None                                     #   고정 대사(line_again) — 방문 여부 기준, 선물 여부와 무관.
            if not again and gift and f.name not in served:  #   실측: 이미 받고도 8틱마다 상인 둘을 번갈아 60틱(seed 726984)
                got = []                                     # 마을 v1(09-11): 길드 접수원은 물약+단검을 함께 준다(기본 물품, 메모 §4-4)
                if gift.get('potions'):
                    bot['potions'] = bot.get('potions', 0) + int(gift['potions'])
                    got.append('물약')
                if gift.get('weapon') and not bot.get('weapon'):     # 빈손일 때만 — 스왑·비교는 던전 몫(D28)
                    nm = str(gift['weapon'])
                    bot['weapon'] = {'id': self._alloc_fid(), 'name': nm, 'bonus': GEAR_KINDS.get(nm, 1),
                                     'worn': [bot['char']]}   # D57: 손에서 태어나도 개체 — 내려놓으면 같은 번호
                    got.append(nm)
                given = '·'.join(got) if got else None
            if given:
                served.add(f.name)
                self._witness(bots, tx, ty,      # 마을=전체 시야 — 챙기는 걸 본 사람은 안다(ally_loot 문법 그대로)
                              {'kind': 'ally_loot', 'char': bot['char'], 'what': given},
                              exclude=(bot['char'],))
                return {**base, 'result': 'npc_gift', 'npc': f.name, 'item': given,
                        'line': self.npc_lines.get(f.name, '…')}
            line_again = (getattr(self, 'npc_lines_again', None) or {}).get(f.name)
            return {**base, 'result': 'npc_talk', 'npc': f.name,
                    'line': line_again if (again and line_again) else self.npc_lines.get(f.name, '…'),
                    **({'again': True} if again else {})}    # 스트림 additive — 재방문 계측(부검용)
        if f and f.type == 'treasure':
            del self.features[f.id]; bot['bag'] += 1
            self._witness(bots, tx, ty,          # 전달층(D22 확장 07-29): 획득도 목격 — 사라진 보물의 행방
                          {'kind': 'ally_loot', 'char': bot['char'], 'what': '보물'},
                          exclude=(bot['char'],))
            return {**base, 'result': 'treasure'}
        if f and f.type == 'potion':             # 회복 물약 — 곁에서 집기(줍기 문법, 마시는 건 drink)
            del self.features[f.id]
            bot['potions'] = bot.get('potions', 0) + 1
            self._witness(bots, tx, ty,
                          {'kind': 'ally_loot', 'char': bot['char'], 'what': '물약'},
                          exclude=(bot['char'],))
            return {**base, 'result': 'potion', 'potions': bot['potions']}
        if f and f.type in ('weapon', 'armor'):  # 장비(07-30) — 착용은 자동 줍기가 아니라 여기,
            slot = f.type                        #   즉 캐릭터의 '결정'이다(밟고 지나가면 그대로 둔 것).
            old = bot.get(slot)
            bonus = GEAR_KINDS.get(f.name, 0)
            # D57(09-12): 같거나 못한 장비로 바꾸는 것도 세계는 허용한다 — 무효 규칙(D56) 철회. 파트너 "규칙으로 캐릭터의 행동을
            #   강제하는 게 아니라 판단 가능한 목록을 넓혀주는 게 맞다": 개체 번호·비교 수치·new·'착용해 봄' 태그·장부가 정보이고,
            #   그래도 바꾸는 건 캐릭터 몫. 판 51828 의 되집기는 세계가 개체를 새로 찍어 낸 게 뿌리였다(번호 유지로 해소).
            worn = set(getattr(f, 'worn', None) or ()) | {bot['char']}
            del self.features[f.id]
            did = self._put_gear(slot, old, tx, ty, bot['char']) if old else None   # 스왑: 헌 장비는 **같은 번호**로 그 자리에(슬롯=소지의 전부)
            bot[slot] = {'id': f.id, 'name': f.name, 'bonus': bonus, 'worn': sorted(worn)}
            self._witness(bots, tx, ty,          # 전달층(D22): 획득 문법 그대로 — 챙기는 걸 본 사람은 안다
                          {'kind': 'ally_loot', 'char': bot['char'], 'what': f.name},
                          exclude=(bot['char'],))
            return {**base, 'result': 'equip', 'slot': slot, 'item': f.name, 'id': 'f%d' % f.id,
                    'bonus': bonus, **({'dropped': old['name'], 'dropped_id': 'f%d' % did} if old else {})}
        if f and f.type == 'chest':              # 상자 도박 — 손재주(DEX)가 좋으면 안전하게 연다
            cid = 'f%d' % f.id                   # D30: 사용 목격의 id(삭제 전에 잡는다)
            del self.features[f.id]
            r = self.d20(); total = r + bot['dex']
            if total >= 10:
                bot['bag'] += 2
                self._witness(bots, tx, ty,      # D30 확장(09-05): 상자=오브젝트 사용, 결과는 괄호 한 마디
                              {'kind': 'ally_use', 'char': bot['char'], 'what': '상자',   # (07-29 좋은/나쁜
                               'id': cid, 'result': '보물을 꺼냈다'},                   #  결과 대칭 보존)
                              exclude=(bot['char'],))
                return {**base, 'result': 'chest_loot', 'roll': r, 'mod': bot['dex'],
                        'total': total, 'loot': 2}
            bot['hp'] -= 2
            out = {**base, 'result': 'chest_trap', 'roll': r, 'mod': bot['dex'],
                   'total': total, 'dmg': 2, 'hp': bot['hp']}
            if bot['hp'] <= 0:
                bot['alive'] = False; out['down'] = True
                g = self._on_down(bot, bots, by='함정 상자', by_kind='hazard')
                if g:
                    out['grave'] = g
            if bot['alive']:                     # 상자 독침의 특수(D34): 중독
                st = self._apply_status(bot, '중독', '함정 상자', bots, by_kind='hazard')
                if st:
                    out['status'] = st
            if bot['alive']:                     # D30 확장: 독침도 '상자를 사용 (독침에 당했다)' — 전사면
                self._witness(bots, tx, ty,      #   ally_down 이 담당(중복 금지, 함정 패턴 그대로)
                              {'kind': 'ally_use', 'char': bot['char'], 'what': '상자',
                               'id': cid, 'result': '독침에 당했다', 'dmg': 2},
                              exclude=(bot['char'],))
            return out
        if f and f.type == 'fountain':           # 샘 도박 — 대체로 이득(회복), 가끔 오염
            del self.features[f.id]
            r = self.d20()
            if r >= 8:
                heal = min(3, bot['maxhp'] - bot['hp'])
                bot['hp'] += heal
                self._witness(bots, tx, ty,      # 전달층(D22): 회복 장면도 시야를 탄다
                              {'kind': 'ally_heal', 'char': bot['char'], 'how': '샘'},
                              exclude=(bot['char'],))
                return {**base, 'result': 'fountain_heal', 'roll': r, 'heal': heal, 'hp': bot['hp']}
            bot['hp'] -= 1
            out = {**base, 'result': 'fountain_harm', 'roll': r, 'dmg': 1, 'hp': bot['hp']}
            if bot['hp'] <= 0:
                bot['alive'] = False; out['down'] = True
                g = self._on_down(bot, bots, by='오염된 샘', by_kind='hazard')
                if g:
                    out['grave'] = g
            if bot['alive']:                     # 오염된 샘의 특수(D34): 중독
                st = self._apply_status(bot, '중독', '오염된 샘', bots, by_kind='hazard')
                if st:
                    out['status'] = st
            if bot['alive']:                     # 전달층: 오염 장면 목격 — 같은 샘의 축복(ally_heal)만
                self._witness(bots, tx, ty,      #   보이고 저주는 안 보이던 비대칭의 해소(07-29)
                              {'kind': 'ally_mishap', 'char': bot['char'],
                               'what': '오염된 샘', 'dmg': 1},
                              exclude=(bot['char'],))
            return out
        return {**base, 'result': 'nothing'}

    def _attack(self, bot, target_id=None, bots=None):
        """사거리 안 몬스터를 친다. target 지정되면 *그 몹만*(사거리 밖이면 too_far — 다른 적
        몰래치기 금지), 미지정이면 가장 약한 사거리 내 몹. d20+STR(원거리는 DEX) ≥ AC.
        사거리는 시트의 atk_range(맨해튼) — 근접 1이 기본이고 궁수만 2다."""
        adj = [m for m in self.monsters
               if m.alive and not m.concealed              # 숨은(존재 모르는) 몹은 지목·폴백 대상 아님
               and self._can_hit(bot, m)]
        base = {'char': bot['char'], 'type': 'attack'}
        if target_id:
            res = self._resolve_target(target_id, bots)
            if not res or res[0] != 'monster':
                return {**base, 'result': 'no_target'}        # 지정 대상이 (살아있는) 몹이 아님
            mon = next((m for m in adj if (m.x, m.y) == res[1]), None)
            if mon is None:
                return {**base, 'result': 'too_far'}          # 지정 몹이 사거리 밖 → 폴백 금지
        else:
            mon = min(adj, key=lambda m: m.hp) if adj else None   # 미지정 폴백: 가장 약한 사거리 내
        if not mon:
            return {**base, 'result': 'no_target'}
        # 인식 매트릭스(봇쪽): 몹이 날 못 봄(잠·배회) → 우리 기습(we-ambush-them).
        # 유리굴림(2d20 max) + 보너스 피해. 굴림 횟수는 분기로 고정(시드 스트림 결정론 유지).
        # waking(TIME_TO_WAKE_UP=1): 막 깬(발각 직후) 몹은 1턴 더 기습 가능 — 늦잠의 대가.
        # ⚠️ FLEEING 은 기습 아님 — 봇을 빤히 보며 도망치는 중(완전 인지). 등을 쳐도 정면 인지다.
        surprise = mon.state in ('SLEEPING', 'WANDERING') or mon.waking > 0
        mod = bot['dex'] if int(bot.get('atk_range') or 1) > 1 else bot['str']
        if self.trpg_combat:
            combat_roll = SC.check(self, mod, mon.ac, advantage=surprise,
                                   disadvantage=self.status and '중독' in (bot.get('status') or {}), attack=True)
            r = combat_roll['roll']
        else:
            r = max(self.d20(), self.d20()) if surprise else self.d20()
        if self.status and not self.trpg_combat and '중독' in (bot.get('status') or {}):
            mod -= POISON_MOD                     # 중독(D34): 손이 떨린다 — 명중 감산
        # 활잡이는 DEX 로 굴린다 — 힘이 아니라 겨눔이다. 스트림의 mod 키는 그대로라
        # 소비자 무접촉(값만 어느 능력치에서 왔는지가 달라진다).
        total = r + mod
        hit = (r == 20) or (total >= mon.ac)
        if self.trpg_combat:
            hit = combat_roll['success']
        res = {**base, 'result': 'attack', 'target': mon.kind, 'target_id': 'm%d' % mon.id,
               'roll': r, 'mod': mod, 'total': total, 'ac': mon.ac, 'hit': hit}
        if self.trpg_combat:
            res['combat_roll'] = combat_roll
        if surprise:
            res['surprise'] = True
        if hit:
            dmg = ((bot['wdmg'] + gear_bonus(bot, 'weapon'))   # 장비(07-30): 무기 보정은 크리에도
                   * (2 if r == 20 else 1)                     #   함께 배가된다(맹타는 든 것째로)
                   + (SURPRISE_DMG_BOT if surprise else 0))
            if self.trpg_combat:
                damage_roll = SC.weapon_damage(self, bot['wdmg'], r == 20)
                dmg = damage_roll['value'] + gear_bonus(bot, 'weapon') + (SURPRISE_DMG_BOT if surprise else 0)
                res['damage_roll'] = damage_roll
            res.update(self._damage_monster(bot, mon, dmg, bots, r == 20))
        self._wake_attacked_monster(bot, mon, surprise)
        return res

    def _damage_monster(self, bot, mon, dmg, bots, critical=False):
        """기본 공격과 스킬의 피해·처치·관계·목격 처리를 한곳에서 유지한다."""
        res = {}
        mon.hp -= dmg
        res.update(crit=critical, dmg=dmg, monster_hp=max(0, mon.hp))
        if self.relations:                    # 함께 싸움(D36): FOUGHT_WINDOW 틱 안에 같은 몹을 친 둘
            for oc, t in list(mon.last_hits.items()):
                key = frozenset((oc, bot['char']))
                if oc != bot['char'] and self.turn - t <= FOUGHT_WINDOW and key not in mon.fought:
                    ob = next((o for o in (bots or []) if o['char'] == oc), None)
                    if ob is not None:
                        mon.fought.add(key)   # 몹당 한 번 — 한 전투는 한 번 센다
                        self._bone(bot, oc, 'fought'); self._bone(ob, bot['char'], 'fought')
            mon.last_hits[bot['char']] = self.turn
        if mon.hp <= 0:
            mon.alive = False; res['killed'] = True
            if getattr(self, 'boss', None) is mon and getattr(self, 'sealed', False):   # D65: 보스가 쓰러지면 워프게이트 봉인 해제
                self.sealed = False                       #   (다음 관측부터 게이트가 '열려 있다' — 결과 unsealed 는 로그·관전용)
                res['unsealed'] = True
            if self.relations and mon.state == 'HUNTING' and mon.target \
                    and mon.target != bot['char']:    # 나를 구함(D36): 나를 물던 몹을 동료가 처치 —
                victim = next((o for o in (bots or []) if o['char'] == mon.target   # 그 처치를 본 사람만
                               and o['alive'] and not o['won']), None)              # (시야-온리)
                if victim is not None and (mon.x, mon.y) in self.visible_cells(victim['x'], victim['y']):
                    self._bone(victim, bot['char'], 'rescued')
            for o in (bots or []):    # 목격한 죽음은 장부에서 지운다(D17 교정 — 죽는 걸 본
                if (o.get('alive') and not o.get('won')       # 몹이 '마지막 목격'으로 살아
                        and o.get('ledger') is not None       # 있는 척 잔존하는 유령 방지,
                        and (mon.x, mon.y) in self.visible_cells(o['x'], o['y'])):
                    o['ledger']['moving'].pop('m%d' % mon.id, None)   # 리뷰 픽스.
                    # 안 본 죽음은 안 지운다 — 지우면 그게 역누설이다
        self._witness(bots, mon.x, mon.y,     # 전달층(D22): "카야가 공격했다!"/"고블린이 쓰러졌다!"
                      {'kind': 'ally_kill' if not mon.alive else 'ally_hit',
                       'char': bot['char'], 'mon': mon.kind,
                       **({'crit': True} if critical else {})},
                      exclude=(bot['char'],))  # 빗나감은 안 싣는다(소음 절약 — D22 구현 재량)
        return res

    def _wake_attacked_monster(self, bot, mon, surprise):
        if mon.alive:                            # 공격받음 = 완전 각성(justAlerted 우회)
            mon.waking = 0                       # 취약창 소비 — 안 끄면 기습→skip→waking 미소비 무한 스턴락
            if mon.state != 'FLEEING':           # 도주몹은 도주 지속(HUNTING 뒤집으면 flee 시계 리셋 교란)
                mon.state, mon.target = 'HUNTING', bot['char']
                mon.last_seen, mon.lost = (bot['x'], bot['y']), 0
            if surprise:
                mon.skip_turns = 1               # 기습라운드 = 다음 몹턴 반격 1회 스킵(대상 턴 스킵)

    def _drink(self, bot, bots=None):
        """회복 물약 마시기(07-17): 확정 완전 회복 — 샘(그 자리 d20 도박)과 대비되는 '들고 다니는
        보험'(PD 문법). 굴림 없음(아이템의 약속은 확실성), 한 턴 소모. 만피에 마셔도 소모된다
        (세계는 낭비를 말리지 않는다 — 리모컨 라벨의 사실 주석이 알려줄 뿐). 빈 손 = no_potion
        정직 보고(plan_step 열린 동사 선례: 유무는 발동 시점 판정)."""
        base = {'char': bot['char'], 'type': 'drink'}
        if not bot.get('potions'):
            return {**base, 'result': 'no_potion'}
        bot['potions'] -= 1
        heal = bot['maxhp'] - bot['hp']
        bot['hp'] = bot['maxhp']
        self._witness(bots, bot['x'], bot['y'],   # 전달층(D22): 회복 장면도 시야를 탄다
                      {'kind': 'ally_heal', 'char': bot['char'], 'how': '물약'},
                      exclude=(bot['char'],))
        return {**base, 'result': 'drink_heal', 'heal': heal, 'hp': bot['hp'],
                'potions': bot['potions']}

    def _search(self, bot, bots=()):
        """능동 search(SPD 능동/수동 분리의 능동쪽): 턴을 통째로 써서 인지 반경(search_r) 내
        '보이는' 숨은 것 **전부 확정 발견**(굴림 없음 — 시간을 쓰는 대가). 도적 반경 2 vs 전사 1."""
        r = bot.get('search_r', 1)
        seen = self.visible_cells(bot['x'], bot['y'], r)
        cx, cy = bot['x'], bot['y']
        found = []
        for t in self.traps:
            if t.hidden and not t.sprung and (t.x, t.y) in seen:
                t.hidden = False
                found.append({'kind': 'trap', 'name': t.name,
                              'bearing': self._bearing(t.x - cx, t.y - cy)})
                self._witness(bots, t.x, t.y,     # 전달층(D22 확장 07-29): 능동 수색의 발견도 목격
                              {'kind': 'ally_spot', 'char': bot['char'], 'what': t.name},
                              exclude=(bot['char'],))
        for f in list(self.features.values()):
            if f.concealed and (f.x, f.y) in seen:
                f.concealed = False
                found.append({'kind': f.type, 'name': f.name,
                              'bearing': self._bearing(f.x - cx, f.y - cy)})
                self._witness(bots, f.x, f.y,
                              {'kind': 'ally_spot', 'char': bot['char'], 'what': f.name},
                              exclude=(bot['char'],))
        for m in self.monsters:
            if m.alive and m.concealed and (m.x, m.y) in seen:
                m.concealed = False
                bot['aware_of'].add(m.id)
                found.append({'kind': 'monster', 'name': m.kind, 'id': 'm%d' % m.id,
                              'bearing': self._bearing(m.x - cx, m.y - cy)})
                self._witness(bots, m.x, m.y,     # 몹 이름은 mon 필드 — 목격자 도감 게이트를 탄다
                              {'kind': 'ally_spot', 'char': bot['char'], 'mon': m.kind},
                              exclude=(bot['char'],))
        return {'char': bot['char'], 'type': 'search', 'radius': r, 'found': found}

    # ── 몬스터 턴 (봇들이 행동한 뒤 엔진이 굴린다) ──────────────
    def _monster_walkable(self, x, y, bots):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False
        if self.grid[y][x] == WALL:
            return False
        if any(b['x'] == x and b['y'] == y and b['alive'] and not b['won'] for b in bots):
            return False
        if self.monster_at(x, y):
            return False
        return True

    @staticmethod
    def _cheb(ax, ay, bx, by):
        return max(abs(ax - bx), abs(ay - by))

    def _witness(self, bots, x, y, fact, exclude=()):
        """D22 전달층 — (x,y)가 시야에 든 생존 봇에게 목격 사실 주입. A-3 문법 그대로:
        witnessed 에 쌓였다가 다음 결정 obs 에 1회 실리고 소거(휘발=다음 결정 1회 — 시계 TTL 이면
        자동보행 틱 동안 아무 두뇌도 못 읽고 증발한다). 당사자는 exclude(자기 경험은 last 소관).
        events 스위치 뒤 — 기존 몹 피격 주입(무스위치, _monster_attack)과 별개로 어휘만 늘린다.
        어휘(kind): ally_hit/kill/trap/heal/down(전투·함정·회복·전사) · ally_loot/spot/mishap(07-29 획득·
        발견·비대칭) · **ally_use{what,id}**(D30 09-05 — 오브젝트 사용, 첫 사례=문 타일 밟기. 동사는
        '사용' 하나, 확장 시 what 만 바뀐다 — 파트너 확정. 상태가 아니라 사건인 이유: 걷는 동료는 그
        틱에 결정하지 않는다)."""
        if not self.events:
            return
        for o in bots or ():
            if o['char'] in exclude or not o['alive'] or o['won']:
                continue
            if (x, y) in self.visible_cells(o['x'], o['y']):
                o.setdefault('witnessed', []).append(dict(fact))
                self._floor_count_w(o, fact)          # D40 ② 층 집계 — 목격도 센다(같은 사전의 목격 라벨)

    def _witness_use(self, bots, x, y, movers, what, fid=None, result=None):
        """D30 오브젝트 사용 목격 — 사용한 사람마다 한 줄(문·계단·상자…). 동사는 '사용' 하나, what 은
        obs 가 그 오브젝트를 부르는 이름(문 d0 / 계단(exit) / 상자), result 는 결과가 있는 사용의 괄호
        한 마디(상자: 보물을 꺼냈다·독침에 당했다 — 파트너 동의 09-05). 사용자 전원은 제외(자기
        경험=last). 계단처럼 사용자가 층을 떠나는 경우 witnessed 는 남는 사람에게만 실린다 —
        파티 전원 하강이면 목격자가 없고, 솔로·부분 하강이면 "낯선 사람이 계단을 사용"이 남는다."""
        for m in movers:
            fact = {'kind': 'ally_use', 'char': m['char'], 'what': what}
            if fid:
                fact['id'] = fid
            if result:
                fact['result'] = result
            self._witness(bots, x, y, fact, exclude=tuple(mm['char'] for mm in movers))

    def _rel(self, bot, other):
        rel = bot.setdefault('relations', {})
        e = rel.get(other)
        if e is None:
            e = rel[other] = {'bones': {}, 'total': 0, 'line': None, 'line_turn': None,
                              'line_src': None, 'queue': []}
        return e

    def _bone(self, bot, other, kind):
        """뼈 한 개(D36) — bot 의 장부에 '상대 other 와 kind 가 한 번 더'. 강한 뼈(구함·죽을 때 곁)는
        즉시 초대를 큐에 넣고, 약한 뼈는 합계가 RELATION_K 의 배수가 되는 순간에만 넣는다(문턱 요약 —
        파트너 확정 "일정 수치가 넘어가면 몇 자 이내로 요약"). 초대는 view 가 결정당 하나씩 꺼낸다."""
        if not self.relations or other == bot['char'] or not bot.get('alive', True):
            return
        e = self._rel(bot, other)
        b = e['bones'].setdefault(kind, {'n': 0, 'last': None})
        b['n'] += 1; b['last'] = self.turn
        if kind in STRONG_BONES:
            e['queue'].append(kind)
        else:
            e['total'] += 1
            if e['total'] % RELATION_K == 0:
                e['queue'].append('milestone')

    def note_talk(self, a, b):
        """이야기를 나눔(D36 뼈) — 서로 보여 말이 배달된 틱에 쌍당 1회(양방향 대칭). 배달 규칙은
        러너 inbox 가 소유하고 여기는 세기만 한다(말 내용은 안 읽는다)."""
        if not self.relations:
            return
        key = (frozenset((a['char'], b['char'])), self.turn)
        if key in self._talked:
            return
        self._talked.add(key)
        self._bone(a, b['char'], 'talk')
        self._bone(b, a['char'], 'talk')

    def note_proposal(self, a, b):
        """제안(D47 뼈) — a 가 b 에게 제안한 틱에 1회: a 의 장부엔 proposed, b 의 장부엔 asked. 종류는 말한 캐릭터의
        자기 신고(응답 say_kind)이고 여기는 세기만 한다(내용 무해석 — D5). 같은 제안의 반복(응답 전 재제안)은 러너가
        거른다(open 장부) — 여기 오면 새 시도다."""
        if not self.relations:
            return
        self._bone(a, b['char'], 'proposed')
        self._bone(b, a['char'], 'asked')

    def note_answer(self, a, b):
        """제안에 답함(D47 뼈) — b 가 a 의 제안 뒤 첫 결정에서 a(또는 모두)에게 말했다: a 의 장부엔 answered, b 의 장부엔
        replied. 답의 내용(수락/거절)은 안 읽는다 — 파트너 "시도했다고 수락까지 자동으로 정하지 않는다"."""
        if not self.relations:
            return
        self._bone(a, b['char'], 'answered')
        self._bone(b, a['char'], 'replied')

    def _ally_target(self, bot, target_id, bots):
        """건네기·친목 공용 대상 해소 — ('b2'|'2') → 곁(체비셰프≤1, 동행의 '곁'과 같은 자)의 살아있는 동료 dict.
        반환 (tid, recv, why) — why ∈ None/'no_target'/'too_far'. 시야 밖 동료는 D18 개정대로 없는 것."""
        s = str(target_id or '')
        tid = s if s[:1] == 'b' else 'b%s' % s
        res = self._resolve_target(tid, bots, bot)
        if res is None or res[0] != 'bot':
            return tid, None, 'no_target'
        if not self._beside(bot, res[1], 'bot'):
            return tid, None, 'too_far'
        recv = next((o for o in (bots or []) if o['char'] == tid[1:]), None)
        return tid, recv, (None if recv is not None else 'no_target')

    def _receive(self, recv, rec, bots=None):
        """받은 쪽의 자기 사건(D47 ②) — hurt 문법(남이 내게 한 일도 내 경험): last+궤적에 싣는다. 걷는 동료는 안 세운다
        (다음 결정에서 읽는다 — 잡담·친목=무정지 원칙). 대기·휴식 중이면 깨운다(손에 쥐어 주고 어깨를 두드리는 건 사건 —
        wait 의 '동료 진입'과 같은 급). 판정 무접촉."""
        recv['last'] = dict(rec)
        self._trail_add(recv, recv['last'])
        if str(recv.get('order') or '') in ('wait', 'rest'):
            recv['order'], recv['path'], recv['plan'] = None, [], []
            recv['wait'] = None
            recv['rest'] = None

    def _give(self, bot, target_id, item, bots=None):
        """건네기(D47 ②, 2026-09-09 파트너 "건네기를 만들려면 아이템 거래를 넣어야 해") — 곁의 동료에게 소지품을 넘긴다.
        물약: potions −1/+1. 무기·방어구: 벗어 건넨다 — 상대 슬롯이 비었으면 그가 걸치고(equipped), 차 있으면 발밑에 피처로
        놓인다(placed — 착용은 상대의 결정, equip 스왑 '헌것은 그 자리에' 문법과 대칭. 발밑이 찼으면 내 발밑, 둘 다 찼으면 no_room).
        굴림 없음·한 턴 소모·상대는 안 선다. 엔진은 선물인지 거래의 절반인지 모른다(D5) — 거래 = 제안(말) + 건네기 둘, 협상 상태
        없음(파트너 09-09 "제안은 열리게"). 뼈: 한 쪽 gave / 받은 쪽 received. 목격(ally_give)은 둘을 뺀 시야 안 동료."""
        item = str(item or '')
        tid, recv, why = self._ally_target(bot, target_id, bots)
        base = {'char': bot['char'], 'type': 'give', 'target': tid, 'item': item}
        if not self.give_verb:                          # 꺼진 판 — 미노출 동사(환각 방어: 아무 일도 없다)
            return {**base, 'result': 'nothing'}
        if why:
            return {**base, 'result': why}
        extra, got = {}, {}
        if item == 'potion':
            if not bot.get('potions'):
                return {**base, 'result': 'nothing'}
            bot['potions'] -= 1
            recv['potions'] = recv.get('potions', 0) + 1
            what = '물약'
            extra, got = {'potions': bot['potions']}, {'potions': recv['potions']}
        elif item in ('weapon', 'armor'):
            g = bot.get(item)
            if not g:
                return {**base, 'result': 'nothing'}
            what = g['name']
            if recv.get(item):                          # 차 있다 — 발밑에 놓는다(그가 고른다)
                spot = next(((x, y) for (x, y) in ((recv['x'], recv['y']), (bot['x'], bot['y']))
                             if self.feature_at(x, y) is None), None)
                if spot is None:
                    return {**base, 'result': 'no_room'}
                bot[item] = None
                self._put_gear(item, g, spot[0], spot[1], bot['char'])   # D57: 같은 번호로 발밑에(건넨 이의 착용 이력 포함)
                extra, got = {'placed': True}, {'placed': True}
            else:
                bot[item] = None
                recv[item] = dict(g)
                extra, got = {'equipped': True}, {'equipped': True}
        else:
            return {**base, 'result': 'nothing'}
        self._receive(recv, {'char': recv['char'], 'type': 'received', 'from': bot['char'],
                             'what': what, 'item': item, **got}, bots)
        self._bone(bot, recv['char'], 'gave')
        self._bone(recv, bot['char'], 'received')
        self.note_act(bot, recv, '건네기', what)
        self._witness(bots, bot['x'], bot['y'],
                      {'kind': 'ally_give', 'char': bot['char'], 'to': recv['char'], 'what': what},
                      exclude=(bot['char'], recv['char']))
        return {**base, 'result': 'given', 'to': recv['char'], 'what': what, **extra}

    def _bond(self, bot, target_id, form, bots=None):
        """친목(D47 ②, 2026-09-09 파트너 "['대화' '친목' '머리를 쓰다듬기'] … 이건 친목 행위라 일반 대화와는 별개") — 곁의
        동료에게 하는 행동. 서술(form)은 캐릭터의 자유 문구(BOND_LEN 자 이내) —
        엔진은 세기만 한다(내용 무해석 D5, 목록 없음 = 파트너 결정 "형태는 기록으로, 기계는 횟수만"). 물리 없음: 받은 쪽 자기
        사건(bonded)·목격(ally_bond)·뼈 bond(쌍이 같이)·상세 기록(acts — 반응은 러너가 상대의 다음 결정에서 형태로 적는다).
        시도했다고 반응까지 정해지진 않는다(파트너 초안 §A-3). 한 턴 소모, 상대는 안 선다."""
        form = ' '.join(str(form or '').split())[:BOND_LEN] or '몸짓'
        tid, recv, why = self._ally_target(bot, target_id, bots)
        base = {'char': bot['char'], 'type': 'bond', 'target': tid, 'form': form}
        if not self.bond_verb:
            return {**base, 'result': 'nothing'}
        if why:
            return {**base, 'result': why}
        self._receive(recv, {'char': recv['char'], 'type': 'bonded', 'from': bot['char'], 'form': form}, bots)
        self._bone(bot, recv['char'], 'bond')
        self._bone(recv, bot['char'], 'bond')
        self.note_act(bot, recv, '친목', form)
        self._witness(bots, bot['x'], bot['y'],
                      {'kind': 'ally_bond', 'char': bot['char'], 'to': recv['char'], 'form': form},
                      exclude=(bot['char'], recv['char']))
        return {**base, 'result': 'done', 'to': recv['char']}

    def note_act(self, a, b, kind, what):
        """상세 기록(D47 ②, 파트너 초안 §A-5 "상세 기록에는 농담·접촉·함께 쉰 내용과 상대 반응을 보존한다") — a 가 b 에게 한
        친목·건네기 한 건을 양쪽 장부에: {turn, kind(친목|건네기), what(형태|물건), mine, reply}. reply 는 상대의 다음 결정에서
        러너가 note_reply 로 적는다(행동|말|없음 — 형태만, 뜻은 살 초대에). 상한 ACTS_MAX(오래된 것부터 바랜다)."""
        if not self.relations:
            return
        for me, other, mine in ((a, b, True), (b, a, False)):
            if not me.get('alive', True):
                continue
            e = self._rel(me, other['char'])
            acts = e.setdefault('acts', [])
            acts.append({'turn': self.turn, 'kind': kind, 'what': what, 'mine': mine, 'reply': None})
            del acts[:-ACTS_MAX]

    def note_reply(self, recv, giver, how):
        """반응 기록(D47 ②) — recv 가 giver 의 친목·건네기 뒤 첫 결정에서 어떻게 답했나(how ∈ 행동|말|없음, 러너가 분류).
        아직 답이 안 적힌 그 상대의 기록 전부에 적는다(한 결정이 그 사이 쌓인 것 모두의 답이다). 수락·거절은 안 읽는다."""
        if not self.relations:
            return
        for me, other, mine in ((recv, giver, False), (giver, recv, True)):
            acts = ((me.get('relations') or {}).get(other['char']) or {}).get('acts') or []
            for a in acts:
                if a.get('mine') == mine and a.get('reply') is None:
                    a['reply'] = how

    def _remember_grave(self, bot, f):
        """묘 발견 기억(D22 개정) — 그 죽음을 이미 아는 봇(목격 fallen·발견 grave_found)은 무등재,
        아니면 지속 기억 grave_found{char,name,zone,turn} 1회(fallen 문법: 좌표 금지·구역 이름만).
        당사자(자기 묘 — 부활 판)는 안 온다: 죽은 봇은 view 를 안 받는다."""
        who = self.grave_of[f.id]['char']
        if who == bot['char']:
            return
        mem = bot.setdefault('memories', [])
        if any(e.get('char') == who and e.get('kind') in (None, 'fallen', 'grave_found')
               for e in mem):
            return                             # 목격했거나 이미 발견했다 — 한 죽음은 한 줄
        zid = getattr(self, 'zone_at', {}).get((f.x, f.y)) if self.scan else None
        zone = self._zone_name(bot, zid) if zid is not None else self._zone_label(f.x, f.y)
        mem.append({'kind': 'grave_found', 'char': who, 'grave': f.name,
                    'zone': zone, 'turn': self.turn})

    def _apply_status(self, bot, tag, by, bots=(), by_kind='hazard', force=False):
        """상태 태그(D34) 부착 — 몹·함정·오브젝트의 특수. 스위치 꺼짐=무동작(기존 판 비트 동일).
        같은 태그 재발=n 만 는다(×N 표시 — 효과 불변, 첫 판 관찰 뒤 재론). 목격(D22 문법): 시야 안
        동료는 '카야가 가시 함정으로 출혈 상태가 되는 것을' 본다 — 상태는 겉으로 드러난다(파트너 확정
        "동료도 같은 단어를 본다"). by_kind: monster(도감 게이트 대상)/trap/hazard. 반환=태그 또는 None."""
        if not (self.status or (self.skills and force)) or not bot.get('alive', True):
            return None
        st = bot.setdefault('status', {})
        e = st.get(tag)
        if e:
            e['n'] += 1; e['by'] = by; e['since'] = self.turn
        else:
            st[tag] = {'n': 1, 'by': by, 'since': self.turn}
        self._witness(bots, bot['x'], bot['y'],
                      {'kind': 'ally_status', 'char': bot['char'], 'tag': tag, 'by': by,
                       **({'by_kind': by_kind} if by_kind != 'monster' else {})},
                      exclude=(bot['char'],))
        return tag

    def _on_down(self, bot, bots, by, by_kind='monster', witness=True):
        """D22 — 쓰러짐의 공통 처리(굴림 없음). 모든 사망 경로(몹·함정·상자·샘)가 부른다.
        · 묘(graves): 쓰러진 칸에 '~의 묘' 피처 — 광학(sights)·조회·goto 앵커. 표지판이지 시체가
          아니다(D4 불가침). 생성 정보를 반환 — 사망 이벤트에 'grave' 키로 실린다(스트림 additive).
        · 목격(events, witness=True): 시야 내 동료에게 ally_down 주입. 몹 공격 경로는 기존 A-3
          주입(무스위치)이 이미 담당 — witness=False 로 중복 금지(기존 비트 보존).
        · 기억(events): 목격자마다 지속 기억 fallen {누가, 무엇에게, 어디서(그 봇의 사람말 이름),
          언제} — view 가 매 결정 재제시(휘발 0). 좌표 금지 — 구역 이름만(D19 사람의 공간 언어)."""
        x, y = bot['x'], bot['y']
        g = None
        if self.graves:
            gname = '%s의 묘' % (bot.get('name') or bot['job'])
            fid = self._add_feature('grave', gname, x, y)
            g = {'id': 'f%d' % fid, 'name': gname, 'x': x, 'y': y}
            self.grave_of[fid] = {'char': bot['char'], 'name': gname}   # 묘 발견(비목격자)의 재료
        if self.events:
            fact = {'kind': 'ally_down', 'char': bot['char'], 'by': by,
                    **({'by_kind': by_kind} if by_kind != 'monster' else {})}
            zid = getattr(self, 'zone_at', {}).get((x, y)) if self.scan else None
            for o in bots or ():
                if o is bot or not o['alive'] or o['won']:
                    continue
                if (x, y) not in self.visible_cells(o['x'], o['y']):
                    continue                          # 못 본 죽음은 모른다 — 시야-온리(전지 주입 금지)
                if witness:
                    o.setdefault('witnessed', []).append(dict(fact))
                self._bone(o, bot['char'], 'at_death')   # 죽을 때 곁에 있었음(D36, 강한 뼈) — 목격자 장부
                zone = self._zone_name(o, zid) if zid is not None else self._zone_label(x, y)
                o.setdefault('memories', []).append(
                    {'kind': 'fallen', 'char': bot['char'], 'by': by,
                     **({'by_kind': by_kind} if by_kind != 'monster' else {}),
                     'zone': zone, 'turn': self.turn})
        return g

    def _monster_attack(self, m, b, bots=()):
        """몹이 직교 인접 봇 b를 친다. 인식 매트릭스(몹쪽): 봇이 이 몹을 못 봤으면(aware_of 밖) =
        매복(they-ambush-us) → 유리굴림(2d20 max)+보너스 피해. 맞으면 봇은 그 몹을 즉시 인지(연속 매복 차단).
        ⚠️ 비은닉 몹은 봇이 시야로 늘 먼저 보므로(aware_of 등재) 실전 매복은 ~0이 정상 — '트인 곳에선 다 보인다'.
        진짜 they-ambush는 concealed(투명/매복몹·Stage3)가 생겨야 발화: concealed면 _perceive가 못 걸러
        aware_of에 영영 없음 → 이 분기가 자동으로 매복 처리. 즉 여기는 Stage3 솔기(지금은 대부분 dormant).
        A-3(D18): 명중/처치는 피격 칸이 시야 내인 다른 생존 봇의 witnessed 에 목격 사실로 쌓인다
        ("상처도 시야를 탄다" — 라이브 22틱 카야 전사 무목격 부검)."""
        ambush = m.id not in b.get('aware_of', set())
        ac = 10 + b['dex'] + gear_bonus(b, 'armor')   # 장비(07-30): 방어구=막기 — 갑옷이 이를 받는다
        if self.status and '중독' in (b.get('status') or {}):
            ac -= POISON_MOD                      # 중독(D34): 몸이 무디다 — 회피 감산
        if self.trpg_combat:
            combat_roll = SC.check(self, m.atk, ac, advantage=ambush, attack=True)
            r = combat_roll['roll']
        else:
            r = max(self.d20(), self.d20()) if ambush else self.d20()
        total = r + m.atk
        hit = (r == 20) or (total >= ac)
        if self.trpg_combat:
            hit = combat_roll['success']
        ev = {'type': 'monster_attack', 'id': 'm%d' % m.id, 'monster': m.kind,
              'target': b['char'],
              'roll': r, 'mod': m.atk, 'total': total, 'ac': ac, 'hit': hit}
        if self.trpg_combat:
            ev['combat_roll'] = combat_roll
        if ambush:
            ev['surprise'] = True
        if hit:
            dmg = m.dmg + (SURPRISE_DMG_MON if ambush else 0)
            if self.trpg_combat:
                damage_roll = SC.weapon_damage(self, m.dmg, r == 20)
                dmg = damage_roll['value'] + (SURPRISE_DMG_MON if ambush else 0)
                ev['damage_roll'] = damage_roll
            b['hp'] -= dmg; ev['dmg'] = dmg; ev['hp'] = b['hp']
            # 피격 = 인터럽트(D1 대개정): 하던 일(자동보행 order)을 멈추고 다음 틱 에이전트에게 묻는다.
            # 세계가 봇을 세우는 유일한 '접촉' 채널 — 정지 규칙(레벨 트리거) 삭제의 반대급부.
            b['order'], b['path'], b['plan'] = None, [], []   # 남은 작정(D16)도 찢는다
            interrupted = self._cancel_approach(b)
            ev.update(interrupted)
            b['last'] = {'type': 'hurt', 'by': m.kind, 'by_id': 'm%d' % m.id,
                          'dmg': dmg, 'hp': b['hp'],
                          **interrupted,
                         **({'surprise': True} if ambush else {})}
            if b['hp'] <= 0:
                b['alive'] = False; ev['down'] = True
                g = self._on_down(b, bots, by=m.kind, witness=False)   # 목격은 아래 A-3 소관(중복 금지)
                if g:
                    ev['grave'] = g            # 사망 이벤트에 묘 정보 동봉(스트림 additive — 뷰어·태그용)
            st = MON_STATUS.get(m.kind)          # 몹의 특수(D34): 그림자거미 명중=둔화(생존 시)
            if st and b['alive']:
                if self._apply_status(b, st, m.kind, bots, by_kind='monster'):
                    ev['status'] = st
                    b['last']['status'] = st     # 자기 관측(D1-4): "맞았다 — 둔화가 생겼다"
            self._trail_add(b, b['last'])        # D38 궤적 — status 병기까지 끝난 뒤 한 번(자기 피격도 궤적에)
            # 목격 주입(A-3): 자기 피격은 last 가 담당 — 중복 금지. 다음 view() 가 1회성 노출·소거.
            fact = {'kind': 'ally_down' if not b['alive'] else 'ally_hurt',
                    'char': b['char'], 'by': m.kind, 'by_id': 'm%d' % m.id}
            for o in bots:
                if o is b or not o['alive'] or o['won']:
                    continue
                if (b['x'], b['y']) in self.visible_cells(o['x'], o['y']):
                    o.setdefault('witnessed', []).append(dict(fact))
        b.setdefault('aware_of', set()).add(m.id)        # 맞으면 안다 — 같은 몹에 연속 매복 금지
        return ev

    def _mon_door(self, m, bots):
        """D30 확장 2차(2026-09-06 파트너 발제 "몬스터도 문을 이용하는 건 캐릭터에게 전달해야") — 몹이 문
        타일을 밟는 순간 그 칸을 본 봇에게 mon_use{mon,id,what:'문',door} 1회. 동료 문법(ally_use)과 같은 문장
        "고블린(m0)가 문 d0을(를) 사용하는 것을". 문 타일은 양쪽에서 보이는 순간이라 나가는 몹도 들어오는 몹도
        같은 사건이다(다음 틱 사라지거나 나타나는 이유를 봇이 안다). 매복(concealed) 몹은 존재 비누설. 도감
        게이트는 _mask 의 mon 필드가 탄다(모르는 종=낯선 짐승). 반환=문 id 또는 None(monster_move 병기용)."""
        if not self.scan or m.concealed:
            return None
        dr = next((dd for dd in self.doors.values() if dd.cell == (m.x, m.y)), None)
        if dr is None:
            return None
        self._witness(bots, m.x, m.y, {'kind': 'mon_use', 'mon': m.kind, 'id': 'm%d' % m.id,
                                       'what': '문', 'door': dr.id})
        return dr.id

    def _ally_monster_beside(self, m):
        """D51: 살아있는 다른 몹이 곁(체비셰프≤1)에 있나 — 있으면 저HP 라도 도주하지 않고 같이 싸운다."""
        return any(o is not m and o.alive and max(abs(o.x - m.x), abs(o.y - m.y)) <= 1 for o in self.monsters)

    def _nearest_ally_monster(self, m, bots):
        """D51 합류 대상(파트너 09-11 "근처의 모든 다른 몬스터 아무 곳이나 붙어서 그 친구랑 같이 싸우는 거야"):
        몬스터 보행 규칙(_monster_walkable: 벽·봇·몹 칸 제외)의 BFS 로 join_range 걸음 안에서 곁(체비셰프≤1)에 닿는
        가장 가까운 살아있는 다른 몹 — 종 무관, 은닉 매복자 포함('모든'). 반환 (ally, 첫 걸음) / 이미 곁이면 (ally, None) /
        없으면 (None, None). 결정론: 이웃 순서 고정·동률은 낮은 id."""
        allies = [o for o in self.monsters if o is not m and o.alive]
        if not allies:
            return None, None
        here = [o for o in allies if max(abs(o.x - m.x), abs(o.y - m.y)) <= 1]
        if here:
            return min(here, key=lambda o: o.id), None
        start = (m.x, m.y)
        prev = {start: None}
        frontier = deque([(start, 0)])
        while frontier:
            (x, y), dist = frontier.popleft()
            if dist >= m.flee_join_range:
                continue
            for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in prev or not self._monster_walkable(nx, ny, bots):
                    continue
                prev[(nx, ny)] = (x, y)
                cand = [o for o in allies if max(abs(o.x - nx), abs(o.y - ny)) <= 1]
                if cand:
                    cur = (nx, ny)
                    while prev[cur] != start:
                        cur = prev[cur]
                    return min(cand, key=lambda o: o.id), cur
                frontier.append(((nx, ny), dist + 1))
        return None, None

    def _join_step(self, m, first, bots, events):
        """D51 동료 쪽으로 한 칸(BFS 첫 걸음). 봇 시야 안이면 관전 이벤트(fleeing·joining 표식)."""
        if first is None or not self._monster_walkable(first[0], first[1], bots):
            return False
        m.x, m.y = first
        door = self._mon_door(m, bots)
        live = [o for o in bots if o['alive'] and not o['won']]
        if any((m.x, m.y) in self.visible_cells(o['x'], o['y'], MON_SIGHT) for o in live):
            events.append({'type': 'monster_move', 'id': 'm%d' % m.id, 'monster': m.kind,
                           'to': [m.x, m.y], 'fleeing': True, 'joining': True, **({'door': door} if door else {})})
        return True

    def _join_ally(self, m, ally, near, events):
        """D51 합류: 곁에 닿았다 — 그 뒤는 동료를 따른다(파트너 "그 친구랑 같이 싸우는 거야"): 동료가 쫓는 중이면 같은
        표적을 함께 문다(HUNTING), 동료가 자거나 배회 중이면 곁에서 진정(WANDERING — 봇이 오면 동료와 같이 깬다).
        혼자 봇에게 되돌아 달려가지 않는다(합류 직후 홀로 돌격 → 다시 도주의 2틱 왕복을 막는다). flee_turns 는 안 지운다."""
        live_near = {b['char']: b for b in near}
        if ally.state in ('HUNTING',) and ally.target and (ally.target in live_near or ally.last_seen):
            tb = live_near.get(ally.target)
            m.state, m.target, m.lost = 'HUNTING', ally.target, 0
            m.last_seen = (tb['x'], tb['y']) if tb else ally.last_seen
        else:
            m.state, m.target, m.lost = 'WANDERING', None, 0
        events.append({'type': 'monster_join', 'id': 'm%d' % m.id, 'monster': m.kind,
                       'ally': 'm%d' % ally.id, 'ally_kind': ally.kind, 'state': m.state})

    def _flee_step(self, m, near, bots, events):
        """도주 한 칸: '보이는 모든 봇과의 최소 맨해튼 거리'가 **엄격히 늘어나는** 직교 칸으로.
        ⚠️ '가장 가까운 봇 한 명' 기준이면 협공(양쪽에 봇) 사이에서 좌우 셔틀 진동 —
        봇 결정 틱엔 거리2, 자동보행 틱엔 인접이 되는 위상 잠금 livelock 실측(seed 156/157/176…).
        최소거리 기준이면 끼인 상황 = 개선 불가 = 궁지로 정확히 판정된다(제자리).
        개선 칸 없으면 False = 궁지(호출쪽에서 인접 봇 있으면 필사 반격)."""
        def score(x, y):
            return min(abs(x - b['x']) + abs(y - b['y']) for b in near)
        here = score(m.x, m.y)
        cands = [(m.x + dx, m.y + dy) for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))
                 if self._monster_walkable(m.x + dx, m.y + dy, bots)]
        cands = [c for c in cands if score(*c) > here]
        if not cands:
            return False
        m.x, m.y = max(cands, key=lambda c: (score(*c), c))
        door = self._mon_door(m, bots)                # 문 타일이면 목격(D30 확장 2차)
        live = [o for o in bots if o['alive'] and not o['won']]
        if any((m.x, m.y) in self.visible_cells(o['x'], o['y'], MON_SIGHT) for o in live):
            events.append({'type': 'monster_move', 'id': 'm%d' % m.id, 'monster': m.kind,
                           'to': [m.x, m.y], 'fleeing': True, **({'door': door} if door else {})})
        return True

    def _chase_step(self, m, bots, events):
        """last_seen 쪽으로 한 칸(greedy 직교 — 전투가 직교라 직교 추격). 봇 시야 안이면 관전 이벤트."""
        if not m.last_seen:
            return
        ddx, ddy = m.last_seen[0] - m.x, m.last_seen[1] - m.y
        steps = ([(1 if ddx > 0 else -1, 0), (0, 1 if ddy > 0 else -1)]
                 if abs(ddx) >= abs(ddy) else
                 [(0, 1 if ddy > 0 else -1), (1 if ddx > 0 else -1, 0)])
        for sx, sy in steps:
            if (sx, sy) == (0, 0):
                continue
            nx, ny = m.x + sx, m.y + sy
            if self._monster_walkable(nx, ny, bots):
                m.x, m.y = nx, ny
                door = self._mon_door(m, bots)        # 문 타일이면 목격(D30 확장 2차)
                live = [o for o in bots if o['alive'] and not o['won']]
                if any((nx, ny) in self.visible_cells(o['x'], o['y'], MON_SIGHT) for o in live):
                    events.append({'type': 'monster_move', 'id': 'm%d' % m.id,
                                   'monster': m.kind, 'to': [nx, ny],
                                   **({'door': door} if door else {})})
                return                                # 이동 이벤트=봇 시야 안일 때만(도주/배회와 정책 통일)

    def monster_turn(self, bots):
        self._record_positions(bots)                 # D48 개정: 틱 경계 자리 기록(is_moving 의 재료) — 판정·난수 무접촉
        if not self.skills:
            return self._monster_turn(bots)
        starts = {m.id: (m.x, m.y) for m in self.monsters}
        result = self._monster_turn(bots)
        result.extend(SK.monster_status_after_move(self, bots, starts))
        return result

    def _record_positions(self, bots):
        """틱 경계의 자리 기록(D48 개정) — is_moving 의 재료. 스냅샷·관측에 안 나가는 봇 내부 키."""
        for b in bots:
            b['_xy_end_prev'] = b.get('_xy_end')
            b['_xy_end'] = (b['x'], b['y'])

    def _monster_turn(self, bots):
        """독립 시계 몹 AI(2b): SLEEPING/WANDERING/HUNTING + LOS 발각굴림 + 대칭 기습 + 강등.
        처리순서(상호배타):
          ① 기습당함(skip_turns>0) = 이번 턴 행동 스킵(대상 턴 스킵). 단조감소 → 무한루프 없음.
          ② HUNTING = 직교 인접 봇 공격(매트릭스로 매복/정면). 없으면 last_seen 추격;
             LOS 상실 LOSE_GRACE 넘거나 last_seen 도달 → WANDERING 강등(그 턴 종료=턴당 전이 1회).
          ③ SLEEPING/WANDERING = FOV 봇에 *발각굴림만*(인접이어도 공격 X = 봇의 we-ambush 창).
             FOV에 봇 없으면 가끔 한 칸 직교 표류.
        ⚠️ 비-HUNTING 표류(무FOV)는 2a '외길 영구봉쇄' livelock 해약 — SLEEPING 포함, 절대 빼지 말 것.
        ⚠️ 모든 굴림 self.rng/self.d20 경유(발각·유리·표류), 동점 2차키 b['char'] → 시드 재현."""
        events = []
        for m in self.monsters:
            if not m.alive:
                continue
            if m.skip_turns > 0:                          # ① 허 찔림 — 이번 턴 무행동
                m.skip_turns -= 1
                continue
            if m.waking > 0:                              # 막 깬 취약창(TIME_TO_WAKE_UP) 소진 — 행동은 한다
                m.waking -= 1
            live = [b for b in bots if b['alive'] and not b['won']]
            if not live:
                continue
            if m.concealed:                               # ①.5 매복자(Stage 3): 조용히 도사린다 —
                adj = [b for b in live                    #     배회·발각굴림 없음. 직교 인접 봇에 일격.
                       if abs(m.x - b['x']) + abs(m.y - b['y']) == 1]
                if adj:
                    b = min(adj, key=lambda b: b['char'])
                    m.concealed = False                   # 정체 드러남 → 이후는 보통 몹
                    m.state, m.target = 'HUNTING', b['char']
                    m.last_seen, m.lost = (b['x'], b['y']), 0
                    ev = self._monster_attack(m, b, bots)  # 봇 aware_of 에 없음 → they-ambush 자동 성립
                    ev['from_hiding'] = True
                    events.append(ev)
                continue
            if (m.state == 'HUNTING' and not m.desperate and m.flee_frac
                    and m.hp * m.flee_frac <= m.maxhp       # 정의의 ai.flee(D50) — 없으면 도주 안 함
                    and not (m.flee_to == 'ally' and self._ally_monster_beside(m))):   # D51: 동료가 곁이면 도주 대신 같이 싸운다
                m.state, m.target, m.lost = 'FLEEING', None, 0    # 저HP → 도주(SPD FLEEING 린 채용)
                if m.flee_to != 'ally':
                    m.flee_turns = 0                          # D51 ally 모드는 합류↔도주 왕복에도 탈진이 누적된다
                events.append({'type': 'monster_flee', 'id': 'm%d' % m.id, 'monster': m.kind})
            if m.state == 'FLEEING':                      # ②.5 도주: 가까운 봇에게서 멀어진다 / D51 동료에게 붙는다
                seen = self.visible_cells(m.x, m.y, MON_SIGHT)
                near = [b for b in live if (b['x'], b['y']) in seen]
                ally, first = (self._nearest_ally_monster(m, bots) if m.flee_to == 'ally' else (None, None))
                if ally is not None and first is None:     # D51 이미 곁 = 합류: 보이는 봇이 있으면 함께 싸운다, 없으면 곁에서 진정
                    self._join_ally(m, ally, near, events)
                    continue
                if not near:                              # 봇이 안 보이면 → 진정(배회 강등, HP는 안 돈다)
                    if ally is not None:                  #   D51: 갈 동료가 있으면 봇 시야 밖에서도 그쪽으로 계속
                        self._join_step(m, first, bots, events)
                        continue
                    m.lost += 1
                    if m.lost >= LOSE_GRACE:
                        m.state, m.lost = 'WANDERING', 0
                    continue
                m.lost = 0                                # 봇이 보이면 '연속 상실' 리셋(HUNTING과 동일 스펙)
                m.flee_turns += 1
                if m.flee_turns >= m.flee_stamina:        # 탈진 → 필사 반전: 몰린 쥐가 고양이를 문다(정의의 ai.flee.stamina)
                    b = min(near, key=lambda b: (self._cheb(m.x, m.y, b['x'], b['y']), b['char']))
                    m.state, m.desperate = 'HUNTING', True
                    m.target, m.last_seen, m.lost = b['char'], (b['x'], b['y']), 0
                    events.append({'type': 'monster_desperate', 'id': 'm%d' % m.id,
                                   'monster': m.kind})
                    continue                              # 전이 = 턴 소모(턴당 상태전이 1회)
                if ally is not None and self._join_step(m, first, bots, events):   # D51: 동료 쪽으로 한 칸(막히면 아래 기존 도주)
                    continue
                if not self._flee_step(m, near, bots, events):
                    adj = [b for b in near
                           if abs(m.x - b['x']) + abs(m.y - b['y']) == 1]
                    if adj:                           # 궁지 몰린 쥐 — 필사 반격
                        events.append(self._monster_attack(m, min(adj, key=lambda b: b['char']), bots))
                continue
            if m.state == 'HUNTING':                      # ② 추격/교전
                adj = [b for b in live if abs(m.x - b['x']) + abs(m.y - b['y']) == 1]
                if adj:                                   # 직교 인접 봇 = 타겟 무관 즉시 공격(face-to-face/매복)
                    b = min(adj, key=lambda b: b['char'])
                    m.target, m.last_seen, m.lost = b['char'], (b['x'], b['y']), 0
                    events.append(self._monster_attack(m, b, bots))
                    continue
                seen = self.visible_cells(m.x, m.y, MON_SIGHT)
                tgt = next((b for b in live if b['char'] == m.target), None)
                if tgt and (tgt['x'], tgt['y']) in seen:  # 타겟 보임 → last_seen 갱신
                    m.last_seen, m.lost = (tgt['x'], tgt['y']), 0
                else:                                     # 놓침 → grace 카운트, 넘으면 배회 강등
                    m.lost += 1
                    if m.lost >= LOSE_GRACE or (m.x, m.y) == m.last_seen:
                        m.state, m.target, m.lost = 'WANDERING', None, 0
                        continue                          # 강등 = 이번 턴 종료(턴당 상태전이 1회 → 진동 방지)
                self._chase_step(m, bots, events)         # last_seen 향해 한 칸(인접해지면 다음 턴 교전)
                continue
            # ③ SLEEPING / WANDERING — 발각굴림(자동 시야 아님)
            seen = self.visible_cells(m.x, m.y, MON_SIGHT)
            fov = [b for b in live if (b['x'], b['y']) in seen]
            if fov:                                       # FOV에 봇 있음 → 발각굴림(인접이어도 공격 안 함)
                b = min(fov, key=lambda b: (self._cheb(m.x, m.y, b['x'], b['y']), b['char']))
                prox = MON_SIGHT - self._cheb(m.x, m.y, b['x'], b['y'])    # dist1→2 .. dist3→0
                bonus = prox + (WANDER_DETECT_BONUS if m.state == 'WANDERING' else 0)
                if self.d20() + bonus >= DETECT_DC_BASE + b.get('stealth', 0):
                    m.waking = 1 if m.state == 'SLEEPING' else 0   # 잠에서 막 깸 = 1턴 더 기습 가능(취약창)
                    m.state, m.target = 'HUNTING', b['char']
                    m.last_seen, m.lost = (b['x'], b['y']), 0
                    events.append({'type': 'monster_notice', 'id': 'm%d' % m.id,
                                   'monster': m.kind, 'target': b['char']})
                continue                                  # 발각 성패 무관 — FOV 있으면 표류 안 함(막 깸=반응창)
            if self.rng.random() < 0.5:                   # FOV에 봇 없음 → 가끔 표류(외길봉쇄 livelock 방지)
                wx, wy = self.rng.choice([(0, -1), (0, 1), (1, 0), (-1, 0)])
                if self._monster_walkable(m.x + wx, m.y + wy, bots):
                    m.x, m.y = m.x + wx, m.y + wy
                    door = self._mon_door(m, bots)    # 문 타일이면 목격(D30 확장 2차)
                    if any((m.x, m.y) in self.visible_cells(b['x'], b['y'], MON_SIGHT) for b in live):
                        events.append({'type': 'monster_move', 'id': 'm%d' % m.id,
                                       'monster': m.kind, 'to': [m.x, m.y],
                                       **({'door': door} if door else {})})
        return events

    def render(self, bots):
        canvas = [[self.tile(x, y, spectator=True) for x in range(self.w)] for y in range(self.h)]
        for b in bots:
            if b['alive'] and not b['won']:   # 탈출·사망한 영웅은 던전에 없다 → 맵에서 뺀다
                canvas[b['y']][b['x']] = b['char']
        return '\n'.join(''.join(row) for row in canvas)

    def level_snapshot(self):
        """층 전체를 JSON 직렬화(스트림 'level' 라인의 몸통) — 웹/리플레이 뷰어가 엔진 없이
        렌더할 수 있는 진실. grid 는 raw 지형('#'/'.')만 — tile() 관전 글리프가 아니다
        (몹·피처·함정은 각자 배열로 나가므로 겹쳐 그리는 건 소비자 몫)."""
        return {'depth': self.depth, 'w': self.w, 'h': self.h,
                'master_seed': self.master_seed,
                'level_seed': self._derive_seed(self.master_seed, self.depth),
                'grid': [''.join(row) for row in self.grid],
                'exit': list(self.exit),
                'rooms': [{'id': r.id, 'x': r.x, 'y': r.y, 'w': r.w, 'h': r.h,
                           'type': r.type, 'neighbours': list(r.neighbours)}
                          for r in self.rooms],       # feature.room_id 의 해소처(방 하이라이트용)
                'features': [f.as_dict() for f in self.features.values()],
                'traps': [t.as_dict() for t in self.traps],
                'monsters': [m.as_dict() for m in self.monsters],
                **({'gate': {'sealed': bool(self.sealed), 'boss': (self.boss.id if self.boss else None)}}
                   if getattr(self, 'boss_on', False) else {}),   # D65 additive — 보스층: 출구=워프게이트(층 시작 때 봉인 상태·보스 id)
                **({'visual': self.visual} if getattr(self, 'visual', None) else {})}   # 마을 v1(09-11) 시각 레이어 — 던전 층엔 없다


def new_ledger():
    """공간 장부(D17-1) 빈 원장 — 러너가 봇에 꽂아 켠다(bot['ledger']=new_ledger()).
    구조를 한 곳에서 소유(러너·시나리오·검증이 제각각 dict 를 빚으면 드리프트).
    statics=제자리 목격물(id 키) / moving=마지막 목격(몹·동료) / zones=방문 구역.
    장부=층의 기억 — 층 전이 재스폰 때 새로 꽂는다(도감=플레이어의 기억과 대비, D17)."""
    return {'statics': {}, 'moving': {}, 'zones': {}}


def spawn(dungeon, char, bots, min_exit_dist=8, cluster=4, sheet=None, apart=False):
    """캐릭터 시트를 입혀 봇을 던전에 놓는다. sheet=None 이면 내장 HEROES[char]
    (하위호환 — 기존 verify 들의 spawn(d,'1',[]) 그대로 통과). 시트 외부화(party.json)는
    러너가 load_party 로 검증해 sheet= 로 넘긴다 — 시트=사용자 저작물의 원형(UGC 씨앗).
    파티는 함께 출발한다 — 첫 영웅은 출구에서 멀리(즉시 탈출 방지), 다음 영웅은
    그 곁(맨해튼 cluster 이내)에. 출구 바로 옆·맵 양끝 분리를 막는다.
    apart=True(솔로 판)면 그 가정이 뒤집힌다 — 전원이 '첫 영웅'처럼 출구에서 멀리, 그리고
    서로에게서도 SOLO_APART 이상 떨어져 선다. 남남이 같은 던전에서 각자 눈뜨는 그림.
    ⚠️ 'bots 리스트 = 파티' 가정을 여기서 더 심화하지 말 것(솔기 노트) — 살아있는 세상에선
    파티=에이전트 간 관계(가입/탈퇴)라 이 등식이 깨진다. apart 가 그 솔기의 첫 사용처다."""
    sheet = sheet or HEROES[char]
    ex, ey = dungeon.exit

    def free(x, y):
        return (dungeon.grid[y][x] == FLOOR
                and not dungeon.feature_at(x, y)                          # 피처(출구·보물·상자·샘…) 위 출발 금지
                and not any((t.x, t.y) == (x, y) for t in dungeon.traps)  # 숨은 함정 위 출발 금지
                and not dungeon.monster_at(x, y)
                and not any(b['x'] == x and b['y'] == y for b in bots))

    base = [(x, y) for y in range(dungeon.h) for x in range(dungeon.w) if free(x, y)]
    lone = [(x, y) for (x, y) in base            # 홀로 서는 자리: 출구에서 멀고 몹과도 떨어진 곳
            if abs(x - ex) + abs(y - ey) >= min_exit_dist
            and all(abs(x - m.x) + abs(y - m.y) >= 2 for m in dungeon.monsters)]
    if apart:                      # 솔로 판: 전원이 '첫 영웅'처럼 놓인다 — 출구에서도, 서로에게서도
        gap = max(SOLO_APART, (dungeon.w + dungeon.h) // 5)   #   멀리. 간격은 맵 크기를 탄다.
        cands = []
        while not cands and gap >= 2:
            cands = [(x, y) for (x, y) in lone
                     if all(abs(x - b['x']) + abs(y - b['y']) >= gap for b in bots)]
            gap //= 2              # 맵이 좁아 못 벌리면 단계적 완화(빈 후보로 base 추락하는 것 방지)
    elif bots:                     # 둘째+ 영웅: 먼저 온 동료 곁에 (함께 출발)
        a = bots[0]
        cands = [(x, y) for (x, y) in base
                 if 1 <= abs(x - a['x']) + abs(y - a['y']) <= cluster]
    else:                          # 첫 영웅: 출구에서 멀고 몬스터와 떨어진 곳
        cands = lone
    if not cands:                  # 조건이 너무 빡빡하면 완화
        cands = base
    x, y = dungeon.rng.choice(cands)
    dungeon.visited.add((x, y))              # 시작 칸도 '가본 곳'
    return {**SK.spawn_fields(dungeon, sheet, char), 'char': char, 'x': x, 'y': y,
            'hp': sheet['hp'], 'maxhp': sheet['hp'],
            'str': sheet['str'], 'dex': sheet['dex'], 'wdmg': sheet['wdmg'],
            'stealth': sheet['stealth'],    # 발각 DC 가산(은신) — 도적이 잘 안 들킴
            'search_r': sheet['search_r'],  # 인지 반경(Stage 3) — 도적 2 / 전사 1
            'atk_range': int(sheet.get('atk_range') or 1),   # 공격 사거리(맨해튼, 2026-07-26)
                                            # 근접 1(기본·하위호환) / 궁수 2. 2 이상이면 사선이
                                            # 필요하고(벽·문이 막는다. 동료는 안 막는다) 명중을
                                            # STR 대신 DEX 로 굴린다 — 활은 힘이 아니라 겨눔이다
            'job': sheet['job'], 'sex': sheet['sex'], 'persona': sheet['persona'],
            # ↓ 선택 4필드 = 프롬프트 전용(성격 연기·관계) — 엔진 판정은 절대 안 읽는다
            'name': sheet.get('name'), 'speech': sheet.get('speech'),
            'goal': sheet.get('goal'),
            'background': sheet.get('background'),   # D31(09-05) 배경(자유 입력 — load_party 가 정제) — 프롬프트 전용
            'traits': list(sheet.get('traits') or []),   # 성격 키워드 원본 — run_meta 기록용(프롬프트 미노출)
            'look': sheet.get('look'),      # D37(09-06) 외형 — run_meta 기록용·뷰어 전용. 엔진·프롬프트 무접촉
            'relationships': dict(sheet.get('relationships') or {}),
            'bag': 0, 'alive': True, 'won': False,
            'potions': 0,                   # 소지 회복 물약(07-17) — 첫 소비 아이템. 층 이월은
                                            # 러너 재스폰이 담당(bag 이월 선례)
            'status': {},                   # 상태 태그(D34, 09-06): 태그→{n, by, since}. 몹·함정의 특수가
                                            # 붙이고 휴식(D35)만 지운다. 층 이월=러너 재스폰(물약 선례)
            'bleed_steps': 0,               # 출혈 걸음 부기(BLEED_STEPS 마다 HP 1)
            'slow_beat': 0,                 # 둔화 박자(SLOW_EVERY 마다 한 칸)
            'rest': None,                   # 휴식 장부(D35): {n, healed, allies} — order='rest' 동안만
            'relations': ({oc: {'bones': {}, 'total': 0, 'line': str(txt), 'line_turn': 0,
                                'line_src': 'sheet', 'queue': []}
                           for oc, txt in dict(sheet.get('relationships') or {}).items()}
                          if getattr(dungeon, 'relations', False) else {}),
                                            # 관계 장부(D36): 상대→{bones{kind:{n,last}}, total(약한 뼈 합),
                                            # line(살 — 시트 관계 칸이 초기값, 캐릭터가 겹쳐 쓴다),
                                            # line_turn, line_src(sheet/self), queue(청할 초대)}.
                                            # 엔진은 line 을 절대 읽지 않는다(D15② 불투명 왕복)
            'weapon': None, 'armor': None,  # 장비 슬롯 2(07-30) — {'name','bonus'} 또는 None.
                                            # 시트 wdmg=기본 무장(불가침), 장비=위에 얹는 보정.
                                            # 층 이월은 러너 재스폰(물약 선례)
            'order': None, 'path': [],      # 핑 목표 id + 엔진이 BFS로 깐 자동보행 경로
            'aware_of': set(),              # 인지한 몹 id (newly 판정 + 매트릭스 봇쪽 비트)
            'known': None,                  # 도감(D9): 아는 종키 set — None=게이팅 끔(하위호환).
            'book': None,                   # 도감 원장 기록(D53): {종키: {n, deep?}} — None=옛 2층(등재 즉시 본문).
                                            #   러너가 발급기(bestiary)의 set 을 꽂는다(획득 즉시 obs 반영)
            'last': None,                   # 직전 행동/피격 결과 메모(D1 개정) — view 가 obs.last 로 노출
            'trail': [], 'trail_gap': 0,    # 자기 행동 궤적(D38, 09-06) — 마지막 view() 이후 결과 목록(노출 후 소거)
            'obj_tags': {},                 # 오브젝트 태그(D39, 09-06) — fid→{n, note?}. 층 재스폰=초기화
            'floor': {'since': dungeon.turn, 'n': {}, 'w': {}},   # 층 집계(D40 ②) — 이 층의 자기 사건·목격 횟수(라벨→n)
            'floors': [],                   # 지난 층 결산 목록(D40 ②) — 러너가 층 전이 때 얼려 이월
            'critical': False,              # 위급(D40) 상태 플래그 — 전이 사건의 기준. 러너가 층 넘어 이월
            'witnessed': [],                # 목격(D18 A-3): 시야 내 동료 피격/전사 사실 축적 —
                                            # view 가 1회성 노출·소거. 스냅샷 화이트리스트 밖(계약 불변)
            'memories': [],                 # 기억(D22): 목격한 중대사(v0=fallen 전사) — 휘발 0,
                                            # view 가 매 결정 재제시. 층 이월=러너(물약 선례). 밖
            'follow_idle': None,            # 동행 고착 카운터(D18 FOLLOW_IDLE) — (x, y, n):
                                            # 곁 대기 중 대상 제자리 연속 관측. 화이트리스트 밖
            'paced': None,                  # 교대 양보 메모(D18 개정 07-17) — (동료char, x, y):
                                            # 같은 방향 행군 동료에게 한 박자 양보한 상황. 같은 상황
                                            # 재현 시 교대 강행(맞교대 셔틀·순환 대기 차단). 밖
            'searched': set(),              # 이 봇이 능동 수색으로 살핀 칸(자기 행동 기억 — 세계 정보
                                            # 아님. 리모컨 수색 라벨의 '이미 살폈다' 사실 주석 근거)
            'ledger': None,                 # 공간 장부(D17-1): None=끔(도감 known=None 선례 —
                                            # 기존 verify/헤들리스 무변경 통과). 러너가 new_ledger()
                                            # 를 꽂아 켠다. 층 전이=재스폰에서 새 원장(층의 기억)
            'plan': []}                     # 작정(D16) 남은 수 — 층 전이는 재스폰(새 dict)이라 자동
                                            # 리셋(target id 가 층-로컬. intent 와 같은 논리)


def bot_snapshot(b):
    """봇 dict → 스트림(JSONL) 스냅샷. path 는 제외 — 핑 시점 BFS 고정이라 order+현재
    스냅샷으로 재유도가 일반적으로 안 된다(정확 복원 = 시드+decisions 리플레이. order 는 목표 표시용).
    aware_of 는 정렬 리스트(JSON 가능 + 결정론적 직렬화). order 는 raw('@x,y' 포함) —
    스트림은 관전자/웹 데이터라 시야-온리 마스킹(obs 계약)의 대상이 아니다."""
    return {**SK.snapshot(b), 'char': b['char'], 'job': b['job'], 'sex': b['sex'],
            'x': b['x'], 'y': b['y'], 'hp': b['hp'], 'maxhp': b['maxhp'],
            'bag': b['bag'], 'alive': b['alive'], 'won': b['won'],
            'potions': b.get('potions', 0),   # 회복 물약 소지(07-17 additive)
            'weapon': b.get('weapon'), 'armor': b.get('armor'),   # 장비(07-30 additive)
            'order': b.get('order'),
            **({'approach': dict(b['approach'])} if b.get('approach') and b.get('order') else {}),
            **({'status': sorted(b['status'])} if b.get('status') else {}),   # 상태 태그(D34 additive)
            **({'relations': {oc: {k: v['n'] for k, v in e['bones'].items() if v['n']}
                              for oc, e in sorted(b['relations'].items())
                              if any(v['n'] for v in e['bones'].values())}}
               if any(v['n'] for e in (b.get('relations') or {}).values()
                      for v in e['bones'].values()) else {}),    # 관계 뼈 횟수(D36 additive — 살은 decisions)
            'aware_of': sorted(b.get('aware_of', set()))}


# ── 더미 두뇌 (엔진 검증용·폴백). 봇 자리는 brains.claude_brain 이 채운다. ──
# 핑 모델(v3): 인접 적/보물→즉시, 보이는 출구/보물→핑, 아니면 explore(시야 내 미지의 문).
# 출구 beacon 폐기 — 출구는 sights['exit']가 있을 때(=보일 때)만 쓴다.
# 결정론적(전역 random 미사용) — 같은 세계 시드면 더미 플레이도 재현된다.
def dummy_brain(obs, char='?'):
    s = obs['sights']
    for m in s['monsters']:                          # 인접 몬스터 → 공격(도망가는 건 안 쫓아가 침)
        if m['adj']:
            return {'type': 'attack', 'target': m['id']}
    for f in s['features']:                          # 인접 보물/상자 → 줍기·열기(자동회수 안전망)
        if f['type'] in ('treasure', 'chest') and f['adj']:
            return {'type': 'interact', 'target': f['id']}
    gear = obs.get('gear') or {}
    for f in s['features']:                          # 인접 장비(07-30): 엄격히 더 좋을 때만 걸친다
        if f['type'] in ('weapon', 'armor') and f['adj']:   # (같거나 낮으면 무시 — 스왑으로 떨어진
            cur = gear.get(f['type'])                       #  헌 장비를 되집는 왕복 진동 방지)
            if GEAR_KINDS.get(f['name'], 0) > (cur['bonus'] if cur else 0):
                return {'type': 'interact', 'target': f['id']}
    ex = s.get('exit')
    if ex and ex.get('adj'):                          # 곁에 계단 → 하강 시도. 파티가 안 모였으면
        return {'type': 'interact', 'target': 'exit'}  # wait_allies = 그 자리서 기다린다(제자리 대기).
        # ('데리러 가기'는 일부러 안 한다 — 둘 다 데리러 나서면 서로 엇갈리는 왕복 진동(livelock).
        #  동료의 explore 폴백이 결국 계단으로 수렴하므로 기다림이 결정론적으로 안전. 데리러
        #  가는 드라마는 LLM 봇의 선택지(goto b<char>)로만 남긴다.)
    if obs['hp'] * 2 <= obs['maxhp']:                # 많이 다쳤다 → 물약(확정) 먼저, 없으면 샘(도박)
        if obs.get('potions'):
            return {'type': 'drink'}
        fts = [f for f in s['features'] if f['type'] == 'fountain']
        if fts:
            near = min(fts, key=lambda f: f['dist'])
            if near['adj']:
                return {'type': 'interact', 'target': near['id']}
            return {'type': 'goto', 'target': near['id']}
    treas = [f for f in s['features'] if f['type'] in ('treasure', 'potion')]
    if treas:                                        # 보이는 보물 → 가까운 것 핑
        return {'type': 'goto', 'target': min(treas, key=lambda f: f['dist'])['id']}
    if ex:                                            # 계단이 보이면 → 계단으로
        return {'type': 'goto', 'target': 'exit'}
    if obs.get('job') == '전사':                     # 전사 = 보이는 몹에 돌격(단 도주몹은 안 쫓는다).
                                                     # 그 외 직업(도적·음유시인…)은 explore 폴백 — 바드가
                                                     # 싸움을 안 찾아다니는 건 캐릭터에 맞다(의도).
        hostile = [m for m in s['monsters'] if m['state'] != 'FLEEING']
        if hostile:
            return {'type': 'goto', 'target': min(hostile, key=lambda m: m['dist'])['id']}
    return {'type': 'explore'}                        # 볼 게 없으면 탐색(엔진이 미지의 문으로)


def run(max_turns=300, brain=dummy_brain, verbose=True):
    """틱 기반 루프: order 있으면 엔진 자동보행(LLM 0), 없으면 두뇌 재결정(핑/공격). max_turns=틱."""
    d = Dungeon()
    bots = []
    bots.append(spawn(d, '1', bots))
    bots.append(spawn(d, '2', bots))
    for tick in range(1, max_turns + 1):
        d.turn = tick                                       # 장부 목격 스탬프(판정 무관여)
        for b in bots:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                d.step_order(b, bots)                       # 자동보행(LLM 0콜)
            else:
                d.act(b, brain(d.view(b, bots), b['char']), bots)   # 재결정: 핑/공격/상호작용
        d.monster_turn(bots)
        if all(b['won'] or not b['alive'] for b in bots):
            break
    if verbose:
        print(d.render(bots))
        for b in bots:
            state = '탈출' if b['won'] else ('전사(戰死)' if not b['alive'] else 'HP %d' % b['hp'])
            print(f"  봇{b['char']}({b['job']}): pos=({b['x']},{b['y']})"
                  f" 보물={b['bag']} 물약={b.get('potions', 0)} {state}")
        alive_m = sum(1 for m in d.monsters if m.alive)
        print(f"  몬스터 생존 {alive_m}/{len(d.monsters)},  함정 발동 "
              f"{sum(1 for t in d.traps if t.sprung)}/{len(d.traps)}")
    return d, bots


if __name__ == '__main__':
    run()
