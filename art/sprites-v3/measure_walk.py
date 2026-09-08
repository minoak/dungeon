"""원본은 수정하지 않고 네 캐릭터의 표시 영역만 측정한다."""
from pathlib import Path
from PIL import Image
import json
root=Path(__file__).resolve().parent
result={}
for direction in ['front','right','back','left']:
    im=Image.open(root/f'warrior-{direction}-walk-generated.png').convert('RGB')
    w,h=im.size
    boxes=[];anchors=[]
    for i in range(4):
        start,end=round(w*i/4),round(w*(i+1)/4)
        points=[(x,y) for y in range(h) for x in range(start,end) if not (im.getpixel((x,y))[0]>150 and im.getpixel((x,y))[2]>120 and im.getpixel((x,y))[1]<115)]
        x0=min(x for x,y in points);x1=max(x for x,y in points)+1
        y0=min(y for x,y in points);y1=max(y for x,y in points)+1
        head=[x for x,y in points if y<y0+(y1-y0)*.45]
        anchors.append((min(head)+max(head)+1)/2)
        boxes.append([x0,y0,x1,y1])
    top=min(b[1] for b in boxes)-18;bottom=max(b[3] for b in boxes)+18
    half=max(max(a-b[0],b[2]-a) for a,b in zip(anchors,boxes))+18
    crops=[[round(a-half),top,round(half*2),bottom-top] for a in anchors]
    assert all(x>=0 and y>=0 and x+cw<=w and y+ch<=h for x,y,cw,ch in crops)
    result[direction]={'file':f'warrior-{direction}-walk-generated.png','crops':crops,'bounds':boxes}
print(json.dumps(result))
