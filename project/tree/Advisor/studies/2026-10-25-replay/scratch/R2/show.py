import json,sys,re,collections
from common import *
for i in IDX:
    o=json.load(open(f'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays/ep{i}.json'))
    t0=o['t0']
    print('=====',i,o['mission'],o['depth_ft'],'t0',hms(t0),'trig',hms(o['t_trigger']),'end',hms(o['t_end']),'dur',round(o['t_end']-t0))
    print(' rule:',o['t0_rule']);print(' player',o['player']['pos'],o['player']['hp'],o['player']['mhp'],o['player']['clvl'],o['player']['ac'],[k for k,v in o['player']['status'].items() if v])
    print(' inv',o['inventory'],o['inventory_source']);print(' notes',o['notes'][:400])
    print(' mons0',[(m['name'],m['dist']) for m in o['monsters_t0']])
    print(' arr',collections.Counter(a['name'] for a in o['arrivals']))
    c=collections.Counter()
    for h in o['hostile_msgs']:
        m=re.match(r"^(?:The )?(.*?) (hits|misses|bites|claws|stings|touches|gazes|breathes|casts|fires|crushes|butts|spits|kicks|drains|mumbles|summons|magically|points|wails|makes|shrieks|concentrates|creates|engulfs|crawls|releases)",h['text'])
        c[(m.group(1) if m else h['text'][:30],m.group(2) if m else '')]+=1
    print(' host',sorted(c.items(),key=lambda x:-x[1])[:14])
    print(' unseen',[(hms(u['t']),u['text']) for u in o['unseen_hits'][:6]],len(o['unseen_hits']))
    print(' summ',[(hms(u['t']),u['text']) for u in o['summons']])
    print(' status',[(hms(u['t']),u['text']) for u in o['status_msgs']][:14])
    print(' kills',collections.Counter(k['name'] for k in o['kills']),'melee',len(o['melee_by_us']))
    for a in o['actions']:
        if a['what'] in('walk','run'):continue
        print('   ',hms(a['t']),a['what'],a['cmd'],'eff',a['t_effect'] and round(a['t_effect']-a['t'],1),(a['why'] or '')[:70],a['src'])
    print(' walks',sum(1 for a in o['actions'] if a['what']=='walk'),'melee-acts',sum(1 for a in o['actions'] if a['what']=='melee'))
    print(' outcome',o['outcome'])
    print(' tf',o['time_factor'][:3],len(o['hp_series']))
    print('\n'.join(o['map_window'][17:24]) if o['map_window'] else 'NO MAP')
