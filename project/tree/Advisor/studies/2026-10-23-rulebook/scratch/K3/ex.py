import re
src=open('/projectnb/jbrcs/mangband/github/src/server/tables.c').read()
m=re.search(r'u16b level_speeds\[128\]\s*=\s*\{(.*?)\};',src,re.S)
nums=[int(x) for x in re.findall(r'\b\d{4,5}\b',re.sub(r'/\*.*?\*/','',m.group(1)))]
print(len(nums))
FPS=75
for d in [0,1,5,10,15,20,30,40,50,60,70,90,100,127]:
    ls=nums[d]*5
    t=ls//1000
    move=ls/1000/FPS  # s per player turn at normal speed (1000 energy/tick)
    tr=int(t/(5.0)); trest=int(t/10.0); tlow=int(t/0.2)
    print(d,ls,t,round(t/FPS,3),'run',round(ls/5000/FPS,3),'rest_ticks',trest,'rest_dt',round(trest/FPS,3),'recall mean s',round(24.5*t/FPS,1),'rest',round(24.5*trest/FPS,2), 'food/s',round(20*FPS/(10*t),2),'torch2500 s',round(2500*t/FPS))
