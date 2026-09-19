"""Compile the active v3 layout and make a self-contained map review page."""
import base64
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import town_layout

layout = json.loads((HERE/'layout.json').read_text(encoding='utf-8'))
compiled = town_layout.compile_layout(layout)
visual = town_layout.visual_layer(layout, compiled)
objects = json.loads((HERE/'design-objects.json').read_text(encoding='utf-8'))
report = json.loads((HERE/'validation.json').read_text(encoding='utf-8'))
assets = {}
for key, filename in [('terrain','town-terrain.png'),('props','town-props.png')] + [
        (b['texture'],'town-'+b['texture']+'.png') for b in visual['buildings']]:
    assets[key] = 'data:image/png;base64,' + base64.b64encode((ROOT/'game/src/assets/world'/filename).read_bytes()).decode()
data = dict(layout=layout, compiled=compiled, visual=visual, objects=objects['objects'],
            exterior=objects['reserved_exits'][0], report=report, assets=assets)
template = (HERE/'preview.template.html').read_text(encoding='utf-8')
(HERE/'preview.html').write_text(template.replace('__DRAFT_DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')
(HERE/'compiled.json').write_text(json.dumps(dict(**compiled,visual=visual),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'town-ascii.txt').write_text('\n'.join(compiled['map'])+'\n',encoding='utf-8')
print('Exported town v3 from production entities and layout.')
