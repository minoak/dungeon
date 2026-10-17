# -*- coding: utf-8 -*-
"""p0.5.22 성격 키워드 → 캐릭터 특성(DECISIONS 10-17 '특성 격상'·'두 기능'·'대식가 = 덜 찬다' · 설계 초안 .orch/drafts/trait_design_v0.md) — 헤들리스 검증. LLM 0콜.
게이트:
  ① 저장소 꼴: entities/trait 31장(초안 §4 전부 — 옛 키워드 12 + 새 19) · 이름 = 옛 키워드 글자 그대로 · 반대 짝 8쌍(서로 가리킨다) · 효과는 대식가(fill)·미식가·소박한(기분 조각 %)·
     수다스러운↔과묵한·호기심 많은·충직한(준비 중 욕구 등급) · p0.5.23 낙천적인↔냉소적인(기분 기본값 ±5)뿐 · traits.json 은 직업만 · 시트 조립 표(가나다순·반대 짝·최대 3) ·
     동료 프리셋·기본 파티의 특성은 그대로(비어 있다) · 검증기가 잘못된 특성 정의를 한 번에 거절한다
  ② 반대 짝 거절: 시트 조립(8쌍 × 양 순서)·파티 조립·저장 캐릭터 · 반대가 아닌 조합은 받는다 · 화면(반대 짝 잠금 · 이름 '특성' · '입맛' 상자)
  ③ 이름 바이트 동일: 옛 키워드 시트의 성격 줄 = 이름 그대로(', ' · '. ' 규칙) · 러너 판의 완성 프롬프트에 그 줄이 그대로 · 특성 id·배율은 어디에도 없다
  ④ 대식가: 채우는 양만 70%(무게 등급 fill 과 같은 길 — 높음 70% 와 곱해 49%) · 배고파지는 빠르기·기분 시간은 그대로
  ⑤ 미식가·소박한: 먹은 뒤 기분 조각의 크기(미식가 좋아함·싫어함 150% · 소박한 전부 50%) · 기본 갈래·단계가 주는 기분·조각 시간은 그대로
  ⑥ 겹침 규칙: 배율은 곱(정수 %로 반올림) · 등급은 모두 같으면 그 등급, 다르면 보통 · 같은 이름은 한 번 · 모르는 이름은 건너뜀
  ⑦ 준비 중 무시: 사교·호기심·애정 등급은 정의에만 — 몸에 무게·배율이 없고 판이 특성 없는 몸과 똑같이 돈다
  ⑧ 숫자 누설 없음: 몸의 trait_fx 는 공개 투영의 관전 칸 · 관측·봇 스냅샷·완성 프롬프트에 배율·id 없음 · run_meta.party[].trait_ids 는 남는다
  ⑨ 이관: presets 2→3(needs·needs_meta 걷음 · taste 그대로 · 반대 짝 둘 다면 먼저 고른 쪽) · party 1→2(같은 걷음 · 특성 그대로) · 옛 파일을 저장소·러너가 그대로 읽는다 ·
     p0522b 스냅샷 11→12(시트의 needs·needs_meta 걷음 · 몸마다 무게·배율을 특성으로 다시 — 지금 세계·다른 세계·부활 대기 · 다시 올려도 같다)
  ⑪ p0522b 동료 프리셋의 입맛(p0.5.20 칸): 검증기가 받고(어휘 밖이면 거절) 시트·론처 동료 목록·파티 조립에 실린다
  ⑩ 배선: 욕구 생성 호출(need_gen)은 없다 · _run_gates.sh · VERSION · STREAM_FORMAT · PATCH_NOTES
  ⑫ p0.5.23 낙천적인 ↔ 냉소적인(DECISIONS 10-17 '림월드식 B'): 기분 기본값만이면 '기분:' 줄 없음 · 다른 이유와 합산(문턱 그대로 — 줄이 생기고·사라지고·뒤집힌다) ·
     이유 낱말에 안 나온다(이유는 조각에서만) · 겹침(같은 이름 한 번 · 여러 특성 더함) · 검증기(0·참거짓·상한 밖) · 관전 합(mood_now·need_mood sum)엔 들어간다 ·
     숫자 누설 없음(관측 낱말·공개 투영) · 몸에 칸이 없다(이어간 v0.5.22 판도 이관 없이 같은 합) · 배선(VERSION·PATCH_NOTES·STREAM_FORMAT)
"""
import contextlib
import copy
import io
import json
import os
import pickle
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_traits_")
PARTY = os.path.join(TMP, "party_traits.json")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_SEED="11",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0", DUNGEON_DEPTHS="1",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_STEP_DELAY="0", DUNGEON_PARTY_FILE=PARTY,
                  DUNGEON_STATE_DIR=os.path.join(TMP, "state"), DUNGEON_BRAIN_BACKEND="dummy")
for k in ("DUNGEON_RESUME", "DUNGEON_RUNS_DIR", "DUNGEON_STREAM_OBS", "DUNGEON_TOWN", "DUNGEON_BOSS", "DUNGEON_START"):
    os.environ.pop(k, None)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import brains                                        # noqa: E402
SENT = []                                            # LLM 에 간 글 전부(③·⑧)
brains._call_claude = lambda prompt, model="haiku": (SENT.append(prompt), "")[1]   # 0콜 — 빈 응답이면 dummy 폴백
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import info_guard as IG                              # noqa: E402
import launcher                                      # noqa: E402
import needs as NE                                   # noqa: E402
import savedata                                      # noqa: E402
import sheetkit                                      # noqa: E402
import show_runner as R                              # noqa: E402
import snapshot                                      # noqa: E402
from character_presets import PresetStore            # noqa: E402
R.STEP_DELAY = 0


class C:
    failed = 0
    n = 0


def check(name, ok, detail=""):
    C.n += 1
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:400]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with io.open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


def jw(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def rejects(fn):
    try:
        fn()
    except ValueError as e:
        return str(e)
    return None


OLD_KEYWORDS = ["호기심 많은", "신중한", "용맹한", "과묵한", "수다스러운", "겁 많은", "탐욕스러운", "충직한",   # v0.5.21 traits.json 의 traits 목록 글자 그대로
                "냉소적인", "낙천적인", "의심 많은", "명예를 중시하는"]
NEW_NAMES = ["대식가", "미식가", "소박한", "근면한", "게으른", "친절한", "무뚝뚝한", "침착한", "성급한", "겸손한", "허영심 많은",   # 초안 §4 의 새 후보
             "강인한", "예민한", "고집 센", "질투 많은", "덜렁대는", "야행성", "외로움을 타는", "혼자가 편한"]
PAIRS = [("수다스러운", "과묵한"), ("낙천적인", "냉소적인"), ("용맹한", "겁 많은"), ("근면한", "게으른"), ("친절한", "무뚝뚝한"),
         ("침착한", "성급한"), ("겸손한", "허영심 많은"), ("외로움을 타는", "혼자가 편한")]
DATA = sheetkit.load_traits()
DEFS0 = ENT.load()
BY = ENT.trait_by_name()


def comp(name):
    return BY[name]["comps"]["trait"]


# ─────────────────────────────────────────────────────────────────────────────
print("── ① 저장소 꼴")
check("① entities/trait 31장 = 옛 키워드 12(글자 그대로) + 초안 §4 새 후보 19 · kind trait · 이름이 곧 열쇠(서로 다르다)",
      sorted(BY) == sorted(OLD_KEYWORDS + NEW_NAMES) and len(ENT.by_kind("trait")) == 31
      and all(d["kind"] == "trait" and os.path.exists(os.path.join(ENT.ROOT, "trait", d["id"] + ".json")) for d in BY.values()),
      sorted(set(BY) ^ set(OLD_KEYWORDS + NEW_NAMES)))
opp_got = sorted(tuple(sorted((n, DATA["opposites"][n]))) for n in DATA["opposites"])
check("① 반대 짝 8쌍(↔ — 서로 가리킨다) · 나머지는 짝 없음",
      set(OLD_KEYWORDS + NEW_NAMES) <= set(BY) and opp_got == sorted(tuple(sorted(p)) for p in PAIRS for _ in (0, 1))
      and all(BY[b]["id"] == comp(a).get("opposite") and BY[a]["id"] == comp(b).get("opposite") for a, b in PAIRS)
      and sum(1 for n in BY if comp(n).get("opposite")) == 16, opp_got)
if C.failed:                                         # 저장소·조립 표가 틀리면 뒤 검사는 뜻이 없다(이름으로 찾는 자리가 깨진다) — 여기서 멈춘다
    print("\nFAIL — %d/%d (특성 저장소·조립 표가 틀려 뒤 검사를 건너뛴다)" % (C.failed, C.n))
    sys.exit(1)
EFF = {n: comp(n).get("effects") for n in BY if comp(n).get("effects")}
check("① 효과: 대식가 배고픔 fill 70 · 미식가 좋아함·싫어함 150 · 소박한 셋 다 50 · 수다스러운 사교 높음 ↔ 과묵한 낮음 · 호기심 많은 호기심 높음 · 충직한 애정 높음 · "
      "p0.5.23 낙천적인 기분 기본값 +5 ↔ 냉소적인 −5 — 그 밖은 글만",
      EFF == {"대식가": {"need": {"hunger": {"fill": 70}}},
              "미식가": {"need": {"hunger": {"mood": {"like": 150, "dislike": 150}}}},
              "소박한": {"need": {"hunger": {"mood": {"like": 50, "plain": 50, "dislike": 50}}}},
              "수다스러운": {"need": {"social": {"level": "높음"}}}, "과묵한": {"need": {"social": {"level": "낮음"}}},
              "호기심 많은": {"need": {"curiosity": {"level": "높음"}}}, "충직한": {"need": {"affection": {"level": "높음"}}},
              "낙천적인": {"mood": 5}, "냉소적인": {"mood": -5}}, EFF)
tj = json.loads(src("traits.json"))
check("① traits.json 은 직업만(옛 traits·max_traits 칸 없음) · 시트 조립 표 = 특성 이름 가나다순 · 반대 짝 · 최대 3(sheetkit.MAX_TRAITS) · 이름→id",
      "traits" not in tj and "max_traits" not in tj and set(tj) == {"_readme", "jobs"}
      and DATA["traits"] == sorted(BY) and DATA["max_traits"] == sheetkit.MAX_TRAITS == 3
      and DATA["trait_ids"] == {n: d["id"] for n, d in BY.items()} and list(DATA["jobs"]) == ["전사", "도적", "궁수", "마법사"])
party_json = json.loads(src("party.json"))
check("① 동료 프리셋 셋·기본 파티의 특성은 바꾸지 않았다(비어 있는 채로 — 민옥이 정함)",
      all(d["comps"]["sheet"].get("traits") == [] for d in ENT.companions().values()) and len(ENT.companions()) == 3
      and not any("traits" in s for k, s in party_json.items() if not k.startswith("_")))
# 검증기 거절 — 리포 정의 사본 + 나쁜 특성 정의들
ROOT_V = os.path.join(TMP, "ents")
shutil.copytree(ENT.ROOT, ROOT_V)
jw(os.path.join(ROOT_V, "need", "test_thirst.json"), {"id": "test_thirst", "name": "목마름", "kind": "need", "tags": ["need"],
                                                     "comps": {"need": {"start": 50, "decay": 2, "full_at": 90, "full_blocks": False,
                                                                        "stages": {"normal": {"min": 0, "word": "보통"}},
                                                                        "mood": {"plain": {"time": 10, "mood": 4, "why": "물을 마심"}}}}})
BAD = {"t_key": {"trait": {"wat": 1}}, "t_lvl": {"trait": {"effects": {"need": {"hunger": {"level": "보통"}}}}},
       "t_fill": {"trait": {"effects": {"need": {"hunger": {"fill": 0}}}}}, "t_mood": {"trait": {"effects": {"need": {"hunger": {"mood": {"great": 150}}}}}},
       "t_eff": {"trait": {"effects": {"combat": {"atk": 1}}}}, "t_ghost": {"trait": {"opposite": "nope"}},
       "t_oneway": {"trait": {"opposite": "brave"}}, "t_self": {"trait": {"opposite": "t_self"}},
       "t_need": {"trait": {"effects": {"need": {"thirst": {"level": "높음"}}}}}, "t_ready": {"trait": {"effects": {"need": {"social": {"fill": 50}}}}},
       "t_branch": {"trait": {"effects": {"need": {"test_thirst": {"mood": {"like": 150}}}}}}, "t_none": {"story": {"trait": "x"}},
       "t_m0": {"trait": {"effects": {"mood": 0}}}, "t_mbool": {"trait": {"effects": {"mood": True}}}, "t_mbig": {"trait": {"effects": {"mood": -101}}},   # p0.5.23 기분 기본값
       "t_mstr": {"trait": {"effects": {"mood": "5"}}}, "t_empty": {"trait": {"effects": {}}}}
NAMES_V = {"t_key": "가", "t_lvl": "나", "t_fill": "다", "t_mood": "라", "t_eff": "마", "t_ghost": "바", "t_oneway": "사", "t_self": "아",
           "t_need": "자", "t_ready": "차", "t_branch": "카", "t_none": "타", "t_m0": "파", "t_mbool": "하", "t_mbig": "거", "t_mstr": "너", "t_empty": "더"}
for tid, cps in BAD.items():
    jw(os.path.join(ROOT_V, "trait", tid + ".json"), {"id": tid, "name": NAMES_V[tid], "kind": "trait", "tags": ["trait"], "comps": cps})
for tid, nm in (("t_comma", "용감하고, 착한"), ("t_long", "가" * 21), ("t_dup", "신중한")):
    jw(os.path.join(ROOT_V, "trait", tid + ".json"), {"id": tid, "name": nm, "kind": "trait", "tags": ["trait"], "comps": {"trait": {}}})


def mate(cid, name, taste):                          # p0522b 동료 프리셋의 입맛 칸(p0.5.20 — 데이터에 적은 대로)
    return {"id": cid, "name": name, "kind": "companion", "tags": ["companion"],
            "comps": {"sheet": {"job": "전사", "sex": "남", "traits": ["대식가"], "persona": "조용하다.", "taste": taste}}}


MATE_OK = mate("c_taste_ok", "맛보기", {"likes": ["고기", "빵"], "dislikes": ["과일"]})
jw(os.path.join(ROOT_V, "companion", "c_taste_ok.json"), MATE_OK)
jw(os.path.join(ROOT_V, "companion", "c_taste_bad.json"), mate("c_taste_bad", "쓴맛", {"likes": ["초콜릿"], "dislikes": []}))
try:
    ENT.read(ROOT_V)
    msg = ""
except ENT.EntityError as e:
    msg = str(e)
WANT = ("t_key.json: trait 가 모르는 칸 ['wat']", "t_lvl.json: trait.effects.need.hunger.level 은 낮음|높음", "t_fill.json: trait.effects.need.hunger.fill 은 정수 1~",
        "t_mood.json: trait.effects.need.hunger.mood 는", "t_eff.json: trait.effects 는", "t_ghost.json: trait.opposite 'nope' 는",
        "t_oneway.json: trait.opposite 'brave' 는", "t_self.json: trait.opposite 't_self' 는", "t_need.json: trait.effects.need 의 'thirst' 는 욕구 정의가 아니다",
        "t_ready.json: trait.effects.need.social — 단계가 없는(준비 중) 욕구엔 level 만", "t_branch.json: trait.effects.need.test_thirst.mood 의 'like' 는",
        "t_none.json: 엔진이 모르는 부품 'story'", "t_none.json: trait 부품(객체)이 있어야 한다", "t_comma.json: 특성 이름은", "t_long.json: 특성 이름은",
        "특성 이름 '신중한' 중복", "c_taste_bad.json: sheet — taste 칸이 검증기를 지나며 달라진다",
        "t_m0.json: trait.effects.mood 는 0 이 아닌 정수", "t_mbool.json: trait.effects.mood 는 0 이 아닌 정수", "t_mbig.json: trait.effects.mood 는 0 이 아닌 정수",
        "t_mstr.json: trait.effects.mood 는 0 이 아닌 정수", "t_empty.json: trait.effects 는")
check("① 검증기 거절 22종을 한 번에 — 모르는 칸·보통 등급·채움 0·모르는 갈래·모르는 효과·없는 반대·한쪽만 가리키는 반대·자기 자신·없는 욕구·준비 중 욕구의 fill·"
      "그 욕구에 없는 갈래·trait 부품 없음·쉼표 이름·21자 이름·이름 중복 · p0522b 동료 입맛의 어휘 밖 꼬리표 · p0.5.23 기분 기본값 0·참거짓·상한 밖·글 · 빈 효과",
      all(w in msg for w in WANT), [w for w in WANT if w not in msg] or msg[:300])
check("① p0522b 동료 프리셋의 입맛 칸(p0.5.20 — 어휘 안)은 받는다(그 정의의 오류 줄이 없다 · 특성 이름도 그대로)", "c_taste_ok.json" not in msg, msg[:300])
check("① 정본 폴더는 그대로 읽힌다(나쁜 사본이 정본을 흔들지 않는다)", set(ENT.reload()) == set(DEFS0))
DEFS0 = ENT.load()

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 반대 짝 거절")
bad_pairs = [(a, b) for a, b in PAIRS for x, y in ((a, b), (b, a))
             if not (rejects(lambda: sheetkit.build_sheet("전사", [x, y], "가", "남")) or "").startswith("반대 특성은 같이 고를 수 없다")]
check("② 시트 조립: 반대 짝 8쌍 × 양 순서 전부 거절('반대 특성은 같이 고를 수 없다: …') · 사이에 다른 특성이 끼어도", not bad_pairs
      and (rejects(lambda: sheetkit.build_sheet("전사", ["수다스러운", "신중한", "과묵한"], "가", "남")) or "").endswith("수다스러운 · 과묵한"), bad_pairs)
ok_combo = sheetkit.build_sheet("전사", ["미식가", "소박한", "대식가"], "가", "남")
check("② 반대가 아닌 조합은 받는다(미식가·소박한은 짝이 아니다 — 겹침 규칙으로 합친다) · 최대 3 · 모르는 이름 거절",
      ok_combo["traits"] == ["미식가", "소박한", "대식가"] and ok_combo["persona"] == "미식가, 소박한, 대식가"
      and rejects(lambda: sheetkit.build_sheet("전사", ["미식가", "소박한", "대식가", "신중한"], "가", "남"))
      and (rejects(lambda: sheetkit.build_sheet("전사", ["사악한"], "가", "남")) or "").startswith("등재되지 않은 특성"))
check("② 파티 조립·저장 캐릭터도 같은 검증(시트 조립기 하나) — 반대 짝은 거절",
      rejects(lambda: sheetkit.build_party([{"job": "도적", "traits": ["용맹한", "겁 많은"], "name": "가", "sex": "여"}]))
      and rejects(lambda: PresetStore(os.path.join(TMP, "p_reject.json"), DATA).save({"job": "도적", "traits": ["친절한", "무뚝뚝한"], "name": "가", "sex": "여"}))
      and not os.path.exists(os.path.join(TMP, "p_reject.json")))
html = src("launcher", "index.html")
check("② 화면: 이름 '특성'('성격 키워드' 없음) · 반대 짝을 고르면 다른 쪽이 잠긴다(presets.opposites — 고를 수 없고 꺼진 칩) · '입맛' 상자(고르기만) · 욕구 등급 고르기·생성 호출 없음",
      '<label class="f">특성 <span class="cnt" data-cnt="traits">' in html and "성격 키워드" not in html
      and "const opp = presets.opposites || {};" in html and "const locked = v => s.traits.includes(opp[v]);" in html
      and "(s.traits.length >= presets.max_traits || locked(v))" in html and "else if (s.traits.length < presets.max_traits && !locked(v)) s.traits.push(v);" in html
      and "<summary>입맛</summary>" in html and 'data-taste-box' in html and "presets.taste_ui" in html
      and not any(t in html for t in ("needs_ui", "/api/needs", "data-needs", "needs_meta", "욕구와 입맛", "brainChoice", "다시 정하기")))
CTX = launcher.Ctx(HERE, os.path.join(TMP, "lp", "party_custom.json"), os.path.join(TMP, "lp", "state"), os.path.join(TMP, "lp", "runs"))
PL = launcher.presets_payload(CTX)
check("② /api/presets 본문: traits = 특성 이름 · opposites = 반대 짝 · taste_ui = 입맛 어휘·상한(욕구 정의에서) · 0.5.20 needs_ui 는 없다",
      PL["traits"] == DATA["traits"] and PL.get("opposites") == DATA["opposites"] and DATA["opposites"].get("과묵한") == "수다스러운"
      and PL.get("taste_ui") == {"tastes": NE.tastes(), "likes_max": NE.LIKES_MAX, "dislikes_max": NE.DISLIKES_MAX} and "needs_ui" not in PL,
      {k: PL.get(k) for k in ("opposites", "taste_ui")})

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ 이름 바이트 동일 · ⑧ 숫자 누설 없음(러너 판)")
GROUPS = [["호기심 많은", "신중한", "용맹한"], ["과묵한", "겁 많은", "탐욕스러운"], ["충직한", "냉소적인", "의심 많은"], ["명예를 중시하는", "낙천적인", "수다스러운"]]
personas = [sheetkit.build_sheet("궁수", g, "가", "여", persona_text=("말이 짧다." if i % 2 else None))["persona"] for i, g in enumerate(GROUPS)]
check("③ 옛 키워드 12종을 고른 시트(넷)의 성격 줄 = 이름 그대로 ', ' 로 · 서술이 있으면 '. ' 뒤(v0.5.21 과 같은 규칙 — 특성 이름 = 옛 키워드 글자)",
      personas == [", ".join(GROUPS[0]), ", ".join(GROUPS[1]) + ". 말이 짧다.", ", ".join(GROUPS[2]), ", ".join(GROUPS[3]) + ". 말이 짧다."], personas)
sheets_run = sheetkit.build_party([{"job": "전사", "traits": ["대식가", "미식가", "신중한"], "name": "두란", "sex": "남", "taste": {"likes": ["고기"], "dislikes": []}},
                                   {"job": "도적", "traits": GROUPS[1], "name": "카야", "sex": "여", "persona": "말이 짧다."},
                                   {"job": "궁수", "traits": ["수다스러운", "호기심 많은", "충직한"], "name": "피른", "sex": "여"}], data=DATA)
sheetkit.write_party(sheets_run, PARTY)
R.PARTY_FILE = PARTY
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err_run:
    R.main()
with io.open(os.path.join(R.STATE, "stream.jsonl"), encoding="utf-8") as f:
    raw_stream = f.read()
recs = [json.loads(x) for x in raw_stream.splitlines() if x.strip()]
meta = recs[0]
p_by = {p["char"]: p for p in meta.get("party") or []}
check("③ 러너 판(더미 · 6틱): 폴백 없이 세 시트로 돈다 · LLM 에 간 글 %d건" % len(SENT),
      "폴백" not in err_run.getvalue() and sorted(p_by) == ["1", "2", "3"] and len(SENT) > 0, err_run.getvalue()[-300:])
check("③ 완성 프롬프트의 성격 줄 = 시트 그대로('- 성격: 대식가, 미식가, 신중한' · '- 성격: 과묵한, 겁 많은, 탐욕스러운. 말이 짧다.') — 설명 문장이 붙지 않는다",
      any("- 성격: 대식가, 미식가, 신중한\n" in s for s in SENT) and any("- 성격: 과묵한, 겁 많은, 탐욕스러운. 말이 짧다.\n" in s for s in SENT)
      and not any(n + "는 " in s or n + "(" in s for s in SENT for n in ("대식가", "미식가")))
check("⑧ run_meta.party[].trait_ids(additive · 같은 순서) · traits(이름) · 입맛 · 욕구 무게 칸(needs·needs_meta)은 없다",
      p_by["1"].get("trait_ids") == ["glutton", "gourmet", "cautious"] and p_by["1"].get("traits") == ["대식가", "미식가", "신중한"]
      and p_by["2"].get("trait_ids") == ["taciturn", "timid", "greedy"] and p_by["1"].get("taste") == {"likes": ["고기"], "dislikes": []}
      and not any(k in p for p in p_by.values() for k in ("needs", "needs_meta", "trait_fx")), p_by.get("1"))
LEAK_IDS = [d["id"] for d in BY.values()]
leak = [t for t in ["trait_fx", '"fill"', "'fill'", "glutton", "gourmet", "taciturn", "trait_ids"] if any(t in s for s in SENT)]
check("⑧ LLM 에 간 글 어디에도 특성 id·배율 칸 이름이 없다(에이전트에게는 이름만)", not leak, leak)
ticks = [r for r in recs if r.get("kind") == "tick"]
check("⑧ 스트림 틱의 봇 스냅샷·관측에 trait_fx 가 없다(배율은 몸에만 — 봇 스냅샷은 화이트리스트)",
      ticks and "trait_fx" not in "".join(json.dumps(t, ensure_ascii=False) for t in ticks))
check("⑧ 몸의 trait_fx 는 공개 투영의 관전 칸(SPECTATOR_KEYS — 어느 깊이든 걷는다) · 0.5.20 needs_meta 칸은 거뒀다",
      "trait_fx" in IG.SPECTATOR_KEYS and "needs_meta" not in IG.SPECTATOR_KEYS
      and IG.public({"result": "x", "deep": {"trait_fx": {"hunger": {"fill": 70}}, "k": 1}}) == {"result": "x", "deep": {"k": 1}})

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ 대식가 — 덜 찬다")
D, ST = G.Dungeon.from_ascii(["#########", "#123...>#", "#########"], seed=3)
D.turn = 1


def body(traits, char="1", taste=None):
    sh = sheetkit.build_sheet("전사", traits, "몸" + char, "남", persona_text="시험", taste=taste)
    b = G.spawn(D, char, [], sheet=sh)
    b["moods"] = []
    return b


def hun(b):
    return b["needs"]["hunger"]


plain_b, glut = body([]), body(["대식가"], "2")
check("④ 몸: 대식가 = trait_fx{hunger: {fill: 70}} · 무게 등급(need_w)은 없다(보통) · 특성 없는 몸엔 칸이 없다",
      glut.get("trait_fx") == {"hunger": {"fill": 70}} and "need_w" not in glut and "trait_fx" not in plain_b and "need_w" not in plain_b)
for t in range(1, 13):
    NE.tick(D, [plain_b, glut], t)
check("④ 배고파지는 빠르기는 그대로(4틱마다 1 — 12틱에 70 → 67 둘 다)", hun(plain_b) == hun(glut) == 67, (hun(plain_b), hun(glut)))
rows = {}
for food in ("ration", "meal", "apple"):
    for b in (plain_b, glut):
        b["needs"]["hunger"], b["moods"] = 10, []
    rp, rg = NE.eat(D, plain_b, ENT.get(food), D.turn), NE.eat(D, glut, ENT.get(food), D.turn)
    rows[food] = (rp["after"], rg["after"], plain_b["moods"][0]["until"] - D.turn, glut["moods"][0]["until"] - D.turn)
check("④ 채우는 양만 70%: 휴대식 +50 → +35 · 식사 +70 → +49 · 햇사과 +20 → +14 · 기분 조각 시간은 그대로(60)",
      rows == {"ration": (60, 45, 60, 60), "meal": (80, 59, 60, 60), "apple": (30, 24, 60, 60)}, rows)
W_HI = {"test_heavy": {"id": "test_heavy", "name": "많이 먹는(시험)", "kind": "trait", "tags": ["trait"],
                       "comps": {"trait": {"effects": {"need": {"hunger": {"level": "높음"}}}}}}}
ENT._DEFS = {**DEFS0, **W_HI}
try:
    both = body(["대식가", "많이 먹는(시험)"], "3")
finally:
    ENT._DEFS = DEFS0
both["needs"]["hunger"] = 10
r_both = NE.eat(D, both, ENT.get("meal"), D.turn)
w_both = NE.weight_of(both, "hunger", NE.spec("hunger"))
check("④ 무게 등급의 fill 과 같은 길: 등급 높음(70%) × 대식가(70%) = 49% — 식사 +70 → +34 · 줄기는 등급 높음 그대로(3틱) · 기분 시간 150%(90틱)",
      both.get("need_w") == {"hunger": "높음"} and r_both["after"] == 44 and w_both["every"] == 3 and abs(w_both["fill"] - 49.0) < 1e-9
      and both["moods"][0]["until"] - D.turn == 90, (r_both, w_both, both.get("moods")))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ 미식가·소박한 — 기분 조각의 크기")
TASTE = {"likes": ["고기"], "dislikes": ["과일"]}


def mood_sums(traits, char):
    b = body(traits, char, taste=TASTE)
    out = {}
    for food, kind in (("meal", "like"), ("apple", "dislike"), ("ration", "plain")):
        b["needs"]["hunger"], b["moods"] = 41, []
        r = NE.eat(D, b, ENT.get(food), D.turn)
        m = NE.mood_of(b, D.turn)
        out[kind] = (r.get("mood"), m["sum"] if m else 0, b["moods"][0]["until"] - D.turn)
    return b, out


_, m0 = mood_sums([], "4")
b_g, m_g = mood_sums(["미식가"], "5")
b_s, m_s = mood_sums(["소박한"], "6")
b_gs, m_gs = mood_sums(["미식가", "소박한"], "7")
check("⑤ 특성 없음: 좋아함 +15 · 싫어함 −5 · 기본 +8(정의 그대로 — 조각 시간 120·60·60)",
      m0 == {"like": ("like", 15, 120), "dislike": ("dislike", -5, 60), "plain": ("plain", 8, 60)}, m0)
check("⑤ 미식가: 좋아함·싫어함만 150%(+23 · −8 — 0 에서 먼 쪽 반올림) · 기본 +8 그대로 · 조각 시간 그대로",
      m_g == {"like": ("like", 23, 120), "dislike": ("dislike", -8, 60), "plain": ("plain", 8, 60)}
      and b_g.get("trait_fx") == {"hunger": {"mood": {"dislike": 150, "like": 150}}}, m_g)
check("⑤ 소박한: 셋 다 50%(+8 · −3 · +4) · 조각 시간 그대로",
      m_s == {"like": ("like", 8, 120), "dislike": ("dislike", -3, 60), "plain": ("plain", 4, 60)}, m_s)
check("⑤ 미식가 + 소박한: 곱(좋아함·싫어함 75% · 기본 50%) — +11 · −4 · +4",
      m_gs == {"like": ("like", 11, 120), "dislike": ("dislike", -4, 60), "plain": ("plain", 4, 60)}, m_gs)
b_s["needs"]["hunger"], b_s["moods"] = 20, []
b_g["needs"]["hunger"], b_g["moods"] = 20, []
check("⑤ 단계가 주는 기분은 그대로(배고픔 −10 — 조각이 아니다) · 기분 줄 낱말·이유는 그대로('좋지 않다 (이유: 배고픔)')",
      NE.mood_of(b_s, D.turn)["sum"] == NE.mood_of(b_g, D.turn)["sum"] == -10 and NE.mood_line(b_s, D.turn) == "좋지 않다 (이유: 배고픔)")
b_g["needs"]["hunger"], b_g["moods"] = 41, []
NE.eat(D, b_g, ENT.get("meal"), D.turn)
check("⑤ 관측의 기분 줄은 낱말뿐(숫자 없음): 미식가가 좋아하는 식사 → '좋다 (이유: 좋아하는 식사를 먹음)'",
      NE.mood_line(b_g, D.turn) == "좋다 (이유: 좋아하는 식사를 먹음)", NE.mood_line(b_g, D.turn))
ZERO = {"test_tiny": {"id": "test_tiny", "name": "무덤덤한(시험)", "kind": "trait", "tags": ["trait"],
                      "comps": {"trait": {"effects": {"need": {"hunger": {"mood": {"like": 1, "plain": 1, "dislike": 1}}}}}}}}
ENT._DEFS = {**DEFS0, **ZERO}
try:
    tiny = body(["무덤덤한(시험)"], "8", taste=TASTE)
finally:
    ENT._DEFS = DEFS0
tiny["needs"]["hunger"], tiny["moods"] = 41, []
NE.eat(D, tiny, ENT.get("ration"), D.turn)
check("⑤ 곱해서 0 이 된 조각은 세지 않는다(기본 +8 × 1% → 0 — 이유에도 없다 · 기분 줄 없음)",
      NE.mood_of(tiny, D.turn) is None and NE._parts(tiny, D.turn) == [], NE._parts(tiny, D.turn))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑥ 겹침 규칙")
OV = {"test_f80": {"id": "test_f80", "name": "배가 큰(시험)", "kind": "trait", "tags": ["trait"],
                   "comps": {"trait": {"effects": {"need": {"hunger": {"fill": 80}}}}}},
      "test_hi2": {"id": "test_hi2", "name": "또 많이 먹는(시험)", "kind": "trait", "tags": ["trait"],
                   "comps": {"trait": {"effects": {"need": {"hunger": {"level": "높음"}}}}}},
      "test_lo": {"id": "test_lo", "name": "적게 먹는(시험)", "kind": "trait", "tags": ["trait"],
                  "comps": {"trait": {"effects": {"need": {"hunger": {"level": "낮음"}, "social": {"level": "높음"}}}}}}}
ENT._DEFS = {**DEFS0, **W_HI, **OV}
try:
    e_fill = NE.trait_effects(["대식가", "배가 큰(시험)"])
    e_dup = NE.trait_effects(["대식가", "대식가"])
    e_mood = NE.trait_effects(["미식가", "소박한"])
    e_same = NE.trait_effects(["많이 먹는(시험)", "또 많이 먹는(시험)"])
    e_conf = NE.trait_effects(["많이 먹는(시험)", "적게 먹는(시험)"])
    e_soc = NE.trait_effects(["수다스러운", "적게 먹는(시험)"])
    e_unk = NE.trait_effects(["사악한", None, 3, "대식가"])
    f_conf = NE.fields({"traits": ["많이 먹는(시험)", "적게 먹는(시험)", "대식가"]})
finally:
    ENT._DEFS = DEFS0
check("⑥ 배율은 곱(대식가 70 × 배가 큰 80 = 56) · 같은 이름은 한 번(대식가 둘 = 70) · 미식가 × 소박한 = 좋아함·싫어함 75 · 기본 50",
      e_fill == ({}, {"hunger": {"fill": 56}}) and e_dup == ({}, {"hunger": {"fill": 70}})
      and e_mood == ({}, {"hunger": {"mood": {"dislike": 75, "like": 75, "plain": 50}}}), (e_fill, e_dup, e_mood))
check("⑥ 등급: 모두 같으면 그 등급(높음 + 높음 = 높음) · 다르면 보통(높음 + 낮음 — 칸 없음) · 다른 욕구끼리는 따로(사교 높음 둘 = 높음) · 모르는 이름·글 아닌 것은 건너뛴다",
      e_same == ({"hunger": "높음"}, {}) and e_conf == ({"social": "높음"}, {}) and e_soc == ({"social": "높음", "hunger": "낮음"}, {})
      and e_unk == ({}, {"hunger": {"fill": 70}}), (e_same, e_conf, e_soc, e_unk))
check("⑥ 몸: 서로 지운 등급은 몸에 없다(보통) · 배율은 그대로 · 준비 중 욕구(사교) 등급은 몸에 없다",
      f_conf.get("trait_fx") == {"hunger": {"fill": 70}} and "need_w" not in f_conf, f_conf)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑦ 준비 중 욕구 — 엔진은 건너뛴다")
ready = ["수다스러운", "호기심 많은", "충직한"]
check("⑦ 수다스러운·호기심 많은·충직한 → 등급은 정의에서 읽힌다(사교·호기심·애정 높음) · 과묵한 → 사교 낮음",
      NE.trait_effects(ready) == ({"social": "높음", "curiosity": "높음", "affection": "높음"}, {})
      and NE.trait_effects(["과묵한"]) == ({"social": "낮음"}, {}))
rb, nb = body(ready, "1"), body([], "2")
rb["needs"]["hunger"] = nb["needs"]["hunger"] = 50
for t in range(1, 41):
    NE.tick(D, [rb, nb], t)
check("⑦ 몸에는 무게·배율이 없다 · 단계 있는 욕구만 몸에 있다(배고픔) · 40틱을 특성 없는 몸과 똑같이 돈다",
      not ({"need_w", "trait_fx"} & set(rb)) and set(rb["needs"]) == {"hunger"} and rb["needs"] == nb["needs"] and rb["moods"] == nb["moods"] == [])

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑨ 이관")
K = savedata.KEY
SLOT2 = {"name": "미나", "sex": "여", "job": "도적", "traits": ["수다스러운", "과묵한", "신중한"], "persona": "", "background": "", "look": None,
         "needs": {"hunger": {"level": "높음", "why": "먹보", "src": "model"}}, "taste": {"likes": ["빵"], "dislikes": []},
         "needs_meta": {"by": "gemini_api", "ok": True}}
SLOT2B = dict(SLOT2, name="린", traits=["대식가"], needs={"social": {"level": "낮음"}})
old_presets = {K: 2, "version": 1, "presets": [{"id": "p1", "label": "미나", "slot": SLOT2}, {"id": "p2", "label": "린", "slot": SLOT2B}]}
before = json.dumps(old_presets, ensure_ascii=False, sort_keys=True)
up = savedata.upgrade("presets", old_presets)
s1, s2 = up["presets"][0]["slot"], up["presets"][1]["slot"]
check("⑨ presets 2→3: needs·needs_meta 를 걷는다 · taste 그대로 · 반대 짝(수다스러운·과묵한)은 먼저 고른 쪽만 · 짝 없는 특성은 그대로 · 원본 dict 불변",
      up.get(K) == savedata.CURRENT["presets"] == 3 and s1["traits"] == ["수다스러운", "신중한"] and s2["traits"] == ["대식가"]
      and not ({"needs", "needs_meta"} & (set(s1) | set(s2))) and s1["taste"] == {"likes": ["빵"], "dislikes": []}
      and json.dumps(old_presets, ensure_ascii=False, sort_keys=True) == before, up)
PR = os.path.join(TMP, "character_presets.json")
jw(PR, old_presets)
try:
    lst = PresetStore(PR, DATA).list()
except ValueError as e_:                             # 이관이 반대 짝을 정리하지 않으면 여기서 목록 전체가 막힌다(이 칸이 지키는 사고)
    lst = [{"id": "막힘: %s" % e_}]
check("⑨ 옛 저장 캐릭터 파일을 저장소가 그대로 읽는다(반대 짝 때문에 목록 전체가 막히지 않는다) · 입맛 남음",
      [e["id"] for e in lst] == ["p1", "p2"] and lst[0]["slot"]["traits"] == ["수다스러운", "신중한"] and lst[0]["slot"].get("taste") == {"likes": ["빵"], "dislikes": []}
      and "needs" not in lst[0]["slot"], lst)
v0 = savedata.upgrade("presets", {"version": 1, "presets": [{"id": "p0", "label": "x", "slot": dict(SLOT2, traits=["용맹한", "겁 많은"])}]})
check("⑨ 판 번호 없는 옛 파일도 0→1→2→3 차례로(반대 짝 정리까지)", v0.get(K) == 3 and v0["presets"][0]["slot"]["traits"] == ["용맹한"], v0)
sheet_old = dict(sheetkit.build_sheet("궁수", ["수다스러운", "충직한"], "피른", "여"), needs={"hunger": {"level": "낮음"}},
                 needs_meta={"by": "gemini_api"}, taste={"likes": ["단것"], "dislikes": []})
old_party = {K: 1, "_readme": "옛", "1": sheet_old, "2": dict(sheet_old, name="두란", traits=["수다스러운", "과묵한"], persona="수다스러운, 과묵한")}
upp = savedata.upgrade("party", old_party)
check("⑨ party 1→2: 시트의 needs·needs_meta 를 걷는다 · traits·성격 줄·taste 그대로(옛 키워드는 그대로 특성 이름) · '_' 칸 그대로",
      upp.get(K) == savedata.CURRENT["party"] == 2 and upp["_readme"] == "옛"
      and {k: v for k, v in upp["1"].items()} == {k: v for k, v in sheet_old.items() if k not in ("needs", "needs_meta")}
      and upp["2"]["traits"] == ["수다스러운", "과묵한"] and upp["2"]["persona"] == "수다스러운, 과묵한", upp)
PP = os.path.join(TMP, "party_custom.json")
jw(PP, old_party)
with contextlib.redirect_stderr(io.StringIO()) as err_p:
    lp = R.load_party(PP)
b_old = G.spawn(D, "2", [], sheet=lp["2"])
check("⑨ 옛 파티 파일을 러너가 그대로 읽는다(폴백 없음) — 옛 시트에 반대 짝이 둘 다 있어도(러너는 막지 않는다) 사교 등급은 서로 지워 보통 · 입맛은 몸에",
      "폴백" not in err_p.getvalue() and "needs" not in lp["1"] and lp["1"]["taste"] == {"likes": ["단것"], "dislikes": []}
      and NE.trait_effects(lp["2"]["traits"]) == ({}, {}) and b_old.get("taste") == {"likes": ["단것"], "dislikes": []}, err_p.getvalue()[-200:])
check("⑨ 저장 판: party 2 · presets 3 · 이관 함수 등록부 완결(0..현재-1)",
      savedata.CURRENT["party"] == 2 and savedata.CURRENT["presets"] == 3
      and all(sorted(savedata.MIGRATIONS[k]) == list(range(savedata.CURRENT[k])) for k in savedata.CURRENT))
# p0522b 스냅샷 11→12 — 0.5.21 에서 멈춘 판(시트에 생성 호출의 needs·needs_meta, 몸에 그 무게 need_w)을 이어간다
sA, sB, sC, sW, sD = (body(["대식가", "미식가"], "1"), body([], "2"), body(["소박한"], "3"), body(["수다스러운"], "4"), body([], "5"))
for b_, w_ in ((sA, "낮음"), (sB, "높음"), (sW, "높음")):
    b_.pop("trait_fx", None)
    b_["need_w"] = {"hunger": w_}                     # 옛 몸: 생성 호출이 시트에 적은 무게(특성과 무관)
sC.pop("trait_fx", None)
del sD["traits"]                                     # 특성 칸이 없는 몸 — 그 판의 시트로
sA["needs"], sA["moods"] = {"hunger": 33}, [{"src": "hunger", "size": "like", "what": "식사", "until": 99}]
SHEETS11 = {c: dict(sheetkit.build_sheet("전사", tr, "몸" + c, "남", persona_text="시험"), needs={"hunger": {"level": "낮음"}}, needs_meta={"by": "gemini_api"},
                    **({"taste": {"likes": ["빵"], "dislikes": []}} if c == "1" else {}))
            for c, tr in (("1", ["대식가", "미식가"]), ("2", []), ("3", ["소박한"]), ("4", ["수다스러운"]), ("5", ["대식가"]))}
SD = os.path.join(TMP, "snap11")
os.makedirs(SD)
with open(os.path.join(SD, snapshot.PKL), "wb") as f:
    pickle.dump({"version": 2, "state_version": 11, "run_id": "11@x", "d": D, "bots": [sA, sB], "sheets": SHEETS11, "next_turn": 5, "stream_pos": 0,
                 "seed": 11, "started": "x", "worlds": [{"bots": [sC, sD]}], "waiting": {"4": sW}}, f)
snapshot.write_meta(SD, {"run_id": "11@x"})
up11, _m = snapshot.load(os.path.join(SD, snapshot.PKL))
U = {b_["char"]: b_ for b_ in snapshot._bodies(up11)}
check("⑨ p0522b 스냅샷 11→12: 몸마다 무게·배율을 특성으로 다시 — 대식가·미식가 = 배율만(옛 무게 낮음 걷힘) · 특성 없음 = 칸 없음(옛 높음 걷힘) · 소박한(다른 세계) · "
      "수다스러운(부활 대기 — 준비 중이라 칸 없음) · 특성 칸 없는 몸은 그 판의 시트(대식가)로",
      up11["state_version"] == snapshot.STATE_VERSION == 12 and snapshot.MIGRATIONS[11] is snapshot._m11_traits
      and "need_w" not in U["1"] and U["1"].get("trait_fx") == {"hunger": {"fill": 70, "mood": {"dislike": 150, "like": 150}}}
      and not ({"need_w", "trait_fx"} & set(U["2"])) and U["3"].get("trait_fx") == {"hunger": {"mood": {"dislike": 50, "like": 50, "plain": 50}}}
      and not ({"need_w", "trait_fx"} & set(U["4"])) and U["5"].get("trait_fx") == {"hunger": {"fill": 70}}, {c: (b_.get("need_w"), b_.get("trait_fx")) for c, b_ in U.items()})
check("⑨ p0522b 스냅샷 11→12: 시트의 needs·needs_meta 를 걷는다(입맛·특성 그대로) · 충족도·기분 조각 그대로 · 다시 올려도 같다",
      all(not ({"needs", "needs_meta"} & set(s_)) for s_ in up11["sheets"].values()) and up11["sheets"]["1"]["taste"] == {"likes": ["빵"], "dislikes": []}
      and up11["sheets"]["1"]["traits"] == ["대식가", "미식가"] and U["1"]["needs"] == {"hunger": 33} and U["1"]["moods"] == sA["moods"]
      and [b_ for b_ in snapshot._bodies(snapshot.upgrade(copy.deepcopy(up11)))] == snapshot._bodies(up11), up11["sheets"].get("1"))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑪ 동료 프리셋의 입맛(p0522b)")
ENT._DEFS = {**DEFS0, MATE_OK["id"]: MATE_OK}
try:
    m_sheet = sheetkit.build_companion_sheet(MATE_OK, data=DATA)
    m_pay = next((c for c in launcher.companions_payload(DATA) if c["id"] == MATE_OK["id"]), {})
    m_party = sheetkit.build_party([{"job": "도적", "traits": [], "name": "가", "sex": "여", "persona": "x"}, {"companion": MATE_OK["id"]}],
                                   data=DATA, companions=ENT.companions())
except ValueError as e_:                             # 입맛 칸을 못 받으면 조립이 거절한다 — 이 칸이 지키는 회귀
    m_sheet, m_pay, m_party = {"막힘": str(e_)}, {}, {"2": {}}
finally:
    ENT._DEFS = DEFS0
bad_taste = rejects(lambda: sheetkit.build_companion_sheet(mate("c_x", "엑스", {"likes": ["고기", "빵", "단것"], "dislikes": []}), data=DATA))
check("⑪ 동료 시트에 입맛이 실린다(데이터 그대로) · 론처 동료 목록에도(화면의 한 줄 요약) · 파티 조립에도 · 검증기를 지나며 달라지는 입맛(좋아함 3개)은 거절",
      m_sheet.get("taste") == MATE_OK["comps"]["sheet"]["taste"] and m_pay.get("taste") == MATE_OK["comps"]["sheet"]["taste"]
      and m_party["2"].get("taste") == MATE_OK["comps"]["sheet"]["taste"] and (bad_taste or "").startswith("taste 칸이 검증기를 지나며 달라진다")
      and "taste" in sheetkit.COMPANION_SHEET_KEYS and not ({"needs", "needs_meta"} & set(sheetkit.COMPANION_SHEET_KEYS)), (m_sheet.get("taste"), m_pay.get("taste"), bad_taste))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑩ 배선")
gone = [p for p in ("need_gen.py", os.path.join("tools", "need_gen.py"), os.path.join("prompts", "launcher", "need_gen.md"), "verify_need_gen.py")
        if os.path.exists(os.path.join(HERE, p))]
code_refs = [f for f in ("launcher.py", "server.py", "sheetkit.py", "character_presets.py", "needs.py", "show_runner.py", "words.py", "entities.py", "savedata.py")
             if any(t in src(f) for t in ("import need_gen", "need_gen.", '"/api/needs', "fill_party_needs(", "NEED_FIELDS", "set_needs("))]
check("⑩ 욕구 생성 호출(0.5.20~21)은 없다 — 모듈·도구·프롬프트·게이트 파일 · 론처·공개 서버·저장소의 호출 자리",
      not gone and not code_refs and not any(hasattr(NE, a) for a in ("_META_RE", "WHY_MAX")) and not hasattr(sheetkit, "NEED_FIELDS"), (gone, code_refs))
gates = src("_run_gates.sh")
check("⑩ 배선: _run_gates.sh 에 verify_traits(verify_need_gen 없음) · VERSION 0.5.22 이상(p0.5.23: 다음 판에서 깨지지 않게) · STREAM_FORMAT(trait_ids) · PATCH_NOTES(0.5.22)",
      "verify_traits" in gates and "verify_need_gen" not in gates and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 22)
      and "trait_ids" in src("STREAM_FORMAT.md") and "## 0.5.22" in src("docs", "PATCH_NOTES.md"))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑫ p0.5.23 낙천적인 ↔ 냉소적인 — 기분 기본값(림월드식 B)")
D.turn = 50
NE.drain(D)
TR3 = {"없음": [], "낙천": ["낙천적인"], "냉소": ["냉소적인"]}


def mood3(hunger, food=None):
    """특성 셋(없음·낙천·냉소)의 몸 — 충족도 hunger, food 를 먹은 뒤 → {이름: (mood_line, sum 또는 None, 이유 목록)}."""
    out = {}
    for i, (k, tr) in enumerate(TR3.items()):
        b = body(tr, str(i + 1), taste=TASTE)
        b["needs"]["hunger"], b["moods"] = hunger, []
        if food:
            NE.eat(D, b, ENT.get(food), D.turn)
            b["needs"]["hunger"] = hunger                # 먹어 오른 충족도를 되돌린다 — 단계는 hunger 그대로, 조각만 남긴다
        m = NE.mood_of(b, D.turn)
        out[k] = (NE.mood_line(b, D.turn), m["sum"] if m else None, m["why"] if m else None)
    return out


m_norm = mood3(60)
check("⑫ 다른 이유가 없으면(보통 단계 · 조각 없음) 기본값만으로는 '기분:' 줄이 없다 — 낙천 +5·냉소 −5 가 문턱(3)을 넘어도",
      all(v == (None, None, None) for v in m_norm.values()) and NE.trait_mood(["낙천적인"]) == 5 and NE.trait_mood(["냉소적인"]) == -5
      and abs(NE.trait_mood(["낙천적인"])) >= NE.MOOD_EDGE, m_norm)
m_hun = mood3(20)
check("⑫ 다른 이유와 합산: 배고픔(−10) → 없음 −10 · 낙천 −5 · 냉소 −15 — 낱말·이유는 같다('좋지 않다 (이유: 배고픔)')",
      m_hun == {"없음": ("좋지 않다 (이유: 배고픔)", -10, ["배고픔"]), "낙천": ("좋지 않다 (이유: 배고픔)", -5, ["배고픔"]),
                "냉소": ("좋지 않다 (이유: 배고픔)", -15, ["배고픔"])}, m_hun)
m_dis = mood3(60, "apple")
check("⑫ 문턱으로 줄이 사라진다: 싫어하는 햇사과(−5) → 없음 '좋지 않다' · 낙천 합 0 → 줄 없음 · 냉소 −10",
      m_dis == {"없음": ("좋지 않다 (이유: 입에 맞지 않는 음식)", -5, ["입에 맞지 않는 음식"]), "낙천": (None, None, None),
                "냉소": ("좋지 않다 (이유: 입에 맞지 않는 음식)", -10, ["입에 맞지 않는 음식"])}, m_dis)
m_mix = mood3(20, "ration")
check("⑫ 줄이 생기고 뒤집힌다: 배고픔(−10) + 배불리 먹음(+8) = −2 → 없음은 줄 없음 · 낙천 +3 '좋다 (이유: 배불리 먹음)' · 냉소 −7 '좋지 않다 (이유: 배고픔)'",
      m_mix == {"없음": (None, None, None), "낙천": ("좋다 (이유: 배불리 먹음)", 3, ["배불리 먹음"]),
                "냉소": ("좋지 않다 (이유: 배고픔)", -7, ["배고픔"])}, m_mix)
lines12 = [v[0] for m_ in (m_norm, m_hun, m_dis, m_mix) for v in m_.values() if v[0]]
check("⑫ 이유 낱말에 특성이 안 나온다(이유는 조각에서만) · 기분 줄에 숫자 없음",
      lines12 and not any(t in ln for ln in lines12 for t in ("낙천", "냉소", "특성", "성격")) and not any(re.search(r"\d", ln) for ln in lines12), lines12)
BIG = {"test_sunny": {"id": "test_sunny", "name": "아주 밝은(시험)", "kind": "trait", "tags": ["trait"], "comps": {"trait": {"effects": {"mood": 20}}}},
       "test_glad": {"id": "test_glad", "name": "명랑한(시험)", "kind": "trait", "tags": ["trait"], "comps": {"trait": {"effects": {"mood": 3}}}}}
ENT._DEFS = {**DEFS0, **BIG}
try:
    sunny = body(["아주 밝은(시험)"], "4")
    sunny["needs"]["hunger"], sunny["moods"] = 20, []
    m_sun, l_sun = NE.mood_of(sunny, D.turn), NE.mood_line(sunny, D.turn)
    t_sum = (NE.trait_mood(["낙천적인", "명랑한(시험)"]), NE.trait_mood(["낙천적인", "낙천적인"]), NE.trait_mood(["사악한", None, 3, "냉소적인"]), NE.trait_mood([]))
finally:
    ENT._DEFS = DEFS0
check("⑫ 기본값이 합을 조각과 반대쪽으로 뒤집으면 이유 없이 낱말만(시험 특성 +20 · 배고픔 −10 → '좋다', 이유 칸 비움 — 배고픔은 좋은 쪽 이유가 아니다)",
      m_sun == {"key": "good", "sum": 10, "why": []} and l_sun == "좋다", (m_sun, l_sun))
check("⑫ 겹침(trait_effects 와 같은 자리): 여러 특성은 더한다(낙천 5 + 명랑한 3 = 8) · 같은 이름은 한 번 · 모르는 이름·글 아닌 것은 건너뛴다 · 없으면 0",
      t_sum == (8, 5, -5, 0), t_sum)
opt = body(["낙천적인"], "5", taste=TASTE)
cyn = body(["냉소적인"], "6", taste=TASTE)
check("⑫ 몸에 기분 기본값 칸이 없다(특성 이름 traits 에서 그릴 때 읽는다) · 무게·배율 칸도 없다 — 낙천·냉소는 기분 합에만 닿는다",
      opt.get("traits") == ["낙천적인"] and not ({"need_w", "trait_fx", "trait_mood", "mood_base"} & set(opt))
      and not ({"need_w", "trait_fx", "trait_mood", "mood_base"} & set(cyn)))
NE.drain(D)
cyn["needs"]["hunger"], cyn["moods"] = 60, []
NE.eat(D, cyn, ENT.get("ration"), D.turn)            # 냉소 + 배불리 먹음 = +3 → 기분 없음 → 좋다
ev12 = [e for e in NE.drain(D) if e.get("result") == "need_mood"]
snap12 = NE.snap(cyn)
check("⑫ 관전 합에는 들어간다: need_mood 사건 sum 3(+8 − 5) · 봇 스냅샷 mood_now.sum 3 · 관전 로그 '합 +3'",
      ev12 == [{"type": "need", "bot": "6", "result": "need_mood", "from": None, "to": "good", "sum": 3, "why": ["배불리 먹음"]}]
      and snap12.get("mood_now") == {"key": "good", "sum": 3, "why": ["배불리 먹음"]} and "합 +3" in (NE.summary(ev12[0]) if ev12 else ""), (ev12, snap12))
o12 = D.view(cyn, [cyn])
w12 = brains._wire(o12, {"6": "몸6"}, compose=True)
check("⑫ 숫자 누설 없음: 관측 need_mood 는 낱말('좋다 (이유: 배불리 먹음)') · 프롬프트 '기분:' 줄에 숫자 없음 · 관측에 특성 효과 칸 없음 · 공개 투영은 sum·mood_now 를 걷는다",
      o12.get("need_mood") == "좋다 (이유: 배불리 먹음)" and "- 기분: 좋다 (이유: 배불리 먹음)\n" in w12
      and not any(k in json.dumps(o12, ensure_ascii=False) for k in ("trait", "mood_now", '"sum"'))
      and IG.public(ev12[0] if ev12 else {"sum": 1}).get("sum") is None and IG.public({"r": 1, "mood_now": snap12.get("mood_now")}) == {"r": 1},
      (o12.get("need_mood"), IG.public(ev12[0] if ev12 else {})))
# v0.5.22 에서 멈춘 판(내용 판 12 — 몸에 새 칸 없음)을 이어간다: 이관 없이 몸의 특성 이름으로 같은 합
o22 = body(["낙천적인"], "1")
o22["needs"]["hunger"], o22["moods"] = 20, []
SD12 = os.path.join(TMP, "snap12")
os.makedirs(SD12)
with open(os.path.join(SD12, snapshot.PKL), "wb") as f:
    pickle.dump({"version": 2, "state_version": 12, "run_id": "12@x", "d": D, "bots": [o22], "sheets": {}, "next_turn": 51, "stream_pos": 0,
                 "seed": 11, "started": "x"}, f)
snapshot.write_meta(SD12, {"run_id": "12@x"})
up12, _m12 = snapshot.load(os.path.join(SD12, snapshot.PKL))
b12 = up12["bots"][0]
check("⑫ 이어가기: v0.5.22 판(내용 판 12)은 그대로 읽힌다(판 번호를 올리지 않았다 — 몸에 새 칸이 없다) · 이어간 몸도 기본값이 든 합(배고픔 −10 + 낙천 5 = −5)",
      up12["state_version"] == snapshot.STATE_VERSION == 12 and b12.get("traits") == ["낙천적인"]
      and (NE.mood_of(b12, 51) or {}).get("sum") == -5 and NE.mood_line(b12, 51) == "좋지 않다 (이유: 배고픔)", (up12["state_version"], NE.mood_of(b12, 51)))
check("⑫ 배선: VERSION 0.5.23 이상 · PATCH_NOTES 0.5.23 · STREAM_FORMAT(기분 합에 특성 기본값) · CHANGELOG p0.5.23",
      tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 23) and "## 0.5.23" in src("docs", "PATCH_NOTES.md")
      and "trait_mood" in src("STREAM_FORMAT.md") and "p0.5.23" in src("docs", "CHANGELOG.md"))

shutil.rmtree(TMP, ignore_errors=True)
print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    sys.exit(1)
print("ALL PASS — verify_traits (p0.5.22 성격 키워드 → 캐릭터 특성 · p0.5.23 낙천↔냉소 기분 기본값: %d checks · 저장소 꼴·검증기·반대 짝·이름 바이트·대식가·미식가·소박한·겹침·준비 중·누설·이관·배선·낙천·냉소, 실 LLM 0콜)" % C.n)
