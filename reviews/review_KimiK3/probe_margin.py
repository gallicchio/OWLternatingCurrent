import numpy as np

# Linearized loop: plant  m s^2 d = +k_neg d - F ;  F = C(s) e (force units)
# C(s) = kp + ki/s + kd * s/(1+s/wd), plus 1-tick delay, plus coil L/R pole, plus sensor 20 kHz pole.
m = 3.6e-3; k_neg = 5.008; bw = 10.0; zeta = 0.7; ki_div = 8.0; dfilt = 50.0
wc = 2*np.pi*bw
kp = m*wc**2 + k_neg
kd = 2*zeta*m*wc
ki = kp*wc/ki_div
wd = 2*np.pi*dfilt
T = 1e-4
Lcoil, Rcoil = 30.1e-6, 2.76     # coil + bridge
wLR = Rcoil/Lcoil                # 91.7 krad/s = 14.6 kHz
wsens = 2*np.pi*20e3             # DRV5055 BW

def Ls(s):
    C = kp + ki/s + kd*s/(1+s/wd)
    G = 1.0/(m*s*s - k_neg)
    D = np.exp(-s*T)                      # 1 tick delay
    return C*G*D * 1/(1+s/wLR) * 1/(1+s/wsens)

ws = np.logspace(1, 6, 200000)
Lv = np.array([Ls(1j*w) for w in ws])
mag = np.abs(Lv)
i = np.argmin(np.abs(mag-1))
wgc = ws[i]
pm = 180 + np.degrees(np.angle(Lv[i]))
# gain margin: phase crossover
ph = np.unwrap(np.angle(Lv))
j = np.argmin(np.abs(ph + np.pi))
gm = -20*np.log10(mag[j])
print(f"with delay+coil+sensor: crossover {wgc/2/np.pi:.2f} Hz, phase margin {pm:.1f} deg, gain margin {gm:.1f} dB (at {ws[j]/2/np.pi:.0f} Hz)")
# without the driver/sensor extras
def Ls0(s):
    C = kp + ki/s + kd*s/(1+s/wd)
    return C/(m*s*s - k_neg)
Lv0 = np.array([Ls0(1j*w) for w in ws])
i0 = np.argmin(np.abs(np.abs(Lv0)-1))
print(f"controller+plant only:    crossover {ws[i0]/2/np.pi:.2f} Hz, phase margin {180+np.degrees(np.angle(Lv0[i0])):.1f} deg")
# how much phase do the extras cost at crossover?
extra = np.degrees(np.angle(Lv0[i0])) - np.degrees(np.angle(Lv[i0]))
print(f"phase lost to 1-tick delay + L/R pole + 20 kHz sensor at crossover: {-extra:.2f} deg")
# delay of 2 ticks (u applied at 75 us + 100 us sample)
def Ls2(s):
    C = kp + ki/s + kd*s/(1+s/wd)
    return C/(m*s*s-k_neg) * np.exp(-s*2*T) / (1+s/wLR) / (1+s/wsens)
Lv2 = np.array([Ls2(1j*w) for w in ws])
i2 = np.argmin(np.abs(np.abs(Lv2)-1))
print(f"with 2-tick delay:        crossover {ws[i2]/2/np.pi:.2f} Hz, phase margin {180+np.degrees(np.angle(Lv2[i2])):.1f} deg")
# kc error effect: true kc 6% low -> loop gain 6% low: crossover & PM
for kc_err in (1.0, 0.9, 0.85, 1.2):
    Lv3 = kc_err*Lv
    i3 = np.argmin(np.abs(np.abs(Lv3)-1))
    print(f"loop gain x{kc_err:.2f}:           crossover {ws[i3]/2/np.pi:5.2f} Hz, PM {180+np.degrees(np.angle(Lv3[i3])):.1f} deg")
