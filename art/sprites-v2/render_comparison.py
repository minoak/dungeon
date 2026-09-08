"""팔레트 행렬을 PNG로 출력한다. 원본 이미지의 축소·색 분류는 하지 않는다."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
root=Path(__file__).resolve().parent
data=json.loads((root/'warrior-pixels.json').read_text(encoding='utf-8'))
palette={k:tuple(bytes.fromhex(v[1:])) for k,v in data['palette'].items()}
sheet=Image.new('RGB',(800,620),'#20242c')
draw=ImageDraw.Draw(sheet)
draw.text((28,20),'WONDERLAND / EXACT PIXEL COMPARISON',fill='#f0dec2')
for col,s in enumerate(data['sprites']):
    n=s['size']
    assert len(s['rows'])==n and all(len(r)==n for r in s['rows'])
    im=Image.new('RGBA',(n,n))
    im.putdata([palette[c] if len(palette[c])==4 else (*palette[c],255) for r in s['rows'] for c in r])
    im.save(root/(s['name']+'.png'))
    check=Image.open(root/(s['name']+'.png'))
    assert check.size==(n,n) and set(check.getchannel('A').getdata())<={0,255}
    x=52+col*400
    draw.text((x,55),f'{n} x {n} / SAME DISPLAY SIZE',fill='#f0dec2')
    big=im.resize((288,288),Image.Resampling.NEAREST)
    sheet.paste(big,(x,85),big)
    for j,size in enumerate([32,48,64]):
        preview=im.resize((size,size),Image.Resampling.NEAREST)
        px=x+j*100
        sheet.paste(preview,(px,430),preview)
        draw.text((px,505),f'{size}px',fill='#b8c3cf')
    draw.text((x,554),'native: '+str(n)+'px',fill='#b8c3cf')
    sheet.paste(im,(x+110,548),im)
sheet.save(root/'warrior-comparison.png')
print('PASS: exact dimensions, binary alpha; exported both PNGs and comparison')
