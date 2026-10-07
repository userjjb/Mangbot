import json,time
R="/projectnb/jbrcs/mangband/runs/pilot/"
def starts(d):
    return [json.loads(l)["t"] for l in open(R+d+"/decisions.jsonl") if '"what": "started"' in l]
def events(d):
    st=starts(d); runs=[[]]; prev=-1
    for l in open(R+d+"/events.jsonl"):
        try: r=json.loads(l)
        except: continue
        if r["t"]<prev-1 and prev>5: runs.append([])
        prev=r["t"]; runs[-1].append(r)
    return st,runs
if __name__=="__main__":
    for d in("dive03","dive04"):
        st,runs=events(d)
        print(d,len(st),len(runs),[len(x) for x in runs][:80])
