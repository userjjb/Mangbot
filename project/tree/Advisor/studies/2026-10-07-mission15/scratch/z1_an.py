import sys; sys.path.insert(0,'.')
from z1_load import *
import collections, bisect, datetime
off=1791425380.0
M0=datetime.datetime(2026,10,7,22,42).timestamp(); M1=datetime.datetime(2026,10,7,23,36).timestamp()
dts=[d['t'] for d in dec if d.get('depth') is not None]
dd=[d.get('depth') for d in dec if d.get('depth') is not None]
def depth_at(T):
    i=bisect.bisect_right(dts,T)-1
    return dd[i] if i>=0 else None
# build step list
steps=[]; lastp=None; lastT=None; lastack=None
for e in ev:
    T=e['t']+off
    if T<M0-5 or T>M1: continue
    if e['ev']=='ack': lastack=(T,e['cmd']); continue
    if e['ev']!='pos': continue
    p=(e['y'],e['x'])
    if lastp is not None and p!=lastp and max(abs(p[0]-lastp[0]),abs(p[1]-lastp[1]))==1:
        steps.append(dict(T=T,dt=T-lastT,d=(p[0]-lastp[0],p[1]-lastp[1]),p=p,ack=lastack[1] if lastack else None,ackdt=T-lastack[0] if lastack else None,depth=depth_at(T)))
    lastp=p; lastT=T
steps=[s for s in steps if s['depth'] and s['depth']>0]
print('dungeon steps',len(steps))
import pickle; pickle.dump(steps,open('z1_steps.pkl','wb'))
tot=sum(s['dt'] for s in steps if s['dt']<2)
print('moving time',tot, 'n<2s',sum(1 for s in steps if s['dt']<2))
fast=[s for s in steps if s['dt']<0.3]
print('fast(<0.3)',len(fast),'time',sum(s['dt'] for s in fast))
slow=[s for s in steps if 0.3<=s['dt']<2]
print('slow',len(slow),'time',sum(s['dt'] for s in slow), 'mean',sum(s['dt'] for s in slow)/len(slow))
