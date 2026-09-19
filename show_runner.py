#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
던전 관전 러너 — TRPG 루프 (L2 봇 두뇌 + L3 의논 + L4 GM 진행자)
─────────────────────────────────────────────
매 턴:
  ① 봇들 동시 사고 (의논=지난 턴 say 주입)  → 행동 선언(move/attack/search)
  ② 엔진이 행동을 d20으로 판정 (전투·함정 = 진실)
  ③ 몬스터 턴 (엔진: 인접 봇 공격 / 추적)
  ④ GM(Sonnet)이 이 턴 events를 '장면'으로 연출
상태를 state/ 파일로 흘려보내고 tmux 5분할이 본다:
  맵(+몬스터·함정·HP) / 봇1·봇2 사고 / 엔진 이벤트 / GM 연대기(독립 pane).

구조화 스트림(JSONL): 매 실행 state/stream.jsonl 에 틱별 의미 데이터를 흘린다(LLM 0콜).
  엔진 → 스트림 → [맵뷰어 | 기계 크로니클 | GM(옵션) | 웹뷰어] — GM 은 형제 소비자 중 하나로 강등.
  데이터 계약 = STREAM_FORMAT.md. 시드+decisions = 완전 리플레이.

환경변수: DUNGEON_W / DUNGEON_H / DUNGEON_SEED / DUNGEON_TURNS
          DUNGEON_GM(0이면 GM 끔) / DUNGEON_MONSTERS(기본2) / DUNGEON_TRAPS(기본3)
          DUNGEON_DEPTHS(스킬 원정 기본5 — 층수. 마지막 층 계단=탈출)
          DUNGEON_SKILLS / DUNGEON_TRPG_COMBAT / DUNGEON_RANDOM_SKILL(조합형 원정 기본1)
          DUNGEON_LURKERS(기본1 — 층당 매복몹 수) / DUNGEON_POTIONS(기본1 — 층당 회복 물약)
          DUNGEON_GEAR(기본3 — 층당 장비. 순환 배치: 단검·가죽 갑옷·장검·사슬 갑옷. 0=끔)
          DUNGEON_TOWN(기본0 — 마을 판(D29): 마을(0층)↔던전 왕복. 켜면 DEPTHS 기본 1 —
                       1층 아래 계단=관측 클리어. 재입장=같은 층(세계·기억 보존). 솔로와 동시 불가 v0)
          DUNGEON_STREAM_OBS(1이면 스트림 decisions 에 각 봇 obs 동봉 — 용량 커짐, 디버그/BYO용)
          DUNGEON_PARTY_FILE(기본 party.json — 캐릭터 시트. 검증 실패=내장 2인 폴백)
          DUNGEON_ACTION_MODE(기본 compose — 조합형. menu/free는 백업 비교용)
          DUNGEON_STEP_DELAY(기본 0.5초 — 관전 페이싱. 헤들리스 실측은 0)
          DUNGEON_STATE_DIR(기본 ./state — 상태·스트림 출력 폴더. 병렬 실측 시 판마다 분리)
          DUNGEON_GM_MODEL/DUNGEON_GM_TIMEOUT(GM 모델·타임아웃 — gm.py. GM 은 비동기 후채움이라
          느려도 루프는 안 멈춘다: 밀린 턴은 건너뛰고 최신 턴만 연출)
          DUNGEON_BESTIARY_FILE(도감 원장 경로 — 빈값(기본)=영속 끔: 판 안 학습만 하고 파일은
          안 남긴다. start.sh 가 라이브 판에만 bestiary.json 을 켠다 → verify/실험 자동 격리)
          DUNGEON_SCAN(기본1 — 스캐너(D19): 기하 구역/문/sighted 정지/트리 wire.
                       2026-07-15 미로 판정 채택으로 기본 1 승격)
          DUNGEON_LOOPS(기본1 — 월드 빌더(D20): 사슬(외길) 대신 주 고리+막다른 가지.
                       0=구식 사슬. 엔진 직생성 기본은 0 — 기존 verify 비트 동일)
          DUNGEON_SELFSTOP(기본1 — 자기 관찰 정지(D21): 재회("낯익은 곳") + 맴돎(걸음만 잇고
                       새 목격 0 + 되밟기). 정지+관찰 보고만, 판단은 두뇌 몫. 엔진 기본 0)
          DUNGEON_WAIT(기본1 — wait 동사(D25): 제자리 대기, 깨어남=사건(말 걸림·새 존재·피격·
                       지루함 상한 15틱). 숫자 인자 없음. 엔진 기본 0)
          DUNGEON_MOTION(기본1 — 이동중 표시(D27): 보이는 동료가 걷는 중이면 상태에 (이동중)
                       깃발 하나. 방향·목적지 비노출. 엔진 기본 0)
          DUNGEON_HAIL(기본1 — 말 걸림 정지(D24): 들리는 말=여섯 번째 정지 신호. 걷던 동료가
                       멈춰 다음 틱 결정권(강제 응답 아님). 같은 발화자 쿨다운 3턴. 엔진 기본 0)
          DUNGEON_DRY(기본1 — 무발견 신호: 마지막 새 목격 이후 25걸음 = 다음 결정 obs 한 줄
                       "한참을 걸었는데 새로 보이는 것이 없다". 도달 시점 1회만. 엔진 기본 0)
          DUNGEON_GRAVES(기본1 — 묘(D22): 쓰러진 자리에 '~의 묘' 피처 — 광학·조회·goto 앵커.
                       시체가 아니라 표지판(D4 불가침). 엔진 기본 0)
          DUNGEON_EVENTS(기본1 — 사건층(D22): 전달층=시야 내 사건 목격 주입(전투·함정·회복,
                       휘발=다음 결정 1회)+기억층=목격한 전사 fallen 지속 재제시. 엔진 기본 0)
          DUNGEON_LEDGER(기본1 — 공간 장부(D17): 본 것을 엔진이 캐릭터 명의로 기억,
          시야 밖 '돌아가기' 핑 허용. 0=끔. 층 전이 때 새 원장=층의 기억)
"""
import os
import sys
import glob
import json
import shutil                   # D79 폴백 때 옛 기록 대피(runs/)
import time
import queue
import random                   # D37(09-06) 외형 랜덤 — seed·char 로 따로 만든 Random(던전 난수 무접촉)
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dungeon_gm as G
import brains
import run_control
import snapshot                 # D79(09-16) 이어가기 — 판의 몸을 틱마다 얼려 둔다(마지막 기록에서 이어간다)
import gm
import stream
import run_summary                 # D58 판 결산 — 스트림 소비자(Tap 으로 모든 레코드를 흘려 세고, end.summary + events.log 표)
import bestiary
import sheetkit                 # D31(09-05) 배경 정제(자유 입력 격리) — 러너도 같은 자를 쓴다

STATE = os.environ.get("DUNGEON_STATE_DIR") or os.path.join(HERE, "state")
os.makedirs(STATE, exist_ok=True)

DUNGEON_W = int(os.environ.get("DUNGEON_W", "56"))
DUNGEON_H = int(os.environ.get("DUNGEON_H", "20"))
def _pick_seed(raw):
    """DUNGEON_SEED 해석 — 정수 또는 'random'(D31 09-05, 파트너 발제 "데모도 이제 랜덤 시드").
    'random' 이면 SystemRandom 으로 1~999999 를 뽑는다. 재현성은 그대로다: 뽑힌 값이
    run_meta.seed 에 기록되므로 "시드+결정 기록=재현"(README·D8)이 불변. 게이트·A/B 는
    환경변수로 정수를 명시하니 무영향(기본값 7 도 그대로 — live.bat 만 random 을 기본으로 건다)."""
    if str(raw).strip().lower() == "random":
        import random
        return random.SystemRandom().randrange(1, 10 ** 6)
    return int(raw)


# 09-11: 사용자 플레이 확인 후 기본 채택. 과거 메뉴형·직접 생성 엔진의 비교 조건은 유지한다.
SKILLS_ON = os.environ.get('DUNGEON_SKILLS', '1' if brains.COMPOSE else '0') == '1'
TRPG_COMBAT_ON = os.environ.get('DUNGEON_TRPG_COMBAT', '1' if brains.COMPOSE else '0') == '1'
RANDOM_SKILL_ON = os.environ.get('DUNGEON_RANDOM_SKILL', '1' if brains.COMPOSE else '0') == '1'
DUNGEON_SEED = _pick_seed(os.environ.get("DUNGEON_SEED", "7"))
MAX_TURNS = int(os.environ.get("DUNGEON_TURNS", "600" if SKILLS_ON else "250"))
PAUSE_LIMIT_SEC = max(0, int(os.environ.get("DUNGEON_PAUSE_LIMIT_SEC", "0") or 0))   # F1(09-18) 판단 정지를 기다려 주는 초 — 기본 0 = 끝없이(로컬). 공개 서버(server.py)가 값을 준다
N_MON =int(os.environ.get("DUNGEON_MONSTERS", "2"))
N_TRAP = int(os.environ.get("DUNGEON_TRAPS", "3"))
N_LURK = int(os.environ.get("DUNGEON_LURKERS", "1"))
N_POTION = int(os.environ.get("DUNGEON_POTIONS", "1"))   # 층당 회복 물약(07-17) — 러너 기본 1,
                                                          # 엔진 직생성 기본 0(기존 verify 비트 동일)
N_GEAR = int(os.environ.get("DUNGEON_GEAR", "3"))        # 층당 장비(07-30) — 러너 기본 3(순환:
                                                          # 단검·가죽 갑옷·장검 = 한 층 안에서 상위
                                                          # 무기 비교가 성립). 엔진 직생성 기본 0
TOWN_ON = os.environ.get("DUNGEON_TOWN", "0") == "1"     # 마을 판(D29) — 마을(0층)↔던전 왕복.
                                                          # 기본 0(기존 판 그대로) — 퀵스타터가 켠다
BOSS_ON = os.environ.get("DUNGEON_BOSS", "0") == "1"     # 보스층·워프게이트(D65, 09-13 파트너 "보스를 잡고 워프게이트를 타고 돌아가는
                                                          # 것까지 관찰"): 최심층(depth == DEPTHS)에 보스, 출구=봉인된 워프게이트, 보스가
                                                          # 죽으면 열리고 사용=마을(0층) 귀환=판 종료(outcome 'returned'). 러너 기본 0
                                                          # (기존 판·게이트 그대로) — 론처 옵션 '보스층·귀환'(화면 기본 켬)이 켠다
DEPTHS = int(os.environ.get("DUNGEON_DEPTHS", "1" if TOWN_ON else "5" if SKILLS_ON else "2"))
START_BOSS = os.environ.get("DUNGEON_START", "") == "boss"   # D67 프리셋(09-13 파트너 "보스전까지 가는 데 콜 수가 너무 많아서 보스방 앞에
if START_BOSS:                                                #   있는 프리셋이 하나 필요"): 최심층에서 시작·보스 켬·마을 없음·파티는 보스룸 앞 칸
    TOWN_ON, BOSS_ON = False, True                            #   (Dungeon.boss_front) 곁에 선다 — 관찰용. 론처 체크박스 '보스방 앞에서 시작'
START_DEPTH = DEPTHS if START_BOSS else 1                     #   첫 층 번호(몬스터 수·보스 여부도 그 층 기준)
                                                          # 마을 판 기본 1층까지(2층=아직 안 만듦 —
                                                          # 1층의 하강 계단=관측 클리어 조건, 파트너 확정)
GM_ON = os.environ.get("DUNGEON_GM", "1") != "0"
PARTY_FILE = os.environ.get("DUNGEON_PARTY_FILE", os.path.join(HERE, "party.json"))
BESTIARY_FILE = os.environ.get("DUNGEON_BESTIARY_FILE", "")  # 도감 원장(D9). 빈값=영속 끔(판 안 학습만)
                                                             #   — 격리 기본: verify/실험이 라이브 원장을 안 더럽힌다
LEDGER_ON = os.environ.get("DUNGEON_LEDGER", "1") != "0"     # 공간 장부(D17) — 러너 판 기본 켬
SCAN_ON = os.environ.get("DUNGEON_SCAN", "1") != "0"         # 스캐너(D19) — 기본 1 승격
                                                             #   (2026-07-15 미로 판정 채택 — 파트너 육안)
                                                             #   (채택 시 기본 1로 승격 — 사전등록 절차)
                                                             #   (spawn 기본은 None=끔 — 기존 게이트 무접촉)
LOOPS_ON = os.environ.get("DUNGEON_LOOPS", "1") != "0"       # 월드 빌더(D20) — 러너 기본 1(물약 선례),
                                                             #   엔진 직생성 기본 0(기존 verify 비트 동일).
                                                             #   사슬(외길) 대신 주 고리+막다른 가지
SELF_ON = os.environ.get("DUNGEON_SELFSTOP", "1") != "0"     # 자기 관찰 정지(D21 재회·맴돎) — 러너 기본 1,
                                                             #   엔진 직생성 기본 0(기존 verify 비트 동일).
                                                             #   scan 장부가 재료라 scan 판에서만 발화.
DRY_ON = os.environ.get("DUNGEON_DRY", "1") != "0"           # 무발견 신호(07-24) — 러너 기본 1, 엔진
                                                             #   기본 0. 마지막 새 목격 이후 25걸음
                                                             #   = 다음 결정 obs 한 줄(도달 1회만)
ALLY_DOING_ON = os.environ.get("DUNGEON_ALLY_DOING", "1") != "0"   # 동료 행동 표시(D27 개정 09-12) — 러너 기본 1,
                                                             #   엔진 기본 0. 보이는 동료 항목에 doing(고른 행동)
MOTION_ON = os.environ.get("DUNGEON_MOTION", "1") != "0"     # 이동중 표시(07-24 D27) — 러너 기본 1,
                                                             #   엔진 기본 0. 보이는 동료 상태에
                                                             #   (이동중) 깃발 하나(몸짓도 시야를 탄다)
SOCIAL_ON = os.environ.get("DUNGEON_SOCIAL", "0") != "0"      # 채널 분리(07-26) — 러너·엔진
                                                             #   둘 다 기본 0. 켜면 말 걸림이
                                                             #   작정을 안 부수고 사교 콜만 연다
                                                             #   (걸으면서 대답). 판정 전 실험층
ALLY_SIGHT_ON = os.environ.get("DUNGEON_ALLY_SIGHT", "1") != "0"   # 동료 시야 면제(07-26) —
                                                             #   **러너 기본 1 승격(D33 09-05, 파트너
                                                             #   확정 "절대시야 범위는 일반시야와 같이")**:
                                                             #   동료만 반경 안에서 벽·문 무관. 엔진 기본
                                                             #   0 유지(게이트 비트). 근거=07-26 A/B(lost
                                                             #   6→0·간격 2→6칸) + 09-05 [L] 판 부검(lost 9·
                                                             #   재회 대화 정체 — analyze_social.py).
SOLO_ON = os.environ.get("DUNGEON_SOLO", "0") != "0"          # 솔로 판(07-29 파트너 발제) — 러너·
                                                             #   엔진 둘 다 기본 0. 켜면 파티 전제가
                                                             #   빠진다: 흩어져 출발·서로 모름·혼자
                                                             #   하강. 마주친 뒤는 자유(엔진 무규정).
                                                             #   ⚠️ 별개의 실험 판이지 기본 게임의
                                                             #   개선이 아니다 — 승격 대상 아님.
PLAN_ON = os.environ.get("DUNGEON_PLAN", "0") == "1"         # 작정(D16 then) — D66(09-13 파트너 "계획이 이제 굳이 필요할까"): 러너 기본 0.
                                                              # 조합형 자동 접근이 '가서 한다'를 품어 작정의 주 용도가 사라졌고(오늘 판 집행 7~8%),
                                                              # 작정 집행 틱은 관측·들은 말을 안 읽는다. 켜려면 DUNGEON_PLAN=1(엔진 PLAN_MAX 그대로)
WAIT_ON = os.environ.get("DUNGEON_WAIT", "1") != "0"         # wait 동사(07-24 D25) — 러너 기본 1,
                                                             #   엔진 기본 0. 제자리 대기(사건 기반) —
                                                             #   셔틀의 고정점, 대기 중 LLM 0콜
HAIL_ON = os.environ.get("DUNGEON_HAIL", "1") != "0"         # 말 걸림 정지(07-24 D24) — 러너 기본 1,
                                                             #   엔진 기본 0. 들리는 말=여섯 번째
                                                             #   정지 신호(걷던 동료가 멈춰 돌아본다)
GRAVES_ON = os.environ.get("DUNGEON_GRAVES", "1") != "0"     # 묘(D22) — 러너 기본 1, 엔진 기본 0.
                                                             #   쓰러진 자리에 '~의 묘'(광학·조회·goto 앵커)
EVENTS_ON = os.environ.get("DUNGEON_EVENTS", "1") != "0"     # 사건층(D22) — 러너 기본 1, 엔진 기본 0.
                                                             #   전달층(시야 내 사건 목격, 휘발=다음 결정
                                                             #   1회)+기억층(fallen 지속 재제시, 휘발 0)
STATUS_ON = os.environ.get("DUNGEON_STATUS", "1") != "0"     # 상태 태그(D34, 09-06) — 러너 기본 1,
                                                             #   엔진 기본 0. 몹·함정의 특수=태그(출혈·
                                                             #   둔화·중독), 효과는 몸에만, 지우기=휴식
NOTICES_ON = os.environ.get("DUNGEON_NOTICES", "1") != "0"     # 건물 역할 부품(D61, 09-12 파트너 "신탁 소켓을 만들어 두자,
                                                             #   퀘스트 게시판 같은 것도") — 게시판(의뢰)·신탁(state/oracle.json)이
                                                             #   문턱 근처 캐릭터 관측에. 러너 기본 1(build_town 만), 정보만
ORACLE_FILE = "oracle.json"                                  # D61 신탁 소켓 — 론처 /api/oracle 이 쓰고 러너가 틱마다 읽는다
ORACLE_MAX = 200
TOWN_BUILDINGS_ON = os.environ.get("DUNGEON_TOWN_BUILDINGS", "1") != "0"   # 마을 관측(D60, 09-12 파트너 "마을에서는 관측 정보를
                                                             #   느슨하게") — 건물 = 문턱 칸의 피처(이름·방위·거리·goto)
                                                             #   + obs.town_zone(구역 이름). 러너 기본 1(build_town 만)
QUESTS_ON = os.environ.get("DUNGEON_QUESTS", "1") != "0"     # D69(09-14 파트너 "던전과 마을을 이어주는 연결점이 바로 길드") 길드 척추 —
                                                             #   게시판 의뢰 맡기(use q<n>)·엔진 완료 판정·워프 귀환 뒤 마을에서 이어
                                                             #   놀고 접수원 보고 = 원정의 끝(returned). 러너 기본 1(notices 필요), 엔진 기본 없음
TOWN_APART_ON = os.environ.get("DUNGEON_TOWN_APART", "1") != "0"   # D69 흩어진 출발 — 마을 시작 때 셋이 광장에 붙어 서는 대신 각자 건물
                                                             #   (길드·주점·신전) 문턱 곁에서 시작(파트너 "캐릭터마다 다양한 모습").
                                                             #   러너 기본 1(⚠️임시 가정 — 배정 순서=건물 id 순). 마을 판만
TOWN_HEAR = os.environ.get("DUNGEON_TOWN_HEAR", "zone")          # D70(09-14 파트너 "물리적으로만 멀게 해서 … 사실상 붙어있는거나 마찬가지"
                                                             #   → "구역 단위로 가자") 마을 사람 지각: 'zone'=동료·목소리·목격이 같은 구역
                                                             #   (또는 곁 1칸)에서만 — 장소(길·건물)는 다 안다 / 'all'=옛 전체 시야. 러너 기본 zone
NPC_HAIL_ON = os.environ.get("DUNGEON_NPC_HAIL", "1") != "0"     # D71(09-14 파트너 "npc 가 먼저 말을 걸게 하면 어때?") NPC 가 먼저 거는 인사 —
                                                             #   같은 구역·6칸 안에 오면 캐릭터당 NPC 당 한 번, 정의의 상황별 문장(0콜),
                                                             #   잡담 배달(정지 없음). 러너 기본 1(마을만)
NPC_HAIL_BRAIN_ON = os.environ.get("DUNGEON_NPC_HAIL_BRAIN", "0") == "1"   # D71 인사도 LLM 이 쓴다(인사당 1콜, 최대 캐릭터×NPC) — 기본 0(고정 문장)
NPC_HAIL_STOP_ON = os.environ.get("DUNGEON_NPC_HAIL_STOP", "1") != "0"   # D76(09-15 파트너 "npc가 캐릭터에게 말을 걸릴 때도 멈추게 하자") 인사를 받은
#   걷던·기다리던 캐릭터는 그 자리에 서서 그 틱에 결정한다(Dungeon.npc_hail_stop, 0콜) — 러너 기본 1(엔진은 호출해야만 선다)
TOWN_WALKERS_ON = os.environ.get("DUNGEON_TOWN_WALKERS", "1") != "0"   # D73(09-14 파트너 "마을에 돌아다니는 일반 캐릭터들 … 플레이어블 캐릭터의
                                                             #   반응을 확인") 마을 행인 — 정의(npc.walk)가 있는 NPC 가 제 구역을 걷는다(0콜,
                                                             #   말 걸면 대답·인사도 D69·D71 그대로). 러너 기본 1(마을 판만), build_town 직접 호출은 끔
TOWN_GUIDE_ON = os.environ.get("DUNGEON_TOWN_GUIDE", "1") != "0"   # D81(09-17 파트너 "마을 첫 관측에 튜토리얼 문단") 마을 안내 — 원정을 시작한 마을의
                                                             #   첫 관측에 한 번: 장소마다 정의의 특징 한 줄(새 문장 없음) + 동료가 지금 선 구역. 0콜.
                                                             #   러너 기본 1(마을 판만), build_town 직접 호출은 끔(행인 D73 과 같은 관례)
PARTYFORM_ON = os.environ.get("DUNGEON_PARTYFORM", "0") == "1" and TOWN_ON   # D84 조각 2(09-19 파트너 "마을/던전 이렇게 나누는 편이
#   좋지 않아?" → "마을은 마을의 시계로, 던전은 던전의 시계로 — 사람이 있는 세계는 다 흐른다") 파티 결성 판 — 파티 장부(G.new_parties)를
#   층마다 걸고, 계단을 쓴 무리만 옮긴다: 남은 사람의 세계는 그대로 계속 틱을 돈다(같은 층은 같은 세계 — 사람이 있으면 합류, 비었으면 복원).
#   본 스트림은 내 캐릭터(첫 번호 — 쓰러지면 살아 있는 가장 앞 번호)가 있는 세계만 지금과 같은 모양으로, 다른 세계의 기록은 옆 파일
#   (state/stream_side.jsonl). 러너 기본 0 = 세계 하나(옛 판과 비트까지 같다 — 같은 틱 몸통을 세계 하나로 도는 것). 마을 판만.
TOWN_SIGHT = "zone" if os.environ.get("DUNGEON_TOWN_SIGHT", "all") == "zone" else "all"   # D86(09-19 파트너 "구역 내에서는 시야를 전부 주고 이동도 거기에
#   맞게 하자") 마을의 시야 — 'zone' = 지금 선 구역만 보인다(건물·NPC·사람 전부) · 이동은 보이는 것 + 아는 장소(건물·입구는 장부에 미리)로 핑하고
#   걷다가 새 구역에 들어서면 멈춰 다시 본다. 'all'(러너 기본) = 옛 판 그대로(마을 전체가 보이고 핑 한 번에 어디든). layout 마을만.
STRANGERS_ON = os.environ.get("DUNGEON_STRANGERS", "0") == "1" and PARTYFORM_ON   # 파티 결성 판에서만 — 끈 판은 셋이 자동으로 한 일행이라 '모르는 일행'이 된다 · D85(09-19 파트너 "낯선 사람이 맞아 … 말을 걸고 상호작용을 하면서 해당 캐릭터에
#   대한 지식이 생기고 나면 거기에 대해 따로 저장할수 있게 하자 로어북처럼") 인물 기록 — 켜면 몸마다 bot['people'](내가 쓴 사람 기록)을 건다:
#   기록이 없는 사람은 '낯선 사람'(+겉모습), 이름·직업은 자동으로 주어지지 않는다. 시트에 작가가 쓴 관계 문장은 미리 채워진 기록이 된다.
#   러너 기본 0 = 옛 판과 비트까지 같다(엔진·프롬프트는 bot['people'] 이 None 이면 옛 길). 파티 결성(D84)과 별개 스위치.
NPC_BRAIN_ON = os.environ.get("DUNGEON_NPC_BRAIN", "1") != "0"   # D69 마을 NPC 두뇌 — 캐릭터가 말을 걸면 NPC 한마디를 LLM 이 쓴다(1콜,
                                                             #   먼저 말하지 않음·잡담 배달·판정은 엔진·고정 대사=폴백). 러너 기본 1,
                                                             #   더미 두뇌(dummy) 판에선 저절로 꺼진다(콜 0 유지)
REST_ON = os.environ.get("DUNGEON_REST", "1") != "0"         # 휴식(D35, 09-06) — 러너 기본 1, 엔진
                                                             #   기본 0. 회복이 붙은 wait: 틱마다 HP,
                                                             #   완료 시 상태 태그 소거. 사건이 깨운다
RELATIONS_ON = os.environ.get("DUNGEON_RELATIONS", "1") != "0"   # 관계 장부(D36, 09-06) — 러너 기본 1,
                                                             #   엔진 기본 0. 뼈 5종+문턱 초대, 살은
                                                             #   결정 응답 relation_line(엔진 불가침)
EXPLORE_DIRS_ON = os.environ.get("DUNGEON_EXPLORE_DIRS", "1") != "0"   # 방향 탐색 열거(D19 개정 4, 09-07) — 러너
                                                             #   기본 1, 엔진 기본 0. scan 판 메뉴에 트인 방위마다
                                                             #   '탐색' 한 줄(갈 방향의 선택은 에이전트가)
TRAIL_ON = os.environ.get("DUNGEON_TRAIL", "1") != "0"       # 자기 행동 궤적(D38, 09-06) — 러너 기본 1,
                                                             #   엔진 기본 0. 마지막 결정 이후 일어난 일을
                                                             #   순서대로 다음 결정에(작정 집행 틱의 공백 보전)
OBJTAGS_ON = os.environ.get("DUNGEON_OBJTAGS", "1") != "0"   # 오브젝트 태그(D39, 09-06) — 러너 기본 1,
                                                             #   엔진 기본 0. 상인·샘과의 상호작용 횟수·마지막
                                                             #   사실을 시야 줄·라벨 접미로("말 걸어 봄 ×2")
SAYTO_ON = os.environ.get("DUNGEON_SAYTO", "1") != "0"       # 지목(D41, 09-06) — 러너 기본 1. 말 걸림 정지·대화
                                                             #   뼈는 `to` 로 지목된 사람만(대상 없는 말=혼잣말:
                                                             #   들리지만 아무도 안 선다). off=구판(들리면 전원 정지)
SAYKIND_ON = os.environ.get("DUNGEON_SAYKIND", "1") != "0"   # 말의 종류(D47, 09-08 파트너 "제안은 캐릭터를 멈추게 하고
                                                             #   명확한 요구를 한다 — 일반 대화는 굳이 멈출 필요가 없다")
                                                             #   — 러너 기본 1. 응답 say_kind ∈ 잡담(기본)|제안. 세우는 건
                                                             #   제안뿐: to=번호 → 그 사람 / 대상 없음·all → 회의(시야 안
                                                             #   전원). 잡담은 들리기만(지목·방송 잡담은 talk 뼈). 같은
                                                             #   사람의 재제안은 상대가 답하기 전엔 안 세운다(open 장부).
                                                             #   off=D41 판(지목이면 종류 무관 정지). SAYTO 가 꺼지면 무효.
PENDING_ON = os.environ.get("DUNGEON_PENDING", "1") != "0"   # 들은 말 보관(D47 배관 — 437987d 재사용) — 러너 기본 1.
                                                             #   걷는 중 들린(안 세운) 말을 그 봇의 다음 결정까지 보관해
                                                             #   함께 읽힌다. 옛 판: 결정 없는 틱의 말은 증발.
PENDING_MAX = 6                                              #   보관 상한(오래된 것부터 바랜다 — D43 DIALOGUE_MAX 와 같은 자)
FLOOR_ON = os.environ.get("DUNGEON_FLOOR", "1") != "0"       # 층 집계·결산(D40 ②, 09-06) — 러너 기본 1,
                                                             #   엔진 기본 0. "이 층에서 지금까지" 꼬리표 ×N +
                                                             #   층 전이 때 얼려 "지난 층"(캐릭터 한 줄 피기백)
GIVE_ON = os.environ.get("DUNGEON_GIVE", "1") != "0"         # 건네기(D47 ②, 09-09 파트너 "건네기를 만들려면 아이템 거래를
                                                             #   넣어야 해") — 러너 기본 1, 엔진 기본 0. 곁의 동료에게 물약·
                                                             #   무기·방어구를 넘기는 즉시 동사(메뉴 열거). 승낙=이 줄을 고르는 것
BOND_ON = os.environ.get("DUNGEON_BOND", "1") != "0"         # 친목(D47 ②, 09-09 파트너 "['대화' '친목' '머리를 쓰다듬기']") —
                                                             #   러너 기본 1, 엔진 기본 0. 곁의 동료에게 하는 몸짓(응답 form
                                                             #   자유 문구) — 물리 없음, 기록·목격·뼈. 반응은 상대의 다음 결정
# 지식 본문(옛 lore.json)은 엔티티 저장소(entities/, D50)의 knowledge.deep — G.ENT.lore()
STEP_DELAY = float(os.environ.get("DUNGEON_STEP_DELAY", "0.5"))   # 한 수 적용 후 맵이 보이게(헤들리스=0)
RESUME_PATH = os.environ.get("DUNGEON_RESUME", "")   # D79(09-16) 이어가기 — 스냅샷(state/snapshot.pkl) 경로. 있으면 그 몸에서 같은 기록 파일에 이어 쓴다
RUNS_DIR = os.environ.get("DUNGEON_RUNS_DIR", "")    #   되살리기 실패 폴백 때 옛 기록을 대피시킬 폴더(론처가 준다 — 없으면 STATE 옆 runs/)
RESUME_NOTICE = "원정을 이어간다 — 지난번에는 여기(%s, t%d)서 멈췄다. 몸·짐·기억은 그대로다.%s"   # D79 첫 관측 한 번(floor_notice 자리) ⚠️문구 임시
RESUME_NOTICE_PAGE = " 멈추기 전에 쓴 수첩 한 장이 '기억해두기로 한 것'에 있다."                    # ⚠️문구 임시

# 캐릭터 시트 계약(party.json): 필수 9필드(수치형/문자형) + 선택 4필드(프롬프트 전용)
SHEET_REQ = {"job": str, "sex": str, "hp": int, "str": int, "dex": int,
             "wdmg": int, "stealth": int, "search_r": int, "persona": str}
SHEET_OPT = ("name", "speech", "goal")     # + relationships(dict) 별도 취급
# 선택 **수치** 필드: 없으면 기본값, 있으면 범위 검증. 위 SHEET_OPT(프롬프트 전용)와 달리
# **엔진 판정이 읽는다** — 그래서 상한을 둔다(시트=UGC, 사거리 999 같은 값이 오면 안 된다).
SHEET_OPT_NUM = {"atk_range": (1, 1, 3)}   # 공격 사거리(맨해튼): 기본 1(근접) · 궁수 2
FREETEXT_MAX = 300                          # 말투·목표·관계 등 기존 필드. 성격·배경은 sheetkit의 별도 상한.


def alpha_metadata():
    if not any((SKILLS_ON, TRPG_COMBAT_ON, RANDOM_SKILL_ON)):
        return {}
    # alpha 필드는 이전 뷰어·분석기 호환을 위해 보존하고 채택된 규칙을 별도로 표시한다.
    return {'ruleset': 'skills-v1', 'alpha': {'version': G.SK.schema.VERSION, 'skills': SKILLS_ON,
                      'trpg_combat': TRPG_COMBAT_ON, 'random_skill': RANDOM_SKILL_ON,
                      'random_skill_effective': SKILLS_ON and RANDOM_SKILL_ON,
                      'acquisition_depth': 3, 'random_budget': 5,
                      'cooldown_clock': 'completed_actions',
                      'presets': G.SK.schema.PRESETS if SKILLS_ON else {}}}


def load_party(path):
    """party.json → {char: sheet}. 시트=사용자 저작물의 원형이라 여기서 깐깐히 거른다(UGC 검증 씨앗).
    어떤 실패든 내장 2인(HEROES)으로 폴백 + 경고 1줄 — 시트가 이상해도 게임은 죽지 않는다.
    '_' 로 시작하는 최상위 키는 메타(설명문)로 보고 무시한다."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("최상위가 객체가 아님")
        sheets = {}
        for char, s in raw.items():
            char = str(char)
            if char.startswith("_"):
                continue
            if not (len(char) == 1 and char.isdigit() and char != "0"):
                raise ValueError("char 키는 '1'~'9' 한 글자여야 함: %r" % char)
            if not isinstance(s, dict):
                raise ValueError("봇%s 시트가 객체가 아님" % char)
            out = {}
            for k, typ in SHEET_REQ.items():
                if k not in s:
                    raise ValueError("봇%s 필수 필드 누락: %s" % (char, k))
                v = s[k]
                if typ is int:
                    if not isinstance(v, int) or isinstance(v, bool):
                        raise ValueError("봇%s %s 는 정수여야 함: %r" % (char, k, v))
                else:
                    if not isinstance(v, str) or not v.strip():
                        raise ValueError("봇%s %s 는 비지 않은 문자열이어야 함: %r" % (char, k, v))
                    v = v[:sheetkit.PERSONA_TOTAL_MAX if k == 'persona' else FREETEXT_MAX]
                out[k] = v
            if out["hp"] < 1:
                raise ValueError("봇%s hp 는 1 이상" % char)
            for k in SHEET_OPT:
                if k in s and s[k] is not None:
                    if not isinstance(s[k], str):
                        raise ValueError("봇%s %s 는 문자열이어야 함" % (char, k))
                    out[k] = s[k][:FREETEXT_MAX]
            for k, (dflt, lo, hi) in SHEET_OPT_NUM.items():   # 선택 수치 — 없으면 기본값
                v = s.get(k, dflt)
                if not isinstance(v, int) or isinstance(v, bool) or not (lo <= v <= hi):
                    raise ValueError("봇%s %s 는 %d~%d 정수여야 함: %r" % (char, k, lo, hi, v))
                out[k] = v
            bg = s.get("background")            # D31(09-05) 자유 입력 2호 — 시트 UGC 인젝션 관문:
            if bg is not None:                  #   막지 않고 격리한다(sheetkit.sanitize_background —
                if not isinstance(bg, str):     #   개행·마크다운 표식 제거·공통 상한). 빈 결과=필드 없음
                    raise ValueError("봇%s background 는 문자열이어야 함" % char)
                bg = sheetkit.sanitize_background(bg, sheetkit.BACKGROUND_MAX)
                if bg:
                    out["background"] = bg
            tr = s.get("traits")                # 성격 키워드 원본(부검용 — 프롬프트엔 문장이 대신 나간다)
            if tr is not None:
                if (not isinstance(tr, list) or len(tr) > 5
                        or not all(isinstance(t, str) and 0 < len(t) <= 20 for t in tr)):
                    raise ValueError("봇%s traits 는 20자 이내 문자열 최대 5개 리스트" % char)
                out["traits"] = list(tr)
            rel = s.get("relationships")
            if rel is not None:
                if not isinstance(rel, dict):
                    raise ValueError("봇%s relationships 는 객체여야 함" % char)
                out["relationships"] = {str(o): str(t)[:FREETEXT_MAX] for o, t in rel.items()}
            lk = s.get("look")                  # D37(09-06) 외형 — 뷰어 전용(엔진·프롬프트 무접촉).
            if lk is not None:                  #   미등재 파츠·hex 아님 = ValueError = 폴백 경로 그대로
                out["look"] = sheetkit.sanitize_look(lk)
            pid = s.get("id")                   # D78(09-16) 저장 캐릭터 id(론처 프리셋) — 판 기록·캠페인·도감 원장의 키.
            if pid is not None:                 #   없으면 1회용 캐릭터(기록이 안 남는다). 엔진·프롬프트 무접촉.
                if not (isinstance(pid, str) and 0 < len(pid) <= 64 and all(ch.isalnum() or ch in "-_" for ch in pid)):
                    raise ValueError("봇%s id 는 영숫자·-_ 64자 이내여야 함: %r" % (char, pid))
                out["id"] = pid
            if SKILLS_ON and 'skills' in s:
                ids = s['skills']
                if (not isinstance(ids, list) or len(ids) > 3 or
                        not all(isinstance(sid, str) and sid in G.SK.schema.PRESETS for sid in ids)
                        or len(set(ids)) != len(ids)):
                    raise ValueError('skills는 등록된 스킬 ID 최대 3개 목록이어야 함')
                out['skills'] = list(ids)
            sheets[char] = out
        if not sheets:
            raise ValueError("시트가 하나도 없음")
        seen_names = {}                     # name = 도감 원장(캐릭터 재산)의 키 — 여기서 거른다(리뷰 픽스)
        for char in sorted(sheets):
            nm = sheets[char].get("name")
            if nm is None:
                continue
            if nm.lstrip().startswith("_"):
                raise ValueError("봇%s name 은 '_'로 시작 불가(도감 원장 메타 키와 충돌 — 지식이 소실된다): %r"
                                 % (char, nm))
            if nm in seen_names:
                raise ValueError("name 중복(봇%s·봇%s = %r) — 도감 원장(캐릭터별 재산)이 섞인다"
                                 % (seen_names[nm], char, nm))
            seen_names[nm] = char
        if len(sheets) > 5:
            print("[경고] 파티 %d인 — 5인 초과는 관전 화면이 좁다(그대로 진행)"
                  % len(sheets), file=sys.stderr)
        return sheets
    except Exception as e:
        print("[경고] 파티 파일(%s) 로드 실패: %s — 내장 2인(전사·도적)으로 폴백"
              % (path, e), file=sys.stderr)
        return {c: dict(G.HEROES[c]) for c in ("1", "2")}


def write_map(d, bots, turn):
    lines = [f"  던전 지하 {d.depth}/{DEPTHS}층  (turn {turn})", ""]
    lines.append(d.render(bots))
    lines.append("")
    for b in bots:
        if b["won"]:
            state = "하강 v" if d.depth < DEPTHS else "탈출 O"
        elif not b["alive"]:
            state = "쓰러짐 X"
        else:
            state = "HP %d/%d" % (b["hp"], b["maxhp"])
        order = b.get("order")
        ping = ("탐색" if str(order or "")[:1] == "@" else order) or "-"
        nm = ("%s·" % b["name"]) if b.get("name") else ""
        w, a = b.get("weapon"), b.get("armor")            # 장비(07-30) — 관전 한 눈 확인
        gear = ("".join(filter(None, (w and ")%s" % w["name"], a and "[%s" % a["name"])))
                or "-")
        lines.append("  봇%s %s%s(%s)  pos=(%2d,%2d)  보물 %d  물약 %d  장비:%s  핑:%s  %s"
                     % (b["char"], nm, b["job"], b["sex"], b["x"], b["y"], b["bag"],
                        b.get("potions", 0), gear, ping, state))
    alive_m = sum(1 for m in d.monsters if m.alive)
    lines.append("")
    lines.append("  몬스터 %d/%d    범례: # 벽  . 바닥  + 문  $ 보물  > 계단  < 위계단  & NPC  M 몬스터  ^ 함정  = 상자  ~ 샘  ! 물약  ) 무기  [ 방어구  %s 영웅"
                 % (alive_m, len(d.monsters), ",".join(sorted(b["char"] for b in bots))))
    lines.append("               (관전자 전용: m 숨은 적  * 숨은 보물 — 봇들은 모른다)")
    with open(os.path.join(STATE, "gm_map.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def append(name, line):
    with open(os.path.join(STATE, name), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def event(line):
    print(line, flush=True)
    append("events.log", line)


def read_oracle():
    """D61 신탁 소켓 — 론처가 STATE/oracle.json 에 둔 사용자 한 줄 {id, text, at}. 없거나 깨지면 None.
    텍스트는 시트 배경과 같은 격리(sheetkit.sanitize_freetext: 개행·마크다운 표식 제거, ORACLE_MAX 자) — 사용자 글이 프롬프트로 들어간다."""
    try:
        with open(os.path.join(STATE, ORACLE_FILE), encoding="utf-8") as f:
            o = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(o, dict) or not o.get("id"):
        return None
    text = sheetkit.sanitize_freetext(o.get("text"), ORACLE_MAX)
    return {"id": str(o["id"]), "text": text, "turn": o.get("turn")} if text else None


def quest_sfx(res):
    """D69 결과에 실린 의뢰 진행 → ' 📜 의뢰 「…」 2/3'(세계가 센 숫자). 없으면 빈 문자열."""
    bits = ["의뢰 「%s」 %s" % (q.get("title", "?"), "완수!" if q.get("done") else "%d/%d" % (int(q.get("n") or 0), int(q.get("need") or 1)))
            for q in (res or {}).get("quest") or []]
    return (" \U0001f4dc " + " · ".join(bits)) if bits else ""


def act_summary(res):
    """봇 한 행동/자동보행 결과를 한 줄 요약 — 로그/이벤트 공용."""
    t = res["type"]
    if res.get('skill_id'):
        return G.SK.summary(res)
    if res.get("result") == "approaching":
        return "%s %s — 실행 거리까지 접근 시작 (%d걸음)" % (t, res.get("target", "?"), res.get("len", 0))
    if res.get("result") == "no_path" and res.get("parent_action_id"):
        return "%s %s — 접근할 길이 없다" % (t, res.get("target", "?"))
    if res.get('result') == 'no_effect':
        return '%s %s — 변화 없음 (%s)' % (t, res.get('target', '?'), res.get('reason_code', 'no_effect'))
    if t == 'use' and res.get('result') == 'healed':
        return '%s에게 물약 사용 — HP +%d (HP %d)' % (res.get('target', '?'), res.get('heal', 0), res.get('hp', 0))
    if res.get('result') == 'drink_boon':                  # D74(09-15) 축복의 물약 — drink(item=boon)·use(self, i4) 공용
        return '축복의 물약을 들이켰다 — %s +1 (지금 %d), 남은 %d병' % (G.STAT_KR.get(res.get('stat'), '?'), res.get('value', 0), res.get('boons', 0))
    if res.get('result') == 'no_boon':
        return '축복의 물약을 마시려 했지만 — 없다'
    if t == 'use' and res.get('effect_type'):
        return act_summary({**res, 'type': res['effect_type']})
    if t == 'use':
        return '%s 사용 실패 — %s' % (res.get('target', '?'), res.get('result', '?'))
    if t == "goto":
        if res["result"] == "blocked" and res.get("allies"):   # D18: 동료發 대우회 — 멈춰 보고
            return "%s — 동료(%s)가 길목에 서 있어 크게 돌아야 함, 멈춰 보고" % (
                res.get("target", "?"), ", ".join(a["name"] for a in res["allies"]))
        tag = {"pathed": "핑 -> 자동보행 개시", "arrived": "이미 곁에", "no_path": "길이 없다",
               "already_beside": "이미 곁에 있고 멈춰 있음 — 갈 곳 없음"}   # D48 개정 goto<아군>
        return "%s %s" % (res.get("target", "?"), tag.get(res["result"], res["result"]))
    if t == "follow":                                          # 동행(D18 A-5)
        r = res["result"]
        allies = ", ".join(a["name"] for a in res.get("allies", []))
        tag = {"pathed": "동행 개시 -> %s 곁으로" % res.get("target", "?"),
               "following": "동행 개시 — 이미 곁, 따라 걷는다 (%s)" % res.get("target", "?"),
               "blocked": "동행 — 동료(%s)가 길목을 막아 멈춰 보고" % allies}
        return tag.get(r, "동행(%s)" % r)
    if t == "wait":                                            # 제자리 대기(D25)
        return ("기다린다 — 이 자리에서(사건이 깨울 때까지)"
                if res["result"] == "waiting" else "대기(%s)" % res["result"])
    if t == "rest":                                            # 휴식(D35)
        return ("쉰다 — 이 자리에서(다 낫거나 사건이 깨울 때까지)"
                if res["result"] == "resting" else "휴식(%s)" % res["result"])
    if t == "explore":
        r = res["result"]
        if r == "pathed":
            if res.get("to_exit"):
                return ("탐색 — 더 볼 곳 없음, 기억의 계단으로 향함" if res.get("remembered")
                        else "탐색 — 더 볼 곳 없음, 출구로 향함")
            if res.get("door"):                                # D19 개정: 기억 속 안 가 본 문
                return "탐색 — 더 볼 곳 없음, 기억 속 문 %s 너머로" % res["door"]
            if res.get("frontier"):                            # D19 개정: 기억 속 안 본 가장자리
                return "탐색 — 더 볼 곳 없음, 기억 속 안 본 가장자리로"
            return "탐색 -> %s 방향 자동보행" % res.get("bearing", "?")
        if r == "no_path":
            return ("탐색 — 갈 곳 없음(새 길·기억의 계단·안 가 본 문 전부 없음)" if res.get("exhausted")
                    else "탐색 — 갈 곳 없음")
        return "탐색(%s)" % r
    if t == "walk":
        r = res["result"]
        if res.get("bleed", {}).get("down"):
            return "출혈로 쓰러졌다!"                     # 상태 태그(D34) — 걷다 피를 다 흘림
        if r == "walking" and res.get("slowed"):
            return "둔화 — 이 틱은 못 걷는다"
        if r == "waiting":
            return "대기 중"
        if r == "resting":
            return "휴식 중 (HP%d)" % res.get("hp", 0)
        if r == "rested":
            return "휴식 끝 — HP +%d%s" % (res.get("healed", 0),
                                          (", 나음: " + "·".join(res["cleared"])) if res.get("cleared") else "")
        if r == "rest_met":
            return "휴식 중단 — 동료(%s) 시야 진입" % ", ".join(res.get("allies", []))
        if r == "wait_met":
            return "대기 끝 — 동료(%s) 시야 진입" % ", ".join(res.get("allies", []))
        if r == "wait_bored":
            return "대기 끝 — 한참을 기다려도 아무도 오지 않음"
        if r == "wait_left":                        # D25 개정 3(09-13)
            return "대기 끝 — 기다리던 동료(%s) 시야 이탈" % ", ".join(res.get("allies", []))
        if r == "encounter":
            bits = []
            if res.get("monsters"):
                bits.append("적 출현: " + ", ".join(m["kind"] for m in res["monsters"]))
            if "trap" in res:
                tr = res["trap"]
                if tr.get("safe"):
                    bits.append("%s 회피!" % tr.get("name", "함정"))
                elif tr.get("alarm") is not None:
                    bits.append("%s 발동!! 몹 %d 각성" % (tr.get("name", "경보"), tr["alarm"]))
                else:
                    bits.append("%s! %d피해" % (tr.get("name", "함정"), tr.get("dmg", 0)))
            if res.get("treasure"):
                bits.append("$ 획득")
            if res.get("potion"):
                bits.append("! 물약 획득")
            if res.get("found"):
                bits.append("발견: " + ", ".join(f["name"] for f in res["found"]))
            if res.get("entered"):                     # D19: 같은 걸음이 처음 방 진입이기도 했다
                bits.append("처음 온 %s %s 진입" % (res["entered"].get("kind", "공간"),
                                                    res["entered"].get("id", "?")))
            return "보행 정지 — " + (" / ".join(bits) or "조우")
        if r == "entered":                             # D19 처음 방 정지 — 구조가 열렸다, 재결정
            zz = res.get("zone") or {}
            return "처음 온 %s %s에 들어섰다 — 멈춰서 살핀다 (재결정)" % (
                zz.get("kind", "공간"), zz.get("id", "?"))
        if r == "sighted":                             # D19 탐색 종점 — 새 명사가 나타나면 멈춤
            return "보행 정지 — 새로 보임: " + ", ".join(
                x.get("name", "?") for x in res.get("seen", []))
        if r == "blocked" and res.get("monsters"):     # D1 개정: 보이는 몹의 길목 점거 = 멈춰 보고
            return "길 막힘 — %s가 길목을 점거" % ", ".join(m["kind"] for m in res["monsters"])
        if r == "blocked" and res.get("allies"):       # D18: 동료發 대우회 — 멈춰 보고
            return "길 막힘 — 동료(%s)가 길목에 서 있어 크게 돌아야 함" % \
                ", ".join(a["name"] for a in res["allies"])
        if r == "following":                           # 동행(D18 A-5) — 지속 order, 완결 아님
            tgt = str(res.get("target", "?")).replace("follow:", "")
            return ("%s 곁을 따라 걷는다" if res.get("to") else "%s 곁을 지키며 따른다") % tgt
        if r == "beside":                              # 추적(D48 개정) — 곁을 지키는 틱(대상이 움직이는 중)
            return "%s 곁에 붙어 있다 (추적 중)" % str(res.get("target", "?")).replace("chase:", "")
        if r == "idle":                                # 동행 고착 해약(FOLLOW_IDLE) — 재결정 반환
            tgt = str(res.get("target", "?")).replace("follow:", "")
            return "동행을 접는다 — %s가 한동안 제자리 (같이 서 있기만 했다, 재결정)" % tgt
        if r == "reunion":                             # 재회 정지(D21①) — 연결의 발견, 재결정
            return "보행 정지 — 낯익은 곳 재회: %s (재결정)" % res.get("name", "?")
        if r == "wander":                              # 맴돎 정지(D21②) — 관찰 보고, 재결정
            return "보행 정지 — 맴돎 자각: 최근 %d걸음 새 목격 0 (재결정)" % res.get("steps", 0)
        tag = {"walking": "자동보행", "arrived": "도착", "at_exit": "계단 앞에 섰다",
               "treasure": "$ 획득", "potion": "! 물약 획득", "blocked": "길 막힘"}
        if r == "arrived" and "to" not in res:         # 움직이는 목표(몹·동료) 곁 도달 = 걷기 전 완료
            return "%s 곁에 도착 — 재결정" % str(res.get("target", "?")).replace("chase:", "")
        if r == "lost":                                # 유령 좌표의 끝(07-05 부검 정직화) — 허탕 보고.
            # '곁에 없다'까지만 단정 — 대각 한 칸에 비껴 서 있을 수도 있다(그건 sights 가 보여준다)
            return "%s를 마지막 본 자리까지 갔지만 — 곁에 없다 (재결정)" % str(res.get("target", "?")).replace("follow:", "").replace("chase:", "")
        if res.get("paced"):                           # 교대(D18 개정) 양보 — 같은 방향 행군 한 박자
            return "동료(봇%s)가 앞서 걷는 중 — 한 박자 양보(제자리)" % res["paced"]
        pre = ("동료(%s)와 자리 교대 — " % res["swap"]["name"]) if res.get("swap") else ""
        return pre + "%s (%s)" % (res.get("to", "?"), tag.get(r, r))
    if t == "interact":
        r = res["result"]
        if r == "exit":
            group = res.get("party", [])
            if len(group) == 1:                    # 솔로 판 — 혼자 계단을 내려간다. '다 모였다'는
                return "홀로 계단을 내려간다 — 탈출!!"   #   거짓이다(결과 보고 오역은 이 판의 오랜 병).
            return "다 모였다 — 함께 하강!! (%s)" % "·".join(group)
        if r == "locked":                          # D65 봉인된 워프게이트
            return "워프게이트 — 봉인돼 있다(열리지 않는다)"
        if r == "ascend":
            group = res.get("party", [])
            if res.get("gate"):                    # D65 워프게이트 귀환
                return ("홀로 워프게이트를 지나 마을로" if len(group) == 1
                        else "다 모였다 — 봉인 풀린 워프게이트로 마을 귀환!! (%s)" % "·".join(group))
            if len(group) == 1:
                return "홀로 계단을 올라 마을로"
            return "다 모였다 — 함께 마을로!! (%s)" % "·".join(group)
        if r == "npc_gift":
            return '%s — %s 받음 — "%s"' % (res.get("npc", "?"), res.get("item", "?"), res.get("line", "…"))
        if r == "npc_talk":
            return '%s — "%s"' % (res.get("npc", "?"), res.get("line", "…"))
        if r == "npc_report":                      # D69 귀환 보고
            tt = res.get("titles") or {}
            return '%s에게 원정 보고 — 완수 %s / 미완 %s — "%s"' % (
                res.get("npc", "?"), "·".join(tt.get(x, x) for x in (res.get("done") or [])) or "없음",
                "·".join(tt.get(x, x) for x in (res.get("undone") or [])) or "없음", res.get("line", "…"))
        if r == "quest_accepted":                  # D69 의뢰 맡음
            return "\U0001f4dc 의뢰 맡음: %s — %s%s" % (res.get("title", "?"), res.get("goal", "?"),
                                                     (" (보상: %s)" % res["reward"]) if res.get("reward") else "")
        if r == "quest_already":
            return "\U0001f4dc 이미 맡은 의뢰: %s" % res.get("title", "?")
        if r == "wait_allies":
            bits = ([f"아직: 봇{'·'.join(res['missing'])}"] if res.get("missing") else []) \
                 + ([f"볼일 중: 봇{'·'.join(res['busy'])}"] if res.get("busy") else [])
            return "계단에서 동료를 기다린다 (%s)" % " / ".join(bits)
        if r == "chest_loot":
            return "상자를 열었다 — 보물 %d개!" % res.get("loot", 0)
        if r == "chest_trap":
            return "상자에서 독침이! %d피해" % res.get("dmg", 0)
        if r == "fountain_heal":
            return "샘물을 마셨다 — HP %d 회복" % res.get("heal", 0)
        if r == "fountain_harm":
            return "샘물이 오염돼 있었다 — %d피해" % res.get("dmg", 0)
        if r == "equip":
            return "%s 착용 — %s +%d%s" % (
                res.get("item", "?"), "피해" if res.get("slot") == "weapon" else "막기",
                res.get("bonus", 0),
                (" (헌 %s은 그 자리에)" % res["dropped"]) if res.get("dropped") else "")
        tag = {"treasure": "$ 획득", "potion": "! 회복 물약 획득", "too_far": "너무 멀다",
               "nothing": "허탕", "no_target": "대상 없음"}
        return "상호작용 %s — %s%s" % (res.get("target", "?"), tag.get(r, r), quest_sfx(res))
    if t == "give":                                            # 건네기(D47 ②)
        if res.get("result") == "given":
            return "봇%s에게 %s 건넴%s" % (res.get("to", "?"), res.get("what", "?"),
                                          " (그의 발밑에 놓임)" if res.get("placed") else "")
        return "건네기 — " + {"too_far": "곁에 없다", "nothing": "줄 것이 없다", "no_target": "대상 없음",
                              "no_room": "놓을 자리 없음"}.get(res.get("result"), str(res.get("result")))
    if t == "bond":                                            # 친목(D47 ②)
        if res.get("result") == "done":
            return "봇%s에게 친목 — %s" % (res.get("to", "?"), res.get("form", "몸짓"))
        return "친목 — " + {"too_far": "곁에 없다", "no_target": "대상 없음"}.get(res.get("result"), str(res.get("result")))
    if res.get("result") == "zone_enter":                      # D86 — 걷다가 새 구역에 들어서 멈춤
        return "%s에 들어섰다 — 걸음을 멈추고 둘러본다" % (res.get("zone") or "다른 구역")
    if res.get("result") == "need_party":                      # D84 조각 4 — 던전 입구는 파티를 맺은 사람만
        return "던전 입구 — 파티가 없어 지나지 못했다"
    if t == "party_form":                                      # 파티 결성(D84 조각 3)
        r_ = res.get("result")
        if r_ == "party_asked":
            return "봇%s에게 파티 결성을 청함" % res.get("to", "?")
        if r_ == "party_formed":
            return "파티 결성 — %s" % "·".join("봇%s" % c for c in res.get("members") or [])
        return "파티 결성 — " + {"party_need_guild": "모험가 길드 구역 밖", "party_already": "이미 같은 파티", "party_asked_already": "이미 청해 두었다",
                             "party_not_gathered": "길드 구역에 없는 사람 " + "·".join("봇%s" % c for c in res.get("missing") or []),
                             "no_target": "대상 없음"}.get(r_, str(r_))
    if t == "party_leave":                                     # 파티 탈퇴(D84 조각 3)
        if res.get("result") == "party_left":
            return "파티 탈퇴%s" % (" — 남은 사람이 하나라 그 파티는 없어졌다" if res.get("freed") else "")
        return "파티 탈퇴 — " + {"party_none": "파티가 없다", "party_need_guild": "모험가 길드 구역 밖"}.get(res.get("result"), str(res.get("result")))
    if t == "drink":
        if res.get("result") == "drink_heal":
            return "회복 물약을 들이켰다 — HP %d 회복(전부), 남은 물약 %d병" % (
                res.get("heal", 0), res.get("potions", 0))
        return "물약을 마시려 했지만 — 없다"
    if t == "attack":
        if res.get("result") == "no_target":
            return "공격 — 인접한 적 없음(허공)"
        if res.get("result") == "too_far":
            return "공격 — 지목한 적이 너무 멀다"
        sneak = "기습! " if res.get("surprise") else ""    # 우리가 기습(자는/배회 적 급습)
        if not res["hit"]:
            return "%s공격 %s — 빗나감" % (sneak, res["target"])
        head = sneak + ("대성공! " if res.get("crit") else "")
        tail = " 처치!" if res.get("killed") else " (적HP%d)" % res["monster_hp"]
        return "공격 %s — %s%d피해%s%s" % (res["target"], head, res["dmg"], tail, quest_sfx(res))
    if t == "search":
        f = res.get("found", [])
        if not f:
            return "샅샅이 살폈다(반경%d) — 아무것도 없음" % res.get("radius", 1)
        return "샅샅이 살폈다 — 발견: " + ", ".join(x["name"] for x in f)
    return t


def mon_summary(e):
    if e['type'] == 'monster_status':
        return '%s — %s %d 피해%s' % (e['monster'], e['status'], e['dmg'], '·쓰러짐' if e.get('killed') else '')
    if e["type"] == "monster_notice":                      # 몹이 파티를 발견(발각굴림 성공) = 추적 개시
        return "%s 파티를 발견 — 봇%s 추적 개시!" % (e["monster"], e["target"])
    if e["type"] == "monster_flee":                        # 저HP → 도주 전환
        return "%s 겁에 질려 달아나기 시작한다!" % e["monster"]
    if e["type"] == "monster_join":                        # D51 합류: 동료 곁에 붙어 같이 싸운다
        return "%s %s 곁에 붙는다 — %s" % (e["monster"], e.get("ally_kind", "동료"),
                                         "함께 싸운다!" if e.get("state") == "HUNTING" else "숨을 고른다")
    if e["type"] == "monster_desperate":                   # 도주 탈진 → 필사 반전
        return "%s 더는 도망칠 곳이 없다 — 이빨을 드러낸다!" % e["monster"]
    if e["type"] == "monster_attack":
        if e.get("from_hiding"):                           # 매복자(concealed)의 정체 드러나는 일격
            sneak = "매복!! 어둠에서 %s가 튀어나온다 — " % e["monster"]
        else:
            sneak = "기습! " if e.get("surprise") else ""   # 몹이 봇을 매복(봇이 못 봄)
        if not e["hit"]:
            return "%s%s -> 봇%s  빗나감" % (sneak, e["monster"], e["target"])
        tail = "  쓰러짐!" if e.get("down") else "  (HP%d)" % e["hp"]
        if e.get("status"):
            tail += "  [%s]" % e["status"]                 # 몹의 특수(D34) — 태그가 붙었다
        return "%s%s -> 봇%s  %d피해%s" % (sneak, e["monster"], e["target"], e["dmg"], tail)
    if e.get("fleeing"):
        return "%s 도망친다" % e["monster"]
    return "%s 다가온다" % e["monster"]


# ── 마을(D29, 2026-07-30) — 마을(0층)↔던전(1층~) 왕복의 러너 몫 ──────────────
def _story_of(eid):
    """D75(09-15) 정의의 story 부품({trait, history}) — 없으면 None(옛 인라인 NPC·정의 없는 건물)."""
    try:
        return ((G.ENT.get(eid) or {}).get("comps") or {}).get("story") if eid else None
    except Exception:
        return None


def build_town(path=None, apart=False, quests=None, walkers=False, guide=False):
    """town.json(손그림 고정 맵 — 고향은 랜덤이 아니다) → 마을 Dungeon.
    NPC 는 좌표로 심는다(맵의 '&'는 그림 표기 — from_ascii 는 바닥으로 읽음).
    town.json 이 {"layout": "<상대경로>"} 면(09-11, 맵 트랙 저작 원본 참조 — 상대 경로는 town 파일 위치 기준) 그 layout 을
    Dungeon.from_layout 으로 격자화하고 NPC 배치는 layout 의 id·칸을 쓴다(이름·대사·선물은 entities/npc).
    D69(09-14): apart=True 면 출발 자리를 건물(길드·주점·신전) 문턱 곁으로 흩는다(캐릭터 번호 순 ↔ 건물 id 순, 결정론) ·
    quests=의뢰 장부(new_quests)를 걸고 게시판 순서로 관측 id 를 매긴다(index_quests) · NPC 정의 전체·역할 한 줄을 엔진에 둔다.
    반환: (dungeon, starts) — starts=맵 숫자 표기 자리(첫 출발) 또는 흩어진 자리."""
    path = path or os.path.join(HERE, "town.json")
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    if spec.get("layout"):
        with open(os.path.join(os.path.dirname(os.path.abspath(path)), spec["layout"]), encoding="utf-8") as f:
            layout = json.load(f)
        d, starts = G.Dungeon.from_layout(layout, seed=DUNGEON_SEED, depth=0)
        placements = d.layout_result["npcs"]
    else:
        d, starts = G.Dungeon.from_ascii(spec["map"], seed=DUNGEON_SEED, depth=0)
        placements = spec.get("npcs", [])
    d.town = True
    d.status = STATUS_ON                   # 상태 태그(D34)는 마을에서도 몸에 붙어 있다(걸으면 피가 난다)
    d.rest_verb = REST_ON                  # 휴식(D35)은 마을에서도 된다(여관은 다음 단계)
    d.relations = RELATIONS_ON             # 관계 장부(D36)는 마을 대화도 센다
    # D29 개정(09-06): 러너 스위치 미러링 — from_ascii 는 __new__ 경유라 아래가 전부 False 였다(마을=스위치 암흑
    # 지대: 실측 마을 113틱 말 걸림 정지 0회·배달된 말 7%만 읽힘·wait 동사 없음·상인 선물 목격 미배달). 09-05
    # scenario.py 구멍 ②와 같은 부류(D24~D27 신설 때 여기 미러링 누락). selfstop·dry_signal 은 마을에서 계속
    # 끈다 — 전체 시야라 seen_cells 증분이 항상 0 이라 맴돎·무발견 신호가 뜻을 잃는다(상인 왕복에 맴돎 정지를
    # 걸지는 후속 재론).
    d.hail, d.wait_verb, d.motion = HAIL_ON, WAIT_ON, MOTION_ON       # D24 말 걸림 정지 · D25 wait · D27 이동중
    d.ally_doing = ALLY_DOING_ON                                       # D27 개정(09-12) 동료 행동 표시
    d.events, d.graves = EVENTS_ON, GRAVES_ON                          # D22 사건층(상인 선물 목격·입구 사용 목격)
    d.ally_sight, d.social = ALLY_SIGHT_ON, SOCIAL_ON                  # 동료 시야 면제 · 채널 분리
    d.trail_on, d.objtags = TRAIL_ON, OBJTAGS_ON                       # D38 궤적 · D39 오브젝트 태그
    d.floor_on = FLOOR_ON                                              # D40 층 집계·결산(마을도 한 층)
    d.give_verb, d.bond_verb = GIVE_ON, BOND_ON                         # D47 ② 건네기·친목(마을에서도 곁이면 된다)
    d.auto_approach = brains.COMPOSE
    d.composed_actions = brains.COMPOSE
    d.place_story, d.zone_story, d.town_notice = {}, {}, None   # D75(09-15) 장소·사람 소개(피처 id → {trait, history}) · 구역 이름 → 같은 꼴 · 마을 진입 한마디
    d.skills, d.trpg_combat, d.random_skill = SKILLS_ON and brains.COMPOSE, TRPG_COMBAT_ON, RANDOM_SKILL_ON
    for n in placements:
        x, y = int(n["x"]), int(n["y"])
        spec_n = {**G.ENT.npc(n["id"]), **{k: v for k, v in n.items() if k in ("name", "line", "line_again", "gift")}} \
            if n.get("id") else n              # D50: 배치(id·좌표)는 town.json, 이름·대사·선물은 entities/npc — 옛 인라인 꼴도 읽힌다
        if d.grid[y][x] != G.FLOOR:            # 좌표-그림 어긋남은 시작 전에 죽는 게 낫다
            raise ValueError("town.json NPC %r 좌표 (%d,%d)가 바닥이 아니다" % (spec_n["name"], x, y))
        nfid = d._add_feature("npc", spec_n["name"], x, y)
        d.npc_defs[spec_n["name"]] = {k: v for k, v in spec_n.items() if v not in (None, [], "")}   # D69 역할·성격·보고 대사(판정은 report 만)
        if spec_n.get("role"):                 # D69 역할 한 줄 — 관측 "길드 접수원 (원정 물품 · 의뢰 접수와 귀환 보고)"
            d.feature_roles[nfid] = spec_n["role"]
        d.npc_lines[spec_n["name"]] = spec_n.get("line") or "…"
        if n.get("id") and _story_of(n["id"]):
            d.place_story[nfid] = dict(_story_of(n["id"]))   # D75 소개(정의가 있는 NPC 만)
        if spec_n.get("gift"):                 # D32 상점 v0 — 고정 선물(물약 1/방문·빈손이면 단검)
            d.npc_gifts[spec_n["name"]] = dict(spec_n["gift"])
        if spec_n.get("line_again"):           #   두 번째 대사(정해진 문장만)
            d.npc_lines_again[spec_n["name"]] = spec_n["line_again"]
    res = getattr(d, "layout_result", None) or {}
    if TOWN_BUILDINGS_ON and res.get("spaces"):   # D60(09-12) 마을 관측: 건물 = 문턱 칸의 피처 — 관측(이름·방위·거리)·goto·목격이
        names = {b["id"]: b["name"] for b in res["spaces"]["buildings"]}   #   기존 오브젝트 체계로 그대로 된다(엔진 무접촉)
        ents = {b["id"]: b.get("entity") for b in res["spaces"]["buildings"]}   # D61: 피처 → 건물 정의 id(역할 부품 조회)
        d.building_defs = {}
        for e in res.get("entrances", []):
            x, y = int(e["cell"][0]), int(e["cell"][1])
            if max(abs(x - d.exit[0]), abs(y - d.exit[1])) <= 1:   # 던전 입구 건물: 문턱이 '>' 바로 곁 — 입구 피처가 이미 그 자리(이름도 '던전 입구')
                continue
            if d.grid[y][x] != G.FLOOR:
                raise ValueError("건물 %r 문턱 (%d,%d)가 바닥이 아니다" % (e.get("building"), x, y))
            fid = d._add_feature("building", names.get(e.get("building"), "건물"), x, y)
            if NOTICES_ON:                         # D61 건물 역할 부품 — 정의의 board/oracle 을 _notices 가 읽는다
                d.building_defs[fid] = ents.get(e.get("building"))
            try:                                   # D69 건물 역할 한 줄(정의 comps.building.role) — 관측 "모험가 길드 (의뢰 게시판 · …)"
                role = ((G.ENT.get(ents.get(e.get("building"))) or {}).get("comps") or {}).get("building", {}).get("role")
            except Exception:
                role = None
            if role:
                d.feature_roles[fid] = role
            if _story_of(ents.get(e.get("building"))):
                d.place_story[fid] = dict(_story_of(ents.get(e.get("building"))))   # D75 건물 소개
    d.features[d._exit_fid].name = "던전 입구"   # 같은 '>'라도 마을에선 탈출구가 아니라 입구다
    if _story_of("dungeon_gate"):
        d.place_story[d._exit_fid] = dict(_story_of("dungeon_gate"))   # D75 던전 입구 소개(입구 피처=건물 정의 dungeon_gate)
    d.town_hear = "zone" if (TOWN_HEAR == "zone" and res.get("spaces")) else None   # D70 구역 지각 — 구역이 있는(layout) 마을만
    d.town_sight = "zone" if (TOWN_SIGHT == "zone" and res.get("spaces")) else None   # D86 시야 = 지금 선 구역 — 같은 조건
    if res.get("spaces"):                          # D75 구역·마을 소개 — 구역 이름 → story, 마을 전체 history 는 진입 한마디(첫 관측 1회, G.spawn 이 floor_notice 로)
        for r_ in res["spaces"].get("regions", []):
            if r_.get("name") and _story_of(r_.get("entity")):
                d.zone_story[r_["name"]] = dict(_story_of(r_.get("entity")))
        d.town_notice = (_story_of("town_wonderland") or {}).get("history") or None
        if guide:                                  # D81 마을 안내의 장소 줄 — 건물과 던전 입구의 특징(정의 story.trait 그대로)을 구역 이름과 함께. 입구는 맨 끝
            d.town_guide = [{"name": d.features[fid_].name, "zone": d._town_zone(d.features[fid_].x, d.features[fid_].y), "about": st_["trait"]}
                            for fid_, st_ in sorted(d.place_story.items(), key=lambda kv: (d.features[kv[0]].type == "exit", kv[0]))
                            if st_.get("trait") and d.features[fid_].type in ("building", "exit")] or None
    if walkers and res.get("spaces"):              # D73 마을 행인 — 정의(npc.walk)가 있는 NPC 를 제 구역의 빈 칸에(시드 파생 RNG, 결정론)
        rname = {r["id"]: r.get("name") for r in res["spaces"]["regions"]}
        avoid = {tuple(v) for v in starts.values()}
        for eid in sorted(e for e, dd in G.ENT.load().items() if dd["kind"] == "npc" and (dd["comps"].get("npc") or {}).get("walk")):
            spec_w = G.ENT.npc(eid)
            if eid in res.get('walker_rects', {}):
                spec_w = {**spec_w, 'walk': {**spec_w['walk'], 'rect': list(res['walker_rects'][eid])}}
            region = rname.get((spec_w.get("walk") or {}).get("region"))
            if not region:
                continue
            fid = d.add_walker(spec_w["name"], region, (spec_w.get("walk") or {}).get("rate", 0.5), avoid=avoid,
                               rect=(spec_w.get("walk") or {}).get("rect"))   # D82 걷는 자리(구역 안의 앞마당) — 없으면 구역 전체
            if fid is None:
                continue
            d.npc_defs[spec_w["name"]] = {k: v for k, v in spec_w.items() if v not in (None, [], "")}
            if spec_w.get("role"):
                d.feature_roles[fid] = spec_w["role"]
            d.npc_lines[spec_w["name"]] = spec_w.get("line") or "…"
            if _story_of(eid):
                d.place_story[fid] = dict(_story_of(eid))   # D75 행인 소개
            if spec_w.get("line_again"):
                d.npc_lines_again[spec_w["name"]] = spec_w["line_again"]
    if quests is not None:                         # D69 의뢰 장부(파티 단위) — 게시판 순서로 q1, q2… 를 매긴다(결정론)
        d.quests = quests
        d.index_quests()
    if apart and res.get("entrances"):             # D69 흩어진 출발 — 던전 입구 건물(문턱이 '>' 곁)은 빼고, 건물 id 순 ↔ 캐릭터 번호 순
        ents = sorted((e for e in res["entrances"]
                       if max(abs(int(e["cell"][0]) - d.exit[0]), abs(int(e["cell"][1]) - d.exit[1])) > 1),
                      key=lambda e: str(e.get("building")))
        taken, apart_starts = set(), {}
        for i, c in enumerate(sorted(starts)):
            if i >= len(ents):
                break                              # 건물보다 사람이 많으면 나머지는 광장 자리 그대로
            x, y = int(ents[i]["cell"][0]), int(ents[i]["cell"][1])
            cells = [p for p in arrive_cells(d, x, y, 8) if p not in taken]
            if cells:
                apart_starts[c] = cells[0]
                taken.add(cells[0])
        starts = {**starts, **apart_starts}
    return d, starts


def deliver_and_hail(d, bots, says, say_to, say_kind=None, open_props=None):
    """사회층 한 틱(러너 소유) — ①배달: 말한 사람이 시야 안이면 들린다(전원, `to` 무관 — 귀는 못 닫는다)
    ②대화 뼈(D36 talk): ③말 걸림 정지(D24 hail_stop): **지목(D41, 2026-09-06 파트너 확정 "대상 없음=혼잣말,
    아무도 안 멈춤")**이 켜진 판은 ②③ 둘 다 `to` 로 나를 지목한 말(또는 all)만 센다 — 07-24 큰 판·09-06 17091
    판의 3인 회전 공명(한마디에 둘이 서고 둘이 답하면 셋이 서는 되먹임)의 뿌리를 캐릭터의 의도로 돌린다.
    SAYTO_ON=0 이면 구판(들리면 전원 정지·배달 쌍 전부 뼈).
    **말의 종류(D47, 2026-09-08 파트너 "제안은 멈추게 하고 명확한 요구를, 일반 대화는 안 멈춘다")** — SAYKIND_ON 판:
    ③정지는 **제안만**(say_kind=제안: to=나 → 나만, 대상 없음·all → 회의=시야 안 전원), 잡담은 종류 무관 들리기만.
    ②뼈는 잡담=talk(D41 그대로 지목·방송만), 제안=proposed/asked(제안 장부 `open_props[받는 봇][한 봇]=turn` — 상대가
    답하기 전 같은 사람의 재제안은 정지도 뼈도 없이 들리기만: 파트너 "같은 제안이 반복돼 계속 세우는 문제 방지").
    반환 (inbox, hails) — inbox 메시지 `{from, text, turn, to?, kind?}`(kind 는 제안일 때만)."""
    say_kind = say_kind or {}
    open_props = open_props if open_props is not None else {}
    kind_on = SAYKIND_ON and SAYTO_ON
    inbox = {}
    for b in bots:
        seen = d.visible_cells(b["x"], b["y"]) if b["alive"] else set()
        inbox[b["char"]] = [{"from": oc, "text": t, "turn": d.turn,
                             **({"to": say_to[oc]} if say_to.get(oc) else {}),
                             **({"kind": "제안"} if (kind_on and say_kind.get(oc) == "제안") else {})}
                            for oc, t in says.items()
                            if oc != b["char"]
                            and any(o["char"] == oc and d.hears(b, o["x"], o["y"], seen) for o in bots)]   # 던전=시야 · 마을 구역 지각(D70)
    by_char = {o["char"]: o for o in bots}
    reaction_book = G.SR.book(d)
    if reaction_book is not None:
        for actor, text in says.items():
            recipients = [b['char'] for b in bots if b['alive'] and not b['won']
                          and any(m['from'] == actor for m in inbox[b['char']])]
            rid = reaction_book.record('say', actor, recipients, d.turn, text=text,
                                       say_kind=say_kind.get(actor, '잡담'), addressed_to=say_to.get(actor))
            if rid:
                for char in recipients:
                    for message in inbox[char]:
                        if message['from'] == actor:
                            message['social_event_id'] = rid

    def proposal_to(m, b):
        # D47: 이 말이 나를 세울 제안인가 — 지목(to=나) 또는 회의(대상 없음·all)
        to = m.get("to")
        return kind_on and m.get("kind") == "제안" and (to in (None, "all") or str(to) == str(b["char"]))

    def counts(m, b):
        # 대화 뼈(talk): 구판은 전부, 지목 판은 나를 지목·방송한 말만. 제안은 제 뼈(proposed/asked)로 따로 센다(D47)
        if not SAYTO_ON:
            return True
        if kind_on and m.get("kind") == "제안":
            return False
        return G.addressed_to(m, b["char"])
    for b in bots:                         # 이야기를 나눔(D36 뼈) — 지목된 말마다 쌍당 틱당 1(엔진이 중복 제거)
        for m in inbox.get(b["char"], []):
            ob = by_char.get(m["from"])
            if ob is not None and b["alive"] and ob["alive"] and counts(m, b):
                d.note_talk(b, ob)
    fresh = {}                             # D47 제안 장부: 이번 틱 새로 접수된 제안 {받는 봇: [한 봇, …]} = 정지 후보
    for b in bots:
        if not (b["alive"] and not b["won"]):
            continue
        for m in inbox.get(b["char"], []):
            ob = by_char.get(m["from"])
            if ob is None or not ob["alive"] or not proposal_to(m, b):
                continue
            opened = open_props.setdefault(b["char"], {})
            if m["from"] in opened:
                continue                   # 응답 전 재제안 = 무효(들리기만 — 반복 방지)
            opened[m["from"]] = d.turn
            d.note_proposal(ob, b)         # 시도의 뼈 — 한 쪽 proposed, 받는 쪽 asked
            fresh.setdefault(b["char"], []).append(m["from"])

    def stops(m, b):
        if not kind_on:
            return counts(m, b)            # D41 판: 지목·방송이면 종류 무관 정지
        return m["from"] in fresh.get(b["char"], []) and proposal_to(m, b)
    hails = {}                             # 말 걸림 정지(07-24 D24): 나를 부른 말이 있는 '걷던' 동료는 멈춰서
    for b in bots:                         #   다음 틱 결정권을 받는다(지목 판 — 혼잣말·남에게 한 말엔 안 선다)
        if b["alive"] and not b["won"] and inbox.get(b["char"]):
            froms = [m["from"] for m in inbox[b["char"]] if stops(m, b)]
            got = d.hail_stop(b, froms) if froms else []
            if got:
                hails[b["char"]] = got
    # D72(09-14 파트너 "혼자 있을 때도 동료의 이름을 부르면서 동료에게 말하는 것처럼 말한다 … 이상한 부분"): 말의 결과 되먹임 —
    #   지목한 말(to=번호|all)이 누구에게 들렸는지를 말한 사람의 궤적에 남긴다(0콜, 자기 경험 = 시야-온리 무위반). 규칙을 더 적는 대신
    #   "네 말을 들은 사람: 없음"을 다음 결정에서 보게 한다(D1 "자기 행동의 결과를 관측"). 혼잣말(to 없음)은 남기지 않는다.
    for oc, t in says.items():
        if not say_to.get(oc):
            continue
        sb = by_char.get(oc)
        if sb is None or not sb["alive"]:
            continue
        heard = [b["char"] for b in bots if b["char"] != oc and any(m["from"] == oc for m in inbox.get(b["char"], []))]
        d._trail_add(sb, {"type": "said", "to": say_to[oc], "kind": say_kind.get(oc, "잡담"), "heard": heard,
                          "text": str(t)[:40], "turn": d.turn})
    return inbox, hails


def classify_reply(dec, other):
    """반응의 형태(D47 ②, 2026-09-09 파트너 "응답에서 제안 승낙 시 선택지 안에서 행동할 수 있게") — 상대(other)의 제안·친목·
    건네기 뒤 내 첫 결정이 그 사람을 향했나: **행동**(건네기·친목·동행·합류(goto b<그>)의 대상이 그 사람) / **말**(say 의 to 가
    그 사람 또는 all) / **없음**. 내용(수락·거절)은 안 읽는다 — 엔진이 제안 내용을 모르니 승낙은 곧 행동이다(파트너 초안 §A-3
    "시도했다고 수락까지 자동으로 정하지 않는다"). 순수 함수."""
    if not dec:
        return "없음"
    if dec.get("type") in ("give", "bond", "follow", "goto", "party_form") and str(dec.get("target") or "") == "b%s" % other:   # party_form = D84 조각 3
        return "행동"
    if dec.get("say") and dec.get("to") in (other, "all"):
        return "말"
    return "없음"


def settle_proposals(d, bots, open_props, decisions, replies=None):
    """D47 반응 장부 — 제안을 받은 봇이 그 뒤 **첫 결정**을 내리면 제안은 닫힌다(유효기간 = 상대의 다음 결정까지, 파트너
    "제안을 받았으니 판단을 새로 내리게 하자"). 그 결정에서 제안한 사람에게 **말했거나 행동했으면**(classify_reply — D47 ②:
    건네기·친목·동행·합류로 그를 향한 것도 답이다) '답함' 뼈(answered/replied) — 내용(수락·거절)은 안 읽는다. 작정 집행
    (src=plan)은 읽지 않았으니 열어 둔다. 반환 {받은 봇: {한 봇: 답함 여부}}(계측 — 형태는 replies 목록에 {from,to,kind,how})."""
    by = {b["char"]: b for b in bots}
    out = {}
    for c, dec in (decisions or {}).items():
        if not dec or dec.get("src") == "plan" or dec.get("skipped"):
            continue
        opened = open_props.get(c)
        if not opened:
            continue
        for a in list(opened):
            how = classify_reply(dec, a)
            answered = how != "없음"
            if answered and by.get(a) is not None and by.get(c) is not None:
                d.note_answer(by[a], by[c])
            out.setdefault(c, {})[a] = answered
            if replies is not None:
                replies.append({"from": c, "to": a, "kind": "제안", "how": how})
            del opened[a]
    return out


def settle_acts(d, bots, open_acts, decisions, replies=None):
    """D47 ② 친목·건네기의 반응 — 받은 봇의 그 뒤 **첫 결정**(작정 집행 제외)이 답이다: 형태(행동|말|없음)를 양쪽 관계 장부의
    상세 기록에 적고(note_reply) 계측 목록에 {from,to,kind,how}. 제안과 같은 자(classify_reply) — 뜻은 안 읽는다."""
    by = {b["char"]: b for b in bots}
    out = []
    for c, dec in (decisions or {}).items():
        if not dec or dec.get("src") == "plan" or dec.get("skipped"):
            continue
        opened = open_acts.get(c)
        if not opened:
            continue
        for a in list(opened):
            how = classify_reply(dec, a)
            if by.get(a) is not None and by.get(c) is not None:
                d.note_reply(by[c], by[a], how)
            ent = {"from": c, "to": a, "kind": opened[a], "how": how}
            out.append(ent)
            if replies is not None:
                replies.append(ent)
            del opened[a]
    return out


def merge_inbox(pending, inbox, cap=PENDING_MAX):
    """D47 배관(437987d): 보관된 말 + 이번 틱 말(오래된 것부터, 상한 cap — 새 말이 뒤라 남는다). 순수 함수."""
    return {c: ((pending.get(c) or []) + (inbox.get(c) or []))[-cap:] for c in inbox}


def keep_pending(inbox, decisions, cap=PENDING_MAX):
    """D47 배관: 이번 틱 결정한 봇(작정 집행은 view() 를 안 불러 못 읽었으니 제외)은 읽었으니 비우고, 걷던 봇은 들린 말을 보관."""
    out = {}
    for c in inbox:
        read = c in decisions and (decisions[c] or {}).get("src") != "plan"
        out[c] = [] if read else list(inbox[c])[-cap:]
    return out


def arrive_cells(d, ax, ay, k, taken=()):
    """(ax,ay) 곁의 자유 칸 k개 — BFS 순(결정론). 계단을 내려선 사람들이 계단 곁에 선다.
    taken(D84) = 이미 사람이 서 있는 칸 — 사람이 있는 세계에 합류할 때만 준다(없으면 옛 판 그대로)."""
    seen, out, frontier = {(ax, ay)}, [], [(ax, ay)]
    while frontier and len(out) < k:
        nxt = []
        for (x, y) in frontier:
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                           (-1, -1), (1, -1), (-1, 1), (1, 1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in seen or not (0 <= nx < d.w and 0 <= ny < d.h):
                    continue
                seen.add((nx, ny))
                if d.grid[ny][nx] == G.WALL:
                    continue
                nxt.append((nx, ny))
                if d.feature_at(nx, ny) is None and not d.monster_at(nx, ny) and (nx, ny) not in taken:
                    out.append((nx, ny))
        frontier = nxt
    return out[:k]


PARTYFORM_GATE_TRAIT = ("계단 아래가 던전. %d명이 맺은 파티만 내려갈 수 있고, 파티는 3칸 안에 모여야 함께 내려간다. 원정에는 제한 시간이 있다"
                        % G.PARTY_ENTRY_SIZE)
#   D84(09-19): 파티 결성 판의 던전 입구 특징 — 정의의 문장("일행이 3칸 안에 모여야 내려간다")은 이 판에서 거짓이다(세계가 하는 말은 참이어야 한다).
#   정의(entities/building/dungeon_gate)는 옛 판과 같이 쓰므로 러너가 그 판의 마을에만 갈아 끼운다. ⚠️문구 임시(검토표)


def _partyform_town(d):
    """파티 결성 판의 마을 — 던전 입구의 특징 문장(관측의 입구 줄·마을 안내 문단)을 그 판의 규칙대로."""
    fid = getattr(d, "_exit_fid", None)
    st = (getattr(d, "place_story", None) or {}).get(fid)
    if st and st.get("trait"):
        st["trait"] = PARTYFORM_GATE_TRAIT
        for g_ in (getattr(d, "town_guide", None) or []):
            if g_.get("name") == d.features[fid].name:
                g_["about"] = PARTYFORM_GATE_TRAIT
    return d


def town_for_run(apart, quests, walkers=False, guide=False):
    """build_town 호출 자리(D69) — 게이트 둘(verify_approach·verify_reactions)이 build_town 을 **인자 없는 스텁**으로 갈아 끼우므로,
    시그니처에 apart 가 없으면 옛 방식으로 부르고 의뢰 장부만 건다(스텁 마을에도 보고·맡기 배관이 죽지 않게)."""
    import inspect
    if 'apart' in inspect.signature(build_town).parameters:
        extra = {"guide": guide} if 'guide' in inspect.signature(build_town).parameters else {}   # D81 — 옛 시그니처 스텁도 그대로 산다
        return build_town(apart=apart, quests=quests, walkers=walkers, **extra)
    d, starts = build_town()
    if quests is not None and getattr(d, 'quests', None) is None:
        d.quests = quests
        if hasattr(d, 'index_quests'):
            d.index_quests()
    return d, starts


def new_floor(nd, lore, quests=None):
    """던전 층 하나(nd ≥ 1) — 시작 층·층 전이·소문 미리보기가 같은 인자로 짓는다(D69 에서 한곳으로). 시드 파생이라 같은 nd 는 같은 층."""
    d = G.Dungeon(w=DUNGEON_W, h=DUNGEON_H, seed=DUNGEON_SEED, depth=nd,
                  n_monsters=N_MON + nd - 1, n_traps=N_TRAP, n_lurkers=N_LURK,
                  scan=SCAN_ON, n_potions=N_POTION, loops=LOOPS_ON, selfstop=SELF_ON,
                  graves=GRAVES_ON, events=EVENTS_ON, dry_signal=DRY_ON, hail=HAIL_ON,
                  wait_verb=WAIT_ON, motion=MOTION_ON, ally_doing=ALLY_DOING_ON,
                  ally_sight=ALLY_SIGHT_ON, social=SOCIAL_ON, solo=SOLO_ON,
                  n_gear=N_GEAR, status=STATUS_ON, rest_verb=REST_ON,
                  relations=RELATIONS_ON, trail=TRAIL_ON, objtags=OBJTAGS_ON, floor=FLOOR_ON, explore_dirs=EXPLORE_DIRS_ON,
                  give_verb=GIVE_ON,
                  bond_verb=BOND_ON,               # (verify_give ⑩ 이 give·bond 인자 한 줄짜리를 두 곳(시작·전이)만 세므로 여기선 두 줄로 나눈다)
                  auto_approach=brains.COMPOSE, composed_actions=brains.COMPOSE,
                  skills=SKILLS_ON, trpg_combat=TRPG_COMBAT_ON, random_skill=RANDOM_SKILL_ON,
                  boss=BOSS_ON and nd >= DEPTHS,   # D65: 최심층 = 보스층(보스·봉인 워프게이트·상자)
                  plan_max=G.PLAN_MAX if PLAN_ON else 0)   # D66: 작정 스위치
    d.lore = lore
    d.quests = quests                              # D69 의뢰 장부는 층을 넘어 같은 객체
    return d


def floor_rumor(d):
    """D69 소문 재료 — 층 하나의 실제 배치를 세계가 센 숫자로(0콜): 몬스터 종별 수·함정·보물·상자·물약·장비. 주점 주인의 '아는 것'."""
    kinds = {}
    for m in d.monsters:
        kinds[m.kind] = kinds.get(m.kind, 0) + 1
    feats = {}
    for f in d.features.values():
        if f.type in ("treasure", "chest", "potion", "weapon", "armor", "fountain"):
            feats[f.type] = feats.get(f.type, 0) + 1
    return {"depth": d.depth, "monsters": kinds, "traps": len(d.traps), "features": feats}


def npc_facts(d, npc_name, bots, fallen, quests):
    """D69 NPC 두뇌의 '아는 것' — 전부 세계의 사실(정의·장부·배치)이고 캐릭터 시트는 없다. NPC 역할별로 다른 사실을 준다:
    접수원=게시판 의뢰·맡은 의뢰·진행·보고 결과 / 주점 주인=지하 1층 실측 소문 / 성직자=신의 요청·묘. 공통=파티 명단·귀환 여부."""
    nd = (getattr(d, "npc_defs", None) or {}).get(npc_name) or {}
    alive = [b for b in bots if b["alive"]]
    facts = ["파티: " + ", ".join("%s(%s, HP %d/%d)" % (b.get("name") or ("모험가 %s" % b["char"]), b["job"], b["hp"], b["maxhp"]) for b in alive)]
    ps_ = getattr(d, "parties", None)
    if ps_ is not None:                    # D84 조각 5: 파티 결성 판 — 옛 첫 줄('파티: 전원')은 거짓이다. 맺어진 파티의 크기와 입구의 규칙을 사실로(이름은 인물 기록 판이면 싣지 않는다)
        sizes = sorted((len(G.party_members(ps_, c)) for c in {min(G.party_members(ps_, b["char"])) for b in alive if G.party_members(ps_, b["char"])}), reverse=True)
        who_ = ("마을의 모험가 %d명(통성명한 적이 없어 이름은 모른다)" % len(alive) if STRANGERS_ON
                else "마을의 모험가: " + ", ".join("%s(%s)" % (b.get("name") or ("모험가 %s" % b["char"]), b["job"]) for b in alive))
        facts[0] = who_ + " · 맺어진 파티: " + (", ".join("%d명" % n for n in sizes) if sizes else "아직 없다")
        if nd.get("report"):
            facts.append("던전 입구의 규정: %d명이 맺은 파티만 지나갈 수 있다 · 파티는 모험가 길드나 주점에서, 같은 곳에 있는 사람끼리 맺는다 — 파티가 모자란 사람에게는 이 규정을 알려 준다" % G.PARTY_ENTRY_SIZE)
    if fallen:
        facts.append("이번 원정에서 쓰러진 사람: " + ", ".join(str(c) for c in fallen))
    facts.append("지금은 원정에서 돌아온 뒤다(워프게이트로 귀환)" if getattr(d, "expedition_returned", False)
                 else "이 사람들은 아직 던전에 내려가지 않았다")   # D83(09-18): 옛 '지금은 원정을 떠나기 전이다'는 내려감을 전제했다 — 사실만(⚠️문구 임시)
    if nd.get("report") and quests is not None:
        board = []
        for tid, qid in sorted((getattr(d, "quest_ids", None) or {}).items()):
            qd = G.quest_def(qid) or {}
            st = "완수" if qid in quests["done"] else ("맡음 %d/%d" % (quests["progress"].get(qid, 0), int((qd.get("req") or {}).get("n") or 1))
                                                       if qid in quests["accepted"] else "게시 중")
            board.append("%s(%s%s) — %s" % (qd.get("title", qid), qd.get("goal", ""), (", 보상: %s" % qd["reward"]) if qd.get("reward") else "", st))
        facts.append("게시판 의뢰: " + (" / ".join(board) or "없음"))
    if nd.get("role") and "소문" in nd["role"] and getattr(d, "rumor", None):
        r = d.rumor
        mons = ", ".join("%s %d마리" % (k, v) for k, v in r["monsters"].items()) or "몬스터 없음"
        fe = r.get("features") or {}
        facts.append("지하 %d층 소문(세계가 센 실제 수): %s · 함정 %d개 · 보물 %d · 상자 %d · 물약 %d · 장비 %d"
                     % (r["depth"], mons, r["traps"], fe.get("treasure", 0), fe.get("chest", 0), fe.get("potion", 0),
                        fe.get("weapon", 0) + fe.get("armor", 0)))
        if quests is not None:
            mine = [G.quest_def(q) or {} for q in quests["accepted"] if (G.quest_def(q) or {}).get("client") == npc_name]
            if mine:
                facts.append("네가 낸 의뢰를 이 파티가 맡았다: " + ", ".join(q.get("title", "?") for q in mine))
    if nd.get("role") and "신" in nd["role"]:
        orc = getattr(d, "oracle", None) or {}
        facts.append(("신의 요청이 걸려 있다: 「%s」" % orc["text"]) if orc.get("text") else "지금 걸려 있는 신의 요청은 없다")
        graves = [f.name for f in d.features.values() if f.type == "grave"]
        if graves:
            facts.append("마을의 묘: " + ", ".join(graves))
    return facts


_WK = ("d", "bots", "inbox", "pending", "open_props", "open_acts")   # D84 세계 하나의 지역 상태(틱 몸통이 머리에서 풀고 나갈 때 되담는다)


def _world_fingerprint():
    """D79 이어가기 전제 — 판의 모양을 정하는 상수들. 스냅샷과 지금 러너가 다르면 그 몸을 이 세계에 놓지 않는다(폴백)."""
    return {"w": DUNGEON_W, "h": DUNGEON_H, "depths": DEPTHS, "max_turns": MAX_TURNS, "town": TOWN_ON, "boss": BOSS_ON,
            "start_boss": START_BOSS, "skills": SKILLS_ON, "trpg": TRPG_COMBAT_ON, "random_skill": RANDOM_SKILL_ON,
            "solo": SOLO_ON, "monsters": N_MON, "traps": N_TRAP, "lurkers": N_LURK, "potions": N_POTION, "gear": N_GEAR,
            "compose": bool(brains.COMPOSE), "scan": SCAN_ON, "loops": LOOPS_ON, "town_apart": TOWN_APART_ON,
            "town_hear": TOWN_HEAR, "quests": bool(QUESTS_ON and NOTICES_ON), "plan": PLAN_ON,
            **({"partyform": True} if PARTYFORM_ON else {}),   # D84: 켠 판에만 적는다 — 옛 스냅샷의 지문과 글자까지 같게
            **({"strangers": True} if STRANGERS_ON else {}),   # D85: 같은 규율
            **({"town_sight": "zone"} if (TOWN_SIGHT == "zone" and TOWN_ON) else {})}   # D86: 같은 규율


def _preserve_stream(src):
    """폴백(되살리기 실패) 때 옛 기록을 runs/ 로 대피 — 론처 preserve_previous 와 같은 규칙(mtime 이름·있으면 안 덮음)."""
    if not (os.path.exists(src) and os.path.getsize(src) > 0):
        return None
    runs = RUNS_DIR or os.path.join(os.path.dirname(os.path.abspath(STATE)), "runs")
    os.makedirs(runs, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(os.path.getmtime(src)))
    dst = os.path.join(runs, "stream-%s.jsonl" % stamp)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    return dst


def _load_resume():
    """DUNGEON_RESUME 처리 → (snap, meta, fail). fail = 이어가기를 청했는데 못 한 사유(새 판을 열되 run_meta.resume_failed 에 남긴다).
    순서: 피클 되살림 → 세계 지문 대조 → 기록 파일(state/stream.jsonl)의 run_meta 가 같은 판인지 → 스냅샷 자리(stream_pos)로 자른다(그 뒤의
    반 줄·판단 정지 줄은 버린다 — 스냅샷이 진실). 어느 단계든 실패면 파일은 건드리지 않은 채 사유만 돌려준다."""
    if not RESUME_PATH:
        return None, None, None
    sp = os.path.join(STATE, "stream.jsonl")
    try:
        snap, meta = snapshot.load(RESUME_PATH)
        fp = _world_fingerprint()
        old = snap.get("world") or {}
        if old != fp:
            diff = sorted(k for k in set(fp) | set(old) if fp.get(k) != old.get(k))
            raise snapshot.SnapshotError("판의 설정이 다르다: %s" % ", ".join(diff))
        with open(sp, "rb") as f:
            head = f.readline()
        m = json.loads(head.decode("utf-8"))
        if m.get("kind") != "run_meta" or m.get("seed") != snap["seed"] or m.get("started") != snap["started"]:
            raise snapshot.SnapshotError("기록 파일이 다른 판이다")
        pos = int(snap["stream_pos"])
        if pos > os.path.getsize(sp) or pos < len(head):
            raise snapshot.SnapshotError("기록이 스냅샷 자리보다 짧다")
        with open(sp, "r+b") as f:
            f.seek(pos - 1)
            if f.read(1) != b"\n":
                raise snapshot.SnapshotError("스냅샷 자리가 줄 끝이 아니다")
            f.truncate(pos)
        if snap.get("side_pos") is not None:                 # D84: 옆 파일도 스냅샷 자리로(없거나 짧으면 그대로 — 옆 기록은 보조, 실패 사유가 아니다)
            ssp = os.path.join(STATE, "stream_side.jsonl")
            if os.path.exists(ssp) and os.path.getsize(ssp) >= int(snap["side_pos"]):
                with open(ssp, "r+b") as f:
                    f.truncate(int(snap["side_pos"]))
        return snap, meta, None
    except (snapshot.SnapshotError, OSError, ValueError, KeyError, TypeError) as e:
        meta0 = snapshot.read_meta(os.path.dirname(os.path.abspath(RESUME_PATH))) or {}
        return None, None, {"path": os.path.basename(RESUME_PATH), "reason": str(e)[:200], "run_id": meta0.get("run_id"),
                            "pages": dict((meta0.get("stop") or {}).get("pages") or {})}


def _take_snapshot(sw, core, meta):
    """루프 머리마다 — 몸 전체를 얼린다(D79, ~100KB·1ms). 실패해도 판은 계속(스냅샷은 보험이지 판정이 아니다)."""
    try:
        return snapshot.write(STATE, {**core, "stream_pos": sw.tell()}, meta)
    except Exception as e:
        event("   \u26a0 스냅샷 실패: %s: %s" % (type(e).__name__, str(e)[:80]))
        return 0


def stop_pages(d, bots, names, turn, req):
    """D79 곱게 멈춤의 수첩 — 살아 있는(아직 계단을 안 탄) 캐릭터마다 한 장(1콜, 동시에). 더미 두뇌·수첩 끔·요청 pages=false 면 0콜."""
    if not (req.get("pages", True) and FLOOR_ON and brains.NOTEBOOK_ON and brains.backend_name() != "dummy"):
        return {}
    live = [b for b in bots if b["alive"] and not b["won"]]
    if not live:
        return {}

    def one(b):
        entry = G.floor_freeze(b, d.depth, turn)[-1]      # 지금 층의 집계 그대로(얼리지 않는다 — 봇 dict 무접촉)
        return b["char"], brains.stop_page(b, entry, names, bots)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(live)) as ex:
        out = dict(ex.map(one, live))
    for c in sorted(out):
        if out[c]:
            event('   \U0001f4d3 %s — 멈추며 수첩 한 장: "%s"' % (names[c], out[c]))
        else:
            event('   \U0001f4d3 %s — 수첩 없음(두뇌 응답 없음)' % names[c])
    return {c: p for c, p in out.items() if p}


def main():
    global DUNGEON_SEED, MAX_TURNS               # D79 이어가기: 스냅샷의 시드·틱 상한으로 되묶는다(새 층 생성·루프 끝이 읽는다)
    run_control.reset(STATE)
    if SKILLS_ON and not brains.COMPOSE:
        raise SystemExit('스킬 알파는 DUNGEON_ACTION_MODE=compose에서 실행한다')
    if TOWN_ON and SOLO_ON:
        raise SystemExit("솔로+마을(D29 v0)은 아직 함께 못 쓴다 — 행선(위/아래)이 갈리면 "
                         "러너의 현재 층이 하나뿐이라 두 무리를 동시에 못 좇는다(서랍: 다중 층 동시 진행)")
    snap, snap_meta, resume_fail = _load_resume()          # D79 이어가기 — 스냅샷이 있으면 그 몸·그 기록 파일에서 이어 쓴다
    if snap is not None:
        DUNGEON_SEED, MAX_TURNS = int(snap["seed"]), int(snap["max_turns"])
        sheets = snap["sheets"]                            #   시트도 그때 것(파티 파일이 바뀌었어도 이 판의 사람들은 그대로)
    else:
        sheets = load_party(PARTY_FILE)                   # 시트 외부화 — 파티 구성=이 파일이 결정
    for c in sorted(sheets):                              # D37(09-06): 외형이 없는 시트는 여기서 뽑아 run_meta 에
        if not sheets[c].get("look"):                     #   적는다(파트너 확정 "기본 파티는 랜덤") — 뷰어가 뽑으면
            sheets[c] = {**sheets[c], "look": sheetkit.random_look(    # 리플레이마다 얼굴이 바뀐다. 난수는 seed·char
                random.Random("look:%d:%s" % (DUNGEON_SEED, c)), sheets[c]["sex"])}   # 로 따로(dungeon.rng 무접촉)
    chars = sorted(sheets)
    names = {c: (sheets[c].get("name") or "봇%s" % c) for c in chars}
    ledger_keys = {c: (sheets[c].get("id") or names[c]) for c in chars}   # D78(09-16) 원장 키 = 저장 캐릭터 id, 없으면 이름(옛 규칙 그대로)
    lore = G.ENT.lore()                                   # 지식 '본문'(D9) — 엔티티 저장소(D50), 판정 무접촉, obs 전용
    if snap is not None:                                   # D79: 발급기·결산은 얼린 그대로(known/book 은 봇과 같은 객체 — 피클이 공유를 보존) · 로그는 이어 쓴다
        iss, rs = snap["iss"], snap["rs"]
    else:
        iss = bestiary.Issuer(ledger_keys)                # 도감 발급기 = 스트림 소비자(D9 '획득')
        if os.environ.get("DUNGEON_LEDGER_IDS_ONLY", "0") != "0":   # D78 계정 원장: 저장한 캐릭터만 이어진다 — 1회용 캐릭터는 파일에 안 남긴다
            iss.skip_keys = {names[c] for c in chars if not sheets[c].get("id")}
        if BESTIARY_FILE:
            iss.load(BESTIARY_FILE)                       # 지난 원정의 지식 이월 — 죽어도 남는 재산(D4)
        for p in glob.glob(os.path.join(STATE, "bot*.log")):  # 이전 판 잔재(다른 인원수) 제거
            os.remove(p)
        for n in ["events.log", "gm.log"] + ["bot%s.log" % c for c in chars]:
            open(os.path.join(STATE, n), "w", encoding="utf-8").close()
        rs = run_summary.Collector()                                # D58 판 결산(기계가 센 숫자 — 판정은 사람이)
    if resume_fail:                                        # 이어가기를 청했는데 못 했다 — 옛 기록은 runs/ 로 대피시키고 새 판을 연다(정직 폴백)
        kept = _preserve_stream(os.path.join(STATE, "stream.jsonl"))
        resume_fail["kept"] = os.path.basename(kept) if kept else None
    sw = run_summary.Tap(stream.StreamWriter(os.path.join(STATE, "stream.jsonl"), append=snap is not None), rs)   # 실행당 truncate(이어가기는 스냅샷 자리 뒤에 append) · 모든 emit 이 결산에도
    brain_pause = run_control.BrainPause(STATE, sw, names, event, limit=PAUSE_LIMIT_SEC)
    returned, returned_party = False, []   # D65 워프게이트 귀환으로 끝난 판의 표식(outcome 'returned')·귀환한 사람들
    last_oracle_id = None                  # D61 개정: 마지막으로 스트림에 남긴 신의 요청 id(새 요청·거둠을 한 번만 적는다)
    quests = G.new_quests() if (QUESTS_ON and NOTICES_ON) else None   # D69 의뢰 장부(파티 단위·판 전체) — 층마다 같은 객체를 건다
    parties = G.new_parties() if PARTYFORM_ON else None               # D84 파티 장부(판 전체) — 의뢰 장부처럼 층마다 같은 객체를 건다(None = 옛 판)
    if snap is not None:                   # D79: 장부·표식도 얼린 그대로
        returned, returned_party = bool(snap["returned"]), list(snap["returned_party"])
        last_oracle_id, quests = snap["last_oracle_id"], snap["quests"]
        parties = snap.get("parties") if PARTYFORM_ON else None
    npc_brain = NPC_BRAIN_ON and brains.backend_name() != "dummy"       # D69 마을 NPC 두뇌 — 더미 판은 콜 0 유지

    if snap is None:                       # ── 새 판: 세계를 짓고 파티를 놓는다 ──
        if TOWN_ON:                            # 마을 판(D29): 원정은 고향에서 시작한다
            d, tstarts = town_for_run(TOWN_APART_ON, quests, TOWN_WALKERS_ON, TOWN_GUIDE_ON)   # D69 흩어진 출발·의뢰 장부 · D73 행인 · D81 마을 안내(게이트 스텁 허용)
            d.lore = lore
            if npc_brain or NPC_HAIL_ON:       # D69·D71 주점 소문 재료 — 지하 1층의 실제 배치(같은 시드=같은 층, 0콜): NPC 답·인사의 숫자
                d.rumor = floor_rumor(new_floor(1, lore))
        else:
            d = G.Dungeon(w=DUNGEON_W, h=DUNGEON_H, seed=DUNGEON_SEED, n_potions=N_POTION, depth=START_DEPTH,   # D67: 프리셋이면 최심층
                          n_monsters=N_MON + START_DEPTH - 1, n_traps=N_TRAP, n_lurkers=N_LURK, scan=SCAN_ON,   #   (층 전이와 같은 몹 수 규칙)
                          loops=LOOPS_ON, selfstop=SELF_ON, graves=GRAVES_ON, events=EVENTS_ON,
                          dry_signal=DRY_ON, hail=HAIL_ON, wait_verb=WAIT_ON, motion=MOTION_ON, ally_doing=ALLY_DOING_ON,
                          ally_sight=ALLY_SIGHT_ON, social=SOCIAL_ON, solo=SOLO_ON, n_gear=N_GEAR,
                          status=STATUS_ON, rest_verb=REST_ON, relations=RELATIONS_ON, trail=TRAIL_ON, objtags=OBJTAGS_ON, floor=FLOOR_ON, explore_dirs=EXPLORE_DIRS_ON, give_verb=GIVE_ON, bond_verb=BOND_ON,
                          auto_approach=brains.COMPOSE, composed_actions=brains.COMPOSE,
                          skills=SKILLS_ON, trpg_combat=TRPG_COMBAT_ON, random_skill=RANDOM_SKILL_ON,
                          boss=BOSS_ON and START_DEPTH >= DEPTHS,   # D65: 첫 층이 곧 최심층이면 여기가 보스층(D67 프리셋 포함)
                          plan_max=G.PLAN_MAX if PLAN_ON else 0)   # D66: 작정 스위치(러너 기본 0)
            d.lore = lore
            d.quests = quests                  # D69 던전 시작 판(보스 프리셋 등)도 장부를 든다 — 워프 귀환 뒤 마을에서 보고
        d.plan_max = G.PLAN_MAX if PLAN_ON else 0    # 마을(from_layout)도 같은 스위치
        if PARTYFORM_ON:
            d.parties = parties                # D84 파티 장부 — 계단이 '내 파티원'만 센다(파티 없는 캐릭터는 혼자)
            if TOWN_ON:
                _partyform_town(d)             #   던전 입구의 특징 문장도 그 규칙대로(옛 문장 '일행이 모여야'는 이 판에서 거짓)
        bots = []
        for c in chars:
            b = G.spawn(d, c, bots, sheet=sheets[c], apart=SOLO_ON)
            if TOWN_ON:                        # 출발 자리=맵 숫자 표기(광장). 표기 밖 인원은 1번 곁
                spot = tstarts.get(c) or (arrive_cells(d, *tstarts[min(tstarts)], 9)[len(bots)]
                                          if tstarts else (b['x'], b['y']))
                d.visited.discard((b['x'], b['y']))
                b['x'], b['y'] = spot
                d.visited.add(spot)
            elif START_BOSS:                   # D67 프리셋 — 보스룸 앞 칸 곁(도착 칸 BFS, 결정론). 앞 칸이 없으면 기본 스폰
                front = d.boss_front()
                spots = arrive_cells(d, *front, 9) if front else []
                if len(bots) < len(spots):
                    d.visited.discard((b['x'], b['y']))
                    b['x'], b['y'] = spots[len(bots)]
                    d.visited.add((b['x'], b['y']))
            b['known'] = iss.known(ledger_keys[c])   # 도감 주입 켬 — 발급기의 set 과 *같은 객체*(획득 즉시 다음 obs 반영) · D78 키=id|이름
            b['book'] = iss.record(ledger_keys[c])   # D53 진행도(조우 수·심층 여부)도 같은 객체 — 해금 즉시 다음 obs 에 본문
            if LEDGER_ON:
                b['ledger'] = G.new_ledger()   # 공간 장부(D17) 켬 — 이 층에서 본 것의 원장
            if STRANGERS_ON:                   # D85 인물 기록 — 씨앗 = 시트에 작가가 쓴 관계 문장(이 캐릭터가 이미 아는 사람). 없으면 아무도 모르는 채로
                b['people'] = {"b%s" % oc: {"name": sheets[oc].get("name") or "봇%s" % oc, "text": str(txt), "turn": 0, "src": "sheet"}
                               for oc, txt in sorted((sheets[c].get("relationships") or {}).items()) if oc in sheets and oc != c}
            bots.append(b)
        saved = {}                             # 마을 판(D29): 층 보존 — depth → {'d': 던전, 'mem': 봇별
                                               #   층-로컬 기억}. "재입장=같은 1층"(파트너 확정 07-30)
        if PARTYFORM_ON:                       # D84: 세계는 지어질 때 등록한다 — 사람이 있든 비었든 같은 층은 같은 세계(합류·복원이 한 길)
            saved[d.depth] = {"d": d, "mem": {}}
    else:                                  # D79 이어가기 — 세계·파티·보존 층을 얼린 그대로(같은 객체 그래프: quests·reaction_book·known 공유 유지)
        d, bots, saved = snap["d"], snap["bots"], snap["saved"]
        d.lore = lore                      #   지식 본문은 지금 정의로(피클에 든 옛 사본 대신 — 판정 무접촉)
        for sv in saved.values():
            sv["d"].lore = lore
    if resume_fail and resume_fail.get("pages"):   # 되살리기 실패 폴백 — 몸은 새로, 멈출 때 쓴 수첩 장은 유지(파트너 "요약해서 들고 있게")
        for b in bots:
            pg = resume_fail["pages"].get(b["char"])
            if pg:
                ns = b.setdefault("notes", [])
                ns.append(pg)
                del ns[:-brains.NOTE_MAX]
    botlog = {c: "bot%s.log" % c for c in chars}
    gm_q = gm_thread = None
    if GM_ON:
        gm.set_party(sheets)      # GM 등장인물 명단(이름·성격) — 1회. 미호출이어도 GM은 동작(폴백)
        # ── GM 페이싱 픽스: 비동기 후채움 + 최신-우선 스킵 ─────────────────
        # 동기 호출(sonnet 60s)이 틱 루프를 장악하던 병목 제거 — 루프는 GM 을 절대 기다리지 않는다.
        # GM 이 연출하는 사이 쌓인 낡은 턴은 버리고 항상 '최신 턴'만 연출(GM=사치품 소비자,
        # 강등 구조 그대로). gm.log 는 [turn N] 표시라 건너뛴 턴이 그대로 보인다.
        gm_q = queue.Queue()

        def _gm_worker():
            while True:
                item = gm_q.get()
                if item is None:
                    return
                t, evs, party = item
                narration = gm.narrate(t, evs, party)
                append("gm.log", "[turn %d]" % t)
                append("gm.log", narration)
                append("gm.log", "")
                event("   GM(t%d): %s" % (t, narration.splitlines()[0] if narration else ""))

        gm_thread = threading.Thread(target=_gm_worker, daemon=True)
        gm_thread.start()
    fallen = list(snap["fallen"]) if snap is not None else []   # 이전 층에서 쓰러진 영웅(층 전이 때 bots 에서 빠짐 — 기록만 남긴다) · D79 얼린 그대로

    if snap is None:                       # ── 새 판: 스트림 머리 ──
        # 스트림 머리: run_meta(1회 — started 가 유일한 비결정 필드) + 첫 level
        reaction_book = G.SR.book(d)
        run_started = time.strftime("%Y-%m-%dT%H:%M:%S")
        sw.emit("run_meta", v=1, started=run_started,
                **alpha_metadata(),
                **({"resume_failed": resume_fail} if resume_fail else {}),   # D79(09-16 additive) 이어가기를 청했으나 못 함 — 새 판을 열었다(사유·대피한 옛 기록·들고 온 수첩)
                **({'reaction': True, 'reaction_schema': 'social-v0.4'} if reaction_book is not None else {}),
                **({"town_sight": "zone"} if (TOWN_SIGHT == "zone" and TOWN_ON) else {}),   # D86(09-19 additive, 켠 판에만) 마을의 시야 = 지금 선 구역 — 시야·정지 물리 메타(town_hear 급)
                **({"strangers": True} if STRANGERS_ON else {}),   # D85(09-19 additive, 켠 판에만) 인물 기록 판 — 프롬프트의 호칭이 캐릭터마다 다르다(내가 적은 이름|낯선 사람) · decisions.person_note
                **({"partyform": True} if PARTYFORM_ON else {}),   # D84(09-19 additive, 켠 판에만) 파티 결성 판 — 계단은 내 파티원만·세계마다 제 시계:
                                           #   tick.bots 가 '이 세계에 있는 사람'만이고 depart/arrive 줄이 실린다(다른 세계 = stream_side.jsonl). 판 모양 메타(town 급)
                seed=DUNGEON_SEED, w=DUNGEON_W, h=DUNGEON_H, depths=DEPTHS,
                monsters=N_MON, traps=N_TRAP, lurkers=N_LURK,
                potions=N_POTION,          # 층당 회복 물약(07-17 additive) — 배치를 바꾸는 판 파라미터
                gear=N_GEAR,               # 층당 장비(07-30 additive) — 같은 급(배치 파라미터)
                town=TOWN_ON,              # 마을 판(D29 additive) — 판 모양 자체가 다름(0층·왕복·클리어)
                start=("boss" if START_BOSS else ("town" if TOWN_ON else "dungeon")),   # D67(09-13 additive) 시작 지점 프리셋 — boss=최심층 보스룸 앞
                sight=G.SIGHT,             # 시야 반경(DUNGEON_SIGHT) — 굴림 수를 바꾸는 세계 물리
                                           #   (리플레이·판 비교의 전제, seed 와 같은 급)
                max_turns=MAX_TURNS, gm=GM_ON,
                stream_obs=os.environ.get("DUNGEON_STREAM_OBS") == "1",   # decisions 에 obs 동봉 여부(스키마 판별용)
                menu=brains.MENU,          # 리모컨(번호 선택) 여부 — decisions 에 choice 가 실리는지 판별용
                **brains.action_metadata(),  # compose 선행 프로브 / 기존 menu·free 구분
                ledger=LEDGER_ON,          # 공간 장부(D17) 여부 — obs(known·돌아가기)를 바꾸는 실행모드 메타
                scan=SCAN_ON,              # 스캐너(D19) 여부 — obs(구조)·정지 물리를 바꾸는 실행모드 메타
                                           #   (걸음 정지 규칙이 달라지므로 리플레이·판 비교의 전제)
                selfstop=SELF_ON,          # 자기 관찰 정지(D21) 여부 — 정지 물리 메타(scan 과 같은 급)
                dry_signal=DRY_ON,         # 무발견 신호(07-24) 여부 — obs 한 줄이 늘어나는 실행모드 메타
                hail=HAIL_ON,              # 말 걸림 정지(D24) 여부 — 정지 물리 메타(selfstop 과 같은 급)
                wait=WAIT_ON,              # wait 동사(D25) 여부 — 메뉴·정지 물리 메타
                plan=PLAN_ON,              # 작정(D16 then) 여부 — D66(09-13 additive) 러너 기본 0: false 면 then 을 받아도 작정 없음(콜 수·관측 접점 메타)
                motion=MOTION_ON,          # 이동중 표시(D27) 여부 — obs 동료 항목 메타
                ally_doing=ALLY_DOING_ON,  # 동료 행동 표시(D27 개정 09-12) 여부 — obs 동료 항목(doing) 표현층 메타
                social=SOCIAL_ON,          # 채널 분리(07-26) 여부 — 말 걸림이 작정을 부수는지
                                           #   여부가 달라진다(정지 물리 + 콜 구조 메타)
                ally_sight=ALLY_SIGHT_ON,  # 동료 시야 면제(07-26) 여부 — **시야 물리 메타**(scan 과 같은 급).
                                           #   켠 판은 동료가 벽·문을 통과해 보이므로 obs·결정이 근본적으로
                                           #   달라진다. A/B 비교의 전제라 리플레이·판 대조 시 필수 대조 필드.
                solo=SOLO_ON,              # 솔로 판(07-29) 여부 — **판의 종류가 다른 메타**. 배치(흩어짐)·
                                           #   obs(party 명단 부재)·승리 조건(혼자 하강)이 전부 달라지므로
                                           #   파티 판과는 애초에 비교 대상이 아니다. 대조군 고를 때 필수 필드.
                graves=GRAVES_ON,          # 묘(D22) 여부 — 피처가 늘어나는 세계 물리 메타
                events=EVENTS_ON,          # 사건층(D22) 여부 — obs(목격·기억)를 바꾸는 실행모드 메타
                status=STATUS_ON,          # 상태 태그(D34) 여부 — 몸 물리(걸음·굴림)와 obs 를 바꾸는 메타
                rest=REST_ON,              # 휴식(D35) 여부 — 메뉴·회복 물리 메타(wait 와 같은 급)
                relations=RELATIONS_ON,    # 관계 장부(D36) 여부 — obs(뼈·초대)와 시트(살)를 바꾸는 메타
                trail=TRAIL_ON,            # 자기 행동 궤적(D38) 여부 — obs(trail·intent turn)를 바꾸는 표현층 메타
                objtags=OBJTAGS_ON,        # 오브젝트 태그(D39) 여부 — obs(sights.features[].tag)·라벨을 바꾸는 표현층 메타
                floor=FLOOR_ON,            # 층 집계·결산(D40 ②) 여부 — obs(floor·floors)·decisions.floor_line 표현층 메타
                explore_dirs=EXPLORE_DIRS_ON,   # 방향 탐색 열거(D19 개정 4) 여부 — 메뉴(options)를 바꾸는 표현층 메타(rest 와 같은 급)
                sayto=SAYTO_ON,            # 지목(D41) 여부 — 말 걸림 정지·대화 뼈가 `to` 지목만 세는 사회층 물리 메타
                                           #   (정지 물리를 바꾸므로 리플레이·판 비교의 전제 — hail 과 같은 급)
                say_kind=SAYKIND_ON,       # 말의 종류(D47) 여부 — 정지는 제안만·회의·반복 방지·반응 뼈(정지 물리 메타, sayto 와 같은 급)
                pending=PENDING_ON,        # 들은 말 보관(D47 배관) 여부 — inbox 에 보관된 옛 말(turn 스탬프)이 섞이는 표현층 메타
                give=GIVE_ON,              # 건네기(D47 ②, 09-09) 여부 — 메뉴(options give)·소지품 이동 물리 메타(rest 와 같은 급)
                bond=BOND_ON,              # 친목(D47 ②) 여부 — 메뉴(options bond)·관계 뼈·tick.replies 를 바꾸는 사회층 메타
                town_buildings=TOWN_BUILDINGS_ON,   # 마을 관측(D60, 09-12) 여부 — 마을 level.features 에 building 피처·obs.town_zone 표현층 메타
                notices=NOTICES_ON,        # 건물 역할 부품(D61, 09-12) 여부 — obs.notices(게시판·신의 요청)·decisions.oracle_reply 표현층 메타
                quests=quests is not None, # D69(09-14 additive) 길드 척추 여부 — 의뢰 맡기(use q<n>)·완료 판정·워프 귀환 뒤 마을 계속·보고=종료.
                                           #   판 모양(종료 조건)을 바꾸는 실행모드 메타(boss 급)
                town_apart=bool(TOWN_ON and TOWN_APART_ON),   # D69 additive 흩어진 출발(마을 판만) — 배치 메타(solo 급)
                town_guide=bool(TOWN_ON and TOWN_GUIDE_ON),   # D81 additive 마을 안내(마을 판만) — 시작 마을의 첫 관측에 장소·동료 위치 문단이 한 번 실린다는 표현층 메타
                town_hear=(TOWN_HEAR if TOWN_HEAR == "zone" else "all"),   # D70 additive 마을 사람 지각 — 'zone'(같은 구역·곁)|'all'(옛 전체). 배달·가시·목격 물리 메타(ally_sight 급)
                npc_brain=bool(npc_brain), # D69 additive 마을 NPC 두뇌 여부 — 이벤트 line 이 LLM 문장(line_src 'brain')일 수 있다는 표현층 메타
                npc_hail_stop=bool(NPC_HAIL_ON and NPC_HAIL_STOP_ON),   # D76 additive NPC 인사에 걸음을 멈추는 판(0콜)
                npc_hail=bool(NPC_HAIL_ON),   # D71 additive NPC 가 먼저 거는 인사 여부 — tick.npc_hails·inbox 'npc:' 잡담(마을만). 표현층 메타(콜 0)
                town_walkers=bool(TOWN_ON and TOWN_WALKERS_ON),   # D73 additive 마을 행인 여부 — level/tick features 의 npc 가 걷는다(walker 표식). 배치 메타
                obs_ascii=brains.OBS_ASCII,   # wire 직렬화 스위치(D17-4) — LLM 프롬프트 표현 메타
                obs_pos=brains.OBS_POS,       #   (obs dict 는 불변 — 판독·재현 시 어느 wire 였는지 식별용)
                notes=brains.NOTES_ON,        # D26 의미 기억(남길 한 줄) 여부 — 표현층 메타(menu 와 같은 급)
                history=brains.HISTORY_ON,    # D38 개정 2 최근 판단 장부 여부 — 표현층 메타(notes 와 같은 급)
                dialogue=brains.DIALOGUE_ON,  # D43 대화 기억 여부 — 표현층 메타(notes 와 같은 급)
                notebook=brains.NOTEBOOK_ON,  # D59 수첩 여부 — 층 전이 descend/ascend.pages·floors[].page·notes 층에서 닫힘
                prompt_context=brains.PROMPT_CONTEXT_ON,   # D54(09-12 additive) 판단 요청 맨 앞 맥락 한 줄 여부 — 같은 급
                block_degrade=brains.BLOCK_DEGRADE_ON,     # D62(09-13 additive) 안전 차단 때 몸짓 서술 줄만 접고 재요청(지문 고정) 여부 — 같은 급
                backend=brains.backend_name(),   # 두뇌 백엔드(2026-07-25 additive) — claude_cli/
                                           #   anthropic_api/gemini_api/dummy. gm·menu 와 같은 급의
                                           #   실행모드 메타: 같은 시드라도 백엔드가 다르면 다른 판이다
                                           #   (모델 접점이 다르다 = A/B 비교의 전제).
                                           #   ⚠️ 지연·토큰·요청id 는 여기 넣지 않는다 — 실행마다 변하면
                                           #   verify_stream 결정론(라인 바이트 동일)이 즉시 깨진다.
                bestiary=iss.snapshot(),   # 판 시작 시점 지식(additive) — 도감이 obs 를 바꾸므로 리플레이·비교의 전제
                bestiary_progress=iss.progress(),   # D53(09-12 additive): 시작 진행도 {이름:{종키:{n, deep?}}} — 심층 해금
                                           #   시점이 obs 를 바꾸므로 이것도 전제. 오프라인 소급(bestiary.replay)의 시드
                boss=BOSS_ON,              # D65(09-13 additive): 보스층·워프게이트 여부 — 최심층 판 모양(보스·봉인 출구·귀환 종료)을 바꾸는 실행모드 메타(town 급)
                bestiary_defs=lore,        # D63(09-13 additive): 지식 본문 정의 {종키:{name, lore, brief?, unlock?, review?}} — 도감·수첩 창이
                                           #   캐릭터 상태(모름·등재·심층)만큼 본문을 보여 주는 데 쓴다. 판정 무접촉·정의가 뒤에 바뀌어도 그 판이 알던 본문
                brain_failure_policy=run_control.POLICY,
                bestiary_file=bool(BESTIARY_FILE),   # 영속 여부(실행모드 메타 — gm/menu 와 같은 급)
                party=[{**G.SK.snapshot(b), **{k: b[k] for k in ("char", "job", "sex", "maxhp", "str", "dex",
                                             "wdmg", "stealth", "search_r", "persona")},
                        **({"name": b["name"]} if b.get("name") else {}),   # additive: 보고서·웹의 호칭
                        **({"id": b["id"]} if b.get("id") else {}),         # D78(09-16) additive: 저장 캐릭터 id — 캠페인·원장 키
                        **{k: b[k] for k in ("speech", "goal", "background")   # D31(09-05) additive —
                           if b.get(k)},                                       #   커스텀 시트 원문(있을 때만)
                        **({"traits": list(b["traits"])} if b.get("traits") else {}),   # 키워드 원본
                        **({"look": b["look"]} if b.get("look") else {})}   # D37(09-06) 외형 — 뷰어 전용
                       for b in bots])
        lvl = {"turn": 0, **d.level_snapshot(),
               **({'reaction_stats': reaction_book.snapshot()} if reaction_book is not None else {}),
               "party": [G.bot_snapshot(b) for b in bots]}
        sw.emit("level", **lvl)
        iss.consume("level", lvl)          # 발급기도 같은 원장을 본다 — 층의 몹 id→종 지도 구축
    else:                                  # D79 이어가기 — 같은 기록 파일에 resume 줄(additive)을 붙이고 몸에 요약을 쥐여 준다
        reaction_book = snap["reaction_book"]
        run_started = snap["started"]
        segment = int(snap.get("segment") or 0) + 1
        stop_info = (snap_meta or {}).get("stop") or snap.get("stop") or {}
        pages_prev = dict(stop_info.get("pages") or {})
        for b in bots:                     # 요약을 들고 간다: 멈추기 전에 쓴 수첩 장은 '기억해두기로 한 것'에, 이어간다는 사실은 첫 관측에 한 번
            pg = pages_prev.get(b["char"])
            if pg:
                ns = b.setdefault("notes", [])
                ns.append(pg)
                del ns[:-brains.NOTE_MAX]
            b["floor_notice"] = RESUME_NOTICE % (brains._floor_name(d.depth), int(snap["next_turn"]) - 1,
                                                RESUME_NOTICE_PAGE if pg else "")
        sw.emit("resume", turn=int(snap["next_turn"]) - 1, started=time.strftime("%Y-%m-%dT%H:%M:%S"), segment=segment,
                backend=brains.backend_name(), depth=d.depth,
                stopped=(stop_info.get("reason") or None),          # 앞 조각이 어떻게 끝났나: user(수첩 쓰고 멈춤)·user_paused(판단 정지 중 멈춤)·pause_timeout(F1 판단 정지 제한 시간)·unwatched(D91 관전자 없는 판 — 공개 서버)·None(끊김·크래시)
                **({"pages": pages_prev} if pages_prev else {}),   # 멈출 때 쓴 수첩 장(캐릭터별) — 이어가는 몸이 들고 간다
                party=[{"char": b["char"], "hp": b["hp"], "alive": b["alive"]} for b in bots])
    run_id = "%s@%s" % (DUNGEON_SEED, run_started)   # 캠페인(D78)의 판 식별자 — 이어가도 같은 판

    gmtag = "Sonnet GM" if GM_ON else "GM 없음"
    roster = "·".join((b.get("name") or b["job"]) for b in bots)
    event("=== TRPG 던전 시작 (%s / Haiku 두뇌 / %s / 구독 과금 0)  %dx%d  지하%d층  몬스터%d 함정%d 매복%d  seed=%d ==="
          % (roster, gmtag, DUNGEON_W, DUNGEON_H, DEPTHS, N_MON, N_TRAP, N_LURK, DUNGEON_SEED))
    if START_BOSS:                          # D67 프리셋 — 관전·로그에 시작 조건을 남긴다
        event("=== 프리셋(D67): 최심층 지하 %d층 보스룸 앞에서 시작 — 보스와 봉인된 워프게이트가 문 너머에 있다 ===" % d.depth)
    if snap is not None:
        event("=== 원정을 이어간다 — 지난번 t%d(%s)에서 멈춘 몸 그대로 (이어가기 %d번째%s) ==="
              % (int(snap["next_turn"]) - 1, brains._floor_name(d.depth), segment,
                 ", 수첩 %d장 들고" % len(pages_prev) if pages_prev else ""))
    inbox = {b["char"]: [] for b in bots}   # 봇별 받은편지함 (동료가 지난 턴 한 say).
                                            # 빈 dict 아닌 전 봇 키 — 스트림 tick.inbox 형태 고정(소비자 인덱싱)
    pending = {b["char"]: [] for b in bots}   # D47 배관 — 걷는 동안 들린 말의 보관함(결정 때 함께 읽힘)
    open_props = {}                         # D47 제안 장부 {받은 봇: {한 봇: turn}} — 상대의 다음 결정까지 열려 있다
    open_acts = {}                          # D47 ② 친목·건네기 장부 {받은 봇: {한 봇: 종류}} — 반응은 상대의 다음 결정에서 형태로
    if snap is not None:                    # D79: 편지함·보관함·장부도 얼린 그대로
        inbox, pending = snap["inbox"], snap["pending"]
        open_props, open_acts = snap["open_props"], snap["open_acts"]
    write_map(d, bots, 0)
    time.sleep(1.0)

    turn = 0
    says = {}
    first_turn = int(snap["next_turn"]) if snap is not None else 1   # D79: 이어가기는 멈춘 다음 틱부터(틱 번호 연속 — 같은 판)
    segment = segment if snap is not None else 0
    stopped_now = None                       # D79 곱게 멈춤이 이 판을 닫았나(루프 뒤 end 를 쓰지 않는다 — 끊긴 판 = 이어갈 판)

    def _snap_core():                        # D79 스냅샷 몸 — 루프 머리의 지역 상태 전부(같은 객체 그래프로 한 번에 피클: known·quests·reaction_book 공유 보존)
        return {"run_id": run_id, "seed": DUNGEON_SEED, "started": run_started, "max_turns": MAX_TURNS, "world": _world_fingerprint(),
                "sheets": sheets, "d": d, "bots": bots, "saved": saved, "fallen": fallen, "inbox": inbox, "pending": pending,
                "open_props": open_props, "open_acts": open_acts, "quests": quests, "iss": iss, "rs": rs,
                "reaction_book": reaction_book, "last_oracle_id": last_oracle_id, "returned": returned,
                "returned_party": returned_party, "segment": segment,
                **({"worlds": worlds, "parties": parties, "side_pos": side.tell()} if PARTYFORM_ON else {})}   # D84: 켠 판에만(옛 스냅샷과 같은 열쇠)

    def _snap_meta(next_turn, stop=None):    # 론처가 읽는 요약(json) — 피클을 열지 않고도 '지하 3층 t158 에서 멈춤'을 안다
        return {"run_id": run_id, "seed": DUNGEON_SEED, "started": run_started, "next_turn": next_turn, "turn_last": next_turn - 1,
                "depth": d.depth, "segment": segment, "backend": brains.backend_name(),
                "party": [{"char": b["char"], "name": b.get("name") or b["job"], "id": b.get("id"), "job": b["job"],
                           "hp": b["hp"], "alive": b["alive"]} for b in _everyone()],
                "fallen": list(fallen), "stop": stop}

    # ── D84 조각 2(09-19): 세계 = 틱 몸통이 도는 단위(층 하나와 거기 있는 사람들·편지함·장부) ──
    # 옛 판은 세계가 하나다(W — 층을 옮기면 그 내용이 통째로 바뀐다). 파티 결성 판(PARTYFORM_ON)은 사람이 있는 세계마다 한 번씩 돈다.
    # main 의 d·bots·inbox… 는 '본 스트림이 좇는 세계(W)'의 거울 — 틱마다 맨 끝에서 다시 맞춘다(스냅샷·판 끝 집계가 읽는다).
    W = {"d": d, "bots": bots, "inbox": inbox, "pending": pending, "open_props": open_props, "open_acts": open_acts}
    worlds, side = [W], None
    if PARTYFORM_ON:
        if snap is not None and snap.get("worlds"):   # 이어가기 — 세계 목록도 얼린 그대로(같은 피클 그래프라 d·bots 가 같은 객체)
            worlds = snap["worlds"]
            W = next(x for x in worlds if x["d"] is d)
        else:
            W["iss"] = {"depth": iss.depth, "_idkind": iss._idkind, "_aware": iss._aware}
        side = stream.StreamWriter(os.path.join(STATE, "stream_side.jsonl"), append=snap is not None)   # 본 스트림 밖 세계의 기록(관전·캠페인 무접촉)

    def _iss(w, kind, rec):                  # 도감 발급기는 세계 하나(층의 몹 id→종 지도·인지 집합)를 가정한다 — 세계마다 제 것을 끼웠다 뺀다
        if not PARTYFORM_ON:
            return iss.consume(kind, rec)
        st = w.setdefault("iss", {"depth": w["d"].depth, "_idkind": {}, "_aware": {}})
        iss.depth, iss._idkind, iss._aware = st["depth"], st["_idkind"], st["_aware"]
        out = iss.consume(kind, rec)
        st.update(depth=iss.depth, _idkind=iss._idkind, _aware=iss._aware)
        return out

    def _everyone():                         # 판에 있는 사람 전부 — 옛 판은 이 층의 사람들 그대로
        return sorted((b for x in worlds for b in x["bots"]), key=lambda b: b["char"]) if PARTYFORM_ON else bots

    def _focus():                            # 본 스트림이 좇는 사람 = 내 캐릭터(첫 번호) — 쓰러졌으면 살아 있는 가장 앞 번호
        live = sorted(b["char"] for x in worlds for b in x["bots"] if b["alive"])
        return live[0] if live else chars[0]

    def _tick_world(w, turn):
        """한 세계의 한 틱(판단 → 행동 → 몹 → 말 배달 → 기록). 돌려주는 값: None | "break"(판을 닫는다).
        몸통은 옛 틱 루프 그대로 — 세계의 지역 상태를 머리에서 풀고 나갈 때 되담는다."""
        nonlocal last_oracle_id, returned, returned_party, stopped_now
        d, bots, inbox, pending, open_props, open_acts = (w[k] for k in _WK)
        show = w is W                        # 본 스트림·지도·관전 속도는 좇는 세계만(옛 판은 늘 참)
        if PARTYFORM_ON:                     # D84 조각 3: 다른 층에 가 있는 산 사람들 — 명단(obs.party)이 '여기 없다 — 어디에 있다'를 말한다
            d.elsewhere = [{"char": b["char"], "job": b["job"], "depth": x["d"].depth}
                           for x in worlds if x is not w for b in x["bots"] if b["alive"]]
        d.turn = turn       # 장부(D17) 목격 스탬프 — 판정 무관여, "언제 봤나"의 단일 원천
        if PENDING_ON:                        # D47 배관: 걷는 동안 들은(안 세운) 말을 이번 결정에 함께 읽힌다
            inbox = merge_inbox(pending, inbox)
        npc_hails = []                        # D71 NPC 가 먼저 거는 인사 — 같은 구역·6칸 안, 캐릭터당 NPC 당 한 번, 잡담 · D76 걸음을 멈춘다(NPC_HAIL_STOP_ON)
        if NPC_HAIL_ON and getattr(d, "town", False):
            for nm_, ch_, line_, hx_, hy_, key_ in d.npc_greetings(bots):
                src_ = None
                if npc_brain and NPC_HAIL_BRAIN_ON:   # 옵션: 인사도 LLM 이(인사당 1콜) — 기본은 정의의 문장(0콜)
                    b_ = next((x for x in bots if x["char"] == ch_), None)
                    line2 = brains.npc_reply(b_, {"result": "npc_hail", "npc": nm_, "line": line_, "key": key_}, None,
                                             npc_facts(d, nm_, bots, fallen, quests), npc=(getattr(d, "npc_defs", None) or {}).get(nm_)) if b_ else None
                    if line2:
                        line_, src_ = line2, "brain"
                inbox.setdefault(ch_, []).append({"from": "npc:" + nm_, "text": line_, "turn": turn, "to": ch_})
                stopped_ = False
                if NPC_HAIL_STOP_ON:                  # D76(09-15): 걷던·기다리던 몸을 세워 이 틱에 결정권을 준다(order 없으면 이미 결정 차례)
                    b2_ = next((x for x in bots if x["char"] == ch_), None)
                    stopped_ = bool(b2_ is not None and d.npc_hail_stop(b2_, nm_))
                npc_hails.append({"npc": nm_, "char": ch_, "line": line_, "key": key_, **({"line_src": src_} if src_ else {}),
                                  **({"stopped": True} if stopped_ else {})})   # stopped=D76 additive
                event('   %s → 봇%s \U0001f4ac "%s"%s' % (nm_, ch_, line_, " — 걸음을 멈췄다" if stopped_ else ""))
        inbox_in = inbox    # 이번 틱 사고에 주입된 받은편지함 — 루프 끝에서 이름이 새 dict 로
                            # 재바인딩되므로(덮어씀) think_all 직전 참조를 잡아 스트림에 남긴다
        # order 없는 봇만 사고(자동보행 중인 봇은 LLM 0콜)
        d.oracle = read_oracle() if NOTICES_ON else None   # D61 개정(09-13 파트너 "플레이 중에 신탁을 내릴 수 있게"): 어느 층에서나 틱마다 읽는다
        oracle_now = (d.oracle or {}).get("id") if d.oracle and d.oracle.get("text") else None
        oracle_new = None
        if oracle_now != last_oracle_id:                # 새 요청(또는 거둠) — 관전·스트림에 남긴다(요청 본문은 판 밖 원천이라 여기서만 보인다)
            if oracle_now:
                oracle_new = {"id": oracle_now, "text": d.oracle["text"]}
                event("🔮 신의 요청이 들려온다(전원에게): 「%s」" % d.oracle["text"])
            elif last_oracle_id:
                event("🔮 신의 요청이 거두어졌다")
            last_oracle_id = oracle_now
        try:
            decisions = brains.think_all(d, bots, inbox, on_error=lambda errors: brain_pause.wait(turn, errors))
        except run_control.StopRequested as stop_exc:   # D79: 판단 정지 대기 중 사용자가 멈춤 — 루프 머리 스냅샷(이 틱 전)이 진실. 조용히 닫는다
            # F1(09-18): 제한 시간(PAUSE_LIMIT_SEC) 동안 아무도 재시도를 안 누른 판도 같은 길로 스스로 닫는다 — 사유만 다르다
            # D91(09-20): 판단 정지 중에 온 멈춤 요청이 사유를 들고 있으면(unwatched = 관전자 없는 판) 그 사유를 그대로 적는다
            stopped_now = ("pause_timeout" if isinstance(stop_exc, run_control.PauseTimeout)
                           else run_control.stop_reason(run_control.stop_requested(STATE), "user_paused"))
            snapshot.write_meta(STATE, _snap_meta(turn, {"reason": stopped_now, "pages": {}}))
            if stopped_now == "pause_timeout":
                event("=== 판단 정지가 제한 시간(%d초)을 넘겨 원정을 멈춘다(t%d 전) — 마지막 기록에서 이어갈 수 있다 ===" % (PAUSE_LIMIT_SEC, turn))
            else:
                event("=== 판단 정지 중에 원정을 멈춘다(t%d 전) — 마지막 기록에서 이어갈 수 있다 ===" % turn)
            w.update(d=d, bots=bots, inbox=inbox, pending=pending, open_props=open_props, open_acts=open_acts)
            return "break"
        brain_pause.resolved(turn)
        for c_, dec_ in (decisions or {}).items():   # D61 신탁 응답 — 캐릭터 장부(요청 id 별 한 번)·events.log. 판정 없음
            orp = dec_.get("oracle_reply") if isinstance(dec_, dict) else None
            if orp and orp.get("id"):
                b_ = next((x for x in bots if x["char"] == c_), None)
                if b_ is not None:
                    b_.setdefault("oracle_replies", {})[orp["id"]] = orp["text"]
                    event("🔮 %s: 신의 요청에 답했다 — 「%s」" % (b_.get("name") or ("봇%s" % c_), orp["text"]))
        # 사교 콜(채널 분리) — 걷는 중에 말을 들은 봇만. 행동은 못 바꾸고 say 만 낸다.
        social = brains.social_all(d, bots, inbox)
        replies = []                          # D47 ② 반응(형태) 계측 — 제안·친목·건네기에 대한 첫 결정의 답(행동|말|없음)
        answers = settle_proposals(d, bots, open_props, decisions, replies) if (SAYKIND_ON and SAYTO_ON) else {}
                                             # D47 반응 장부: 제안 받은 봇의 첫 결정에서 닫힌다(답했으면 뼈)
        settle_acts(d, bots, open_acts, decisions, replies)   # D47 ② 친목·건네기의 반응 — 같은 결정에서 같은 자로
        if PENDING_ON:
            pending = keep_pending(inbox, decisions)   # 읽은 봇은 비우고, 걷던 봇은 보관(D47 배관)
        for b in bots:
            b.pop("hailed", None)            # 표시 소비 — 한 번 들은 말로 두 번 열리지 않는다
        thinkers = "·".join(sorted(decisions)) if decisions else "-"
        event("-- tick %d --  (사고:%s / 나머지 자동보행)%s" % (turn, thinkers, ("  [%s]" % brains._floor_name(d.depth)) if PARTYFORM_ON else ""))
        turn_events = []
        npc_says = []                        # D69 이번 틱 NPC 의 답 [(NPC 이름, 문장, 말 건 봇)] — 배달은 아래(잡담·정지 없음)
        says = dict(social)                  # 걸으면서 한 말도 같은 배달 규칙을 탄다
        say_to = {}                          # D41 지목 — 이번 틱 말의 상대(봇 번호 | all), 없으면 혼잣말
        say_kind = {}                        # D47 말의 종류 — 잡담(기본)|제안. 사교 콜의 말은 종류 없음=잡담
        for b in bots:
            if not b["alive"] or b["won"]:
                dec = decisions.get(b["char"])
                if dec is not None:          # 접수됐지만 미실행된 결정(같은 틱 동료의 exit 하강이
                    dec["skipped"] = True    # 이 봇의 won 을 선점) — say 도 발화 안 됐음을 스트림에 표시
                continue
            if b.get("order"):
                res = d.step_order(b, bots)              # 자동보행(LLM 0)
                src = "walk"
                append(botlog[b["char"]], "        ~> %s" % act_summary(res))
            else:
                dec = decisions.get(b["char"])
                if not dec:
                    continue
                res = d.act(b, dec, bots)                # 핑/공격/상호작용 판정 = 진실
                res["reason"] = dec.get("reason", "")
                src = dec.get("src", "haiku")
                if res.get("result") in ("npc_talk", "npc_gift", "npc_report") and res.get("npc"):   # D69 마을 NPC — 말을 걸었다
                    if npc_brain:                        # NPC 두뇌: 판정(선물·보고)은 끝났고 문장만 LLM 이(1콜, 실패=고정 대사)
                        npc_def = (getattr(d, "npc_defs", None) or {}).get(res["npc"]) or {}
                        line_ = brains.npc_reply(b, res, dec.get("say"), npc_facts(d, res["npc"], bots, fallen, quests), npc=npc_def)
                        if line_:
                            res["line_fixed"], res["line"], res["line_src"] = res.get("line"), line_, "brain"
                    if res.get("line"):
                        npc_says.append((res["npc"], res["line"], b["char"]))
                append(botlog[b["char"]], "[t%02d] %s" % (turn, dec.get("reason", "")))
                append(botlog[b["char"]], "        -> %s  <%s>" % (act_summary(res), src))
                dg = dec.get("brain_degraded")           # D62(09-13): 이 판단은 몸짓 서술 줄을 접고 물은 것 — 차단 뒤 재요청 | 지문 고정으로 이어서
                if dg:
                    dg_line = "몸짓 세부 접고 물음 " + ("(이어서)" if isinstance(dg, dict) and dg.get("sticky") else "(차단 뒤 다시)")   # ⚠️문구 임시(파트너 문장 대기)
                    append(botlog[b["char"]], "        ⚠ " + dg_line)
                    event("   봇%s ⚠ %s" % (b["char"], dg_line))
                if dec.get("say"):
                    says[b["char"]] = dec["say"]
                    if dec.get("to"):                     # D41 지목 — 말의 상대(봇 번호 | all)
                        say_to[b["char"]] = dec["to"]
                    if dec.get("say_kind"):               # D47 말의 종류(잡담|제안)
                        say_kind[b["char"]] = dec["say_kind"]
                    append(botlog[b["char"]], '        \U0001f4ac "%s"%s%s'
                           % (dec["say"], (" → %s" % dec["to"]) if dec.get("to") else "",
                              " [제안]" if dec.get("say_kind") == "제안" else ""))
                    event('   봇%s \U0001f4ac "%s"' % (b["char"], dec["say"]))
            if res.get("type") in ("give", "bond") and res.get("result") in ("given", "done"):
                # 접근 완료도 수신자의 다음 결정에서 반응을 기록한다. 접근 시작에는 기록하지 않는다.
                open_acts.setdefault(res["to"], {})[b["char"]] = "건네기" if res["type"] == "give" else "친목"
            res["job"] = b["job"]
            turn_events.append(res)
            mark = {"fallback": " [규칙]", "plan": " [작정]"}.get(src, "")
            event("   봇%s  %s%s" % (b["char"], act_summary(res), mark))
            if not b["alive"]:
                event("   봇%s 쓰러졌다!" % b["char"])
            if show:
                write_map(d, bots, turn)
                time.sleep(STEP_DELAY)

        if reaction_book is not None:
            for char, decision in sorted(decisions.items()):
                reaction = reaction_book.consume(char, decision, turn)
                if reaction:
                    line = '%s → %s: %s — %s [%s]' % (
                        names.get(char, char), names.get(reaction['to'], reaction['to']),
                        '좋아함' if reaction['value'] == 'like' else '싫어함',
                        G.SR.describe(reaction['source']), reaction['reaction_to'])
                    append(botlog[char], '        반응: ' + line)
                    event('   반응: ' + line)

        # ③ 몬스터 턴 (엔진 — 독립 시계)
        mon_events = d.monster_turn(bots)
        for e in mon_events:
            event("   %s" % mon_summary(e))
            if e.get("down"):
                event("   봇%s 쓰러졌다!" % e["target"])
        if mon_events and show:
            write_map(d, bots, turn)
        turn_events += mon_events
        if TOWN_WALKERS_ON and getattr(d, "walkers", None):   # D73 마을 행인 걸음(0콜) — 사건은 npc_move, 관전은 스냅샷 좌표로 그린다
            turn_events += d.walk_npcs(bots)

        # 의논 핑퐁: say -> 동료가 *볼 수 있을 때만*(근접/시야) 다음 틱 받은편지함
        inbox, hails = deliver_and_hail(d, bots, says, say_to, say_kind, open_props)   # 사회층 한 틱(배달·뼈·정지 — D24·D36·D41·D47)
        for c in hails:
            event("   봇%s 멈칫 — %s" % (c, "제안을 받고 돌아본다" if (SAYKIND_ON and SAYTO_ON) else "말을 걸어온 동료 쪽을 돌아본다"))
        for npc_name, line_, to_c in npc_says:    # D69 NPC 의 답 — 마을의 잡담으로 들린다: 정지 없음·뼈 없음·사교 콜 없음
            nf = next((f for f in d.features.values() if f.type == "npc" and f.name == npc_name), None)
            for b in bots:                        #   (from 'npc:<이름>' — 두뇌는 이름으로 표기, 관계 장부는 봇만 센다)
                if b["alive"] and not b["won"] and (nf is None or d.hears(b, nf.x, nf.y)):   # D70: NPC 목소리도 같은 구역에서만
                    inbox.setdefault(b["char"], []).append({"from": "npc:" + npc_name, "text": line_, "turn": turn, "to": to_c})
            event('   %s \U0001f4ac "%s"' % (npc_name, line_))

        # 스트림 tick — 빈 틱 포함 매 반복(turn 연속 불변식). GM 블록 *앞*에서 emit:
        # 여기서 즉시 직렬화되므로 GM 지연·이후 dict 변경과 독립(공유 오염 방어).
        # 스냅샷은 델타 아닌 전체 — 임의 틱 시킹용. visited 만 제외(파생: 스폰+틱별 봇 좌표 누적).
        tick_rec = {"turn": turn, "inbox": inbox_in, "decisions": decisions,
                    **({'skill_events': G.SK.stream_records(turn_events)} if SKILLS_ON else {}),
                    **(reaction_book.drain() if reaction_book is not None else {}),
                    **({"hails": hails} if hails else {}),   # 말 걸림 정지 성사(D24) — additive 계측
                    **({"answers": answers} if answers else {}),   # 제안 반응(D47) {받은 봇: {한 봇: 답함 여부}} — additive 계측
                    **({"replies": replies} if replies else {}),   # 반응 형태(D47 ②) [{from,to,kind,how}] — additive 계측
                    **({"oracle": oracle_new} if oracle_new else {}),   # D61 개정(09-13 additive) 이 틱에 새로 들린 신의 요청 {id,text}
                    **({"npc_hails": npc_hails} if npc_hails else {}),  # D71(09-14 additive) 이 틱에 NPC 가 먼저 건 인사 [{npc,char,line,key,line_src?}]
                    "events": turn_events,
                    "bots": [G.bot_snapshot(b) for b in bots],
                    "monsters": [m.as_dict() for m in d.monsters],
                    "features": [f.as_dict() for f in d.features.values()],
                    "traps": [t.as_dict() for t in d.traps]}
        if show:
            sw.emit("tick", **tick_rec)
        else:                                 # D84: 좇지 않는 세계의 틱은 옆 파일에(world = 그 층)
            side.emit("tick", world=d.depth, **tick_rec)

        # 도감 획득(D9) — 스트림의 결정론 투영(LLM 0콜). 등재 즉시 봇 known(공유 set)에 반영.
        new_knowledge = _iss(w, "tick", tick_rec)
        for nm, key, tier in new_knowledge:
            if tier == 'deep':                  # D53 심층 해금 — 다음 obs 부터 본문 전체
                event('   \U0001f4d6 %s — 도감 심층 해금: %s' % (nm, bestiary.label(key, lore)))
            elif tier == 'invite':              # D55 인식 초대 대기 — 다음 실 결정의 프롬프트에 "## 도감" 절
                event('   \U0001f4d6 %s — 도감 생각 한 줄 초대: %s' % (nm, bestiary.label(key, lore)))
            elif tier == 'note':                # D55 캐릭터가 남긴 인식(원장 note — 내용은 기계가 안 읽는다)
                rec_ = (iss.record(nm).get(key) or {}).get('note') or {}
                event('   \U0001f4d6 %s — %s에 대한 생각: "%s"' % (nm, bestiary.label(key, lore), rec_.get('text', '')))
            else:
                event('   \U0001f4d6 %s — 도감 등재: %s' % (nm, bestiary.label(key, lore)))
        if iss.dirty and BESTIARY_FILE:         # 조우 수만 올라도 저장(원장의 n 이 스트림 투영과 어긋나지 않게)
            iss.save(BESTIARY_FILE)

        # ④ GM 진행자(옵션 소비자): 이번 틱 events를 장면으로 연출.
        #    party 도 스트림 스냅샷의 projection — GM 이 별도 진실 조립을 갖지 않는다(이중화 제거).
        #    name 만 시트에서 보강(스냅샷엔 없음 — 호칭용).
        if GM_ON and turn_events and show:
            party = [{**{k: s[k] for k in ("char", "job", "hp", "maxhp", "bag", "alive", "won")},
                      "name": sheets[s["char"]].get("name")}
                     for s in tick_rec["bots"]]
            try:                                  # 밀린(아직 안 집은) 턴은 버린다 — 최신-우선
                while True:
                    gm_q.get_nowait()
            except queue.Empty:
                pass
            gm_q.put((turn, turn_events, party))  # 비동기 — 루프는 즉시 다음 틱으로

        if quests is not None and any(e.get("result") == "npc_report" for e in turn_events):   # D69 길드 보고 = 원정의 끝
            rep = next(e for e in turn_events if e.get("result") == "npc_report")
            returned, returned_party = True, [b["char"] for b in bots if b["alive"]]
            tt = rep.get("titles") or {}
            event("=== 길드에 보고했다 — 완수 %s / 미완 %s — 원정 완료 ==="
                  % ("·".join(tt.get(x, x) for x in (rep.get("done") or [])) or "없음",
                     "·".join(tt.get(x, x) for x in (rep.get("undone") or [])) or "없음"))
            w.update(d=d, bots=bots, inbox=inbox, pending=pending, open_props=open_props, open_acts=open_acts)
            return "break"
        w.update(d=d, bots=bots, inbox=inbox, pending=pending, open_props=open_props, open_acts=open_acts)
        return None

    def _shift_world(w, turn):
        """층 전이 — 계단을 쓴 사람들을 간 곳의 세계로 옮긴다. 돌려주는 값: None | "break"(판을 닫는다).
        옛 판(세계 하나): 전원이 떠났을 때만, 이 세계의 내용이 간 곳으로 통째로 바뀐다(몸통은 옛 전이 그대로).
        파티 결성 판(D84): 계단을 쓴 무리만 옮긴다 — 남은 사람의 세계는 그대로 흐르고, 간 층에 사람이 있으면 그 세계에 합류한다."""
        nonlocal fallen, returned, returned_party, W
        d, bots, inbox, pending, open_props, open_acts = (w[k] for k in _WK)
        if all(b["won"] or not b["alive"] for b in bots) or (PARTYFORM_ON and any(b["won"] for b in bots)):
            survivors = [b for b in bots if b["won"]]
            if PARTYFORM_ON and survivors:    # 한 번에 한 무리(같은 길을 고른 사람들) — 같은 틱에 길이 갈린 나머지는 다음 틱에 옮긴다
                way = (bool(survivors[0].get("warp")), survivors[0].get("went"))
                survivors = [b for b in survivors if (bool(b.get("warp")), b.get("went")) == way]
            fallen += [b["char"] for b in bots if not b["alive"] and b["char"] not in fallen]
            warp = bool(survivors) and all(b.get("warp") for b in survivors)   # D65 워프게이트 — 최심층에서 바로 마을(0층)로
            up = bool(survivors) and all(b.get("went") == "up" for b in survivors) and (TOWN_ON or warp)
            # 행선 혼합(위/아래)은 여기 못 온다 — 파티는 모임 규칙이 한 계단을 강제하고,
            # 솔로+마을은 main() 초입에서 거부(v0 — 서랍: 다중 층 동시 진행).
            if not survivors or (not up and d.depth >= DEPTHS):
                if PARTYFORM_ON and not survivors and any(b["alive"] for x in worlds if x is not w for b in x["bots"]):
                    worlds[:] = [x for x in worlds if x is not w]   # D84: 이 세계엔 산 사람이 없다 — 다른 세계는 계속 흐른다
                    return None
                if PARTYFORM_ON:
                    W = w                 # 판을 닫는 세계를 끝 기록이 비춘다(좇던 세계가 아니어도)
                return "break"            # 전멸 or 최심층 하강 = 탈출(기존)/관측 클리어(마을 판)
            # ── 층 전이: 하강(기존 Stage 4) + 마을 왕복(D29 — 보존된 층은 그대로 복원) ──
            keep_mem = ((saved.get(d.depth) or {}).get("mem") or {}) if PARTYFORM_ON else {}   # D84: 먼저 떠난 사람의 그 층 기억도 남긴다
            if TOWN_ON:                   # 떠나는 층을 봇별 층-로컬 기억과 함께 보존("같은 1층")
                saved[d.depth] = {"d": d, "mem": {**keep_mem, **{
                    b["char"]: {"seen_keys": b.get("seen_keys"),
                                "searched": b.get("searched"),
                                "aware_of": b.get("aware_of"),
                                "ledger": b.get("ledger")}
                    for b in survivors}}}
            frozen = ({b["char"]: G.floor_freeze(b, d.depth, turn) for b in survivors}   # D40 ② 결산: 떠나는
                      if FLOOR_ON else {})                                            #   층의 집계를 얼린다
            pages = {}
            if FLOOR_ON and brains.NOTEBOOK_ON:       # D59 수첩: 층을 떠나는 순간 캐릭터당 1콜(재시도 0 — 실패면 뼈만)
                for b in sorted(survivors, key=lambda b: b["char"]):
                    fl = frozen[b["char"]]
                    page = brains.notebook_page(b, fl[-1], names, bots, up=up)
                    if page:
                        fl[-1]["page"], fl[-1]["invite"] = page, False   # 한 장이 있으면 한 줄 초대는 접는다
                        pages[b["char"]] = page
                        event('   \U0001f4d3 %s — 수첩 한 장: "%s"' % (names[b["char"]], page))
                    else:
                        event('   \U0001f4d3 %s — 수첩 없음(두뇌 응답 없음) — 뼈만 남긴다' % names[b["char"]])
            nd = 0 if warp else (d.depth - 1 if up else d.depth + 1)   # D65: 워프게이트는 층을 건너뛰어 마을로
            follow = (not PARTYFORM_ON) or any(b["char"] == _focus() for b in survivors)   # D84: 본 스트림이 좇는 사람이 옮기나(옛 판은 늘 참)
            out = sw if follow else side                      #   좇는 사람이 옮기면 본 스트림에 지금과 같은 모양으로, 아니면 옆 파일에
            out.emit("ascend" if up else "descend", turn=turn, to_depth=nd,
                    **({'gate': True} if warp else {}),       # D65 additive — 워프게이트로 귀환한 상행
                    **({'pages': pages} if pages else {}),    # D59 additive — 캐릭터별 수첩 한 장(플레이 데이터)
                    **({'reaction_summary': reaction_book.close_floor(turn)} if (reaction_book is not None and follow) else {}),
                    party=[{"char": b["char"], "hp": b["hp"], "bag": b["bag"],
                            "potions": b.get("potions", 0), **({"boons": b["boons"]} if b.get("boons") else {})}   # boons=D74 additive
                           for b in sorted(survivors, key=lambda b: b["char"])],
                    fallen=list(fallen),
                    **({} if follow else {"world": d.depth}))
            if not follow and w is W:                         # D84 additive: 좇는 세계에서 다른 사람들이 떠났다(다음 틱부터 tick.bots 에 없다)
                sw.emit("depart", turn=turn, to_depth=nd, dir=("up" if up else "down"),
                        party=sorted(b["char"] for b in survivors))
            src_depth = d.depth
            mem = {}
            if nd in saved:               # 가 본 층(마을 판) = 세계 상태 그대로(몹·주운 것·묘·헌 장비)
                d = saved[nd]["d"]
                mem = saved[nd]["mem"]
                fresh = False
            elif nd == 0:                 # D65: 마을 시작이 아닌 판의 워프 귀환 — 마을(D52 v1)을 새로 짓는다
                d, _tstarts = town_for_run(False, quests, TOWN_WALKERS_ON)   # D69 장부를 건다(보고를 받을 접수원이 있는 마을) — 도착은 입구 곁이라 apart 없음
                d.lore = lore
                fresh = False
            else:
                d = G.Dungeon(w=DUNGEON_W, h=DUNGEON_H, seed=DUNGEON_SEED, depth=nd,
                              n_monsters=N_MON + nd - 1, n_traps=N_TRAP, n_lurkers=N_LURK,
                              scan=SCAN_ON, n_potions=N_POTION, loops=LOOPS_ON, selfstop=SELF_ON,
                              graves=GRAVES_ON, events=EVENTS_ON, dry_signal=DRY_ON, hail=HAIL_ON,
                              wait_verb=WAIT_ON, motion=MOTION_ON, ally_doing=ALLY_DOING_ON,
                              ally_sight=ALLY_SIGHT_ON, social=SOCIAL_ON, solo=SOLO_ON,
                              n_gear=N_GEAR, status=STATUS_ON, rest_verb=REST_ON,
                              relations=RELATIONS_ON, trail=TRAIL_ON, objtags=OBJTAGS_ON, floor=FLOOR_ON, explore_dirs=EXPLORE_DIRS_ON, give_verb=GIVE_ON, bond_verb=BOND_ON,
                              auto_approach=brains.COMPOSE, composed_actions=brains.COMPOSE,
                              skills=SKILLS_ON, trpg_combat=TRPG_COMBAT_ON, random_skill=RANDOM_SKILL_ON,
                              boss=BOSS_ON and nd >= DEPTHS,   # D65: 최심층 = 보스층(보스·봉인 워프게이트·상자)
                              plan_max=G.PLAN_MAX if PLAN_ON else 0)   # D66: 작정 스위치
                d.lore = lore
                d.quests = quests         # D69 의뢰 장부 — 새 층도 같은 객체(처치·획득 판정이 여기로 센다)
                fresh = True
            d.plan_max = G.PLAN_MAX if PLAN_ON else 0    # 복원한 층·새로 지은 마을도 같은 스위치
            tw = None                     # D84: 간 층에서 지금 흐르고 있는 세계(사람이 있다) — 있으면 합류, 없으면(옛 판은 늘) 새로 연다
            if PARTYFORM_ON:
                d.parties = parties
                if nd == 0:
                    _partyform_town(d)    # 워프 귀환으로 새로 지은 마을도 같은 문장(이미 갈아 끼운 마을은 같은 글이라 무해)
                saved.setdefault(nd, {"d": d, "mem": {}})
                tw = next((x for x in worlds if x["d"] is d), None)
            there = tw["bots"] if tw else []
            # 도착 지점(D29): 계단을 지나 온 사람은 계단 곁에 선다 — 마을 복귀='던전 입구' 곁,
            # 재입장='위로 오르는 계단' 곁. 첫 하강만 기존 스폰(깊은 곳에서 눈뜸)+곁에 '<' 신설.
            anchor = None
            if (TOWN_ON or warp) and not fresh:   # D65: 워프 귀환도 던전 입구 곁에 선다
                anchor = (d.exit if up else
                          next(((f.x, f.y) for f in d.features.values()
                                if f.type == "stairs_up"), d.exit))
            spots = arrive_cells(d, *anchor, len(survivors), taken={(o["x"], o["y"]) for o in there}) if anchor else []
            nb = []
            for b in sorted(survivors, key=lambda b: b["char"]):
                n = G.spawn(d, b["char"], there + nb, sheet=sheets[b["char"]],
                            apart=SOLO_ON and not spots)                # ⚠️ sheet 필수 — 없으면
                if spots:                                 # 계단 곁 도착(BFS 순 = 결정론)
                    d.visited.discard((n["x"], n["y"]))
                    n["x"], n["y"] = spots[len(nb)]
                    d.visited.add((n["x"], n["y"]))
                n["hp"], n["bag"] = b["hp"], b["bag"]     # HP·보물 이월     외부 시트 봇('3'+)이 2층서 죽는다
                n["potions"] = b.get("potions", 0)        # 물약도 이월(07-17) — 들고 내려간다
                n["boons"] = b.get("boons", 0)            # 축복의 물약도 이월(D74, 09-15)
                n["str"], n["dex"] = b["str"], b["dex"]   # 축복으로 오른 능력치는 이 판 안에서 영구(D74) — 시트 초기값을 덮는다
                n["weapon"] = b.get("weapon")             # 장비도 이월(07-30) — 걸치고 내려간다
                n["armor"] = b.get("armor")
                d.adopt_gear(n)                           # D57: 개체 번호는 층-로컬 — 새 층의 번호를 받는다
                n["status"] = {t: dict(e) for t, e in (b.get("status") or {}).items()}   # 상태 태그(D34)
                n["bleed_steps"] = b.get("bleed_steps", 0)   #   도 이월 — 몸은 층을 넘어도 그 몸이다
                G.SK.inherit(d, b, n)
                n["relations"] = {oc: {**e, "bones": {k: dict(v) for k, v in e["bones"].items()},
                                       "queue": list(e.get("queue") or []),
                                       "acts": [dict(a) for a in (e.get("acts") or [])]}   # D47 ② 상세 기록도 이월
                                  for oc, e in (b.get("relations") or {}).items()}   # 관계 장부(D36)도 이월
                if b.get("people") is not None:
                    n["people"] = b["people"]                 # D85 인물 기록도 이월 — 사람에 대한 기억은 층을 넘어도 그대로(같은 객체)
                n["memories"] = list(b.get("memories") or [])   # 기억도 이월(D22) — 전사는 원정급
                                                          # 사건(장부=층의 기억과 대비. 구역 이름은
                                                          # 그 층의 것 — 층수 없인 모호하나 v0 수용)
                n["notes"] = ([] if brains.NOTEBOOK_ON else   # D59: 수첩이 층의 기억을 흡수 — 단기 절(한 줄들)은 층에서 닫힌다
                              list(b.get("notes") or []))     # (수첩 끔 = D26 그대로 이월)
                n["floors"] = frozen.get(b["char"], [dict(x) for x in (b.get("floors") or [])])   # 결산(D40 ②) 이월
                n["floor"] = {"since": turn, "n": {}, "w": {}}   # 새 층의 집계는 지금부터(스폰 시각이 아니라 이 틱)
                n["critical"] = bool(b.get("critical"))   # 위급 플래그(D40) — 몸은 층을 넘어도 그 몸이다
                n["known"] = iss.known(ledger_keys[b["char"]])  # 도감은 층을 넘어도 그대로(지식=영속층) · 09-19 수선: 열쇠는 시작 때와 같은
                n["book"] = iss.record(ledger_keys[b["char"]])  # D78 원장 키(id|이름) — 이름으로 묶으면 저장 캐릭터는 첫 계단에서 지식을 잃는다
                if LEDGER_ON:
                    n["ledger"] = G.new_ledger()          # 장부는 새 원장(층의 기억 — id 층-로컬, D17)
                lm = mem.get(b["char"]) or {}             # 가 본 층 = 그 층의 기억도 그대로(D29 —
                for k in ("seen_keys", "searched", "aware_of", "ledger"):   # 낯익은 곳을 낯설게
                    if lm.get(k) is not None:             # 다시 배우게 하지 않는다)
                        n[k] = lm[k]
                nb.append(n)
            if TOWN_ON and fresh and nd >= 1:             # 첫 입장 층에 '위로 오르는 계단' 신설 —
                c0 = arrive_cells(d, nb[0]["x"], nb[0]["y"], 1)   # 일행이 내려선 자리 곁(왕복의 몸)
                ux, uy = c0[0] if c0 else (nb[0]["x"], nb[0]["y"])
                d._add_feature("stairs_up", "위로 오르는 계단", ux, uy)
            d.turn = turn
            if reaction_book is not None:
                if follow:                          # D84: 반응 장부의 '지금 층'은 좇는 사람의 층(v0 — 다른 세계의 반응도 이 층 집계로 센다)
                    reaction_book.start_floor(d.depth, turn)
                d.reaction_book = reaction_book
            bots = nb
            acquired_skills = G.SK.acquire(d, bots)
            inbox = {b["char"]: [] for b in bots}   # 층 전이 = 대화 리셋(형태는 전 봇 키로 고정)
            pending = {b["char"]: [] for b in bots}   # 보관함도 리셋(D47 배관)
            open_props = {}                         # 제안 장부도 리셋(D47)
            open_acts = {}                          # 친목·건네기 장부도 리셋(D47 ②)
            if tw is not None:                      # D84: 사람이 있는 세계에 합류 — 그 세계의 편지함·장부는 그대로, 온 사람 몫만 새로
                bots = tw["bots"] + nb
                inbox = {**tw["inbox"], **{b["char"]: [] for b in nb}}
                pending = {**tw["pending"], **{b["char"]: [] for b in nb}}
                open_props, open_acts = tw["open_props"], tw["open_acts"]
            lvl = {"turn": turn, **d.level_snapshot(),            # descend/ascend 직후 level 불변식
                   **({'skill_acquisitions': acquired_skills} if acquired_skills else {}),
                   **({'reaction_stats': reaction_book.snapshot()} if reaction_book is not None else {}),
                   "party": [G.bot_snapshot(b) for b in bots]}
            qv_ = d._quest_event("reach", depth=d.depth) if (quests is not None and nd >= 1) else []   # D69 층 도달형 의뢰
            if qv_:
                lvl["quests"] = qv_                  # additive — 이 층에 들어서며 채워진 의뢰
            dest = w                                # 옛 판: 이 세계가 곧 간 곳이다(세계 하나 — 내용이 통째로 바뀐다)
            if PARTYFORM_ON:                        # D84: 떠난 세계엔 남은 사람이, 간 세계엔 온 사람이 — 둘 다 계속 흐른다
                gone = {b["char"] for b in survivors}
                stay = [b for b in w["bots"] if b["char"] not in gone]
                w.update(bots=stay, inbox={c: v for c, v in w["inbox"].items() if c not in gone},
                         pending={c: v for c, v in w["pending"].items() if c not in gone},
                         open_props={c: {c2: v for c2, v in m.items() if c2 not in gone}       # 떠난 사람이 낀 열린 제안·친목은 닫는다
                                     for c, m in w["open_props"].items() if c not in gone},
                         open_acts={c: {c2: v for c2, v in m.items() if c2 not in gone}
                                    for c, m in w["open_acts"].items() if c not in gone})
                if not any(b["alive"] for b in stay):
                    worlds[:] = [x for x in worlds if x is not w]   # 사람이 없는 세계는 멈춘다(보존은 saved 에 — 다시 오면 그대로 이어진다)
                dest = tw
                if dest is None:
                    dest = {}
                    worlds.append(dest)
            dest.update(d=d, bots=bots, inbox=inbox, pending=pending, open_props=open_props, open_acts=open_acts)
            if follow or tw is None:                # 본 스트림(좇는 사람이 옮겼다) 또는 옆 세계가 새로 열렸다 — descend/ascend 직후 level 불변식
                out.emit("level", **lvl, **({} if follow else {"world": d.depth}))
            if tw is None:
                _iss(dest, "level", lvl)            # 새 층 몹 id→종 지도 갱신
            else:                                   # 흐르던 세계 — 있던 사람의 인지 집합은 그대로, 온 사람 것만 새로(스폰 봇의 aware_of 초기화와 짝)
                for b in nb:
                    (tw.get("iss") or {}).get("_aware", {}).pop(b["char"], None)
            if PARTYFORM_ON and follow:
                W = dest                            # 본 스트림이 좇는 세계가 바뀌었다
            elif PARTYFORM_ON and tw is W:          # D84 additive: 좇는 세계에 다른 사람들이 왔다(다음 틱부터 tick.bots 에 있다)
                sw.emit("arrive", turn=turn, from_depth=src_depth, party=[G.bot_snapshot(b) for b in nb])
            for qv in qv_:
                event("   \U0001f4dc 의뢰 %s: %s (%d/%d)" % ("완수" if qv.get("done") else "진행", qv.get("title", "?"), qv.get("n", 0), qv.get("need", 0)))
            if warp:
                event("=== 워프게이트의 빛이 걷힌다 — 마을이다. 원정에서 돌아왔다 ===")   # D65
            elif up:
                event("=== 일행은 계단을 올라선다 — 마을이다. 낯익은 지붕들 ===")
            elif TOWN_ON and d.depth == 1:
                event("=== 일행은 던전 입구로 내려선다 — 지하 1층 (몬스터 %d) ===" % (N_MON,))
            else:
                event("=== 일행은 어둠 속 계단을 내려선다 — 지하 %d층 (깊을수록 흉흉하다: 몬스터 %d) ==="
                      % (nd, N_MON + nd - 1))
            if follow:
                write_map(d, bots, turn)
                time.sleep(1.0)
            if warp:                          # D65: 마을 도착 = 원정 완료 — 옛 판(의뢰 없음)은 여기서 닫는다
                if quests is not None:        # D69(09-14 파트너 "원정의 끝을 게이트가 아니라 길드 보고로"): 마을에서 이어 논다 —
                    quests["returned"] = turn  #   접수원에게 말을 걸면 보고(원정 완료). 안 하면 턴 상한으로 끝난다(세계 규칙, 캐릭터 규칙 아님)
                    d.expedition_returned = True
                    event("=== 원정에서 돌아왔다 — 길드 접수원에게 보고하면 원정이 끝난다 ===")
                else:
                    returned, returned_party = True, [b["char"] for b in survivors]
                    return "break"
        return None

    for turn in range(first_turn, MAX_TURNS + 1):
        req = run_control.stop_requested(STATE)   # D79 곱게 멈춤(론처 '수첩 쓰고 멈춤') — 이 틱을 시작하기 전에, 지난 틱까지의 기록이 진실
        if req:
            why = run_control.stop_reason(req)    # D91(09-20): 사람이 누른 멈춤 = "user" · 공개 서버가 관전자 없는 판을 멈춤 = "unwatched" — 길은 같고 사유만 다르다(기록은 누가 멈췄는지 그대로)
            pages = stop_pages(d, bots, names, turn - 1, req)
            for x in worlds:                      # D84: 다른 세계에 있는 사람도 한 장씩(옛 판은 세계가 하나라 돌지 않는다)
                if x is not W:
                    pages.update(stop_pages(x["d"], x["bots"], names, turn - 1, req))
            sw.emit("stopped", turn=turn - 1, reason=why, depth=d.depth, **({"pages": pages} if pages else {}))   # D79 additive
            stop_rec = {"reason": why, "pages": pages}
            _take_snapshot(sw, {**_snap_core(), "next_turn": turn, "stop": stop_rec}, _snap_meta(turn, stop_rec))
            event("=== 원정을 멈춘다(t%d, %s) — 마지막 기록에서 이어갈 수 있다%s%s ==="
                  % (turn - 1, brains._floor_name(d.depth), " · 수첩 %d장" % len(pages) if pages else "",
                     " · 관전자가 없어 서버가 멈췄다" if why == "unwatched" else ""))
            stopped_now = why
            break
        _take_snapshot(sw, {**_snap_core(), "next_turn": turn, "stop": None}, _snap_meta(turn))   # 틱마다 — 끊겨도 여기서 이어간다
        flag = None
        order = [W] + sorted((x for x in worlds if x is not W), key=lambda x: x["d"].depth)   # 좇는 세계 먼저, 나머지는 얕은 층부터(결정론)
        for x in order:                           # 사람이 있는 세계마다 한 번 — "마을은 마을의 시계로, 던전은 던전의 시계로"(옛 판은 세계가 하나)
            flag = _tick_world(x, turn)
            if flag:
                break
        if not flag:                              # 전이는 모든 세계의 틱이 끝난 뒤에 — 옮겨 간 사람이 같은 틱에 두 번 움직이지 않는다
            for x in order:
                if any(x is y for y in worlds):
                    flag = _shift_world(x, turn)
                    if flag:
                        break
        if PARTYFORM_ON and not flag:             # D84: 좇던 사람이 쓰러졌거나 그 세계가 비었다 — 살아 있는 가장 앞 번호의 세계로 본 스트림을 옮긴다
            fc = _focus()
            nw = next((x for x in worlds if any(b["char"] == fc and b["alive"] for b in x["bots"])), None)
            if nw is not None and nw is not W:
                W = nw
                sw.emit("level", turn=turn, **W["d"].level_snapshot(), party=[G.bot_snapshot(b) for b in W["bots"]], follow=fc)
        d, bots, inbox, pending, open_props, open_acts = (W[k] for k in _WK)   # 거울 맞추기(스냅샷·판 끝 집계가 읽는다)
        if flag:
            break

    if side is not None:
        side.close()
    if stopped_now:                                  # D79 곱게 멈춤 — end 없이 닫는다(끊긴 판 = 이어갈 판). stopped 줄·스냅샷이 남았다
        sw.close()
        if GM_ON:
            gm_q.put(None)
            gm_thread.join(timeout=gm.TIMEOUT + 10)
        write_map(d, bots, turn)
        return
    won = [b["char"] for b in _everyone() if b["won"]]            # D84: 켠 판은 모든 세계의 사람을 센다(옛 판 = 이 층의 사람들 그대로)
    dead = fallen + [b["char"] for b in _everyone() if not b["alive"] and b["char"] not in fallen]
    left = [b["char"] for b in _everyone() if b["alive"] and not b["won"]]
    if returned:                                     # D65: 보스를 잡고 워프게이트로 마을 귀환 = 원정 완료 (D69: 길드 보고까지)
        outcome = "returned"
        won = list(returned_party)
        left = []                                    # 돌아온 사람들은 '던전에 남은 자'가 아니다(D69 — 마을에서 보고하고 끝났다)
        event("=== 종료 (turn %d) — %s (원정 완료) %s / 쓰러짐 %s ==="
              % (turn, "워프게이트로 마을 귀환, 길드에 보고" if quests is not None else "보스를 쓰러뜨리고 워프게이트로 마을 귀환!!",
                 won, dead or "없음"))
    elif won and d.depth >= DEPTHS:
        outcome = "escaped"                          # 최심층 돌파 = 진짜 탈출(승리)
        if TOWN_ON:                                  # 마을 판(D29): 아래 계단 = 관측 클리어 조건
            event("=== 종료 (turn %d) — 지하 %d층의 아래 계단으로, 더 깊은 어둠 속으로!! "
                  "(클리어) %s / 쓰러짐 %s ===" % (turn, d.depth, won, dead or "없음"))
        else:
            event("=== 종료 (turn %d) — 지하 %d층 돌파·탈출!! %s / 쓰러짐 %s ==="
                  % (turn, d.depth, won, dead or "없음"))
    elif not left:                                   # 전원 사망(승자 없음)
        outcome = "wiped"
        event("=== 종료 (turn %d, 지하 %d층) — 파티 전멸... 쓰러짐 %s ==="
              % (turn, d.depth, dead or "없음"))
    else:                                            # 틱 한도 도달 — 크래시 아님을 분명히
        outcome = "timeout"
        event("=== 시간 종료 (틱 한도 %d 도달, 지하 %d층) — %s 던전에 남음 / 쓰러짐 %s ==="
              % (MAX_TURNS, d.depth, left, dead or "없음"))
        event("    (더 길게: 론처 옵션의 틱 상한 또는 DUNGEON_TURNS=400 scripts/start.sh)")
    if reaction_book is not None:
        reaction_book.close_floor(turn)
    summary = rs.result(outcome=outcome, depth=d.depth, survivors=won, fallen=dead)   # D58: end 직전까지의 모든 레코드
    sw.emit("end", turn=turn, outcome=outcome, depth=d.depth,
            **({'reaction_summary': reaction_book.summary(), 'reaction_floors': reaction_book.floors}
               if reaction_book is not None else {}),
            survivors=won, fallen=dead, remaining=left,
            bots=[G.bot_snapshot(b) for b in bots],
            **({"quests": G.quest_summary(quests)} if quests is not None else {}),   # D69 additive — 의뢰 장부(맡음·진행·완수·귀환·보고 틱)
            **({"warped": True} if (quests is not None and quests.get("returned") is not None) else {}),   # D69 additive — 워프로 돌아온 판
            summary=summary)                          # D58 additive — 오프라인 `python run_summary.py` 와 같은 계산
    sw.close()
    snapshot.remove(STATE)                        # D79 끝난 판은 이어갈 몸이 없다(스냅샷 삭제)
    for ln in run_summary.render(summary, names):    # 1차 부검은 여기서(파트너 "이러려고 결산 기능을 만든 거잖아")
        event(ln)
    if GM_ON:                                     # 마지막 연출은 기다려 준다(최대 타임아웃+여유)
        gm_q.put(None)
        gm_thread.join(timeout=gm.TIMEOUT + 10)
    write_map(d, bots, turn)


if __name__ == "__main__":
    import envload
    envload.load()      # ⚠️ 유일한 .env 로드 지점 — 모듈 최상단이 아니라 __main__ 안이다.
                        #    게이트는 `import show_runner; show_runner.main()` 으로 부르므로
                        #    이 줄을 밟지 않는다 → 게이트 프로세스엔 API 키가 안 들어간다.
                        #    키 없는 프로세스에선 백엔드가 소켓을 열기 전에 끊으므로, 모킹을
                        #    빠뜨린 게이트가 있어도 실 API 가 물리적으로 못 나간다(안전핀).
    main()
