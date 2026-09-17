#!/usr/bin/env python3
import binascii,struct,sys,zlib
N=300
def inside(x,y,r=58):c=min(max(x,r),N-r);d=min(max(y,r),N-r);return(x-c)**2+(y-d)**2<=r*r
def px(x,y):
 if not inside(x,y):return(0,0,0,0)
 t=(x+y)/(2*N);bg=tuple(round(a*(1-t)+b*t)for a,b in zip((139,92,246),(67,56,202)))
 lines=[((61,197),(239,197)),((78,163),(111,122)),((111,122),(143,148)),((143,148),(211,76))]
 for(a,b),(c,d)in lines:
  vx,vy=c-a,d-b;w=((x-a)*vx+(y-b)*vy)/(vx*vx+vy*vy);w=max(0,min(1,w));dx=x-(a+w*vx);dy=y-(b+w*vy)
  if dx*dx+dy*dy<42:return(255,255,255,255)
 return(*bg,255)
def ch(k,d):return struct.pack('>I',len(d))+k+d+struct.pack('>I',binascii.crc32(k+d)&0xffffffff)
r=bytearray()
for y in range(N):r.append(0);[r.extend(px(x+.5,y+.5))for x in range(N)]
p=b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack('>IIBBBBB',N,N,8,6,0,0,0))+ch(b'IDAT',zlib.compress(bytes(r),9))+ch(b'IEND',b'');open(sys.argv[1],'wb').write(p)
