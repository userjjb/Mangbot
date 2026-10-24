import pickle,re,csv,glob,os,bisect,datetime,zoneinfo,json
from common import *
ev=pickle.load(open('ev.pkl','rb'))
ev=[d for d in ev if d['abs'] and d['ev'] in('message','monlist','level')]
ts=[d['abs'] for d in ev]
FEEL=["Looks like any other level.","You feel there is something special about this level.","You have a superb feeling about this level.","You have an excellent feeling...","You have a very good feeling...","You have a good feeling...","You feel strangely lucky...","You feel your luck is turning...","You like the look of this place...","This level can't be all bad...","What a boring place..."]
def parse_head(h):
    m=re.match(r'# (\d+) ft, (\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d) - (\d\d):(\d\d):(\d\d)',h)
    g=list(map(int,m.groups()))
    t0=T(g[1],g[2],g[3],g[4],g[5],g[6])
    t1=T(g[1],g[2],g[3],g[7],g[8],g[9])
    if t1<t0:t1+=86400
    return g[0],t0,t1
MON=re.compile(r"^(.*?) \('(.)'\)/")
def analyse(f):
    h=open('/projectnb/jbrcs/mangband/runs/pilot/dive04/levels/'+f).readline()
    dep,t0,t1=parse_head(h)
    i0=bisect.bisect_left(ts,t0-3);i1=bisect.bisect_right(ts,t1+3)
    seg=ev[i0:i1]
    feel=None;arr=None
    for d in seg:
        if d['ev']=='message':
            if d['text'].startswith('You enter a maze'):arr=d['text'][-17:]
            if d['text'] in FEEL and feel is None and abs(d['abs']-t0)<10: feel=d['text']
    mons={}
    first={}
    for d in seg:
        if d['ev']=='monlist':
            for l in d['lines']:
                m=MON.match(l)
                if m:
                    n=re.sub(r'^(The) ','',m.group(1))
                    mons.setdefault(n,d['abs'])
    # first-mention classification
    acted={};
    for d in seg:
        if d['ev']!='message':continue
        tx=d['text']
        for n in mons:
            if n in acted:continue
            if n in tx:
                if re.match(r"^(You (hit|miss|have slain|have destroyed|have killed|bite|smite))",tx): acted[n]='P'
                elif tx.startswith(('The '+n,n)) or tx.startswith('It '): 
                    if tx.startswith(('The '+n,n)): acted[n]='M:wake' if 'wakes up' in tx else 'M'
    firstmon=min(mons.values()) if mons else None
    return dict(file=f,depth=dep,t0=t0,t1=t1,feel=feel,arr=arr,mons=mons,acted=acted,seg=(i0,i1))
if __name__=='__main__':
    import sys
    res={}
    for p in sorted(glob.glob('/projectnb/jbrcs/mangband/runs/pilot/dive04/levels/*.txt')):
        f=os.path.basename(p)
        try:res[f]=analyse(f)
        except Exception as e:print('ERR',f,e)
    pickle.dump(res,open('res.pkl','wb'))
    print(len(res))
