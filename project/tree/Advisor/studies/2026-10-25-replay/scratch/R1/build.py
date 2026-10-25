import sys,pickle,re,json,os,datetime,collections,statistics
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1')
from common import *
E='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1/'
OUT='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays/'
recs=pickle.load(open(E+'recs.pkl','rb')); wins=pickle.load(open('wins.pkl','rb')); evw=pickle.load(open('evw.pkl','rb')); evm=pickle.load(open('evmsg.pkl','rb'))
out=pickle.load(open(E+'out.pkl','rb'))
recs.sort(key=lambda d:d['t'])
R=lambda x:round(x,3)
def cheb(a,b):return max(abs(a[0]-b[0]),abs(a[1]-b[1]))
HOST_V=r'(hits|bites|claws|crushes|touches|stings|kicks|butts|crawls on|engulfs|gazes|spits|misses|drools|begs|insults|moons|gives you|dances|makes obscene|fires|casts|breathes|mumbles|points at you|commands you|drains|gestures|creates|magically summons|summons|tramples|grunts|releases|stole|steals|squeezes|wails|grabs|wraps)'
def hostile(t):
    if t.startswith(('You ','Your ','In your','There ','That ')) : return False
    if re.search(r'(flees in terror|turns to fight|wakes up|blinks away|teleports away|was slain|dies|is destroyed|It was a|is unharmed|shrugs off)',t) and 'It was a' not in t: return False
    if t.startswith('It was a'): return True
    if re.search(r' (%s)'%HOST_V,t) and re.search(r'(you|your|summons|casts|breathes|fires|mumbles|gestures|creates)',t):return True
    if re.match(r'(\d+ coins were stolen|One of your .* destroyed)',t):return True
    return False
def unseen(t): return bool(re.match(r'(It|Something) ',t)) and hostile(t) and 'was a' not in t
STAT=[r'You are (blind|confused|terrified|paralyzed|poisoned|slowed|stunned|afraid|bleeding|hasted)',r'You can see again',r'You feel (less confused|bolder|like a hero|like a killing machine|less berserk|yourself (moving|speed))',r'You are no longer',r'wears off',r'You can move again',r'You have been (stunned|knocked)',r'drains power from your muscles',r'You (resist the effects|are unaffected|refuse to be frightened|disbelieve)',r'You feel (better|poison)',r'You have been given a graze',r'You are too afraid',r'You are getting hungry|You are no longer hungry|gorged']
def isstat(t): return any(re.search(p,t) for p in STAT)
def itemkey(s):
    s=s.lower()
    if 'phase' in s:return 'phase'
    if 'word of recall' in s or 'word_of_recall' in s:return 'wor'
    if 'staff' in s and 'teleport' in s:return 'staff_tele'
    if 'teleport' in s and 'ring' not in s:return 'tele'
    if 'cure light' in s or 'cure_light' in s:return 'clw'
    if 'cure serious' in s or 'cure_serious' in s:return 'csw'
    if 'cure critical' in s or 'cure_critical' in s:return 'ccw'
    if 'speed' in s and 'potion' in s:return 'speed'
    if 'berserk' in s:return 'berserk'
    if 'heroism' in s or 'hero' in s:return 'hero'
    if 'boldness' in s:return 'boldness'
    if 'magic mapping' in s:return 'magic_mapping'
    return None
def whatof(cmd,why):
    c=cmd;w=why
    if c.startswith('custom r'):
        k=itemkey(w); 
        if 'Identify' in w:return 'other'
        return {'phase':'phase','wor':'wor','tele':'tele','staff_tele':'staff_tele'}.get(k,'other')
    if c.startswith('custom q'):
        k=itemkey(w); return k if k in('clw','csw','ccw','speed','berserk','hero','boldness') else 'other'
    if c.startswith('custom u') or c.startswith('custom a'): return 'staff_tele' if 'teleport' in w.lower() else 'other'
    if c in('custom <','custom >'):return 'stairs'
    if c.startswith('rest'):return 'rest'
    if c.startswith('walk'):return 'walk'
    if c.startswith(('run','custom .')):return 'run'
    return 'other'
CONF={'phase':r'(You have .*Scrolls? of Phase Door|no more Scrolls of Phase Door)','wor':r'air about you becomes charged','tele':r'(You have .*Scrolls? of Teleportation|no more Scrolls of Teleportation)',
 'clw':r'You have .*Potions? of Cure Light|no more Potions of Cure Light','csw':r'You have .*Potions? of Cure Serious|no more Potions of Cure Serious','ccw':r'You have .*Potions? of Cure Critical|no more Potions of Cure Critical',
 'speed':r'(You have .*Potions? of Speed|no more Potions of Speed|You feel yourself moving faster)','hero':r'(You have .*Potions? of Heroism|no more Potions of Heroism|You feel like a hero)','boldness':r'(Potions? of Boldness|You feel bolder)','berserk':r'(Berserk|killing machine)'}
def uniq_name(t):
    return t
def mk(i):
    w=wins[i];o=out[i];trig=w['trig'];end=w['end']
    # ---- decisions window
    hps=[(d['t'],d['hp'][0],d['hp'][1]) for d in recs if isinstance(d.get('hp'),list) and len(d['hp'])>1 and d['hp'][1]>=20 and trig-200<=d['t']<=end+5]
    mons_all=[d for d in recs if d['kind']=='mons' and trig-200<=d['t']<=end+5]
    # t0 rule
    hp_trig=[x for x in hps if x[0]<=trig][-1]
    tA=None
    for t,h,m in reversed([x for x in hps if x[0]<=trig]):
        if h>=0.9*m: tA=t;break
    tB=None
    for d in reversed([d for d in mons_all if d['t']<=trig]):
        if not d['monsters'] or min(cheb(d['pos'],(m[0],m[1])) for m in d['monsters'])>2: tB=d['t'];break
    cands=[x for x in (tA,tB) if x is not None]
    t0=max(cands) if cands else trig-60
    rule="walk back from trigger: last HP>=90%% of max (%s) vs last mons record with nothing within 2 squares (%s); the later of the two"%(hms(tA) if tA else 'none',hms(tB) if tB else 'none')
    if t0<trig-60: t0=trig-60;rule+="; capped to 60 s before the trigger"
    if t0>trig: t0=trig
    tp=min(x for x in (tA,tB,t0) if x is not None); tp=max(min(tp,t0),trig-60)
    # player at t0
    last=[d for d in recs if d['t']<=t0 and d.get('pos') and isinstance(d.get('hp'),list) and d['hp'][1]>=20][-1]
    pos=list(last['pos']);hp,mhp=last['hp'][:2]
    aud=[d for d in recs if d['kind']=='audit_check' and d['t']<=t0 and d.get('clvl')]
    clvl=aud[-1]['clvl'] if aud else None
    acraw=aud[-1].get('ac') if aud else None
    # messages
    M=sorted([v for v in evm if v['ev']=='message'],key=lambda v:v['epoch'])
    Mw=[v for v in M if tp<=v['epoch']<=end+0.0]
    # status before t0
    stat={'slow':False,'fast':False,'hero':False,'berserk':False,'blind':False,'confused':False,'afraid':False,'poisoned':False,'paralyzed':False}
    ON={'blind':r'You are blind','confused':r'You are confused','afraid':r'You are terrified|You are too afraid','poisoned':r'You are poisoned','paralyzed':r'You are paralyzed','hero':r'feel like a hero','berserk':r'killing machine','slow':r'You feel yourself moving slower','fast':r'You feel yourself moving faster'}
    OFF={'blind':r'You can see again','confused':r'less confused','afraid':r'feel bolder','poisoned':r'no longer poisoned','paralyzed':r'You can move again','hero':r'heroism wears off','berserk':r'less berserk','slow':r'speed up|slowness wears off','fast':r'speed wears off|feel yourself slow down'}
    for v in M:
        if v['epoch']>t0 or v['epoch']<t0-1800:continue
        for k in stat:
            if re.search(ON[k],v['text']):stat[k]=True
            if re.search(OFF[k],v['text']):stat[k]=False
    fl=[v for v in evm if v['ev']=='flags' and v['epoch']<=t0]
    fa=si=None
    if fl:
        f=fl[-1]['flags'];fa=bool(f.get('free_act'));si=bool(f.get('see_invis'))
    # inventory counts from "You have N X" messages
    inv={}
    obs=collections.defaultdict(list)
    for v in M:
        t=v['text']
        m=re.match(r'You have (no more|an?|\d+) ((?:Scrolls?|Potions?|Staffs?|Staves) of [^{(\.]+?)\s*(\{.*\})?(\s*\(\w\))?\.?$',t)
        if not m:continue
        k=itemkey(m.group(2))
        if not k:continue
        n=0 if m.group(1)=='no more' else 1 if m.group(1) in('a','an') else int(m.group(1))
        obs[k].append((v['epoch'],n))
    src_notes=[]
    for k,l in obs.items():
        # sum duplicates (discounted stacks are separate stacks): keep per message last value per stack tag -> treat by taking nearest obs
        before=[x for x in l if x[0]<=t0]
        if before and t0-before[-1][0]<1700:
            inv[k]=before[-1][1]
        else:
            after=[x for x in l if x[0]>t0]
            if after:
                inv[k]=after[0][1]+1
    inventory={k:inv.get(k) for k in ['ccw','csw','clw','phase','tele','staff_tele','wor','speed','berserk','hero','boldness','magic_mapping','door_stair_rod']}
    # monsters_t0
    mt=[d for d in mons_all if d['t']<=t0]
    mt0=[];age=None
    if mt:
        d=mt[-1];age=R(t0-d['t'])
        mt0=[{'name':m[2],'y':m[0],'x':m[1],'dist':cheb(d['pos'],(m[0],m[1]))} for m in d['monsters']]
    # arrivals
    seen=collections.Counter(m['name'] for m in mt0)
    prev_pos=collections.defaultdict(list)
    for m in mt0:prev_pos[m['name']].append((m['y'],m['x']))
    arrivals=[]
    ms=[d for d in mons_all if t0-10<=d['t']<=end+0.0]
    lastt=t0
    for d in [d for d in mons_all if t0<d['t']<=end]:
        # kills between lastt and d.t reduce seen
        for v in Mw:
            if lastt<v['epoch']<=d['t']:
                mm=re.match(r'You have (?:slain|destroyed) (?:the )?(.+)\.$',v['text'])
                if mm and seen[mm.group(1)]>0: seen[mm.group(1)]-=1
        lastt=d['t']
        cnt=collections.Counter(m[2] for m in d['monsters'])
        for nm,c in cnt.items():
            while seen[nm]<c:
                cands=[m for m in d['monsters'] if m[2]==nm]
                best=max(cands,key=lambda m:min([cheb((m[0],m[1]),p) for p in prev_pos[nm]] or [99]))
                arrivals.append({'t':R(d['t']),'name':nm,'y':best[0],'x':best[1],'dist':cheb(d['pos'],(best[0],best[1]))})
                prev_pos[nm].append((best[0],best[1]));seen[nm]+=1
        for m in d['monsters']:prev_pos[m[2]]=[(m[0],m[1])] if False else prev_pos[m[2]]
    # messages
    hostile_msgs=[{'t':R(v['epoch']),'text':v['text']} for v in Mw if hostile(v['text'])]
    unseen_hits=[x for x in hostile_msgs if unseen(x['text'])]
    summons=[{'t':R(v['epoch']),'text':v['text']} for v in Mw if re.search(r'summons|appear nearby|You hear many things',v['text'])]
    status_msgs=[{'t':R(v['epoch']),'text':v['text']} for v in Mw if isstat(v['text'])]
    melee=[{'t':R(v['epoch']),'text':v['text']} for v in Mw if re.match(r'You (hit|miss|smite|bash|punch|kick|slash|bite|claw|strike|pierce) (the |it)',v['text']) or re.match(r'You are too afraid to attack',v['text'])]
    kills=[]
    for v in Mw:
        mm=re.match(r'You have (?:slain|destroyed) (?:the )?(.+)\.$',v['text'])
        if mm:kills.append({'t':R(v['epoch']),'name':mm.group(1)})
        mm=re.match(r'(.+) was slain by',v['text'])
        if mm:kills.append({'t':R(v['epoch']),'name':mm.group(1)})
    # actions
    acts=[];lvl=[v for v in evw if v['ev']=='level']
    posev=sorted([v for v in evw if v['ev']=='pos'],key=lambda v:v['epoch'])
    acks=[v for v in evw if v['ev']=='ack']
    raw=[d for d in recs if d['kind']=='act' and tp<=d['t']<=end+3]
    for d in raw:
        acts.append({'t':R(d['t']),'cmd':d['cmd'],'what':whatof(d['cmd'],d['why']),'why':d['why'],'src':'navigator' if d['why'].startswith('agent:') else 'pilot','t_effect':None})
    # nav_cmd strategic
    for d in recs:
        if d['kind']=='nav_cmd' and tp<=d['t']<=end+3 and d['cmd'] in('goal','order','monster','hunt'):
            acts.append({'t':R(d['t']),'cmd':'nav '+d['cmd']+' '+' '.join(map(str,d['args'])),'what':'other','why':'navigator order','src':'navigator','t_effect':None})
    # acks not matched to act: walk/run
    actt=[(a['t'],a['cmd']) for a in acts if a['cmd'].startswith('custom') or a['cmd'].startswith('rest') or a['cmd'].startswith('eat')]
    goalrec=[d for d in recs if d['kind']=='goal' and d['t']<=end]
    seenack=set()
    for v in acks:
        kk=(round(v['epoch'],2),v['cmd'])
        if kk in seenack:continue
        seenack.add(kk)
        if any(abs(a['t']-v['epoch'])<0.3 and a['cmd']==v['cmd'] and a['src']=='pilot' and a['why'] and not str(a['why']).startswith('goal:') for a in acts):continue
        if not (tp<=v['epoch']<=end+3):continue
        c=v['cmd']
        if c.startswith('walk') or c.startswith('custom . '):
            gl=[g for g in goalrec if g['t']<=v['epoch']]
            acts.append({'t':R(v['epoch']),'cmd':c,'what':'walk' if c.startswith('walk') else 'run','why':('goal: '+gl[-1]['goal']) if gl else None,'src':'pilot','t_effect':None})
    acts.sort(key=lambda a:a['t'])
    # effects
    msgs=[(v['epoch'],v['text']) for v in M]
    used=set()
    for kind in CONF:
        pass
    pos_t=[v['epoch'] for v in posev]
    for a in acts:
        k=a['what'];te=None
        if k in CONF:
            for j,(t,tx) in enumerate(msgs):
                if t>=a['t']-0.01 and t<=a['t']+60 and j not in used and re.search(CONF[k],tx):
                    te=t;used.add(j);break
            # require not skipping a later act of the same kind? greedy
        elif k=='stairs':
            for v in lvl:
                if a['t']-0.01<=v['epoch']<=a['t']+30:te=v['epoch'];break
        elif k in('walk','run'):
            for v in posev:
                if a['t']-0.01<v['epoch']<=a['t']+3:te=v['epoch'];break
            if k=='walk':
                for t,tx in msgs:
                    if a['t']-0.01<t<=a['t']+1.5 and re.match(r'You (hit|miss)',tx) and (te is None or t<te):
                        te=t;a['what']='melee';break
        a['t_effect']=R(te) if te else None
    # series
    hp_series=[[R(t),h,m] for t,h,m in hps if t0-30<=t<=end]
    pos_series=[[R(v['epoch']),v['y'],v['x']] for v in posev if t0-5<=v['epoch']<=end]
    tf=[[R(d['t']),d['factor']] for d in recs if d['kind']=='time_factor' and t0-60<=d['t']<=end]
    mons_series=[[R(d['t']),[[m[0],m[1],m[2]] for m in d['monsters']]] for d in mons_all if t0-10<=d['t']<=end]
    # level dump
    ft=o['depth_ft'];ld=None
    best=None
    for fn in sorted(os.listdir(RUN+'levels')):
        if not fn.endswith(f'-{ft}ft.txt'):continue
        h=open(RUN+'levels/'+fn).readline()
        m=re.match(r'# (\d+) ft, (\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) - (\d\d:\d\d:\d\d)',h)
        if not m:continue
        a=eps_(m.group(2)+' '+m.group(3));b=eps_(m.group(2)+' '+m.group(4))
        if a-2<=t0<=b+2: ld=fn
    mapw=None
    if ld:
        L=open(RUN+'levels/'+ld).read().split('\n')
        mapw=[]
        for y in range(pos[0]-20,pos[0]+21):
            row=L[y+1] if 0<=y and y+1<len(L) else ''
            mapw.append(''.join((row[x] if 0<=x<len(row) else ' ') for x in range(pos[1]-20,pos[1]+21)))
    # outcome
    inw=[x for x in hps if t0<=x[0]<=end]
    low=min(inw,key=lambda x:x[1]) if inw else None
    yank=any('yanked upwards' in tx for t,tx in msgs if t0<=t<=end+10)
    lvch=[v for v in lvl if t0<v['epoch']<=end+10]
    endk='recall' if yank else ('stairs' if lvch else ('killed all' if o['outcome'].startswith(('killed','fought','phased')) else 'other'))
    cons=collections.Counter()
    for a in acts:
        if a['what'] in('clw','csw','ccw','phase','tele','wor','speed','hero','berserk','boldness','staff_tele'):
            cons[a['what']]+=1
    consconf=collections.Counter()
    for a in acts:
        if a['what'] in CONF and a['t_effect']:consconf[a['what']]+=1
    notes=f"t_pre = earlier of the two t0 candidates (clamped to 60 s before trigger): hostile_msgs, summons, status_msgs, melee_by_us, kills and actions are listed from t_pre, not t0, so that events just before the rule's t0 (e.g. a summon) are kept. E1 outcome: {o['outcome']}. E1 verdict {o['verdict']}. t0 HP {hp}/{mhp} (trigger HP {hp_trig[1]}/{hp_trig[2]}). monsters_t0 from last mons record {age}s before t0. dist = Chebyshev from player pos in that record. 'arrivals' heuristic: a monster of a name is new when the count of that name in a mons record exceeds the max seen since t0 (minus kills). ac raw (decisions audit_check ind 'armor', meaning of 3 numbers unverified): {acraw}. status false = no on-message in 30 min before t0 (flags/status not logged in decisions). Inventory = last 'You have N X' use/pickup message before t0 (else first after t0 +1); discounted (N% off in name) stacks appear as separate messages so counts may cover only one stack; null = never mentioned in 30 min window. Level dump is the end-of-level map, may show more than known at t0. Acts in window include resends; consumables_issued counts act records, confirmed counts matched confirmation messages."
    rep={'idx':i,'mission':o['mission'],'depth_ft':ft,'level_dump':ld,'t0':R(t0),'t_pre':R(tp),'t_trigger':R(trig),'t_end':R(end),'t0_rule':rule,
     'player':{'pos':pos,'hp':hp,'mhp':mhp,'clvl':clvl,'ac':None,'status':stat,'free_action':fa,'see_invisible':si},
     'inventory':inventory,'inventory_source':"act 'why' strings + 'You have N ...' pack messages (events.jsonl); no inventory snapshots before m24",
     'monsters_t0':mt0,'arrivals':arrivals,'summons':summons,'unseen_hits':unseen_hits,'hostile_msgs':hostile_msgs,'status_msgs':status_msgs,
     'actions':acts,'melee_by_us':melee,'kills':kills,'hp_series':hp_series,'pos_series':pos_series,'time_factor':tf,'mons_series':mons_series,'map_window':mapw,
     'outcome':{'lowest_hp':low[1] if low else None,'t_lowest':R(low[0]) if low else None,'end':endk,'consumables_issued':dict(cons),'consumables_confirmed':dict(consconf)},'notes':notes}
    json.dump(rep,open(OUT+f'ep{i}.json','w'))
    return rep
if __name__=='__main__':
    for i in [0,1,3,4,6,7,8,9,10,11,12,14]:
        r=mk(i)
        print(i,r['mission'],hms(r['t0']),hms(r['t_trigger']),hms(r['t_end']),len(r['monsters_t0']),len(r['arrivals']),len(r['actions']),len(r['unseen_hits']),r['level_dump'],r['inventory'],len(r['time_factor']))
