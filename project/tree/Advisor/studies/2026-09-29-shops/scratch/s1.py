import re,collections,csv
G='/projectnb/jbrcs/mangband/github/'
d={}
for l in open(G+'src/server/mdefines.h',errors='replace'):
    m=re.match(r'#define\s+((?:TV|SV)_\w+)\s+(\d+)',l)
    if m: d[m.group(1)]=int(m.group(2))
kinds={};cur=None
for l in open(G+'lib/edit/object.txt',errors='replace'):
    l=l.rstrip()
    if l.startswith('N:'):
        p=l.split(':');cur=[int(p[1]),p[2]];
    elif l.startswith('I:') and cur:
        p=l.split(':');kinds[(int(p[1]),int(p[2]))]=cur
    elif l.startswith('W:') and cur:
        cur.append(l)
src=open(G+'src/server/init2.c').read()
a=src.index('static byte store_table[');b=src.index('static byte ironman_store_table')
blk=src[a:b]
parts=re.split(r'/\* (General Store|Armoury|Weaponsmith|Temple|Alchemy shop|Magic-User store|Black market)[^*]*\*/',blk)
rows=[]
for i in range(1,len(parts),2):
    name=parts[i];cnt=collections.Counter();order=[]
    for tv,sv in re.findall(r'\{\s*(TV_\w+|0)\s*,\s*(SV_\w+|\d+)\s*\}',parts[i+1]):
        t=d.get(tv,0) if tv!='0' else 0
        s=d[sv] if sv in d else int(sv)
        if (t,s) not in cnt: order.append((t,s,tv,sv))
        cnt[(t,s)]+=1
    tot=sum(cnt.values())
    for t,s,tv,sv in order:
        k=kinds.get((t,s))
        rows.append((name,tv,sv,t,s,k[1] if k else 'NOT FOUND',k[0] if k else '',k[2] if k and len(k)>2 else '',cnt[(t,s)]))
    print(name,tot,len(order))
with open('S1_stock.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['store','tval','sval','item_name','entries','tval_num','sval_num','k_idx','W_line'])
    for r in rows:w.writerow([r[0],r[1],r[2],r[5],r[8],r[3],r[4],r[6],r[7]])
for r in rows:print(r[0],'|',r[1],r[2],'|',r[5],r[6],r[7],'x',r[8])
