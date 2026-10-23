import json,time,collections,os,re
os.environ['TZ']='America/New_York'; time.tzset()
RUN='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
MIS=json.load(open('/projectnb/jbrcs/mangband/runs/missions.json'))
def ep(s): return time.mktime(time.strptime(s,"%Y-%m-%d %H:%M"))
def win(label):
    m=[m for m in MIS if m['label']==label][0]
    return ep(m['start']),ep(m['end'])
_cache=None
def dec():
    global _cache
    if _cache is None:
        _cache=[json.loads(l) for l in open(RUN+'decisions.jsonl')]
    return _cache
def recs(label):
    a,b=win(label); return [d for d in dec() if a<=d['t']<=b]
def hhmmss(t): return time.strftime('%H:%M:%S',time.localtime(t))
LABELS=['m%d'%i for i in range(17,24)]
def evs(label,pad=0):
    a,b=win(label)
    for l in open(RUN+'events.jsonl'):
        if '"epoch"' not in l: continue
        d=json.loads(l)
        if a-pad<=d['epoch']<=b+pad: yield d
