import sys,pickle,collections,statistics as S;sys.path.insert(0,'.')
allr=pickle.load(open('r4_runs2.pkl','rb'))
g=collections.defaultdict(lambda:[0,0,0.0,0.0,0])
for r in allr:
    if r['steps']>=2 and r['cycle'] and r['cycle']<30 and not r['lev']:
        k=(r['ctx'] if not r['ctx'].startswith('dungeon') else 'dungeon-multi', 'pilotstop' if r['stops'] else 'server')
        v=g[k];v[0]+=1;v[1]+=r['steps'];v[2]+=r['secs'];v[3]+=r['cycle']
for k,v in sorted(g.items()): print(k,'runs',v[0],'tiles',v[1],'tiles/run %.1f'%(v[1]/v[0]),'in-run t/s %.2f'%(v[1]/v[2]),'effective (ack->next cmd) t/s %.2f'%(v[1]/v[3]))
# short-run chains: dungeon single/no-move: effective rate = cycles
sh=[r for r in allr if r['where']=='dungeon' and r['steps']<=1 and r['cycle'] and r['cycle']<2]
print('dungeon short runs',len(sh),'mean cycle %.3f'%S.mean(r['cycle'] for r in sh),'tiles per run %.2f'%(sum(r['steps'] for r in sh)/len(sh)))
sh0=[r for r in sh if r['steps']==0 and r['endcmd'] and r['endcmd'].startswith('walk')]
print(' no-step runs with fallback walk',len(sh0),'median cycle',S.median(r['cycle'] for r in sh0))
sh1=[r for r in sh if r['steps']==1]
print(' single-step runs',len(sh1),'median cycle',S.median(r['cycle'] for r in sh1), 'median first-step lag',S.median(r['firststep'] for r in sh1))
# overshoot after stop
ov=collections.Counter(min(r['over'],5) for r in allr if r['stops'] and r['steps']>=2)
print('steps after stop sent',sorted(ov.items()))
# per-ctx counts
c=collections.Counter()
for r in allr: c[(r['nick'],r['where'])]+=1
print(c)
# chains: runs per level of consecutive short runs
