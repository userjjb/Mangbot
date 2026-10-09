import pickle,re,collections,bisect,statistics,datetime,csv
dec,evs,st=pickle.load(open('d4.pkl','rb'))
D=lambda m,d,h,mi,s=0:datetime.datetime(2026,10 if True else 0,d,h,mi,s).timestamp()
hp={};cur=None;flags={}
for l in open('/projectnb/jbrcs/mangband/github/lib/edit/monster.txt'):
    l=l.rstrip('\n')
    if l.startswith('N:'): cur=l.split(':',2)[2].lower(); flags[cur]=''
    elif l.startswith('I:') and cur and cur not in hp:
        p=l.split(':'); m=re.match(r'(\d+)d(\d+)',p[2]); n,s=int(m.group(1)),int(m.group(2)); hp[cur]=[n*(s+1)/2.0,n*s]
    elif l.startswith('F:') and cur: flags[cur]+=l
def mhp(n):
    n=n.lower()
    if n not in hp: return None
    return hp[n][1] if 'FORCE_MAXHP' in flags[n] else hp[n][0]
# audit timeline
A=[(j['t'],j['blows'],j['stats']['STR'][0],j['clvl']) for j in dec if j['kind']=='audit_check' and j['t']>1791400000 and j.get('blows')]
At=[a[0] for a in A]
MW=D(0,7,17,52,14); TD=D(0,7,22,58,52)
def weapon(ep):
    if ep<MW: return 'Sabre(1d7)'
    if ep<TD: return 'MainGauche(+0,+1)'
    return 'MainGauche(+0,+2)'
def mission(ep):
    if D(0,7,17,52)<=ep<=D(0,7,18,25): return 'M14'
    if D(0,7,22,42)<=ep<=D(0,7,23,36): return 'M15'
    if D(0,8,15,31)<=ep<=D(0,8,16,8): return 'M16'
    return 'other'
msgs=sorted([e for e in evs if e['ev']=='message' and e['ep']>1791400000],key=lambda e:e['ep'])
sw=collections.defaultdict(list);rows=[]
for e in msgs:
    t=e['text'];ep=e['ep']
    m=re.match(r'You (hit|miss) (?:the )?(.*?)\.$',t)
    if m: sw[m.group(2)].append((ep,m.group(1)=='hit')); continue
    m=re.match(r'You have (slain|destroyed) (?:the )?(.*?)\.$',t)
    if not m: continue
    n=m.group(2); L=sw.pop(n,[]); seq=[]
    for s in reversed(L):
        if not seq or seq[-1][0]-s[0]<=6: seq.append(s)
        else: break
    seq.reverse()
    if not seq: continue
    h=mhp(n)
    if h is None: continue
    i=bisect.bisect_right(At,ep)-1
    if i<0: continue
    rows.append(dict(time=datetime.datetime.fromtimestamp(ep).strftime('%m-%d %H:%M:%S'),ep=ep,mission=mission(ep),monster=n,swings=len(seq),hits=sum(s[1] for s in seq),hp=h,blows=A[i][1],str=A[i][2],weapon=weapon(ep)))
with open('E3_kills.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow('time,mission,monster,swings,hits,mon_hp_avg,blows,str,weapon'.split(','))
    for r in rows: w.writerow([r['time'],r['mission'],r['monster'],r['swings'],r['hits'],round(r['hp'],1),r['blows'],r['str'],r['weapon']])
pickle.dump(rows,open('E3_rows.pkl','wb'))
def summ(key,minhp=8):
    g=collections.defaultdict(list)
    for r in rows:
        if r['hp']>=minhp and r['mission']!='other': g[key(r)].append(r)
    for k,v in sorted(g.items()):
        sh=sum(r['hits'] for r in v); ss=sum(r['swings'] for r in v); hpv=sum(r['hp'] for r in v)
        print(k,'n=%d'%len(v),'swings',ss,'hits',sh,'hit=%.2f'%(sh/ss),'hp/hit=%.2f'%(hpv/max(sh,1)),'hp/swing=%.2f'%(hpv/ss),'med_sw=%.1f'%statistics.median(r['swings'] for r in v),'avgHP=%.0f'%(hpv/len(v)))
print('by mission,weapon,blows,str'); summ(lambda r:(r['mission'],r['weapon'],r['blows'],r['str']))
print('by weapon,blows,str'); summ(lambda r:(r['weapon'],r['blows'],r['str']))
print('by mission'); summ(lambda r:r['mission'])
print('all rows',len(rows),collections.Counter(r['mission'] for r in rows))
print('hp>=20'); summ(lambda r:(r['weapon'],r['blows'],r['str']),20)
