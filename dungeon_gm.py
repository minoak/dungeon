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

import os
import random
from collections import deque

WALL, FLOOR, EXIT, TREASURE, MONSTER, TRAP = '#', '.', '>', '$', 'M', '^'
CHEST, FOUNTAIN = '=', '~'      # 방 콘텐츠(Stage 3): 상자(도박)·샘(회복 도박)
LURKER, HIDDEN = 'm', '*'       # 관전자 전용(극적 아이러니): 숨은 적/숨은 보물. 봇 시야(view)엔 절대 안 나간다.
UNKNOWN_BEAST = '낯선 짐승'     # 도감(D9) 미등재 몬스터의 obs 표기 — 보이지만 정체를 모른다.


def _wound_label(hp, maxhp):
    """육안 부상 등급(D18 A-4) — 남의 숫자 HP는 볼 수 없다: 겉보기 어휘 4단 고정(튜닝마라).
    빈사 경계 1/3 은 몹 도주 경계(FLEE_FRAC)와 같은 눈금 — 세계가 한 자로 잰다. 순수 파생(굴림 없음)."""
    if hp >= maxhp:
        return '멀쩡'
    if hp * 3 <= maxhp:
        return '빈사'
    if hp * 3 <= maxhp * 2:
        return '다침'
    return '가벼운 상처'


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
PLAN_MAX = 2             # 작정(D16): 현재 행동에 이어 미리 정해둘 수 있는 수의 상한 —
                         # 귀머거리 창(작정 집행 중엔 inbox 를 다음 결정점까지 못 읽음) 억제
DETOUR_FACTOR = 2        # 사회적 대우회 감지(D18): 동료를 피해 깐 경로가 '동료 없다 치고'의 최단 대비
DETOUR_SLACK = 2         #   FACTOR배+SLACK칸을 넘고, 그 최단길 위에 동료가 서 있으면 → 말없는 행군
                         #   대신 blocked 보고(누가 막는지 allies 로) — 라이브 22틱 두란 서쪽 행군 부검.
                         #   지형이 원래 먼 것(free 도 길다)은 정당한 지리 — 감지 대상 아님.
FOLLOW_IDLE = 3          # 동행 고착 해약(D18): 곁 대기 중 대상이 이만큼 연속 틱 제자리면 동행 종료
                         #   (result=idle) → 재결정. 동행은 '따라 걷기'다 — 아무도 안 걸으면 성립하지
                         #   않는다. 상호 동행 삼각 고착(fellowsmoke 120틱 결정 5회 실측)=흡수 상태의
                         #   물리적 제거. 파트너 판정 2026-07-11: "셋이 서서 세 턴이면 어색해질 시간"
                         #   — K=3 고정(튜닝마라).

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
    concealed: 숨은 적(Stage 3 인지판정). id: 핑 대상."""
    def __init__(self, x, y, kind='고블린', hp=6, atk=2, dmg=2, ac=12, mid=0):
        self.x, self.y, self.kind = x, y, kind
        self.hp, self.maxhp = hp, hp
        self.atk, self.dmg, self.ac = atk, dmg, ac
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

    def as_dict(self):
        """스트림(JSONL) 직렬화 — 관전자/웹 데이터 계약(STREAM_FORMAT.md).
        AI 내부 장부(last_seen/lost/skip_turns/waking/flee_turns)는 제외 —
        resume 은 시드+decisions 리플레이로 하지, 스냅샷 복원으로 하지 않는다."""
        return {'id': self.id, 'kind': self.kind, 'x': self.x, 'y': self.y,
                'hp': self.hp, 'maxhp': self.maxhp, 'ac': self.ac,
                'atk': self.atk, 'dmg': self.dmg, 'alive': self.alive,
                'state': self.state, 'concealed': self.concealed,
                'target': self.target, 'desperate': self.desperate}


# 함정 패밀리(Stage 3, SPD 33종→3종 린 스타터): 베이스 클래스 1개 + kind 테이블.
#   spike = 기본 피해 / dart = 독침(가벼운 피해·회피 어려움) / alarm = 경보(피해 0, 층의 몹 일제 각성
#   = justAlerted 굴림 우회 → 함정이 인식 시스템에 결합되는 지점. 줄당 연출 최고).
TRAP_KINDS = {
    'spike': {'name': '가시 함정', 'dc': 13, 'dmg': 3},
    'dart':  {'name': '독침 함정', 'dc': 14, 'dmg': 2},
    'alarm': {'name': '경보 함정', 'dc': 13, 'dmg': 0},
}


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
    __slots__ = ('id', 'type', 'name', 'x', 'y', 'room_id', 'concealed', 'perception_gate')

    def __init__(self, fid, ftype, name, x, y, room_id=None,
                 concealed=False, perception_gate=0):
        self.id, self.type, self.name = fid, ftype, name
        self.x, self.y, self.room_id = x, y, room_id
        self.concealed, self.perception_gate = concealed, perception_gate

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


class Dungeon:
    def __init__(self, seed=7, depth=1, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1):
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
        self.rooms = self._carve_rooms()
        self._connect(self.rooms)
        self._build_room_graph()   # 방 인접 그래프(connect 체인) — BFS·'방 핑'의 토대
        self._place_targets(n_monsters, n_traps, n_lurkers)
        self._assign_room_types()  # entrance/exit/standard 타입 부여 (출구 배치 후)
        self._classify_tiles()     # 각 바닥 칸에 'room'/'corridor' 속성 부여

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
    def from_ascii(cls, rows, seed=7, depth=1, monsters=None, traps=None):
        """디버깅/시나리오 모드(장면 저작, scenario.py 소비): 생성기 대신 손으로 그린
        문자 맵으로 층을 짓는다. 판정·시야·자동보행·스트림은 생성 층과 완전 동일(같은 코드) —
        조립되는 건 세계가 아니라 '장면'이다.
        기호: '#'/공백=벽 · '.'=바닥 · '>'=출구(필수) · '$'보물 · '='상자 · '~'샘 ·
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
        starts, mslots, tslots = {}, [], []
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in (WALL, ' '):
                    continue
                d.grid[y][x] = FLOOR
                if ch == EXIT:
                    d._exit_fid = d._add_feature('exit', '출구', x, y)
                elif ch == TREASURE:
                    d._add_feature('treasure', '보물', x, y)
                elif ch == '=':
                    d._add_feature('chest', '상자', x, y)
                elif ch == '~':
                    d._add_feature('fountain', '샘', x, y)
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
            m = Monster(x, y, kind=t.get('kind', '고블린'), hp=t.get('hp', 6),
                        atk=t.get('atk', 2), dmg=t.get('dmg', 2),
                        ac=t.get('ac', 12), mid=i)
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
        return d, starts

    # ── 맵 생성 (로그라이크식 방+통로 — 기존 검증된 로직 그대로) ──
    def _carve_rooms(self, n=5):
        rooms = []
        attempts = 0
        while len(rooms) < n and attempts < 60:
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
        centers = [r.center for r in rooms]
        for (x1, y1), (x2, y2) in zip(centers, centers[1:]):
            for x in range(min(x1, x2), max(x1, x2) + 1):
                self.grid[y1][x] = FLOOR
            for y in range(min(y1, y2), max(y1, y2) + 1):
                self.grid[y][x2] = FLOOR

    def _build_room_graph(self):
        """connect 가 이은 '체인'을 그래프로 기록(버리지 말고 기억). 양방향 neighbours.
        지금 생성기는 연속쌍을 잇는 선형 체인 → 그래프도 경로(트리)지만 모든 방 연결됨."""
        for r in self.rooms:
            r.neighbours = []
        for a, b in zip(self.rooms, self.rooms[1:]):   # _connect 와 동일한 연속쌍
            if b.id not in a.neighbours:
                a.neighbours.append(b.id)
            if a.id not in b.neighbours:
                b.neighbours.append(a.id)

    def _place_targets(self, n_monsters, n_traps, n_lurkers=0):
        """출구·보물·몬스터·함정·방콘텐츠를 겹치지 않게 흩뿌린다. 출구·보물 = Feature 로 흡수.
        출구는 가능하면 '방 안'에 둔다(ExitRoom 성립 → Stage 2 기본 핑 목표).
        Stage 3 추가: 매복몹(concealed)·함정 종류 순환(경보 포함)·상자/샘·숨은 보물(도적 인지의 보상)."""
        floors = [(x, y) for y in range(self.h) for x in range(self.w)
                  if self.grid[y][x] == FLOOR]
        self.rng.shuffle(floors)
        room_floors = [c for c in floors if self._room_id_at(*c) is not None]
        ex, ey = room_floors[0] if room_floors else floors[-1]
        self._exit_fid = self._add_feature('exit', '출구', ex, ey)
        used = {(ex, ey)}
        pool = [c for c in floors if c not in used]
        for _ in range(min(3, len(pool))):
            x, y = pool.pop()
            self._add_feature('treasure', '보물', x, y)
        for i in range(n_monsters):
            if pool:
                x, y = pool.pop()
                self.monsters.append(Monster(x, y, mid=i))
        for i in range(n_lurkers):            # 매복몹: 봇 obs·맵(봇시야)에 안 나감 → they-ambush 의 몸통
            if pool:
                x, y = pool.pop()
                lurk = Monster(x, y, kind='그림자거미', hp=5, atk=3, dmg=3, ac=13,
                               mid=n_monsters + i)
                lurk.concealed = True
                self.monsters.append(lurk)
        kinds = ['spike', 'alarm', 'dart']    # 종류 순환 — 함정 2개 이상이면 경보가 반드시 들어간다
        for i in range(n_traps):
            if pool:
                x, y = pool.pop()
                self.traps.append(Trap(x, y, kind=kinds[i % len(kinds)]))
        if pool:                              # 상자: 열면 보물 2개 or 독침(리스크/보상 도박)
            x, y = pool.pop()
            self._add_feature('chest', '상자', x, y)
        if pool:                              # 샘: 마시면 회복 or 오염(가벼운 도박, 대체로 이득)
            x, y = pool.pop()
            self._add_feature('fountain', '샘', x, y)
        if pool:                              # 숨은 보물: 인지(도적)로만 드러난다 — 직업 보상의 몸통
            x, y = pool.pop()
            self._add_feature('treasure', '숨은 보물', x, y,
                              concealed=True, perception_gate=PASSIVE_DC)

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

    # ── 피처 / 방 그래프 헬퍼 ───────────────────────────────────
    def _add_feature(self, ftype, name, x, y, concealed=False, perception_gate=0):
        fid = self._next_fid
        self._next_fid += 1
        self.features[fid] = Feature(fid, ftype, name, x, y,
                                     room_id=self._room_id_at(x, y),
                                     concealed=concealed, perception_gate=perception_gate)
        return fid

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

    def walkable(self, x, y, bots):
        """봇이 들어갈 수 있나. 벽·다른 봇·몬스터가 막으면 못 간다(몬스터는 공격 대상).
        탈출(won)한 봇은 던전을 떠났으므로 아무것도 막지 않는다(출구 칸 막힘 방지).
        설계 결정: concealed(매복) 몹도 막는다 — 그 칸에 뭔가 '물리적으로 실재'하므로 경로가 막히는 건
        세계의 사실이다(시야-온리는 obs 층의 계약). 외길 봉쇄는 explore→출구 best_effort가 봇을 몹
        직전 칸까지 안내→매복 일격 발화로 자연 해소된다(verify_stage3 300시드 무교착 실측)."""
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False
        if self.grid[y][x] == WALL:
            return False
        if any(b['x'] == x and b['y'] == y and b['alive'] and not b['won'] for b in bots):
            return False
        if self.monster_at(x, y):
            return False
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

    def path_to(self, sx, sy, tx, ty, bots, best_effort=False, avoid_traps=True):
        """(sx,sy)→(tx,ty) 최단 경로. 이동=8연결(대각선 코너컷 금지), walkable 재사용.
        목표가 못 들어가는 칸(몹·봇·가구)이면 → 목표의 **직교 인접** walkable 칸들을
        목표집합으로 BFS, 그중 *도달 가능한 가장 가까운* 칸까지 길을 낸다.
          · 직교 인접만: 전투·상호작용은 맨해튼 1(직교)이라(_attack/monster_turn) 대각 접근은 무용.
          · '도달 가능한' 가장 가까운 칸: 맨해튼 최단 한 칸만 고르면 그 칸이 막혔을 때 거짓 '도달불가'.
          · avoid_traps(Stage 3): '드러난' 미발동 함정 칸은 피해서 길을 낸다(인지의 보상 = 우회).
            우회로가 없으면 함정 경유 허용으로 1회 재시도(외길 봉쇄 방지) — 그 땐 알고 건너니
            _enter_cell 에서 조심 보너스(CAREFUL_BONUS)를 받는다.
        반환: 시작 제외, 밟을 칸 목록(목표/접근칸=마지막). 도달불가/이미도착이면 []. (Stage2 자동보행용)"""
        tblock = ({(t.x, t.y) for t in self.traps if not t.hidden and not t.sprung}
                  if avoid_traps else set())
        if self.walkable(tx, ty, bots):
            goals = {(tx, ty)}
        else:                                     # 점유/가구 → 직교 인접 walkable 칸이 목표
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
                if (nx, ny) in prev or not self.walkable(nx, ny, bots):
                    continue
                if (nx, ny) in tblock and (nx, ny) not in goals:
                    continue                      # 드러난 함정은 밟지 않는 경로로(목표 자신이면 허용)
                if dx and dy and not (self.walkable(cx + dx, cy, bots)
                                      and self.walkable(cx, cy + dy, bots)):
                    continue                      # 대각선 코너컷 금지(양 직교칸 둘 다 뚫려야)
                prev[(nx, ny)] = (cx, cy)
                q.append((nx, ny))
        if reached is None:
            if tblock:                            # 함정 우회로가 없다 → 함정 경유 허용으로 재시도(외길 봉쇄 방지)
                return self.path_to(sx, sy, tx, ty, bots,
                                    best_effort=best_effort, avoid_traps=False)
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
    def _sight_blocked(self, cx, cy, tx, ty):
        """(cx,cy)↔(tx,ty) 직선 '중간'에 벽이 있으면 시야가 가린다. 타겟 자신이 벽이면 보인다(중간만 막는다).
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
                break                       # 타겟 도달 — 타겟(첫 벽 가능)은 보인다
            if self.grid[y][x] == WALL:
                return True                 # 중간에 벽 → 그 너머는 가려짐
        return False

    def _bearing(self, dx, dy):
        h = 'E' if dx > 0 else ('W' if dx < 0 else '')
        v = 'S' if dy > 0 else ('N' if dy < 0 else '')
        return (v + h) or '-'

    def visible_cells(self, cx, cy, r=SIGHT):
        """(cx,cy)이 지금 보는 칸 집합 — (2r+1)² 중 벽에 안 가린 칸(LOS). 대칭(A↔B)."""
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

        def _knowledge(kind_key, entry):
            """아는 종 = lore 주입, 모르는 몹 = 정체 은닉(낯선 짐승). 시야-온리 불변 —
            무엇이 '보이는가'는 그대로, 바뀌는 건 그것을 '무엇이라 아는가'뿐.
            획득은 발급기(bestiary.py, 스트림 소비자) 소관 — 도감에 있어도 매복은 당한다(D9)."""
            if known is None:
                return entry
            if kind_key not in known:
                if kind_key.startswith('monster:'):
                    entry['kind'] = UNKNOWN_BEAST          # 처음 겪는 종 — 이름·습성 미상
            else:
                lo = self.lore.get(kind_key, {}).get('lore')
                if lo:
                    entry['lore'] = lo
            return entry

        mons = [_knowledge('monster:' + m.kind,
                           {'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state,
                            'aware': (m.state == 'HUNTING' and m.target == bot['char']),  # 이 몹이 *날* 노린다(매트릭스 신호)
                            'hp': m.hp, **bear(m.x, m.y)})
                for m in self.monsters
                if m.alive and not m.concealed and (m.x, m.y) in seen]
        feats = [_knowledge('feature:' + f.type,
                            {'id': 'f%d' % f.id, 'type': f.type, 'name': f.name,
                             'visited': (f.x, f.y) in self.visited, **bear(f.x, f.y)})
                 for f in self.features.values()
                 if f.type != 'exit' and not f.concealed and (f.x, f.y) in seen]
        ex, ey = self.exit                                       # v3: 출구 = beacon 아님 → 보일 때만
        exit_obj = ({'id': 'exit', 'type': 'exit', 'name': '출구', **bear(ex, ey)}
                    if (ex, ey) in seen else None)
        led = bot.get('ledger')            # D17 스위치: 장부 켠 판만 구역 어휘·known 노출
                                           # (끈 판 obs 는 구판과 자구까지 동일 — 게이트 무수정 통과)
        way_keys = (('bearing', 'dist', 'visited', 'zone') if led is not None
                    else ('bearing', 'dist', 'visited'))
        ways = [{k: w[k] for k in way_keys}            # 미지로 트인 출입구(셀좌표는 엔진만 보유.
                for w in self._ways(cx, cy, seen)]     #  zone=어느 구역으로 트였나, D17-2)
        allies = [{'id': 'b%s' % b['char'], 'char': b['char'],
                   'condition': _wound_label(b['hp'], b['maxhp']),   # 겉보기 부상 등급(A-4) —
                   **bear(b['x'], b['y'])}                           #   보이는 동료만(시야-온리)
                  for b in bots
                  if b['alive'] and not b['won'] and b['char'] != bot['char']
                  and (b['x'], b['y']) in seen]
        # party = 파티 명단(좌표 없음 — 시야-온리 유지). 안 보여도 'b<char>' 핑은 허용(파티 감각):
        # TRPG에서 일행의 대략적 방향은 안다는 통념. 하강 조율(동료 데리러 가기)의 통로.
        party = [{'char': o['char'], 'job': o['job'], 'alive': o['alive'],
                  'won': o['won'], 'visible': (o['x'], o['y']) in seen}
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
                if (e['x'], e['y']) in seen and e['type'] != 'trap':
                    continue                           # 지금 보이는 건 sights 소관(중복 금지).
                                                       # 함정만 예외 — sights 에 함정 어휘가 없어
                                                       # 시야에 들면 구조화 obs 에서 증발하는
                                                       # 비대칭 방지(리뷰 픽스): 중복이 아니다
                ent = {'type': e['type'], 'name': e['name'],
                       'zone': e['zone'], 'turn': e['turn']}
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
                ent = {'id': e['id'], 'zone': e['zone'], 'turn': e['turn']}
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
            if m['adj']:
                _add('attack', m['id'], '공격: %s (인접)' % _mfact(m))
        if exit_obj and exit_obj['adj']:
            _add('interact', 'exit',
                 '계단에서 하강 시도 (규칙: 살아있는 파티 전원이 계단 근처에 모여야 내려간다)')
        for f in feats:
            if f['adj']:
                _add('interact', f['id'], '상호작용: %s %s (발밑/인접)' % (f['name'], f['id']))
        if exit_obj and not exit_obj['adj']:
            _add('goto', 'exit', '이동: 계단 exit — %s, 거리 %d'
                 % (exit_obj['bearing'], exit_obj['dist']))
        for f in feats:
            if not f['adj']:
                _add('goto', f['id'], '이동: %s %s — %s, 거리 %d'
                     % (f['name'], f['id'], f['bearing'], f['dist']))
        for m in mons:
            if not m['adj']:
                _add('goto', m['id'], '접근: %s — %s, 거리 %d'
                     % (_mfact(m), m['bearing'], m['dist']))
        names = {o['char']: (o.get('name') or o['job']) for o in bots}
        vis_allies = {a['char'] for a in allies}
        for a in allies:
            if a['adj']:
                continue        # 이미 곁(직교 인접)의 동료 '합류'는 no-op — 다른 adj 분기와 대칭
            _add('goto', a['id'], '합류: %s(봇%s) — %s, %s, 거리 %d'
                 % (names.get(a['char'], '동료'), a['char'], a['condition'],
                    a['bearing'], a['dist']))          # 등급 병기(A-4) — 빈사 동료가 눈에 밟히게
        for p in party:
            if p['alive'] and not p['won'] and p['char'] not in vis_allies:
                _add('goto', 'b%s' % p['char'],        # 안 보이는 동료 = 등급 미병기(시야-온리)
                     '찾아가기: %s(봇%s) — 지금 안 보임(파티 감각으로 접근)'
                     % (names.get(p['char'], '동료'), p['char']))
        for a in allies:                               # 동행(D18 A-5) — 보이는 동료마다 지속 order
            ob = next(o for o in bots if o['char'] == a['char'])
            mutual = str(ob.get('order') or '') == 'follow:b%s' % bot['char']
            _add('follow', a['id'],                    # ※주석=사실만(수색 '이미 살폈다' 선례).
                 '동행: %s(봇%s) 곁을 따라 걷는다 — 새 일이 생기면 멈추고 묻는다%s'
                 % (names.get(a['char'], '동료'), a['char'],
                    ' ※ 그는 지금 너를 따르는 중이다 — 서로 따르면 아무도 못 움직인다'
                    if mutual else ''))                # 곁에서 나를 계속 따르는 행동은 눈에 보인다
                                                       # (보이는 동료 한정=allies 루프 — 시야-온리)
        # 돌아가기(D17-1 귀환 핑) — 장부의 제자리 물건(id 있는 것)로 시야 밖 복귀. 라벨=사실만
        # (어디서·언제 봤나). '그 사이 없어졌을 수 있다'는 세계의 진실 — 가서야 안다(lost 드라마).
        if known_obs is not None:
            for e in known_obs['statics']:             # 이미 '지금 안 보이는 것'만 담겨 있다
                if 'id' not in e:
                    continue                           # 함정 항목(정보만) — 핑 대상 아님
                ago = self.turn - e['turn']
                _add('goto', e['id'], '돌아가기: %s — %s에서 봄(%s), 지금은 시야 밖'
                     % (e['name'], e['zone'],       # '안 보임'은 '사라짐'으로 오독됨(프로브 실측)
                        ('%d턴 전' % ago) if ago > 0 else '방금'))
        # 수색 라벨 — 지금 살필 반경이 전부 '이미 살핀 곳'이면 그 사실을 붙인다(자기 행동 기억).
        # A/B 실측에서 이 주석 없이는 같은 자리 수색 반복 평균 70회(수색 합창 루프)로 판이 죽었다.
        s_seen = self.visible_cells(cx, cy, bot.get('search_r', 1))
        already = s_seen <= bot.get('searched', set())
        _add('search', None,
             '수색: 반경 %d 안 보이는 범위의 숨은 함정·매복·보물을 드러낸다 (벽 뒤는 못 본다 — 한 턴 소모)%s'
             % (bot.get('search_r', 1),
                ' ※ 이 반경은 이미 샅샅이 살폈다 — 반복해도 새로 나올 게 없다' if already else ''))
        fresh_ways = [w for w in ways if not w['visited']]
        for w in fresh_ways:
            _add('explore', w['bearing'], '탐색: %s쪽 안 가본 길 — 거리 %d'
                 % (w['bearing'], w['dist']))
        if not fresh_ways:
            _add('explore', None, '탐색: 새 길을 찾아 나선다 (시야 밖 — 엔진에 맡긴다)')

        # A-3(D18): 목격 — 내 눈으로 본 동료의 피격/전사. 1회성: 이번 결정에 한 번 전달하고 비운다.
        # 자기 피격은 last 가 담당(중복 없음). 종 표기는 내 도감 기준(모르는 종=낯선 짐승 — D9 정합).
        wit = bot.get('witnessed') or []
        if wit:
            bot['witnessed'] = []
            wit = [{**w, 'name': names.get(w['char'], '동료'),
                    **({'by': UNKNOWN_BEAST} if known is not None
                       and 'monster:' + w['by'] not in known else {})}
                   for w in wit]

        rid_here = self._room_id_at(cx, cy)
        return {'pos': [cx, cy], 'hp': bot['hp'], 'maxhp': bot['maxhp'],
                'job': bot['job'], 'sex': bot['sex'],
                'str': bot['str'], 'dex': bot['dex'], 'inventory': bot['bag'],
                'depth': self.depth,
                **({'zone': {'id': ('r%d' % rid_here) if rid_here is not None else None,
                             'kind': '방' if rid_here is not None else '통로'}}
                   if led is not None else {}),        # 구역 어휘(D17-2) — 장부 스위치와 한 몸
                **({'turn': self.turn} if led is not None else {}),   # 장부 turn 스탬프의 '지금'
                                                       # — wire 가 'N턴 전'을 셈(D17-3). 장부와 한 몸
                **({'known': known_obs} if known_obs is not None else {}),   # 공간 장부(D17-1)
                **({'witnessed': wit} if wit else {}),   # 목격(A-3) — 있을 때만 실림(intent 선례)
                'last': bot.get('last'),      # 직전 행동/피격의 결과(D1 개정) — "봇은 자기 행동의
                                              #   결과를 관측할 수 있어야 한다". 자기 경험=시야-온리 무위반
                'order': ('explore' if str(bot.get('order') or '')[:1] == '@'
                          else bot.get('order')),        # 진행중 핑(자동보행). '@x,y' 생좌표는 봇에 노출X
                'ascii_view': rows,
                'sights': {'exit': exit_obj, 'features': feats, 'monsters': mons,
                           'ways': ways, 'bots': allies},
                'party': party,
                'options': options,   # 리모컨 — 엔진 열거 유효 행동(additive. BYO 계약: 번호+한마디)
                'legend': {'@': 'you', '#': 'wall', '.': 'floor',
                           '$': 'treasure', '>': 'stairs/exit', 'M': 'monster',
                           '^': 'trap', '=': 'chest', '~': 'fountain', ' ': 'unknown'}}

    # ── 탐색 프런티어 (explore = 미지로 트인 출입구) ─────────────
    def _frontier_cells(self, cx, cy, seen):
        """시야 내 '미지로 트인' 바닥칸 — 보이는 floor 중 직교 이웃에 미지(시야밖)가 있는 칸.
        = 지금 보이는 '더 갈 수 있는 가장자리'. 방이면 출입구, 통로면 진행 방향이 잡힌다."""
        out = []
        for (x, y) in seen:
            if (x, y) == (cx, cy) or self.grid[y][x] != FLOOR:
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
        typ = (action or {}).get('type', 'goto')
        tgt = (action or {}).get('target')
        if 'then' in (action or {}):              # 작정 접수 — 저작 검증(시야-온리)은 brains 소관,
            bot['plan'] = ([] if typ == 'follow'  # 동행(A-5)은 열린 결말 — then 뒤수 부적합(비움)
                           else [dict(s) for s in (action.get('then') or [])
                                 if isinstance(s, dict) and s.get('type')][:PLAN_MAX])
        if typ == 'attack':
            res = self._attack(bot, tgt, bots)
        elif typ == 'interact':
            res = self._interact(bot, tgt, bots)
        elif typ == 'search':
            res = self._search(bot)
        elif typ == 'explore':
            res = self._set_explore(bot, tgt, bots)   # 탐색(선택적 방위 tgt)
        elif typ == 'follow':
            res = self._set_follow(bot, tgt, bots)    # 동행(D18 A-5) — 곁 유지 지속 order
        else:
            res = self._set_order(bot, tgt, bots)     # goto(기본)
        self._note_last(bot, res)
        return res

    @staticmethod
    def _note_last(bot, res):
        """봇 자기 행동의 최신 결과 메모 — 원칙 "봇은 자기 행동의 결과를 관측할 수 있어야 한다".
        view()가 obs['last']로 노출. 자기 경험만 담으므로 시야-온리 무위반(세계 정보 아님)."""
        bot['last'] = {k: v for k, v in res.items() if k != 'char'}

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
        typ = str(step.get('type') or '')
        tgt = step.get('target')
        why = None
        if typ in ('search', 'explore'):
            pass
        elif typ == 'goto':
            e = ((bot.get('ledger') or {}).get('statics') or {}).get(str(tgt))
            if self._resolve_target(tgt, bots) is None and not (e and e.get('id')):
                why = '대상 소멸'                 # 작정의 goto 는 explore 폴백 안 탄다 —
                # (장부 귀환 목표(id 있는 것만 — trap@ 정보 항목 제외, 리뷰 픽스)는 통과:
                #  '없다'는 보지 않고는 모른다 — 가서 lost 로 확인(D17).
                #  여기서 '대상 소멸'을 알려주면 안 본 사실의 누설이다)
        elif typ == 'attack':                     #   대상이 사라졌으면 그건 새 정보다(재결정)
            res = self._resolve_target(tgt, bots)
            if res is None or res[0] != 'monster':
                why = '대상 소멸'
            elif abs(bot['x'] - res[1][0]) + abs(bot['y'] - res[1][1]) != 1:
                why = '인접 아님'
        elif typ == 'interact':
            res = self._resolve_target(tgt, bots)
            if res is None:
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

    def _resolve_target(self, target_id, bots=None):
        """핑 id → (kind, (x,y)). 'exit' / 'f<n>' 피처 / 'm<n>' 몹 / '@x,y' 셀(explore) / 'b<char>' 동료.
        엔진은 출구 위치를 늘 안다(해석은 무조건) — '보일 때만'은 obs/_valid_targets 층에서 막는다."""
        if target_id == 'exit':
            return ('exit', self.exit)
        s = str(target_id or '')
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
            return ('bot', (o['x'], o['y'])) if o else None
        return None

    @staticmethod
    def _beside_xy(x, y, tx, ty, kind):
        """'곁' 판정(D18 A-1): 동료(bot)=체비셰프≤1(대각 포함 — 식탁 모서리도 곁이다),
        그 외(몹 등)=직교 1 유지(몹 공격창이 직교 — 대각 도착이면 못 때리는 모순 방지)."""
        ddx, ddy = abs(x - tx), abs(y - ty)
        return max(ddx, ddy) <= 1 if kind == 'bot' else ddx + ddy == 1

    def _beside(self, bot, txy, kind):
        return self._beside_xy(bot['x'], bot['y'], txy[0], txy[1], kind)

    def _ally_jam(self, bot, tx, ty, path, bots):
        """사회적 대우회 감지(D18) — 방금 깐 path 가 '동료 때문에' 폭증했는지 판정.
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
        resolved = self._resolve_target(target_id, bots)
        ghost = False
        if resolved is None:
            e = ((bot.get('ledger') or {}).get('statics') or {}).get(str(target_id))
            if e and e.get('id'):       # 장부 귀환(D17)의 소비된 대상 — '기억의 좌표'로 간다.
                resolved = ('feature', (e['x'], e['y']))   # 갔더니 없으면 _order_done 이 lost 로
                ghost = True            #   정직 보고(+장부 교정) — 조용한 explore 강등 금지.
                                        #   id 없는 항목(trap@)은 핑 대상 아님(리뷰 픽스) → 아래 폴백
            else:
                return self._set_explore(bot, None, bots)    # 무효 핑 → 탐색(출구 떠먹이기 폐기)
        tx, ty = resolved[1]
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
            return self._set_explore(bot, None, bots)    # 도달불가 핑 → 탐색 폴백(무효핑과 대칭·재핑 livelock 차단)
        jam = self._ally_jam(bot, tx, ty, path, bots)
        if jam:                                          # 동료가 길목 점유 = 새 정보 — 멈춰 보고, 에이전트가 정한다
            bot['order'], bot['path'], bot['plan'] = None, [], []   # (비켜달라 말하든, 돌아가길 택하든)
            self._perceive(bot)                          # 멈춘 자리에서도 눈은 뜨고 — 거짓 매복 방지
            return {**base, 'result': 'blocked',
                    'allies': [{'char': o['char'], 'name': o.get('name') or o['job']}
                               for o in jam]}
        return {**base, 'result': 'pathed', 'len': len(path)}

    def _set_follow(self, bot, target_id, bots):
        """동행(D18 A-5) 개시: order='follow:b<char>' — 곁(체비셰프≤1)을 유지하며 따라 걷는
        지속 order(도착 개념 없음 — 열린 결말이라 작정(then)을 못 잇는다, act 가 비운다).
        곁이면 이 틱은 대기부터(following), 아니면 대상 현재 좌표로 경로. 매 틱 재경로는
        _step_order 의 A-2 블록이 공유 담당. 무효/도달불가 대상은 goto 와 대칭(explore 폴백).
        · 곁 대기 중 대상이 모퉁이 너머로 사라지면(잔여 path 없음) 즉시 lost — 정직 보고.
          재개는 에이전트의 몫('찾아가기' goto b<char> = 파티 감각 통로가 이미 있다).
        · 상호 동행(둘이 서로 follow)은 제자리 대기 고착 — 인터럽트(몹 출현·피격)와 max_turns 가
          종결을 보장하나, 관찰되면 재론 카드(사회층에서 '누가 이끄나'로 풀 문제)."""
        s = str(target_id or '')
        tid = s if s[:1] == 'b' else 'b%s' % s           # 'b2'/'2' 관용(자유서술 흔들림 흡수)
        resolved = self._resolve_target(tid, bots)
        if resolved is None or resolved[0] != 'bot':
            return self._set_explore(bot, None, bots)    # 무효 대상 → 탐색(무효 핑과 대칭)
        tx, ty = resolved[1]
        base = {'char': bot['char'], 'type': 'follow', 'target': tid}
        bot['follow_idle'] = None                        # 개시 = 제자리 카운터 리셋(FOLLOW_IDLE)
        if self._beside(bot, (tx, ty), 'bot'):
            bot['order'], bot['path'] = 'follow:' + tid, []
            return {**base, 'result': 'following'}
        path = self.path_to(bot['x'], bot['y'], tx, ty, bots)
        if not path:
            return self._set_explore(bot, None, bots)    # 도달불가 → 탐색 폴백(재핑 livelock 차단)
        jam = self._ally_jam(bot, tx, ty, path, bots)
        if jam:                                          # 동료發 대우회 — A-0과 동형 blocked
            bot['order'], bot['path'], bot['plan'] = None, [], []
            self._perceive(bot)
            return {**base, 'result': 'blocked',
                    'allies': [{'char': o['char'], 'name': o.get('name') or o['job']}
                               for o in jam]}
        bot['order'], bot['path'] = 'follow:' + tid, path
        return {**base, 'result': 'pathed', 'len': len(path)}

    def _set_explore(self, bot, direction, bots):
        """탐색 폴백(v3): 지금 보이는 '미지로 트인 출입구' 중 *도달 가능*한 걸 골라 자동보행.
        안 밟은(발자국 없는) 곳 우선 = 발자국 가지치기(왕복 방지). direction 주면 그 방위 우선.
        도달 가능한 미지 출입구가 없으면(탐색 끝) 그때만 출구로 best-effort 행군."""
        base = {'char': bot['char'], 'type': 'explore', 'target': direction or 'auto'}
        seen = self.visible_cells(bot['x'], bot['y'])
        fresh = []
        for w in self._ways(bot['x'], bot['y'], seen):
            if w['visited']:
                continue                              # 발자국 있는 길은 '새 발견'이 아니다(왕복/진동 차단)
            p = self.path_to(bot['x'], bot['y'], w['cell'][0], w['cell'][1], bots)
            if p:
                fresh.append((w, p))
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
            w, path = min(fresh, key=lambda rp: (len(rp[1]), rp[0]['cell']))
            tx, ty = w['cell']
            bot['order'], bot['path'] = '@%d,%d' % (tx, ty), path
            return {**base, 'result': 'pathed', 'len': len(path), 'bearing': w['bearing']}
        # 새로 트인 길이 (도달 가능하겐) 없다 → 발견할 게 없으니 출구로(떠먹임 아님). 막혔으면 가장 가까운 칸까지.
        ex, ey = self.exit
        path = self.path_to(bot['x'], bot['y'], ex, ey, bots, best_effort=True)
        if path:
            tx, ty = path[-1]
            bot['order'], bot['path'] = '@%d,%d' % (tx, ty), path
            return {**base, 'result': 'pathed', 'len': len(path), 'to_exit': True}
        bot['order'], bot['path'], bot['plan'] = None, [], []   # 발 디딜 곳 없음 — 작정 진행 불가(D16)
        return {**base, 'result': 'no_path'}

    def step_order(self, bot, bots):
        res = self._step_order(bot, bots)
        self._note_last(bot, res)             # 자동보행 결과도 봇의 '직전 결과'(obs.last)에 남는다
        return res

    def _step_order(self, bot, bots):
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
        follow = order_s.startswith('follow:')            # 동행(A-5): 'follow:b<char>' 지속 order
        tid = order_s[7:] if follow else bot.get('order')
        res0 = self._resolve_target(tid, bots)
        if follow and (res0 is None or res0[0] != 'bot'):
            bot['order'], bot['path'], bot['plan'] = None, [], []
            self._perceive(bot)               # 동행 대상 사망/하강 — 해석 실패 = lost(허탕 의미론)
            return {**base, 'result': 'lost'}
        if (res0 and res0[0] in ('monster', 'bot')
                and self._beside(bot, res0[1], res0[0])):
            if follow:                        # 곁 유지 — 이 틱은 대기, order 지속(도착 개념 없음)
                bot['path'] = []
                newly = self._perceive(bot)   # 대기 중에도 눈은 뜨고 — 새 것이 보이면 멈춰 묻는다
                if newly:
                    bot['order'], bot['path'], bot['plan'] = None, [], []
                    return {**base, 'result': 'encounter',
                            'monsters': [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state}
                                         for m in newly]}
                prev = bot.get('follow_idle')            # 고착 해약(FOLLOW_IDLE): 대상이 연속
                n = (prev[2] + 1 if prev and (prev[0], prev[1]) == res0[1]
                     else 1)                             #   제자리면 카운트, 움직이면 리셋
                if n >= FOLLOW_IDLE:
                    bot['order'], bot['follow_idle'] = None, None
                    return {**base, 'result': 'idle'}    # "계속 서 있네?" — 재결정으로 반환
                bot['follow_idle'] = (res0[1][0], res0[1][1], n)
                return {**base, 'result': 'following'}
            bot['order'], bot['path'] = None, []
            self._perceive(bot)               # 교전/합류 거리 도달 — 눈뜨고 재결정(거짓 매복 방지)
            return {**base, 'result': 'arrived'}
        if follow:
            bot['follow_idle'] = None         # 곁 아님 = 걷는 틱 — 제자리 카운터 리셋(FOLLOW_IDLE)
        # A-2(D18): 시야 내 실물 재경로 — 움직이는 목표(m/b)가 지금 눈에 보이는데 경로 종점이
        # 낡았으면(현 좌표 곁이 아님) 현재 좌표로 재계산. 매 틱이어도 결정론 BFS라 비용 미미.
        # 시야 밖=마지막 본 자리 스냅샷 유지(유령 추적 정당 — 07-05 판정). 경로 소진+시야 내도
        # 재경로 대상(아니면 FLEEING 추격이 한 틱 걸러 lost 나는 술래잡기). concealed 몹 좌표로는
        # 재조준 금지(시야-온리) — 사실상 order 대상 몹은 비은닉이지만 불변식은 코드로 지킨다.
        if res0 and res0[0] in ('monster', 'bot'):
            tx, ty = res0[1]
            mon = self.monster_at(tx, ty) if res0[0] == 'monster' else None
            if ((tx, ty) in self.visible_cells(bot['x'], bot['y'])
                    and not (mon and mon.concealed)):
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
        nx, ny = bot['path'][0]
        if not self.walkable(nx, ny, bots):           # 길이 막힘(몹·동료 끼어듦)
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
            res = self._resolve_target(tid, bots)              # 동료·은닉몹 점거 → 재경로 1회
                                                               #   (동행이면 tid='b<char>' — 원 대상)
            bot['path'] = self.path_to(bot['x'], bot['y'], res[1][0], res[1][1], bots) if res else []
            jam = (self._ally_jam(bot, res[1][0], res[1][1], bot['path'], bots)
                   if res else None)          # 재경로가 동료發 대우회면 여기서도 멈춰 묻는다(D18)
            if not bot['path'] or not self.walkable(*bot['path'][0], bots) or jam:
                bot['order'], bot['path'], bot['plan'] = None, [], []   # 막힘=새 정보 — 작정 파기
                self._perceive(bot)           # blocked 정지도 눈은 뜨고 — 거짓 매복 방지(위와 동일)
                out = {**base, 'result': 'blocked'}
                if jam:
                    out['allies'] = [{'char': o['char'], 'name': o.get('name') or o['job']}
                                     for o in jam]
                return out
            nx, ny = bot['path'][0]
        bot['path'].pop(0)
        enter = self._enter_cell(bot, nx, ny)         # 이동 + 보물/계단/함정 처리
        base.update(to=[nx, ny])
        if not bot['alive']:                          # 함정 즉사 — 시체는 지각하지 않는다(사후 인지굴림 금지:
            bot['order'], bot['path'], bot['plan'] = None, [], []   # 죽은 자의 주사위가 숨은 것을 드러내
                                                      #   산 자 경로를 바꿈. 작정도 죽음과 함께 소멸
            res = {**base, 'result': 'encounter', 'trap': enter['trap']}
            if enter.get('treasure'):                 # 죽으며 주운 보물도 진실(원장)에 남긴다 — 지금은 보물·함정
                res['treasure'] = True                #   동칸 배치가 없어 dormant이나, 배치 규칙 변경 즉시 발화
            return res
        if enter.get('at_exit'):                      # 계단 도착 — 하강/탈출은 interact(파티 조율)로
            self._perceive(bot)                       # 계단 위에서도 눈은 뜨고 있다(생략하면 뻔히 보이는
            bot['order'], bot['path'] = None, []      #   적의 공격이 '매복' 판정되는 거짓 they-ambush)
            return {**base, 'result': 'at_exit'}
        newly = self._perceive(bot)                   # 이동으로 새로 보인 몹 = aware_of 등록(처음 본 것만)
        found = self._passive_search(bot)             # 직업 인지 스윕(수동 search-on-move) — 숨은 것 발견
        if enter.get('trap') or newly or found:       # 인카운터 = *새 정보*만(에지) — 알던 몹 인접은
            bot['order'], bot['path'], bot['plan'] = None, [], []   # 정지 사유 아님(D1 개정: 물리면
                                                      #   그때 묻는다). 새 정보 = 남은 작정 파기(D16)
            res = {**base, 'result': 'encounter'}
            if enter.get('trap'):
                res['trap'] = enter['trap']
            if enter.get('treasure'):
                res['treasure'] = True                # 같은 걸음의 보물 획득도 진실에 남긴다(GM 서사용)
            if found:
                res['found'] = found                  # 인지로 드러난 것들("잠깐, 함정이야!")
            if newly:
                res['monsters'] = [{'id': 'm%d' % m.id, 'kind': m.kind, 'state': m.state}
                                   for m in newly]
            return res
        if enter.get('treasure'):
            if not bot['path']:                       # 목표 칸의 보물을 주움 = 이 order 의 완결(자기 소비).
                bot['order'] = None                   #   남겨두면 다음 틱 빈 자리에 lost/arrived 거짓 보고
            return {**base, 'result': 'treasure'}     # 보물은 줍고 계속 자동보행(안 멈춤)
        if not bot['path']:
            return self._order_done(bot, bots, base)
        return {**base, 'result': 'walking'}

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
        s = str(base.get('target') or '')
        if s.startswith('follow:'):                   # 동행(A-5): 경로 소진은 완결이 아니다 —
            res = self._resolve_target(s[7:], bots)
            if res and self._beside(bot, res[1], 'bot'):
                bot['path'] = []                      #   곁이면 지속(다음 틱 대기/재경로)
                return {**base, 'result': 'following'}
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

    def _enter_cell(self, bot, nx, ny):
        """한 칸 진입 = 좌표 갱신 + (보이는) 보물 줍기 + 계단 도착 + 숨은 함정 DEX 판정. 플래그 dict 반환.
        Stage 4: 출구 밟기 = 즉시탈출 아님(at_exit 만) — 하강/탈출은 interact + 파티 조율(_interact)로.
        Stage 3: 드러난 함정을 알고 밟으면 조심 보너스(CAREFUL_BONUS). 경보 함정은 층의 몹을 깨운다."""
        bot['x'], bot['y'] = nx, ny
        self.visited.add((nx, ny))
        out = {}
        tf = self.feature_at(nx, ny, 'treasure')
        if tf and not tf.concealed:               # 숨은 보물은 밟아도 모른다 — 인지로 드러나야 줍는다
            del self.features[tf.id]; bot['bag'] += 1; out['treasure'] = True
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

    def _passive_search(self, bot):
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
        for f in list(self.features.values()):
            if f.concealed and (f.x, f.y) in seen:
                if self.d20() + bot['dex'] >= (f.perception_gate or PASSIVE_DC):
                    f.concealed = False
                    found.append({'kind': f.type, 'name': f.name,
                                  'bearing': self._bearing(f.x - cx, f.y - cy)})
        for m in self.monsters:
            if m.alive and m.concealed and (m.x, m.y) in seen:
                if self.d20() + bot['dex'] >= LURK_DC:
                    m.concealed = False
                    bot['aware_of'].add(m.id)     # 정체를 봤다 → 매트릭스 봇쪽 비트 = we-ambush 가능
                    found.append({'kind': 'monster', 'name': m.kind, 'id': 'm%d' % m.id,
                                  'bearing': self._bearing(m.x - cx, m.y - cy)})
        return found

    def _zone_label(self, x, y):
        """구역 어휘(D17-2) — 좌표의 '주소'. 방=안정 id(생성 순서), 그 외 바닥=통로.
        방 타입(entrance/exit)은 안 싣는다 — '계단 방' 라벨은 안 본 계단의 존재를 누설(시야-온리)."""
        rid = self._room_id_at(x, y)
        return ('방 r%d' % rid) if rid is not None else '통로'

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
        newly = [m for m in self.monsters
                 if m.alive and not m.concealed and (m.x, m.y) in seen
                 and m.id not in bot['aware_of']]
        for m in newly:
            bot['aware_of'].add(m.id)
        return newly

    def _interact(self, bot, target_id, bots=None):
        """인접/현재 칸의 피처와 상호작용.
        출구(계단) = **파티 조율 하강**(Stage 4): 살아있는 파티 전원이 계단 반경 EXIT_GATHER 안에
          모여야 함께 내려간다(솔로탈출 방지). 안 모였으면 wait_allies — 동료를 부르거나 데리러 가라.
        상자/샘(Stage 3) = 도박: 상자 d20+DEX≥10 → 보물2 / 실패 → 독침 2피해. 샘 d20≥8 → 회복3 / 오염 1피해."""
        base = {'char': bot['char'], 'type': 'interact', 'target': target_id}
        res = self._resolve_target(target_id, bots)
        if not res:
            return {**base, 'result': 'no_target'}
        kind, (tx, ty) = res
        if abs(bot['x'] - tx) + abs(bot['y'] - ty) > 1:
            return {**base, 'result': 'too_far'}
        if kind == 'exit':
            others = [o for o in (bots or []) if o['alive'] and not o['won']
                      and o['char'] != bot['char']]
            far = [o for o in others if self._cheb(o['x'], o['y'], tx, ty) > EXIT_GATHER]
            if far:                              # 아직 안 모임 — 혼자 내려가지 않는다
                return {**base, 'result': 'wait_allies',
                        'missing': sorted(o['char'] for o in far)}
            group = [bot] + others
            for o in group:                      # 모인 전원이 함께 하강/탈출 — 이 층의 작정도 끝
                o['won'] = True
                o['order'], o['path'], o['plan'] = None, [], []
            return {**base, 'result': 'exit', 'party': sorted(o['char'] for o in group)}
        f = self.feature_at(tx, ty)
        if f and f.concealed:                    # 숨은 건 아직 '없는' 것 — 드러나야 만질 수 있다
            return {**base, 'result': 'nothing'}
        if f and f.type == 'treasure':
            del self.features[f.id]; bot['bag'] += 1
            return {**base, 'result': 'treasure'}
        if f and f.type == 'chest':              # 상자 도박 — 손재주(DEX)가 좋으면 안전하게 연다
            del self.features[f.id]
            r = self.d20(); total = r + bot['dex']
            if total >= 10:
                bot['bag'] += 2
                return {**base, 'result': 'chest_loot', 'roll': r, 'mod': bot['dex'],
                        'total': total, 'loot': 2}
            bot['hp'] -= 2
            out = {**base, 'result': 'chest_trap', 'roll': r, 'mod': bot['dex'],
                   'total': total, 'dmg': 2, 'hp': bot['hp']}
            if bot['hp'] <= 0:
                bot['alive'] = False; out['down'] = True
            return out
        if f and f.type == 'fountain':           # 샘 도박 — 대체로 이득(회복), 가끔 오염
            del self.features[f.id]
            r = self.d20()
            if r >= 8:
                heal = min(3, bot['maxhp'] - bot['hp'])
                bot['hp'] += heal
                return {**base, 'result': 'fountain_heal', 'roll': r, 'heal': heal, 'hp': bot['hp']}
            bot['hp'] -= 1
            out = {**base, 'result': 'fountain_harm', 'roll': r, 'dmg': 1, 'hp': bot['hp']}
            if bot['hp'] <= 0:
                bot['alive'] = False; out['down'] = True
            return out
        return {**base, 'result': 'nothing'}

    def _attack(self, bot, target_id=None, bots=None):
        """인접(직교) 몬스터를 친다. target 지정되면 *그 몹만*(비인접이면 too_far — 다른 적 몰래치기 금지),
        미지정이면 가장 약한 인접몹. d20+STR ≥ AC."""
        adj = [m for m in self.monsters
               if m.alive and not m.concealed              # 숨은(존재 모르는) 몹은 지목·폴백 대상 아님
               and abs(m.x - bot['x']) + abs(m.y - bot['y']) == 1]
        base = {'char': bot['char'], 'type': 'attack'}
        if target_id:
            res = self._resolve_target(target_id, bots)
            if not res or res[0] != 'monster':
                return {**base, 'result': 'no_target'}        # 지정 대상이 (살아있는) 몹이 아님
            mon = next((m for m in adj if (m.x, m.y) == res[1]), None)
            if mon is None:
                return {**base, 'result': 'too_far'}          # 지정 몹이 인접 아님 → 폴백 금지
        else:
            mon = min(adj, key=lambda m: m.hp) if adj else None   # 미지정 폴백: 가장 약한 인접(마무리)
        if not mon:
            return {**base, 'result': 'no_target'}
        # 인식 매트릭스(봇쪽): 몹이 날 못 봄(잠·배회) → 우리 기습(we-ambush-them).
        # 유리굴림(2d20 max) + 보너스 피해. 굴림 횟수는 분기로 고정(시드 스트림 결정론 유지).
        # waking(TIME_TO_WAKE_UP=1): 막 깬(발각 직후) 몹은 1턴 더 기습 가능 — 늦잠의 대가.
        # ⚠️ FLEEING 은 기습 아님 — 봇을 빤히 보며 도망치는 중(완전 인지). 등을 쳐도 정면 인지다.
        surprise = mon.state in ('SLEEPING', 'WANDERING') or mon.waking > 0
        r = max(self.d20(), self.d20()) if surprise else self.d20()
        total = r + bot['str']
        hit = (r == 20) or (total >= mon.ac)
        res = {**base, 'result': 'attack', 'target': mon.kind, 'target_id': 'm%d' % mon.id,
               'roll': r, 'mod': bot['str'], 'total': total, 'ac': mon.ac, 'hit': hit}
        if surprise:
            res['surprise'] = True
        if hit:
            dmg = bot['wdmg'] * (2 if r == 20 else 1) + (SURPRISE_DMG_BOT if surprise else 0)
            mon.hp -= dmg
            res.update(crit=(r == 20), dmg=dmg, monster_hp=max(0, mon.hp))
            if mon.hp <= 0:
                mon.alive = False; res['killed'] = True
                for o in (bots or []):    # 목격한 죽음은 장부에서 지운다(D17 교정 — 죽는 걸 본
                    if (o.get('alive') and not o.get('won')       # 몹이 '마지막 목격'으로 살아
                            and o.get('ledger') is not None       # 있는 척 잔존하는 유령 방지,
                            and (mon.x, mon.y) in self.visible_cells(o['x'], o['y'])):
                        o['ledger']['moving'].pop('m%d' % mon.id, None)   # 리뷰 픽스.
                        # 안 본 죽음은 안 지운다 — 지우면 그게 역누설이다
        if mon.alive:                            # 공격받음 = 완전 각성(justAlerted 우회)
            mon.waking = 0                       # 취약창 소비 — 안 끄면 기습→skip→waking 미소비 무한 스턴락
            if mon.state != 'FLEEING':           # 도주몹은 도주 지속(HUNTING 뒤집으면 flee 시계 리셋 교란)
                mon.state, mon.target = 'HUNTING', bot['char']
                mon.last_seen, mon.lost = (bot['x'], bot['y']), 0
            if surprise:
                mon.skip_turns = 1               # 기습라운드 = 다음 몹턴 반격 1회 스킵(대상 턴 스킵)
        return res

    def _search(self, bot):
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
        for f in list(self.features.values()):
            if f.concealed and (f.x, f.y) in seen:
                f.concealed = False
                found.append({'kind': f.type, 'name': f.name,
                              'bearing': self._bearing(f.x - cx, f.y - cy)})
        for m in self.monsters:
            if m.alive and m.concealed and (m.x, m.y) in seen:
                m.concealed = False
                bot['aware_of'].add(m.id)
                found.append({'kind': 'monster', 'name': m.kind, 'id': 'm%d' % m.id,
                              'bearing': self._bearing(m.x - cx, m.y - cy)})
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

    def _monster_attack(self, m, b, bots=()):
        """몹이 직교 인접 봇 b를 친다. 인식 매트릭스(몹쪽): 봇이 이 몹을 못 봤으면(aware_of 밖) =
        매복(they-ambush-us) → 유리굴림(2d20 max)+보너스 피해. 맞으면 봇은 그 몹을 즉시 인지(연속 매복 차단).
        ⚠️ 비은닉 몹은 봇이 시야로 늘 먼저 보므로(aware_of 등재) 실전 매복은 ~0이 정상 — '트인 곳에선 다 보인다'.
        진짜 they-ambush는 concealed(투명/매복몹·Stage3)가 생겨야 발화: concealed면 _perceive가 못 걸러
        aware_of에 영영 없음 → 이 분기가 자동으로 매복 처리. 즉 여기는 Stage3 솔기(지금은 대부분 dormant).
        A-3(D18): 명중/처치는 피격 칸이 시야 내인 다른 생존 봇의 witnessed 에 목격 사실로 쌓인다
        ("상처도 시야를 탄다" — 라이브 22틱 카야 전사 무목격 부검)."""
        ambush = m.id not in b.get('aware_of', set())
        ac = 10 + b['dex']
        r = max(self.d20(), self.d20()) if ambush else self.d20()
        total = r + m.atk
        hit = (r == 20) or (total >= ac)
        ev = {'type': 'monster_attack', 'id': 'm%d' % m.id, 'monster': m.kind,
              'target': b['char'],
              'roll': r, 'mod': m.atk, 'total': total, 'ac': ac, 'hit': hit}
        if ambush:
            ev['surprise'] = True
        if hit:
            dmg = m.dmg + (SURPRISE_DMG_MON if ambush else 0)
            b['hp'] -= dmg; ev['dmg'] = dmg; ev['hp'] = b['hp']
            # 피격 = 인터럽트(D1 대개정): 하던 일(자동보행 order)을 멈추고 다음 틱 에이전트에게 묻는다.
            # 세계가 봇을 세우는 유일한 '접촉' 채널 — 정지 규칙(레벨 트리거) 삭제의 반대급부.
            b['order'], b['path'], b['plan'] = None, [], []   # 남은 작정(D16)도 찢는다
            b['last'] = {'type': 'hurt', 'by': m.kind, 'by_id': 'm%d' % m.id,
                         'dmg': dmg, 'hp': b['hp'],
                         **({'surprise': True} if ambush else {})}
            if b['hp'] <= 0:
                b['alive'] = False; ev['down'] = True
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
        live = [o for o in bots if o['alive'] and not o['won']]
        if any((m.x, m.y) in self.visible_cells(o['x'], o['y'], MON_SIGHT) for o in live):
            events.append({'type': 'monster_move', 'id': 'm%d' % m.id, 'monster': m.kind,
                           'to': [m.x, m.y], 'fleeing': True})
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
                live = [o for o in bots if o['alive'] and not o['won']]
                if any((nx, ny) in self.visible_cells(o['x'], o['y'], MON_SIGHT) for o in live):
                    events.append({'type': 'monster_move', 'id': 'm%d' % m.id,
                                   'monster': m.kind, 'to': [nx, ny]})
                return                                # 이동 이벤트=봇 시야 안일 때만(도주/배회와 정책 통일)

    def monster_turn(self, bots):
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
            if (m.state == 'HUNTING' and not m.desperate
                    and m.hp * FLEE_FRAC <= m.maxhp):
                m.state, m.target, m.lost = 'FLEEING', None, 0    # 저HP → 도주(SPD FLEEING 린 채용)
                m.flee_turns = 0
                events.append({'type': 'monster_flee', 'id': 'm%d' % m.id, 'monster': m.kind})
            if m.state == 'FLEEING':                      # ②.5 도주: 가까운 봇에게서 멀어진다
                seen = self.visible_cells(m.x, m.y, MON_SIGHT)
                near = [b for b in live if (b['x'], b['y']) in seen]
                if not near:                              # 봇이 안 보이면 → 진정(배회 강등, HP는 안 돈다)
                    m.lost += 1
                    if m.lost >= LOSE_GRACE:
                        m.state, m.lost = 'WANDERING', 0
                    continue
                m.lost = 0                                # 봇이 보이면 '연속 상실' 리셋(HUNTING과 동일 스펙)
                m.flee_turns += 1
                if m.flee_turns >= FLEE_STAMINA:          # 탈진 → 필사 반전: 몰린 쥐가 고양이를 문다
                    b = min(near, key=lambda b: (self._cheb(m.x, m.y, b['x'], b['y']), b['char']))
                    m.state, m.desperate = 'HUNTING', True
                    m.target, m.last_seen, m.lost = b['char'], (b['x'], b['y']), 0
                    events.append({'type': 'monster_desperate', 'id': 'm%d' % m.id,
                                   'monster': m.kind})
                    continue                              # 전이 = 턴 소모(턴당 상태전이 1회)
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
                    if any((m.x, m.y) in self.visible_cells(b['x'], b['y'], MON_SIGHT) for b in live):
                        events.append({'type': 'monster_move', 'id': 'm%d' % m.id,
                                       'monster': m.kind, 'to': [m.x, m.y]})
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
                'monsters': [m.as_dict() for m in self.monsters]}


def new_ledger():
    """공간 장부(D17-1) 빈 원장 — 러너가 봇에 꽂아 켠다(bot['ledger']=new_ledger()).
    구조를 한 곳에서 소유(러너·시나리오·검증이 제각각 dict 를 빚으면 드리프트).
    statics=제자리 목격물(id 키) / moving=마지막 목격(몹·동료) / zones=방문 구역.
    장부=층의 기억 — 층 전이 재스폰 때 새로 꽂는다(도감=플레이어의 기억과 대비, D17)."""
    return {'statics': {}, 'moving': {}, 'zones': {}}


def spawn(dungeon, char, bots, min_exit_dist=8, cluster=4, sheet=None):
    """캐릭터 시트를 입혀 봇을 던전에 놓는다. sheet=None 이면 내장 HEROES[char]
    (하위호환 — 기존 verify 들의 spawn(d,'1',[]) 그대로 통과). 시트 외부화(party.json)는
    러너가 load_party 로 검증해 sheet= 로 넘긴다 — 시트=사용자 저작물의 원형(UGC 씨앗).
    파티는 함께 출발한다 — 첫 영웅은 출구에서 멀리(즉시 탈출 방지), 다음 영웅은
    그 곁(맨해튼 cluster 이내)에. 출구 바로 옆·맵 양끝 분리를 막는다.
    ⚠️ 'bots 리스트 = 파티' 가정을 여기서 더 심화하지 말 것(솔기 노트) — 살아있는 세상에선
    파티=에이전트 간 관계(가입/탈퇴)라 이 등식이 깨진다."""
    sheet = sheet or HEROES[char]
    ex, ey = dungeon.exit

    def free(x, y):
        return (dungeon.grid[y][x] == FLOOR
                and not dungeon.feature_at(x, y)                          # 피처(출구·보물·상자·샘…) 위 출발 금지
                and not any((t.x, t.y) == (x, y) for t in dungeon.traps)  # 숨은 함정 위 출발 금지
                and not dungeon.monster_at(x, y)
                and not any(b['x'] == x and b['y'] == y for b in bots))

    base = [(x, y) for y in range(dungeon.h) for x in range(dungeon.w) if free(x, y)]
    if bots:                       # 둘째+ 영웅: 먼저 온 동료 곁에 (함께 출발)
        a = bots[0]
        cands = [(x, y) for (x, y) in base
                 if 1 <= abs(x - a['x']) + abs(y - a['y']) <= cluster]
    else:                          # 첫 영웅: 출구에서 멀고 몬스터와 떨어진 곳
        cands = [(x, y) for (x, y) in base
                 if abs(x - ex) + abs(y - ey) >= min_exit_dist
                 and all(abs(x - m.x) + abs(y - m.y) >= 2 for m in dungeon.monsters)]
    if not cands:                  # 조건이 너무 빡빡하면 완화
        cands = base
    x, y = dungeon.rng.choice(cands)
    dungeon.visited.add((x, y))              # 시작 칸도 '가본 곳'
    return {'char': char, 'x': x, 'y': y,
            'hp': sheet['hp'], 'maxhp': sheet['hp'],
            'str': sheet['str'], 'dex': sheet['dex'], 'wdmg': sheet['wdmg'],
            'stealth': sheet['stealth'],    # 발각 DC 가산(은신) — 도적이 잘 안 들킴
            'search_r': sheet['search_r'],  # 인지 반경(Stage 3) — 도적 2 / 전사 1
            'job': sheet['job'], 'sex': sheet['sex'], 'persona': sheet['persona'],
            # ↓ 선택 4필드 = 프롬프트 전용(성격 연기·관계) — 엔진 판정은 절대 안 읽는다
            'name': sheet.get('name'), 'speech': sheet.get('speech'),
            'goal': sheet.get('goal'),
            'relationships': dict(sheet.get('relationships') or {}),
            'bag': 0, 'alive': True, 'won': False,
            'order': None, 'path': [],      # 핑 목표 id + 엔진이 BFS로 깐 자동보행 경로
            'aware_of': set(),              # 인지한 몹 id (newly 판정 + 매트릭스 봇쪽 비트)
            'known': None,                  # 도감(D9): 아는 종키 set — None=게이팅 끔(하위호환).
                                            #   러너가 발급기(bestiary)의 set 을 꽂는다(획득 즉시 obs 반영)
            'last': None,                   # 직전 행동/피격 결과 메모(D1 개정) — view 가 obs.last 로 노출
            'witnessed': [],                # 목격(D18 A-3): 시야 내 동료 피격/전사 사실 축적 —
                                            # view 가 1회성 노출·소거. 스냅샷 화이트리스트 밖(계약 불변)
            'follow_idle': None,            # 동행 고착 카운터(D18 FOLLOW_IDLE) — (x, y, n):
                                            # 곁 대기 중 대상 제자리 연속 관측. 화이트리스트 밖
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
    return {'char': b['char'], 'job': b['job'], 'sex': b['sex'],
            'x': b['x'], 'y': b['y'], 'hp': b['hp'], 'maxhp': b['maxhp'],
            'bag': b['bag'], 'alive': b['alive'], 'won': b['won'],
            'order': b.get('order'),
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
    ex = s.get('exit')
    if ex and ex.get('adj'):                          # 곁에 계단 → 하강 시도. 파티가 안 모였으면
        return {'type': 'interact', 'target': 'exit'}  # wait_allies = 그 자리서 기다린다(제자리 대기).
        # ('데리러 가기'는 일부러 안 한다 — 둘 다 데리러 나서면 서로 엇갈리는 왕복 진동(livelock).
        #  동료의 explore 폴백이 결국 계단으로 수렴하므로 기다림이 결정론적으로 안전. 데리러
        #  가는 드라마는 LLM 봇의 선택지(goto b<char>)로만 남긴다.)
    if obs['hp'] * 2 <= obs['maxhp']:                # 많이 다쳤다 → 샘이 보이면 회복 도박
        fts = [f for f in s['features'] if f['type'] == 'fountain']
        if fts:
            near = min(fts, key=lambda f: f['dist'])
            if near['adj']:
                return {'type': 'interact', 'target': near['id']}
            return {'type': 'goto', 'target': near['id']}
    treas = [f for f in s['features'] if f['type'] == 'treasure']
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
            print(f"  봇{b['char']}({b['job']}): pos=({b['x']},{b['y']}) 보물={b['bag']} {state}")
        alive_m = sum(1 for m in d.monsters if m.alive)
        print(f"  몬스터 생존 {alive_m}/{len(d.monsters)},  함정 발동 "
              f"{sum(1 for t in d.traps if t.sprung)}/{len(d.traps)}")
    return d, bots


if __name__ == '__main__':
    run()
