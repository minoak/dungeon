# png_util.py — PIL 없는 환경용 미니 PNG 도구 (뷰어 에셋 준비 전용, 게임 코드와 무관)
# 지원: 8bit RGBA/RGB/palette/gray 디코드, RGBA 인코드, 확대, 격자, 시트 합성
import struct, zlib, sys


def decode(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not a png'
    pos = 8
    idat = b''
    plte = None
    trns = None
    w = h = bitd = ctype = None
    while pos < len(d):
        ln, typ = struct.unpack('>I4s', d[pos:pos+8])
        chunk = d[pos+8:pos+8+ln]
        if typ == b'IHDR':
            w, h, bitd, ctype = struct.unpack('>IIBB', chunk[:10])
            interlace = chunk[12]
            assert interlace == 0 and (bitd == 8 or (bitd in (1, 2, 4) and ctype in (0, 3))), \
                f'unsupported bitd={bitd} ctype={ctype} interlace={interlace}'
        elif typ == b'PLTE':
            plte = chunk
        elif typ == b'tRNS':
            trns = chunk
        elif typ == b'IDAT':
            idat += chunk
        pos += 12 + ln
    raw = zlib.decompress(idat)
    nch = {0: 1, 2: 3, 3: 1, 6: 4, 4: 2}[ctype]
    stride = (w * nch * bitd + 7) // 8
    bpp = max(1, nch * bitd // 8)
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p+stride]); p += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i-bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i-bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i-bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i-bpp] if i >= bpp else 0
                pa, pb, pc = abs(b-c), abs(a-c), abs(a+b-2*c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y*stride:(y+1)*stride] = line
        prev = line
    if bitd < 8:
        # 서브바이트 샘플(팔레트/그레이 1·2·4bit)을 픽셀당 1바이트 인덱스로 전개
        expanded = bytearray(h * w)
        mask = (1 << bitd) - 1
        per_byte = 8 // bitd
        for y in range(h):
            row = out[y*stride:(y+1)*stride]
            for x in range(w):
                b = row[x // per_byte]
                shift = 8 - bitd * (x % per_byte + 1)
                expanded[y*w+x] = (b >> shift) & mask
        out = expanded
    # RGBA 로 정규화
    rgba = bytearray(w*h*4)
    if ctype == 6:
        rgba[:] = out
    elif ctype == 2:
        for i in range(w*h):
            rgba[i*4:i*4+3] = out[i*3:i*3+3]; rgba[i*4+3] = 255
    elif ctype == 3:
        for i in range(w*h):
            idx = out[i]
            rgba[i*4:i*4+3] = plte[idx*3:idx*3+3]
            rgba[i*4+3] = trns[idx] if trns and idx < len(trns) else 255
    elif ctype == 0:
        for i in range(w*h):
            g = out[i]
            rgba[i*4] = rgba[i*4+1] = rgba[i*4+2] = g; rgba[i*4+3] = 255
    elif ctype == 4:
        for i in range(w*h):
            rgba[i*4] = rgba[i*4+1] = rgba[i*4+2] = out[i*2]; rgba[i*4+3] = out[i*2+1]
    return w, h, rgba


def encode(path, w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y*w*4:(y+1)*w*4]
    comp = zlib.compress(bytes(raw), 9)
    def chunk(typ, data):
        c = struct.pack('>I', len(data)) + typ + data
        return c + struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', comp)
    png += chunk(b'IEND', b'')
    open(path, 'wb').write(png)


def upscale(w, h, rgba, s):
    ow, oh = w*s, h*s
    out = bytearray(ow*oh*4)
    for y in range(oh):
        sy = y // s
        row = rgba[sy*w*4:(sy+1)*w*4]
        orow = bytearray(ow*4)
        for x in range(ow):
            sx = x // s
            orow[x*4:x*4+4] = row[sx*4:sx*4+4]
        out[y*ow*4:(y+1)*ow*4] = orow
    return ow, oh, out


def grid(w, h, rgba, cell, color=(255, 0, 255, 255)):
    for y in range(0, h, cell):
        for x in range(w):
            rgba[(y*w+x)*4:(y*w+x)*4+4] = bytes(color)
    for x in range(0, w, cell):
        for y in range(h):
            rgba[(y*w+x)*4:(y*w+x)*4+4] = bytes(color)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'zoom':  # png_util.py zoom in.png out.png scale [gridcell]
        w, h, px = decode(sys.argv[2])
        s = int(sys.argv[4])
        w, h, px = upscale(w, h, px, s)
        if len(sys.argv) > 5:
            grid(w, h, px, int(sys.argv[5]) * s)
        encode(sys.argv[3], w, h, px)
        print(f'{sys.argv[3]} {w}x{h}')
