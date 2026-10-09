import json,sys,datetime
a=datetime.datetime.strptime(sys.argv[1],"%Y-%m-%d %H:%M:%S").timestamp()
b=datetime.datetime.strptime(sys.argv[2],"%Y-%m-%d %H:%M:%S").timestamp()
step=int(sys.argv[3]) if len(sys.argv)>3 else 60
cur=None;rows={}
for l in open('/projectnb/jbrcs/mangband/runs/pilot/dive03/decisions.jsonl'):
    try:d=json.loads(l)
    except: continue
    if a<=d['t']<=b and d.get('depth') is not None:
        k=int((d['t']-a)//step); r=rows.setdefault(k,[99,0,1.0])
        r[0]=min(r[0],d['depth']);r[1]=max(r[1],d['depth'])
        if d['hp'][1]: r[2]=min(r[2],d['hp'][0]/d['hp'][1])
for k in sorted(rows):
    r=rows[k];print(datetime.datetime.fromtimestamp(a+k*step).strftime('%m-%d %H:%M'),'%d-%dft'%(r[0]*50,r[1]*50),'minHP %.0f%%'%(r[2]*100))
