import json,struct,collections
for s in (1,2,3):
    seen=collections.OrderedDict()
    for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
        d=json.loads(l)
        if d['dir']!='R': continue
        b=bytes.fromhex(d['hex'])
        if d['name']=='IND:level': k=('level',b[1],b[2])
        elif d['name']=='IND:exp': k=('exp',)+struct.unpack('>iii',b[1:13])
        elif d['name']=='IND:stat0': k=('stat0',)+struct.unpack('>hhh',b[1:7])
        elif d['name']=='IND:stat3': k=('stat3',)+struct.unpack('>hhh',b[1:7])
        elif d['name']=='IND:state': k=('state',b[1],b[2],b[3])
        elif d['name']=='IND:speed': k=('speed',struct.unpack('>h',b[1:3])[0])
        elif d['name']=='IND:hunger': k=('hunger',b[1])
        elif d['name']=='IND:armor': k=('armor',)+struct.unpack('>hhh',b[1:7])
        elif d['name']=='IND:skills2': k=('skills2(blows,shots,infra)',)+struct.unpack('>hhh',b[1:7])
        elif d['name']=='IND:track': k=('track(attr,len)',)+struct.unpack('BB',b[1:3])
        elif d['name']=='IND:hp': k=('hp',)+struct.unpack('BB',b[1:3])
        else: continue
        seen.setdefault(k,d['t'])
    print('SESSION',s)
    for k,t in seen.items():
        if k[0] in('hp',): continue
        print('  ',t,k)
