import json,pickle
ev=[];e0=None;n=0
for i,l in enumerate(open('/projectnb/jbrcs/mangband/runs/pilot/dive04/events.jsonl')):
    if '"floor"' in l[:15] or '"flags"' in l[:15] or '"ack"' in l[:14] or '"itemlist"' in l[:18]: 
        continue
    d=json.loads(l)
    if d['ev']=='pilot_start': e0=d['epoch']; print(i,e0)
    d['line']=i+1
    d['abs']=(e0+d['t']) if e0 else None
    if 'epoch' in d and e0 and abs(d['epoch']-d['abs'])>5: print('mismatch',i,d['ev'],d['epoch']-d['abs'])
    ev.append(d)
pickle.dump(ev,open('ev.pkl','wb'))
