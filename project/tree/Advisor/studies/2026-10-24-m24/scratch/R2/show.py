import sys;sys.path.insert(0,'.')
from load import *
import datetime
dc=decs()
s=sys.argv[1];dur=float(sys.argv[2]);kinds=sys.argv[3].split(',');W_=int(sys.argv[4]) if len(sys.argv)>4 else 200
t0=datetime.datetime.strptime(s,'%m-%d %H:%M:%S').replace(year=2026,tzinfo=tz).timestamp()
for r in dc:
    if t0-5<=r['t']<=t0+dur and r['kind'] in kinds:
        if r['kind']=='nav_cmd' and r['cmd']=='status': continue
        if r['kind']=='attention' and r['what'] in('goal_done','interesting_item','tactic','lost'): continue
        d={k:v for k,v in r.items() if k not in('t','kind','pos','depth','crop','wait_report')}
        d['hp']=r['hp'][0]
        print(ts(r['t'])[6:],r['kind'],json.dumps(d)[:W_])
