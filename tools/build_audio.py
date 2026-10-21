"""Rebuild original quiet foley / uncanny sounds (not sampled human voices).

Music and Kenney interface sounds are separately credited downloaded assets.
This deterministic sound design uses only Python's standard library.
"""
from array import array
from pathlib import Path
import math
import random
import wave

ROOT = Path(__file__).resolve().parents[1]
RATE = 22050

def build(name, duration, mode, frequency=90):
    rng = random.Random(name)
    samples = array('h')
    low = 0.0
    for i in range(int(RATE*duration)):
        t=i/RATE
        noise=rng.uniform(-1,1)
        low=.94*low+.06*noise
        fade=min(1,t/.025,(duration-t)/.08)
        sine=lambda f: math.sin(2*math.pi*f*t)
        if mode=='tone':
            value=(sine(frequency)+.22*sine(frequency*2))*math.exp(-t*12)
        elif mode=='paper':
            value=noise*.35*(.5+.5*math.sin(t*65))*(math.sin(math.pi*t/duration)**.5)
        elif mode=='knock':
            local=t%.38
            value=(sine(125)+noise*.2)*math.exp(-local*65) if t<1.1 else 0
        elif mode=='metal':
            value=(sine(231)+.5*sine(571)+.35*sine(919))*math.exp(-t*3)
        elif mode=='steps':
            local=t%.52
            value=(low*3+sine(68)*.3)*math.exp(-local*40)
        elif mode=='water':
            value=low*2+math.sin(2*math.pi*(700*t+150*math.sin(t*19)))*.1
        elif mode=='electric':
            value=(noise*.35+sine(60)*.2)*(.5+.5*math.sin(t*30))
        elif mode=='breath':
            value=low*4*math.sin(math.pi*t/duration)**2+sine(57)*.12
        elif mode=='laugh':
            pulse=max(0,math.sin(t*19))**4
            value=pulse*(math.sin(2*math.pi*(180*t+20*math.sin(t*6)))+.25*noise)*.45
        elif mode=='cry':
            value=(math.sin(2*math.pi*(280*t+35*math.sin(t*2)))+.2*sine(563))*math.sin(math.pi*t/duration)*.45
        elif mode=='lion':
            value=(low*5+math.sin(2*math.pi*(48*t+5*math.sin(t*3)))*.35)*math.sin(math.pi*t/duration)**.6
        else:
            value=(sine(frequency)*.35+sine(frequency*1.021)*.2+low*.9)*math.sin(math.pi*t/duration)**.5
        samples.append(int(max(-.8,min(.8,value*fade*.32))*32767))
    with wave.open(str(ROOT/'data/audio'/f'{name}.wav'),'wb') as out:
        out.setparams((1,2,RATE,0,'NONE','not compressed'))
        out.writeframes(samples.tobytes())

if __name__=='__main__':
    for args in [('typing',.035,'tone',520),('coin',.22,'tone',1100),('switch',.07,'tone',140),
                 ('paper',.8,'paper'),('knock',1.2,'knock'),('metal',1.6,'metal'),
                 ('steps',2.5,'steps'),('water',1.5,'water'),('electric',.65,'electric'),
                 ('breath',3,'breath'),('laugh',1.25,'laugh'),('cry',2,'cry'),
                 ('lion',2.8,'lion'),('pump',3,'drone',65),('submerged',3,'drone',48),
                 ('tinnitus',2.2,'drone',1740),('unease',1.8,'drone',62),
                 ('drag',2,'paper'),('door',.8,'steps')]:
        build(*args)
    print('19 original sound effects rebuilt.')
