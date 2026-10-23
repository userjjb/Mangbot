import re
E_='/projectnb/jbrcs/mangband/github/lib/edit/'
K={}  # (tval,name)->dict
cur=None
for l in open(E_+'object.txt'):
    l=l.rstrip('\n')
    if l.startswith('N:'):
        p=l.split(':',2); cur={'id':int(p[1]),'name':p[2]}
    elif l.startswith('I:') and cur is not None:
        p=l.split(':'); cur['tval']=int(p[1]);cur['sval']=int(p[2]);cur['pval']=int(p[3])
    elif l.startswith('W:') and cur is not None:
        p=l.split(':'); cur['cost']=int(p[4]); cur['wt']=int(p[3]); K[(cur['tval'],cur['name'])]=cur
    elif l.startswith('P:') and cur is not None:
        p=l.split(':'); cur['ac']=int(p[1]); cur['dice']=p[2]; cur['th']=int(p[3]); cur['td']=int(p[4]); cur['ta']=int(p[5])
EGO={};cur=None
for l in open(E_+'ego_item.txt'):
    l=l.rstrip('\n')
    if l.startswith('N:'):
        p=l.split(':',2); cur={'name':p[2]}; EGO[p[2]]=cur
    elif l.startswith('W:') and cur is not None:
        cur['cost']=int(l.split(':')[4])
ART={};cur=None
for l in open(E_+'artifact.txt'):
    l=l.rstrip('\n')
    if l.startswith('N:'):
        p=l.split(':',2); cur={'name':p[2]}; ART[p[2]]=cur
    elif l.startswith('W:') and cur is not None:
        cur['cost']=int(l.split(':')[4])
if __name__=='__main__':
    for k,v in K.items():
        if v['name'] in('Wonder','Light','Sleep Monsters','Acid','Resist Acid','Soft Leather Boots','Awl-Pike','Morning Star','Lucerne Hammer','Scimitar','Metal Cap','Stinking Cloud') : print(k,v)
    print(EGO.get('of Free Action'),EGO.get('of Venom'),[ (k,v) for k,v in EGO.items() if 'Free' in k or 'Venom' in k])
