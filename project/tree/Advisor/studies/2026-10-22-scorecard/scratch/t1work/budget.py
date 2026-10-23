import sys; sys.path.insert(0,'.')
from t1c import *
import pickle, bisect

COMBAT_PLAYER=re.compile(r'^You (hit|miss|have slain|have destroyed|bite|smite)\b')
COMBAT_MON=re.compile(r' (hits|misses|bites|claws|stings|butts|kicks|crushes|touches|engulfs|spits on|crawls on|gazes at|grabs|squeezes|tramples|wails at|shrieks at|stares at|insults|moans at|drools on|begs) you\b|^(It|The [A-Za-z\- ]+|[A-Z][A-Za-z, \-]+) (fires|casts|breathes|hurls|throws|shoots|conjures|points|mumbles|makes|magically)')
ESC_TRIG={'emergency','emergency_loop','fight_going_badly','danger_seen','band','unseen_attacker','stat_drained'}

def pos_events(L,pad=60):
    a,b=win(L); out=[]
    last=None
    for d in evs(L,pad=pad):
        if d['ev']=='pos':
            p=(d['y'],d['x'])
            if p!=last: out.append(d['epoch']); last=p
    return out

def build(L, msgs, posch):
    a,b=win(L); N=int(b-a)
    R=recs(L)
    lab=['?']*N
    def idx(t): return int(t-a)
    def span(x,y): return range(max(0,idx(x)),min(N,idx(y)+ (1 if y>x else 0)))
    # depth timeline
    dts=[(d['t'],d['depth']) for d in R if d.get('depth') is not None]
    dt_t=[x for x,_ in dts]
    def depth_at(t):
        i=bisect.bisect_right(dt_t,t)-1
        return dts[i][1] if i>=0 else 0
    # goals
    gl=[]  # (t, goal or None)
    for d in R:
        if d['kind']=='goal': gl.append((d['t'],d.get('goal')))
        elif d['kind']=='attention' and d.get('what') in('goal_done','goal_failed'): gl.append((d['t'],None))
        elif d['kind']=='attention' and d.get('what')=='dead': gl.append((d['t'],None))
    gl_t=[x for x,_ in gl]
    def goal_at(t):
        i=bisect.bisect_right(gl_t,t)-1
        return gl[i][1] if i>=0 else None
    # down
    ts=[d['t'] for d in R]
    down=[False]*N
    for s in range(N):
        t=a+s+0.5
        if t<ts[0] or t>ts[-1]: down[s]=True
    for x,y in zip(ts,ts[1:]):
        if y-x>45:
            for s in span(x,y): down[s]=True
    # combat windows
    fight=[False]*N
    for e,t,ty in msgs:
        if a<=e<=b and depth_at(e)>0 and (COMBAT_PLAYER.search(t) or COMBAT_MON.search(t)):
            for s in span(e,e+5): fight[s]=True
    # escape windows
    esc=[False]*N
    escf=[False]*N
    # flee goal intervals
    for i,(t,g) in enumerate(gl):
        if g and g.startswith('flee'):
            end=gl[i+1][0] if i+1<len(gl) else b
            for s in span(t,end): escf[s]=True
    for d in R:
        if d['kind']=='attention' and d.get('what') in('emergency','emergency_loop'):
            for s in span(d['t'],d['t']+10): esc[s]=True
        if d['kind']=='act' and re.search(r'phase door',d['why'],re.I) and d.get('depth',0):
            for s in span(d['t'],d['t']+5): esc[s]=True
    yanks_up=[e for e,t,ty in msgs if 'yanked upwards' in t]
    wor=[]
    for d in R:
        if d['kind']=='act' and re.match(r'custom r',d['cmd']) and 'Word of Recall' in d['why'] or (d['kind']=='act' and re.search(r'word of recall|recall',d['why'],re.I) and d['cmd'].startswith('custom r')):
            wor.append(d)
    attn=[(d['t'],d['what']) for d in R if d['kind']=='attention']
    wor_info=[]
    for d in wor:
        t=d['t']; dep=d.get('depth') or 0
        if dep==0: wor_info.append((t,'travel_down',None,d)); continue
        why=d['why']
        hard=bool(re.match(r'low HP|flee failed|group danger',why))
        trig=[w for tt,w in attn if t-45<=tt<=t and w in ESC_TRIG]
        hpf=d['hp'][0]/max(1,d['hp'][1]) if d.get('hp') else 1
        kind='escape' if (hard or trig or hpf<0.5) else 'planned_home'
        yk=[e for e in yanks_up if t<e<=t+90]
        wor_info.append((t,kind,(hard,trig[:3],round(hpf,2),yk[0]-t if yk else None),d))
        if kind=='escape':
            end=yk[0] if yk else t+30
            for s in span(t,end): esc[s]=True
    # rest intervals
    rest=[False]*N
    acts=[d for d in R if d['kind']=='act']
    pc=posch
    for i,d in enumerate(R):
        if d['kind']=='act' and d['cmd']=='rest' and d['why']=='rest':
            t=d['t']
            # end: next stop-resting act, next non-rest act, next position change, or 60s
            end=t+60
            for d2 in R[i+1:]:
                if d2['t']>t+60: break
                if d2['kind']=='act' and not (d2['cmd']=='rest' and d2['why']=='rest'):
                    end=d2['t']; break
            j=bisect.bisect_right(pc,t+0.05)
            if j<len(pc) and pc[j]<end: end=pc[j]
            for s in span(t,end): rest[s]=True
    # searching/doors
    srch=[False]*N
    for d in acts:
        if d['cmd']=='custom s': 
            for s in span(d['t'],d['t']+3): srch[s]=True
    for e,t,ty in msgs:
        if re.search(r'pick the lock|picked the lock|dig in the rubble|removed the rubble|secret door',t) and a<=e<=b:
            for s in span(e-3,e+3): srch[s]=True
    for i,(t,g) in enumerate(gl):
        if g and g.startswith('searchroom'):
            end=gl[i+1][0] if i+1<len(gl) else b
            for s in span(t,end): srch[s]=True
    # stuck: no position change >=20s, goal in moving set, not fight/rest/esc/srch
    stuck=[False]*N
    # (computed after other layers below)
    stat=[False]*N
    for x,y in zip(pc,pc[1:]):
        if y-x>=20:
            for q in span(x,y): stat[q]=True
    last_goal_t=max([t for t,g in gl if g] or [a])
    out=[]
    for s in range(N):
        t=a+s+0.5
        dep=depth_at(t); g=goal_at(t)
        gw=(g or '').split(' ')[0].split('(')[0] if g else ''
        if down[s]: lab[s]='pilot_down'; continue
        if dep>0:
            if esc[s]: lab[s]='escaping'; continue
            if fight[s] or gw=='hunt': lab[s]='fighting'; continue
            if rest[s] or gw in('rest','recover'): lab[s]='resting'; continue
            if srch[s]: lab[s]='searching_doors'; continue
            if stat[s] and (gw in('explore','dive','goto') or escf[s]): lab[s]='stuck_looping'; continue
            if escf[s]: lab[s]='escaping'; continue
            if gw=='recall': lab[s]='recall_wait'; continue
            lab[s]={'explore':'exploring','dive':'travel_dive','goto':'travel_goto','':'no_goal_dungeon'}.get(gw,'?dg'+gw)
        else:
            if rest[s]: lab[s]='resting'; continue
            if gw=='shop': lab[s]='town_shopping'
            elif gw=='townfarm': lab[s]='town_farming'
            elif gw=='recall': lab[s]='recall_wait'
            elif gw=='': lab[s]='town_idle_end' if t>last_goal_t else 'town_no_goal'
            else: lab[s]='town_other'
    # stuck pass on dungeon '?dg' seconds
    for s in range(N):
        if lab[s].startswith('?dg'):
            t=a+s+0.5
            j=bisect.bisect_right(pc,t)-1
            since=t-pc[j] if j>=0 else 999
            gw=lab[s][3:]
            if gw in('explore','dive','goto','') and False: pass
            lab[s]=lab[s]  # keep for now
    return lab,wor_info,pc,depth_at,goal_at,a,b

if __name__=='__main__':
    allm=pickle.load(open('msgs.pkl','rb'))
    res={}
    for L in LABELS:
        posch=pos_events(L)
        lab,wi,pc,da,ga,a,b=build(L,allm[L],posch)
        # second-level mapping of ?dg
        c=collections.Counter(lab)
        res[L]=c
        print(L,int(b-a),dict(c))

def summarize():
    allm=pickle.load(open('msgs.pkl','rb'))
    out={}
    for L in LABELS:
        posch=pos_events(L)
        lab,wi,pc,da,ga,a,b=build(L,allm[L],posch)
        dun=sum(1 for s in range(len(lab)) if da(a+s+0.5)>0)
        out[L]=(lab,dun,wi,a,b)
    return out
