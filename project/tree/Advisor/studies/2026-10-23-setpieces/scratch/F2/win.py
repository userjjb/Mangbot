import json,time,sys
m,a,b=sys.argv[1:4]; skip=sys.argv[4] if len(sys.argv)>4 else ''
A=time.mktime(time.strptime(a,'%Y-%m-%d %H:%M:%S'));B=time.mktime(time.strptime(b,'%Y-%m-%d %H:%M:%S'))
last=None
for l in open(m+'_ev.jsonl'):
    d=json.loads(l)
    if d['ev']=='message' and A<=d['epoch']<=B:
        t=d['text']
        if skip and any(s in t for s in skip.split('|')): continue
        print(time.strftime('%H:%M:%S',time.localtime(d['epoch'])),t[:150])
    if d['ev']=='level' and A<=d['epoch']<=B: print(time.strftime('%H:%M:%S',time.localtime(d['epoch'])),'LEVEL',str(d)[:150])
