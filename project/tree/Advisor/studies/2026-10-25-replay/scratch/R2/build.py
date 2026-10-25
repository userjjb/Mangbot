import pickle,re,json,os,datetime,collections,bisect
from common import *
dec,ev,st=pickle.load(open('idx.pkl','rb'))
stat=pickle.load(open('status.pkl','rb'))
dec.sort(key=lambda d:d['t']);ev.sort(key=lambda d:d['epoch'])
E=load_eps()
OUT='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays/'
LV=RUN+'levels/'
def cheb(a,b):return max(abs(a[0]-b[0]),abs(a[1]-b[1]))
MSG=[d for d in ev if d['ev']=='message']
POS=[d for d in ev if d['ev']=='pos']
ACK=[d for d in ev if d['ev']=='ack']
LEVEL=[d for d in ev if d['ev']=='level']
OWNMELEE=re.compile(r'^(You (hit|miss|smite|bash|slash|pierce|bite|punch|kick|claw|crush|butt|strike|whip|slice|maul|cleave|stab|thrust|pound|batter|shoot|throw|fire|mangle|stun|spear) |It was an? \w+ hit)')
KILL=re.compile(r'^You have (slain|destroyed|killed) (.*?)\.$')
HOSTV=r'(hits|misses|bites|claws|stings|touches|gazes|fires|breathes|casts|mumbles|summons|points|wails|makes|drains|crushes|butts|spits|engulfs|shrieks|concentrates|creates|magically|squeezes|crawls on|kicks|insults|begs|grunts|moans|howls|screams|snarls|tries|shoots|throws|crawl|spores|releases|disenchants|burns|grabs|stares|lashes|trips|slimes|hisses)'
EXCL=re.compile(r'(flees|dies\b|is destroyed|blinks away|teleports away|is a wall|heroism wears|The air about|wakes up|fall(s)? asleep|disappears|is unharmed|resists|shrugs off|grunts with pain|screams in pain|looks healthier|recovers)')
STATUS=re.compile(r'^(You are (blind|confused|poisoned|terrified|afraid|paralyzed|no longer|too afraid|stunned|knocked out|slowed|hasted|bleeding|getting)|You can see again|You can move again|You feel (less confused|bolder|yourself (moving|speed|slow)|like a (hero|killing)|very (weak|clumsy|stupid|naive|sickly|ugly|stunned)|less (berserk|stunned|afraid)|your muscles)|You resist the effects|You refuse to be|You stand your ground|You have (gorged|become)|You disbelieve|The heroism|You feel the need)')
SUMM=re.compile(r'(summons|appear nearby|You hear many things|magically summons|a sudden stirring)')
def hostile(tx):
    if tx.startswith(('You hear many','You feel a sudden')): return False
    if re.match(r'^You are (hit by|enveloped|covered|drenched|struck|blasted|surrounded|engulfed|burned|frozen|shocked)',tx):return True
    if tx.startswith('You') or OWNMELEE.match(tx):return False
    if EXCL.search(tx):return False
    if re.match(r'^(It|Something) ',tx):return True
    return bool(re.search(r' you\b|your ',tx) or re.search(r'\b'+HOSTV+r'\b',tx))
def unseen(tx): return bool(re.match(r'^(It|Something) (?!was an? )',tx) or 'hit by something' in tx)
ITEMS=[('ccw',r'Potions? of Cure Critical'),('csw',r'Potions? of Cure Serious'),('clw',r'Potions? of Cure Light'),('phase',r'Scrolls? of Phase Door'),
 ('tele',r'Scrolls? of Teleportation'),('staff_tele',r'Staff of Teleportation'),('wor',r'Scrolls? of Word of Recall'),('speed',r'Potions? of Speed'),
 ('berserk',r'Potions? of Berserk'),('hero',r'Potions? of Heroism'),('boldness',r'Potions? of Boldness'),('magic_mapping',r'Scrolls? of Magic Mapping'),
 ('door_stair_rod',r'Rod of Door/Stair')]
def what_of_name(nm,verb=None):
    for k,r in ITEMS:
        if re.search(r,nm):return k
    return None
def count_of(nm):
    m=re.match(r'^(\d+) ',nm)
    if m:return int(m.group(1))
    m=re.search(r'\((\d+) charges\)',nm)
    if m and 'Staff' in nm: return int(m.group(1))
    return 1
def inv_counts(items):
    c={k:0 for k,_ in ITEMS}
    for it in items:
        k=what_of_name(it['name'])
        if k: c[k]+=count_of(it['name'])
    return c
stk=[s['epoch'] for s in st]
def snap(t):
    i=bisect.bisect_right(stk,t)-1
    return st[i] if i>=0 else None
def last(lst,key,t):
    ks=[key(x) for x in lst]
    i=bisect.bisect_right(ks,t)-1
    return lst[i] if i>=0 else None
HP=[(d['t'],d['hp'][0],d['hp'][1]) for d in dec if isinstance(d.get('hp'),list) and len(d['hp'])>1 and d['hp'][1]>=20]
MONS=[d for d in dec if d['kind']=='mons']
def parse_hdr(f):
    m=re.match(r'# (\d+) ft, (\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) - (\d\d:\d\d:\d\d)',open(LV+f).readline())
    if not m:return None
    d=m.group(2)
    a=datetime.datetime.strptime(d+' '+m.group(3),'%Y-%m-%d %H:%M:%S').replace(tzinfo=tz).timestamp()
    b=datetime.datetime.strptime(d+' '+m.group(4),'%Y-%m-%d %H:%M:%S').replace(tzinfo=tz).timestamp()
    return int(m.group(1)),a,b
HDR={f:parse_hdr(f) for f in sorted(os.listdir(LV)) if f.endswith('.txt')}
def level_file(t0,ft):
    c=[(h[1],f) for f,h in HDR.items() if h and h[0]==ft and h[1]-5<=t0<=h[2]+20]
    return max(c)[1] if c else None
def mapwin(f,pos):
    rows=open(LV+f).read().split('\n')[1:]
    y0,x0=pos;out=[]
    for y in range(y0-20,y0+21):
        s=rows[y] if 0<=y<len(rows) else ''
        line=''.join(s[x] if 0<=x<len(s) else ' ' for x in range(x0-20,x0+21))
        out.append(line)
    return out,(rows[y0][x0] if 0<=y0<len(rows) and 0<=x0<len(rows[y0]) else None)
def r1(x):return round(x,3)
def build(idx):
    e=E[idx];row=e['row']
    s=e['trig']
    # refine trigger
    cand=[d['t'] for d in dec if s<=d['t']<s+1.0 and d['kind'] in('act','escape','attention')]
    trig=min(cand) if cand else s
    tend=e['end']
    # hostile messages
    hostm=[(m['epoch'],m['text']) for m in MSG if hostile(m['text'])]
    # t0
    hp_before=[x for x in HP if trig-60<=x[0]<=trig]
    A=None
    for t,h,m in hp_before:
        if h>=0.9*m:A=t
    B=None
    for d in MONS:
        if trig-60<=d['t']<=trig:
            p=d['pos']
            if not any(cheb(p,m[:2])<=2 for m in d['monsters']):B=d['t']
    cands=[x for x in(A,B) if x is not None]
    rule=''
    if cands:
        t0=max(cands);rule=f"latest of last HP>=90% max (A={hms(A) if A else None}) and last mons record with none within 2 squares (B={hms(B) if B else None}) within 60 s before trigger"
    else:
        t0=trig-60;rule='neither A nor B within 60 s before trigger; used trigger-60'
    fh=[t for t,_ in hostm if t0<=t<=trig+5]
    if not fh or fh[0]-t0>5:
        # move t0 to first hostile message in [t0,trig+5] else trigger
        if fh: t0=fh[0]-0.001;rule+='; moved to first hostile message ('+hms(fh[0])+')'
        else: t0=trig;rule+='; no hostile message after t0, used trigger'
    t0=min(t0,trig)
    # player
    pe=last(POS,lambda x:x['epoch'],t0)
    pd=last([d for d in dec if d.get('pos')],lambda x:x['t'],t0)
    pos=[pe['y'],pe['x']] if pe else (pd['pos'] if pd else None)
    h0=last(HP,lambda x:x[0],t0)
    sts=last(stat,lambda x:x[0],t0)
    # statuses from messages
    S=dict(slow=False,fast=False,hero=False,berserk=False,blind=False,confused=False,afraid=False,poisoned=False,paralyzed=False)
    TOG=[('blind',r'You are blind',r'You can see again'),('confused',r'You are confused',r'You feel less confused'),
         ('poisoned',r'You are poisoned',r'You are no longer poisoned'),('afraid',r'You are (terrified|afraid)',r'You feel bolder now'),
         ('slow',r'You feel yourself moving slower',r'You feel yourself speed up'),('fast',r'You feel yourself moving faster',r'You feel yourself slow down'),
         ('hero',r'You feel like a hero',r'The heroism wears off'),('berserk',r'You feel like a killing machine',r'You feel less berserk|no longer berserk'),
         ('paralyzed',r'You are paralyzed',r'You can move again')]
    for m in MSG:
        if m['epoch']<=t0:
            for k,on,off in TOG:
                if re.search(on,m['text']):S[k]=True
                elif re.search(off,m['text']):S[k]=False
    # level boundary: reset statuses if level change? keep
    pl=dict(pos=pos,hp=h0[1] if h0 else None,mhp=h0[2] if h0 else None,clvl=(sts[3][0] if sts and t0-sts[0]<120 else None),
            ac=(sts[4][0] if sts and t0-sts[0]<120 else None),status=S,free_action=None,see_invisible=None)
    # monsters at t0
    m0=last(MONS,lambda x:x['t'],t0)
    mons0=[]
    if m0 and t0-m0['t']<=30:
        for y,x,n in m0['monsters']:mons0.append(dict(name=n,y=y,x=x,dist=cheb(pos,(y,x)) if pos else None))
    mons_series=[[r1(d['t']),[list(m) for m in d['monsters']]] for d in MONS if t0-10<=d['t']<=tend]
    # arrivals
    seen=collections.defaultdict(int);seenpos=collections.defaultdict(list)
    for d in MONS:
        if t0-10<=d['t']<=t0:
            c=collections.Counter(m[2] for m in d['monsters'])
            for n,k in c.items():seen[n]=max(seen[n],k)
            for y,x,n in d['monsters']:seenpos[n].append((y,x))
    arr=[]
    for d in MONS:
        if t0<d['t']<=tend:
            c=collections.Counter(m[2] for m in d['monsters'])
            for n,k in c.items():
                if k>seen[n]:
                    ms=[m for m in d['monsters'] if m[2]==n]
                    best=max(ms,key=lambda m:min([cheb((m[0],m[1]),p) for p in seenpos[n]] or [99]))
                    for _ in range(k-seen[n]):
                        arr.append(dict(t=r1(d['t']),name=n,y=best[0],x=best[1],dist=cheb(d['pos'],best[:2])))
                    seen[n]=k
            for y,x,n in d['monsters']:seenpos[n].append((y,x))
    # messages
    W=[m for m in MSG if t0<=m['epoch']<=tend]
    hostile_msgs=[dict(t=r1(m['epoch']),text=m['text']) for m in W if hostile(m['text'])]
    unseen_hits=[x for x in hostile_msgs if unseen(x['text'])]
    summons=[dict(t=x['t'],text=x['text']) for x in [dict(t=r1(m['epoch']),text=m['text']) for m in W] if SUMM.search(x['text']) and not x['text'].startswith('You are')]
    status_msgs=[dict(t=r1(m['epoch']),text=m['text']) for m in W if STATUS.match(m['text'])]
    melee=[dict(t=r1(m['epoch']),text=m['text']) for m in W if OWNMELEE.match(m['text'])]
    kills=[dict(t=r1(m['epoch']),name=re.sub(r'^the ','',KILL.match(m['text']).group(2))) for m in W if KILL.match(m['text'])]
    # inventory
    sn=snap(t0);inv=None;invsrc=None;notes=[]
    if sn and t0-sn['epoch']<=600:
        inv=inv_counts(sn['items']);invsrc=f"state.jsonl inven at {hms(sn['epoch'])} (game clock; {t0-sn['epoch']:+.0f} s from t0, approx)"
        invraw=[it['name'] for it in sn['items']]
    else:
        invraw=None
    # actions
    snaps_all=st
    def slot_name(t,item):
        s2=snap(t)
        if not s2:return None
        for it in s2['items']:
            if it['item']==item and not it.get('equip'):return it['name']
    acts=[]
    for d in dec:
        if d['kind']=='act' and t0-15<=d['t']<=tend:
            cmd=d['cmd'];why=d.get('why','')
            w='other'
            m=re.match(r'custom ([rqu]) item=(\d+)',cmd)
            if m:
                k=None
                src_txt=why
                if why.startswith('agent:'):
                    mm=re.search(r"\['(.*?)'\]",why);arg=mm.group(1) if mm else ''
                    src_txt=arg
                    if len(arg)==1 and arg.isalpha():
                        # letter -> slot via the snapshot at t0 (before the fight shifts the pack)
                        s2=snap(t0);nm=None
                        if s2:
                            for it in s2['items']:
                                if it['item']==ord(arg)-97 and not it.get('equip'):nm=it['name']
                        if nm:k=what_of_name(nm);why=why+' [letter '+arg+' = slot '+str(ord(arg)-97)+' = '+nm+' at t0 snapshot; may have shifted]'
                if k is None:
                    tl=src_txt.lower()
                    for kk,pat in (('wor','word of recall'),('tele','teleportation'),('phase','phase'),('ccw','cure critical'),('csw','cure serious'),('clw','cure light'),
                                   ('speed','speed'),('hero','heroism'),('berserk','berserk'),('boldness','boldness')):
                        if pat in tl:k=kk;break
                if m.group(1)=='u' and k=='tele':k='staff_tele'
                w=k or 'other'
            elif cmd=='rest':w='rest'
            elif cmd.startswith(('walk','pathfind')):w='walk'
            elif cmd.startswith('custom .'):w='run'
            elif cmd.startswith('stairs') or cmd.startswith('custom <') or cmd.startswith('custom >'):w='stairs'
            acts.append(dict(t=r1(d['t']),cmd=cmd,what=w,why=why,src='navigator' if why.startswith('agent:') else 'pilot',t_effect=None))
    actt=[a['t'] for a in acts]
    # walk/run acks not in acts
    pk=[(p['epoch'],(p['y'],p['x'])) for p in POS]
    lastack=None
    for a in ACK:
        t=a['epoch']
        if not (t0-15<=t<=tend):continue
        c=a['cmd']
        if not c.startswith(('walk','custom . ','pathfind')):continue
        if any(abs(t-x)<0.02 for x in actt):continue
        if lastack and c==lastack[0] and abs(t-lastack[1])<0.02:continue
        lastack=(c,t)
        acts.append(dict(t=r1(t),cmd=c,what='run' if c.startswith('custom .') else 'walk',why=None,src='pilot',t_effect=None))
    acts.sort(key=lambda a:a['t'])
    # effects
    used=set()
    ps=[(p['epoch'],(p['y'],p['x'])) for p in POS]
    def prevpos(t):
        i=bisect.bisect_left([x[0] for x in ps],t)-1
        return ps[i][1] if i>=0 else None
    msgs_all=[(m['epoch'],m['text']) for m in MSG]
    KW={'ccw':r'You have (\d+|no more|an?) Potions? of Cure Critical','csw':r'You have (\d+|no more|an?) Potions? of Cure Serious','clw':r'You have (\d+|no more|an?) Potions? of Cure Light',
        'speed':r'(You have (\d+|no more|an?) Potions? of Speed|You feel yourself (moving faster|speed up))','berserk':r'You have (\d+|no more|an?) Potions? of Berserk','hero':r'(You feel like a hero|You have (\d+|no more|an?) Potions? of Heroism)','boldness':r'You have (\d+|no more|an?) Potions? of Boldness',
        'phase':r'You have (\d+|no more|an?) Scrolls? of Phase','tele':r'You have (\d+|no more|an?) Scrolls? of Teleportation','wor':r'The air about you becomes charged','staff_tele':r'(You have \d+ charges? remaining|Staff of Teleportation)'}
    for a in acts:
        t=a['t'];w=a['what']
        te=None
        if w in('phase','tele','staff_tele'):
            p0=prevpos(t)
            for tt,pp in ps:
                if tt>t and tt<=t+40 and p0 and cheb(pp,p0)>=(2 if w=='phase' else 4) and tt not in used:
                    te=tt;used.add(tt);break
        elif w in KW:
            for tt,tx in msgs_all:
                if tt>t and tt<=t+40 and re.search(KW[w],tx) and tt not in used:
                    te=tt;used.add(tt);break
        elif w=='walk' or w=='run':
            p0=prevpos(t)
            for tt,pp in ps:
                if tt>t and tt<=t+5 and tt not in used and pp!=p0:
                    te=tt;used.add(tt);break
            if te is None:
                for tt,tx in msgs_all:
                    if t<tt<=t+2 and OWNMELEE.match(tx) and tt not in used:
                        te=tt;used.add(tt);a['what']='melee';break
        a['t_effect']=r1(te) if te else None
    acts=[a for a in acts if a['t']>=t0 or (a['t_effect'] and a['t_effect']>=t0)]
    # inventory message correction
    cons=collections.Counter()
    firstmsg={}
    for tt,tx in msgs_all:
        if t0<=tt<=tend:
            for k,r in KW.items():
                if k in('wor','staff_tele'):continue
                m=re.search(r,tx)
                if m:
                    mc=re.match(r'You have (\d+|no more|an?) ',tx)
                    if not mc: continue
                    cons[k]+=1
                    if k not in firstmsg:
                        g=mc.group(1)
                        n=0 if g=='no more' else (1 if g in('a','an') else int(g));firstmsg[k]=n+1
    if inv is not None:
        for k,v in firstmsg.items():
            if inv.get(k)!=v:
                notes.append(f"inventory {k}: snapshot {inv.get(k)} vs message-derived {v} at t0 (messages ignore items burnt by fire/other loss); kept snapshot")
    else:
        inv={k:None for k,_ in ITEMS}
        for k,v in firstmsg.items():inv[k]=v
        invsrc='"You have N ..." quaff/read messages in the episode (count at t0 derived as N after first use + 1); other items unknown (no state.jsonl inven snapshot before this time)'
        if not firstmsg: inv=None;invsrc=None
    # series
    hp_series=[[r1(t),h,m] for t,h,m in HP if t0-30<=t<=tend]
    pos_series=[];lp=None
    for p in POS:
        if t0<=p['epoch']<=tend:
            q=(p['y'],p['x'])
            if q!=lp:pos_series.append([r1(p['epoch']),p['y'],p['x']]);lp=q
    tf=[[r1(d['t']),d['factor']] for d in dec if d['kind']=='time_factor' and t0-60<=d['t']<=tend]
    depth_ft=int(row['depth_ft'])
    lf=level_file(t0,depth_ft)
    mw=None;chk=None
    if lf and pos:
        mw,chk=mapwin(lf,pos)
        if chk is None or chk in ' #':notes.append(f"map check: char at player pos in dump is {chk!r} (dump may predate/lag)")
    # outcome
    hs=[x for x in HP if t0<=x[0]<=tend]
    low=min(hs,key=lambda x:x[1]) if hs else None
    yank=[m for m in MSG if t0<=m['epoch']<=tend+15 and 'yanked' in m['text']]
    lvl=[l for l in LEVEL if t0<=l['epoch']<=tend+15]
    lastacts=[a['what'] for a in acts if a['what'] not in('walk','run','melee','rest','other')]
    if yank:endk='recall'
    elif lvl:endk='stairs' if any(a['what']=='stairs' for a in acts) else 'left'
    elif lastacts and lastacts[-1] in('tele','staff_tele'):endk='teleport'
    else:endk='other'
    cons_acts=collections.Counter(a['what'] for a in acts if a['what'] not in('walk','run','melee','rest','other','stairs'))
    outcome=dict(lowest_hp=low[1] if low else None,t_lowest=r1(low[0]) if low else None,end=endk,consumables=dict(cons_acts),consumables_by_messages=dict(cons),levels_seen=[[r1(l['epoch']),l['depth']] for l in lvl])
    # speed check from state
    if sts: notes.append(f"state.jsonl status nearest before t0 ({t0-sts[0]:.0f} s, game clock): level {sts[3]}, armor {sts[4]}, speed {sts[5]}, afraid {sts[6]}, blind {sts[7]}, confused {sts[8]}, poisoned {sts[9]}")
    out=dict(idx=idx,mission=row['mission'],depth_ft=depth_ft,level_dump=lf,t0=r1(t0),t_trigger=r1(trig),t_end=r1(tend),t0_rule=rule,
        player=pl,inventory=inv,inventory_source=invsrc,inventory_raw=invraw,monsters_t0=mons0,arrivals=arr,summons=summons,unseen_hits=unseen_hits,
        hostile_msgs=hostile_msgs,status_msgs=status_msgs,actions=acts,melee_by_us=melee,kills=kills,hp_series=hp_series,pos_series=pos_series,
        time_factor=tf,mons_series=mons_series,map_window=mw,outcome=outcome,notes='; '.join(notes))
    json.dump(out,open(OUT+f'ep{idx}.json','w'),indent=0)
    return out
if __name__=='__main__':
    for i in IDX:
        o=build(i)
        print(i,o['mission'],hms(o['t0']),hms(o['t_trigger']),hms(o['t_end']),'dump',o['level_dump'],'pos',o['player']['pos'],'hp',o['player']['hp'],
              'mons0',len(o['monsters_t0']),'arr',len(o['arrivals']),'act',len(o['actions']),'unseen',len(o['unseen_hits']),'host',len(o['hostile_msgs']),'inv',o['inventory_source'] and o['inventory_source'][:40],'|',o['notes'][:200])
