import pickle,re,collections,datetime,csv,sys,bisect
HP_R='/projectnb/jbrcs/mangband/github/lib/edit/monster.txt'
mon={}
cur=None
for l in open(HP_R):
    l=l.rstrip('\n')
    if l.startswith('N:'):
        p=l.split(':',2); cur=p[2]; 
        if cur not in mon: mon[cur]=None
        first = mon[cur] is None
    elif l.startswith('W:') and cur and mon.get(cur) is None:
        p=l.split(':'); mon[cur]=(int(p[1]),int(p[4]))
low={k.lower():v for k,v in mon.items()}
def fmt(ep): return datetime.datetime.fromtimestamp(ep).strftime('%m-%d %H:%M:%S')
def band(dp):
    if dp is None or dp<0 or dp>25: return 'town/surface'
    if dp==0: return 'town/surface'
    ft=dp*50
    if ft<=250: return '0-250'
    if ft<=500: return '250-500'
    if ft<=750: return '500-750'
    if ft<=1000: return '750-1000'
    return '1000+'
BANDS=['town/surface','0-250','250-500','500-750','750-1000','1000+']
# clvl timelines: list of (epoch_start, clvl)
def ts(s,y=2026): return datetime.datetime.strptime(str(y)+' '+s,'%Y %m-%d %H:%M:%S').timestamp()
CL={'dive03':[(0,11),(ts('09-25 21:11:30'),12),(ts('09-25 21:25:00'),13),(ts('09-25 21:27:08'),14),(ts('09-25 22:38:37'),16),
   (ts('09-25 23:15:18'),17),(ts('09-25 23:15:51'),18),(ts('09-25 23:16:00'),15),(ts('09-26 05:00:31'),16),(ts('09-26 15:37:39'),17),
   (ts('09-26 15:43:00'),16),(ts('09-26 15:45:59'),17),(ts('09-26 16:21:04'),18),(ts('09-26 16:32:14'),19),(ts('09-27 11:54:21'),20),
   (ts('09-27 12:36:18'),21),(ts('09-27 22:17:34'),22)],
 'dive04':[(0,1),(ts('09-28 01:39:01',2026),2),(ts('09-28 01:47:59'),3),(ts('09-28 01:53:58'),4),(ts('09-28 01:59:14'),5),(ts('09-28 02:04:52'),6),
   (ts('09-29 21:44:13'),7),(ts('09-29 21:54:16'),8),(ts('09-29 22:16:58'),9),(ts('09-29 22:23:45'),10),(ts('09-29 22:29:40'),8),
   (ts('10-03 12:24:37'),9),(ts('10-03 12:47:33'),10),(ts('10-07 09:11:57'),11)]}
def clvl(nick,ep):
    L=CL[nick]; i=bisect.bisect_right([a for a,b in L],ep)-1
    return L[i][1]
COMBAT=re.compile(r"^(You (hit|miss|bite|smite|have slain|have destroyed|have killed|were hit)|.* (hits|misses|bites|claws|stings|touches|crushes|butts|kicks|gazes at|spits on|crawls on|engulfs|wails at|insults|moans at|begs|crawls|drools|releases spores at) you|.* (casts|breathes|fires|shoots|throws|magically|gestures|mumbles|points)|It (hits|misses|touches))",re.I)
rows=[]
res={}
for nick in ['dive03','dive04']:
    dec,evs,st=pickle.load(open(nick+'.pkl','rb'))
    # series of (epoch, depth, hp, maxhp)
    S=[(j['t'],j.get('depth'),j['hp'][0],j['hp'][1]) for j in dec if j.get('hp') and j['hp'][1]>1]
    S.sort()
    T=[s[0] for s in S]
    # per-time depth lookup, forward-fill depth, but also 'level' events
    def at(ep):
        i=bisect.bisect_right(T,ep)-1
        return S[max(i,0)]
    # active-time: union of all timestamps
    allt=sorted([s[0] for s in S]+[e['ep'] for e in evs])
    # minutes per band: gap<=60s attributed to depth of previous decision record
    mins=collections.defaultdict(float)
    for a,b in zip(allt,allt[1:]):
        g=b-a
        if g>60: continue
        d=at(a)[1]
        mins[band(d)]+=g/60
    msgs=[e for e in evs if e['ev']=='message']
    msgs.sort(key=lambda e:e['ep'])
    xp=collections.defaultdict(float); kills=collections.defaultdict(int); unk=collections.defaultdict(int); gold=collections.defaultdict(int); sold=collections.defaultdict(int)
    unknown_names=collections.Counter()
    kill_rows=[]
    for e in msgs:
        t=e['text']; ep=e['ep']; b=band(at(ep)[1])
        m=re.match(r'You have (slain|destroyed) (?:the )?(.*?)\.$',t)
        if m:
            n=m.group(2)
            v=low.get(n.lower())
            if v is None and n.lower().startswith('the '): v=low.get(n[4:].lower())
            if v:
                lv,ex=v; c=clvl(nick,ep)
                xp[b]+=ex*lv/c; kills[b]+=1; kill_rows.append((ep,b,n,lv,ex,c,ex*lv/c))
            else: unknown_names[n]+=1; unk[b]+=1
        elif t.startswith('You have killed it'): unk[b]+=1
        m=re.match(r'You have found (\d+) gold pieces',t)
        if m: gold[b]+=int(m.group(1))
        m=re.match(r'You sold .* for (\d+) gold',t)
        if m: sold[b]+=int(m.group(1))
    # fights
    fights=[]
    cm=[e for e in msgs if COMBAT.match(e['text'])]
    cur=None
    for e in cm:
        if cur and e['ep']-cur['end']<=15: cur['end']=e['ep']; cur['n']+=1
        else:
            if cur: fights.append(cur)
            cur={'start':e['ep'],'end':e['ep'],'n':1}
    if cur: fights.append(cur)
    fr=collections.defaultdict(lambda:{'n':0,'lost':[],'near':0,'secs':[]})
    for f in fights:
        if f['n']<3: continue
        i0=bisect.bisect_left(T,f['start']-2); i1=bisect.bisect_right(T,f['end']+3)
        seg=S[i0:i1]
        if not seg: continue
        b=band(seg[0][1])
        h0=at(f['start']-2)[2]; mx=max(s[3] for s in seg)
        hmin=min([s[2] for s in seg]+[h0])
        lost=max(0,h0-hmin)
        fr[b]['n']+=1; fr[b]['lost'].append(lost); fr[b]['secs'].append(f['end']-f['start'])
        if hmin<0.4*mx: fr[b]['near']+=1
        f['band']=b; f['lost']=lost; f['frac']=hmin/mx; f['mx']=mx
    # acts
    pot=collections.defaultdict(int); esc=collections.defaultdict(int); stairs=collections.defaultdict(int); search=collections.defaultdict(int)
    deaths=collections.defaultdict(int)
    for j in dec:
        b=band(j.get('depth'))
        if j['kind']=='act':
            w=j['why']; c=j['cmd']
            if 'quaff' in w and ('low HP' in w or 'afraid' in w or 'cure' in w.lower()): pot[b]+=1
            if 'phase door' in w and ('low HP' in w or 'group danger' in w): esc[b]+=1
            if 'word of recall (last resort)' in w: esc[b]+=1
            if w.startswith('stairs'): stairs[b]+=1
            if 'search for secret' in w: search[b]+=1
        if j['kind']=='attention' and j['what']=='dead': deaths[b]+=1
        if j['kind']=='attention' and j['what']=='emergency' and 'took the stairs underfoot' in str(j.get('detail')): esc[b]+=1
    res[nick]=dict(mins=mins,xp=xp,kills=kills,unk=unk,gold=gold,sold=sold,fr=fr,pot=pot,esc=esc,stairs=stairs,search=search,deaths=deaths,fights=fights,kill_rows=kill_rows,unknown=unknown_names,S=S)
    print('=====',nick)
    print('unknown names',unknown_names.most_common(15))
    for b in BANDS:
        f=fr[b]
        print('%-13s min=%6.1f xp=%8.0f kills=%4d unk=%3d gold=%6d sold=%6d fights=%3d lostavg=%5.1f lostmax=%4d near=%2d pot=%3d esc=%3d stairs=%4d search=%3d'%(b,mins[b],xp[b],kills[b],unk[b],gold[b],sold[b],f['n'],(sum(f['lost'])/f['n'] if f['n'] else 0),(max(f['lost']) if f['lost'] else 0),f['near'],pot[b],esc[b],stairs[b],search[b]))
pickle.dump(res,open('G4_res.pkl','wb'))
