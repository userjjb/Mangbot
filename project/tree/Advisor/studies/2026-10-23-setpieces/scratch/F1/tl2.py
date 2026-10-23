import json,sys,datetime
def ep(s): return datetime.datetime.strptime(s,'%Y-%m-%d %H:%M:%S').timestamp()
a,b=ep(sys.argv[1]),ep(sys.argv[2]); W=int(sys.argv[3]) if len(sys.argv)>3 else 220
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
for l in open(D+'decisions.jsonl'):
    d=json.loads(l); t=d['t']
    if t<a: continue
    if t>b: break
    k=d['kind']
    if k in('move','audit_check','mons','audit','options'): continue
    if k=='nav_cmd' and d['cmd'] in('status','journal','stop'): continue
    if k=='act':
        w=d.get('why','')
        if not any(x in w for x in('phase','recall','quaff','read','destroy','sell','agent','forced')): continue
    if k=='note': continue
    ts=datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S')
    if k=='attention': s=d['what']+': '+str(d.get('detail'))
    elif k=='goal': s=str(d['goal'])
    elif k=='act': s=d['cmd']+' // '+d.get('why','')
    elif k=='nav_cmd': s=d['cmd']+' '+' '.join(map(str,d['args']))
    elif k=='nav_journal': s=d['text']
    else: s=json.dumps({x:v for x,v in d.items() if x not in('t','kind','hp','pos','depth','crop')})
    hp=d.get('hp'); 
    print(ts,k[:6],d.get('depth'),d.get('pos'),'%s/%s'%tuple(hp) if hp else '',s[:W])
