import json,time,re,bisect,sys,collections
R="/projectnb/jbrcs/mangband/runs/pilot/"
def load(d):
    recs=[]
    for l in open(R+d+"/decisions.jsonl"):
        r=json.loads(l)
        if r.get("hp") and r.get("depth") is not None:
            recs.append((r["t"],r["depth"]*50,r["hp"][0]/max(1,r["hp"][1]),r))
    return recs
def run(d):
    recs=load(d); ts=[r[0] for r in recs]
    days=sorted({time.strftime("%Y-%m-%d",time.localtime(t)) for t in ts})
    for n,l in enumerate(open(R+d+"/navigator.md"),1):
        m=re.match(r"- (\d\d):(\d\d) (\S+) (\S+)",l)
        if not m: continue
        hh,mm=int(m[1]),int(m[2]); jd=m[3]; jh=m[4]
        out=[]
        for day in days:
            t0=time.mktime(time.strptime(f"{day} {hh}:{mm}","%Y-%m-%d %H:%M"))
            i=bisect.bisect(ts,t0)
            cand=[recs[j] for j in range(max(0,i-1),min(len(recs),i+1))]
            c=min(cand,key=lambda r:abs(r[0]-t0))
            if abs(c[0]-t0)<240:
                out.append(f"{day[5:]} d={c[1]}ft hp={c[2]*100:.0f}% (Δ{c[0]-t0:+.0f}s)")
        print(f"L{n} j:{jd} {jh} | "+" ; ".join(out))
run(sys.argv[1])
