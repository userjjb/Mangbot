import json,sys
s=int(sys.argv[1]); lo=float(sys.argv[2]); hi=float(sys.argv[3])
for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
    d=json.loads(l)
    if not (lo<=d['t']<=hi): continue
    if d['dir']=='R' and d['name'] in('PKT_INVEN','PKT_EQUIP','PKT_FLOOR','IND:depth','IND:level','IND:state','PKT_MESSAGE','IND:gold','IND:hunger'):
        print(d['t'],d['name'],d['len'],d['hex'][:60],d['txt'][:100])
    elif d['dir']=='S' and d['name'] not in('PKT_KEEPALIVE',):
        print(d['t'],'S',d['name'],d['hex'][:30])
    elif d['dir']=='K': print(d['t'],'K',d.get('key'))
