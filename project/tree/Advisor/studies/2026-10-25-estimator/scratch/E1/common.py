import json,datetime,time
from zoneinfo import ZoneInfo
tz=ZoneInfo('America/New_York')
RUN='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
def ep(s):return datetime.datetime.strptime(s,'%Y-%m-%d %H:%M').replace(tzinfo=tz).timestamp()
def hms(t):return datetime.datetime.fromtimestamp(t,tz).strftime('%H:%M:%S')
def hmsd(t):return datetime.datetime.fromtimestamp(t,tz).strftime('%m-%d %H:%M:%S')
def missions():
    out=[]
    for m in json.load(open('/projectnb/jbrcs/mangband/runs/missions.json')):
        l=m['label']
        if l[0]=='m' and l[1:].isdigit() and 17<=int(l[1:])<=34:
            out.append((l,ep(m['start']),ep(m['end'])))
    return out
def eps_(s):return datetime.datetime.strptime(s,'%Y-%m-%d %H:%M:%S').replace(tzinfo=tz).timestamp()
