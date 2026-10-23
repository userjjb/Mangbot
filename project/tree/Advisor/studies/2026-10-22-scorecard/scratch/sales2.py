from common import *
from objcost import K
exec(open('sales.py').read().split("evs=[d")[0])  # OWN
evs=[d for d in events() if 'epoch' in d]
PRE={'Wand':65,'Staff':55,'Rod':66,'Ring':45,'Amulet':40,'Potion':75,'Scroll':70}
def costmodel(item):
    m=re.match(r'(?:an? |(\d+) )?(Wand|Staff|Rod|Ring|Amulet|Potion|Scroll)s? of ([^(\[{]+?)\s*(?:\((\d+) charges\))?\s*(\[[^\]]*\])?\s*$',item)
    if not m: return None
    q=int(m.group(1) or 1); kind=m.group(2); nm=m.group(3).strip(); ch=m.group(4)
    nm=nm.replace('Potions','Potion')
    k=K.get((PRE[kind],nm))
    if not k: return None
    v=k['cost']
    if ch: v+= (v//20)*int(ch)
    return v,k['cost'],q
rows=[];laststore=None
for i,d in enumerate(evs):
    if d['ev']=='store': laststore=d
    if d['ev']=='message' and d['text'].startswith('You sold'):
        mi=mission(d['epoch'])
        if not mi: continue
        mm=re.match(r'You sold (.*) for (\d+) gold\.',d['text'])
        item,got=mm.group(1),int(mm.group(2))
        sh=laststore; own=sh['owner'].split(' the ')[0].split(' ')[0]
        a,s=OWN[own]
        if a: A=a+5;S=s-5
        ask=None
        key=re.sub(r'^(an?|\d+) ','',item)
        for e in evs[i:i+3000]:
            if e['epoch']-d['epoch']>60: break
            if e['ev']=='store':
                for it in e['items']:
                    nm=re.sub(r'^(an?|\d+) ','',it['name']); nm=re.sub(r' \{\d+% off\}','',nm)
                    if nm.replace(' {','').startswith(key[:30]) or key.startswith(nm[:30]):
                        disc=re.search(r'\{(\d+)% off\}',it['name']); 
                        p=it['price']/(1-int(disc.group(1))/100) if disc else it['price']
                        ask=p;break
                if ask: break
        cm=costmodel(item)
        src=''
        if ask and a:
            V=ask/(A/100); src='listing ask %d / A%d%%'%(ask,A)
        elif cm:
            V=cm[0]; src='cost model'
        else: V=None
        exp=None if V is None else V*S/100
        q=1
        n=re.match(r'(\d+) ',item); 
        rows.append((mi,d['epoch'],item,got,sh['name'],own,A if a else None,S if a else None,V,exp,src))
if __name__=='__main__':
  for r in rows:
    mi,e,item,got,sn,own,A,S,V,exp,src=r
    print(mi,hm(e),item[:55],'|got',got,'|',own,A,S,'|V',None if V is None else round(V),'exp',None if exp is None else round(exp),'|',src)
