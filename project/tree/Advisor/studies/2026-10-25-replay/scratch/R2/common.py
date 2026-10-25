import json,datetime
from zoneinfo import ZoneInfo
tz=ZoneInfo('America/New_York')
RUN='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
def eps_(s,y='2026-'):return datetime.datetime.strptime(y+s,'%Y-%m-%d %H:%M:%S').replace(tzinfo=tz).timestamp()
def hms(t):return datetime.datetime.fromtimestamp(t,tz).strftime('%H:%M:%S')
IDX=[15,25,32,33,36,37,38,41,43]
E1='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-estimator/scratch/E1/episodes.csv'
def load_eps():
    import csv
    out={}
    for r in csv.DictReader(open(E1)):
        i=int(r['idx'])
        if i in IDX:
            t=eps_(r['start']);out[i]=dict(row=r,trig=t,end=t+float(r['duration_s']))
    return out
