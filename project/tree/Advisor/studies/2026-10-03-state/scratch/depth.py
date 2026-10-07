import json,sys,struct
for s in (1,2,3):
    print('SESSION',s)
    last=None;cnt=0
    for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
        d=json.loads(l)
        if d['dir']=='R' and d['name']=='IND:depth':
            v=struct.unpack('b',bytes.fromhex(d['hex'])[1:2])[0]
            cnt+=1
            flag='' if v!=last else ' (same value repeated)'
            print(' ',d['t'],'depth',v,flag) if (v!=last or cnt<4) else None
            last=v
        elif d['dir']=='S' and d['name'] in ("CUSTOM:'<'","CUSTOM:'>'"):
            print(' ',d['t'],'S',d['name'])
    print(' total depth pkts',cnt)
