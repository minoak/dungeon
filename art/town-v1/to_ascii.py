"""layout의 명시 필드로 검토용 아스키를 출력한다. 아스키는 편집 원본이 아니다."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from town_layout import compile_layout


def main():
    source = HERE / 'layout.json'
    raw = source.read_bytes()
    layout = json.loads(raw.decode('utf-8'))
    result = compile_layout(layout)
    # NPC의 픽셀 위치도 칸 중심에서 파생한다.
    tile = layout['tileSize']
    visual_npcs = [{**n, 'x': (n['cell'][0]+0.5)*tile, 'y': (n['cell'][1]+0.5)*tile} for n in layout['npcs']]
    result.update({'_': 'layout.json에서 자동 생성한 검토용 결과. 직접 편집하지 말 것.',
                   'layout_source': 'layout.json', 'layout_sha256': hashlib.sha256(raw).hexdigest(),
                   'visual': {k: layout[k] for k in ('tileSize','ground','guild','props')}})
    result['visual'].update(npcs=visual_npcs, manifest='runtime/manifest.json', offset=[result['pad']]*2)
    (HERE/'town-candidate.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (HERE/'town-ascii.txt').write_text('\n'.join(result['map'])+'\n', encoding='utf-8')
    (HERE/'town-layout-ref.json').write_text(json.dumps({'layout': 'layout.json'}, indent=2)+'\n', encoding='utf-8')
    print('\n'.join(result['map']))
    print('격자 %s / 출발 %s / 던전 입구 %s' % (result['size'],result['starts'],result['dungeon_entry']))
    print('도달 가능한 내부 칸: %s / NPC id: %s' % (result['reachable_cells'], ', '.join(n['id'] for n in result['npcs'])))


if __name__ == '__main__':
    main()
