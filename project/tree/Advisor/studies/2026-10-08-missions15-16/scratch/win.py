import json,sys,time
lo,hi=sys.argv[1],sys.argv[2]
def ep(s):
    return time.mktime(time.strptime('2026-10-07 '+s,'%Y-%m-%d %H:%M:%S'))
a,b=ep(lo),ep(hi)
last=None
for l in open('/projectnb/jbrcs/mangband/runs/pilot/dive04/decisions.jsonl'):
    try:d=json.loads(l)
    except: continue
    if not a<=d['t']<=b: continue
    k=d['kind']
    hh=time.strftime('%H:%M:%S',time.localtime(d['t']))
    if k in('move','audit_check'): continue
    if k=='mons':
        s=';'.join(f"{m[2]}@{m[0]},{m[1]}" for m in d['monsters'])
        if (s,d['hp'][0]//10)!=last:
            print(hh,'MONS',d['pos'],d['hp'][0],s[:260]); last=(s,d['hp'][0]//10)
        continue
    print(hh,k,d['pos'],d['hp'][0],(d.get('cmd') or '')+' '+str(d.get('what') or d.get('goal') or '')+': '+str(d.get('why') or d.get('detail') or d.get('text') or d.get('note') or '')[:330])
