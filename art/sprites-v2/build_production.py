"""사용자 승인 픽셀 행렬을 기준으로 직업·머리·방향을 구성한다.
이미지 리샘플링 없이 논리 픽셀을 직접 배치한다. 기존 런타임은 변경하지 않는다.
"""
from pathlib import Path
import json, hashlib
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'approved-warrior-front.json'
approved=json.loads(SOURCE.read_text(encoding='utf-8'))
PAL=dict(approved['palette'])
PAL.update({'P':'#597b45','p':'#36513a','R':'#786077','r':'#483b50'})
DIRS=['front','left','back','right']
NAMES={'M1':'짧은 머리','M2':'가르마','M3':'올백','M4':'헝클어진 머리','F1':'숏컷','F2':'앞머리 단발','F3':'웨이브 롱헤어','F4':'긴 생머리','F5':'풍성한 웨이브','F6':'포니테일','F7':'트윈테일','F8':'올림머리'}
def blank(): return [['.']*16 for _ in range(16)]
def copy(a): return [r[:] for r in a]
def line(a,y,x,text):
    assert 0<=y<16 and 0<=x and x+len(text)<=16
    a[y][x:x+len(text)]=list(text)
def flip(a): return [r[::-1] for r in a]
def strings(a): return [''.join(r) for r in a]
def layer(*parts):
    a=blank()
    for part in parts:
        for y,row in enumerate(part):
            for x,v in enumerate(row):
                if v!='.': a[y][x]=v
    return a
base=[list(r) for r in approved['rows']]
assert approved['size']==16 and all(len(r)==16 for r in base)
front=copy(base)
for y in range(11,16): front[y]=['.']*16
profile=blank()
for y,x,s in [(0,6,'#####'),(1,4,'##hhhH##'),(2,4,'#hhHHhhh#'),(3,3,'#hHHhhhhh#'),(4,3,'#hhhhHhhh#'),(5,3,'#sshhhhhh#'),(6,3,'#ssshhhhh#'),(7,3,'#sEsshhhh#'),(8,2,'#ssEsshhh#'),(9,3,'#sssshhh#'),(10,4,'#######')]: line(profile,y,x,s)
# 옆모습 눈은 같은 x=5의 세로 두 칸이다.
profile[7][5]='E';profile[8][5]='E';profile[8][4]='s'
back=blank()
for y in range(11):
    for x,v in enumerate(front[y]):
        back[y][x]=v if v in '.#hH' else 'h'
for y,x,s in [(4,5,'HhhH'),(6,4,'hhHhhh'),(8,5,'Hhhhh'),(9,5,'hhh')]: line(back,y,x,s)
def hair_style(ident,direction,head):
    a=copy(head);rear=blank()
    # 얼굴 아래쪽은 공통으로 두고 가르마와 윤곽을 차이로 관리한다.
    if ident in ['M2','F1']:
        for y,x,s in [(2,5,'HhhhH'),(3,4,'HhhhH'),(4,4,'hhhH'),(5,4,'hsss')]: line(a,y,x,s)
    if ident=='M3':
        for y,x,s in [(1,5,'hHhHh'),(2,4,'hHhHhHh'),(3,4,'hHhHhHh'),(4,4,'hhhhhhh'),(5,4,'sssssss')]:line(a,y,x,s)
    if ident=='M4':
        for y,x,s in [(0,4,'#h#h###'),(1,3,'#hHhHhhh#'),(3,2,'#hHhhHhhhh#'),(5,3,'hshshshhh')]:line(a,y,x,s)
    if ident=='F1':
        for y in range(3,6):
            a[y][1]='.';a[y][13]='.'
    if ident=='F2':
        for y,x,s in [(4,3,'hhhhhhhhh'),(5,3,'hHhHhHhhh'),(6,3,'hsssssssh')]:line(a,y,x,s)
    if ident in ['F3','F4','F5']:
        for y in range(7,15):
            left=1 if ident=='F5' else 2
            if ident in ['F3','F5']:left+=y%2
            line(rear,y,left,'#Hh');line(rear,y,11,'hH#')
        if ident=='F4':
            for y,x,s in [(3,6,'H#H'),(4,6,'hsh'),(5,5,'hsssh')]:line(a,y,x,s)
        if ident=='F5':
            for y in range(3,7):line(rear,y,0,'#hh');line(rear,y,12,'hh#')
    if ident=='F6':
        for y in range(3,13):line(rear,y,12 if y<8 else 11,'#Hh#')
    if ident=='F7':
        for y in range(4,12):
            line(rear,y,0 if y<9 else 1,'#Hh')
            line(rear,y,13 if y<9 else 12,'hH#')
    if ident=='F8':
        for y,x,s in [(0,6,'#Hh#'),(1,5,'#Hhhh#'),(2,6,'hhhh')]:line(a,y,x,s)
    # 측면 전용 얼굴을 쓰고 헤어 차이는 뒤통수 쪽에 배치한다.
    if direction=='left':
        a=copy(profile);rear=blank()
        if ident in ['M2','F1']:line(a,3,4,'#HhhhHhh#')
        if ident=='M3':line(a,2,5,'HhHhHh');line(a,4,4,'hHhhhh')
        if ident=='M4':line(a,0,5,'#h#h###');line(a,2,3,'#hHhHhhhh#')
        if ident=='F2':
            for y in range(7,11):line(a,y,9,'hh#')
        if ident in ['F3','F4','F5']:
            for y in range(7,15):line(rear,y,9+(y%2 if ident!='F4' else 0),'hH#')
        if ident=='F5':
            for y in range(3,9):line(rear,y,11,'hH#')
        if ident=='F6':
            for y in range(4,13):line(rear,y,12 if y<8 else 11,'hH#')
        if ident=='F7':
            for y in range(5,12):line(rear,y,10,'hH#')
        if ident=='F8':line(a,0,8,'#Hh#');line(a,1,8,'hhhh#')
    if direction=='back':
        # 뒷머리에 눈이나 피부가 섞이지 않도록 정리한다.
        for y in range(11):
            for x,v in enumerate(a[y]):
                if v in 'sE':a[y][x]='h'
        if ident in ['F3','F4','F5']:
            for y in range(10,14):
                line(a,y,3 if ident!='F5' else 2,'#hhhhHhh#')
        if ident=='F6':
            for y in range(6,15):line(a,y,7,'#Hh#')
        if ident=='F7':
            for y in range(5,13):line(rear,y,1,'#Hh');line(rear,y,12,'hH#')
    return rear,a
heads={}
for ident in NAMES:
    frames={}
    for d,h in [('front',front),('left',profile),('back',back)]:
        rear,a=hair_style(ident,d,h)
        # 정면 눈과 피부 위치는 승인본으로 고정한다.
        if d=='front':
            for y in [7,8]:
                for x in range(4,12):
                    a[y][x]=front[y][x]
        frames[d]={'rear':rear,'front':a}
    frames['right']={k:flip(v) for k,v in frames['left'].items()}
    heads[ident]={'name':NAMES[ident],'frames':frames}
def body_rows(lines):
    a=blank()
    for y,s in enumerate(lines,11):assert len(s)==16;(a.__setitem__(y,list(s)))
    return a
warrior=copy(base)
for y in range(11):warrior[y]=['.']*16
rogue=body_rows(['...#RrRRRrR#....','..Gs#RrrrR#s#...','..WG#llgll###...','..W#.#rr#rr#....','.....#ll#ll#....'])
archer=body_rows(['...#PpPPPpP#....','...s#PpppP#s#G..','....#llgll#.#hG.','.....#pp#pp##hG.','.....#ll#ll#.G..'])
bodies={}
for job,name,fr in [('warrior','전사',warrior),('rogue','도적',rogue),('archer','궁수',archer)]:
    if job=='warrior':
        left=body_rows(['....#AaAa#......','...Gs#Aa#.......','..#WG#bg#.......','..#W##bb#.......','..W#.#ll##......'])
        bk=body_rows(['...#AaAAAaA#....','...s#AaaaA#s#G..','....#bbgbb#GW##.','.....#bb#bb##W#.','.....#ll#ll#.##W'])
    elif job=='rogue':
        left=body_rows(['....#RrRr#......','....s#Rr#.......','...GW#lg#.......','...W.#rr#.......','.....#ll##......'])
        bk=body_rows(['...#RrRRRrR#....','...s#RrrrR#sG...','....#llgll#GW...','.....#rr#rr#W...','.....#ll#ll#....'])
    else:
        left=body_rows(['....#PpPp#G.....','....s#Pp#h#.....','..Ghh#lg#h#.....','..Gh.#pp#.......','...G.#ll##......'])
        bk=body_rows(['...#PpPPPpP#....','..G#hPpppP#s....','.Gh#hllgll#.....','.Gh#.#pp#pp#....','..G..#ll#ll#....'])
    if job=='archer':
        # 활은 채운 막대 대신 휜 테두리와 밝은 시위로 구분한다.
        for a,side in [(fr,'right'),(bk,'left'),(left,'left')]:
            for y in range(11,16):
                for x in (range(13,16) if side=='right' else range(0,4)):a[y][x]='.'
            for y,x in [(10,14),(11,15),(12,15),(13,15),(14,14),(15,13)]:
                a[y][x if side=='right' else 15-x]='G'
            for y in range(11,14):a[y][13 if side=='right' else 2]='A'
    frames={'front':fr,'left':left,'back':bk,'right':flip(left)}
    walk={}
    for d,a in frames.items():
        poses=[]
        for phase in range(4):
            p=copy(a)
            # 팔·무기·얼굴은 고정하고 발만 번갈아 한 칸 들어 올린다.
            if phase in [0,2]:
                candidates=[x for x,v in enumerate(a[15]) if v=='l']
                mid=(min(candidates)+max(candidates))/2
                side=[x for x in candidates if (x<=mid)==(phase==0)]
                for x in side:p[14][x]='l';p[15][x]='.'
            poses.append(p)
        walk[d]=poses
    bodies[job]={'name':name,'frames':frames,'walk':walk}
data={'version':2,'frame':[16,16],'palette':PAL,'directions':DIRS,'heads':heads,'bodies':bodies,
      'animations':{'walk':{'frame_ms':160,'head_offset_y':[0,0,0,0]}},
      'approved_source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
def rgba(rows):
    im=Image.new('RGBA',(16,16))
    im.putdata([tuple(bytes.fromhex(PAL[v][1:])) if len(PAL[v])==9 else (*bytes.fromhex(PAL[v][1:]),255) for r in rows for v in r])
    return im
def compose(hid,job,d,phase=-1):
    h=heads[hid]['frames'][d];b=bodies[job]
    return layer(h['rear'],b['frames'][d] if phase<0 else b['walk'][d][phase],h['front'])
assert compose('M1','warrior','front')==base,'승인본 불일치'
OUT=ROOT/'production';OUT.mkdir(exist_ok=True)
(OUT/'sprites.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
count=0
for hid in heads:
    for job in bodies:
        path=OUT/hid/job;path.mkdir(parents=True,exist_ok=True)
        sheet=Image.new('RGBA',(80,64))
        for row,d in enumerate(DIRS):
            for col,phase in enumerate([-1,0,1,2,3]):
                pixels=compose(hid,job,d,phase)
                assert len(pixels)==16 and all(len(r)==16 for r in pixels)
                eyes={(x,y) for y,r in enumerate(pixels) for x,v in enumerate(r) if v=='E'}
                expected={(5,7),(5,8),(9,7),(9,8)} if d=='front' else {(5,7),(5,8)} if d=='left' else {(10,7),(10,8)} if d=='right' else set()
                assert eyes==expected,(hid,job,d,phase,eyes)
                assert any(v=='l' for v in pixels[15]),(hid,job,d,'feet')
                im=rgba(pixels);assert set(im.getchannel('A').getdata())<={0,255}
                im.save(path/(d+('-idle' if phase<0 else '-walk-'+str(phase))+'.png'))
                sheet.paste(im,(col*16,row*16));count+=1
        sheet.save(path/'sheet.png')
# 직업별 검토 이미지는 정면·왼쪽·뒤·오른쪽 순서다.
for job in bodies:
    sheet=Image.new('RGB',(680,12*104+56),'#20242c');draw=ImageDraw.Draw(sheet)
    draw.text((16,14),'16x16 / '+job+' / front left back right',fill='#f0dec2')
    for row,hid in enumerate(heads):
        y=56+row*104;draw.text((12,y+30),hid,fill='#f0dec2')
        for col,d in enumerate(DIRS):
            im=rgba(compose(hid,job,d)).resize((80,80),Image.Resampling.NEAREST)
            sheet.paste(im,(90+col*145,y),im)
    sheet.save(OUT/(job+'-contact.png'))
for job in bodies:
    frames=[]
    for phase in range(4):
        im=Image.new('RGB',(512,144),'#20242c')
        for i,d in enumerate(DIRS):
            sprite=rgba(compose('M1',job,d,phase)).resize((112,112),Image.Resampling.NEAREST)
            im.paste(sprite,(i*128+8,16),sprite)
        frames.append(im)
    frames[0].save(OUT/(job+'-walk.gif'),save_all=True,append_images=frames[1:],duration=160,loop=0)
print('PASS:',count,'frames; 36 sheets; approved front exact; every eye position, planted foot, size and alpha checked')
