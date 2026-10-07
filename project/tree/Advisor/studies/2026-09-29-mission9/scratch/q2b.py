import json,datetime,re,sys
exec(open('q2.py').read().split("out=[]")[0])
def go(run,ks,pat):
    base='/projectnb/jbrcs/mangband/runs/pilot/%s/'%run
    D=load(base+'decisions.jsonl');E=load(base+'events.jsonl')
    starts=[i for i,d in enumerate(D) if d['kind']=='attention' and d['what']=='started']
    S=segs(E)
    for k in ks:
        a,b=S[k];ev=E[a:b]
        d0=starts[k];d1=starts[k+1] if k+1<len(starts) else len(D)
        dd=D[d0:d1]
        acts=[d for d in dd if d['kind']=='act']
        approx=dd[0]['t']-1.5;offs=[]
        for d in acts:
            for e in ev:
                if e['ev']=='ack' and e['cmd']==d['cmd'] and abs(e['t']+approx-d['t'])<6: offs.append(d['t']-e['t']);break
        offs.sort();off=offs[len(offs)//2]
        for d in acts:
            if re.search(pat,d['cmd']):
                print(run,k,F(d['t']),d['cmd'],'|',d['why'])
                for e in ev:
                    t=e['t']+off
                    if d['t']-0.1<=t<=d['t']+2.0 and e['ev']=='message': print('       ',e['text'])
                    if d['t']-0.1<=t<=d['t']+2.0 and e['ev']=='store': print('        STORE',e['name'],len(e['items']))
import sys
go(sys.argv[1],[int(x) for x in sys.argv[2].split(',')],sys.argv[3])
