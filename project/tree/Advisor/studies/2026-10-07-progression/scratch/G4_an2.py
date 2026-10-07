import pickle,re,collections,datetime,csv,bisect,sys
exec(open('G4_an.py').read().split("rows=[]")[0])   # reuse mon/low/band/CL/clvl/COMBAT
MS={'dive03':[('P1',0),('P2',ts('09-25 23:16:30')),('m1',ts('09-26 15:14:00')),('m2',ts('09-26 16:10:00')),('m3',ts('09-27 11:07:00')),('m4',ts('09-27 12:05:00')),('m5',ts('09-27 12:43:50')),('m6',ts('09-27 13:34:00')),('m7',ts('09-27 22:10:00'))],
    'dive04':[('m8',0),('m9',ts('09-29 21:34:00')),('m10',ts('09-29 22:05:20')),('m11',ts('09-29 22:32:00')),('m12',ts('10-03 12:18:00')),('m13',ts('10-07 08:48:00'))]}
END={'dive03':{'P1':ts('09-25 23:16:30'),'P2':ts('09-26 15:13:00'),'m1':ts('09-26 16:06:00'),'m2':ts('09-26 16:55:00'),'m3':ts('09-27 12:00:00'),'m4':ts('09-27 12:44:00'),'m5':ts('09-27 13:12:00'),'m6':ts('09-27 13:59:00'),'m7':ts('09-27 22:29:00')},
 'dive04':{'m8':ts('09-28 02:08:00'),'m9':ts('09-29 22:04:00'),'m10':ts('09-29 22:30:00'),'m11':ts('09-29 23:08:00'),'m12':ts('10-03 12:52:00'),'m13':ts('10-07 09:24:00')}}
def mission(nick,ep):
    L=MS[nick]; i=bisect.bisect_right([b for a,b in L],ep)-1
    m=L[max(i,0)][0]
    return m if ep<=END[nick][m] else 'off'
def dive_goal(g):
    g=g.split()[0] if g else ''
    return g
agg=collections.defaultdict(lambda:collections.defaultdict(float))
catmin=collections.defaultdict(lambda:collections.defaultdict(float))
clv=[]; kills_all={}
for nick in ['dive03','dive04']:
    dec,evs,st=pickle.load(open(nick+'.pkl','rb'))
    S=[(j['t'],j.get('depth'),j['hp'][0],j['hp'][1]) for j in dec if j.get('hp') and j['hp'][1]>1]; S.sort(); T=[s[0] for s in S]
    def at(ep):
        i=bisect.bisect_right(T,ep)-1; return S[max(i,0)]
    allt=sorted([s[0] for s in S]+[e['ep'] for e in evs])
    # goal tracking
    gl=[(j['t'],j['goal'] or 'none') for j in dec if j['kind']=='goal']
    ge=[(j['t'],'END') for j in dec if j['kind']=='attention' and j['what'] in('goal_done','goal_failed')]
    gt=sorted(gl+ge); GT=[x[0] for x in gt]
    stuck=[j['t'] for j in dec if j['kind']=='attention' and j['what']=='stuck']
    for a,b in zip(allt,allt[1:]):
        g=b-a
        if g>60: continue
        d=at(a)[1]; bd=band(d); m=mission(nick,a)
        agg[(nick,m,bd)]['min']+=g/60
        i=bisect.bisect_right(GT,a)-1
        cat='none' if i<0 else gt[i][1]
        cat='idle/none' if cat=='END' else cat.split()[0]
        if bd=='town/surface': cat='T:'+cat
        catmin[(nick,m)][cat]+=g/60
    msgs=sorted([e for e in evs if e['ev']=='message'],key=lambda e:e['ep'])
    for e in msgs:
        t=e['text']; ep=e['ep']; bd=band(at(ep)[1]); m=mission(nick,ep); k=(nick,m,bd)
        mm=re.match(r'You have (slain|destroyed) (?:the )?(.*?)\.$',t)
        if mm:
            v=low.get(mm.group(2).lower())
            if v:
                agg[k]['xp']+=v[1]*v[0]/clvl(nick,ep); agg[k]['kills']+=1
        mm=re.match(r'You have found (\d+) gold pieces',t)
        if mm: agg[k]['gold']+=int(mm.group(1))
        mm=re.match(r'You sold .* for (\d+) gold',t)
        if mm: agg[k]['sold']+=int(mm.group(1))
    # fights
    cm=[e for e in msgs if COMBAT.match(e['text'])]
    fights=[];cur=None
    for e in cm:
        if cur and e['ep']-cur['end']<=15: cur['end']=e['ep']; cur['n']+=1
        else:
            if cur: fights.append(cur)
            cur={'start':e['ep'],'end':e['ep'],'n':1}
    if cur: fights.append(cur)
    for f in fights:
        if f['n']<3: continue
        i0=bisect.bisect_left(T,f['start']-2); i1=bisect.bisect_right(T,f['end']+3)
        seg=S[i0:i1]
        if not seg: continue
        bd=band(seg[0][1]); m=mission(nick,f['start']); k=(nick,m,bd)
        h0=at(f['start']-2)[2]; mx=max(s[3] for s in seg); hmin=min([s[2] for s in seg]+[h0])
        agg[k]['fights']+=1; agg[k]['hp_lost']+=max(0,h0-hmin)
        if hmin<0.4*mx: agg[k]['near']+=1
        if hmin<0.2*mx: agg[k]['near20']+=1
    for j in dec:
        bd=band(j.get('depth')); m=mission(nick,j['t']); k=(nick,m,bd)
        if j['kind']=='act':
            w=j['why']
            if 'quaff' in w and ('low HP' in w or 'afraid' in w): agg[k]['pot']+=1
            if 'phase door' in w and ('low HP' in w or 'group danger' in w): agg[k]['esc']+=1
            if 'word of recall (last resort)' in w: agg[k]['esc']+=1
            if w.startswith('stairs'): agg[k]['stairs']+=1
            if 'search for secret' in w: agg[k]['search']+=1
        if j['kind']=='attention':
            if j['what']=='dead': agg[k]['deaths']+=1
            if j['what']=='emergency' and 'took the stairs underfoot' in str(j.get('detail')): agg[k]['esc']+=1
            if j['what']=='stuck': agg[k]['stuck']+=1
    # level intervals
    L=CL[nick]
    for idx,(a,c) in enumerate(L):
        b=L[idx+1][0] if idx+1<len(L) else S[-1][0]
        if a==0: a=S[0][0]
        seg=[s for s in S if a<=s[0]<b]
        mhp=max([s[3] for s in seg],default=0)
        dm=0.0;xp=0.0;depths=collections.Counter()
        for x,y in zip(allt,allt[1:]):
            if a<=x<b and y-x<=60:
                dd=at(x)[1]
                if band(dd)!='town/surface': dm+=(y-x)/60; depths[dd]+=(y-x)
        for e in msgs:
            if a<=e['ep']<b:
                mm=re.match(r'You have (slain|destroyed) (?:the )?(.*?)\.$',e['text'])
                if mm:
                    v=low.get(mm.group(2).lower())
                    if v: xp+=v[1]*v[0]/c
        clv.append((nick,c,fmt(a),fmt(b),round(dm,1),round(xp),mhp,depths.most_common(1)[0][0]*50 if depths else None, sum(1 for d in depths if d), min(depths) if depths else None, max(depths) if depths else None))
pickle.dump({k:dict(v) for k,v in agg.items()},open('G4_agg.pkl','wb'))
pickle.dump({k:dict(v) for k,v in catmin.items()},open('G4_cat.pkl','wb'))
print('nick clvl from to dungeon_min xp_est maxHP modal_ft nlevels mindepth maxdepth')
for r in clv: print(*r)
