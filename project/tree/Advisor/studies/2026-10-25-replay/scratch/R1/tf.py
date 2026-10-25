import sys,pickle,re,bisect,statistics as S,collections
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1')
sys.path.insert(0,'.')
from common import *
import importlib.util
E='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1/'
recs=pickle.load(open(E+'recs.pkl','rb')); evs=pickle.load(open(E+'evs.pkl','rb'))
src=open('build.py').read()
ns={}
exec(src.split("def uniq_name")[0].split("HOST_V=")[0]+"\n"+"def itemkey"+src.split("def itemkey")[1].split("CONF=")[0].split("def whatof")[0],ns) if False else None
# simple local copies
CONF={'phase':r'(You have .*Scrolls? of Phase Door|no more Scrolls of Phase Door)','clw':r'Cure Light','csw':r'Cure Serious','ccw':r'Cure Critical','speed':r'Potions? of Speed','tele':r'Scrolls? of Teleportation'}
def what(a):
    c,w=a['cmd'],a['why'].lower()
    if c.startswith('custom r'):
        if 'phase' in w:return 'phase'
        if 'teleportation' in w and 'door' not in w:return 'tele'
    if c.startswith('custom q'):
        for k,n in (('clw','cure light'),('csw','cure serious'),('ccw','cure critical'),('speed','speed')):
            if n in w or n.replace(' ','_') in w:return k
    return None
tfr=[(d['t'],d['factor']) for d in recs if d['kind']=='time_factor']
tft=[x[0] for x in tfr]
def fac(t):
    j=bisect.bisect_right(tft,t)-1
    return tfr[j][1] if j>=0 and t-tft[j]<300 else None
msgs=[(v['epoch'],v['text']) for v in evs if v['ev']=='message']
acts=sorted([(d['t'],what(d),d) for d in recs if d['kind']=='act' and what(d) and 'resend' not in d['why']],key=lambda x:x[0])
# restrict to acts inside E1 episode windows (evs covers those)
used=set();res=[]
for t,k,d in acts:
    if not any(abs(m[0]-t)<30 for m in msgs[:0]):pass
    for j,(mt,tx) in enumerate(msgs):
        if mt>=t-0.01 and mt<=t+60 and j not in used and re.search(CONF[k],tx) and tx.startswith(('You have','You feel')) :
            used.add(j);res.append((t,k,mt,fac(t)));break
g=collections.defaultdict(list)
for t,k,mt,f in res:
    g[f].append(mt-t)
def st(l):
    l=sorted(l);return (len(l),round(S.median(l),2),round(l[0],2),round(l[-1],2),round(l[len(l)//10],2),round(l[9*len(l)//10],2))
for f,l in sorted(g.items(),key=lambda x:str(x[0])):print('latency act->confirm, factor',f,st(l))
# consecutive confirm intervals
g2=collections.defaultdict(list)
for (t1,k1,m1,f1),(t2,k2,m2,f2) in zip(res,res[1:]):
    if m2-m1<30 and f1==f2:g2[f1].append(m2-m1)
for f,l in sorted(g2.items(),key=lambda x:str(x[0])):print('interval between consecutive item effects, factor',f,st(l))
print(collections.Counter(f for t,k,m,f in res))
