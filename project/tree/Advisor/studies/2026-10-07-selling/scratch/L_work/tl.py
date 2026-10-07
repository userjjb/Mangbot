import json,sys,datetime
R='/projectnb/jbrcs/mangband/runs/pilot/'
def run(d,out):
    st=[]
    for l in open(R+d+'/decisions.jsonl'):
        j=json.loads(l)
        if j['kind']=='attention' and j['what']=='started': st.append(j['t'])
    rows=[]
    seg=0;prev=-1
    evs=[json.loads(l) for l in open(R+d+'/events.jsonl')]
    nseg=1
    p=-1
    for j in evs:
        if j['t']<p-1: nseg+=1
        p=j['t']
    st=st[len(st)-nseg:]
    seg=0;prev=-1;depth=None
    for i,j in enumerate(evs):
        if j['t']<prev-1: seg+=1
        prev=j['t']
        ep=st[seg]+j['t']
        if j['ev']=='level': depth=j['depth']; txt='LEVEL %s'%depth
        elif j['ev']=='message': txt='MSG '+j['text']
        elif j['ev']=='confirm': txt='CONFIRM '+j['prompt']
        elif j['ev']=='store': txt='STORE '+j['name']+' '+str([ (x['name'],x['price']) for x in j['items']])[:0]
        else: continue
        rows.append((ep,'E',depth,txt))
    dep=None
    for l in open(R+d+'/decisions.jsonl'):
        j=json.loads(l)
        if j['kind']=='act':
            rows.append((j['t'],'A',j.get('depth'),'ACT %s | %s'%(j['cmd'],j['why'])))
        elif j['kind'] in('goal','note','attention') and j['kind']!='attention':
            rows.append((j['t'],'A',j.get('depth'),j['kind'].upper()+' '+str(j.get('goal') or j.get('text') or j)[:200]))
        elif j['kind']=='attention':
            rows.append((j['t'],'A',j.get('depth'),'ATT %s %s'%(j['what'],str(j.get('detail'))[:200])))
    rows.sort(key=lambda r:r[0])
    with open(out,'w') as f:
        for ep,s,dp,t in rows:
            f.write('%s d%s %s\n'%(datetime.datetime.fromtimestamp(ep).strftime('%m-%d %H:%M:%S'),dp,t))
for d in ['dive01','dive02','dive03','dive04']:
    run(d,d+'.tl')
