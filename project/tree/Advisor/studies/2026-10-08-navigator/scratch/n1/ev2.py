import json,datetime,sys
from ev import procs
st=[]
for l in open('/projectnb/jbrcs/mangband/runs/pilot/dive03/decisions.jsonl'):
    if '"what": "started"' in l: st.append(json.loads(l)['t'])
allev=[]
for i,p in enumerate(procs):
    for d in p:
        allev.append((st[i if i<35 else i+1]+d["t"],d))
allev.sort(key=lambda x:x[0])
def ts(t):return datetime.datetime.fromtimestamp(t).strftime('%m-%d %H:%M:%S')
if __name__=='__main__':
    a=datetime.datetime.strptime(sys.argv[1],"%Y-%m-%d %H:%M:%S").timestamp()
    b=datetime.datetime.strptime(sys.argv[2],"%Y-%m-%d %H:%M:%S").timestamp()
    kinds=sys.argv[3].split(',') if len(sys.argv)>3 else ['message']
    pat=sys.argv[4] if len(sys.argv)>4 else None
    import re
    for t,d in allev:
        if a<=t<=b and d['ev'] in kinds:
            if d['ev']=='message': s=d['text']
            elif d['ev']=='level': s='LEVEL %s'%d['depth']
            elif d['ev']=='ack': s='ACK '+d['cmd']
            else: s=json.dumps(d)[:200]
            if pat and not re.search(pat,s): continue
            print(ts(t),s[:220])
