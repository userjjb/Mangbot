import csv,re
TV={16:'shot',17:'arrow',18:'bolt',19:'bow',20:'digging',21:'hafted',22:'polearm',23:'sword',30:'boots',31:'gloves',32:'helm',33:'crown',34:'shield',35:'cloak',36:'softarmor',37:'hardarmor',38:'dragarmor',39:'lite',40:'amulet',45:'ring'}
rows=[];cur=None
for ln in open('/projectnb/jbrcs/mangband/github/lib/edit/ego_item.txt'):
    ln=ln.rstrip('\n')
    if ln.startswith('N:'):
        _,i,n=ln.split(':',2); cur=dict(idx=i,name=n,slots=[],level='',rarity='',h=0,d=0,a=0,pval=0,cost='',flags=[],rating='',xtra='');rows.append(cur)
    elif cur is None: continue
    elif ln.startswith('X:'): _,r,x=ln.split(':'); cur['rating']=r;cur['xtra']=x
    elif ln.startswith('C:'): _,h,d,a,p=ln.split(':'); cur.update(h=h,d=d,a=a,pval=p)
    elif ln.startswith('W:'): _,l,r,w,c=ln.split(':'); cur.update(level=l,rarity=r,cost=c)
    elif ln.startswith('T:'): _,t,a,b=ln.split(':'); cur['slots'].append(f"{TV.get(int(t),t)}[{a}-{b}]")
    elif ln.startswith('F:'): cur['flags']+= [f.strip() for f in ln[2:].split('|') if f.strip()]
w=csv.writer(open('/projectnb/jbrcs/mangband/Advisor/studies/2026-10-23-rulebook/scratch/K1/K1_egos.csv','w'))
w.writerow('name,tval_slots,level,rarity,max_h,max_d,max_a,max_pval,cost,flags,idx,rating,xtra'.split(','))
for r in rows: w.writerow([r['name'],';'.join(r['slots']),r['level'],r['rarity'],r['h'],r['d'],r['a'],r['pval'],r['cost'],'|'.join(r['flags']),r['idx'],r['rating'],r['xtra']])
print(len(rows))
