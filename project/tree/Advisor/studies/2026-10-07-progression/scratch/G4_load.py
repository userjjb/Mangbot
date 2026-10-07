import json,re,datetime,pickle
R='/projectnb/jbrcs/mangband/runs/pilot/'
def load(d):
    st=[];dec=[]
    for l in open(R+d+'/decisions.jsonl'):
        j=json.loads(l); dec.append(j)
        if j['kind']=='attention' and j['what']=='started': st.append(j['t'])
    evs=[json.loads(l) for l in open(R+d+'/events.jsonl')]
    nseg=1;p=-1
    for j in evs:
        if j['t']<p-1: nseg+=1
        p=j['t']
    print(d,'starts',len(st),'segments',nseg)
    st2=st[len(st)-nseg:]
    seg=0;prev=-1;out=[]
    for j in evs:
        if j['t']<prev-1: seg+=1
        prev=j['t']
        j['ep']=st2[seg]+j['t']; out.append(j)
    return dec,out,st
if __name__=='__main__':
    for d in ['dive03','dive04']:
        dec,evs,st=load(d)
        pickle.dump((dec,evs,st),open('/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch/%s.pkl'%d,'wb'))
