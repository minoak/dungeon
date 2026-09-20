#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""원더랜드 웹 론처(D31, 2026-09-05) — "게임처럼 시작한다".
─────────────────────────────────────────────
왜: 지금까지 판은 콘솔 메뉴(wonderland.bat)로 띄우고 브라우저(viewer/)로 관전했다. 뷰어는 정적
서버(python -m http.server)라 저장도 실행도 못 한다. 이 파일이 그 정적 서버를 **대신** 맡아(같은
포트 8000, 같은 서빙 루트 — 뷰어는 한 줄도 안 고침) 세 가지를 더 한다: 파티 저장 · 판 시작/중지 ·
상태 조회. 표준 라이브러리만 쓴다(새 의존 0). 127.0.0.1 만 듣는다.

흐름: 타이틀 → 파티(직업·성격 키워드 최대 3·이름·성별·배경 자유입력) → 옵션(맵·마을·두뇌·시드) →
시작 → 러너(show_runner.py)를 자식 프로세스로 띄우고 → 관전 뷰어로 이어진다.

API(JSON):
  GET  /api/presets  traits.json(키워드·직업) + looks(외형 사전, D37) + 기본 파티(party.json) 미리보기 + 상태
                     + companions(D81 동료 프리셋 목록 — entities/companion/*.json: id·이름·직업·성격·말투·목표·소개 한 줄·외형)
  GET  /api/characters  저장한 캐릭터 목록 {presets:[{id,label,slot}]} — 규격은 docs/character-presets.md
  POST /api/characters  {slot,label?,id?} → id 생략 시 새 저장, 있으면 해당 프리셋 덮어쓰기 → {preset}
  POST /api/characters/delete  {id} → 해당 프리셋 삭제 → {ok:true}
  POST /api/party    {"slots":[{job,traits[],name,sex,background?,persona?,look?} | {"companion":"<동료 프리셋 id>"}, ...]} → sheetkit 조립 →
                     러너의 load_party 로 재검증 → party_custom.json 저장 (실패 400 + 이유 한 줄)
  POST /api/start    {"resume":true, "brain"?, "key"?} → 멈춘 판 이어가기(D79 — 스냅샷+그 판을 시작한 옵션, 같은 기록 파일에 append) 또는
                     {"town":bool,"brain":"gemini_api|claude_cli|anthropic_api|dummy",
                      "seed":int|null|"random","party":"custom|default","mode":"standard|classic",
                      "town_life"?:bool,"npc_reply"?:bool,"floor_life"?:bool,"bestiary_plus"?:bool,"loop"?:bool,"offer"?:bool,
                      "map"?:"normal|big|concept"} → 이전 판 보존(live.bat 규칙)
                     → 러너 subprocess. 동시 1판(실행 중이면 409). 09-20 밤의 스위치들(D89~D95)은 옵션이 없으면 끈다 —
                     화면의 기본 체크는 NIGHT_DEFAULTS(/api/presets.night_defaults)가 정한다.
                     map 은 09-20 오후부터 화면에 없다(판은 늘 MAP_DEFAULT) — 옛 이름은 이어가기·게이트가 계속 보낸다
  GET  /api/status   {running,pid,started,seed,party,turn,outcome,viewer,game, stopping, resume:{run_id,seed,turn_last,depth,party,stopped,pages}|null}
  POST /api/stop     {graceful?:bool, pages?:bool} — graceful 이면 러너가 다음 틱 머리에서 (수첩 한 장씩 쓰고) 스스로 닫는다(D79), 아니면 즉시 종료
  POST /api/retry    {pause_id} → 판단 정지 중인 같은 러너에서 모델 재시도
  GET  /game/        게임 클라이언트(game/dist/ 빌드 산출물 — 초점 캐릭터 카메라 뷰어, 2026-09-09 M3/B5).
                     /game → 302 /game/ · /game/… 은 game/dist/… 서빙 · 빌드가 없으면 503 한 장(빌드 명령 안내)

⚠️ 사용자 자유 입력(이름·배경)은 시트 UGC 의 프롬프트 인젝션 관문이다 — sheetkit 이 격리(정제·
상한·인용 한 줄)하고 러너의 load_party 가 다시 검증한다. 막는 게 아니라 격리+관측(D31).
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import sheetkit                                   # noqa: E402
import entities                                   # noqa: E402  # D81 동료 프리셋 저장소(entities/companion) — 정의만 읽는다(엔진 무접촉)
import campaign                                   # noqa: E402  # D78 캠페인 = 판 기록의 0콜 투영(저장 캐릭터별 원정 기록)
import skill_schema                              # noqa: E402
import run_control                               # noqa: E402
import snapshot                                  # noqa: E402  # D79 이어가기 — 멈춘 판의 요약(snapshot.json)만 읽는다(피클은 러너 몫)
from brain_config import BACKENDS, HTTP_BACKENDS, KEY_ENV, MODEL_ENV, clean_model, model_id, provider_catalog
from character_presets import PresetStore         # noqa: E402

MAPS = {                                          # 시작 옵션 → 러너 환경변수(wonderland.bat 메뉴 값 그대로)
    # ⚠️normal·big 은 09-20 오후부터 **화면에 없는 옛 이름**이다(파트너 "다른건 쓰지 않으니") — 그래도 지우지 않는다:
    #   (a) 멈춰 둔 옛 판의 run_opts.json 에 map:"normal" 이 적혀 있고 이어가기(D79)가 그 이름으로 세계를 다시 짓는다,
    #   (b) 게이트 여럿이 /api/start 에 이 이름을 직접 보낸다(verify_launcher·verify_public·verify_account·verify_campaign·verify_resume).
    "normal": {},
    "big": {"DUNGEON_W": "80", "DUNGEON_H": "30", "DUNGEON_MONSTERS": "7", "DUNGEON_TRAPS": "4",
            "DUNGEON_LURKERS": "2", "DUNGEON_POTIONS": "1", "DUNGEON_DEPTHS": "1", "DUNGEON_TURNS": "500"},
    # D88(09-20) 새 던전 생성 프로필 — 넓은 통로·대홀·기둥의 석조 던전. 생성기가 42x34 에서만 검증됐다(1,000 시드)
    # → 크기를 여기서 같이 준다(부모 env 의 DUNGEON_W/H 를 덮는다). ⚠️키 이름은 바꾸지 않는다 —
    # 멈춰 둔 판의 run_opts.json 이 이 이름으로 이어간다(D79).
    # DUNGEON_MONSTERS 3: 러너 기본은 2(깊이마다 +1 → 1~5층에 2·3·4·5·6 마리)다. 42x34 는 56x20 보다 바닥이 넓어 2 는 헐겁다
    # (파트너 09-20 "몹의 숫자를 약간 늘리자"). 3 이면 3·4·5·6·7 마리 = 판 전체로 20 → 25.
    # 0콜 실측(더미 두뇌·시드 10개·마을 끔·600틱·보스 실수치·던전 살림/새 몬스터 켬):
    #   몹 2 → 전멸 7 · 600틱 생존 3 · 5층 도달 6/10        몹 3 → 전멸 10 · 생존 0 · 5층 도달 2/10
    # 즉 눈에 띄게 험해진다. 규칙 두뇌는 도망도 물약도 제대로 못 쓰므로 이 수치는 하한이다(LLM 판은 더 오래 버틴다).
    # ⚠️값 임시 — 험하면 이 한 줄만 고친다(2 로 되돌리면 옛 몹 수).
    "concept": {"DUNGEON_W": "42", "DUNGEON_H": "34", "DUNGEON_ARCH": "concept", "DUNGEON_MONSTERS": "3"},
}
MAP_DEFAULT = "concept"                           # 09-20 오후(파트너 "이제 맵을 새로운 석조 던전의 보통으로 고정"): 화면에 맵 고르는 자리가 없다.
                                                  #   옵션이 없거나 모르는 이름이면 이 맵으로 뜬다 — 바꾸려면 이 한 줄.
# ── 09-20 밤의 기본값(D89~D95) — 화면(launcher/index.html)의 고급 설정 체크박스가 처음에 서 있는 자리.
# 화면은 이 값을 /api/presets.night_defaults 로 받아 맞춘다(index.html 에는 값이 없다 — 공개 서버 server.py 도 같은 본문을 쓴다).
# 뒤집는 법: 아래 한 줄만 고친다(전부 옛 판 = OLD_DEFAULTS 와 같은 값으로). 론처·서버는 재시작해야 새 값이 나간다.
# ⚠️이것은 '화면의 기본'이다 — /api/start 에 옵션이 아예 없으면 Runner.start 는 스위치를 전부 끈 판으로 띄운다:
#   멈춰 둔 옛 판의 run_opts.json 에는 이 키들이 없고, 그 판은 같은 세계 설정으로 이어가야 한다(D79 세계 지문 대조).
#   맵만은 예외다 — 화면에서 고르는 자리가 없어졌으므로 옵션이 없으면 MAP_DEFAULT 로 뜬다.
NIGHT_DEFAULTS = {"town_life": True, "npc_reply": True, "floor_life": True, "bestiary_plus": True, "loop": True, "offer": True}
OLD_DEFAULTS = {k: False for k in NIGHT_DEFAULTS}   # 화면의 '09-20 추가 전으로' 버튼이 돌아가는 자리(맵은 안 돌아간다 — 화면에 없다)
OPTIONS_UI_VERSION = 2                            # 09-20 시작 옵션(MAPS·위 스위치)의 판 번호 — 화면이 보내는 옵션을 이 서버가 아는가.
                                                  #   8000번에 떠 있던 옛 론처를 다시 쓰는 조건(main)과 화면의 '이전 런처' 안내가 이 값을 본다.
                                                  #   MAPS 에 키를 더하거나 화면이 새 옵션을 보내게 되면 올린다(index.html 의 비교 값도 같이).
                                                  #   2 = 09-20 오후(맵 고르기를 화면에서 걷음 · 스위치 둘 추가: loop·offer).
BRAINS = BACKENDS
TEXT_LIMITS = {"persona": sheetkit.PERSONA_MAX, "persona_total": sheetkit.PERSONA_TOTAL_MAX,
               "background": sheetkit.BACKGROUND_MAX}
GAME_PREFIX = "/game/"                            # 게임 클라이언트(M3/B5): URL 접두 → game/dist/ (vite base '/game/' 와 같다)
GAME_DIST_PREFIX = "/game/dist/"
GAME_NO_STORE = ("/game/", "/game/index.html")    # 진입 HTML 만 캐시 금지 — 해시 자산(/game/assets/*)은 기본 캐시


class Conflict(Exception):
    pass


class BadRequest(Exception):
    pass


class LauncherServer(ThreadingHTTPServer):
    # Windows의 SO_REUSEADDR는 이미 열린 포트에 두 서버를 붙일 수 있다.
    allow_reuse_address = os.name != 'nt'


class Runner:
    """러너 프로세스 1개의 생애 — 시작(이전 판 보존 포함)·상태·중지. 동시 1판."""

    def __init__(self, root, state_dir, runs_dir):
        self.root, self.state_dir, self.runs_dir = root, state_dir, runs_dir
        self.proc = None
        self.started = None
        self.seed_requested = None
        self.lock = threading.Lock()

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def preserve_previous(self):
        """live.bat 규칙의 파이썬판: state/stream.jsonl 이 비어 있지 않으면 runs/stream-<mtime>.jsonl 로 복사."""
        src = os.path.join(self.state_dir, "stream.jsonl")
        if not (os.path.exists(src) and os.path.getsize(src) > 0):
            return None
        os.makedirs(self.runs_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(os.path.getmtime(src)))
        dst = os.path.join(self.runs_dir, "stream-%s.jsonl" % stamp)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        return dst

    RUN_OPTS = "run_opts.json"                   # D79: 이 판을 시작한 옵션 — 이어가기가 같은 세계 설정으로 러너를 띄우는 데 쓴다

    def _write_run_opts(self, opts):
        clean = {k: v for k, v in opts.items() if k not in ("key", "resume")}   # 키는 절대 안 남긴다(BYOK 는 프로세스 env 만)
        run_control.write_json(os.path.join(self.state_dir, self.RUN_OPTS), {"opts": clean, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def _read_run_opts(self):
        doc = run_control.read_json(os.path.join(self.state_dir, self.RUN_OPTS))
        return doc if isinstance(doc.get("opts"), dict) else None

    def resumable(self, status=None):
        """D79 이어갈 몸이 있나 — 러너가 없고 snapshot.json 이 있고 그 판이 state/stream.jsonl 의 판과 같고 끝나지 않았을 때 요약 dict, 아니면 None."""
        if self.running():
            return None
        meta = snapshot.read_meta(self.state_dir)
        if not meta:
            return None
        st = status or {}
        if st.get("outcome") or (st.get("seed") is not None and st.get("seed") != meta.get("seed")):
            return None                           # 끝난 판·다른 판의 스냅샷(러너가 시작·끝에 지우지만 한 번 더 본다)
        stop = meta.get("stop") or {}
        saved = (self._read_run_opts() or {}).get("opts", {})
        return {k: meta.get(k) for k in ("run_id", "seed", "started", "turn_last", "depth", "segment", "party", "saved_at", "backend")} | {
            "stopped": stop.get("reason"), "pages": sorted(stop.get("pages") or {}),
            "provider": saved.get("provider") or saved.get("brain") or meta.get("backend"), "model": saved.get("model", "")}

    def start(self, opts, party_path, default_brain=None, extra_env=None):
        """extra_env: 이 판의 러너에만 주는 환경변수(공개 서버 server.py 의 BYOK 키 — 부모 환경에 안 남고 프로세스에만).
        opts.resume(D79): 멈춘 판을 이어간다 — 화면의 옵션은 두뇌만 받고 나머지는 그 판을 시작한 옵션(run_opts.json)·스냅샷의 시드로."""
        with self.lock:
            if self.running():
                raise Conflict("이미 판이 진행 중이다 — 중지하거나 끝나길 기다려라")
            # 로컬 화면 BYOK도 키를 옵션에서 즉시 분리한다. 재개 옵션·파일로 합치지 않는다.
            supplied_key = opts.get("key", "")
            opts = {k: v for k, v in opts.items() if k != "key"}
            if not isinstance(supplied_key, str) or len(supplied_key) > 1024:
                raise BadRequest("API 키는 1,024자 이내의 문자열이어야 한다")
            supplied_key = supplied_key.strip()
            if any(c.isspace() for c in supplied_key):
                raise BadRequest("API 키에 공백을 넣을 수 없다")
            if opts.get("provider") and not opts.get("brain"):
                opts = {**opts, "brain": opts["provider"]}
            resume = bool(opts.get("resume"))
            meta = None
            if resume:
                meta = self.resumable(self.status())
                if not meta:
                    raise BadRequest("이어갈 원정이 없다 — 멈춘 판의 스냅샷이 없거나 그 판은 이미 끝났다")
                saved = self._read_run_opts()
                if not saved:
                    raise BadRequest("이어갈 판의 시작 옵션이 없다 — 새 원정으로 시작하라")
                changes = {k: opts[k] for k in ("brain", "provider", "model") if k in opts}
                # 회사만 바꾸면 이전 회사 모델을 보내지 않는다. 명시한 빈 모델도 기본값 선택이다.
                if changes.get("brain", changes.get("provider", saved["opts"].get("brain"))) != saved["opts"].get("brain"):
                    changes.setdefault("model", "")
                opts = {**saved["opts"], "seed": meta.get("seed"), **changes}
            env = dict(os.environ)
            if extra_env:
                env.update({k: str(v) for k, v in extra_env.items()})
            env["PYTHONUTF8"] = "1"
            env["DUNGEON_GM"] = "0"
            env["DUNGEON_STATE_DIR"] = self.state_dir
            env.setdefault("DUNGEON_SIGHT", "6")        # 데모 시야 6(D33 09-05, 파트너 "지금은 너무 좁다 — 1~2칸") —
                                                        #   엔진·게이트·장면 기본은 5 그대로(손그림 장면이 5 전제).
                                                        #   run_meta.sight 에 기록되므로 판 비교의 전제가 남는다.
            brain = str(opts.get("brain") or opts.get("provider") or default_brain or "gemini_api")
            if brain not in BRAINS:
                raise BadRequest("두뇌는 %s 중 하나" % "/".join(BRAINS))
            if supplied_key:
                if brain not in HTTP_BACKENDS:
                    raise BadRequest("API 키는 API 두뇌를 선택했을 때만 넣을 수 있다")
                env.update({name: "" for name in KEY_ENV.values()})
                env[KEY_ENV[brain]] = supplied_key
                env["DUNGEON_BRAIN_FALLBACK"] = ""
            env["DUNGEON_BRAIN_BACKEND"] = brain
            opts = {**opts, "brain": brain}
            if brain in HTTP_BACKENDS:
                opts["provider"] = brain
            if "model" in opts:
                try:
                    selected = clean_model(opts["model"])
                except ValueError as e:
                    raise BadRequest(str(e))
                for k in MODEL_ENV:
                    env[k] = selected
            action_mode = str(opts.get("action_mode", "compose"))
            if action_mode not in ("menu", "compose"):
                raise BadRequest("행동 선택 방식은 menu/compose 중 하나")
            env["DUNGEON_ACTION_MODE"] = action_mode
            mode = str(opts.get("mode", "standard"))
            if mode == "alpha":                  # 이전 링크·클라이언트의 알파 선택도 채택된 기본 원정으로 연결
                mode = "standard"
            if mode not in ("standard", "classic"):
                raise BadRequest("원정 모드는 standard/classic 중 하나")
            if mode == "standard" and action_mode != "compose":
                raise BadRequest("스킬 원정은 조합형 행동으로 시작한다")   # 마을 시작은 두 모드 다 된다(09-11 마을 v1, 파트너 요청)
            # 화면에서 고른 규칙이 부모 콘솔의 설정보다 우선한다.
            for key in ("DUNGEON_SKILLS", "DUNGEON_TRPG_COMBAT", "DUNGEON_RANDOM_SKILL"):
                env[key] = "1" if mode == "standard" else "0"
            seed = opts.get("seed")
            if seed in (None, "", "random"):
                env["DUNGEON_SEED"] = "random"
            else:
                try:
                    env["DUNGEON_SEED"] = str(int(seed))
                except (TypeError, ValueError):
                    raise BadRequest("시드는 정수 또는 비움(랜덤)")
            which = opts.get("party", "custom")
            if which == "default":
                env["DUNGEON_PARTY_FILE"] = os.path.join(self.root, "party.json")
            else:
                if not os.path.exists(party_path) and not resume:   # 이어가기는 스냅샷의 시트를 쓴다(파티 파일이 없어도 된다)
                    raise BadRequest("저장된 커스텀 파티가 없다 — 먼저 파티를 저장하라(또는 기본 파티 선택)")
                env["DUNGEON_PARTY_FILE"] = party_path
            # 09-20 오후: 화면에 맵 고르는 자리가 없다 — 옵션이 없으면(새 화면) MAP_DEFAULT 로 뜬다.
            # 모르는 이름도 400 으로 막지 않고 같은 자리로 보낸다: 화면이 안 보내는 값을 옛 링크·옛 클라이언트가 보냈다고
            # 출발을 막을 이유가 없다(옛 이름 normal·big 은 MAPS 에 그대로 있어 제 세계로 간다).
            m = str(opts.get("map") or MAP_DEFAULT)
            if m not in MAPS:
                m = MAP_DEFAULT
            opts = {**opts, "map": m}   # 고른 결과를 run_opts.json 에 남긴다(D79) — 나중에 MAP_DEFAULT 를 바꿔도 멈춰 둔 판은 제 세계로 이어간다
            # normal = 러너 기본 + 부모 env 그대로: 콘솔·.env·게이트가 준 DUNGEON_W/H/TURNS 등은 이 판으로 물려받는다(게이트가
            # 이 길로 40x16·짧은 판을 만든다). 09-20 수선: 여기 있던 'BIG_KEYS 지우기'는 env 가 os.environ 의 사본이라 부모에 있는 키는
            # 하나도 못 지웠다(D31 부터 — 주석은 '안 물려준다'였고 동작은 반대). 지우는 척하던 줄을 걷고 사실을 적는다.
            env.update(MAPS[m])
            # 생성 프로필(D88)만은 물려받지 않는다 — 고른 맵이 정한다. 부모 env(.env · 서비스 환경값)에 DUNGEON_ARCH 가 있어도
            # 다른 맵을 고른 판은 옛 생성기로 지어야 한다(새 생성기는 42x34 에서만 검증됐다 — 56x20·80x30 은 검증 밖).
            if "DUNGEON_ARCH" not in MAPS[m]:
                env.pop("DUNGEON_ARCH", None)
            if mode == "standard":
                env.update(DUNGEON_DEPTHS="5", DUNGEON_TURNS="600", DUNGEON_SOLO="0")
            if opts.get("town"):
                env["DUNGEON_TOWN"] = "1"
            else:
                env.pop("DUNGEON_TOWN", None)
            env["DUNGEON_TOWN_APART"] = "0" if opts.get("town_apart") is False else "1"   # D69 흩어진 출발 — 화면 기본 켬(옵션 없으면 러너 기본 1)
            env["DUNGEON_NPC_BRAIN"] = "0" if opts.get("npc_brain") is False else "1"     # D69 마을 NPC 두뇌 — 화면 기본 켬(더미 두뇌면 러너가 끈다)
            env["DUNGEON_PARTYFORM"] = "1" if opts.get("partyform") is True else "0"      # D84 파티 결성(실험) — 화면 기본 끔·옵션 없으면 끔(러너는 마을 판에서만 켠다)
            env["DUNGEON_STRANGERS"] = "1" if opts.get("strangers") is True else "0"      # D85 낯선 사람(실험) — 화면 기본 끔·옵션 없으면 끔(러너는 파티 결성 판에서만 켠다)
            env["DUNGEON_TOWN_SIGHT"] = "zone" if opts.get("town_sight") == "zone" else "all"   # D86 마을 시야 = 구역(실험) — 화면 기본 끔·옵션 없으면 옛 판(전체)
            # 09-20 밤의 스위치 넷 — 러너 기본은 전부 0 이고 켜는 쪽은 론처다. 화면의 기본 체크는 NIGHT_DEFAULTS, 옵션이 없으면 끈다
            # (부모 env 값도 덮는다 = 옛 판 · 멈춰 둔 옛 판의 run_opts.json 에는 이 키가 없어 같은 세계로 이어간다).
            env["DUNGEON_TOWN_LIFE"] = "1" if opts.get("town_life") is True else "0"          # D90 마을 생활(마을의 물건·새 주민·들린 말)
            env["DUNGEON_NPC_REPLY"] = "1" if opts.get("npc_reply") is True else "0"          # D93 NPC 되받기(NPC 가 말을 되받는다 — LLM 호출이 조금 는다)
            env["DUNGEON_FLOOR_LIFE"] = "1" if opts.get("floor_life") is True else "0"        # D92 던전의 물건들
            env["DUNGEON_BESTIARY_PLUS"] = "1" if opts.get("bestiary_plus") is True else "0"  # D92 새 몬스터
            env["DUNGEON_LOOP"] = "1" if opts.get("loop") is True else "0"                    # D94 원정 고리(길드 보고가 판을 닫지 않는다 — 러너는 마을·의뢰·게시판이 있는 판에서만 켠다)
            env["DUNGEON_OFFER"] = "1" if opts.get("offer") is True else "0"                  # D95 신에게 바치기
            env["DUNGEON_BOSS"] = "1" if opts.get("boss") else "0"   # D65 보스층·귀환 — 화면 기본 켬, 러너 기본 0(옵션 없으면 끔)
            # 09-20 오후(파트너 "설정도 보스방 앞에서 시작을 빼곤"): D67 관찰용 프리셋(start=boss)은 화면에서도 여기서도 걷었다.
            # 러너의 DUNGEON_START 자체는 남아 있다 — 게이트 verify_boss 가 env 로 직접 쓴다. 부모 env 의 값은 물려주지 않는다.
            env.pop("DUNGEON_START", None)
            if brain == "dummy" or not opts.get("bestiary"):   # 규칙 두뇌는 도감 원장에 누적하지 않는다 · D64(09-13 파트너 "캐릭터 영속은
                env["DUNGEON_BESTIARY_FILE"] = ""              #   서빙까지 했을 때 시작 — 지금은 완전히 별개의 판"): 기본 이월 안 함(판 안 학습만).
            elif not env.get("DUNGEON_BESTIARY_FILE"):         #   옵션 '도감 이월'(bestiary=true)을 켠 판만 로컬 원장에 읽고 쓴다
                env["DUNGEON_BESTIARY_FILE"] = os.path.join(self.root, "bestiary.json")
            os.makedirs(self.state_dir, exist_ok=True)
            if resume:                                   # D79: 같은 기록 파일에 이어 쓴다(보존 복사 없음) — 러너가 스냅샷 자리까지 자르고 append
                env["DUNGEON_RESUME"] = os.path.join(self.state_dir, snapshot.PKL)
                env["DUNGEON_RUNS_DIR"] = self.runs_dir
            else:
                self.preserve_previous()
                snapshot.remove(self.state_dir)          # D79: 새 원정 = 멈춘 판을 놓아 준다(그 기록은 방금 runs/ 로 복사됐다)
            self._write_run_opts(opts)                  # 이어가기에서 바꾼 회사·모델도 다음 이어가기에 유지
            run_control.reset(self.state_dir)
            with io.open(os.path.join(self.state_dir, "runner.out"), "w", encoding="utf-8") as out:
                self.proc = subprocess.Popen([sys.executable, os.path.join(self.root, "show_runner.py")],
                                             cwd=self.root, env=env, stdout=out, stderr=subprocess.STDOUT)
            self.started = time.strftime("%Y-%m-%dT%H:%M:%S")
            self.seed_requested = env["DUNGEON_SEED"]
            return {"ok": True, "pid": self.proc.pid, "seed": self.seed_requested, "brain": brain,
                    "party": which, "map": m, "town": bool(opts.get("town")),
                    "action_mode": action_mode, "mode": mode,
                    "resumed": resume, **({"from_turn": meta.get("turn_last")} if meta else {})}   # D79 additive

    def stop(self, graceful=False, pages=True, wait=45.0, reason=None):
        """러너 종료. graceful(D79 '수첩 쓰고 멈춤'): state/stop.json 을 두고 러너가 다음 틱 머리에서 스스로 닫기를 기다린다(수첩 캐릭터당 1콜 → 몇 초 ~
        한 틱) — 기다림이 끝나면 terminate(루프 머리 스냅샷이 진실이라 잃는 건 수첩뿐). graceful 이 아니면 즉시 terminate(= 끊김. 역시 이어갈 수 있다).
        reason(D91, 09-20 additive): 사람이 누른 멈춤이 아닐 때 그 사유(공개 서버의 'unwatched' = 관전자 없는 판) — 러너가 stopped 줄·요약에 그대로 적는다.
        화면의 멈춤 버튼(/api/stop)은 reason 을 안 준다 = 옛 동작 그대로."""
        with self.lock:
            if not self.running():
                run_control.clear_stop(self.state_dir)
                return {"ok": True, "stopped": False}
            done = False
            if graceful:
                run_control.request_stop(self.state_dir, pages=pages, reason=reason)
                try:
                    self.proc.wait(timeout=max(1.0, float(wait)))
                    done = True
                except subprocess.TimeoutExpired:
                    done = False
            if not done:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                if reason:
                    self._note_stop(reason)
            run_control.clear_stop(self.state_dir)
            return {"ok": True, "stopped": True, "graceful": bool(graceful and done), **({"reason": reason} if reason else {})}

    def _note_stop(self, reason):
        """D91: 스스로 닫히기 전에 끊은 판에도 멈춘 사유를 요약(snapshot.json)에 남긴다 — 몸(피클)은 루프 머리 그대로, 요약의 stop 만 채운다.
        러너가 이미 사유를 적었으면(stop 있음) 건드리지 않는다. 요약이 없으면(이어갈 몸이 없다) 할 일도 없다."""
        meta = snapshot.read_meta(self.state_dir)
        if meta and not meta.get("stop"):
            body = {k: v for k, v in meta.items() if k not in ("version", "saved_at")}
            snapshot.write_meta(self.state_dir, {**body, "stop": {"reason": reason, "pages": {}}})

    def oracle_set(self, text):
        """D61 신탁 소켓(2026-09-12) — 사용자 한 줄을 state/oracle.json 에 둔다(러너가 틱마다 읽어 신전 문턱 근처 캐릭터의
        관측에 '신의 요청'으로 넣는다 — 요청이지 명령이 아니다). 빈 문자열 = 거둔다. 격리 = 시트 배경과 같은 정제(200자)."""
        clean = sheetkit.sanitize_freetext(text, 200)
        p = os.path.join(self.state_dir, "oracle.json")
        if not clean:
            try:
                os.remove(p)
            except OSError:
                pass
            return {"oracle": None}
        rec = {"id": "%x" % int(time.time() * 1000), "text": clean, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        tmp = p + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
        os.replace(tmp, p)
        return {"oracle": rec}

    def oracle_get(self):
        try:
            with io.open(os.path.join(self.state_dir, "oracle.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def status(self):
        """실행 여부 + 현 판의 사실(스트림에서 읽는다 — 러너 밖 원천 없음)."""
        out = {"running": self.running(), "pid": self.proc.pid if self.proc else None,
               "started": self.started, "seed": None, "party": [], "turn": None, "outcome": None,
               "viewer": "/viewer/?run=state/stream.jsonl",
               "game": "/game/?run=state/stream.jsonl"}      # 게임 클라이언트(M3/B5) — additive, 뷰어 키는 그대로
        out["oracle"] = self.oracle_get()          # D61 신탁 소켓 — 대기 중인 요청(없으면 None), additive
        path = os.path.join(self.state_dir, "stream.jsonl")
        if os.path.exists(path):
            try:
                with io.open(path, encoding="utf-8", errors="replace") as f:   # F5(09-18) 러너가 쓰는 중인 마지막 줄은 한글이 반 토막일 수 있다 — 그 줄은 아래 json 에서 걸러진다
                    lines = f.read().splitlines()
            except OSError:
                lines = []
            if lines:
                try:
                    meta = json.loads(lines[0])
                    if meta.get("kind") == "run_meta":
                        out["seed"] = meta.get("seed")
                        out["mode"] = ("standard" if meta.get("ruleset") == "skills-v1" else
                                       "alpha" if meta.get("alpha") else "classic")
                        out["action_mode"] = meta.get("action_mode", "menu" if meta.get("menu") else "free")
                        out["party"] = [{"char": p.get("char"), "name": p.get("name") or p.get("job"),
                                         "job": p.get("job")} for p in meta.get("party", [])]
                except ValueError:
                    pass
                for ln in reversed(lines):
                    try:
                        o = json.loads(ln)
                    except ValueError:
                        continue
                    if o.get("kind") == "end":
                        out["outcome"] = o.get("outcome")
                    if o.get("kind") == "tick":
                        out["turn"] = o.get("turn")
                        break
        paused = run_control.read_json(os.path.join(self.state_dir, run_control.PAUSE_FILE))
        out["brain_pause"] = paused if out["running"] and paused.get("pid") == out["pid"] else None
        out["stopping"] = bool(out["running"] and run_control.stop_requested(self.state_dir))   # D79 곱게 멈추는 중(수첩을 쓰는 중) — additive
        out["resume"] = self.resumable(out)                                                     # D79 이어갈 몸(멈춘 판 요약) — additive
        return out

    def retry(self, pause_id):
        with self.lock:
            if not self.running():
                raise Conflict("진행 중인 원정이 없다")
            try:
                run_control.request_retry(self.state_dir, pause_id, self.proc.pid)
            except ValueError as error:
                raise Conflict(str(error)) from error
            return {"ok": True}


class Ctx:
    def __init__(self, root, party_path, state_dir, runs_dir, brain=None):
        self.root, self.party_path = root, party_path
        self.state_dir, self.runs_dir = state_dir, runs_dir
        self.default_brain = brain
        self.runner = Runner(root, state_dir, runs_dir)
        self.presets = sheetkit.load_traits()
        # 커스텀 파티와 같은 위치에 보관한다. 임시 검토·검증 서버의 저장소도 함께 격리된다.
        self.characters = PresetStore(os.path.join(os.path.dirname(os.path.abspath(party_path)),
                                                  "character_presets.json"), self.presets)
        self.campaign = campaign.Book(os.path.join(os.path.dirname(os.path.abspath(party_path)),
                                                 "campaign.json"))          # D78 저장 캐릭터별 원정 기록(같은 폴더)

    def campaign_refresh(self):
        """현재 판(state)과 runs/ 아카이브를 캠페인에 접는다(마지막 줄까지 · 아카이브는 한 번씩). 실패해도 목록은 산다."""
        try:
            self.campaign.refresh(os.path.join(self.state_dir, "stream.jsonl"), self.runs_dir, self.runner.running())
            return self.campaign
        except (OSError, ValueError):
            return None


def _preview_look(look):
    """기본 파티 시트의 외형 → 화면 미리보기용. 러너와 같은 검증기(sanitize_look)를 거친 값만 싣는다 — 시트에 없거나 깨졌으면 None
    (그 판의 외형은 러너가 시드로 뽑는다 — 화면은 '랜덤'이라고 말한다)."""
    try:
        return sheetkit.sanitize_look(look)
    except (ValueError, OSError):
        return None


def default_party_preview(root):
    """party.json 미리보기 — 검증은 러너 몫이라 여기선 읽기만(메타 키 제외). look(09-20) = 시트에 적힌 외형(없으면 None)."""
    try:
        with io.open(os.path.join(root, "party.json"), encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for c in sorted(k for k in raw if not str(k).startswith("_")):
        s = raw[c]
        if isinstance(s, dict):
            out.append({"char": c, "name": s.get("name") or ("모험가 %s" % c), "job": s.get("job"),
                        "sex": s.get("sex"), "persona": s.get("persona"), "speech": s.get("speech"),
                        "goal": s.get("goal"), "look": _preview_look(s.get("look")),
                        "prompt_chars": sum(len(str(s.get(k) or "")) for k in ("persona", "background", "speech", "goal"))})
    return out


def companions_payload(data=None):
    """D81 동료 프리셋 목록 — 화면의 동료 칸이 읽는다. 시트 조립을 거친 값만 싣는다(화면에 보인 것 = 판에 서는 것).
    about = 정의의 소개 한 줄(story.trait). 정의가 깨졌으면 빈 목록(론처는 산다 — 이유는 엔티티 게이트가 말한다)."""
    try:
        defs = entities.companions()
    except (entities.EntityError, OSError, ValueError):
        return []
    out = []
    for cid, d in defs.items():
        s = sheetkit.build_companion_sheet(d, data=data)
        out.append({"id": cid, "name": s["name"], "job": s["job"], "sex": s["sex"], "persona": s["persona"],
                    "speech": s.get("speech"), "goal": s.get("goal"), "background": s.get("background"),
                    "about": (d["comps"].get("story") or {}).get("trait"), "look": s.get("look"),
                    "prompt_chars": sum(len(str(s.get(k) or "")) for k in ("persona", "background", "speech", "goal"))})
    return out


def presets_payload(ctx):
    """GET /api/presets 본문 — 론처 화면이 처음 읽는 것(키워드·직업·외형·기본 파티·모드·상한·상태). server.py 가 재사용."""
    p = ctx.presets
    return {"traits": p["traits"], "max_traits": p["max_traits"], "jobs": p["jobs"],
            "looks": sheetkit.load_looks(),   # D37(09-06) 외형 사전 — 파츠·스와치·기본색
            "default_party": default_party_preview(ctx.root),
            "companions": companions_payload(p),   # D81 동료 프리셋(파티 2·3번 칸의 선택지) — additive
            "skill_alpha": {"presets": skill_schema.PRESETS,
                            "default_sets": skill_schema.DEFAULT_SETS},
            "default_mode": "standard", "ruleset": "skills-v1",
            "brain_failure_policy": run_control.POLICY,
            "model_ui_version": 2,
            "party_ui_version": 1,                 # D81 한 장 화면(내 캐릭터 + 동료 칸)이 기대는 서버 — 화면은 이 값이 없으면 '이전 런처' 안내를 띄운다
            "options_ui_version": OPTIONS_UI_VERSION,   # 09-20 시작 옵션의 판 번호 — 새 맵·새 스위치를 모르는 옛 서버면 화면이 '이전 런처' 안내를 띄운다
            "night_defaults": dict(NIGHT_DEFAULTS),     # 09-20 고급 설정 체크박스(09-20 추가분)의 첫 자리(화면에는 값이 없다 — 여기 한 곳)
            "old_defaults": dict(OLD_DEFAULTS),         #   '09-20 추가 전으로' 버튼이 돌아가는 자리(그 스위치들만 끔 — 맵은 화면에 없다)
            "map_default": MAP_DEFAULT,                 #   판이 늘 뜨는 맵(09-20 오후부터 화면에 고르는 자리가 없다 — 화면은 이 이름을 읽어 사실을 적는다)
            "text_limits": TEXT_LIMITS,
            "custom_saved": os.path.exists(ctx.party_path),
            "default_brain": ctx.default_brain or "gemini_api",
            "providers": provider_catalog(),
            "model_defaults": {p: model_id(p, "haiku") for p in HTTP_BACKENDS},
            "status": ctx.runner.status()}


def save_party(ctx, slots, preset_ids=None):
    """슬롯 → sheetkit 조립 → 파일 → 러너의 load_party 로 재검증(이중 검증). 실패는 BadRequest 한 줄.
    preset_ids(D78): 슬롯과 같은 순서의 저장 캐릭터 id — **이 저장소에 있는 id 만** 시트에 붙는다(남의 id·지어낸 id 는 1회용으로)."""
    try:
        comps = (entities.companions() if isinstance(slots, (list, tuple)) and
                 any(isinstance(s, dict) and s.get("companion") is not None for s in slots) else None)
        sheets = sheetkit.build_party(slots, data=ctx.presets, companions=comps)   # D81 동료 칸({"companion": id})은 저장소 정의에서 조립
    except (ValueError, entities.EntityError) as e:
        raise BadRequest(str(e))
    ids = list(preset_ids) if isinstance(preset_ids, (list, tuple)) else []
    if any(isinstance(x, str) and x for x in ids):
        try:
            saved = {p["id"] for p in ctx.characters.list()}
        except (OSError, ValueError):
            saved = set()
        for i, char in enumerate(sorted(sheets, key=int)):
            pid = ids[i] if i < len(ids) else None
            if isinstance(pid, str) and pid in saved:
                sheets[char] = {**sheets[char], "id": pid}
    sheetkit.write_party(sheets, ctx.party_path)
    import show_runner                                # 지연 import — 러너 모듈의 검증기를 그대로 쓴다
    with io.StringIO() as err:
        old = sys.stderr
        sys.stderr = err
        try:
            loaded = show_runner.load_party(ctx.party_path)
        finally:
            sys.stderr = old
        warn = err.getvalue()
    if "폴백" in warn or sorted(loaded) != sorted(sheets):
        try:
            os.remove(ctx.party_path)
        except OSError:
            pass
        raise BadRequest("러너 검증 실패: %s" % (warn.strip().splitlines()[-1] if warn.strip() else "시트 불일치"))
    return {"ok": True, "path": os.path.basename(ctx.party_path),
            "party": [{"char": c, "name": s["name"], "job": s["job"], "traits": s["traits"]}
                      for c, s in sorted(sheets.items())]}


class Handler(SimpleHTTPRequestHandler):
    """정적 서빙(뷰어·runs/ 자동 색인 그대로) + /api/*."""

    def __init__(self, *args, ctx=None, **kwargs):
        self.ctx = ctx
        super().__init__(*args, directory=ctx.root, **kwargs)

    # ── 유틸 ──
    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 256 * 1024:                      # 3인 × 긴 성격·배경, JSON 유니코드 이스케이프까지 수용
            raise BadRequest("요청이 너무 크다")
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise BadRequest("JSON 이 아니다")
        if not isinstance(obj, dict):
            raise BadRequest("JSON 객체가 아니다")
        return obj

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/") and not self.path.startswith("/api/status"):
            sys.stderr.write("[launcher] %s\n" % (fmt % args))

    def end_headers(self):
        if self.path.startswith("/state/") or self.path.startswith("/runs/") or self.path.startswith("/launcher/"):
            self.send_header("Cache-Control", "no-store")   # 라이브 스트림·론처 페이지는 캐시 금지(09-11: 옛 론처 화면이 남아 마을 체크가 회색으로 보인 사고)
        elif urlparse(self.path).path in GAME_NO_STORE:
            self.send_header("Cache-Control", "no-store")   # 게임 클라이언트 진입 HTML — 새 빌드가 바로 보이게(해시 자산은 기본 캐시)
        elif self.path.startswith("/viewer/"):
            # 론처·관전이 같이 쓰는 스프라이트 합성기(sprites.js)·외형 사전(atlas.json)·시트 PNG — 파일 이름에 해시가 없다.
            # 캐시 지시가 없으면 브라우저가 옛 sprites.js 를 제 판단으로 계속 쓰고, 캐시 금지인 론처 화면(새 HTML)과 섞인다
            # (09-19 "WLSprites.defaultHair is not a function" — 새 화면이 옛 스크립트에 없는 함수를 불렀다).
            # no-cache = 저장은 하되 쓸 때마다 서버에 물어본다(안 바뀌었으면 304 — 그림을 다시 내려받지 않는다).
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    # ── 게임 클라이언트(M3/B5) — /game/… 을 game/dist/… 로 ──
    def translate_path(self, path):
        """/game/<x> → <root>/game/dist/<x>. 나머지는 그대로(뷰어·runs·state 서빙 불변). 접두만 바꾸고
        따옴표 풀기·'..' 걸러내기·index.html 선택은 부모 구현이 그대로 맡는다."""
        if path.startswith(GAME_PREFIX):
            path = GAME_DIST_PREFIX + path[len(GAME_PREFIX):]
        return super().translate_path(path)

    def _game_missing(self):
        """빌드 산출물이 없다 — 503 + 한글 안내 한 장(정적 404 대신 이유를 말한다)."""
        body = ("<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>게임 클라이언트 빌드 없음</title>"
                "<style>body{background:#0f1115;color:#d8dee9;font:15px/1.6 system-ui,sans-serif;padding:40px}"
                "code{background:#1c2028;padding:2px 6px;border-radius:4px}</style></head><body>"
                "<h1>게임 클라이언트 빌드가 없다</h1>"
                "<p><code>game/dist/index.html</code> 이 없다. 리포에서 한 번 빌드하면 이 주소(/game/)로 열린다:</p>"
                "<p><code>cd game &amp;&amp; npm install &amp;&amp; npm run build</code></p>"
                "<p>그동안은 <a href=\"/viewer/?run=state/stream.jsonl\">기존 뷰어</a>로 관전할 수 있다.</p>"
                "</body></html>").encode("utf-8")
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── 라우팅 ──
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/characters":
            try:
                presets = self.ctx.characters.list()
                book = self.ctx.campaign_refresh()            # D78 저장 캐릭터별 원정 기록 요약 — 항목은 그대로 두고 별도 키(additive)
                camp = {p["id"]: book.summary(p["id"]) for p in presets} if book else {}
                camp = {k: v for k, v in camp.items() if v}
                return self._json(200, {"presets": presets, **({"campaign": camp} if camp else {})})   # 기록 있을 때만 붙는다(옛 응답 모양 유지)
            except (OSError, ValueError) as e:
                return self._json(500, {"error": str(e)})
        if path == "/api/characters/log":               # D78 한 캐릭터의 원정 기록(수첩 장·도감평·함께 간 동료)
            from urllib.parse import parse_qs
            pid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
            book = self.ctx.campaign_refresh()
            return self._json(200, {"id": pid, "runs": book.runs(pid) if book else []})
        if path == "/api/presets":
            return self._json(200, presets_payload(self.ctx))
        if path == "/api/oracle":                        # D61 신탁 소켓 — 현재 요청
            return self._json(200, {"oracle": self.ctx.runner.oracle_get()})
        if path == "/api/status":
            return self._json(200, self.ctx.runner.status())
        if path.startswith("/api/"):
            return self._json(404, {"error": "없는 API"})
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/launcher/")
            self.end_headers()
            return
        if path == "/game":                           # 게임 클라이언트(M3/B5) — 슬래시 없는 진입은 /game/ 으로(쿼리 보존)
            q = urlparse(self.path).query
            self.send_response(302)
            self.send_header("Location", GAME_PREFIX + ("?" + q if q else ""))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path.startswith(GAME_PREFIX) and not os.path.isfile(os.path.join(self.directory, "game", "dist", "index.html")):
            return self._game_missing()
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/characters":
                try:
                    entry = self.ctx.characters.save(body.get("slot"), body.get("label"), body.get("id"))
                except ValueError as e:
                    raise BadRequest(str(e)) from e
                return self._json(200, {"preset": entry})
            if path == "/api/characters/delete":
                try:
                    self.ctx.characters.delete(body.get("id"))
                except ValueError as e:
                    raise BadRequest(str(e)) from e
                return self._json(200, {"ok": True})
            if path == "/api/party":
                return self._json(200, save_party(self.ctx, body.get("slots") or [], body.get("preset_ids")))
            if path == "/api/start":
                return self._json(200, self.ctx.runner.start(body, self.ctx.party_path, self.ctx.default_brain))
            if path == "/api/retry":
                return self._json(200, self.ctx.runner.retry(body.get("pause_id")))
            if path == "/api/oracle":                    # D61 신탁 소켓 — {"text": "…"} (빈 문자열 = 거둠)
                return self._json(200, self.ctx.runner.oracle_set(body.get("text") or ""))
            if path == "/api/stop":
                return self._json(200, self.ctx.runner.stop(graceful=bool(body.get("graceful")),   # D79 {graceful, pages}
                                                            pages=body.get("pages", True) is not False))
            return self._json(404, {"error": "없는 API"})
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        except Conflict as e:
            return self._json(409, {"error": str(e)})
        except Exception as e:                        # 서버가 죽지 않게 — 이유는 한 줄로 돌려준다
            return self._json(500, {"error": "%s: %s" % (type(e).__name__, e)})


def make_server(host, port, root=HERE, party_path=None, state_dir=None, runs_dir=None, brain=None):
    ctx = Ctx(root, party_path or os.path.join(root, "party_custom.json"),
              state_dir or os.path.join(root, "state"), runs_dir or os.path.join(root, "runs"), brain)
    srv = LauncherServer((host, port), partial(Handler, ctx=ctx))
    srv.daemon_threads = True
    srv.ctx = ctx
    return srv


def main():
    ap = argparse.ArgumentParser(description="봇픽던 웹 론처 — 파티 꾸미기·시작·관전을 한 창에서")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--alpha", action="store_true", help="이전 배치 메뉴 호환용. 스킬 원정은 이제 기본이다")
    a = ap.parse_args()
    url = "http://%s:%d/launcher/" % (a.host, a.port) + ("?mode=alpha" if a.alpha else "")
    # 메뉴를 다시 골랐을 때 기존 서버를 연다. 바인드 전에 확인해야 Windows에서도 중복 실행을 막는다.
    # 09-20: 시작 옵션의 판 번호도 같아야 다시 쓴다 — 코드를 고친 뒤 bat 을 다시 눌러도 떠 있던 옛 론처(옛 MAPS)가 새 화면(캐시 금지라
    # 늘 새 HTML)에 응답하면, 화면이 보낸 새 맵을 옛 서버가 400 으로 거절한다. 번호가 다르면 아래 바인드가 실패해 '그 창을 닫고 다시' 안내가 나간다.
    try:
        with urlopen("http://%s:%d/api/presets" % (a.host, a.port), timeout=2) as response:
            existing = json.load(response)
        if (existing.get("ruleset") == "skills-v1" and existing.get("text_limits") == TEXT_LIMITS
                and existing.get("brain_failure_policy") == run_control.POLICY
                and existing.get("options_ui_version") == OPTIONS_UI_VERSION):
            print("[launcher] 기존 서버에서 연다: " + url)
            if not a.no_browser:
                webbrowser.open(url)
            return 0
    except (OSError, ValueError):
        pass
    try:
        srv = make_server(a.host, a.port)
    except OSError as e:
        print("[launcher] %s:%d 를 열 수 없다(%s) — 이전 런처/뷰어 서버가 떠 있다면 "
              "진행 중인 원정이 끝난 뒤 그 창을 닫고 다시 실행해 주세요." % (a.host, a.port, e), file=sys.stderr)
        return 1
    print("[launcher] %s  (Ctrl-C 로 종료 — 진행 중인 판도 함께 멈춘다)" % url)
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.ctx.runner.stop()
        srv.server_close()
    return 0


if __name__ == "__main__":
    import envload
    envload.load()          # show_runner 와 같은 규칙 — __main__ 안에서만(게이트는 안 밟는다)
    raise SystemExit(main())
