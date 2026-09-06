from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
data=(ROOT/'assets/sprites.json').read_text(encoding='utf-8')
template=(ROOT/'tools/preview.template.html').read_text(encoding='utf-8')
(ROOT/'preview.html').write_text(template.replace('__SPRITE_DATA__',data),encoding='utf-8')
print('Wrote standalone preview.html')
