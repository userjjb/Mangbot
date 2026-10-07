import re,csv
names=["Brass Lantern","Wooden Torch","Flask~ of Oil","Cure Light Wounds","Cure Serious Wounds","Cure Critical Wounds","Phase Door","Word of Recall","Teleportation","Enchant Weapon To-Hit","Enchant Weapon To-Dam","Enchant Armour","Main Gauche","Rapier","Dagger","Short Sword","Soft Leather Armour","Hard Leather Armour","Leather Shield","Hard Leather Cap","Leather Boots","Leather Gloves","Cloak","Ration","Boldness","Heroism","Berserk"]
cur=None;rows=[]
for i,l in enumerate(open('object.txt'),1):
    l=l.rstrip()
    if l.startswith('N:'):
        cur=dict(n=l,nl=i,tv=None,sv=None)
    elif l.startswith('I:') and cur:
        p=l.split(':');cur['tv']=p[1];cur['sv']=p[2]
    elif l.startswith('W:') and cur:
        cur['w']=l;cur['wl']=i
        for nm in names:
            if nm.lower() in cur['n'].lower():
                rows.append((nm,cur['n'],cur['tv'],cur['sv'],l.split(':')[4],cur['nl'],i,l))
for r in rows: print(r)
