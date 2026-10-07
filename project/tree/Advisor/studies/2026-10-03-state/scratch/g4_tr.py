import json,sys
f=sys.argv[1]
out=[]
for l in open(f):
    r=json.loads(l)
    m=r.get("message")
    if not m or not isinstance(m.get("content"),list): continue
    for c in m["content"]:
        if c.get("type")=="tool_use":
            out.append((r["timestamp"],"CALL",json.dumps(c["input"])[:300]))
        elif c.get("type")=="tool_result":
            cc=c.get("content")
            if isinstance(cc,list): cc="\n".join(x.get("text","") for x in cc)
            out.append((r["timestamp"],"RESULT",cc))
        elif c.get("type")=="text" and r["type"]=="assistant":
            out.append((r["timestamp"],"SAY",c["text"]))
import pickle
pickle.dump(out,open("/projectnb/jbrcs/mangband/Advisor/studies/2026-10-03-state/scratch/"+sys.argv[2]+".pkl","wb"))
print(len(out))
