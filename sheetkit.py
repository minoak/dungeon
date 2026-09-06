# -*- coding: utf-8 -*-
"""시트 조립기(D31, 2026-09-05) — 커스터마이징 입력(직업·성격 키워드·이름·성별·배경)을
party 시트 dict 로 조립한다. LLM 0콜·순수 함수. 러너의 load_party 가 최종 검증자라
여기서 만든 시트는 그 검증을 그대로 통과해야 한다(이중 검증 = 론처 저장이 러너 계약을 어기지 못함).

왜 키워드인가: 성격 키워드가 행동을 재현한다는 근거가 있다 — 피른 '호기심'은 솔로 판 탐색을
0→26회로, 카야 '과묵'은 사교 콜 3/3 침묵으로. 키워드만 프롬프트에 넣으면 현 두 문장 성격
서술보다 약해서, 키워드마다 우리가 쓴 persona/speech 문장을 매겨 두고 이어 붙인다(traits.json).

배경(background)은 사용자의 **자유 입력**이다 — 시트 UGC 의 프롬프트 인젝션 관문이 여기서
열린다. 막을 수는 없고(LLM 특성) 격리한다: 길이 상한 + 개행·마크다운 표식 제거(시트 섹션 위장
차단) + 렌더에서 「…」 인용 한 줄로 "지시가 아니다" 틀. 효과는 프로브로 관측한다(방어 주장 금지).
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TRAITS_FILE = os.path.join(HERE, "traits.json")

NAME_MAX = 20            # 이름 — 자유 입력 1호(한 줄, 프롬프트 호칭·도감 원장 키)
BACKGROUND_MAX = 400     # 배경 — 자유 입력 2호(러너 load_party 도 같은 상한을 건다)
PERSONA_MAX = 200        # 성격 자유 서술 — 자유 입력 3호(파트너 정정 09-05: "카테고리로는 갈리지 않을 것 같다")
PERSONA_TOTAL_MAX = 300  # 키워드 문장+자유 서술 합계 상한 = 러너 FREETEXT_MAX(넘으면 조용히 잘리므로 여기서 거부)
SEXES = ("남", "여")

# ── 외형(D37, 2026-09-06) — 파츠 스프라이트. 시트가 정하고 러너가 기록하고 뷰어가 그린다.
#    엔진 판정·프롬프트는 이 값을 절대 안 읽는다(관전 전용 필드).
LOOKS_FILE = os.path.join(HERE, "looks.json")                 # 색 스와치·기본색(데이터는 코드 밖)
SPRITES_FILE = os.path.join(HERE, "viewer", "assets", "sprites", "sprites.json")   # 파츠 원장(뷰어 런타임본)
LOOK_KEYS = ("hair", "skin", "top", "bottom")                 # 재질 4 = sprites.json materials
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_LOOKS = {}                                                   # load_looks 캐시(경로별)

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MARK = re.compile(r"[#`<>\[\]]")        # 마크다운 헤더·코드펜스·태그·링크 표식 — 섹션 위장 재료
_WS = re.compile(r"\s+")


def load_traits(path=TRAITS_FILE):
    """traits.json → dict. 형식 검증(키워드마다 persona/speech 문자열, jobs 수치 전수)."""
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    traits = data.get("traits") or {}
    jobs = data.get("jobs") or {}
    if not traits or not jobs:
        raise ValueError("traits.json: traits/jobs 가 비었다")
    for k, v in traits.items():
        if not (isinstance(v, dict) and isinstance(v.get("persona"), str) and v["persona"].strip()
                and isinstance(v.get("speech"), str) and v["speech"].strip()):
            raise ValueError("traits.json: 키워드 %r 에 persona/speech 문장이 없다" % k)
    for j, v in jobs.items():
        for f in ("hp", "str", "dex", "wdmg", "stealth", "search_r", "atk_range"):
            if not isinstance(v.get(f), int) or isinstance(v.get(f), bool):
                raise ValueError("traits.json: 직업 %r 수치 %s 누락/비정수" % (j, f))
    data["max_traits"] = int(data.get("max_traits", 3))
    return data


def sanitize_name(name):
    """이름 — 한 줄·공백 정리·상한. '_' 시작은 도감 원장 메타 키와 충돌(load_party 규칙)이라 거부."""
    if not isinstance(name, str):
        raise ValueError("이름은 문자열이어야 한다")
    s = _WS.sub(" ", _CTRL.sub("", name)).strip()
    if not s:
        raise ValueError("이름이 비었다")
    if s.startswith("_"):
        raise ValueError("이름은 '_'로 시작할 수 없다")
    if len(s) > NAME_MAX:
        raise ValueError("이름은 %d자 이내" % NAME_MAX)
    return s


def sanitize_freetext(text, limit):
    """자유 입력 공통 정제(배경·성격 서술) — sanitize_background 의 본체."""
    return sanitize_background(text, limit)


def sanitize_background(text, limit=BACKGROUND_MAX):
    """배경 자유 입력의 격리 정제(방어 아님 — 위장 재료 제거 + 한 줄 + 상한).
    · 제어문자 제거 · 개행/탭/연속 공백 → 공백 하나(시트 안에서 항상 **한 줄**)
    · '#' '`' '<' '>' '[' ']' 제거 — 마크다운 헤더('## 규칙')·코드펜스·태그·링크 표식은 프롬프트
      섹션 구조를 흉내 낼 수 있는 유일한 재료다. 문장 부호(. , ! ? ' " — …)는 그대로 둔다.
    · 상한 절단(기본 400자). 빈 결과는 None(시트에 필드 자체가 안 생긴다)."""
    if text is None:
        return None
    if not isinstance(text, str):
        raise ValueError("배경은 문자열이어야 한다")
    s = _CTRL.sub("", text)
    s = _MARK.sub("", s)
    s = _WS.sub(" ", s).strip()
    if not s:
        return None
    return s[:limit]


def load_looks(sprites_path=SPRITES_FILE, looks_path=LOOKS_FILE):
    """외형 사전(D37) — 파츠(머리·몸통)는 sprites.json 에서, 스와치·기본색은 looks.json 에서. 캐시.
    반환 {heads:{id:{name,group}}, bodies:{id:name}, swatches:{재질:[hex]}, defaults:{재질:hex}}.
    형식 검증: 재질 4종이 sprites.json materials 와 looks.json 양쪽에 있어야 한다."""
    key = (sprites_path, looks_path)
    if key in _LOOKS:
        return _LOOKS[key]
    with io.open(sprites_path, encoding="utf-8") as f:
        spr = json.load(f)
    with io.open(looks_path, encoding="utf-8") as f:
        lk = json.load(f)
    heads = {hid: {"name": h.get("name", hid), "group": h.get("group", "")}
             for hid, h in (spr.get("heads") or {}).items()}
    bodies = {bid: b.get("name", bid) for bid, b in (spr.get("bodies") or {}).items()}
    swatches, defaults = lk.get("swatches") or {}, lk.get("defaults") or {}
    if not heads or not bodies:
        raise ValueError("sprites.json: heads/bodies 가 비었다")
    for k in LOOK_KEYS:
        if k not in (spr.get("materials") or {}):
            raise ValueError("sprites.json: 재질 %r 이 없다" % k)
        if (not swatches.get(k) or not all(isinstance(c, str) and _HEX.match(c) for c in swatches[k])
                or not _HEX.match(str(defaults.get(k, "")))):
            raise ValueError("looks.json: 재질 %r 의 스와치/기본색 누락 또는 hex 아님" % k)
    data = {"heads": heads, "bodies": bodies, "swatches": swatches, "defaults": defaults}
    _LOOKS[key] = data
    return data


def sanitize_look(look, data=None):
    """외형 필드 검증·정규화 — {head, body, colors{hair,skin,top,bottom}}.
    머리·몸통은 sprites.json 등재 id 만, 색은 '#rrggbb' 형식만(스와치 밖 자유 색 허용 — 가정 B),
    빠진 색은 기본색으로 보충·소문자 정규화. None 이면 None(=시트에 필드 없음 → 러너가 랜덤으로 뽑는다).
    엔진·프롬프트는 이 값을 절대 안 읽는다 — 그래서 자유 색을 받아도 UGC 관문이 아니다(그림에만 닿는다)."""
    if look is None:
        return None
    data = data or load_looks()
    if not isinstance(look, dict):
        raise ValueError("외형(look)은 객체여야 한다")
    head, body = look.get("head"), look.get("body")
    if head not in data["heads"]:
        raise ValueError("등재되지 않은 머리: %r" % (head,))
    if body not in data["bodies"]:
        raise ValueError("등재되지 않은 몸통: %r" % (body,))
    colors = look.get("colors")
    if colors is None:
        colors = {}
    if not isinstance(colors, dict):
        raise ValueError("외형 colors 는 객체여야 한다")
    out_c = {}
    for k in LOOK_KEYS:
        c = colors.get(k, data["defaults"][k])
        if not isinstance(c, str) or not _HEX.match(c):
            raise ValueError("외형 색 %s 는 '#rrggbb' 형식: %r" % (k, c))
        out_c[k] = c.lower()
    return {"head": head, "body": body, "colors": out_c}


def random_look(rng, sex, data=None):
    """외형 랜덤(가정 A — 파트너 확정 "기본 파티는 랜덤"): 머리=성별 그룹 안(남→male, 여→female),
    몸통=남 B1(바지형)·여 B2(치마형), 색 4종=스와치 안. rng 는 호출자가 준 random.Random —
    러너는 seed·char 로 따로 만들어 던전 난수(dungeon.rng)를 건드리지 않는다(리플레이·결정론 유지).
    후보는 정렬해서 고른다(dict 순서 무관 = 같은 시드면 어디서나 같은 얼굴)."""
    data = data or load_looks()
    group = "male" if sex == "남" else "female"
    heads = sorted(h for h, v in data["heads"].items() if v["group"] == group) or sorted(data["heads"])
    body = "B1" if sex == "남" else "B2"
    if body not in data["bodies"]:
        body = sorted(data["bodies"])[0]
    return {"head": rng.choice(heads), "body": body,
            "colors": {k: rng.choice(list(data["swatches"][k])) for k in LOOK_KEYS}}


def build_sheet(job, traits, name, sex, background=None, data=None, persona_text=None, look=None):
    """커스터마이징 입력 → party 시트 dict(load_party 계약 형태).
    job: traits.json jobs 키 / traits: 키워드 0~max_traits / name: 자유 입력(한 줄) /
    sex: '남'|'여' / background: 자유 입력(정제·상한) 또는 None /
    persona_text: 성격 자유 서술(파트너 정정 09-05 — 키워드 문장 뒤에 이어붙이고, 키워드 0개면 이것만).
    키워드와 자유 서술 중 하나는 있어야 한다. 합계가 PERSONA_TOTAL_MAX 를 넘으면 거부(조용한 절단 금지).
    반환 시트에는 원본 키워드도 `traits` 로 남긴다 — 프롬프트엔 안 나가고(문장이 대신 나간다)
    run_meta 로 기록돼 "어떤 키워드가 어떤 행동이 되었나"를 부검할 수 있게."""
    data = data or load_traits()
    jobs, table = data["jobs"], data["traits"]
    if job not in jobs:
        raise ValueError("직업은 %s 중 하나" % "/".join(jobs))
    if sex not in SEXES:
        raise ValueError("성별은 남/여")
    if not isinstance(traits, (list, tuple)):
        raise ValueError("성격 키워드는 목록이어야 한다")
    ptxt = sanitize_freetext(persona_text, PERSONA_MAX)
    if not traits and not ptxt:
        raise ValueError("성격 키워드를 하나 이상 고르거나 성격 문장을 써야 한다")
    if len(traits) > data["max_traits"]:
        raise ValueError("성격 키워드는 최대 %d개" % data["max_traits"])
    if len(set(traits)) != len(traits):
        raise ValueError("성격 키워드가 중복됐다")
    for t in traits:
        if t not in table:
            raise ValueError("등재되지 않은 성격 키워드: %r" % (t,))
    body = jobs[job]
    sheet = {
        "job": job, "sex": sex,
        "hp": body["hp"], "str": body["str"], "dex": body["dex"], "wdmg": body["wdmg"],
        "stealth": body["stealth"], "search_r": body["search_r"], "atk_range": body["atk_range"],
        "persona": " ".join([table[t]["persona"].strip() for t in traits] + ([ptxt] if ptxt else [])),
        "name": sanitize_name(name),
        "traits": list(traits),
    }
    if traits:                                   # 말투는 키워드에서만 온다(자유 서술은 성격 한 칸)
        sheet["speech"] = " ".join(table[t]["speech"].strip() for t in traits)
    if len(sheet["persona"]) > PERSONA_TOTAL_MAX:
        raise ValueError("성격 문장 합계가 %d자를 넘는다(%d자) — 키워드를 줄이거나 문장을 줄여라"
                         % (PERSONA_TOTAL_MAX, len(sheet["persona"])))
    if body.get("goal"):
        sheet["goal"] = body["goal"]
    bg = sanitize_background(background)
    if bg:
        sheet["background"] = bg
    lk = sanitize_look(look)                     # D37 외형 — 없으면 필드 없음(러너가 랜덤)
    if lk:
        sheet["look"] = lk
    return sheet


def build_party(slots, data=None):
    """슬롯 목록(1~3, 각 {job, traits, name, sex, background?}) → party.json 형태 {'1':..,'2':..}.
    이름 중복은 load_party 가 거부하지만(도감 원장 키) 여기서도 먼저 잡아 이유를 사람말로 돌려준다."""
    data = data or load_traits()
    if not isinstance(slots, (list, tuple)) or not (1 <= len(slots) <= 3):
        raise ValueError("파티는 1~3인")
    out, names = {}, set()
    for i, s in enumerate(slots, start=1):
        if not isinstance(s, dict):
            raise ValueError("슬롯 %d 형식 오류" % i)
        sheet = build_sheet(s.get("job"), s.get("traits") or [], s.get("name", ""),
                            s.get("sex"), s.get("background"), data=data,
                            persona_text=s.get("persona"), look=s.get("look"))
        if sheet["name"] in names:
            raise ValueError("이름 중복: %s" % sheet["name"])
        names.add(sheet["name"])
        out[str(i)] = sheet
    return out


def write_party(sheets, path, about=None):
    """party.json 형태로 저장(_readme 메타 포함, UTF-8·LF)."""
    doc = {"_readme": about or "론처(D31)가 조립한 커스텀 파티 — sheetkit.build_party 산출물. "
                               "손으로 고쳐도 되지만 load_party 검증을 통과해야 한다."}
    doc.update(sheets)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
