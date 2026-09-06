"""Normalize approved/generated artwork into exact 16x16 modular sprite assets.

This is production raster conversion: chroma key, component extraction,
anchor alignment, palette quantization and layer separation. Artwork comes
from sources/*.png. No API calls are made. Requires Pillow, NumPy, SciPy.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import label, find_objects

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
DIRS = ['front', 'left', 'back', 'right']
IDS = [f'M{i}' for i in range(1, 5)] + [f'F{i}' for i in range(1, 9)]
NAMES = ['짧은 머리', '가르마', '올백', '헝클어진 머리', '숏컷', '앞머리 단발',
         '웨이브 롱헤어', '긴 생머리', '풍성한 웨이브', '포니테일', '트윈테일', '올림머리']
# Each material uses shadow / base / light; 0 is transparent.
PAL = ['#000000', '#241b19', '#100f10',
       '#ba805c', '#eabb8c', '#ffe0ad',
       '#623c29', '#945c37', '#bb7b49',
       '#294757', '#42738b', '#73a2ad',
       '#ac9970', '#d7c599', '#f4e4b7',
       '#4e3528', '#765035', '#a4784e']
RGB = np.array([tuple(bytes.fromhex(x[1:])) for x in PAL], dtype=np.uint8)

def foreground(a):
    r, g, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    return ~((r > 160) & (b > 130) & (g < 100) & (r-g > 90) & (b-g > 70))

def components(path):
    a = np.array(Image.open(path).convert('RGB'))
    lab, _ = label(foreground(a))
    items = []
    for i, s in enumerate(find_objects(lab)):
        if s and np.sum(lab[s] == i+1) > 300:
            items.append((s[1].start, s[0].start, s[1].stop, s[0].stop))
    return a, items

def classify(a, body=False):
    """Assign material + tone, retaining semantic masks for recoloring."""
    a = a.astype(float)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = r*.299 + g*.587 + b*.114
    ids = np.zeros(r.shape, dtype=np.uint8)
    fg = foreground(a)
    dark = fg & (np.max(a, axis=-1) < 65)
    skin = fg & ~dark & (r > 164) & (g > 108) & (r > g*1.05) & (g > b*1.08)
    if not body:
        # Hair highlights in this source also satisfy the broad brown/skin
        # threshold. Use the pale face hue, otherwise pale hair pixels change
        # both the face anchor and the apparent facial silhouette.
        skin = fg & ~dark & (r > 185) & (g > 150) & (b > 105) & (r > g) & (g > b)
    # Hair is brown, skin is substantially lighter in source art.
    hair = fg & ~dark & ~skin
    for lo, masks, values in [(3, skin, [151, 206]), (6, hair, [89, 133])]:
        ids[masks] = lo + np.digitize(lum[masks], values)
    if body:
        h = len(ids)
        yy = np.indices(ids.shape)[0] / max(1, h-1)
        top = fg & ~dark & ((b > r*1.05) | (g > r*1.04))
        pants = fg & ~dark & (yy > .39) & (yy < .84) & (r > 135) & (g > 112)
        boots = fg & ~dark & ~skin & ~top & ~pants
        ids[boots] = 15 + np.digitize(lum[boots], [75, 110])
        ids[top] = 9 + np.digitize(lum[top], [80, 125])
        ids[pants] = 12 + np.digitize(lum[pants], [162, 205])
        # bare lower legs on B2 are skin, rather than fabric
        leg_skin = skin & (yy > .68) & (yy < .84) & (r-g > 26)
        ids[leg_skin] = 3 + np.digitize(lum[leg_skin], [151, 206])
    ids[dark] = 1
    if not body:
        blobs,_=label(dark)
        for i,s in enumerate(find_objects(blobs)):
            if not s: continue
            yy,xx=s
            area=int(np.sum(blobs[s]==i+1))
            # Eye marks are small isolated dark components inside the face;
            # the outline is the large connected boundary.
            cy,cx=(yy.start+yy.stop)/2,(xx.start+xx.stop)/2
            eye_w, eye_h = xx.stop-xx.start, yy.stop-yy.start
            eye_shape = (.25 <= eye_w/eye_h <= .85 and
                         eye_w < .14*ids.shape[1] and eye_h < .24*ids.shape[0])
            if eye_shape and ids.size*.003<area<ids.size*.035 and .18*ids.shape[1]<cx<.82*ids.shape[1] and .28*ids.shape[0]<cy<.85*ids.shape[0]:
                around=skin[max(0,yy.start-3):min(len(ids),yy.stop+3),max(0,xx.start-3):min(ids.shape[1],xx.stop+3)]
                if around.any(): ids[blobs==i+1]=2
    return ids

def sample(ids, scale, offset):
    """Area-vote material IDs into 16x16; avoids blended chroma-key fringes."""
    h, w = ids.shape
    result = np.zeros((16, 16), dtype=np.uint8)
    ox, oy = offset
    for y in range(16):
        for x in range(16):
            x0, x1 = int(np.floor((x-ox)/scale)), int(np.ceil((x+1-ox)/scale))
            y0, y1 = int(np.floor((y-oy)/scale)), int(np.ceil((y+1-oy)/scale))
            xa, xb, ya, yb = max(0,x0), min(w,x1), max(0,y0), min(h,y1)
            if xa >= xb or ya >= yb:
                continue
            vals = ids[ya:yb, xa:xb].ravel()
            total = max(1,(x1-x0)*(y1-y0))
            opaque = vals[vals>0]
            if len(opaque)/total < .36:
                continue
            # First vote on material, then shade, so three shades don't lose
            # against a single outline index at a diagonal boundary.
            counts = np.bincount(opaque, minlength=len(PAL))
            groups = [counts[1:3].sum()] + [counts[k:k+3].sum() for k in range(3,18,3)]
            if counts[1] / len(opaque) >= .39:
                result[y,x] = 1
            else:
                group = int(np.argmax(groups))
                base = 1 if group == 0 else 3*group
                n = 2 if group == 0 else 3
                result[y,x] = base + int(np.argmax(counts[base:base+n]))
    return result

def nearest(ids, sx, sy, offset):
    h,w=ids.shape
    out=np.zeros((16,16),dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            xx=int(np.floor((x+.5-offset[0])/sx))
            yy=int(np.floor((y+.5-offset[1])/sy))
            if 0<=xx<w and 0<=yy<h: out[y,x]=ids[yy,xx]
    return out

def normalize(a, box, ident, direction):
    x0,y0,x1,y1 = box
    patch = a[y0:y1,x0:x1]
    ids = classify(patch, ident.startswith('B'))
    h,w = ids.shape
    if ident.startswith('B'):
        width=11 if direction in ['front','back'] else 6
        return nearest(ids,width/w,8/h,((16-width)//2,8))
    # Profiles show one eye on the face-facing edge. Narrow hair seams and
    # ear outlines can resemble eyes, but sit behind the actual eye.
    if direction in ['left', 'right', 'back']:
        eye_labels, _ = label(ids==2)
        candidates = [(i+1, (s[1].start+s[1].stop)/2)
                      for i,s in enumerate(find_objects(eye_labels)) if s]
        ids[ids==2] = 1
        if direction != 'back' and candidates:
            selected = (min if direction=='left' else max)(candidates,key=lambda item:item[1])[0]
            ids[eye_labels==selected] = 2
    # Source face bottom = chin, align it to y=9 on every hair.
    skin = (ids>=3)&(ids<=5)
    ys,xs = np.where(skin)
    if len(ys) and direction != 'back':
        chin = np.percentile(ys,99)+1
        crown = 0
        # Buns and spiky styles may extend one pixel above common skull.
        target_chin = 9
        scale = target_chin/chin
        face_x = (np.percentile(xs,2)+np.percentile(xs,98))/2
        center = face_x if direction == 'front' else w/2
    else:
        # Back hair retains long-hair length; use front scale determined below.
        scale = 9/h
        center = w/2
    return ids, scale, center

def rgba(ids):
    ar = np.zeros((*ids.shape,4), dtype=np.uint8)
    ar[...,:3] = RGB[ids]
    ar[...,3] = (ids>0)*255
    ar[ids==0,:3] = 0
    return Image.fromarray(ar)

def save_part(ids, path):
    path.parent.mkdir(parents=True,exist_ok=True)
    rgba(ids).save(path)

def compose(hair, body, direction):
    b = np.array(body, dtype=np.uint8)
    rear = np.array(hair['rear'],dtype=np.uint8)
    front = np.array(hair['front'],dtype=np.uint8)
    out = rear.copy()
    out[b>0] = b[b>0]
    out[front>0] = front[front>0]
    return out

def main():
    a, boxes = components(ROOT/'sources/directional-atlas.png')
    # Generated source has 13 rows: F4 is supplied in a separate strip.
    rowids = [i for i in IDS if i!='F4'] + ['B1','B2']
    boxes = sorted(boxes, key=lambda b:(b[0]+b[2])/2)
    cols = [sorted(boxes[i*13:(i+1)*13],key=lambda b:b[1]) for i in range(4)]
    assert all(len(c)==13 for c in cols), 'Atlas component count changed'
    sources = {ident:{d:(a,cols[j][i]) for j,d in enumerate(DIRS)} for i,ident in enumerate(rowids)}
    f4, b4 = components(ROOT/'sources/f4-directions.png')
    assert len(b4)==4
    sources['F4'] = {d:(f4,b) for d,b in zip(DIRS,sorted(b4))}
    data = {'version':1,'frame':[16,16],'directions':DIRS,
            'anchors':{'center_x':8,'neck_y':9,'feet_y':16},
            'palette':PAL,'materials':{'skin':[3,4,5],'hair':[6,7,8],
              'top':[9,10,11],'bottom':[12,13,14],'leather':[15,16,17]},
            'heads':{},'bodies':{},'layer_order':['rear','body','front']}
    for ident in ['B1','B2']:
        entry = {'name':'바지형' if ident=='B1' else '치마형','frames':{}}
        for d in DIRS:
            src, box = sources[ident][d]
            body = normalize(src,box,ident,d)
            entry['frames'][d] = body.tolist()
            save_part(body,OUT/'bodies'/ident/(d+'.png'))
        data['bodies'][ident] = entry
    for ident,name in zip(IDS,NAMES):
        entry = {'name':name,'group':'male' if ident[0]=='M' else 'female','frames':{}}
        norm = {d:normalize(*sources[ident][d],ident,d) for d in DIRS}
        # Back shares the source-scale ratio of neighboring profiles, normalized
        # by each source's width: atlas heads have consistent crown proportions.
        for d in DIRS:
            ids,scale,center = norm[d]
            if d=='back':
                ids[ids==2] = 1
                if ident in ['F3','F4','F5']:
                    scale = np.mean([norm[x][1] for x in ['left','right']])
                elif ident in ['F6','F7']:
                    scale = 9/ids.shape[0]
            # Keep large hairstyles within the canvas rather than clipping tips.
            sy=min(scale,13/ids.shape[0])
            sx=min(scale,15/ids.shape[1])
            ox=8-center*sx
            head = nearest(ids,sx,sy,(ox,0))
            # Preserve isolated eyes as exactly one logical pixel each instead
            # of allowing resampling to erase or double-height them.
            eyes, eye_count=label(ids==2)
            expected_eyes = 0 if d=='back' else 2 if d=='front' else 1
            assert eye_count == expected_eyes, (ident, d, 'source eye count', eye_count)
            head[head==2]=5
            for i,s in enumerate(find_objects(eyes)):
                if not s: continue
                yy,xx=s
                x=int((xx.start+xx.stop)*.5*sx+ox)
                y=int((yy.start+yy.stop)*.5*sy)
                if d!='back' and 0<=x<16 and 0<=y<16: head[y,x]=2
            # Approved local retouch: isolated hair-shadow pixel above M1's
            # screen-left eye belongs to the face, not to the fringe.
            if ident == 'M1' and d == 'front':
                head[5,6] = 5
            rear = np.zeros((16,16),dtype=np.uint8)
            front = head.copy()
            if d!='back':
                # Rear tails below neck; preserve side locks outside shirt center.
                for y in range(9,16):
                    for x in range(16):
                        if head[y,x] and 5<=x<=10:
                            rear[y,x]=head[y,x]; front[y,x]=0
            entry['frames'][d] = {'rear':rear.tolist(),'front':front.tolist()}
            save_part(rear,OUT/'heads'/ident/(d+'_rear.png'))
            save_part(front,OUT/'heads'/ident/(d+'_front.png'))
        data['heads'][ident] = entry
    OUT.mkdir(exist_ok=True)
    (OUT/'sprites.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    atlas = Image.new('RGBA',(64,16*24))
    for i,ident in enumerate(IDS):
        for bi,bid in enumerate(['B1','B2']):
            for di,d in enumerate(DIRS):
                frame = compose(data['heads'][ident]['frames'][d],data['bodies'][bid]['frames'][d],d)
                save_part(frame,OUT/'composed'/f'{ident}_{bid}'/(d+'.png'))
                atlas.paste(rgba(frame),(di*16,(i*2+bi)*16))
    atlas.save(OUT/'characters-atlas.png')
    # Human readable QA contact sheet, both body types shown for each haircut.
    sheet = Image.new('RGB',(960,12*116+68),'#20242c')
    draw = ImageDraw.Draw(sheet)
    fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    try: font=ImageFont.truetype(fontpath,15)
    except OSError: font=ImageFont.load_default()
    draw.text((20,18),'WONDERLAND / 16 x 16 / IDLE PARTS v1',fill='#f0dec2',font=font)
    for i,ident in enumerate(IDS):
        y=68+i*116
        draw.text((12,y+40),ident,fill='#f0dec2',font=font)
        for bi,bid in enumerate(['B1','B2']):
            for di,d in enumerate(DIRS):
                x=75+bi*440+di*105
                fr=compose(data['heads'][ident]['frames'][d],data['bodies'][bid]['frames'][d],d)
                sheet.paste(rgba(fr).resize((80,80),Image.Resampling.NEAREST),(x,y),rgba(fr).resize((80,80),Image.Resampling.NEAREST))
                draw.text((x,y+84),bid+' '+d,fill='#a6b1bf',font=font)
    sheet.save(ROOT/'contact-sheet.png')
    print('Built',len(IDS),'heads x 4 directions, 2 bodies x 4 directions, 96 composites')

if __name__=='__main__':
    main()
