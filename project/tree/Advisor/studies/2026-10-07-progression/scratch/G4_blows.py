import pickle,re,collections,bisect,statistics
exec(open('G4_an.py').read().split("rows=[]")[0])
# monster hp
hp={};cur=None
for l in open(HP_R):
    l=l.rstrip('\n')
    if l.startswith('N:'): cur=l.split(':',2)[2]
    elif l.startswith('I:') and cur and cur not in hp:
        p=l.split(':'); m=re.match(r'(\d+)d(\d+)',p[2])
        n,s=int(m.group(1)),int(m.group(2)); hp[cur.lower()]=(n*(s+1)/2.0,int(p[1]),n*s)
REG={'dive03':[(0,'MainGauche(1d5) 4bl'),(ts('09-26 05:00:50'),'Rapier(1d6) 3bl'),(ts('09-27 22:28:25'),'Rapier 2bl(drain)')],
 'dive04':[(0,'BroadSword 2bl'),(ts('09-28 01:41:41'),'?'),(ts('09-28 01:42:18'),'Dagger 4bl'),(ts('09-29 21:46:56'),'Dagger 3bl'),(ts('10-07 09:17:06'),'Dagger->Sabre 2bl')]}
def reg(nick,ep):
    L=REG[nick]; i=bisect.bisect_right([a for a,b in L],ep)-1; return L[i][1]
out=collections.defaultdict(list)
for nick in ['dive03','dive04']:
    dec,evs,st=pickle.load(open(nick+'.pkl','rb'))
    msgs=sorted([e for e in evs if e['ev']=='message'],key=lambda e:e['ep'])
    swings=collections.defaultdict(list)  # name->list of (ep,hit)
    last_kill_ep=0
    for e in msgs:
        t=e['text'];ep=e['ep']
        m=re.match(r'You (hit|miss) (?:the )?(.*?)\.$',t)
        if m:
            swings[m.group(2)].append((ep,m.group(1)=='hit')); continue
        m=re.match(r'You have (slain|destroyed) (?:the )?(.*?)\.$',t)
        if m:
            n=m.group(2); L=swings.pop(n,[])
            # keep swings within last 25 s, contiguous (gap<=6s)
            seq=[]
            for s in reversed(L):
                if not seq or seq[-1][0]-s[0]<=6: seq.append(s)
                else: break
            seq.reverse()
            if not seq: continue
            h=hp.get(n.lower())
            if not h: continue
            nsw=len(seq); nh=sum(1 for s in seq if s[1]); secs=ep-seq[0][0]
            out[(nick,reg(nick,ep))].append((n,h[0],h[2],nsw,nh,secs,clvl(nick,ep)))
print('regime | kills | median swings | median hits | median secs | sum(avgHP)/sum(swings) | sum(avgHP)/sum(hits) | swings/sec')
for k,v in sorted(out.items()):
    # restrict to monsters with avg hp>=8 (not one-shots)
    w=[x for x in v if x[1]>=8]
    if len(w)<3: print(k,'n=',len(v),'(<3 with hp>=8)'); continue
    print(k,'n=%d'%len(w),'med_sw=%.1f'%statistics.median(x[3] for x in w),'med_hits=%.1f'%statistics.median(x[4] for x in w),'med_secs=%.1f'%statistics.median(x[5] for x in w),
      'hp/swing=%.2f'%(sum(x[1] for x in w)/sum(x[3] for x in w)),'hp/hit=%.2f'%(sum(x[1] for x in w)/max(1,sum(x[4] for x in w))),'hitrate=%.2f'%(sum(x[4] for x in w)/sum(x[3] for x in w)),'sw/s=%.2f'%(sum(x[3] for x in w)/max(1,sum(x[5] for x in w))), 'avgHP=%.0f'%statistics.mean(x[1] for x in w))
# same species compare
sp=collections.defaultdict(lambda:collections.defaultdict(list))
for k,v in out.items():
    for x in v: sp[x[0]][k].append(x)
print('\nSpecies killed under >=2 regimes (n>=3 each): name hp | regime n med_swings med_secs')
for n,d in sp.items():
    ok={k:v for k,v in d.items() if len(v)>=3}
    if len(ok)>=2:
        print(n,round(list(ok.values())[0][0][1]),'|',' ; '.join('%s n=%d sw=%.1f s=%.1f'%(k[1],len(v),statistics.median(x[3] for x in v),statistics.median(x[5] for x in v)) for k,v in ok.items()))
