import json,time,re
from g4_ev import events,R
def stamp(a): return time.strftime("%m-%d %H:%M:%S",time.localtime(a))
def abs_t(d):
    st,runs=events(d); out=[]
    for s,run in zip(st,runs):
        for r in run: out.append((s+r["t"],r))
    return out
def decs(d):
    return [json.loads(l) for l in open(R+d+"/decisions.jsonl")]
def parse(s):
    f="%Y-%m-%d %H:%M:%S" if s.count(":")==2 else "%Y-%m-%d %H:%M"
    return time.mktime(time.strptime(s,f))
def msgs(ev,a,b,pat=None):
    for t,r in ev:
        if a<=t<=b and r.get("ev")=="message" and (pat is None or re.search(pat,r["text"])):
            print(stamp(t),r["text"])
