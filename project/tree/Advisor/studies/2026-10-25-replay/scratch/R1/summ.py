import json,re,collections,sys
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1')
from common import *
for i in [0,1,3,4,6,7,8,9,10,11,12,14]:
    r=json.load(open(f'../../replays/ep{i}.json'))
    hm=r['hostile_msgs']
    def who(t):
        m=re.match(r'(?:The )?(.+?) (hits|bites|claws|crushes|touches|stings|fires|casts|breathes|mumbles|points|commands|drains|gestures|creates|magically|misses|insults|moons|dances|gives|makes|begs|butts|kicks)',t)
        return m.group(1) if m else t
    landed=collections.Counter();spell=collections.Counter();miss=collections.Counter()
    for h in hm:
        t=h['text']
        if 'was a' in t:continue
        n=who(t)
        if ' misses you' in t:miss[n]+=1
        elif re.search(r' (fires|casts|breathes|mumbles|points|commands|drains|gestures|creates|magically)',t):spell[n]+=1
        else:landed[n]+=1
    # pure interval damage
    hp=r['hp_series'];dmg=collections.Counter();pn=collections.Counter()
    for a,b in zip(hp,hp[1:]):
        d=a[1]-b[1]
        if d<=0:continue
        ms=[h for h in hm if a[0]<h['t']<=b[0]+0.3 and 'misses' not in h['text'] and 'was a' not in h['text']]
        names={who(h['text']) for h in ms}
        if len(names)==1 and ms:
            n=names.pop();dmg[n]+=d;pn[n]+=len(ms)
    print(f"EP{i} {r['mission']} {r['depth_ft']}ft t0 {hms(r['t0'])} hp {r['player']['hp']}/{r['player']['mhp']} low {r['outcome']['lowest_hp']} end {r['outcome']['end']} unseen {len(r['unseen_hits'])} summ {len(r['summons'])}")
    print('  landed',dict(landed.most_common(5)),'spells',dict(spell.most_common(4)))
    print('  pure-interval dmg/msg',{n:(dmg[n],pn[n],round(dmg[n]/pn[n],1)) for n in dmg if pn[n]>=2})
    print('  mons_t0',[(m['name'],m['dist']) for m in r['monsters_t0']][:8])
    print('  kills',collections.Counter(k['name'] for k in r['kills']).most_common(8))
    print('  actions',collections.Counter(a['what'] for a in r['actions']))
