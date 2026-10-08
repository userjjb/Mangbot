import pickle, datetime
steps=pickle.load(open('z1_steps.pkl','rb'))
def isdiag(d): return d[0]!=0 and d[1]!=0
segs=[]; i=0; n=len(steps)
while i<n-1:
    a=steps[i]['d']; b=steps[i+1]['d']
    contig = steps[i+1]['dt']<2
    if isdiag(a) and isdiag(b) and a!=b and contig and ((a[0]==b[0]) != (a[1]==b[1])):
        j=i+2
        while j<n and steps[j]['dt']<2 and steps[j]['d']==steps[j-2]['d']: j+=1
        if j-i>=4: segs.append((i,j)); i=j; continue
    i+=1
tot_steps=0;tot_time=0
print('segments (>=4 steps alternating two mirrored diagonals):',len(segs))
for a,b in segs:
    S=steps[a:b]; t=sum(s['dt'] for s in S[1:]); 
    runs=sum(1 for s in S if s['ack'] and s['ack'].startswith('custom .') and s['ackdt']<0.2)
    t0=datetime.datetime.fromtimestamp(S[0]['T']).strftime('%H:%M:%S')
    tot_steps+=len(S); tot_time+=t
    print(t0,'depth',S[0]['depth'],'steps',len(S),'from',S[0]['p'],'to',S[-1]['p'],'time %.1f'%t,'mean dt %.3f'%(t/(len(S)-1)),'run-cmd steps',runs)
print('total zig steps',tot_steps,'time %.1f'%tot_time)
ds=[s for s in steps if s['dt']<2]
print('all moving steps',len(ds), 'time %.0f'%sum(s['dt'] for s in ds))
