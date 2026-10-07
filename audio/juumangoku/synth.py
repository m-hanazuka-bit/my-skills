import numpy as np, wave
SR=44100; rng=np.random.default_rng(7)
def save(p,x,st=False):
    x=x/np.max(np.abs(x))*0.89
    if x.ndim==1: x=np.stack([x,x],1)
    w=wave.open(p,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((x*32767).astype(np.int16).tobytes()); w.close()
def lp(x,a):  # one-pole lowpass
    y=np.empty_like(x); s=0.
    for i,v in enumerate(x): s+=a*(v-s); y[i]=s
    return y
def bp(x,fc,q):  # biquad bandpass
    w0=2*np.pi*fc/SR; al=np.sin(w0)/(2*q); b=[al,0,-al]; a=[1+al,-2*np.cos(w0),1-al]
    y=np.zeros_like(x); x1=x2=y1=y2=0.
    for i,v in enumerate(x):
        o=(b[0]*v+b[1]*x1+b[2]*x2-a[1]*y1-a[2]*y2)/a[0]; x2,x1=x1,v; y2,y1=y1,o; y[i]=o
    return y
def reverb(x,mix=0.35,dec=1.8):
    n=int(SR*dec); ir=rng.standard_normal(n)*np.exp(-6.9*np.arange(n)/n)
    ir=lp(ir,0.35); L=np.convolve(x,ir)[:len(x)+n]; R=np.convolve(x,np.roll(ir,331))[:len(x)+n]
    d=np.pad(x,(0,n))[:len(L)]; s=max(np.abs(L).max(),1e-9)/max(np.abs(d).max(),1e-9)
    return np.stack([d+mix*L/s,d+mix*R/s],1)

# ---- shakuhachi: one long note, scoop up from ~630Hz to ~690Hz (meri->kari), breathy, yuri vibrato
def shakuhachi(dur=3.6,f0=345.):
    t=np.arange(int(SR*dur))/SR
    scoop=f0*0.913+(f0-f0*0.913)*(1-np.exp(-t/0.09))
    vib_depth=np.clip((t-0.9)/0.8,0,1)*6.0          # yuri grows in later
    f=scoop+vib_depth*np.sin(2*np.pi*5.2*t)+1.5*lp(rng.standard_normal(len(t)),0.0005)*40
    ph=2*np.pi*np.cumsum(f)/SR
    env=np.minimum(1,t/0.06)*np.exp(-np.clip(t-0.35,0,None)*0.55)
    env*=np.clip((dur-t)/0.6,0,1)**1.5
    env*=1+0.08*np.sin(2*np.pi*0.7*t)
    tone=np.sin(ph)+0.07*np.sin(2*ph+0.3)+0.05*np.sin(3*ph+1.1)+0.015*np.sin(4*ph)
    breath=rng.standard_normal(len(t))
    breath=bp(breath,f0*1.0,6)*0.9+bp(breath,f0*2,5)*0.4+bp(breath,3000,0.7)*0.25
    breath*=(0.35+1.8*np.exp(-t/0.12))            # muraiki-like breath burst on attack
    chiff=bp(rng.standard_normal(len(t)),1800,1.2)*np.exp(-t/0.03)*3
    x=env*(tone+0.22*breath/np.std(breath))+chiff*np.minimum(1,t/0.004)
    return x
# ---- small-bird "chi" calls: fast downward sweep ~4.9k -> 3.0k in ~70ms
def chirp(f1=4900,f2=3000,d=0.07):
    t=np.arange(int(SR*d))/SR; f=f2+(f1-f2)*np.exp(-t/(d*0.45))
    env=np.minimum(1,t/0.005)**2*np.exp(-t/(d*0.5))*np.clip((d-t)/0.01,0,1)
    ph=2*np.pi*np.cumsum(f)/SR
    return env*(np.sin(ph)+0.12*np.sin(2*ph))
def birds(dur=4.0,times=None):
    x=np.zeros(int(SR*dur))
    for tt,f1,f2,d,a in times:
        c=chirp(f1,f2,d)*a; i=int(tt*SR); x[i:i+len(c)]+=c[:len(x)-i]
    return x

sh=shakuhachi(); sh_st=reverb(sh,0.45,2.2)
calls=[(0.20,4950,3050,.07,1),(0.52,4900,3000,.075,.9),(1.10,4300,3500,.05,.5),(1.33,4100,3200,.06,.7),
       (1.48,4950,3100,.05,.6),(2.25,5100,4800,.06,.35),(2.62,4800,3000,.07,.8),(2.95,4800,3000,.07,.75)]
bd=birds(3.6,calls); bd_st=reverb(bd,0.55,1.3)
amb=lp(rng.standard_normal(len(bd_st)),0.02)*0.004   # faint outdoor air
bd_st+=np.stack([amb,np.roll(amb,500)],1)
save('/home/user/my-skills/audio/juumangoku/shakuhachi.wav',sh_st)
save('/home/user/my-skills/audio/juumangoku/birds.wav',bd_st)
# combined, timing like the CM: shakuhachi at 0s, birds from ~2.5s
n=int(SR*7.5); mix=np.zeros((n,2)); mix[:len(sh_st)]+=sh_st/np.abs(sh_st).max()
o=int(SR*2.5); mix[o:o+len(bd_st)]+=0.55*bd_st[:n-o]/np.abs(bd_st).max()
save('/home/user/my-skills/audio/juumangoku/shakuhachi_birds_mix.wav',mix)
