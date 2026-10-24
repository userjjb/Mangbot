import csv,re,sys
from collections import Counter
src='/projectnb/jbrcs/mangband/github/lib/edit/vault.txt'
ents=[];cur=None
for ln in open(src,encoding='latin-1'):
    ln=ln.rstrip('\n')
    if ln.startswith('N:'):
        _,i,name=ln.split(':',2);cur={'id':int(i),'name':name,'D':[]};ents.append(cur)
    elif ln.startswith('X:'):
        t,r,h,w=map(int,ln[2:].split(':'));cur.update(typ=t,rat=r,hgt=h,wid=w)
    elif ln.startswith('D:'):
        cur['D'].append(ln[2:])
PASS=set('.,&@98*^+')  # passable-ish
WALL=set('%#X')
rows=[]
for e in ents:
    h,w=e['hgt'],e['wid']
    txt=''.join(e['D'])
    mism = len(txt)!=h*w
    txt=txt.ljust(h*w)
    g=[txt[r*w:(r+1)*w] for r in range(h)]
    def at(r,c):
        if 0<=r<h and 0<=c<w: return g[r][c]
        return ' '
    cnt=Counter(txt)
    # rim cells
    rim=Counter();pierce=0;openrim=0
    for r in range(h):
        for c in range(w):
            ch=g[r][c]
            if ch==' ':continue
            nb=[(r-1,c,r+1,c),(r+1,c,r-1,c),(r,c-1,r,c+1),(r,c+1,r,c-1)]
            out=[n for n in nb if at(n[0],n[1])==' ']
            if out:
                rim[ch]+=1
                if ch=='%':
                    # outward neighbor space, inward passable
                    if any(at(n[2],n[3]) in PASS for n in out): pierce+=1
                elif ch in PASS: openrim+=1
    # corridors: passable cells with walls (or space) both perpendicular
    def iswall(ch): return ch in WALL or ch==' '
    best=0
    # horizontal runs
    for r in range(h):
        run=0
        for c in range(w+1):
            ok = c<w and g[r][c] in PASS and iswall(at(r-1,c)) and iswall(at(r+1,c))
            if ok: run+=1; best=max(best,run)
            else: run=0
    for c in range(w):
        run=0
        for r in range(h+1):
            ok = r<h and g[r][c] in PASS and iswall(at(r,c-1)) and iswall(at(r,c+1))
            if ok: run+=1; best=max(best,run)
            else: run=0
    npass=sum(cnt[k] for k in PASS)
    # corridor cells fraction
    cor=0
    for r in range(h):
        for c in range(w):
            if g[r][c] in PASS and ((iswall(at(r-1,c)) and iswall(at(r+1,c))) or (iswall(at(r,c-1)) and iswall(at(r,c+1)))): cor+=1
    mon=cnt['&']+cnt['@']+cnt['9']+cnt['8']
    exp_mon=mon+0.5*cnt[',']
    exp_obj=0.75*cnt['*']+cnt['9']+cnt['8']+0.5*cnt[',']
    rows.append(dict(id=e['id'],name=e['name'],type=e['typ'],rating=e['rat'],rows=h,cols=w,len_mismatch=int(mism),
      amp=cnt['&'],at=cnt['@'],nine=cnt['9'],eight=cnt['8'],comma=cnt[','],star=cnt['*'],trap=cnt['^'],secret_door=cnt['+'],
      pct=cnt['%'],hash=cnt['#'],X=cnt['X'],floor=cnt['.'],
      rim_pct=rim['%'],rim_hash=rim['#'],rim_X=rim['X'],rim_open=openrim,pierceable_pct=pierce,
      longest_1wide=best,corridor_cells=cor,passable=npass,
      mon_fixed=mon,exp_mon=exp_mon,exp_obj=exp_obj))
w=csv.DictWriter(open('/projectnb/jbrcs/mangband/Advisor/studies/2026-10-24-structures/scratch/S2/vaults.csv','w',newline=''),fieldnames=list(rows[0]))
w.writeheader();w.writerows(rows)
print(len(rows),Counter(r['type'] for r in rows),sum(r['len_mismatch'] for r in rows))

# --- second pass: what lies just inside the rim
extra={}
for e in ents:
    h,w=e['hgt'],e['wid']
    txt=''.join(e['D']).ljust(h*w)
    g=[txt[r*w:(r+1)*w] for r in range(h)]
    def at(r,c):
        return g[r][c] if 0<=r<h and 0<=c<w else ' '
    ins=Counter()
    for r in range(h):
        for c in range(w):
            if g[r][c]!='%': continue
            for dr,dc in((-1,0),(1,0),(0,-1),(0,1)):
                if at(r-dr,c-dc)==' ':
                    ins[at(r+dr,c+dc)]+=1
    tot=sum(ins.values()) or 1
    inside_open=sum(ins[k] for k in PASS)
    extra[e['id']]=dict(inward_floor=inside_open,inward_pct=ins['%'],inward_X=ins['X'],inward_hash=ins['#'],inward_total=tot)
rows2=[]
for r in rows: r.update(extra[r['id']])
w=csv.DictWriter(open('/projectnb/jbrcs/mangband/Advisor/studies/2026-10-24-structures/scratch/S2/vaults.csv','w',newline=''),fieldnames=list(rows[0]))
w.writeheader();w.writerows(rows)
cl=Counter()
for r in rows:
    t=8 if r['type']==9 else r['type']
    if r['inward_floor']>0: k='open to piercing (floor just inside rim)'
    elif r['inward_X']>0: k='sealed: perm rock X behind rim'
    elif r['inward_hash']>0: k='sealed-ish: # behind rim'
    else: k='other (double % etc)'
    cl[(t,k)]+=1
for k,v in sorted(cl.items()): print(k,v)
