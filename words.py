# -*- coding: utf-8 -*-
"""말 파일 — prompts/world/<종류>/<id>.md (D100, 2026-10-06 · 파트너 10-04 "프롬프트 폴더를 아예 프로젝트화 해서 거기서 전담으로 수정작업").

엔티티 정의(entities/<종류>/<id>.json)는 숫자·규칙·식별자만 들고, 사람과 캐릭터가 읽는 말(대사·성격·설명·지식 본문)은 이 파일들이 든다.
정의 JSON 의 그 칸에는 "@prompts" 표시만 남는다(칸 순서가 그대로라 옮기기 전후의 정의가 글자 하나까지 같다 — verify_words 가 대조한다).
entities.read() 가 둘을 합친다 — 엔진·러너·게이트는 합쳐진 정의만 본다(코드 무수정). 이름(name)은 JSON 에 남는다(도감·대사 표·
클라이언트 npcs.ts 의 열쇠).

파일 꼴(사람이 고치기 쉽게 — 따옴표·쉼표 없음):
    # 성직자 · temple_attendant
    <!-- 주석은 무시된다 -->
    ## `npc.line` — 첫 대사(말을 걸면 · 관전 말풍선)
    기도를 들었어요. …
    ## `overheard` — 구역에 들어설 때 들리는 말(목록)
    - 첫 줄
    - 둘째 줄
· `## ` 뒤 백틱 안 = 칸 이름(정의의 comps 아래 경로 — 엔진이 읽는 열쇠, 바꾸지 않는다). 줄표(—) 뒤 = 사람이 보는 설명(고쳐도 된다).
· 목록 칸(LIST_WORDS)은 한 줄에 하나씩 "- " 로 시작한다. 나머지 칸은 본문 그대로(앞뒤 빈 줄은 걷는다).
· {name} 같은 중괄호 자리는 엔진이 채운다 — 남긴다.
· 경계: prompts/ 안은 파트너가 고치는 '말', 밖은 코드. 말 파일을 고친 뒤 `python tools/check_words.py` 로 확인한다.
· 정의와 말 파일이 어긋나면(표시는 있는데 칸이 없다 · 칸은 있는데 표시가 없다) 정의 오류다 — 모르는 부품과 같은 급으로 읽기를 거절한다.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS_ROOT = os.path.join(HERE, "prompts", "world")
ACTIONS_ROOT = os.path.join(HERE, "prompts", "actions")   # p0.5.5 행동 말 파일 — 정의 JSON 없이 칸 이름이 곧 열쇠(common_extra.md: header + 등록부 동사)
WORD_MARK = "@prompts"
LIST_WORDS = ("texts", "wares", "overheard")       # 목록 칸 — 마지막 키가 이 이름이면 문자열 목록
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_HEAD = re.compile(r"^## `([^`]+)`")

# 말 칸 판별: comps 아래 경로의 마지막 키. space.role(구역의 종류 = 식별자)·note(개발 메모)·walk(걷는 자리) 등은 말이 아니다.
_WORD_KEYS = {"role", "persona", "trait", "history", "brief", "deep", "text", "texts", "wares", "goal", "reward", "client",
              "overheard", "speech", "background",
              "desc", "lore",                       # p0.5.6 아이템 — item.desc(물건 설명) · item.lore(속 — 자리만)
              "about",                              # p0.5.16 욕구 — need.about(한 줄 뜻). 단계 몸 문장·결과 꼬리는 끝 키가 line 이라 이미 말 칸이다
              "why"}                                # p0.5.18 욕구 — 단계·기분 조각의 기분 이유 낱말(need.stages.<단계>.why · need.mood.<갈래>.why)
_NOT_WORDS = ("space.",)                            # 이 접두의 경로는 말이 아니다(구역 종류 id)

# 사람용 설명 — (경로 끝 맞춤, 설명). 앞의 것이 이긴다. life.* 는 describe 가 꼬리를 붙인다. 말 파일 제목 줄의 줄표 뒤에 찍힌다.
DESC = [
    ("building.role", "건물 역할 한 줄 — 관측의 건물 줄 괄호 「모험가 길드 (…)」"),
    ("npc.role", "역할 한 줄 — 마을에서 늘 보이는 사람 줄의 괄호 「성직자 (…)」"),
    ("sheet.persona", "성격 — 파티에 뽑히면 이 캐릭터의 시트가 된다(매 결정 읽는다)"),
    ("sheet.speech", "말투 — 파티에 뽑히면 시트"),
    ("sheet.goal", "목표 — 파티에 뽑히면 시트"),
    ("sheet.background", "소개 — 파티에 뽑히면 시트"),
    ("persona", "성격 — NPC 두뇌가 답을 쓸 때만 읽는다(캐릭터는 못 본다)"),
    ("npc.line", "첫 대사 — 캐릭터가 말을 걸면(NPC 두뇌가 꺼졌거나 실패하면 이 문장 그대로) · 관전 말풍선"),
    ("line_again", "다시 말을 걸 때 — 같은 방문 두 번째부터"),
    ("hail_no_potion", "인사 대신 — 그 캐릭터가 물약이 없을 때"),
    ("hail_board", "인사 대신 — 게시판에 안 맡은 의뢰가 남아 있을 때({quests} = 개수)"),
    ("hail_return", "인사 대신 — 원정에서 돌아온 뒤"),
    ("hail_party", "인사 대신 — 파티 결성 판에서({party_need} = 인원)"),
    ("hail_oracle", "인사 대신 — 신의 요청이 걸려 있을 때"),
    ("hail_blessed", "인사 대신 — 이미 축복을 받은 사람에게(공물 판)"),
    ("hail", "먼저 거는 인사 — 같은 구역 6칸 안을 처음 지날 때(캐릭터당 한 번)"),
    ("line_report_failed", "귀환 보고 — 맡은 의뢰가 미완일 때({undone} = 제목)"),
    ("line_report_empty", "귀환 보고 — 맡은 의뢰가 없었을 때"),
    ("line_report", "귀환 보고 — 맡은 의뢰를 완수했을 때({done} = 제목)"),
    ("line_party", "파티 결성 판에서 덧붙이는 말({party_need} = 인원)"),
    ("line_blessed", "이미 축복을 받은 사람이 말을 걸 때(공물 판)"),
    ("line_close", "닫는 말 — 한 방문에 이 사람과 나눈 대화가 상한에 닿는 마지막 대답(NPC 두뇌가 꺼졌거나 실패할 때 · 선택, 없으면 공통 문장)"),
    ("line", "첫 대사 — 말을 걸면 · 관전 말풍선"),
    ("story.trait", "특징 한 줄 — 늘 보인다(멀리서도 · 관측 줄 끝)"),
    ("story.history", "이야기 — 곁 2칸에 섰을 때 '네 상태' 절에 한 줄"),
    ("item.desc", "물건 설명 — 보이거나 지닐 때 대상 목록에 붙는다({bonus} 등 중괄호는 엔진이 채운다)"),
    ("item.lore", "속 — 살펴서(search) 드러나는 내력(아직 아무도 읽지 않는 자리)"),
    ("knowledge.brief", "처음 알게 된 한 줄 — 도감에 오를 때"),
    ("knowledge.deep", "깊은 지식 — 알게 된 뒤(몬스터는 조우를 쌓아 해금)"),
    ("use.texts", "살펴볼 때마다 하나씩 나오는 글(목록)"),
    ("use.text", "읽으면(쓰면) 나오는 글"),
    ("use.wares", "구경하면 보이는 진열품(목록)"),
    ("quest.goal", "게시판의 목표"),
    ("quest.reward", "게시판의 보상"),
    ("quest.client", "게시판의 의뢰인"),
    ("overheard", "구역에 들어설 때 들리는 말(목록 — 마을 생활 판에서 하나씩 뽑힌다)"),
]


def describe(kind, path):
    """(종류, 경로) → 사람용 설명 한 줄. 모르는 경로면 빈 문자열(제목에 줄표가 안 붙는다)."""
    base = path[5:] if path.startswith("life.") else path
    if kind == "need":                              # p0.5.16 욕구 — 단계 id·기분 갈래가 경로 가운데에 든다(끝 맞춤으로는 못 가른다)
        return ("욕구의 한 줄 뜻 — 캐릭터를 만들 때 무게를 정하는 데 쓴다(게임 프롬프트엔 안 나간다)" if base == "need.about"
                else "몸 문장 — 그 단계에 있는 동안 '몸:' 줄에 뜬다(상태 그대로 · 지시·권유 없이)" if ".stages." in base and base.endswith(".line")
                else "기분 이유 — 그 단계에 있는 동안 '기분:' 줄의 이유에 든다(짧은 명사구)" if ".stages." in base and base.endswith(".why")
                else "기분 이유 — 채운 뒤 정해진 틱 동안 '기분:' 줄의 이유에 든다(짧은 명사구 · {what} = 먹은 것 · {what:을} = 이름 + 조사)"
                if ".mood." in base and base.endswith(".why")
                else "결과 꼬리 — 먹은 순간의 결과 문장에 덧붙는다(사실 한 마디 · {what} 자리 가능)" if ".mood." in base and base.endswith(".line")
                else "")
    d = next((txt for tail, txt in DESC if base == tail or base.endswith("." + tail)), "")
    if kind == "companion" and path.startswith(("npc.", "story.")):
        d += " · 동료로 안 뽑혀 마을 주민일 때"
    if path.startswith("life."):
        d += " · 마을 생활을 켠 판에서 위 칸 대신"
    return d


def is_word_path(path):
    """comps 아래 경로(점으로 이음) → 말 칸인가."""
    if any(path.startswith(p) for p in _NOT_WORDS):
        return False
    last = path.rsplit(".", 1)[-1]
    return last in _WORD_KEYS or last == "line" or last.startswith("line_") or last == "hail" or last.startswith("hail_")


def is_list_path(path):
    return path.rsplit(".", 1)[-1] in LIST_WORDS


def word_paths(comps, prefix=""):
    """정의의 comps → [(경로, 값)] — 말 칸 전부(문자열, 또는 LIST_WORDS 의 문자열 목록). 정의 안 순서 그대로. 옮기기(이전) 도구가 쓴다."""
    out = []
    for k, v in comps.items():
        p = prefix + k
        if isinstance(v, dict):
            out += word_paths(v, p + ".")
        elif is_word_path(p) and (isinstance(v, str) or (k in LIST_WORDS and isinstance(v, list)
                                                          and all(isinstance(x, str) for x in v))):
            out.append((p, v))
    return out


def mark_paths(comps, prefix=""):
    """정의의 comps 에서 "@prompts" 표시가 선 자리 → [경로] (정의 안 순서)."""
    out = []
    for k, v in comps.items():
        p = prefix + k
        if isinstance(v, dict):
            out += mark_paths(v, p + ".")
        elif v == WORD_MARK:
            out.append(p)
    return out


def word_file(words_root, kind, eid):
    return os.path.join(words_root, kind, eid + ".md")


def parse(text):
    """말 파일 → ({경로: 값}, [문제]). 값은 문자열 또는(LIST_WORDS) 문자열 목록."""
    text = _COMMENT.sub("", text.replace("\r\n", "\n"))
    if text.startswith("﻿"):
        text = text[1:]
    items, problems = {}, []
    cur, buf = None, []

    def flush():
        if cur is None:
            return
        lines = [ln.rstrip() for ln in buf]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if is_list_path(cur):
            vals = []
            for ln in lines:
                if not ln.strip():
                    continue
                if not ln.startswith("- "):
                    problems.append("`%s` 은(는) 목록 칸이다 — 줄마다 '- ' 로 시작해야 한다: %r" % (cur, ln[:40]))
                    continue
                vals.append(ln[2:].strip())
            items[cur] = vals
        else:
            items[cur] = "\n".join(lines)

    for ln in text.split("\n"):
        m = _HEAD.match(ln)
        if m:
            flush()
            cur, buf = m.group(1).strip(), []
            if cur in items:
                problems.append("`%s` 칸이 두 번 나온다" % cur)
        elif ln.startswith("## "):
            flush()
            cur, buf = None, []
            problems.append("제목에 `칸 이름` 이 없다: %r" % ln[:50])
        elif ln.startswith("# ") and cur is None:
            continue                                  # 파일 제목(사람용)
        elif cur is not None:
            buf.append(ln)
    flush()
    return items, problems


GUIDE = ("<!-- 이 파일의 말은 entities/%s/%s.json 의 \"@prompts\" 자리로 들어간다(엔진이 둘을 합쳐 읽는다).\n"
         "     · `## ` 뒤 백틱 안의 칸 이름은 바꾸지 않는다(엔진이 읽는 열쇠). 줄표(—) 뒤 설명은 사람용이라 고쳐도 된다.\n"
         "     · {name} 같은 중괄호는 엔진이 채우는 자리라 남긴다. 목록 칸은 한 줄에 하나씩 '- ' 로 시작한다.\n"
         "     · 이런 주석 상자 안의 글은 엔진이 읽지 않는다. 고친 뒤 `python tools/check_words.py` 로 확인한다. -->")


def render(kind, eid, name, pairs):
    """[(경로, 값)] → 말 파일 텍스트(새 정의의 말 파일을 처음 만들 때 · 이전 도구)."""
    out = ["# %s · %s" % (name, eid), "", GUIDE % (kind, eid), ""]
    for p, v in pairs:
        d = describe(kind, p)
        out.append("## `%s`%s" % (p, (" — " + d) if d else ""))
        if isinstance(v, list):
            out += ["- " + x for x in v]
        else:
            out.append(v)
        out.append("")
    return "\n".join(out)


def merge(d, kind, eid, words_root=WORDS_ROOT):
    """정의 d(JSON 그대로)의 "@prompts" 자리에 말 파일의 값을 채운다(제자리). → [문제]. 표시도 말 파일도 없으면 아무 일 없다.
    문제가 있으면 d 는 손대지 않는다(반쯤 합친 정의를 남기지 않는다)."""
    comps = d.get("comps")
    if not isinstance(comps, dict):
        return []
    marks = mark_paths(comps)
    rel = "prompts/world/%s/%s.md" % (kind, eid)
    path = word_file(words_root, kind, eid)
    if not os.path.exists(path):
        if not marks:
            return []
        return ["%s: 말 파일이 없다 — 정의에 \"@prompts\" 자리 %d개: %s" % (rel, len(marks), ", ".join(marks))]
    with open(path, encoding="utf-8") as f:
        items, problems = parse(f.read())
    problems = ["%s: %s" % (rel, p) for p in problems]
    for p in marks:
        if not is_word_path(p):
            problems.append("%s: `%s` 는 말 칸이 아니다(숫자·규칙·식별자는 정의 JSON 에 둔다)" % (rel, p))
        elif p not in items:
            problems.append("%s: 정의의 \"@prompts\" 자리 `%s` 칸이 말 파일에 없다" % (rel, p))
    for p in items:
        if p not in marks:
            problems.append("%s: 칸 `%s` 가 정의(entities/%s/%s.json)에 \"@prompts\" 자리로 없다" % (rel, p, kind, eid))
    if problems:
        return problems
    for p in marks:
        node = comps
        ks = p.split(".")
        for k in ks[:-1]:
            node = node[k]
        node[ks[-1]] = items[p]
    return []


class WordsError(ValueError):
    """행동 말 파일을 못 읽음 — 정의 오류와 같은 급(게임이 뜨지 않는다). check_words 가 같은 문장을 찍는다."""


def action_words(name, root=ACTIONS_ROOT):
    """p0.5.5 행동 말 파일 prompts/actions/<name>.md → {칸: 문장}. 꼴은 세계 말 파일과 같다(`## \\`칸\\` — 설명` · 주석 무시).
    엔티티 정의가 없으니 칸 이름이 곧 열쇠다 — 어느 칸이 있어야 하는지는 쓰는 쪽(composed_actions 등록부)이 정하고 check_words 가 대조한다.
    문장 칸은 한 줄이어야 한다(관측 블록의 한 줄이 된다). 문제가 있으면 WordsError."""
    return _flat_words(os.path.join(root, name + ".md"), "prompts/actions/%s.md" % name)


def world_words(name, root=WORDS_ROOT):
    """p0.5.18 세계 말 폴더 맨 위의 낱말 파일 prompts/world/<name>.md → {칸: 문장}(꼴·검사는 action_words 와 같다).
    모든 행동 방식의 관측에 실리는 낱말 — 종류 폴더(엔티티 정의의 짝)가 아니라 폴더 맨 위에 둔다(지문 'prompts/world/' 에 든다 · mood = '기분:' 줄)."""
    return _flat_words(os.path.join(root, name + ".md"), "prompts/world/%s.md" % name)


def _flat_words(path, rel):
    try:
        with open(path, encoding="utf-8") as f:
            items, problems = parse(f.read())
    except OSError as e:
        raise WordsError("%s: 말 파일을 못 읽는다 — %s" % (rel, type(e).__name__))
    problems = ["%s: %s" % (rel, p) for p in problems]
    for k, v in items.items():
        if not isinstance(v, str) or not v.strip():
            problems.append("%s: `%s` 칸이 비어 있다" % (rel, k))
        elif "\n" in v:
            problems.append("%s: `%s` 칸은 한 줄이어야 한다(관측의 한 줄이 된다)" % (rel, k))
    if problems:
        raise WordsError("\n".join(problems))
    return items


def orphans(root, words_root=WORDS_ROOT):
    """정의가 없는 말 파일 → ['npc/x.md', …]. 읽기를 막지는 않는다(초안을 먼저 써 둘 수 있다) — check_words 가 경고로 찍는다."""
    out = []
    for kind in sorted(os.listdir(words_root)) if os.path.isdir(words_root) else []:
        kd = os.path.join(words_root, kind)
        if not os.path.isdir(kd):
            continue
        for fn in sorted(os.listdir(kd)):
            if fn.endswith(".md") and not os.path.exists(os.path.join(root, kind, fn[:-3] + ".json")):
                out.append("%s/%s" % (kind, fn))
    return out
