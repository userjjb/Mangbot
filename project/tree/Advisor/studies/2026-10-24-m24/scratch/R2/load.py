import json,datetime,zoneinfo,re
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
tz=zoneinfo.ZoneInfo('America/New_York')
def ep(s): return datetime.datetime.strptime(s,'%Y-%m-%d %H:%M').replace(tzinfo=tz).timestamp()
M=json.load(open('/projectnb/jbrcs/mangband/runs/missions.json'))
W=[(m['label'],ep(m['start']),ep(m['end'])) for m in M if m['label'] in ['m%d'%i for i in range(17,25)]]
def ts(e): return datetime.datetime.fromtimestamp(e,tz).strftime('%m-%d %H:%M:%S')
def events():
    base=None;out=[]
    for l in open(D+'events.jsonl'):
        try:r=json.loads(l)
        except: continue
        if r['ev']=='pilot_start': base=r['epoch']-r['t']
        if base is None: continue
        if r['ev'] in('floor','flags','pos','ack','itemlist'): 
            if r['ev']!='pos': continue
        r['T']=base+r['t']; out.append(r)
    return out
def decs():
    return [json.loads(l) for l in open(D+'decisions.jsonl')]
