import json,sys,datetime,collections
def ep(s): return datetime.datetime.strptime(s,'%Y-%m-%d %H:%M:%S').timestamp()
a,b=ep(sys.argv[1]),ep(sys.argv[2])
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
c=collections.Counter()
for l in open(D+'decisions.jsonl'):
    d=json.loads(l)
    if d['t']<a: continue
    if d['t']>b: break
    if d['kind']=='attention': c[d['what']]+=1
    elif d['kind'] in('perception_gap','nav_complaint','user_note'): c[d['kind']]+=1
print(sorted(c.items(),key=lambda x:-x[1]))
