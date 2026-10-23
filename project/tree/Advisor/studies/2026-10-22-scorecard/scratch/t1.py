from common import *
import sys
L=sys.argv[1]
for d in recs(L):
    k=d['kind']
    if k in('goal','attention','nav_cmd','nav_say','user_note'):
        s=d.get('goal') or d.get('detail') or (d.get('cmd'),d.get('args')) or ''
        print(hhmmss(d['t']),k,d.get('depth'),d.get('hp'),d.get('what',''),str(s)[:150])
