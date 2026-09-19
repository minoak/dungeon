"""Self-contained map data in a portable comparison page (images stay external)."""
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
from town_layout import compile_layout
layout=json.loads((HERE/'layout.json').read_text(encoding='utf-8'))
compiled=compile_layout(layout)
page=(HERE/'compare.template.html').read_text(encoding='utf-8')
page=page.replace('__LAYOUT__',json.dumps(layout,ensure_ascii=False)).replace('__COMPILED__',json.dumps(compiled,ensure_ascii=False))
(HERE/'compare.html').write_text(page,encoding='utf-8')
print('compare.html exported')
