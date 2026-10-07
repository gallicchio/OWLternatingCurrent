/* test_lev.c: the levitation controller (src/lev_ctrl.c) against the plant of
 * sim/physics/levitation_loop.py, in the one-magnet design (lev_plant.h, written
 * by tools/gen_lev_tables.py from the same field computations).
 *
 * The plant (double precision, 5 us steps):
 *   m gap'' = -(F_bias(gap) + F_coil(gap) I - m g - c v + F_ext)     (up is +)
 *   L dI/dt = u V12 - (R + R_bridge) I                                (exact per step)
 * the bat rests in a cradle (it can lift off, not sink below) or is held by a hand,
 * and cannot pass the Hall sensor's package (1 mm).
 * The board around it, as the firmware will see it:
 *   - each 100 us tick, 8 samples of the Hall sensor and of IPROPI in the tick's
 *     first ~40 us; the controller runs at 50 us; its u takes effect at the PWM
 *     wrap 75 us into the tick (so the current settles before the next burst);
 *   - DRV5055A4 at 7.5 mV/mT, 0.03 mT rms of its own noise, its VQ off by
 *     vq_err_mT, clipped to 0.2..3.1 V; 12-bit ADC at 3.3 V with 1.5 LSB rms of
 *     noise per sample; the glue's conversion with the nominal VQ;
 *   - the DRV8874's mirror: |I| x 0.99 V/A plus an offset of up to 30 mA;
 *   - the coil warmer than the firmware believes (2.4 ohm against 2.2).
 * Checks: catches from -3, -2, +2, +3 mm; zero-power current after settling;
 * a tap; loss detection; the CAL procedure with the coil and the sensor either
 * way round; the zero calibration; no bat.
 */
#include "config.h"
#include "lev_ctrl.h"
#include "lev_plant.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define G 9.81
#define SUB 20                                   /* plant steps per tick */
#define H (1.0 / (CTRL_TICK_HZ * (double)SUB))   /* 5 us */
#define TICK_HZ ((double)CTRL_TICK_HZ)
#define V12 12.0
#define R_BRIDGE ((double)DRV_RDSON_OHM)
#define C_AIR 2e-3                               /* N s/m, as the simulation */
#define GAP_MIN 1.0e-3                           /* the Hall sensor's package */

static int failures;
#define CHECK(cond, ...)                                                   \
    do {                                                                   \
        if (!(cond)) {                                                     \
            failures++;                                                    \
            printf("  FAIL %s:%d: ", __FILE__, __LINE__);                  \
            printf(__VA_ARGS__);                                           \
            printf("\n");                                                  \
        }                                                                  \
    } while (0)

/* ---- noise ------------------------------------------------------------------------------- */
static unsigned long long rng_s = 0x9E3779B97F4A7C15ull;
static double urand(void)
{
    rng_s ^= rng_s >> 12;
    rng_s ^= rng_s << 25;
    rng_s ^= rng_s >> 27;
    return ((rng_s * 2685821657736338717ull) >> 11) * (1.0 / 9007199254740992.0);
}
static double gauss(void)
{
    double a = urand(), b = urand();
    if (a < 1e-300)
        a = 1e-300;
    return sqrt(-2.0 * log(a)) * cos(6.283185307179586 * b);
}

/* ---- the plant ------------------------------------------------------------------------------ */
static double tab(const double *t, double gap)
{
    double x = (gap - PLANT_GAP0_M) / PLANT_STEP_M;
    if (x < 0)
        x = 0;
    if (x > PLANT_N - 1.000001)
        x = PLANT_N - 1.000001;
    int i = (int)x;
    double f = x - i;
    return t[i] + f * (t[i + 1] - t[i]);
}

typedef struct {
    /* how this board is built */
    int coil_sign;          /* +1: the bridge's forward current is the simulation's + (pushes down) */
    int mount;              /* +1: the sensor reads the bat's field positive, as config.h assumes */
    double vq_err_mT;       /* the sensor's VQ minus nominal */
    double R;               /* the coil's real resistance */
    double mirror_off_A;    /* IPROPI offset */
    /* state */
    double gap, vdown, I;   /* m, m/s (+: falling), forward A */
    double u;               /* applied */
    double cradle;          /* > 0: the cradle's floor (largest gap) */
    int held;               /* a hand holds the bat still */
    double f_ext;           /* N, + up */
    int absent;             /* no bat at all */
} plant;

static void plant_step(plant *p)
{
    double Rt = p->R + R_BRIDGE, tau = COIL_L_H / Rt;
    double Iinf = p->u * V12 / Rt;
    p->I = Iinf + (p->I - Iinf) * exp(-H / tau);
    if (p->held) {
        p->vdown = 0;
        return;
    }
    double Isim = p->coil_sign * p->I;
    double f_up = tab(PLANT_FBIAS_N, p->gap) + tab(PLANT_FCOIL_N_PER_A, p->gap) * Isim - PLANT_MASS_KG * G +
                  C_AIR * p->vdown + p->f_ext;       /* air drags against the motion (v_up = -vdown) */
    p->vdown -= f_up / PLANT_MASS_KG * H;
    p->gap += p->vdown * H;
    if (p->cradle > 0 && p->gap >= p->cradle) {
        p->gap = p->cradle;
        if (p->vdown > 0)
            p->vdown = 0;
    }
    if (p->gap < GAP_MIN) {
        p->gap = GAP_MIN;
        if (p->vdown < 0)
            p->vdown = 0;
    }
}

/* one ADC conversion of each input, as the glue will see them */
static double hall_code(const plant *p)
{
    double Bz = PLANT_BBIAS_T + (p->absent ? 0.0 : tab(PLANT_BBAT_T, p->gap)) +
                PLANT_BCOIL_T_PER_A * p->coil_sign * p->I;
    double b_axis_mT = p->mount * (-Bz) * 1e3 + 0.03 * gauss();
    double v = ADC_VREF_V * HALL_VQ_FRACTION + (p->vq_err_mT + b_axis_mT) * HALL_MV_PER_MT * 1e-3;
    if (v < 0.2)
        v = 0.2;
    if (v > ADC_VREF_V - 0.2)
        v = ADC_VREF_V - 0.2;
    double code = floor(v / ADC_VREF_V * ADC_COUNTS + 1.5 * gauss() + 0.5);
    return code < 0 ? 0 : code > 4095 ? 4095 : code;
}

static double iprop_code(const plant *p)
{
    double i = fabs(p->I) + p->mirror_off_A;
    if (i < 0)
        i = 0;
    double v = i * IPROPI_V_PER_A;
    if (v > ADC_VREF_V)
        v = ADC_VREF_V;
    double code = floor(v / ADC_VREF_V * ADC_COUNTS + 1.5 * gauss() + 0.5);
    return code < 0 ? 0 : code > 4095 ? 4095 : code;
}

/* ---- a run ---------------------------------------------------------------------------------- */
typedef struct {
    plant p;
    lev_ctrl c;
    lev_output out;
    double t;
    double u_next;
    int engaged;            /* the controller has been in HOLD */
    double t_engage;
    int release_after;      /* ticks after the engage a held bat is let go (-1: never) */
    int since_engage;
    double max_cmd;         /* largest |lifting current| asked for, whole run */
    double max_I;           /* largest |coil current|, whole run */
    double max_u;
    /* statistics over a window */
    double win_from, win_to;
    double s_I, s_I2, s_g, s_g2, n;
} run;

static void run_init(run *r, double gap, double cradle_gap, int held)
{
    memset(r, 0, sizeof *r);
    r->p.coil_sign = 1;
    r->p.mount = 1;
    r->p.R = 2.4;
    r->p.mirror_off_A = 0.02;
    r->p.gap = gap;
    r->p.cradle = cradle_gap;
    r->p.held = held;
    lev_init(&r->c);
    r->release_after = -1;
    r->win_from = r->win_to = -1;
}

static void tick(run *r)
{
    double hall = 0, ip = 0;
    for (int s = 0; s < SUB; s++) {
        if (s < 8) {
            hall += hall_code(&r->p);
            ip += iprop_code(&r->p);
        }
        if (s == 10) {          /* the burst is in: run the controller (the glue's arithmetic) */
            lev_input in = {
                .hall_mT = (float)(HALL_POLARITY * ((hall / 8) * ADC_VREF_V / ADC_COUNTS -
                                                    ADC_VREF_V * HALL_VQ_FRACTION) / (HALL_MV_PER_MT * 1e-3)),
                .iprop_A = (float)((ip / 8) * ADC_VREF_V / ADC_COUNTS / IPROPI_V_PER_A),
                .v12_V = (float)V12,
                .coil_R_ohm = COIL_R20_OHM,
                .coil_allowed = true,
                .thermal_trip = false,
            };
            lev_step(&r->c, &in, &r->out);
            r->u_next = r->out.u;
            if (fabs(r->c.i_cmd) > r->max_cmd)
                r->max_cmd = fabs(r->c.i_cmd);
            if (fabs(r->out.u) > r->max_u)
                r->max_u = fabs(r->out.u);
        }
        if (s == 15)            /* the next PWM wrap */
            r->p.u = r->u_next;
        plant_step(&r->p);
        if (fabs(r->p.I) > r->max_I)
            r->max_I = fabs(r->p.I);
    }
    r->t += 1.0 / TICK_HZ;
    if (r->c.state == LEV_HOLD && !r->engaged) {
        r->engaged = 1;
        r->t_engage = r->t;
    }
    if (r->engaged && r->release_after >= 0 && r->p.held && ++r->since_engage > r->release_after)
        r->p.held = 0;
    if (r->t >= r->win_from && r->t < r->win_to) {
        double I = r->p.coil_sign * r->p.I * -1.0;     /* lifting current: the sim's - pushes up */
        r->s_I += I;
        r->s_I2 += I * I;
        r->s_g += r->p.gap;
        r->s_g2 += r->p.gap * r->p.gap;
        r->n += 1;
    }
}

static void run_for(run *r, double secs)
{
    long n = (long)(secs * TICK_HZ + 0.5);
    for (long i = 0; i < n; i++)
        tick(r);
}

typedef struct {
    int held_at_end;
    double t_catch, peak_I, mean_mA, rms_mA, jitter_um, gap_err_mm;
} catch_result;

static void window_stats(const run *r, catch_result *cr)
{
    double n = r->n > 0 ? r->n : 1;
    double mI = r->s_I / n, mg = r->s_g / n;
    cr->mean_mA = mI * 1e3;
    cr->rms_mA = sqrt(fmax(r->s_I2 / n, 0)) * 1e3;
    cr->jitter_um = sqrt(fmax(r->s_g2 / n - mg * mg, 0)) * 1e6;
    cr->gap_err_mm = (mg - PLANT_G0_M) * 1e3;
}

/* released at rest d mm from the float point: in the cradle (d > 0) or held by a hand
 * that lets go 20 ms after the catch (d < 0) */
static catch_result catch_case(double d_mm, double ramp, double vq_err, int coil_sign, int mount, bool calibrate,
                               double secs, run *keep)
{
    static run r;
    double g = PLANT_G0_M + d_mm * 1e-3;
    run_init(&r, g, d_mm > 0 ? g : 0, d_mm <= 0);
    r.release_after = d_mm <= 0 ? 200 : -1;
    r.p.coil_sign = coil_sign;
    r.p.mount = mount;
    r.p.vq_err_mT = vq_err;
    lev_set_param(&r.c, "ramp_mm_s", (float)ramp);
    if (!calibrate) {
        lev_set_param(&r.c, "auto_cal", 0);
        lev_set_param(&r.c, "coil_pol", (float)-coil_sign);   /* what a CAL would find */
    }
    lev_enable(&r.c, true);
    r.win_from = secs - 1.0;
    r.win_to = secs;
    run_for(&r, secs);
    catch_result cr = {0};
    cr.held_at_end = r.c.state == LEV_HOLD;
    cr.t_catch = r.engaged ? r.t_engage : -1;
    cr.peak_I = r.max_I;
    window_stats(&r, &cr);
    CHECK(r.max_cmd <= LEV_I_MAX_A + 1e-6, "asked for %.3f A, above LEV_I_MAX_A", r.max_cmd);
    CHECK(r.max_u <= 1.0 + 1e-6, "u %.3f beyond 1", r.max_u);
    if (keep)
        *keep = r;
    return cr;
}

static void print_case(const char *name, const catch_result *cr)
{
    printf("  %-40s %-4s %6.2f s %6.2f A %+8.2f mA %6.1f mA %6.1f um %+7.3f mm\n", name,
           cr->held_at_end ? "yes" : "NO", cr->t_catch, cr->peak_I, cr->mean_mA, cr->rms_mA, cr->jitter_um,
           cr->gap_err_mm);
}

int main(void)
{
    printf("levitation: float gap %.3f mm, bat %.2f g, coil %.1f mN/A there; DRV5055A4 at %.1f mV/mT\n",
           PLANT_G0_M * 1e3, PLANT_MASS_KG * 1e3, -tab(PLANT_FCOIL_N_PER_A, PLANT_G0_M) * 1e3,
           (double)HALL_MV_PER_MT);
    printf("  %-40s %-4s %8s %8s %11s %9s %9s %10s\n", "case (last second of the run)", "held", "caught",
           "peak I", "mean I", "rms I", "jitter", "gap - g0");

    /* 1. catches: the soft catch (the default), from both sides, CAL on enable */
    const double offs[] = {-3, -2, 2, 3};
    for (int i = 0; i < 4; i++) {
        char name[64];
        snprintf(name, sizeof name, "%s %+.0f mm, CAL, soft catch", offs[i] > 0 ? "cradle" : "hand  ", offs[i]);
        catch_result cr = catch_case(offs[i], 6.0, 0.0, 1, 1, true, 5.0, NULL);
        print_case(name, &cr);
        CHECK(cr.held_at_end, "%s: not holding", name);
        CHECK(fabs(cr.mean_mA) < 10.0, "%s: mean current %.2f mA", name, cr.mean_mA);
        CHECK(cr.peak_I < LEV_I_MAX_A, "%s: peak %.2f A", name, cr.peak_I);
        CHECK(fabs(cr.gap_err_mm) < 0.1, "%s: floats %.3f mm from the float point", name, cr.gap_err_mm);
        CHECK(cr.jitter_um < 30.0, "%s: jitter %.1f um", name, cr.jitter_um);
    }
    /* 2. the simulation's catch: the set-point jumps straight to the float gap */
    for (int i = 0; i < 4; i++) {
        char name[64];
        snprintf(name, sizeof name, "%s %+.0f mm, step to g0 (as the sim)", offs[i] > 0 ? "cradle" : "hand  ",
                 offs[i]);
        catch_result cr = catch_case(offs[i], 0.0, 0.0, 1, 1, false, 5.0, NULL);
        print_case(name, &cr);
        CHECK(cr.held_at_end, "%s: not holding", name);
        CHECK(fabs(cr.mean_mA) < 10.0, "%s: mean current %.2f mA", name, cr.mean_mA);
    }
    /* 3. a VQ error the firmware does not know about, and a mirror offset of the other sign */
    const double vqs[] = {-3.0, 3.0};
    for (int i = 0; i < 2; i++) {
        char name[64];
        snprintf(name, sizeof name, "cradle +3 mm, VQ off by %+.0f mT", vqs[i]);
        catch_result cr = catch_case(3, 6.0, vqs[i], 1, 1, true, 6.0, NULL);
        print_case(name, &cr);
        CHECK(cr.held_at_end && fabs(cr.mean_mA) < 10.0, "%s: held %d, mean %.2f mA", name, cr.held_at_end,
              cr.mean_mA);
    }
    /* 4. CAL with the coil wired the other way, and with the sensor mounted the other way */
    {
        run *r = calloc(1, sizeof *r);
        catch_result cr = catch_case(3, 6.0, 0.0, -1, 1, true, 5.0, r);
        print_case("coil wired the other way, CAL", &cr);
        CHECK(cr.held_at_end && fabs(cr.mean_mA) < 10.0, "reversed coil: held %d, mean %.2f mA", cr.held_at_end,
              cr.mean_mA);
        CHECK(r->c.coil_pol == 1.0f, "CAL found coil_pol %+.0f for a reversed coil (want +1)", r->c.coil_pol);
        CHECK(fabsf(r->c.kcs - (float)(PLANT_BCOIL_T_PER_A * 1e3)) < 0.1f * (float)(PLANT_BCOIL_T_PER_A * 1e3),
              "CAL measured %.2f mT/A, the coil makes %.2f", r->c.kcs, PLANT_BCOIL_T_PER_A * 1e3);
        printf("    CAL: %s, coil_pol %+.0f, %.3f mT/A (plant %.3f)\n", r->c.cal_msg, r->c.coil_pol, r->c.kcs,
               PLANT_BCOIL_T_PER_A * 1e3);
        cr = catch_case(3, 6.0, 0.0, 1, 1, true, 5.0, r);
        CHECK(r->c.coil_pol == -1.0f, "CAL found coil_pol %+.0f for the nominal coil (want -1)", r->c.coil_pol);
        printf("    nominal coil: CAL %s, coil_pol %+.0f, %.3f mT/A\n", r->c.cal_msg, r->c.coil_pol, r->c.kcs);
        cr = catch_case(3, 6.0, 0.0, 1, -1, true, 5.0, r);
        print_case("sensor mounted the other way, CAL", &cr);
        CHECK(cr.held_at_end && fabs(cr.mean_mA) < 10.0, "reversed sensor: held %d, mean %.2f mA",
              cr.held_at_end, cr.mean_mA);
        CHECK(r->c.bat_sign == -1.0f, "bat_sign %+.0f after the sensor reads the bat negative", r->c.bat_sign);
        printf("    bat_sign %+.0f (%s), coil_pol %+.0f\n", r->c.bat_sign, r->c.reason, r->c.coil_pol);
        free(r);
    }

    /* 5. a tap, then a pull: hold through the first, let go within 50 ms of the second */
    {
        run *r = calloc(1, sizeof *r);
        catch_case(3, 6.0, 0.0, 1, 1, true, 4.0, r);
        double gmin = 1, gmax = 0;
        r->p.f_ext = -5e-3;                                    /* a 5 mN tap down, 20 ms */
        for (int i = 0; i < 200; i++)
            tick(r);
        r->p.f_ext = 0;
        for (int i = 0; i < 20000; i++) {
            tick(r);
            gmin = fmin(gmin, r->p.gap);
            gmax = fmax(gmax, r->p.gap);
        }
        printf("  tap (5 mN, 20 ms): still %s, the gap swung %.3f .. %.3f mm\n", lev_state_name(r->c.state),
               gmin * 1e3, gmax * 1e3);
        CHECK(r->c.state == LEV_HOLD, "the tap lost the bat");

        double t0 = r->t, t_cross = -1, t_rel = -1;
        r->p.cradle = 0;                                       /* nothing below to land on */
        r->p.f_ext = -0.1;                                     /* a hand pulls it down: 3x its weight */
        for (int i = 0; i < 5000 && (t_cross < 0 || t_rel < 0); i++) {
            tick(r);
            if (t_cross < 0 && fabs(r->p.gap - (double)r->c.gref) > 5e-3)
                t_cross = r->t;
            if (t_rel < 0 && !r->out.active)
                t_rel = r->t;
        }
        double lat = (t_rel - t_cross) * 1e3;
        printf("  pull down (0.1 N, more than the coil can hold): released %.1f ms after the pull began, %.1f ms %s "
               "the gap left +-5 mm (%s)\n", (t_rel - t0) * 1e3, fabs(lat), lat >= 0 ? "after" : "before",
               r->c.reason);
        CHECK(t_rel > 0 && t_cross > 0, "no release (t_rel %.3f, t_cross %.3f)", t_rel, t_cross);
        CHECK(lat <= 50.0, "released %.1f ms after the bat left the window", lat);
        for (int i = 0; i < 10; i++)
            tick(r);
        CHECK(fabs(r->p.I) < 0.005, "coil current %.3f A 1 ms after the release", r->p.I);
        CHECK(r->c.state == LEV_LOST, "state %s after the pull", lev_state_name(r->c.state));

        /* a hand takes the bat away at 0.2 m/s: the window, not the current limit, must see it go */
        catch_case(3, 6.0, 0.0, 1, 1, true, 4.0, r);
        r->p.held = 1;
        r->p.cradle = 0;
        t0 = r->t;
        t_cross = t_rel = -1;
        for (int i = 0; i < 5000 && (t_cross < 0 || t_rel < 0); i++) {
            r->p.gap += 0.2 / TICK_HZ;
            tick(r);
            if (t_cross < 0 && fabs(r->p.gap - (double)r->c.gref) > 5e-3)
                t_cross = r->t;
            if (t_rel < 0 && !r->out.active)
                t_rel = r->t;
        }
        lat = (t_rel - t_cross) * 1e3;
        printf("  taken away by hand (0.2 m/s): released %.1f ms %s the gap left +-5 mm (%s)\n", fabs(lat),
               lat >= 0 ? "after" : "before", r->c.reason);
        CHECK(t_rel > 0 && t_cross > 0 && lat <= 50.0, "taken away: latency %.1f ms", lat);

        /* and a pull up against the perch */
        catch_case(3, 6.0, 0.0, 1, 1, true, 4.0, r);
        t0 = r->t;
        t_rel = -1;
        r->p.f_ext = +0.1;
        for (int i = 0; i < 5000 && t_rel < 0; i++) {
            tick(r);
            if (!r->out.active)
                t_rel = r->t;
        }
        printf("  pull up (0.1 N): released %.1f ms after the pull began (%s)\n", (t_rel - t0) * 1e3, r->c.reason);
        CHECK(t_rel > 0 && (t_rel - t0) < 0.2, "pull up: release at %.3f s", t_rel - t0);
        free(r);
    }

    /* 6. no bat: nothing to catch, nothing driven, no false flip */
    {
        run *r = calloc(1, sizeof *r);
        run_init(r, 40e-3, 40e-3, 1);
        r->p.absent = 1;
        lev_enable(&r->c, true);
        run_for(r, 2.0);
        double maxu_after_cal = 0;
        for (int i = 0; i < 10000; i++) {
            tick(r);
            maxu_after_cal = fmax(maxu_after_cal, fabs(r->out.u));
        }
        printf("  no bat: %s after 3 s (CAL: %s), bat_sign %+.0f, |u| max %.3f\n", lev_state_name(r->c.state),
               r->c.cal_msg, r->c.bat_sign, maxu_after_cal);
        CHECK(r->c.state == LEV_WAIT && maxu_after_cal == 0.0, "no bat: state %s, u %.3f",
              lev_state_name(r->c.state), maxu_after_cal);
        CHECK(r->c.bat_sign == 1.0f, "no bat flipped bat_sign");
        CHECK(r->c.cal.coil_valid, "CAL without the bat failed: %s", r->c.cal_msg);

        /* 7. the zero calibration (bat removed) finds the VQ error */
        run_init(r, 40e-3, 40e-3, 1);
        r->p.absent = 1;
        r->p.vq_err_mT = 3.0;
        lev_request_cal(&r->c, LEV_CAL_ZERO);
        run_for(r, 0.5);
        printf("  zero CAL with VQ off by +3.0 mT: %s, offset %.2f mT\n", r->c.cal_msg, r->c.offset_mT);
        CHECK(r->c.cal.zero_valid && fabsf(r->c.offset_mT - 3.0f) < 0.2f, "zero CAL: offset %.2f mT",
              r->c.offset_mT);
        /* with it, the gap is read right: the bat held at the float point */
        lev_cal_data cd;
        lev_get_cal(&r->c, &cd);
        run_init(r, PLANT_G0_M, 0, 1);
        r->p.vq_err_mT = 3.0;
        lev_set_cal(&r->c, &cd);
        run_for(r, 0.2);
        printf("    the bat held at %.3f mm reads %.3f mm\n", PLANT_G0_M * 1e3, r->c.gap * 1e3);
        CHECK(fabsf(r->c.gap - (float)PLANT_G0_M) < 0.05e-3f, "with the zero CAL the gap reads %.3f mm",
              r->c.gap * 1e3);
        free(r);
    }

    /* 8. the faults: an open coil, a hand holding the bat, the thermal model, the rail */
    {
        run *r = calloc(1, sizeof *r);
        catch_case(3, 6.0, 0.0, 1, 1, true, 3.0, r);
        r->p.R = 1e6;                                          /* the perch's header comes loose */
        r->p.f_ext = -0.02;                                    /* and the bat starts to sink */
        double t0 = r->t;
        while (r->c.state == LEV_HOLD && r->t - t0 < 1.0)
            tick(r);
        printf("  open coil: %s after %.1f ms (%s)\n", lev_state_name(r->c.state), (r->t - t0) * 1e3, r->c.reason);
        CHECK(r->c.state == LEV_FAULT || r->c.state == LEV_LOST, "open coil: state %s", lev_state_name(r->c.state));
        for (int i = 0; i < 30000; i++)
            tick(r);
        CHECK(r->c.state != LEV_HOLD, "open coil: holding again");

        catch_case(3, 6.0, 0.0, 1, 1, true, 3.0, r);
        r->p.held = 1;                                         /* a hand holds it 1 mm high */
        r->p.gap -= 1e-3;
        t0 = r->t;
        while (r->out.active && r->t - t0 < 5.0)
            tick(r);
        printf("  held 1 mm high by a hand: released after %.0f ms (%s)\n", (r->t - t0) * 1e3, r->c.reason);
        CHECK(!r->out.active && r->t - t0 < 3.0, "held bat: still driving after %.1f s", r->t - t0);

        catch_case(3, 6.0, 0.0, 1, 1, true, 3.0, r);
        lev_input in = {.hall_mT = 30, .iprop_A = 0, .v12_V = 12, .coil_R_ohm = 2.2f, .coil_allowed = false};
        lev_output o;
        lev_step(&r->c, &in, &o);
        CHECK(r->c.state == LEV_INHIBIT && !o.active && o.u == 0.0f, "no 12 V: state %s, u %.3f",
              lev_state_name(r->c.state), o.u);
        in.coil_allowed = true;
        lev_step(&r->c, &in, &o);
        CHECK(r->c.state == LEV_WAIT, "12 V back: state %s", lev_state_name(r->c.state));
        in.thermal_trip = true;
        lev_step(&r->c, &in, &o);
        CHECK(r->c.state == LEV_FAULT && !o.active, "thermal: state %s", lev_state_name(r->c.state));
        in.thermal_trip = false;
        for (int i = 0; i < 100; i++)
            lev_step(&r->c, &in, &o);
        CHECK(r->c.state == LEV_FAULT, "a fault must wait for lev_enable");
        lev_enable(&r->c, true);
        lev_step(&r->c, &in, &o);
        CHECK(r->c.state == LEV_WAIT || r->c.state == LEV_CAL, "re-enabled: state %s", lev_state_name(r->c.state));
        printf("  no 12 V -> inhibit -> wait; thermal -> fault, kept until re-enabled: ok\n");
        free(r);
    }

    /* 9. the console's tunables */
    {
        lev_ctrl c;
        lev_init(&c);
        CHECK(lev_param_count() > 10, "params");
        CHECK(lev_set_param(&c, "bw_hz", 8.0f) && lev_get_param(&c, 0) == 8.0f, "bw_hz");
        CHECK(!lev_set_param(&c, "bw_hz", 1000.0f), "out-of-range accepted");
        CHECK(!lev_set_param(&c, "nonsense", 1.0f), "unknown name accepted");
        CHECK(!lev_set_param(&c, "i_max", 10.0f), "i_max above LEV_I_MAX_A accepted");
    }

    printf(failures ? "test_lev: %d FAILED\n" : "test_lev: all passed\n", failures);
    return failures != 0;
}
