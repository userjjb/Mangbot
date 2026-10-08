import sys,bisect,pickle,datetime
sys.path.insert(0,'.')
from r4_load import *
def ctx_depth(d):
    return d
def extract(d):
    dec,evs,st=load(d)
    dts=[j['t'] for j in dec if j.get('depth') is not None]
    dds=[j['depth'] for j in dec if j.get('depth') is not None]
    def depth_at(t):
        i=bisect.bisect_right(dts,t)-1
        return dds[i] if i>=0 else None
    # sun
    sun=[(j['ep'],j['text']) for j in evs if j['ev']=='message' and j['text'] in('The sun has fallen.','The sun has risen.')]
    sts=[a for a,b in sun]
    def daynight(t):
        i=bisect.bisect_right(sts,t)-1
        if i<0: return '?'
        return 'night' if sun[i][1].endswith('fallen.') else 'day'
    runs=[];walks=[]
    lastpos=None;lastlevel=None
    n=len(evs)
    for i,j in enumerate(evs):
        if j['ev']=='pos': lastpos=(j['y'],j['x'])
        if j['ev']=='level': lastpos=lastpos
        if j['ev']!='ack': continue
        c=j['cmd']
        isrun=c.startswith('custom . dir=')
        iswalk=c.startswith('walk ') and c!='walk 5'
        if not(isrun or iswalk): continue
        k=i+1;poss=[];stop=None;mon=0;lev=None;end_ack=None
        msgs=[]
        while k<n:
            e=evs[k]
            if e['ev']=='ack':
                if e['cmd']=='walk 5' and isrun:
                    stop=stop or e['ep']
                else:
                    end_ack=e;break
            elif e['ev']=='pos': poss.append((e['ep'],e['y'],e['x'],k))
            elif e['ev']=='monlist': mon+=1
            elif e['ev']=='level': lev=e
            elif e['ev']=='message': msgs.append(e['text'])
            if e['ep']-j['ep']>30: break
            k+=1
        rec=dict(d=d,ln=j['ln'],ep=j['ep'],cmd=c,start=lastpos,poss=poss,stop=stop,mon=mon,lev=lev is not None,
                 end_ack=(end_ack['ep'],end_ack['cmd']) if end_ack else None,msgs=msgs[:6],depth=depth_at(j['ep']),dn=daynight(j['ep']),
                 nxt_ln=evs[k]['ln'] if k<n else None)
        (runs if isrun else walks).append(rec)
    return runs,walks,evs
if __name__=='__main__':
    out={}
    for d in ['dive03','dive04']:
        r,w,_=extract(d); out[d]=(r,w); print(d,len(r),len(w))
    pickle.dump(out,open('r4_raw.pkl','wb'))
