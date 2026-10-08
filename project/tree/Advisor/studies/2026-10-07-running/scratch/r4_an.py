import pickle,collections,datetime,csv,statistics as S
raw=pickle.load(open('r4_raw.pkl','rb'))
def surf(dep):
    if dep is None: return 'unk'
    if dep==0: return 'town'
    if dep<0 or dep>22: return 'wild'
    return 'dungeon'
def analyse(r):
    st=r['start']; p=r['poss']
    steps=0;cur=st;jump=0;maxj=0
    for ep,y,x,k in p:
        if cur is None or (y,x)!=cur:
            if cur is not None:
                dj=max(abs(y-cur[0]),abs(x-cur[1]))
                maxj=max(maxj,dj)
            steps+=1
        cur=(y,x)
    r['steps']=steps;r['end']=cur if p else st;r['maxjump']=maxj
    r['secs']=(p[-1][0]-r['ep']) if p else 0
    r['cycle']=(r['end_ack'][0]-r['ep']) if r['end_ack'] else None
    r['where']=surf(r['depth'])
    # displacement
    if st and r['end']:
        r['disp']=max(abs(st[0]-r['end'][0]),abs(st[1]-r['end'][1]))
    else: r['disp']=None
    return r
for d in raw:
    for r in raw[d][0]+raw[d][1]: analyse(r)
pickle.dump(raw,open('r4_an.pkl','wb'))
for d in raw:
    runs,walks=raw[d]
    print(d)
    c=collections.Counter((r['where'],min(r['steps'],10)) for r in runs)
    for w in ['town','wild','dungeon','unk']:
        print(w,[c[(w,s)] for s in range(11)])
    print('maxjump>1',sum(1 for r in runs if r['maxjump']>1),'lev',sum(r['lev'] for r in runs),'stopped',sum(1 for r in runs if r['stop']))
