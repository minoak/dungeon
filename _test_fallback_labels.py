# 임시 단위 테스트 — 폴백 계측 라벨 경로 전수 (LLM 0콜, 모킹)
import json
import brains
import dungeon_gm as G

d = G.Dungeon(seed=7, w=40, h=16, n_monsters=2, n_traps=2, n_lurkers=0)
bots = []
bots.append(G.spawn(d, "1", bots))
bots.append(G.spawn(d, "2", bots))
b = bots[0]
obs = d.view(b, bots)

fails = []
def check(name, cond, got=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  <- %r" % (got,)))
    if not cond:
        fails.append(name)

# ① _extract 라벨 경로
o, w = brains._extract("")
check("빈 입력 -> (None, None)", o is None and w is None, (o, w))
o, w = brains._extract("고블린이 나타났다! 도망쳐!")
check("JSON 없음 라벨", o is None and w.startswith("JSON 없음: 고블린이"), (o, w))
o, w = brains._extract('{"choice": broken}')
check("JSON 불량 라벨", o is None and w.startswith("JSON 불량:"), (o, w))
o, w = brains._extract('```json\n{"choice": 1, "reason": "가자"}\n```')
check("코드펜스 정상 파싱", o == {"choice": 1, "reason": "가자"} and w is None, (o, w))

# ② claude_brain 폴백 reason — 실패 종류별
def brain_with(ret):
    brains._call_claude = lambda prompt, model="haiku": ret
    return brains.claude_brain(obs, b["char"], b, bots)

r = brain_with(("", "타임아웃 60s"))
check("타임아웃 라벨 전파", r["src"] == "fallback" and "타임아웃 60s" in r["reason"], r["reason"])
r = brain_with(("", "빈 응답 rc=1 | Error: rate limit"))
check("빈 응답+stderr 라벨 전파", "rc=1" in r["reason"] and "rate limit" in r["reason"], r["reason"])
r = brain_with("")                      # 구식 str 모킹(verify 표면) — 하위호환
check("str 모킹 하위호환(파싱 실패)", r["src"] == "fallback" and "파싱 실패" in r["reason"], r["reason"])
r = brain_with("아무 JSON 없는 잡담")
check("JSON 없음 -> reason", "JSON 없음" in r["reason"], r["reason"])
r = brain_with('{"choice": 999, "say": "돌격", "reason": "이유"}')
check("무효 choice -> 행동 해석 실패 라벨", r["src"] == "fallback" and "행동 해석 실패" in r["reason"], r["reason"])

# ③ 정상 경로 무손상 — 유효 choice는 여전히 haiku
opt1 = (obs.get("options") or [{}])[0].get("n", 1)
r = brain_with(json.dumps({"choice": opt1, "say": "간다", "reason": "이유"}))
check("유효 choice 정상 경로(src=haiku)", r["src"] == "haiku" and r.get("choice") == opt1, r)

print()
print("결과: %d FAIL" % len(fails))
raise SystemExit(1 if fails else 0)
