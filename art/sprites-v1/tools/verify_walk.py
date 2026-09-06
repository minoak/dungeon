"""Check exported walk PNGs against independently composited PNG layers."""
from pathlib import Path
import json
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'
data=json.loads((ASSETS/'sprites.json').read_text())
assert data['heads']['M1']['frames']['front']['front'][5][6]==5
count=0
for hid,h in data['heads'].items():
    for bid,b in data['bodies'].items():
        folder=ASSETS/'walk/composed'/f'{hid}_{bid}'
        sheet=Image.open(folder/'sheet.png').convert('RGBA')
        assert sheet.size==(64,64)
        for di,d in enumerate(data['directions']):
            poses=b['walk'][d]
            assert poses[0]!=poses[2], (bid,d,'steps must alternate')
            assert poses[1]==poses[3]==b['frames'][d]
            for i,dy in enumerate(data['animations']['walk']['head_offset_y']):
                result=Image.new('RGBA',(16,16))
                for layer in ['rear','body','front']:
                    if layer=='body':
                        part=Image.open(ASSETS/'walk/bodies'/bid/f'{d}_{i}.png').convert('RGBA');offset=(0,0)
                    else:
                        part=Image.open(ASSETS/'heads'/hid/f'{d}_{layer}.png').convert('RGBA');offset=(0,dy)
                    result.alpha_composite(part,offset)
                actual=Image.open(folder/f'{d}_{i}.png').convert('RGBA')
                assert actual.size==(16,16)
                assert np.isin(np.asarray(actual)[...,3],[0,255]).all()
                assert actual.tobytes()==result.tobytes(), (hid,bid,d,i,'layers disagree')
                assert sheet.crop((i*16,di*16,i*16+16,di*16+16)).tobytes()==actual.tobytes()
                count+=1
print(f'OK: {count} walk frames, 24 sheets, alternating legs, M1 face correction')
