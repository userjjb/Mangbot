import json,time,os,re
os.environ['TZ']='America/New_York'; time.tzset()
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
def ep(s): return time.mktime(time.strptime(s,'%Y-%m-%d %H:%M'))
W={17:('2026-10-16 13:57','2026-10-16 14:40'),18:('2026-10-16 18:46','2026-10-16 19:26'),19:('2026-10-16 22:14','2026-10-16 22:55'),20:('2026-10-16 23:41','2026-10-17 00:18'),21:('2026-10-17 00:47','2026-10-17 01:35'),22:('2026-10-17 01:45','2026-10-17 02:16'),23:('2026-10-22 22:15','2026-10-22 22:31')}
WE={m:(ep(a)-120,ep(b)+120) for m,(a,b) in W.items()}
def mission(e):
    for m,(a,b) in WE.items():
        if a<=e<=b: return m
    return None
def hm(e): return time.strftime('%m-%d %H:%M:%S',time.localtime(e))
def events():
    for l in open(D+'events.jsonl'):
        yield json.loads(l)
def decisions():
    for l in open(D+'decisions.jsonl'):
        yield json.loads(l)
