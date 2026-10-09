import json,sys,datetime
# usage: show.py "YYYY-mm-dd HH:MM:SS" "YYYY-mm-dd HH:MM:SS" [kinds comma]
a=datetime.datetime.strptime(sys.argv[1],"%Y-%m-%d %H:%M:%S").timestamp()
b=datetime.datetime.strptime(sys.argv[2],"%Y-%m-%d %H:%M:%S").timestamp()
kinds=set(sys.argv[3].split(',')) if len(sys.argv)>3 else {'goal','attention','act'}
for l in open('/projectnb/jbrcs/mangband/runs/pilot/dive03/decisions.jsonl'):
    try:d=json.loads(l)
    except: continue
    if a<=d['t']<=b and d['kind'] in kinds:
        t=datetime.datetime.fromtimestamp(d['t']).strftime('%m-%d %H:%M:%S')
        d2={k:v for k,v in d.items() if k not in('t','kind','pos')}
        print(t,d['kind'],json.dumps(d2)[:int(sys.argv[4]) if len(sys.argv)>4 else 300])
