import json,sys,datetime,collections
# usage: tl.py START END [kinds] ; times 'YYYY-MM-DD HH:MM:SS' local
def ep(s): return datetime.datetime.strptime(s,'%Y-%m-%d %H:%M:%S').timestamp()
a,b=ep(sys.argv[1]),ep(sys.argv[2])
skip={'move','audit_check','mons'}
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
for l in open(D+'decisions.jsonl'):
    try: d=json.loads(l)
    except: continue
    t=d['t']
    if t<a: continue
    if t>b: break
    k=d['kind']
    if k in skip: continue
    ts=datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S')
    hp=d.get('hp')
    rest={x:v for x,v in d.items() if x not in('t','kind','hp','pos','depth')}
    print(ts,k,d.get('depth'),d.get('pos'),hp,json.dumps(rest)[:int(sys.argv[3]) if len(sys.argv)>3 else 260])
