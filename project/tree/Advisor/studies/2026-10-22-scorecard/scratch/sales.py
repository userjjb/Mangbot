from common import *
OWN={"Bilbo":(153,47),"Rincewind":(153,47),"Snafu":(152,48),"Lyar-el":(157,43),"Kon-Dar":(135,65),"Darg-Low":(156,44),"Decado":(157,43),"Mauglin":(162,38),"Ithyl-Mak":(145,55),"Arndal":(160,40),"Tarl":(160,40),"Oglign":(162,38),"Ludwig":(154,46),"Gunnar":(155,45),"Delilah":(157,43),"Keldon":(159,41),"Mauser":(161,39),"Wizzle":(155,45),"Ga-nat":(161,39),"Vella":(156,44),"Ariel":(160,40),"Buggerby":(158,42),"Inglorian":(155,45),"Luthien":(170,30),"Histor":(None,None)}
evs=[d for d in events() if 'epoch' in d]
def norm(s):
    s=re.sub(r'^(an?|the|\d+) ','',s.strip()); return s
rows=[]
laststore=None
for i,d in enumerate(evs):
    if d['ev']=='store': laststore=d
    if d['ev']=='message' and d['text'].startswith('You sold'):
        m=mission(d['epoch'])
        if not m: continue
        mm=re.match(r'You sold (.*) for (\d+) gold\.',d['text'])
        item,got=mm.group(1),int(mm.group(2))
        # shop: last store before
        shop=laststore
        # next store after with item
        ask=None;qty=1
        n=re.match(r'(\d+) ',item); qty=int(n.group(1)) if n else 1
        key=norm(item)
        key1=re.sub(r'^\d+ ','',item)
        for e in evs[i:i+4000]:
            if e['ev']=='store' and e['epoch']-d['epoch']<60:
                for it in e['items']:
                    nm=it['name']
                    if norm(nm).replace('~','')==key or norm(nm).startswith(key[:25]) :
                        ask=(it['price'],nm); break
                if ask: break
            if e['epoch']-d['epoch']>60: break
        own=shop['owner'].split(' the ')[0].split(' ')[0] if shop else None
        rows.append((m,d['epoch'],item,got,shop['name'] if shop else None,shop['owner'] if shop else None,ask))
import json
for r in rows: print(r[0],hm(r[1]),r[2],'|',r[3],'|',r[4],r[5],'|',r[6])
