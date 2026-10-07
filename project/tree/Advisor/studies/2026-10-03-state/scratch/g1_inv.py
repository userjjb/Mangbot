import json,sys,struct
s=int(sys.argv[1]); t0=float(sys.argv[2]); t1=float(sys.argv[3])
def cstr(b,i):
    j=b.index(0,i); return b[i:j].decode('latin1'), j+1
for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
    d=json.loads(l)
    if not (t0<=d['t']<=t1): continue
    if d.get('dir')=='S' and 'name' in d and d['name'] not in('PKT_KEEPALIVE',):
        print(d['t'],'C->S',d['name'],d['hex'][:40]); continue
    if d.get('dir')!='R' or 'id' not in d: continue
    b=bytes.fromhex(d['hex'])
    if d['id']==30:
        pos=chr(b[1]); wgt,amt=struct.unpack('<Hh',b[5:9]) if False else (None,None)
        # layout: id,pos,ga,gc,attr, wgt(u16), amt(i16), tval, flag, st, name\0, name1\0
        wgt=int.from_bytes(b[5:7],'big'); amt=int.from_bytes(b[7:9],'big',signed=True)
        tval=b[9]; name,i=cstr(b,12)
        print(d['t'],'INVEN',repr(pos),'wgt',wgt,'amt',amt,'tval',tval,'flag',b[10],'st',b[11],repr(name))
    elif d['id']==31:
        pos=chr(b[1]); wgt=int.from_bytes(b[3:5],'big'); tval=b[5]; name,i=cstr(b,7)
        print(d['t'],'EQUIP',repr(pos),'wgt',wgt,'tval',tval,repr(name))
    elif d['id']==49:
        print(d['t'],'FLOOR',b[1:].hex()[:80], b.split(b'\0')[-3:-1])
    elif d['id']==46:
        typ=int.from_bytes(b[1:3],'big'); print(d['t'],'MSG',typ,repr(b[3:].decode('latin1')))
