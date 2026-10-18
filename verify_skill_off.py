# -*- coding: utf-8 -*-
"""알파 OFF의 행동·관측·상태·RNG를 기준선 해시와 대조한다.
기준선 이력: 78fbe84(compose-v0.4, 2026-09-10) → **2026-09-11 D51 갱신**: 고블린 도주가 "근처 다른 몹에게 붙어 같이 싸운다"로
의도적으로 바뀌어(파트너 결정) 시드 7의 흔적이 달라졌다(37·217 은 그대로) — 새 해시는 D51 커밋의 코드에서 뽑았다. 그 외(엔티티 저장소 D50·거미 도주 제거)는
해시가 그대로였다. 기준선을 옮길 때는 반드시 여기 이력과 커밋 메시지에 사유를 적는다.
**2026-09-13 D66 갱신**: 관측 `exit.gather`(모임 규칙을 계단 줄에 미리 — 파트너 "팀원이 전부 모여야 계단을 내려갈 수 있다고 가르쳐줘야")가
obs 에 더해져 세 시드 전부 관측 해시가 달라졌다(행동·난수는 같은 코드 경로 — 의도된 관측 계약 변경). 새 해시는 D66 커밋의 코드에서 뽑았다.
**2026-10-11 t13c 갱신**: 관리자 승인으로 공격 표시용 선택 필드
attack_mode/source_xy/target_xy가 결과와 관측에 추가된 세 시드 해시를 갱신했다.
세 필드만 제거하면 D66 해시와 모두 일치한다(verify_combat_stream). 게임 판정·상태·난수 변경은 없다.
**2026-10-12 p0.5.5 갱신**: 관측 계약 문자열 obs.action_schema 가 compose-v0.4 → compose-v0.5(행동 등록부·추가 행동 블록 자리,
master_plan §7.1). 등록부가 비어 관측의 다른 칸·행동·상태·난수는 그대로다 — 그 문자열만 v0.4 로 되돌리면(schema_v04) t13c 해시와
세 시드 모두 일치한다(아래 main 이 함께 확인). 새 해시는 p0.5.5 작업 트리 코드에서 뽑았다.
**2026-10-12 p0.5.6 갱신**: 조합형 관측의 아이템 줄(바닥 물약·장비·보물, 소지품)에 물건 설명 desc·다루는 규칙 rule 칸이 더해지고 보물 태그에 item 이
붙었다(item_desc_design D1·D2·D4). 행동·상태·난수는 그대로다 — 그 두 칸과 태그만 되돌리면(items_v055) p0.5.5 해시와 세 시드 모두 일치한다.
새 해시는 p0.5.6 작업 트리 코드에서 뽑았다.
**2026-10-15 p0.5.13 갱신**(경제 1a): 새 몸이 골드 5를 지닌다 — 관측에 gold 칸, 봇 스냅샷에 gold 칸, 조합형 소지품·대상 목록에 i7(골드) 줄이 더해졌다.
보물을 지닌 몸의 소지품·대상 목록에 i8(보물) 줄, 보물의 다루는 규칙에 amount 한 문장도 더해졌다.
행동·상태·난수는 그대로다 — 그것만 되돌리면(gold_v0512) p0.5.6 해시와 세 시드 모두 일치한다. 새 해시는 p0.5.13 작업 트리 코드에서 뽑았다.
**2026-10-16 p0.5.16 갱신**(욕구 틀 + 배고픔): 새 몸이 욕구 충족도(needs — 배고픔 시작값 70)를 지닌다 — 봇 스냅샷에 needs 칸이 더해졌다
(이 판은 러너의 틱 머리가 아니라 엔진만 돌려 줄기가 없고, 보통 단계라 관측의 '몸과 기분'·휴대식·기분 조각 칸은 나오지 않는다).
행동·상태·난수는 그대로다 — 그 칸만 되돌리면(needs_v0515) p0.5.13 해시와 세 시드 모두 일치한다. 새 해시는 p0.5.16 작업 트리 코드에서 뽑았다.
**2026-10-17 p0.5.27 갱신**(시작 골드 5 → 10 — DECISIONS 10-17): 새 몸의 골드가 10 이다 — 봇 스냅샷·관측의 gold 칸과 소지품·대상 목록의 i7(골드) 줄 개수가 5 크다
(이 판은 가게·의뢰가 없는 던전이라 골드가 움직이지 않는다). 행동·상태·난수는 그대로다 — 그 값만 5 줄이면(start_gold_v0525) p0.5.16 해시와 세 시드 모두 일치한다.
새 해시는 p0.5.27 작업 트리 코드에서 뽑았다.
**2026-10-18 p0.5.29b 갱신**(동사 세트에 buy·sell — 관리자 결정: 세트가 바뀐 패치가 계약 판본을 올린다): 관측 계약 문자열 obs.action_schema 가
compose-v0.5 → compose-v0.6. 이 판(가게 없는 던전·규칙 두뇌)의 관측 dict·행동·상태·난수는 그대로다(0.5.29 의 buy·sell 은 이 해시를 바꾸지 않았다) —
그 문자열만 v0.5 로 되돌리면(schema_v05) p0.5.27 해시와 세 시드 모두 일치한다. 새 해시는 p0.5.29b 작업 트리 코드에서 뽑았다."""
import hashlib
import json
import os

os.environ['DUNGEON_SIGHT'] = '5'
import dungeon_gm as G


def trace_records(seed):
    """해시 전 원본 기록. 비교 검증도 같은 실행 경로를 사용한다."""
    d = G.Dungeon(seed=seed, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1,
                  scan=True, loops=True, status=True, rest_verb=True, events=True, relations=True,
                  auto_approach=True, composed_actions=True)
    bots = []
    for char in ('1', '2'):
        bots.append(G.spawn(d, char, bots))
    records = [{'level': d.level_snapshot(), 'bots': [G.bot_snapshot(b) for b in bots]}]
    for turn in range(1, 81):
        d.turn = turn
        results, observations = [], []
        for b in bots:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                results.append(d.step_order(b, bots))
            else:
                obs = d.view(b, bots)
                observations.append(obs)
                action = G.CA.fallback(G.dummy_brain(obs, b['char']), obs)
                results.append(d.act(b, action, bots))
        results.extend(d.monster_turn(bots))
        records.append({'turn': turn, 'observations': observations, 'events': results,
                        'bots': [G.bot_snapshot(b) for b in bots], 'monsters': [m.as_dict() for m in d.monsters]})
    records.append({'rng_state': d.rng.getstate()})
    return records


def digest(records):
    return hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def trace(seed):
    return digest(trace_records(seed))


PRE_FX_EXPECTED = {   # 2026-09-13 D66 기준선 — 표시 필드만 뺀 회귀 비교용으로 보존
    7: '7381c95b866374db5bf05e6e9d2024ce46ac1aff3d7a961fab48f5ede06f967e',
    37: '1f61907254608ef7ba9eb18cbebf5563a1d4b835bb4e372734f3b349884f648e',
    217: 'b4645146ea661824cb7b7da8321cdb9a562ab8a5e93c4f3e5ea5bd214418bbe3',
}

T13C_EXPECTED = {   # 2026-10-11 t13c 관리자 승인: 표시 필드 세 개만 추가 — 관측 계약 compose-v0.4 시절(p0.5.5 회귀 비교용으로 보존)
    7: 'b8960e27e3ab2f2ec9d8e564515fb16dee68d908e16fa175ec1def61bf8ab671',
    37: '5fbea318e72f871ed2f1346b889f349f28d46d1a69ad745ac6641c6132e0538e',
    217: 'bb58b87d5eb01f20406d903e7cc057e2a68731c6585a7ca1ecaf9b8643c9a11c',
}

P055_EXPECTED = {   # 2026-10-12 p0.5.5: obs.action_schema compose-v0.4 → compose-v0.5 만(p0.5.6 회귀 비교용으로 보존)
    7: '77fcaf5d80d38e7893873184c59afd450e85474d9fb321f44cd5f2ddaa84e7ac',
    37: 'dbf56f21d5b3043268edb19b7cfafc86008370a4c2cf50e1c08ef897a8d22b05',
    217: 'bad308c563016eceebdfdc6941309468740080ea8cebe75a4ea5b9e11d9fe614',
}

P056_EXPECTED = {   # 2026-10-12 p0.5.6: 관측 대상의 아이템 줄에 desc·rule(물건 설명·다루는 규칙) · 보물 태그 (object) → (object, item)(p0.5.13 회귀 비교용으로 보존)
    7: 'ae60a3bdaff121f9af4a9e60791b3c15fa01ace21d706a6076c787a1daa0499f',
    37: '970fc137ca05d609ba220737ff87dbfb4ae3ab6bb34d0a4312ee4cdb9325b444',
    217: '559207f5ed5428d284428f4d9d4e5120b5233e850f51b5ec86d1fbd8de69832d',
}

P0513_EXPECTED = {   # 2026-10-15 p0.5.13(경제 1a): 몸에 골드(시작 지갑 5) — 관측 gold 칸 · 봇 스냅샷 gold 칸 · 소지품·대상 목록의 i7(골드)·i8(보물) 줄 · 보물 규칙에 amount 한 문장(p0.5.16 회귀 비교용으로 보존)
    7: 'aaac16d346a93dfa9bfc9ed8ba98f79174519c64a301bf4718d5cbf36a28c559',
    37: 'dd2dcaea4bf9ebccc006eab9362fedc4d13b3a8e0de6c26fba8836efe9ef699b',
    217: '383309f1fba78f5581cff307dff71ff445caf72e27d20a1f83ed581c60f12e30',
}

P0516_EXPECTED = {   # 2026-10-16 p0.5.16(욕구 틀 + 배고픔): 봇 스냅샷 needs 칸(배고픔 70)(p0.5.27 회귀 비교용으로 보존)
    7: '940df4944003b0e03d253693c292cab256b88b017f8bc9dc6cb221b33a2f76c7',
    37: '0d2557d0b3630327bab05bd60e14b794d4cfd6f52e48f3faf6161401377ed565',
    217: 'f6744ca2ecaa372c020fd5c8868a04c4f55e89aaead7fbd6c1977001f8be745e',
}

P0527_EXPECTED = {   # 2026-10-17 p0.5.27(시작 골드 5 → 10): 봇 스냅샷·관측의 gold · 소지품·대상 목록의 i7(골드) 개수(p0.5.29b 회귀 비교용으로 보존)
    7: '7d9fc7bf503fcd3cfe34d32e70a10c5aa825853ebddd6f5422e8c37928f85399',
    37: '652101d2d2551512fe49e126f70221eb36a5be1f4d29b54587dec0026274609f',
    217: '2bbfbf029b8919af73c3b89814c7ab977daf721b91617575f0b3b986fd97a84e',
}

EXPECTED = {   # 2026-10-18 p0.5.29b: obs.action_schema compose-v0.5 → compose-v0.6 만(동사 세트에 buy·sell)
    7: '3f9b6b06f48500d6cfe37990d8a9ded1542167d51fc5d28720402f3a79316b04',
    37: '64a780074f345aa798391c4955b31aba15fdec0f120412f500a408e07a8b59bb',
    217: 'b70c7c5267c1627768761a127d440958f7eed57606c28902842b8ca6fb968c77',
}

START_GOLD_P0516 = 5   # p0.5.27 전의 시작 골드(dungeon_gm.START_GOLD 가 10 이 되기 전)


def start_gold_v0525(value):
    """p0.5.27 시작 골드만 되돌린 사본 — gold 칸과 i7(골드) 줄의 개수를 (지금 시작 골드 − 옛 시작 골드)만큼 줄인다.
    이 판엔 골드가 오가는 길(가게·의뢰·건네기)이 없어 늘 시작 값이다. 그 밖의 바이트(행동·상태·난수)가 p0.5.16 기준선과 같은지 보는 데 쓴다."""
    shift = G.START_GOLD - START_GOLD_P0516
    if isinstance(value, dict):
        gold_line = (value.get('id'), value.get('slot')) == ('i7', 'gold')
        return {k: (v - shift if ((k == 'gold' or (gold_line and k == 'count')) and type(v) is int) else start_gold_v0525(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [start_gold_v0525(v) for v in value]
    return value

NEED_KEYS_P0516 = ('needs', 'moods', 'rations', 'need_lines')   # p0.5.16 이 몸·관측·봇 스냅샷에 더한 칸(이 판에 나오는 것은 needs 뿐)


def needs_v0515(value):
    """p0.5.16 욕구 칸만 되돌린 사본 — 그 밖의 바이트(행동·상태·난수)가 p0.5.13 기준선과 같은지 보는 데 쓴다."""
    if isinstance(value, dict):
        return {k: needs_v0515(v) for k, v in value.items() if k not in NEED_KEYS_P0516}
    if isinstance(value, (list, tuple)):
        return [needs_v0515(v) for v in value]
    return value

_TREASURE_NAMES = ('보물', '숨은 보물')


TREASURE_RULE_P056 = '주우면 모은 보물이 하나 는다.'   # p0.5.13 전 보물의 다루는 규칙(prompts/actions/item_rules.md `treasure`)


def gold_v0512(value):
    """p0.5.13 경제 1a 만 되돌린 사본 — 관측·봇 스냅샷의 gold 칸 · 소지품·대상 목록의 i7(골드)·i8(보물) 줄을 빼고, 보물의 다루는 규칙을 옛 한 문장으로.
    그 밖의 바이트(행동·상태·난수)가 p0.5.6 기준선과 같은지 보는 데 쓴다. 이 판(가게 없는 던전)엔 사고팔기·묵기 값·의뢰 보상 결과가 없어 되돌릴 것이 그뿐이다."""
    import entities as ENT
    if isinstance(value, dict):
        return {k: (TREASURE_RULE_P056 if (k == 'rule' and v == ENT.item_rule('treasure')) else gold_v0512(v))
                for k, v in value.items() if k != 'gold'}
    if isinstance(value, (list, tuple)):
        return [gold_v0512(v) for v in value
                if not (isinstance(v, dict) and (v.get('id'), v.get('slot')) in (('i7', 'gold'), ('i8', 'treasure')))]
    return value


def items_v055(value):
    """p0.5.6 관측 변경만 되돌린 사본 — 대상·소지품 줄의 desc·rule 칸을 빼고 보물 태그를 (object) 로. 그 밖의 바이트(행동·상태·난수)가
    p0.5.5 기준선과 같은지 보는 데 쓴다. 축복 물약의 옛 effect 칸은 이 판(축복 없음)에 나오지 않아 되돌릴 것이 없다."""
    if isinstance(value, dict):
        out = {k: items_v055(v) for k, v in value.items()
               if not (k in ('desc', 'rule') and value.get('kind') in ('feature', 'item') and 'tags' in value)}
        if out.get('kind') == 'feature' and out.get('name') in _TREASURE_NAMES and out.get('tags') == ['object', 'item']:
            out['tags'] = ['object']
        return out
    if isinstance(value, (list, tuple)):
        return [items_v055(v) for v in value]
    return value


def schema_v05(value):
    """p0.5.29b 관측 계약 문자열만 옛 값(compose-v0.5)으로 되돌린 사본 — 그 밖의 바이트가 p0.5.27 기준선과 같은지 보는 데 쓴다."""
    if isinstance(value, dict):
        return {k: ('compose-v0.5' if k == 'action_schema' and v == 'compose-v0.6' else schema_v05(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [schema_v05(v) for v in value]
    return value


def schema_v04(value):
    """p0.5.5 관측 계약 문자열만 옛 값으로 되돌린 사본 — 그 밖의 바이트가 t13c 기준선과 같은지 보는 데 쓴다."""
    if isinstance(value, dict):
        return {k: ('compose-v0.4' if k == 'action_schema' and v == 'compose-v0.5' else schema_v04(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [schema_v04(v) for v in value]
    return value


if __name__ == '__main__':
    for seed in (7, 37, 217):
        records = trace_records(seed)
        actual = digest(records)
        assert actual == EXPECTED[seed], (seed, actual, EXPECTED[seed])
        v05 = schema_v05(records)
        p0527 = digest(v05)
        assert p0527 == P0527_EXPECTED[seed], (seed, p0527, P0527_EXPECTED[seed])
        gold5 = start_gold_v0525(v05)
        p0516 = digest(gold5)
        assert p0516 == P0516_EXPECTED[seed], (seed, p0516, P0516_EXPECTED[seed])
        p0513 = digest(needs_v0515(gold5))
        assert p0513 == P0513_EXPECTED[seed], (seed, p0513, P0513_EXPECTED[seed])
        nogold = gold_v0512(needs_v0515(gold5))
        p056 = digest(nogold)
        assert p056 == P056_EXPECTED[seed], (seed, p056, P056_EXPECTED[seed])
        p055 = digest(items_v055(nogold))
        assert p055 == P055_EXPECTED[seed], (seed, p055, P055_EXPECTED[seed])
        old = digest(schema_v04(items_v055(nogold)))
        assert old == T13C_EXPECTED[seed], (seed, old, T13C_EXPECTED[seed])
        print('  OK seed=%d: 기준선과 관측·결과·난수 상태 일치 · 관측 계약 문자열 v0.6 만 되돌리면 p0.5.27 · 시작 골드까지 되돌리면 p0.5.16 · 욕구 칸까지 되돌리면 p0.5.13 · 골드 칸까지 되돌리면 p0.5.6 · 아이템 설명 칸까지 되돌리면 p0.5.5 · 관측 계약 문자열 v0.5 까지 되돌리면 t13c 기준선과 일치' % seed)
    print('ALL PASS — verify_skill_off (3시드 × 80틱, 기준선 = 78fbe84 + D51 + D66 + t13c + p0.5.5 + p0.5.6 + p0.5.13 + p0.5.16 + p0.5.27 + p0.5.29b 2026-10-18)')
