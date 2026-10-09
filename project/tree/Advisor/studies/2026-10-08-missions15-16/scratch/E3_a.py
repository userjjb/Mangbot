import sys,json,re,datetime,collections,bisect,statistics,pickle
sys.path.insert(0,'/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch')
import G4_load
dec,evs,st=G4_load.load('dive04')
pickle.dump((dec,evs,st),open('d4.pkl','wb'))
f=lambda e:datetime.datetime.fromtimestamp(e).strftime('%m-%d %H:%M:%S')
for e in evs:
    if e['ev']=='message' and e['ep']>1791420000 and re.search(r'You are (wielding|wearing)|You were (wielding|wearing)|glows|wield',e['text']): print(f(e['ep']),e['text'])
