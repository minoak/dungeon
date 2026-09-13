"""현재 엔티티 정의와 layout을 미리보기·아스키 출력으로 내보낸다."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
import town_layout
layout = json.loads((HERE/'layout.json').read_text(encoding='utf-8'))
compiled = town_layout.compile_layout(layout)
(HERE/'compiled.json').write_text(json.dumps({**compiled,'visual':town_layout.visual_layer(layout,compiled)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'town-ascii.txt').write_text('\n'.join(compiled['map'])+'\n',encoding='utf-8')
print('마을 아스키·미리보기 데이터 갱신 완료')
