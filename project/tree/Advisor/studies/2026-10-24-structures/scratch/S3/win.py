import csv,sys
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/data/structures')
import corridors as c
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/levels/'
lv=[r for r in csv.DictReader(open('/projectnb/jbrcs/mangband/Advisor/data/structures/corridor_levels.csv')) if int(r['n1'])>0]
for r in lv:
    head,rows=c.load(D+r['file'])
    rs=[x for x in c.runs(rows,5) if x['width']==1]
    print('=====',r['file'],head)
    for x in rs: print(' run',x)
    # windows
    done=[]
    for x in sorted(rs,key=lambda x:-x['length']):
        y,xx=x['y'],x['x']
        if any(abs(y-a)<8 and abs(xx-b)<20 for a,b in done): continue
        done.append((y,xx))
        L=x['length']
        if x['dir']=='h': y0,y1,x0,x1=y-6,y+7,xx-6,xx+L+6
        else: y0,y1,x0,x1=y-6,y+L+6,xx-12,xx+13
        y0=max(0,y0);x0=max(0,x0)
        print('--window y%d-%d x%d-%d'%(y0,y1,x0,x1))
        for yy in range(y0,min(66,y1)): print('%3d '%yy+rows[yy][x0:x1])
