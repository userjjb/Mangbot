import sys,pickle,collections,csv,datetime,statistics as S;sys.path.insert(0,'.')
allr=pickle.load(open('r4_runs3.pkl','rb'))
f=lambda e:datetime.datetime.fromtimestamp(e).strftime('%Y-%m-%d %H:%M:%S')
def oc(r):
    s=r['steps']
    if r['where'] in('town','wild') and r['maxj']>=60: return 'left map (edge crossed)'
    if r['lev'] or r['maxj']>1: return 'level changed under run (recall/teleport/trapdoor)'
    if s==0: return 'no step before 0.5s timeout (fallback walk follows)'
    if s==1: return '1 tile, immediate (run ended after 1 step)' if r['firststep']<0.3 else '1 tile, late ~0.56s (arrives with fallback walk)'
    mon=False
    if r['mon']:
        ref=r['stops'][0] if r['stops'] else r['ep']+r['secs']
        mon=any(abs(ref-m)<0.3 or 0<=ref-m<0.6 for m in r['mon'])
    if r['stops']:
        o=r['over'];return 'multi-tile, pilot stop (+%d tile after stop sent)%s'%(min(o,2),', monster list changed' if mon else '')
    return 'multi-tile, ended by server'+(' [monster list changed]' if mon else '')
def ctx(r):
    w=r['where']
    if w=='town': return 'town-'+(r['dn'] or '?')
    if w=='wild': return 'wilderness'
    if r['steps']<=1: return 'dungeon-short'
    return 'dungeon-bend(corridor follow)' if r['ndirs']>1 else 'dungeon-straight'
with open('R4_runs.csv','w',newline='') as fh:
    w=csv.writer(fh);w.writerow(['nick','time','depth','start','end','squares','seconds','outcome','context','cite','secs_since_prev_step','cycle_s'])
    for r in allr:
        r['oc']=oc(r);r['ctx']=ctx(r)
        w.writerow([r['nick'],f(r['ep']),r['depth'],'%s'%(r['start'],),'%s'%(r['end'],),r['steps'],round(r['secs'],2),r['oc'],r['ctx'],'%s/events.jsonl:%d'%(r['d'],r['ln']),round(r.get('gap',-1),2),round(r['cycle'],2) if r['cycle'] is not None else ''])
pickle.dump(allr,open('r4_runs4.pkl','wb'))
def base(o): return o.split(' (')[0].split(' [')[0].split(',')[0] if not o.startswith('multi') else ('multi pilot-stop' if 'pilot' in o else 'multi server-ended')
c=collections.Counter((r['where'],base(r['oc'])) for r in allr)
for k,v in sorted(c.items()): print(k,v)
print([ (r['nick'],f(r['ep']),r['where'],r['ln']) for r in allr if r['oc'].startswith('left map')])
print([ (r['nick'],f(r['ep']),r['where'],r['depth'],r['ln']) for r in allr if r['oc'].startswith('level changed')])
