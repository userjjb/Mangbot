import json,sys,time
m=sys.argv[1]; kinds=set(sys.argv[2].split(',')); msg=len(sys.argv)>3 and sys.argv[3]=='msg'
rows=[]
for l in open(m+'_dec.jsonl'):
    d=json.loads(l)
    if d['kind'] in kinds: rows.append((d['t'],d))
if msg:
    for l in open(m+'_ev.jsonl'):
        d=json.loads(l)
        if d['ev']=='message': rows.append((d['epoch'],{'kind':'MSG','txt':d.get('text') or d.get('msg') or str(d)}))
        if d['ev']=='level': rows.append((d['epoch'],{'kind':'LEVEL','txt':str(d)}))
rows.sort(key=lambda r:r[0])
for t,d in rows:
    k=d['kind']
    ts=time.strftime('%H:%M:%S',time.localtime(t))
    if k=='MSG' or k=='LEVEL': print(ts,k,d['txt'][:200]); continue
    hp=d.get('hp'); dep=d.get('depth')
    rest={x:v for x,v in d.items() if x not in('t','kind','depth','pos','hp')}
    print(ts,k,dep,hp,str(d.get('pos')),json.dumps(rest)[:300])
