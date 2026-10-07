import json,collections,sys
for s in (1,2,3):
    c=collections.Counter(); ids={}
    for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
        d=json.loads(l)
        if d.get('dir')=='R' and 'id' in d:
            c[d['name']]+=1; ids[d['name']]=d['id']
    print('session',s)
    for n,k in sorted(c.items(), key=lambda x:ids[x[0]]): print(' ',ids[n],n,k)
