import json,re,collections
from common import *
for i in IDX:
    o=json.load(open(f'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays/ep{i}.json'))
    hp=[x for x in o['hp_series'] if x[0]>=o['t0']]
    hm=[m for m in o['hostile_msgs'] if not re.search(r' misses you',m['text'])]
    acc=collections.Counter();tot=0
    for (t1,h1,_),(t2,h2,_) in zip(hp,hp[1:]):
        d=h1-h2
        if d<=0:continue
        ms=[m for m in hm if t1<m['t']<=t2]
        if not ms:acc['(unattributed)']+=d;tot+=d;continue
        for m in ms:
            mm=re.match(r"^(?:The )?(.*?) (hits|bites|claws|breathes|stings|fires|casts|touches|gazes|crushes|butts|spits|kicks|mumbles|points|makes|creates|wails)",m['text'])
            n=mm.group(1) if mm else m['text'][:25]
            n2=n if n!='It' else 'It(unseen)'
            acc[n2]+=d/len(ms)
        tot+=d
    print(i,'total drop',tot,[(k,round(v)) for k,v in acc.most_common(5)],'min',o['outcome']['lowest_hp'],'hp t0',o['player']['hp'],'/',o['player']['mhp'])
