import sys,pickle,collections,statistics as S,datetime;sys.path.insert(0,'.')
from r4_runs import *
steps=pickle.load(open('r4_steps.pkl','rb'))
allr=pickle.load(open('r4_runs.pkl','rb'))
# sun state function per log
suns={}
for d in['dive03','dive04']:
    dec,evs,st=load(d); suns[d]=sunstate(evs)
def place(s,d):
    w=wherecat(s['depth'])
    if w=='town': return 'town-'+suns[d](s['ep'])
    return w
def med(a): return S.median(a) if a else None
print('STEP dt by mode/place')
for d in steps:
    g=collections.defaultdict(list)
    for s in steps[d]:
        if s['dt']>=2: continue
        k=place(s,d)
        cls='steady-run' if s['dt']<0.2 else ('walk' if s['mode']=='walk' else 'run-late' if s['mode']=='run' else 'other')
        if cls in('walk','steady-run'): 
            if cls=='walk' and not 0.4<s['dt']<0.8: continue
        g[(k,cls)].append(s['dt'])
    for k in sorted(g): 
        v=g[k]
        if len(v)>=20: print(d,k,len(v),'median dt %.3f'%med(v),'mean %.3f'%S.mean(v),'tiles/s %.2f'%(1/med(v)))
