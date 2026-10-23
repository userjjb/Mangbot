import sys,pickle,csv,glob,os;sys.path.insert(0,'.')
from load import *
ev=pickle.load(open('ev.pkl','rb'))
arr=pickle.load(open('arr.pkl','rb'))
dc=decs()
def T(r): return r.get('epoch',r['T'])
for r in ev: r['E']=T(r)
levels=[r for r in ev if r['ev']=='level']
ATT=re.compile(r'(hits|misses|bites|claws|stings|touches|crushes|kicks|butts|spits|fires|casts|shoots|throws|breathes|You are hit|magic missile|You feel|crawls|drools|gazes|mumbles|points at you) ',re.I)
rows=[];det=[]
for lab,t0 in arr:
    t0=[r['E'] for r in ev if r['ev']=='message' and 'yanked downwards' in r['text'] and abs(r['T']-t0)<0.01][0]
    lv=[r for r in levels if abs(r['E']-t0)<3][0]
    depth=lv['depth']
    nxt=[r for r in levels if r['E']>t0+2][:1]
    leave=nxt[0]['E']-t0 if nxt else None
    leave_depth=nxt[0]['depth'] if nxt else None
    # how left
    how=''
    if nxt:
        ms=[r['text'] for r in ev if r['ev']=='message' and nxt[0]['E']-4<r['E']<=nxt[0]['E']+0.5 and re.search(r'yanked|maze|trap door|teleport',r['text'])]
        how=ms[-1] if ms else '?'
    def maxcnt(w):
        best=0;names=set()
        for r in ev:
            if r['ev']=='monlist' and t0<=r['E']<=t0+w:
                n=0
                for ln in r['lines']:
                    m=re.search(r"^(.*?) \('.'\)/\('.'\):\[(\d+)\]",ln)
                    if m: n+=int(m.group(2));names.add(m.group(1))
                best=max(best,n)
        return best,len(names)
    m30=maxcnt(30);m120=maxcnt(120)
    att120=sum(1 for r in ev if r['ev']=='message' and t0<=r['E']<=t0+120 and re.search(r'(hits you|misses you|bites you|fires|casts|shoots|You are hit|touches you|claws you|stings you|breathes|crushes you|spits)',r['text']))
    # hp
    h=[(r['t'],r['hp']) for r in dc if t0-15<=r['t']<=t0+300 and r.get('hp') and r['hp'][1]>1 and r.get('depth')==depth]
    hp0=[x for x in h if x[0]>=t0-1][:1]
    end=t0+300
    hmin=min(((a[0]/a[1],a[0],a[1]) for t,a in h if t<=end),default=None)
    hmin_lvl=min(((a[0]/a[1],a[0],a[1],t) for t,a in h if t<=end and (leave is None or t<=t0+leave)),default=None)
    wor=[r['E']-t0 for r in ev if r['ev']=='message' and 'air about you' in r['text'] and t0<r['E']<=t0+300]
    # lowest HP of whole stay incl beyond
    stairs_glyph=None
    fs=[f for f in glob.glob(D+'levels/*ft.txt')]
    # find file by start time
    fn=None
    for f in sorted(fs):
        b=os.path.basename(f)[:15]
        dt=datetime.datetime.strptime(b,'%Y%m%d-%H%M%S').replace(tzinfo=tz).timestamp()
        if abs(dt-t0)<4: fn=f
    sg=None;hdr=''
    if fn:
        txt=open(fn).read().split('\n')
        hdr=txt[0]
        body='\n'.join(txt[1:])
        sg=(body.count('>'),body.count('<'))
    row=dict(mission=lab,time=ts(t0),depth_level=depth,depth_ft=depth*50,hp_at_arrival=(hp0[0][1] if hp0 else (h[0][1] if h else None)),
      vis_max_30s=m30[0],vis_kinds_30s=m30[1],vis_max_120s=m120[0],vis_kinds_120s=m120[1],attack_msgs_120s=att120,
      stair_glyphs_final_map=sg,wor_reread_s=(round(wor[0]) if wor else ''),min_hp_pct_5min=(round(hmin[0]*100) if hmin else ''),min_hp=(f'{hmin[1]}/{hmin[2]}' if hmin else ''),
      min_hp_pct_on_level=(round(hmin_lvl[0]*100) if hmin_lvl else ''),secs_to_leave=(round(leave) if leave else ''),left_how=how,left_to=leave_depth,levelfile=hdr)
    rows.append(row)
w=csv.DictWriter(open('arrivals.csv','w'),fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for r in rows: print(r)
pickle.dump(rows,open('rows.pkl','wb'))
