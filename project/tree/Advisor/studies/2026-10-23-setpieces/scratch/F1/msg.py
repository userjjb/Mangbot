import json,sys,datetime,collections
def ep(s): return datetime.datetime.strptime(s,'%Y-%m-%d %H:%M:%S').timestamp()
a,b=ep(sys.argv[1]),ep(sys.argv[2]); mode=sys.argv[3] if len(sys.argv)>3 else 'count'
flt=sys.argv[4] if len(sys.argv)>4 else None
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/events.jsonl'
c=collections.Counter(); first={}
with open(D) as f:
    for l in f:
        if '"epoch"' not in l or '"message"' not in l: continue
        try:d=json.loads(l)
        except: continue
        e=d.get('epoch')
        if e is None or e<a: continue
        if e>b: break
        if d['ev']!='message': continue
        if flt and flt not in d['text']: continue
        if mode=='list': print(datetime.datetime.fromtimestamp(e).strftime('%H:%M:%S.%f')[:10],d['text'])
        else:
            c[d['text']]+=1; first.setdefault(d['text'],e)
if mode!='list':
    for t,n in sorted(c.items(),key=lambda x:first[x[0]]): print(datetime.datetime.fromtimestamp(first[t]).strftime('%H:%M:%S'),n,t)
