import json,sys,time
B=1791425379.96
def ep(s): return time.mktime(time.strptime('2026-10-07 '+s,'%Y-%m-%d %H:%M:%S'))
a,b=ep(sys.argv[1])-B,ep(sys.argv[2])-B
lo=int(sys.argv[3]) if len(sys.argv)>3 else 0
hi=int(sys.argv[4]) if len(sys.argv)>4 else 10**9
skip=('You hit','You miss','You have no','Light source','Your light')
for i,l in enumerate(open('/projectnb/jbrcs/mangband/runs/pilot/dive04/events.jsonl')):
    if not lo<=i<=hi: continue
    d=json.loads(l)
    if not a<=d['t']<=b: continue
    if d['ev']=='message':
        if d['text'].startswith(skip): continue
        print(i,time.strftime('%H:%M:%S',time.localtime(d['t']+B)),d['text'])
    elif d['ev']=='ack' and not d['cmd'].startswith(('walk','custom .','redraw')): print(i,time.strftime('%H:%M:%S',time.localtime(d['t']+B)),'ACK',d['cmd'])
