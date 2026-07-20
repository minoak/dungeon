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
          DUNGEON_DEPTHS(기본2 — 층수. 계단 '>'로 파티가 함께 내려간다. 마지막 층 계단=탈출)
          DUNGEON_LURKERS(기본1 — 층당 매복몹 수) / DUNGEON_POTIONS(기본1 — 층당 회복 물약)
          DUNGEON_STREAM_OBS(1이면 스트림 decisions 에 각 봇 obs 동봉 — 용량 커짐, 디버그/BYO용)
          DUNGEON_PARTY_FILE(기본 party.json — 캐릭터 시트. 검증 실패=내장 2인 폴백)
          DUNGEON_MENU(기본1 — 리모컨: 행동을 엔진 열거 옵션에서 번호 선택. 0=구식 자유서술)
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
import time
import queue
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dungeon_gm as G
import brains
import gm
import stream
import bestiary

STATE = os.environ.get("DUNGEON_STATE_DIR") or os.path.join(HERE, "state")
os.makedirs(STATE, exist_ok=True)

DUNGEON_W = int(os.environ.get("DUNGEON_W", "56"))
DUNGEON_H = int(os.environ.get("DUNGEON_H", "20"))
DUNGEON_SEED = int(os.environ.get("DUNGEON_SEED", "7"))
MAX_TURNS = int(os.environ.get("DUNGEON_TURNS", "250"))   # 1틱=한 걸음(구 30은 단층·1턴=1행동 시절 값.
                                                          # 2층 관통 더미 실측 ~185틱 → 여유 250)
N_MON = int(os.environ.get("DUNGEON_MONSTERS", "2"))
N_TRAP = int(os.environ.get("DUNGEON_TRAPS", "3"))
N_LURK = int(os.environ.get("DUNGEON_LURKERS", "1"))
N_POTION = int(os.environ.get("DUNGEON_POTIONS", "1"))   # 층당 회복 물약(07-17) — 러너 기본 1,
                                                          # 엔진 직생성 기본 0(기존 verify 비트 동일)
DEPTHS = int(os.environ.get("DUNGEON_DEPTHS", "2"))
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
GRAVES_ON = os.environ.get("DUNGEON_GRAVES", "1") != "0"     # 묘(D22) — 러너 기본 1, 엔진 기본 0.
                                                             #   쓰러진 자리에 '~의 묘'(광학·조회·goto 앵커)
EVENTS_ON = os.environ.get("DUNGEON_EVENTS", "1") != "0"     # 사건층(D22) — 러너 기본 1, 엔진 기본 0.
                                                             #   전달층(시야 내 사건 목격, 휘발=다음 결정
                                                             #   1회)+기억층(fallen 지속 재제시, 휘발 0)
LORE_FILE = os.path.join(HERE, "lore.json")
STEP_DELAY = float(os.environ.get("DUNGEON_STEP_DELAY", "0.5"))   # 한 수 적용 후 맵이 보이게(헤들리스=0)

# 캐릭터 시트 계약(party.json): 필수 9필드(수치형/문자형) + 선택 4필드(프롬프트 전용)
SHEET_REQ = {"job": str, "sex": str, "hp": int, "str": int, "dex": int,
             "wdmg": int, "stealth": int, "search_r": int, "persona": str}
SHEET_OPT = ("name", "speech", "goal")     # + relationships(dict) 별도 취급
FREETEXT_MAX = 300                          # 자유서술 절단 — 프롬프트 폭주 방지(UGC 검증 씨앗)


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
                    v = v[:FREETEXT_MAX]
                out[k] = v
            if out["hp"] < 1:
                raise ValueError("봇%s hp 는 1 이상" % char)
            for k in SHEET_OPT:
                if k in s and s[k] is not None:
                    if not isinstance(s[k], str):
                        raise ValueError("봇%s %s 는 문자열이어야 함" % (char, k))
                    out[k] = s[k][:FREETEXT_MAX]
            rel = s.get("relationships")
            if rel is not None:
                if not isinstance(rel, dict):
                    raise ValueError("봇%s relationships 는 객체여야 함" % char)
                out["relationships"] = {str(o): str(t)[:FREETEXT_MAX] for o, t in rel.items()}
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
        lines.append("  봇%s %s%s(%s)  pos=(%2d,%2d)  보물 %d  물약 %d  핑:%s  %s"
                     % (b["char"], nm, b["job"], b["sex"], b["x"], b["y"], b["bag"],
                        b.get("potions", 0), ping, state))
    alive_m = sum(1 for m in d.monsters if m.alive)
    lines.append("")
    lines.append("  몬스터 %d/%d    범례: # 벽  . 바닥  + 문  $ 보물  > 계단  M 몬스터  ^ 함정  = 상자  ~ 샘  ! 물약  %s 영웅"
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


def act_summary(res):
    """봇 한 행동/자동보행 결과를 한 줄 요약 — 로그/이벤트 공용."""
    t = res["type"]
    if t == "goto":
        if res["result"] == "blocked" and res.get("allies"):   # D18: 동료發 대우회 — 멈춰 보고
            return "%s — 동료(%s)가 길목에 서 있어 크게 돌아야 함, 멈춰 보고" % (
                res.get("target", "?"), ", ".join(a["name"] for a in res["allies"]))
        tag = {"pathed": "핑 -> 자동보행 개시", "arrived": "이미 곁에", "no_path": "길이 없다"}
        return "%s %s" % (res.get("target", "?"), tag.get(res["result"], res["result"]))
    if t == "follow":                                          # 동행(D18 A-5)
        r = res["result"]
        allies = ", ".join(a["name"] for a in res.get("allies", []))
        tag = {"pathed": "동행 개시 -> %s 곁으로" % res.get("target", "?"),
               "following": "동행 개시 — 이미 곁, 따라 걷는다 (%s)" % res.get("target", "?"),
               "blocked": "동행 — 동료(%s)가 길목을 막아 멈춰 보고" % allies}
        return tag.get(r, "동행(%s)" % r)
    if t == "explore":
        r = res["result"]
        if r == "pathed":
            if res.get("to_exit"):
                return "탐색 — 더 볼 곳 없음, 출구로 향함"
            return "탐색 -> %s 방향 자동보행" % res.get("bearing", "?")
        return "탐색 — 갈 곳 없음" if r == "no_path" else "탐색(%s)" % r
    if t == "walk":
        r = res["result"]
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
            return "%s 곁에 도착 — 재결정" % res.get("target", "?")
        if r == "lost":                                # 유령 좌표의 끝(07-05 부검 정직화) — 허탕 보고.
            # '곁에 없다'까지만 단정 — 대각 한 칸에 비껴 서 있을 수도 있다(그건 sights 가 보여준다)
            return "%s를 마지막 본 자리까지 갔지만 — 곁에 없다 (재결정)" % res.get("target", "?")
        if res.get("paced"):                           # 교대(D18 개정) 양보 — 같은 방향 행군 한 박자
            return "동료(봇%s)가 앞서 걷는 중 — 한 박자 양보(제자리)" % res["paced"]
        pre = ("동료(%s)와 자리 교대 — " % res["swap"]["name"]) if res.get("swap") else ""
        return pre + "%s (%s)" % (res.get("to", "?"), tag.get(r, r))
    if t == "interact":
        r = res["result"]
        if r == "exit":
            return "다 모였다 — 함께 하강!! (%s)" % "·".join(res.get("party", []))
        if r == "wait_allies":
            return "계단에서 동료를 기다린다 (아직: 봇%s)" % "·".join(res.get("missing", []))
        if r == "chest_loot":
            return "상자를 열었다 — 보물 %d개!" % res.get("loot", 0)
        if r == "chest_trap":
            return "상자에서 독침이! %d피해" % res.get("dmg", 0)
        if r == "fountain_heal":
            return "샘물을 마셨다 — HP %d 회복" % res.get("heal", 0)
        if r == "fountain_harm":
            return "샘물이 오염돼 있었다 — %d피해" % res.get("dmg", 0)
        tag = {"treasure": "$ 획득", "potion": "! 회복 물약 획득", "too_far": "너무 멀다",
               "nothing": "허탕", "no_target": "대상 없음"}
        return "상호작용 %s — %s" % (res.get("target", "?"), tag.get(r, r))
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
        return "공격 %s — %s%d피해%s" % (res["target"], head, res["dmg"], tail)
    if t == "search":
        f = res.get("found", [])
        if not f:
            return "샅샅이 살폈다(반경%d) — 아무것도 없음" % res.get("radius", 1)
        return "샅샅이 살폈다 — 발견: " + ", ".join(x["name"] for x in f)
    return t


def mon_summary(e):
    if e["type"] == "monster_notice":                      # 몹이 파티를 발견(발각굴림 성공) = 추적 개시
        return "%s 파티를 발견 — 봇%s 추적 개시!" % (e["monster"], e["target"])
    if e["type"] == "monster_flee":                        # 저HP → 도주 전환
        return "%s 겁에 질려 달아나기 시작한다!" % e["monster"]
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
        return "%s%s -> 봇%s  %d피해%s" % (sneak, e["monster"], e["target"], e["dmg"], tail)
    if e.get("fleeing"):
        return "%s 도망친다" % e["monster"]
    return "%s 다가온다" % e["monster"]


def main():
    sheets = load_party(PARTY_FILE)                       # 시트 외부화 — 파티 구성=이 파일이 결정
    chars = sorted(sheets)
    names = {c: (sheets[c].get("name") or "봇%s" % c) for c in chars}
    lore = bestiary.load_lore(LORE_FILE)                  # 지식 '본문'(D9) — 판정 무접촉, obs 전용
    iss = bestiary.Issuer(names)                          # 도감 발급기 = 스트림 소비자(D9 '획득')
    if BESTIARY_FILE:
        iss.load(BESTIARY_FILE)                           # 지난 원정의 지식 이월 — 죽어도 남는 재산(D4)
    for p in glob.glob(os.path.join(STATE, "bot*.log")):  # 이전 판 잔재(다른 인원수) 제거
        os.remove(p)
    for n in ["events.log", "gm.log"] + ["bot%s.log" % c for c in chars]:
        open(os.path.join(STATE, n), "w", encoding="utf-8").close()
    sw = stream.StreamWriter(os.path.join(STATE, "stream.jsonl"))   # 실행당 truncate

    d = G.Dungeon(w=DUNGEON_W, h=DUNGEON_H, seed=DUNGEON_SEED, n_potions=N_POTION,
                  n_monsters=N_MON, n_traps=N_TRAP, n_lurkers=N_LURK, scan=SCAN_ON,
                  loops=LOOPS_ON, selfstop=SELF_ON, graves=GRAVES_ON, events=EVENTS_ON)
    d.lore = lore
    bots = []
    for c in chars:
        b = G.spawn(d, c, bots, sheet=sheets[c])
        b['known'] = iss.known(names[c])   # 도감 주입 켬 — 발급기의 set 과 *같은 객체*(획득 즉시 다음 obs 반영)
        if LEDGER_ON:
            b['ledger'] = G.new_ledger()   # 공간 장부(D17) 켬 — 이 층에서 본 것의 원장
        bots.append(b)
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
    fallen = []         # 이전 층에서 쓰러진 영웅(층 전이 때 bots 에서 빠짐 — 기록만 남긴다)

    # 스트림 머리: run_meta(1회 — started 가 유일한 비결정 필드) + 첫 level
    sw.emit("run_meta", v=1, started=time.strftime("%Y-%m-%dT%H:%M:%S"),
            seed=DUNGEON_SEED, w=DUNGEON_W, h=DUNGEON_H, depths=DEPTHS,
            monsters=N_MON, traps=N_TRAP, lurkers=N_LURK,
            potions=N_POTION,          # 층당 회복 물약(07-17 additive) — 배치를 바꾸는 판 파라미터
            sight=G.SIGHT,             # 시야 반경(DUNGEON_SIGHT) — 굴림 수를 바꾸는 세계 물리
                                       #   (리플레이·판 비교의 전제, seed 와 같은 급)
            max_turns=MAX_TURNS, gm=GM_ON,
            stream_obs=os.environ.get("DUNGEON_STREAM_OBS") == "1",   # decisions 에 obs 동봉 여부(스키마 판별용)
            menu=brains.MENU,          # 리모컨(번호 선택) 여부 — decisions 에 choice 가 실리는지 판별용
            ledger=LEDGER_ON,          # 공간 장부(D17) 여부 — obs(known·돌아가기)를 바꾸는 실행모드 메타
            scan=SCAN_ON,              # 스캐너(D19) 여부 — obs(구조)·정지 물리를 바꾸는 실행모드 메타
                                       #   (걸음 정지 규칙이 달라지므로 리플레이·판 비교의 전제)
            selfstop=SELF_ON,          # 자기 관찰 정지(D21) 여부 — 정지 물리 메타(scan 과 같은 급)
            graves=GRAVES_ON,          # 묘(D22) 여부 — 피처가 늘어나는 세계 물리 메타
            events=EVENTS_ON,          # 사건층(D22) 여부 — obs(목격·기억)를 바꾸는 실행모드 메타
            obs_ascii=brains.OBS_ASCII,   # wire 직렬화 스위치(D17-4) — LLM 프롬프트 표현 메타
            obs_pos=brains.OBS_POS,       #   (obs dict 는 불변 — 판독·재현 시 어느 wire 였는지 식별용)
            bestiary=iss.snapshot(),   # 판 시작 시점 지식(additive) — 도감이 obs 를 바꾸므로 리플레이·비교의 전제
            bestiary_file=bool(BESTIARY_FILE),   # 영속 여부(실행모드 메타 — gm/menu 와 같은 급)
            party=[{**{k: b[k] for k in ("char", "job", "sex", "maxhp", "str", "dex",
                                         "wdmg", "stealth", "search_r", "persona")},
                    **({"name": b["name"]} if b.get("name") else {})}   # additive: 보고서·웹의 호칭
                   for b in bots])
    lvl = {"turn": 0, **d.level_snapshot(),
           "party": [G.bot_snapshot(b) for b in bots]}
    sw.emit("level", **lvl)
    iss.consume("level", lvl)          # 발급기도 같은 원장을 본다 — 층의 몹 id→종 지도 구축

    gmtag = "Sonnet GM" if GM_ON else "GM 없음"
    roster = "·".join((b.get("name") or b["job"]) for b in bots)
    event("=== TRPG 던전 시작 (%s / Haiku 두뇌 / %s / 구독 과금 0)  %dx%d  지하%d층  몬스터%d 함정%d 매복%d ==="
          % (roster, gmtag, DUNGEON_W, DUNGEON_H, DEPTHS, N_MON, N_TRAP, N_LURK))
    inbox = {b["char"]: [] for b in bots}   # 봇별 받은편지함 (동료가 지난 턴 한 say).
                                            # 빈 dict 아닌 전 봇 키 — 스트림 tick.inbox 형태 고정(소비자 인덱싱)
    write_map(d, bots, 0)
    time.sleep(1.0)

    turn = 0
    says = {}
    for turn in range(1, MAX_TURNS + 1):
        d.turn = turn       # 장부(D17) 목격 스탬프 — 판정 무관여, "언제 봤나"의 단일 원천
        inbox_in = inbox    # 이번 틱 사고에 주입된 받은편지함 — 루프 끝에서 이름이 새 dict 로
                            # 재바인딩되므로(덮어씀) think_all 직전 참조를 잡아 스트림에 남긴다
        # order 없는 봇만 사고(자동보행 중인 봇은 LLM 0콜)
        decisions = brains.think_all(d, bots, inbox)
        thinkers = "·".join(sorted(decisions)) if decisions else "-"
        event("-- tick %d --  (사고:%s / 나머지 자동보행)" % (turn, thinkers))
        turn_events = []
        says = {}
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
                append(botlog[b["char"]], "[t%02d] %s" % (turn, dec.get("reason", "")))
                append(botlog[b["char"]], "        -> %s  <%s>" % (act_summary(res), src))
                if dec.get("say"):
                    says[b["char"]] = dec["say"]
                    append(botlog[b["char"]], '        \U0001f4ac "%s"' % dec["say"])
                    event('   봇%s \U0001f4ac "%s"' % (b["char"], dec["say"]))
            res["job"] = b["job"]
            turn_events.append(res)
            mark = {"fallback": " [규칙]", "plan": " [작정]"}.get(src, "")
            event("   봇%s  %s%s" % (b["char"], act_summary(res), mark))
            if not b["alive"]:
                event("   봇%s 쓰러졌다!" % b["char"])
            write_map(d, bots, turn)
            time.sleep(STEP_DELAY)

        # ③ 몬스터 턴 (엔진 — 독립 시계)
        mon_events = d.monster_turn(bots)
        for e in mon_events:
            event("   %s" % mon_summary(e))
            if e.get("down"):
                event("   봇%s 쓰러졌다!" % e["target"])
        if mon_events:
            write_map(d, bots, turn)
        turn_events += mon_events

        # 의논 핑퐁: say -> 동료가 *볼 수 있을 때만*(근접/시야) 다음 틱 받은편지함
        inbox = {}
        for b in bots:
            seen = d.visible_cells(b["x"], b["y"]) if b["alive"] else set()
            inbox[b["char"]] = [{"from": oc, "text": t} for oc, t in says.items()
                                if oc != b["char"]
                                and any(o["char"] == oc and (o["x"], o["y"]) in seen for o in bots)]

        # 스트림 tick — 빈 틱 포함 매 반복(turn 연속 불변식). GM 블록 *앞*에서 emit:
        # 여기서 즉시 직렬화되므로 GM 지연·이후 dict 변경과 독립(공유 오염 방어).
        # 스냅샷은 델타 아닌 전체 — 임의 틱 시킹용. visited 만 제외(파생: 스폰+틱별 봇 좌표 누적).
        tick_rec = {"turn": turn, "inbox": inbox_in, "decisions": decisions,
                    "events": turn_events,
                    "bots": [G.bot_snapshot(b) for b in bots],
                    "monsters": [m.as_dict() for m in d.monsters],
                    "features": [f.as_dict() for f in d.features.values()],
                    "traps": [t.as_dict() for t in d.traps]}
        sw.emit("tick", **tick_rec)

        # 도감 획득(D9) — 스트림의 결정론 투영(LLM 0콜). 등재 즉시 봇 known(공유 set)에 반영.
        new_knowledge = iss.consume("tick", tick_rec)
        for nm, key in new_knowledge:
            event('   \U0001f4d6 %s — 도감 등재: %s' % (nm, bestiary.label(key, lore)))
        if new_knowledge and BESTIARY_FILE:
            iss.save(BESTIARY_FILE)

        # ④ GM 진행자(옵션 소비자): 이번 틱 events를 장면으로 연출.
        #    party 도 스트림 스냅샷의 projection — GM 이 별도 진실 조립을 갖지 않는다(이중화 제거).
        #    name 만 시트에서 보강(스냅샷엔 없음 — 호칭용).
        if GM_ON and turn_events:
            party = [{**{k: s[k] for k in ("char", "job", "hp", "maxhp", "bag", "alive", "won")},
                      "name": sheets[s["char"]].get("name")}
                     for s in tick_rec["bots"]]
            try:                                  # 밀린(아직 안 집은) 턴은 버린다 — 최신-우선
                while True:
                    gm_q.get_nowait()
            except queue.Empty:
                pass
            gm_q.put((turn, turn_events, party))  # 비동기 — 루프는 즉시 다음 틱으로

        if all(b["won"] or not b["alive"] for b in bots):
            survivors = [b for b in bots if b["won"]]
            fallen += [b["char"] for b in bots if not b["alive"]]
            if not survivors or d.depth >= DEPTHS:
                break                     # 전멸 or 최심층 돌파 = 진짜 탈출(승리)
            # ── 강하 전이(Stage 4): 다음 층 생성(마스터시드→층별 파생) + 생존 파티 이월 ──
            nd = d.depth + 1
            sw.emit("descend", turn=turn, to_depth=nd,
                    party=[{"char": b["char"], "hp": b["hp"], "bag": b["bag"],
                            "potions": b.get("potions", 0)}
                           for b in sorted(survivors, key=lambda b: b["char"])],
                    fallen=list(fallen))
            d = G.Dungeon(w=DUNGEON_W, h=DUNGEON_H, seed=DUNGEON_SEED, depth=nd,
                          n_monsters=N_MON + nd - 1, n_traps=N_TRAP, n_lurkers=N_LURK,
                          scan=SCAN_ON, n_potions=N_POTION, loops=LOOPS_ON, selfstop=SELF_ON,
                          graves=GRAVES_ON, events=EVENTS_ON)
            d.lore = lore
            nb = []
            for b in sorted(survivors, key=lambda b: b["char"]):
                n = G.spawn(d, b["char"], nb, sheet=sheets[b["char"]])   # ⚠️ sheet 필수 — 없으면
                n["hp"], n["bag"] = b["hp"], b["bag"]     # HP·보물 이월     외부 시트 봇('3'+)이 2층서 죽는다
                n["potions"] = b.get("potions", 0)        # 물약도 이월(07-17) — 들고 내려간다
                n["memories"] = list(b.get("memories") or [])   # 기억도 이월(D22) — 전사는 원정급
                                                          # 사건(장부=층의 기억과 대비. 구역 이름은
                                                          # 그 층의 것 — 층수 없인 모호하나 v0 수용)
                n["known"] = iss.known(names[b["char"]])  # 도감은 층을 넘어도 그대로(지식=영속층)
                if LEDGER_ON:
                    n["ledger"] = G.new_ledger()          # 장부는 새 원장(층의 기억 — id 층-로컬, D17)
                nb.append(n)
            d.turn = turn
            bots = nb
            inbox = {b["char"]: [] for b in bots}   # 층 전이 = 대화 리셋(형태는 전 봇 키로 고정)
            lvl = {"turn": turn, **d.level_snapshot(),            # descend 직후 level 불변식
                   "party": [G.bot_snapshot(b) for b in bots]}
            sw.emit("level", **lvl)
            iss.consume("level", lvl)               # 새 층 몹 id→종 지도 갱신
            event("=== 일행은 어둠 속 계단을 내려선다 — 지하 %d층 (깊을수록 흉흉하다: 몬스터 %d) ==="
                  % (nd, N_MON + nd - 1))
            write_map(d, bots, turn)
            time.sleep(1.0)

    won = [b["char"] for b in bots if b["won"]]
    dead = fallen + [b["char"] for b in bots if not b["alive"] and b["char"] not in fallen]
    left = [b["char"] for b in bots if b["alive"] and not b["won"]]
    if won and d.depth >= DEPTHS:
        outcome = "escaped"                          # 최심층 돌파 = 진짜 탈출(승리)
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
        event("    (더 길게: DUNGEON_TURNS=400 bash ~/dungeon/start.sh)")
    sw.emit("end", turn=turn, outcome=outcome, depth=d.depth,
            survivors=won, fallen=dead, remaining=left,
            bots=[G.bot_snapshot(b) for b in bots])
    sw.close()
    if GM_ON:                                     # 마지막 연출은 기다려 준다(최대 타임아웃+여유)
        gm_q.put(None)
        gm_thread.join(timeout=gm.TIMEOUT + 10)
    write_map(d, bots, turn)


if __name__ == "__main__":
    main()
