import sys,pickle,collections,csv,datetime,statistics as S;sys.path.insert(0,'.')
from r4_runs import *
allr=pickle.load(open('r4_runs.pkl','rb'))
def oc(r):
    s=r['steps']
    if r['lev'] or (r['maxj']>1): return 'left map/level' if r['where']!='dungeon' else 'level change/teleport'
    if s==0:
        return 'no movement (run produced no step in window; fallback walk follows)' if r['endcmd'] and r['endcmd'].startswith('walk') else 'no movement'
    if s==1: return 'single step only'
    if r['stops']: return 'multi-step, pilot sent stop (walk 5)'
    return 'multi-step, ended by server'
def ctx(r):
    w=r['where']
    if w=='town': return 'town-'+(r['dn'] or '?')
    if w=='wild': return 'wilderness'
    if r['steps']<=1: return 'dungeon-short'
    return 'dungeon-bend(corridor follow)' if r['ndirs']>1 else 'dungeon-straight'
f=lambda e:datetime.datetime.fromtimestamp(e).strftime('%Y-%m-%d %H:%M:%S')
with open('R4_runs.csv','w',newline='') as fh:
    w=csv.writer(fh);w.writerow(['nick','time','depth','start','end','squares','seconds','outcome','context','cite','steps_after_stop','cycle_s'])
    for r in allr:
        r['oc']=oc(r);r['ctx']=ctx(r)
        w.writerow([r['nick'],f(r['ep']),r['depth'],'%s'%(r['start'],),'%s'%(r['end'],),r['steps'],round(r['secs'],2),r['oc'],r['ctx'],'%s/events.jsonl:%d'%(r['d'],r['ln']),r['over'] if r['stops'] else '',round(r['cycle'],2) if r['cycle'] is not None else ''])
pickle.dump(allr,open('r4_runs2.pkl','wb'))
c=collections.Counter((r['nick'],r['where'],r['oc']) for r in allr)
tl=collections.defaultdict(lambda:[0,0.0])
for r in allr:
    k=(r['where'],r['oc']);tl[k][0]+=1;tl[k][1]+=r['steps']
for k,v in sorted(c.items()): print(k,v)
print()
for k,v in sorted(tl.items()): print(k,v)
print()
c2=collections.Counter((r['ctx'],r['oc'][:20]) for r in allr)
for k,v in sorted(c2.items()): print(k,v)
