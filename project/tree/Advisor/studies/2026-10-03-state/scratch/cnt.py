import json,collections,sys
for s in (1,2,3):
    p=f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'
    c=collections.Counter(); cs=collections.Counter(); last=0;n=0;bad=0; res=collections.Counter()
    for l in open(p):
        try:d=json.loads(l)
        except: bad+=1;continue
        n+=1; last=d['t']
        if d['dir']=='R': c[d['name']]+=1; res[d['res']]+=1
        elif d['dir']=='S': cs[d['name']]+=1
        else: cs['dir_'+d['dir']]+=1
    print('SESSION',s,'lines',n,'bad',bad,'last t',last,'res',dict(res))
    print(' R:',sorted(c.items(),key=lambda x:-x[1]))
    print(' S/other:',sorted(cs.items(),key=lambda x:-x[1])[:25])
