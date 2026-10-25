import json,pickle,re,collections,csv
from common import *
eps=pickle.load(open('eps.pkl','rb'))
recs=pickle.load(open('recs.pkl','rb'))
hp=pickle.load(open('hp.pkl','rb'))
evs=pickle.load(open('evs.pkl','rb'))
# merge: m25 Ibun chain; m29 20:43 pair
def merge(pred_start,pred_end_t,newkey=None):
    global eps
    idx=[i for i,e in enumerate(eps) if pred_start(e)]
    if len(idx)<2:return
    first=eps[idx[0]];last=eps[idx[-1]]
    first['t1']=max(first['t1'],pred_end_t if pred_end_t else last['t1'])
    first['levels']=sum((eps[i]['levels'] for i in idx),[])
    first['trig']=sum((eps[i]['trig'] for i in idx),[])
    first['end']=last['end']
    eps=[e for i,e in enumerate(eps) if i not in idx[1:]]
merge(lambda e:e['mission']=='m25' and eps_('2026-10-24 02:31:20')<=e['t0']<=eps_('2026-10-24 02:32:30'),eps_('2026-10-24 02:32:36'))
merge(lambda e:e['mission']=='m29' and eps_('2026-10-24 20:43:00')<=e['t0']<=eps_('2026-10-24 20:43:20'),None)
print(len(eps))
def cheb(a,b):return max(abs(a[0]-b[0]),abs(a[1]-b[1]))
def classify(d):
    w=d['why'].lower();c=d['cmd']
    if c.startswith('custom r'):
        if 'phase' in w:return 'Phase'
        if 'recall' in w:return 'WoR'
        if 'teleportation' in w:return 'Teleport'
        if "['i']" in w:return 'Teleport'
        if 'agent: read' in w:return 'read?'
    if c.startswith('custom q'):
        if 'speed' in w:return 'Speed'
        if 'heroism' in w:return 'Heroism'
        if 'berserk' in w:return 'Berserk'
        if 'bold' in w:return 'Boldness'
        if 'cure critical' in w:return 'CCW'
        if 'cure serious' in w:return 'CSW'
        if 'cure light' in w:return 'CLW'
        if "agent: quaff ['g']" in w:return 'CCW(by hand)'
        if "agent: quaff" in w:return 'quaff?'
    if c=='custom <' or c=='custom >':return 'stairs'
    return None
rows=[]
for e in eps:
    t0,t1=e['t0'],e['t1']
    seg=[x for x in hp if t0-1<=x[0]<=t1]
    h0=[x for x in hp if x[0]<=t0][-1]
    mn=min(seg,key=lambda x:x[1])
    names=collections.Counter();maxadj=0;adj_at_min=None;adj_at_min_names=[]
    best=None
    for d in recs:
        if t0-8<=d['t']<=t1 and d['kind']=='mons' and d.get('pos'):
            ms=d['monsters'];adj=[m[2] for m in ms if cheb((m[0],m[1]),d['pos'])<=1]
            for n in set(m[2] for m in ms):names[n]=max(names[n],sum(1 for m in ms if m[2]==n))
            if len(adj)>maxadj:maxadj=len(adj)
            if best is None or abs(d['t']-mn[0])<best[0]:best=(abs(d['t']-mn[0]),len(adj),adj,len(ms))
    acts=[];cons=collections.Counter();last=None
    for d in recs:
        if t0-1<=d['t']<=t1+1:
            if d['kind']=='act' and 'resend' not in d['why']:
                c=classify(d)
                if c and not (c=='stairs'):
                    if c=='read?':c='read'
                    acts.append(f"{hms(d['t'])} hp{d['hp'][0]} {c}");cons[c]+=1
                elif c=='stairs':
                    acts.append(f"{hms(d['t'])} hp{d['hp'][0]} stairs{d['cmd'][-1]}");cons['stairs']+=1
            elif d['kind']=='nav_cmd' and d['cmd'] in('goal','plan','stop','order'):
                acts.append(f"{hms(d['t'])} hp{d['hp'][0]} NAV {d['cmd']} {' '.join(map(str,d['args']))[:30]}")
    # buff/status messages
    st=collections.Counter()
    for v in evs:
        if v['ev']=='message' and t0-5<=v['epoch']<=t1:
            tx=v['text']
            for k,pat in (('slowed','moving slower'),('hasted','speed up'),('blind','You are blind'),('confused','You are confused'),('paralyzed','paralyzed'),('afraid','terrified|too afraid'),('poisoned','You are poisoned'),('item_burned','was destroyed|were destroyed'),('stat_drain','drains power|feel very clumsy|You feel very')):
                if re.search(pat,tx):st[k]+=1
    rows.append(dict(mission=e['mission'],start=hmsd(t0),t0=t0,t1=t1,end=e['end'],depth_ft=(e['depth'] or 0)*50,hp_start=f"{h0[1]}/{h0[2]}",hp_start_pct=round(100*h0[1]/h0[2]),
        hp_min=mn[1],hp_max=mn[2],hp_min_pct=round(100*mn[1]/mn[2]),min_time=hms(mn[0]),dur_s=round(t1-t0),
        monsters='; '.join(f"{n} x{c}" for n,c in names.most_common(8)),max_adjacent=maxadj,adj_at_min=(best[1] if best else None),adj_names_at_min=(','.join(best[2]) if best else ''),
        actions=' | '.join(acts),cons=dict(cons),status=dict(st),levels=len(e['levels'])))
pickle.dump(rows,open('rows.pkl','wb'))
for i,r in enumerate(rows):
    print(i,r['mission'],r['start'],f"{r['dur_s']}s",r['hp_start'],'min',r['hp_min'],r['hp_min_pct'],'%',r['min_time'],'adj@min',r['adj_at_min'],'maxadj',r['max_adjacent'],r['cons'],r['status'])
