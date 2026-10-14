"""t13 표시 필드 계약 검증. LLM 호출·파일 쓰기·전역 직렬화 패치 없음."""

import dungeon_gm as G
import skill_schema as S
import skill_core as SK
import composed_actions as CA
import verify_skill_off as baseline

FIELDS = {'attack_mode', 'source_xy', 'target_xy'}


def strip(value):
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in FIELDS}
    if isinstance(value, (tuple, list)):
        return [strip(v) for v in value]
    return value


def arena():
    d, starts = G.Dungeon.from_ascii(
        ['############', '#12.a.....>#', '#..........#', '############'],
        monsters={'a': {'hp': 60, 'state': 'HUNTING', 'ac': 8}})
    bots = []
    for c, at in starts.items():
        b = G.spawn(d, c, bots)
        b['x'], b['y'] = at
        b['skills'] = list(S.PRESETS)
        bots.append(b)
    d.skills = d.composed_actions = True
    d.d20 = lambda: 18
    return d, bots, d.monsters[0]


def main():
    d, bots, m = arena()
    b = bots[0]
    b['x'], b['atk_range'] = m.x - 1, 2
    e = d._attack(b, 'm%d' % m.id, bots)
    assert e['attack_mode'] == 'ranged'  # 붙어서 쏘는 궁수도 원거리
    assert e['source_xy'] == [b['x'], b['y']] and e['target_xy'] == [m.x, m.y]
    b['atk_range'] = 1
    assert d._attack(b, 'm%d' % m.id, bots)['attack_mode'] == 'melee'
    assert not FIELDS.intersection(d._attack(b, 'm999', bots))
    e = CA.attack_actor(d, b, bots[1], bots)
    assert e['attack_mode'] == 'melee' and e['target_xy'] == [bots[1]['x'], bots[1]['y']]
    e = d._monster_attack(m, b, bots)
    assert e['attack_mode'] == 'melee' and e['source_xy'] == [m.x, m.y]
    before = [m.x, m.y]
    d.view(b, bots)
    e = SK.execute(d, b, {'type': 'push_slash', 'target': 'm%d' % m.id}, bots)
    assert e['target_xy'] == before and e['attack_mode'] == 'melee'
    assert any(x['type'] == 'push' and x['applied'] for x in e['effects'])
    assert e['target_xy'] != [m.x, m.y]  # 밀침 이전 좌표를 보존
    ranged = S.make('ranged_probe', '검증용 원거리', [{'type': 'damage', 'dice': '1d6'}], range_=3)
    b['skills'].append(ranged['id'])
    b.setdefault('generated_skills', {})[ranged['id']] = ranged
    d.view(b, bots)
    d.d20 = lambda: 1
    e = SK.execute(d, b, {'type': ranged['id'], 'target': 'm%d' % m.id}, bots)
    assert e['attack_mode'] == 'ranged' and not e['hit'] and e['target_xy'] == [m.x, m.y]
    b['hp'] -= 2
    d.view(b, bots)
    e = SK.execute(d, b, {'type': 'first_aid', 'target': 'b' + b['char']}, bots)
    assert 'attack_mode' not in e and e['target_xy'] == [b['x'], b['y']]
    print('  OK 공격·실패·인접 원거리·사람/몹 대상·밀침 전 좌표·스킬 빗나감·회복')

    for seed, expected in baseline.PRE_FX_EXPECTED.items():
        records = baseline.trace_records(seed)
        actual = baseline.digest(records)
        stripped = baseline.digest(strip(baseline.schema_v04(baseline.items_v055(baseline.gold_v0512(records)))))   # p0.5.5: 관측 계약 문자열(v0.5) · p0.5.6: 아이템 설명 칸 · p0.5.13: 골드·보물 소지 줄도 D66 시절 꼴로 되돌려 비교
        assert actual == baseline.EXPECTED[seed], (seed, actual, baseline.EXPECTED[seed])
        assert stripped == expected, (seed, stripped, expected)
        print('  OK 시드=%s: 새 기준선 일치, 표시 필드 제외 시 기존 관측·상태·난수 일치' % seed)
    print('ALL PASS — verify_combat_stream (표시 필드 계약·3시드 전후 비교)')


if __name__ == '__main__':
    main()
