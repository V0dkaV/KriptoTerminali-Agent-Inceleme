"""Generate the application's geometric icon without remote assets."""
import math
import struct
import zlib
from pathlib import Path


def png(size):
    segments=[(18,43,18,22),(18,33,31,21),(18,33,33,44),(41,18,41,34),(49,25,49,43)]
    def distance(x,y,line):
        a,b,c,d=line
        t=max(0,min(1,((x-a)*(c-a)+(y-b)*(d-b))/max(1,(c-a)**2+(d-b)**2)))
        return math.hypot(x-a-t*(c-a),y-b-t*(d-b))
    pixels=bytearray()
    for yy in range(size):
        pixels.append(0)
        for xx in range(size):
            x,y=(xx+.5)*64/size,(yy+.5)*64/size
            if math.hypot(max(abs(x-32)-19,0),max(abs(y-32)-19,0))>12:
                color=(0,0,0,0)
            elif any(distance(x,y,line)<2.5 for line in segments[:3]): color=(82,222,193,255)
            elif any(distance(x,y,line)<2 for line in segments[3:]): color=(117,157,249,255)
            else: color=(15+int(y/10),31+int(x/7),49+int(y/6),255)
            pixels.extend(color)
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')


folder=Path(__file__).resolve().parent.parent/'assets'
folder.mkdir(exist_ok=True)
(folder/'icon.png').write_bytes(png(256))
images=[(n,png(n)) for n in (16,32,48,256)]
offset=6+16*len(images)
entries=[]
for size,data in images:
    entries.append(struct.pack('<4B2H2I',size%256,size%256,0,0,1,32,len(data),offset))
    offset+=len(data)
(folder/'icon.ico').write_bytes(struct.pack('<3H',0,1,len(images))+b''.join(entries)+b''.join(data for _,data in images))
print('Application icons generated.')
