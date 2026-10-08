import sys,bisect,pickle,collections,datetime,csv;sys.path.insert(0,'.')
from r4_load import *
NICK={'dive03':'Dive03','dive04':'Dive04'}
def wherecat(dep):
    if dep is None: return 'unk'
    if dep==0: return 'town'
    if dep<0 or dep>21: return 'wild'
    return 'dungeon'
def sunstate(evs):
    sun=[(j['ep'],j['text'].endswith('fallen.')) for j in evs if j['ev']=='message' and j['text'].startswith('The sun has')]
    P=10000/3.0
    ts=[a for a,b in sun]
    def st(t):
        i=bisect.bisect_right(ts,t)-1
        res=[]
        if i>=0 and t-ts[i]<3*3600:
            k=int((t-ts[i])//P); night=sun[i][1]; res.append(night if k%2==0 else (not night))
        if i+1<len(ts) and ts[i+1]-t<3*3600:
            k=int((ts[i+1]-t)//P)+1; night=sun[i+1][1]  # state after message; before it opposite
            # state at t: message at ts[i+1] says state AFTER = night; steps back k half-periods
            res.append(night if k%2==0 else (not night))
        if not res: return '?'
        if len(res)==2 and res[0]!=res[1]: return '?'
        return 'night' if res[0] else 'day'
    return st
def extract(d):
    dec,evs,st=load(d)
    dts=[j['t'] for j in dec if j.get('depth') is not None]
    dds=[j['depth'] for j in dec if j.get('depth') is not None]
    levs=[(j['ep'],j['depth']) for j in evs if j['ev']=='level']
    lts=[a for a,b in levs]
    def depth_at(t):
        # prefer level events if within same segment & recent, else decisions
        i=bisect.bisect_right(dts,t)-1
        return dds[i] if i>=0 else None
    sun=sunstate(evs)
    n=len(evs);runs=[]
    lastpos=None
    for i,j in enumerate(evs):
        if j['ev']=='pos': lastpos=(j['y'],j['x'])
        if not(j['ev']=='ack' and j['cmd'].startswith('custom . dir=')): continue
        k=i+1;poss=[];stops=[];mon=[];lev=None;endack=None;msgs=[]
        while k<n:
            e=evs[k]
            if e['ev']=='ack':
                if e['cmd']=='walk 5': stops.append(e['ep'])
                else: endack=e;break
            elif e['ev']=='pos': poss.append((e['ep'],(e['y'],e['x'])))
            elif e['ev']=='monlist': mon.append(e['ep'])
            elif e['ev']=='level': lev=e
            elif e['ev']=='message': msgs.append(e['text'])
            if e['ep']-j['ep']>40: break
            k+=1
        trail=0
        if endack is not None and endack['cmd'].startswith('walk '):
            m=k+1
            while m<n and evs[m]['ev']=='pos' and evs[m]['ep']-endack['ep']<0.03:
                poss.append((evs[m]['ep'],(evs[m]['y'],evs[m]['x'])));trail+=1;m+=1
        # steps
        cur=lastpos;steps=0;maxj=0;path=[];pts=[]
        for ep,p in poss:
            if cur is None or p!=cur:
                if cur is not None: maxj=max(maxj,abs(p[0]-cur[0]),abs(p[1]-cur[1]))
                steps+=1;pts.append((ep,p))
            cur=p
        end=pts[-1][1] if pts else lastpos
        secs=(pts[-1][0]-j['ep']) if pts else 0.0
        cycle=(endack['ep']-j['ep']) if endack else None
        # overshoot: steps after first stop
        over=sum(1 for ep,p in pts if stops and ep>stops[0]) if stops else 0
        # bends
        dirs=set();prevp=lastpos
        for ep,p in pts:
            if prevp: dirs.add((p[0]-prevp[0],p[1]-prevp[1]))
            prevp=p
        dep=depth_at(j['ep'])
        runs.append(dict(nick=NICK[d],d=d,ln=j['ln'],ep=j['ep'],cmd=j['cmd'],depth=dep,where=wherecat(dep),start=lastpos,end=end,steps=steps,
            secs=secs,cycle=cycle,stops=stops,mon=mon,lev=lev is not None,maxj=maxj,ndirs=len(dirs),trail=trail,
            endcmd=endack['cmd'] if endack else None,over=over,msgs=msgs[:4],dn=sun(j['ep']) if wherecat(dep)=='town' else '',
            firststep=(pts[0][0]-j['ep']) if pts else None,lastgap=None))
    return runs,evs
def outcome(r):
    s=r['steps']
    if r['lev'] or r['maxj']>1 and r['where']!='dungeon': 
        return 'left map/level (run crossed edge)'
    if r['maxj']>1: return 'level changed / teleport'
    if s==0: return 'no movement'
    if s==1: return 'single step only'
    if r['stops']:
        return 'pilot stop (walk 5) after run'
    if r['mon'] and any(abs(m-(r['ep']+r['secs']))<0.5 for m in r['mon']): return 'server ended: monster list change at end'
    return 'server ended (no pilot stop)'
if __name__=='__main__':
    allr=[]
    for d in['dive03','dive04']:
        r,evs=extract(d)
        for x in r: x['outcome']=outcome(x)
        allr+=r
    pickle.dump(allr,open('r4_runs.pkl','wb'))
    c=collections.Counter((x['nick'],x['where'],x['outcome']) for x in allr)
    for k,v in sorted(c.items()): print(k,v)
