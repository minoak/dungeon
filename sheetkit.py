# -*- coding: utf-8 -*-
"""시트 조립기(D31, 2026-09-05) — 커스터마이징 입력(직업·성격 키워드·이름·성별·배경)을
party 시트 dict 로 조립한다. LLM 0콜·순수 함수. 러너의 load_party 가 최종 검증자라
여기서 만든 시트는 그 검증을 그대로 통과해야 한다(이중 검증 = 론처 저장이 러너 계약을 어기지 못함).

왜 키워드인가: 성격 키워드가 행동을 재현한다는 근거가 있다 — 피른 '호기심'은 솔로 판 탐색을
0→26회로, 카야 '과묵'은 사교 콜 3/3 침묵으로. 처음(09-05)엔 키워드마다 우리가 쓴 persona/speech
문장을 매겨 이어 붙였으나, 2026-09-12(파트너 메모 §3-3 [결정]) 키워드를 **그대로** 시트 성격 줄에
넣는다 — traits.json 은 키워드 목록만, 말투(speech)는 손으로 쓴 시트에서만 온다.

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
BACKGROUND_MAX = 4000    # 09-11: 긴 과거 서술도 저장·복원·프롬프트까지 같은 상한으로 전달한다.
PERSONA_MAX = 2000       # 사용자가 직접 쓰는 성격. 키워드 문장 길이는 별도로 확보한다.
PERSONA_TOTAL_MAX = 2500 # 키워드 문장+자유 서술 합계. 러너도 성격에만 이 상한을 쓴다.
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
    """traits.json → dict. 형식 검증(traits = 키워드 문자열 목록·중복 없음, jobs 수치 전수).
    옛 형식(키워드→{persona,speech} 사전, 2026-09-05~09-11)은 키 목록으로 읽는다 — 문장은 버린다."""
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    traits = data.get("traits") or []
    jobs = data.get("jobs") or {}
    if isinstance(traits, dict):                 # 옛 사전 형식(오래 켜 둔 론처·옛 파일) — 키워드만 취한다
        traits = list(traits)
    if not traits or not jobs:
        raise ValueError("traits.json: traits/jobs 가 비었다")
    if not isinstance(traits, list) or any(not isinstance(t, str) or not t.strip() for t in traits):
        raise ValueError("traits.json: traits 는 비어 있지 않은 키워드 문자열 목록")
    traits = [t.strip() for t in traits]
    if len(set(traits)) != len(traits):
        raise ValueError("traits.json: 키워드 중복")
    data["traits"] = traits
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
    · 상한 절단(기본 BACKGROUND_MAX). 빈 결과는 None(시트에 필드 자체가 안 생긴다)."""
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
    반환 {heads:{id:{name,group}}, bodies:{id:name}, swatches:{재질:[hex]}, defaults:{재질:hex},
          illustrations:{id:{name,job,hairstyles:{머리id:이름}}}}.
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
    # 완성 SD 외형도 같은 look에 기록한다. 파츠를 함께 보존해 구형 뷰어의 폴백을 유지한다.
    atlas_path = os.path.join(os.path.dirname(sprites_path), "sd", "atlas.json")
    illustrations = {}
    if os.path.exists(atlas_path):
        with io.open(atlas_path, encoding="utf-8") as f:
            atlas = json.load(f)
        illustrations = {sid: {"name": p["name"], "job": p["job"],
                              "hairstyles": {hid: h["name"] for hid, h in
                                             p.get("hairstyles", {"default": {"name": "기본 머리"}}).items()},
                              # 세계 안에서 보이는 모습(looks_line 용 — name 은 고르는 목록의 분류 이름): 체격 = 성별 · 옷 한 줄 · 헤어 한 줄
                              "sex": p.get("sex"), "looks": p.get("looks"),
                              "hair_looks": {hid: h["looks"] for hid, h in (p.get("hairstyles") or {}).items() if h.get("looks")}}
                         for sid, p in atlas.get("presets", {}).items()}
    data = {"heads": heads, "bodies": bodies, "swatches": swatches, "defaults": defaults,
            "illustrations": illustrations}
    _LOOKS[key] = data
    return data


def sanitize_look(look, data=None):
    """외형 필드 검증·정규화 — {head, body, colors{hair,skin,top,bottom}, sprite?, hairstyle?}.
    머리·몸통은 sprites.json 등재 id 만, 색은 '#rrggbb' 형식만(스와치 밖 자유 색 허용 — 가정 B),
    빠진 색은 기본색으로 보충·소문자 정규화. None 이면 None(=시트에 필드 없음 → 러너가 랜덤으로 뽑는다).
    프롬프트에 닿는 것은 '낯선 사람' 판의 겉모습 한 줄(looks_line)뿐이고, 그것도 등재된 이름(완성 외형·헤어)이나 정해진 색 이름
    (color_word)으로만 나간다 — 그래서 자유 색을 받아도 UGC 관문이 아니다(사용자가 쓴 글자는 프롬프트에 안 들어간다)."""
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
    result = {"head": head, "body": body, "colors": out_c}
    sprite = look.get("sprite")
    if sprite is not None:
        if not isinstance(sprite, str) or sprite not in data.get("illustrations", {}):
            raise ValueError("등재되지 않은 완성 외형: %r" % (sprite,))
        result["sprite"] = sprite
    hairstyle = look.get("hairstyle")
    if hairstyle is not None:
        styles = data.get("illustrations", {}).get(sprite, {}).get("hairstyles", {})
        if not isinstance(hairstyle, str) or hairstyle not in styles:
            raise ValueError("이 외형에 등재되지 않은 헤어스타일: %r" % (hairstyle,))
        # 필드가 없는 기존 저장본은 그대로 둔다. 새 선택만 기록한다.
        result["hairstyle"] = hairstyle
    return result


def color_word(hx):
    """hex 색 → 한국어 색 이름(D85, 2026-09-19 — 낯선 사람의 겉모습 문장용 · ⚠️어휘 임시). 스와치 밖 자유 색도 받는다(가까운 이름)."""
    import colorsys
    try:
        h_ = str(hx).lstrip("#")
        r, g, b = (int(h_[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return "빛바랜"
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.25:
        return "검은" if v < 0.3 else ("회색" if v < 0.72 else "흰")
    deg = h * 360
    if deg < 20 or deg >= 330:
        return "붉은"
    if deg < 35:
        return "갈색" if v < 0.75 else "주황"
    if deg < 70:
        return "금빛" if v >= 0.6 else "황갈색"
    if deg < 170:
        return "녹색"
    if deg < 200:
        return "청록"
    if deg < 255:
        return "푸른"
    return "보랏빛"


SEX_LOOKS = {"남": "남자", "여": "여자"}       # 완성 외형의 체격 = 겉으로 보이는 성별(⚠️어휘 임시)


def looks_line(bot):
    """겉으로 보이는 것 한 줄(D85) — 그림 그대로. 완성 외형(look.sprite)이면 외형 사전이 적어 둔 '보이는 모습'(looks):
    성별(체격 — 파트너 09-19 "체격은 원래 여성 남성을 구분하려고 만든거라 성별으로 두면 될것 같아") · 옷 한 줄 · 헤어 한 줄
    ("여자 · 녹색 두건 망토 · 녹색 리본으로 묶은 금발 포니테일"). 완성 외형은 머리색·옷이 그림에 고정이라 옛 colors 는 그림과 무관한
    잔재다 — 안 읽는다. looks 가 없는 항목(옛 3종)은 분류 이름으로 물러난다(파트너 "색깔같은 정보보다는 궁수, 남성형, 리본 포네테일
    이렇게 전달하면 되잖아" → "외형 네이밍은 좀 많이 다르게 … 사전에 넣기 좋게 가공"). 파츠 조합(종이인형)이면 그 색이 곧 그림이라
    머리색·윗옷색. 뒤에 찬 무기·걸친 갑옷. 이름·직업은 겉으로 안 보인다(옷을 보고 직업을 짐작하는 것은 보는 사람의 몫)."""
    look = bot.get("look") or {}
    bits = []
    ill = None
    if look.get("sprite"):
        try:
            ill = (load_looks().get("illustrations") or {}).get(look["sprite"])
        except (OSError, ValueError):              # 외형 사전을 못 읽는 배치 — 아래 색으로 물러난다
            ill = None
    if ill:
        hid = look.get("hairstyle") or "default"
        if ill.get("looks"):
            if ill.get("sex") in SEX_LOOKS:
                bits.append(SEX_LOOKS[ill["sex"]])
            bits.append(ill["looks"])
        else:
            name = ill["name"]
            bits.append(name[3:] if name.startswith("SD ") else name)     # 옛 3종의 이름 머리말 'SD '는 세계의 말이 아니다
        hair = (ill.get("hair_looks") or {}).get(hid) or (ill.get("hairstyles") or {}).get(hid)
        if hair:
            bits.append(hair)
    else:
        colors = look.get("colors") or {}
        if colors.get("hair"):
            bits.append("%s 머리" % color_word(colors["hair"]))
        if colors.get("top"):
            bits.append("%s 윗옷" % color_word(colors["top"]))
    for slot in ("weapon", "armor"):
        it = bot.get(slot)
        if isinstance(it, dict) and it.get("name"):
            bits.append(it["name"])
    return " · ".join(bits)


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
    persona_text: 성격 자유 서술(파트너 정정 09-05 — 키워드 뒤에 이어붙이고, 키워드 0개면 이것만).
    키워드와 자유 서술 중 하나는 있어야 한다. 합계가 PERSONA_TOTAL_MAX 를 넘으면 거부(조용한 절단 금지).
    persona = 키워드 그대로(2026-09-12 개정, 파트너 메모 §3-3): "신중한, 겁 많은" · 자유 서술이 있으면
    "신중한, 겁 많은. <서술>" — 문장 템플릿 없음. speech 는 만들지 않는다(손 시트의 speech 만 산다).
    반환 시트에는 원본 키워드도 `traits` 로 남긴다 — run_meta 기록(부검)·론처 복원에 쓴다."""
    data = data or load_traits()
    jobs, keywords = data["jobs"], data["traits"]
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
        if t not in keywords:
            raise ValueError("등재되지 않은 성격 키워드: %r" % (t,))
    kw = ", ".join(traits)                       # 키워드 그대로 — 복수는 ', ' 로(⚠️임시 가정, 파트너 미답)
    persona = (kw + ". " + ptxt) if (kw and ptxt) else (kw or ptxt)
    body = jobs[job]
    sheet = {
        "job": job, "sex": sex,
        "hp": body["hp"], "str": body["str"], "dex": body["dex"], "wdmg": body["wdmg"],
        "stealth": body["stealth"], "search_r": body["search_r"], "atk_range": body["atk_range"],
        "persona": persona,
        "name": sanitize_name(name),
        "traits": list(traits),
    }
    if len(sheet["persona"]) > PERSONA_TOTAL_MAX:
        raise ValueError("성격 문장 합계가 %d자를 넘는다(%d자) — 키워드를 줄이거나 문장을 줄여라"
                         % (PERSONA_TOTAL_MAX, len(sheet["persona"])))
    # 직업은 몸 수치만 정한다. 사용자가 쓰지 않은 행동 목표를 직업 사전에서 보충하지 않는다.
    # 직접 작성한 시트의 선택 필드 goal은 기존 load_party → 프롬프트 경로에서 그대로 지원한다.
    bg = sanitize_background(background)
    if bg:
        sheet["background"] = bg
    lk = sanitize_look(look)                     # D37 외형 — 없으면 필드 없음(러너가 랜덤)
    if lk:
        sheet["look"] = lk
    return sheet


COMPANION_TEXT_MAX = 300   # 동료 프리셋의 말투·목표 상한 — 러너 load_party 의 FREETEXT_MAX 와 같은 값
COMPANION_SHEET_KEYS = ("job", "sex", "traits", "persona", "speech", "goal", "background", "look")


def build_companion_sheet(defn, data=None):
    """동료 프리셋 정의(entities/companion/<id>.json, D81) → party 시트.
    정의의 comps.sheet 는 '파티 시트 칸'만 든다(job·sex·traits·persona·speech·goal·background·look) — 능력치는 적지 않고
    직업에서 온다(build_sheet 그대로). 말투·목표는 손 시트(party.json)처럼 그대로 싣는다(같은 정제·상한).
    이름은 정의의 name — 정제 뒤에 달라지는 이름은 거부한다(화면에 보인 이름 = 판에 선 이름)."""
    if not isinstance(defn, dict) or not isinstance((defn.get("comps") or {}).get("sheet"), dict):
        raise ValueError("동료 프리셋에 sheet 부품이 없다")
    comp = defn["comps"]["sheet"]
    extra = sorted(set(comp) - set(COMPANION_SHEET_KEYS))
    if extra:
        raise ValueError("sheet 부품이 모르는 칸: %s" % ", ".join(extra))
    sheet = build_sheet(comp.get("job"), comp.get("traits") or [], defn.get("name", ""), comp.get("sex"),
                        comp.get("background"), data=data, persona_text=comp.get("persona"), look=comp.get("look"))
    if sheet["name"] != defn.get("name"):
        raise ValueError("이름이 정제 뒤 달라진다: %r → %r" % (defn.get("name"), sheet["name"]))
    for k in ("speech", "goal"):
        v = comp.get(k)
        if v is None:
            continue
        if not isinstance(v, str):
            raise ValueError("%s 는 문자열이어야 한다" % k)
        v = sanitize_freetext(v, COMPANION_TEXT_MAX)
        if v:
            sheet[k] = v
    return sheet


def build_party(slots, data=None, companions=None):
    """슬롯 목록(1~3, 각 {job, traits, name, sex, background?}) → party.json 형태 {'1':..,'2':..}.
    이름 중복은 load_party 가 거부하지만(도감 원장 키) 여기서도 먼저 잡아 이유를 사람말로 돌려준다.
    D81: 슬롯이 {"companion": "<id>"} 면 동료 프리셋이다 — companions({id: 정의})에서 찾아 build_companion_sheet 로.
    사전을 안 넘기면(None) 동료 칸은 거부한다(옛 호출부는 그대로)."""
    data = data or load_traits()
    if not isinstance(slots, (list, tuple)) or not (1 <= len(slots) <= 3):
        raise ValueError("파티는 1~3인")
    out, names = {}, set()
    for i, s in enumerate(slots, start=1):
        if not isinstance(s, dict):
            raise ValueError("슬롯 %d 형식 오류" % i)
        if s.get("companion") is not None:
            cid = s.get("companion")
            if not isinstance(cid, str) or cid not in (companions or {}):
                raise ValueError("슬롯 %d: 없는 동료 프리셋 %r" % (i, cid))
            sheet = build_companion_sheet(companions[cid], data=data)
            if sheet["name"] in names:
                raise ValueError("이름 중복: %s" % sheet["name"])
            names.add(sheet["name"])
            out[str(i)] = sheet
            continue
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
