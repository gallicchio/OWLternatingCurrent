/* familiar.h: the wireless familiars (PLAN.md C1): find a token on a perch, say
 * which it is, and light it.
 *
 * What is measured.  FAMn_ISENSE is the perch bridge's 4.8 V supply current, averaged
 * (RC-filtered).  The coil sees +4.8 V during leg A's pulse, -4.8 V during leg B's and 0
 * while both legs are low, so the supply delivers the coil's power: I = P / 4.8 V, with
 * P = sum over the odd harmonics of (Vn^2 / 2) G(n f), G = Re(Y) the perch's
 * conductance and Vn = (4 / (n pi)) 4.8 V sin(n pi duty); plus the drivers' own draw
 * (a few mA, independent of the duty).  An empty perch is almost purely inductive:
 * G = R1 / (R1^2 + (w L1)^2), small and falling as 1/f^2.  A token (a coil with a
 * C0G tank and two LEDs, the owl tuned to FAM_OWL_HZ, the cat to FAM_CAT_HZ) absorbs
 * power round its resonance: G has a peak there, but strongly coupled (k ~ 0.47) the
 * peak sits at the coupled mode, ft / sqrt(1 - k^2), 14-15 % above the token's own
 * tuning ft, where the perch current is 1.4-2.4 times an empty perch's.
 *
 * Each perch, on its own:
 *   IDLE      bridge off; every FAM_SWEEP_PERIOD_S a
 *   SWEEP     FAM_F_MIN_HZ..FAM_F_MAX_HZ in FAM_SWEEP_N log steps, each at two small
 *             duties (FAM_SWEEP_DUTY_LO and FAM_SWEEP_DUTY, 0.2 and 0.6 V of
 *             fundamental: a token stays dark); the difference of the two supply
 *             currents gives the conductance with the drivers' own draw cancelled, and
 *             the low one that draw itself;
 *   FIT       against the empty perch (a model, then learned from sweeps that found
 *             nothing): a conductance peak means a token; a fit of the coupled-tank model,
 *             including the 3rd harmonic (at these narrow pulses it is as strong as the
 *             fundamental, so the cat at 330 kHz also shows a peak at a third of its
 *             frequency, in the owl's band), gives its tuning ft and coupling; owl, cat
 *             or unknown by ft; a poor fit (a coin, a key: no resonance) is not driven;
 *   RAMP_UP   at ft, the delivered power (5 V x (supply current - the drivers' draw))
 *             rises smoothly to FAM_P_TARGET_W, closed loop; the duty never exceeds what
 *             would put FAM_CAP_MARGIN x FAM_I_MAX_A into an EMPTY perch at that frequency.
 *             At and below ft a token only raises the perch's impedance, so this cap holds
 *             the perch current under FAM_I_MAX_A whether the token is there or not
 *             (which is why it drives at ft, not at the conductance peak above it, where
 *             the token would draw more current than the cap allows for);
 *   DRIVE     holds it at ft (the token's own coil and C0G capacitor: it does not drift;
 *             moving the token changes the coupling, which moves the conductance peak, not
 *             ft); the frequency is dithered +-FAM_DITHER at 100 Hz with the drive
 *             compensated so the delivered power (and the light) stays steady, and the
 *             conductance's local slope (+5 to +13 at ft, about -2 on an empty perch)
 *             notices the token leave, as does the conductance falling back toward the
 *             empty perch's;
 *   RAMP_DOWN when it leaves or the perch is switched off.
 *
 * Why power, not duty: the same power gives about the same light whatever the token's
 * placement on the perch (coupling), and it bounds the token's own heating (most of the
 * power is lost in its coil: ~0.2 W, a few kelvin in a printed figurine).
 *
 * How the glue calls it (core 0): fam_step() every ~1 ms per perch, with FAMn_ISENSE as
 * amps of 5 V supply current (after FAM_ISENSE_V_PER_A) and what it actually applied
 * (frequency and duty after the PWM's quantisation; NULL: as commanded).  It sets the
 * bridge from the returned command: phase-correct PWM at freq_hz, leg A's pulse centred
 * on the period's start, leg B's (inverted) on its middle, each duty x period long.
 * FAM_EN is on while either perch's command is enabled.  For a sweep report the glue
 * may read state, who, f[] (Hz), y[] (measured conductance, S) and base[] (the empty
 * perch's, S).
 * Portable C (no SDK): test/test_familiar.c runs it against a simulated perch.
 */
#pragma once
#include <stdbool.h>

/* ---- tunables ---------------------------------------------------------------------- */
#define FAM_SWEEP_N            32         /* [CHOICE] 4.6 % steps from 100 to 400 kHz (48 until 2026-11-07: a put-down token took 4 s to relight) */
#define FAM_SWEEP_DUTY         0.030f     /* [CHOICE] the sweep's upper level: tokens stay dark ... */
#define FAM_SWEEP_DUTY_LO      0.010f     /* ... and its lower one */
#define FAM_BASE_SLACK         1.6f       /* [CHOICE] an empty perch may read up to this x the baseline */
#define FAM_SETTLE_S           0.004f     /* [ASSUMED] ISENSE's filter settles in 4 ms (tau <= 1 ms) */
#define FAM_AVG_N              8          /* [CHOICE] samples averaged per level (1 ms each) */
#define FAM_SWEEP_PERIOD_S     0.2f       /* [CHOICE] an empty perch looks this often (the sweep itself takes 0.5 s) */
#define FAM_P_TARGET_W         0.25f      /* [CHOICE] delivered power when lit */
#define FAM_CAP_MARGIN         0.92f      /* [CHOICE] the cap aims this far under FAM_I_MAX_A */
#define FAM_RAMP_S             0.8f       /* [CHOICE] dark to lit: orange first, then violet (2.5 s until 2026-11-07) */
#define FAM_RAMP_DOWN_S        0.5f
/* Live mode's presence probe (bench 2026-11-11, the fam_scan records in results/2026-11-11).
 * At the live drive (the token's design tuning) a token on its target changes the perch's
 * supply current by nothing: it is where the change turns from negative (below) to
 * positive (above).  At the coupled mode, ft / sqrt(1 - k^2) with k ~0.75 for a token
 * lying on the copper, about 1.5 ft, it draws several times an empty perch's current
 * even at a low duty: owl perch at 213 kHz, duty 0.05, 1.8 mA empty and 12.4 mA with the
 * owl; the cat's mode (455 kHz) is above the PWM's range, so the cat perch looks at its
 * 3rd-harmonic image, 152 kHz: 2.5 mA empty, 11.0 mA with the cat.  Every
 * FAM_PROBE_PERIOD_S the live drive steps aside for a short probe there, at two duties
 * (as a sweep's step): their currents' difference, with the drivers' own draw cancelled,
 * against an empty perch's (modelled over the 1st, 3rd and 5th harmonics, then learned). */
#define FAM_PROBE_PERIOD_S     3.0f       /* [Jason 2026-11-11] the token breathes: its drive fades down and
                                              back up once in this, raised-cosine, and the probe sits in
                                              the trough (a probe every 0.5 s made the tokens blink:
                                              "annoying"); a token is seen, or seen to leave, within this */
#define FAM_BREATH_MIN         0.3f       /* [CHOICE] the trough's duty, a fraction of the cap: about a
                                              fifth of the power, near the probe's own glow */
#define FAM_PROBE_RATIO        1.5f       /* [BENCH 2026-11-11] the coupled mode over the design tuning */
#define FAM_PROBE_DUTY         0.06f      /* [BENCH 2026-11-11] the upper level ... */
#define FAM_PROBE_DUTY_LO      0.03f      /* ... and the lower (not lower: the token would dip) */
#define FAM_PROBE_SETTLE_S     0.006f     /* ISENSE's filter from the live drive's 60 mA to the probe's 2 mA */
#define FAM_PROBE_AVG_S        0.004f
#define FAM_PROBE_ON           2.5f       /* [CHOICE] present above this x an empty perch's difference ... */
#define FAM_PROBE_ON_MIN_A     0.003f     /* [BENCH 2026-11-11] ... and above this: empty perches read 0.3-0.9 mA
                                              (owl) and 1.4-1.6 (cat), and each was once taken for a token
                                              against 2.5 x its modelled empty alone; tokens read 6-13 mA */
#define FAM_PROBE_OFF          0.35f      /* [BENCH 2026-11-11] ... and gone below this x the token's own:
                                              owl 10-13 mA on, 0.4-1.5 off; cat 11-12 on, 1.8 off (the
                                              empty perch's model is 1.4-2.7 x low, so not against that) ... */
#define FAM_PROBE_OFF_EMPTY    1.5f       /* ... or below this x an empty perch's (a weakly coupled token) */
#define FAM_PROBE_LEARN        0.1f       /* [CHOICE] each empty probe moves the learned empty difference this far */
#define FAM_DITHER             0.01f      /* [CHOICE] +-1 % frequency dither in DRIVE ... */
#define FAM_DITHER_HALF_S      0.005f     /* ... 5 ms each side: 100 Hz */
#define FAM_L1_H               30.3e-6f   /* [SIM] gen/coils.py: the perch coil as drawn (familiar.py's
                                             idealised 28.5 uH until the review of 2026-10-09) */
#define FAM_R1_OHM             4.2f       /* [SIM] familiar.py: the perch coil's resistance, 150-330 kHz.
                                             The UCC27524's own output resistance (ROH 5 ohm typical at
                                             12 V, more at 4.8 V) is in series with it and in no model:
                                             measure the loop on the first board and fold it in here */

typedef enum { FAM_NONE = 0, FAM_OWL, FAM_CAT, FAM_UNKNOWN } fam_who;
typedef enum { FAM_ST_OFF = 0, FAM_ST_IDLE, FAM_ST_SWEEP, FAM_ST_FIT, FAM_ST_RAMP_UP, FAM_ST_DRIVE,
               FAM_ST_RAMP_DOWN, FAM_ST_LIVE } fam_state;
enum { FAM_EV_NONE = 0, FAM_EV_ARRIVED, FAM_EV_LEFT };

typedef struct {
    bool enable;          /* bridge on (else both legs low) */
    float freq_hz;
    float duty;           /* 0 .. 0.5: each leg's pulse, a fraction of the period */
} fam_cmd;

typedef struct {
    int kind;             /* FAM_EV_* */
    int perch;
    fam_who who;
    float freq_hz;        /* the token's tuning */
} fam_event;

typedef struct {
    int index;
    bool enabled;
    fam_state state;
    float t_state;               /* when the state began */
    float t_last_sweep;
    fam_cmd cmd;
    /* sweep: two levels per frequency */
    float f[FAM_SWEEP_N];        /* Hz */
    float y[FAM_SWEEP_N];        /* measured conductance, S (gain of ISENSE included) */
    float base[FAM_SWEEP_N];     /* the empty perch's, S */
    float iq[FAM_SWEEP_N];       /* the drivers' own draw at each frequency, A */
    float w3[FAM_SWEEP_N];       /* the 3rd harmonic's weight in each conductance reading */
    int base_learned;            /* sweeps that found nothing and taught the baseline */
    int step, level, n_avg;
    float acc, acc_v1sq, i_lo, v1sq_lo, v3sq_lo;
    float t_step;
    /* fit (a few candidates per call) */
    float dg[FAM_SWEEP_N];       /* conductance above the empty perch's */
    float ge1[FAM_SWEEP_N], ge3[FAM_SWEEP_N];  /* the empty perch's model at f and 3 f */
    float gain;                  /* the fitted empty-perch scale (ISENSE's gain x R1's error) */
    float s_bb, s_yb, s_yy;      /* sums the fit's candidates share */
    float fit_a;                 /* the fitted scale (ISENSE's gain) */
    float base_scale;            /* the baseline against the model */
    int n_base;                  /* fit bases (peak frequencies, and 3 x them) */
    float fit_base[4];
    int fit_i, fit_stage;
    float fit_best, fit_ft, fit_k2, fit_q, fit_scale, fit_r2;
    float fine_ft, fine_k2, fine_q;
    /* the token */
    fam_who who;
    float f_token, f_drive;
    float duty_cap, trim;
    float p_target, p_meas_f;
    float iq_drive;              /* the drivers' draw at the drive frequency */
    float g_lit;                 /* the token's conductance once lit (for noticing it leave) */
    float g_acc;
    int g_n;
    float ramp_from_W;
    float ramp_s;
    /* dither in DRIVE */
    int dith_side;
    float dith_acc[2], dith_f[2];
    int dith_cnt[2];
    float slope;
    bool slope_ok;
    float t_low;
    float t_prev;
    /* live mode (FAM_ST_LIVE): the perch drives its own token's tuning all the time */
    bool live;                   /* asked for (fam_set_live) */
    bool live_present;           /* a token is on the perch (the probe) */
    float p_live_f;              /* the power delivered beyond an empty perch's, filtered (W): reported only */
    bool probing;
    float t_probe, t_probe_next;
    float f_probe;               /* Hz */
    float probe_acc, probe_i_hi;
    int probe_n, probe_level, probe_low;  /* samples; 0 upper duty, 1 lower; probes in a row under
                                             the leaving threshold */
    float probe_di;              /* the last probe's supply current, upper level minus lower, A */
    float probe_on;              /* the token's own, while present (filtered), A */
    float probe_empty;           /* an empty perch's: modelled, then learned, A */
} fam_perch;

void fam_init(fam_perch *p, int index);
/* off: a lit token fades out, then the bridge stops */
void fam_enable(fam_perch *p, bool on);
/* live: no sweep and no fit.  The perch drives its own token's tuning (perch 0 the owl's,
 * perch 1 the cat's) at the empty-perch current cap all the time, so the token's glow
 * follows the hand that brings it in, instantly; "present" (FAM_EV_ARRIVED / LEFT) is
 * the probe's (FAM_PROBE_*): seen, or gone, within FAM_PROBE_PERIOD_S; the drive breathes
 * with that period, the probe in its trough.  Safe at any
 * coupling: at its tuning a token only raises the perch's impedance.  (Jason, bench
 * 2026-11-07: the sweep's seconds of lag on a put-down token were "annoyingly long".) */
void fam_set_live(fam_perch *p, bool live);
void fam_step(fam_perch *p, float t_s, float isense_A, const fam_cmd *applied, fam_cmd *cmd, fam_event *ev);
/* the duty at f that puts FAM_CAP_MARGIN x FAM_I_MAX_A into an empty perch (the live drive's) */
float fam_duty_cap(float f_hz);
const char *fam_who_name(fam_who w);
const char *fam_state_name(fam_state s);
