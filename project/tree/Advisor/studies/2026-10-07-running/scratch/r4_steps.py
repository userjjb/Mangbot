import sys,bisect,pickle,collections;sys.path.insert(0,'.')
from r4_load import *
def steps(d):
    dec,evs,st=load(d)
    dts=[j['t'] for j in dec if j.get('depth') is not None]
    dds=[j['depth'] for j in dec if j.get('depth') is not None]
    out=[]
    mode=None;modeep=0;prev=None;depth=None
    lastlev=None
    for j in evs:
        e=j['ev']
        if e=='ack':
            c=j['cmd']
            if c.startswith('custom . dir='): mode='run';modeep=j['ep']
            elif c.startswith('walk ') and c!='walk 5': mode='walk';modeep=j['ep']
            elif c=='walk 5': pass
            else: mode='other';modeep=j['ep']
        elif e=='level':
            prev=None;depth=j['depth']
        elif e=='pos':
            p=(j['y'],j['x'])
            if prev is not None and p!=prev[1]:
                i=bisect.bisect_right(dts,j['ep'])-1
                dep=dds[i] if i>=0 else None
                out.append(dict(ln=j['ln'],ep=j['ep'],dt=j['ep']-prev[0],frm=prev[1],to=p,mode=mode,since=j['ep']-modeep,depth=dep))
            prev=(j['ep'],p)
    return out
if __name__=='__main__':
    res={}
    for d in['dive03','dive04']:
        s=steps(d);res[d]=s;print(d,len(s))
    pickle.dump(res,open('r4_steps.pkl','wb'))
    import math
    for d in res:
        for m in ['run','walk','other']:
            h=collections.Counter()
            for s in res[d]:
                if s['mode']==m and s['dt']<2: h[min(int(s['dt']*20)/20,1.5)]+=1
            print(d,m,sorted(h.items())[:30])
