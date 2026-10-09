import json,re,datetime,sys
# build absolute-time events; pilot.log has only HH:MM:SS, so infer dates by monotonic roll-over starting 2026-09-25
starts=[]
d0=datetime.date(2026,9,25); prev=None
for l in open('/projectnb/jbrcs/mangband/runs/pilot/dive03/pilot.log'):
    m=re.match(r'(\d\d):(\d\d):(\d\d) in the game',l)
    if m:
        h,mi,s=map(int,m.groups()); sec=h*3600+mi*60+s
        if prev is not None and sec<prev: d0+=datetime.timedelta(days=1)
        prev=sec
        starts.append(datetime.datetime.combine(d0,datetime.time(h,mi,s)).timestamp())
procs=[];cur=[];last=-1
for l in open('/projectnb/jbrcs/mangband/runs/pilot/dive03/events.jsonl'):
    try:d=json.loads(l)
    except: continue
    if d['t']<last-5: procs.append(cur);cur=[]
    last=d['t'];cur.append(d)
procs.append(cur)
if __name__=='__main__':
    print(len(starts),len(procs))
    for i,(s,p) in enumerate(zip(starts,procs)):
        print(i,datetime.datetime.fromtimestamp(s),len(p),p[-1]['t'])
