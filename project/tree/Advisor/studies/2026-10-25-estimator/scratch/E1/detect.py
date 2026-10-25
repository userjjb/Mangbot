import json,re,pickle,sys
from common import *
M=missions()
def mis(t):
    for l,a,b in M:
        if a<=t<=b+60:return l
recs=[]
for l in open(RUN+'decisions.jsonl'):
    d=json.loads(l)
    if M[0][1]<=d['t']<=M[-1][2]+60 and mis(d['t']):
        recs.append(d)
print(len(recs))
pickle.dump(recs,open('recs.pkl','wb'))
