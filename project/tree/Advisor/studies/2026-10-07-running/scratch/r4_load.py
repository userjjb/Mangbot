import json,pickle
P='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch/'
def load(d):
    dec,evs,st=pickle.load(open(P+d+'.pkl','rb'))
    # line numbers
    for i,j in enumerate(evs): j['ln']=i+1
    return dec,evs,st
