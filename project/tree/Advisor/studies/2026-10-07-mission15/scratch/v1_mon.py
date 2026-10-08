import re,sys
ents=[];cur=None
for l in open('/projectnb/jbrcs/mangband/github/lib/edit/monster.txt'):
    l=l.rstrip('\n')
    if l.startswith('N:'):
        cur={'n':l.split(':',2)[1],'name':l.split(':',2)[2],'F':'','S':'','B':[]};ents.append(cur)
    elif cur is None: continue
    elif l.startswith('G:'): cur['ch']=l.split(':')[1]
    elif l.startswith('I:'): cur['I']=l.split(':')[1:]
    elif l.startswith('W:'): cur['W']=l.split(':')[1:]
    elif l.startswith('F:'): cur['F']+=l[2:]
    elif l.startswith('S:'): cur['S']+=l[2:]
    elif l.startswith('B:'): cur['B'].append(l[2:])
def show(pred,maxl):
    global ents
    ents=[e for e in ents if 'W' in e]
    for e in sorted(ents,key=lambda e:int(e['W'][0])):
        if 'UNIQUE' in e['F'] or int(e['W'][0])>maxl: continue
        if pred(e):
            print(e['n'],e['name'],'L'+e['W'][0],'r'+e['W'][1],'spd',e['I'][0],'hp',e['I'][1],'sl',e['I'][4],'|', 'NM' if 'NEVER_MOVE' in e['F'] else '', 'MULT' if 'MULTIPLY' in e['F'] else '', e['S'][:60],'|',';'.join(e['B'])[:80])
mode=sys.argv[1];maxl=int(sys.argv[2])
if mode=='jelly': show(lambda e:e['ch'] in 'ijm,',maxl)
if mode=='orc': show(lambda e:e['ch']=='o',maxl)
if mode=='animal': show(lambda e:'ANIMAL' in e['F'],maxl)
if mode=='troll': show(lambda e:e['ch']=='T',maxl)
