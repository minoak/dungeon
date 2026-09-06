"""Animate the native indexed parts; all coordinates are logical pixels.

Four-step loop: contact A, passing, contact B, passing. The passing pose
reuses the idle body with the head lowered by one pixel. No raster resampling
or new facial pixels are involved.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from build_assets import rgba, save_part, compose, DIRS, IDS

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'


def contact(body, bid, direction, phase):
    source = np.asarray(body,dtype=np.uint8)
    out = source.copy()
    if direction in ['front','back']:
        # Keep waist and skirt hem intact; alternating lifted feet provide
        # the step, with the opposite hand moving down by one pixel.
        lifted_left = phase == 0
        if direction == 'back': lifted_left = not lifted_left
        for left in [True,False]:
            xa,xb = (3,7) if left else (8,12)
            leg=source[13:16,xa:xb].copy()
            out[13:16,xa:xb]=0
            y=12 if left == lifted_left else 13
            # On skirt bodies, leave the hem and raise only the boot.
            if bid=='B2' and left == lifted_left:
                leg=source[14:16,xa:xb].copy(); y=13
            out[y:y+len(leg),xa:xb]=leg
            axa,axb=(2,4) if left else (11,13)
            arm=source[10:12,axa:axb].copy()
            out[10:13,axa:axb]=0
            ay=11 if left != lifted_left else 10
            out[ay:ay+2,axa:axb]=arm
    else:
        # At this size both legs overlap in the idle profile. Separate them
        # around the hip for contact, keeping the far leg darker and shorter.
        out[13:16,:]=0
        sign=1 if direction=='right' else -1
        near_dx=sign*(1 if phase==0 else -1)
        far_dx=-near_dx
        for near,dx in [(False,far_dx),(True,near_dx)]:
            x=7+dx
            fabric=(14 if near else 12) if bid=='B1' else (4 if near else 3)
            out[13,x:x+2]=fabric
            out[14,x:x+2]=16 if near else 15
            if near: out[15,x:x+2]=16
        # Near arm swings opposite the near foot. All colors remain material
        # indices so hair/skin/clothing recoloring works for every frame.
        hand_x=7-near_dx
        out[10:12,7:9]=source[10:12,7:9]
        out[10,hand_x:hand_x+2]=10
        out[11,hand_x:hand_x+2]=4
    return out


def shifted(head,dy):
    result={}
    for layer in ['rear','front']:
        ar=np.asarray(head[layer],dtype=np.uint8)
        out=np.zeros((16,16),dtype=np.uint8)
        if dy: out[dy:]=ar[:-dy]
        else: out[:]=ar
        result[layer]=out.tolist()
    return result


def main():
    data=json.loads((ASSETS/'sprites.json').read_text())
    data['revision']='idle-walk-1'
    data['animations']={'walk':{'frame_ms':140,'loop':True,
        'body_sequence':['step_a','idle','step_b','idle'],
        'head_offset_y':[0,1,0,1],
        'sheet':{'columns':'cycle frames 0..3','rows':DIRS,'size':[64,64]}}}
    for bid,b in data['bodies'].items():
        b['walk']={}
        for direction in DIRS:
            poses=[contact(b['frames'][direction],bid,direction,0),
                   np.asarray(b['frames'][direction]),
                   contact(b['frames'][direction],bid,direction,1),
                   np.asarray(b['frames'][direction])]
            b['walk'][direction]=[p.tolist() for p in poses]
            for i,p in enumerate(poses):
                save_part(p,ASSETS/'walk/bodies'/bid/f'{direction}_{i}.png')
    for hid,h in data['heads'].items():
        for bid,b in data['bodies'].items():
            sheet=Image.new('RGBA',(64,64))
            for di,d in enumerate(DIRS):
                for i,dy in enumerate([0,1,0,1]):
                    frame=compose(shifted(h['frames'][d],dy),b['walk'][d][i],d)
                    save_part(frame,ASSETS/'walk/composed'/f'{hid}_{bid}'/f'{d}_{i}.png')
                    sheet.paste(rgba(frame),(i*16,di*16))
            sheet.save(ASSETS/'walk/composed'/f'{hid}_{bid}'/'sheet.png')
    (ASSETS/'sprites.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    # Small animated review sheet: two body types and all four directions.
    frames=[]
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
    for i,dy in enumerate([0,1,0,1]):
        canvas=Image.new('RGB',(640,380),'#20242c'); draw=ImageDraw.Draw(canvas)
        draw.text((18,14),'WALK / 4 DIRECTIONS / 16 x 16',font=font,fill='#f0dec2')
        for row,(hid,bid) in enumerate([('M1','B1'),('F3','B2')]):
            for col,d in enumerate(DIRS):
                ar=compose(shifted(data['heads'][hid]['frames'][d],dy),data['bodies'][bid]['walk'][d][i],d)
                im=rgba(ar).resize((112,112),Image.Resampling.NEAREST)
                x=24+col*156;y=52+row*160
                canvas.paste(im,(x,y),im)
                draw.text((x,y+118),hid+' '+bid+' '+d,font=font,fill='#a6b1bf')
        frames.append(canvas)
    frames[0].save(ROOT/'walk-preview.gif',save_all=True,append_images=frames[1:],duration=140,loop=0,disposal=2)
    print('Built walk: 384 composite frames, 24 sheets, 32 body frames')


if __name__=='__main__': main()
