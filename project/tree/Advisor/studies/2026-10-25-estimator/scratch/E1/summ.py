import json,pickle,sys,re,collections
from common import *
eps=pickle.load(open('eps.pkl','rb'))
recs=pickle.load(open('recs.pkl','rb'))
evs=pickle.load(open('evs.pkl','rb'))
hp=pickle.load(open('hp.pkl','rb'))
def cheb(a,b):return max(abs(a[0]-b[0]),abs(a[1]-b[1]))
def summ(i,pre=10,post=5):
    e=eps[i];t0,t1=e['t0'],e['t1']
    L=[]
    L.append(f"=== EP{i} {e['mission']} {hmsd(t0)}->{hms(t1)} ({t1-t0:.0f}s) end={e['end']} depth={e['depth']} levels={[(hms(a),b,c) for a,b,c in e['levels']]}")
    seg=[x for x in hp if t0-2<=x[0]<=t1]
    h0=[x for x in hp if x[0]<=t0][-1:]
    if h0:L.append(f"hp at start {h0[0][1]}/{h0[0][2]}")
    if seg:
        mn=min(seg,key=lambda x:x[1]);L.append(f"min hp {mn[1]}/{mn[2]} ({100*mn[1]//mn[2]}%) at {hms(mn[0])}")
    # monsters
    names=collections.Counter();maxadj=0;maxadjt=None;maxview=0
    for d in recs:
        if t0-pre<=d['t']<=t1+post and d['kind']=='mons' and d.get('pos'):
            ms=d['monsters'];adj=[m for m in ms if cheb((m[0],m[1]),d['pos'])<=1]
            for n in set(m[2] for m in ms):names[n]=max(names[n],sum(1 for m in ms if m[2]==n))
            if len(adj)>maxadj:maxadj=len(adj);maxadjt=(hms(d['t']),[m[2] for m in adj])
            maxview=max(maxview,len(ms))
    L.append(f"monsters(max count in view): {dict(names)}; max adjacent {maxadj} {maxadjt}; max in view {maxview}")
    last=None
    for d in recs:
        if t0-pre<=d['t']<=t1+post:
            k=d['kind']
            if k=='act' and not d['cmd'].startswith(('walk','run','move','custom ,','custom s ','custom w','custom t')) :
                s=f"{hms(d['t'])} hp{d['hp'][0]} ACT {d['cmd']} | {d['why'][:70]}"
                if s!=last:L.append(s)
                last=s
            elif k=='escape':L.append(f"{hms(d['t'])} hp{d['hp'][0]} ESC {d['escape']} | {d['trigger'][:60]} | adj={d.get('adjacent')} goal={str(d.get('goal'))[:30]}")
            elif k=='nav_cmd':L.append(f"{hms(d['t'])} hp{d['hp'][0]} NAV {d['cmd']} {d['args']}")
            elif k=='attention' and d.get('what') in('emergency','emergency_loop','fight_going_badly','danger_seen','tactic'):L.append(f"{hms(d['t'])} hp{d['hp'][0]} ATT {d['what']}: {d['detail'][:110]}")
            elif k=='goal':L.append(f"{hms(d['t'])} GOAL {str(d['goal'])[:60]}")
    # melee count
    nm=sum(1 for v in evs if v['ev']=='message' and t0<=v['epoch']<=t1 and re.match(r'You (hit|miss|bite|smite|slash)',v['text']))
    L.append(f"melee message count {nm}")
    return '\n'.join(L)
if __name__=='__main__':
    for a in sys.argv[1:]:print(summ(int(a)));print()
