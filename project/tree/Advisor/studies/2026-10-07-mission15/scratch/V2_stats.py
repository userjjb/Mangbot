import re,collections
exec(open("V2_parse.py").read().split("rows=[]")[0])
raw=collections.Counter()
t7=[v for v in V if v["typ"]==7]; t8=[v for v in V if v["typ"]==8]; t9=[v for v in V if v["typ"]==9]
print(len(t7),len(t8),len(t9))
def cnt(vs,ch): return max(("".join(v["D"]).count(ch)) for v in vs)
for ch in "&@98,X+^*": print(ch,"max in t7:",cnt(t7,ch),"t7 vaults with any:",sum(1 for v in t7 if ch in "".join(v["D"])))
print("t7 with @:",[ (v["name"],"".join(v["D"]).count("@")) for v in t7 if "@" in "".join(v["D"])])
print("t7 with 9:",[ (v["name"],"".join(v["D"]).count("9")) for v in t7 if "9" in "".join(v["D"])][:60])
print("t7 rating hist",sorted(collections.Counter(v["rat"] for v in t7).items()))
print("t7 w/ X interior",[v["name"] for v in t7 if "X" in "".join(v["D"])])
print("t7 total area range",min(v["h"]*v["w"] for v in t7),max(v["h"]*v["w"] for v in t7))
print("t8 count w/ typ9",[v["name"] for v in t9])
# odds
for D in range(5,21):
    p=(D/200)**2
    greater=0.10 if D>=10 else 0
    lesser=0.15 if D>=10 else 0.25
    nl=50*p*lesser; ng=50*p*greater
    print(D,D*50,"E[lesser attempts]=%.3f E[greater]=%.3f P(>=1 lesser)=%.1f%% P(>=1 greater)=%.1f%%"%(nl,ng,100*(1-(1-p*lesser)**50),100*(1-(1-p*greater)**50)))
