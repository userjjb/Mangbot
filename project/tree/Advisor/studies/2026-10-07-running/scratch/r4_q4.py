import sys,pickle,collections,statistics as S,datetime;sys.path.insert(0,'.')
from r4_runs import *
steps=pickle.load(open('r4_steps.pkl','rb'))
CUT=datetime.datetime(2026,9,25,21,55,43).timestamp()   # 6c3cea5 commit time
CUT2=datetime.datetime(2026,10,7,9,25,0).timestamp()     # a516853
res={}
for d in['dive03','dive04']:
    dec,evs,st=load(d)
    # total active time: sum of segment spans
    segs=[];s0=None;p=None
    for j in evs:
        if p is None or j['t']<p-1:
            if s0 is not None: segs.append((s0,pe))
            s0=j['ep']
        p=j['t'];pe=j['ep']
    segs.append((s0,pe))
    tot=sum(b-a for a,b in segs)
    print(d,'segments',len(segs),'active hours %.1f'%(tot/3600))
    ss=steps[d]
    # movement time
    mv=sum(s['dt'] for s in ss if s['dt']<2)
    walk=[s for s in ss if s['mode']=='walk' and s['dt']<1.2]
    print(' movement time h %.2f'%(mv/3600),' walk-step time h %.2f'%(sum(s['dt'] for s in walk)/3600),'n walk',len(walk))
    # straight walk stretches
    stretches=[];cur=[]
    prev=None
    for s in ss:
        vec=(s['to'][0]-s['frm'][0],s['to'][1]-s['frm'][1])
        ok=s['mode']=='walk' and s['dt']<1.2 and abs(vec[0])<=1 and abs(vec[1])<=1
        if ok and cur and cur[-1][1]==vec and s['ln']-cur[-1][2]<40 and s['ep']-cur[-1][3]<1.2:
            cur.append((s,vec,s['ln'],s['ep']))
        else:
            if cur: stretches.append(cur)
            cur=[(s,vec,s['ln'],s['ep'])] if ok else []
    if cur: stretches.append(cur)
    res[d]=stretches
    for lo in (3,5,8,12):
        sel=[c for c in stretches if len(c)>=lo]
        # time spent walking beyond first step; estimated run time
        tw=0;tr=0;n=0
        for c in sel:
            L=len(c)
            dep=c[0][0]['depth']
            dw=S.median([x[0]['dt'] for x in c])
            dr=dw/5.0
            tw+=sum(x[0]['dt'] for x in c)
            tr+=dw+ (L-2)*dr+dr*0 + 0.0   # first step ~ walk step, then run steps (stop one early costs ~ nothing)
            n+=L
        print(' straight walk stretches >=%d: %d stretches, %d tiles, walk time %.0f s, est run time %.0f s, saving %.0f s (%.2f%% of active)'%(lo,len(sel),n,tw,tr,tw-tr,100*(tw-tr)/tot))
    # by place for >=4
    g=collections.defaultdict(lambda:[0,0,0.0,0.0])
    for c in stretches:
        if len(c)<4: continue
        dep=c[0][0]['depth']; w=wherecat(dep)
        post=c[0][0]['ep']>CUT2
        key=(w,'after-a516853' if post else ('before-6c3cea5' if c[0][0]['ep']<CUT else 'between'))
        dw=S.median([x[0]['dt'] for x in c]);L=len(c)
        g[key][0]+=1;g[key][1]+=L;g[key][2]+=sum(x[0]['dt'] for x in c);g[key][3]+=dw+(L-2)*dw/5
    for k,v in sorted(g.items(),key=lambda kv:str(kv[0])): print('  ',k,'n',v[0],'tiles',v[1],'walk s %.0f'%v[2],'run est s %.0f'%v[3],'saved %.0f'%(v[2]-v[3]))
