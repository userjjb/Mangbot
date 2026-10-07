import json,sys,struct
s=int(sys.argv[1]); start=float(sys.argv[2]) if len(sys.argv)>2 else 0
def dec(h):
    b=bytes.fromhex(h)
    pos=chr(b[1]);a=b[2];c=b[3];attr=b[4]
    wgt=struct.unpack('>H',b[5:7])[0]; amt=struct.unpack('>h',b[7:9])[0]; tval=b[9]; flag=b[10]; tester=b[11]
    rest=b[12:].split(b'\0')
    return pos,tval,amt,wgt,rest[0].decode('latin1'),rest[1].decode('latin1') if len(rest)>1 else ''
prev=None
for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
    d=json.loads(l)
    if d['t']<start: continue
    if d['dir']=='R' and d['name']=='PKT_INVEN':
        print(d['t'],'INVEN',dec(d['hex']))
    elif d['dir']=='R' and d['name']=='PKT_EQUIP':
        b=bytes.fromhex(d['hex']); print(d['t'],'EQUIP',chr(b[1]),b[5],b[6:].split(b'\0')[0].decode('latin1')[:60] if False else b[8:].split(b'\0')[0].decode('latin1'))
    elif d['dir']=='R' and d['name']=='PKT_MESSAGE':
        print(d['t'],'MSG',d['txt'][3:90])
    elif d['dir']=='S' and d['name'] not in('PKT_KEEPALIVE','PKT_WALK'):
        print(d['t'],'S',d['name'],d['hex'][:24])
    elif d['dir']=='R' and d['name'] in ('IND:depth','IND:level','PKT_FLOOR'):
        print(d['t'],d['name'],d['hex'])
