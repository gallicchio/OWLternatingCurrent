/* test_rt.c: core 1's realtime half (src/rt.c), the coil PWM (src/coils.c) and the
 * safe pin state (src/board.c), on the host.
 *
 * The SDK calls they make are modelled in stubs/ (GPIO levels and functions, the
 * PWM slices' registers, the ADC, the DMA channel, the interrupt handlers, the
 * clock).  The test captures core 1's two interrupt handlers and plays the hardware:
 * every 100 us it fires the tick, fills the DMA's burst with what the ADC would read
 * (the multiplexer's channel taken from the select pins), and fires the DMA's
 * completion.  The coils are a resistive load behind a model of the DRV8874's truth
 * table, driven by the PWM registers exactly as rt.c leaves them.
 *
 *   SAFE      after board_safe_init() every bridge pin is a plain output, low; the
 *             DRV8874s asleep; the perch drivers disabled
 *   PWM       coil_set_u() gives the mean voltage asked for, never coasts while
 *             driving, keeps min_alt each way; the perch legs never overlap
 *   NO 12 V   no request is accepted and nothing wakes on USB power alone
 *   REQUEST   a request wakes the bridges, makes its current, ends at its deadline;
 *             the bridges sleep after a second of nothing
 *   LIMITS    each owner's current limit holds
 *   BROWN-OUT 12 V falling stops everything within a couple of milliseconds
 *   nFAULT    held 1 ms: everything off; retried after 100 ms; three in a minute
 *             latch off until `clear`
 *   MIRRORS   a shorted coil (overcurrent) and an open one are caught
 *   THERMAL   a coil driven hard for minutes stays under its limit
 *   LEV       the levitation loop's coil calibration runs through the real glue
 */
#include "board.h"
#include "board_pins.h"
#include "coils.h"
#include "config.h"
#include "lev_ctrl.h"
#include "lev_table.h"
#include "rt.h"
#include "sdk_stub.h"
#include "hardware/irq.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...)                                  \
    do {                                                  \
        if (!(cond)) {                                    \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);   \
            printf(__VA_ARGS__);                          \
            printf("\n");                                 \
            failures++;                                   \
        }                                                 \
    } while (0)

static const uint8_t SLICE[COIL_COUNT] = {PWM_SLICE_PEND1, PWM_SLICE_PEND2, PWM_SLICE_PEND3, PWM_SLICE_LEV};
static const uint8_t PIN_IN1[COIL_COUNT] = {PIN_PEND1_IN1, PIN_PEND2_IN1, PIN_PEND3_IN1, PIN_LEV_IN1};

/* ---- the world -------------------------------------------------------------------------- */
static float v12 = 0.0f, v5 = 0.0f, vbus = 5.0f;
static float coil_r[COIL_COUNT] = {COIL_R20_OHM, COIL_R20_OHM, COIL_R20_OHM, COIL_R20_OHM};   /* the real coils at 25 C */
static float coil_t[COIL_COUNT] = {25.0f, 25.0f, 25.0f, 25.0f}; /* their temperature: one node, 2.8 J/K, ... */
static float coil_rth[COIL_COUNT] = {43.0f, 43.0f, 43.0f, 43.0f}; /* ... and this many K/W to the room */
static float hall_bias_mT = 6.36f;                             /* the owl's magnet at the sensor */
static float hall_coil_mT_per_A = LEV_BCOIL_MT_PER_A;           /* the coil at the sensor, per forward amp */
static long ticks;

/* the fractions of a PWM period the bridge spends in each state, from the registers */
static void bridge(unsigned s, float *fwd, float *rev, float *brake, float *coast)
{
    uint32_t top = stub_pwm.slice[s].top, cc = stub_pwm.slice[s].cc;
    uint32_t a = cc & 0xffffu, b = cc >> 16;
    unsigned n[4] = {0, 0, 0, 0};
    for (uint32_t v = 0; v <= top; v++) {                   /* phase-correct: each count twice */
        bool in1 = (v < a) != stub_pwm_inv_a[s];
        bool in2 = (v < b) != stub_pwm_inv_b[s];
        n[(in1 ? 1 : 0) | (in2 ? 2 : 0)]++;
    }
    float P = (float)(top + 1u);
    *coast = (float)n[0] / P;
    *fwd = (float)n[1] / P;
    *rev = (float)n[2] / P;
    *brake = (float)n[3] / P;
}

/* what the coil really sees: the bridge takes DRV_PULSE_LOSS_S off each output pulse
 * (rev A, bringup/REVB.md 3.3), one forward and one reverse pulse a period */
static float seen(float frac, unsigned s)
{
    float loss = DRV_PULSE_LOSS_S * (float)SYS_CLK_HZ / (2.0f * (float)(stub_pwm.slice[s].top + 1u));
    return frac > loss ? frac - loss : 0.0f;
}

/* the coil's mean current: nothing asleep or with the pins not on the PWM */
static float coil_current(int c)
{
    if (!stub_gpio_out[PIN_DRV_nSLEEP] || stub_gpio_func[PIN_IN1[c]] != GPIO_FUNC_PWM)
        return 0.0f;
    float f, r, b, k;
    bridge(SLICE[c], &f, &r, &b, &k);
    float rc = coil_r[c] * (1.0f + COPPER_TEMPCO * (coil_t[c] - 25.0f));
    return (seen(f, SLICE[c]) - seen(r, SLICE[c])) * v12 / (rc + DRV_RDSON_OHM);
}

static uint16_t code(float volts)
{
    float x = volts / ADC_VREF_V * 4096.0f;
    return (uint16_t)(x < 0.0f ? 0.0f : x > 4095.0f ? 4095.0f : x + 0.5f);
}

static float mux_volts(unsigned ch)
{
    if (ch == MUX_CH_PEND1_IPROPI) return fabsf(coil_current(COIL_PEND1)) * IPROPI_V_PER_A;
    if (ch == MUX_CH_PEND2_IPROPI) return fabsf(coil_current(COIL_PEND2)) * IPROPI_V_PER_A;
    if (ch == MUX_CH_PEND3_IPROPI) return fabsf(coil_current(COIL_PEND3)) * IPROPI_V_PER_A;
    if (ch == MUX_CH_V12_SENSE) return v12 * V12_DIVIDER;
    if (ch == MUX_CH_V5_SENSE) return v5 * V5_DIVIDER;
    if (ch == MUX_CH_VBUS_SENSE) return vbus * VBUS_DIVIDER;
    return 0.0f;
}

/* one 100 us tick, as the hardware would run it */
static void tick(void)
{
    stub_now_us += 100u;
    stub_irq_handler[PWM_IRQ_WRAP_1]();
    if (!stub_dma_busy)
        return;
    unsigned mux = (unsigned)stub_gpio_out[PIN_MUX_S0] | (unsigned)stub_gpio_out[PIN_MUX_S1] << 1 |
                   (unsigned)stub_gpio_out[PIN_MUX_S2] << 2;
    float i_lev = coil_current(COIL_LEV);
    float hall_V = HALL_VQ_FRACTION * ADC_VREF_V +
                   (float)HALL_POLARITY * (hall_bias_mT + hall_coil_mT_per_A * i_lev) * HALL_MV_PER_MT * 1e-3f;
    for (unsigned i = 0; i < stub_dma_count / 3; i++) {
        stub_dma_dest[3 * i + ADC_SLOT_HALL] = code(hall_V);
        stub_dma_dest[3 * i + ADC_SLOT_LEV_IPROPI] = code(fabsf(i_lev) * IPROPI_V_PER_A);
        stub_dma_dest[3 * i + ADC_SLOT_MUX_OUT] = code(mux_volts(mux));
    }
    stub_dma_busy = false;
    stub_dma_irq_pending = true;
    stub_irq_handler[DMA_IRQ_1]();
    for (int c = 0; c < COIL_COUNT; c++) {           /* the plant's coils warm and cool */
        float i = coil_current(c);
        float rc = coil_r[c] * (1.0f + COPPER_TEMPCO * (coil_t[c] - 25.0f));
        coil_t[c] += (i * i * rc - (coil_t[c] - 25.0f) / coil_rth[c]) * 1e-4f / 2.8f;
    }
    ticks++;
}

static void run_ms(float ms)
{
    for (int i = 0; i < (int)(ms * 10.0f + 0.5f); i++)
        tick();
}

static bool asleep(void) { return !stub_gpio_out[PIN_DRV_nSLEEP]; }

static bool bridges_plain_low(void)
{
    for (unsigned p = 0; p < 32; p++)
        if ((BRIDGE_PIN_MASK & (1u << p)) && stub_gpio_func[p] == GPIO_FUNC_PWM)
            return false;
    return true;
}

/* ---- the tests ---------------------------------------------------------------------------- */
static void test_safe(void)
{
    for (unsigned p = 0; p < 32; p++) {
        stub_gpio_func[p] = GPIO_FUNC_PWM;            /* as if something had left them driving */
        stub_gpio_out[p] = true;
    }
    stub_gpio_in[PIN_DRV_nFAULT] = true;              /* the board's pull-up */
    stub_gpio_in[PIN_BUTTON] = true;
    board_safe_init();
    for (unsigned p = 0; p < 32; p++)
        if (BRIDGE_PIN_MASK & (1u << p))
            CHECK(stub_gpio_func[p] == GPIO_FUNC_SIO && stub_gpio_oe[p] && !stub_gpio_out[p],
                  "SAFE: GPIO%u not a plain low output", p);
    CHECK(stub_gpio_oe[PIN_DRV_nSLEEP] && !stub_gpio_out[PIN_DRV_nSLEEP], "SAFE: the DRV8874s awake");
    CHECK(stub_gpio_oe[PIN_FAM_EN] && !stub_gpio_out[PIN_FAM_EN], "SAFE: the perch drivers enabled");
    CHECK(!stub_gpio_out[PIN_AUDIO], "SAFE: the audio pin high");
    CHECK(!stub_gpio_oe[PIN_DRV_nFAULT] && !stub_gpio_oe[PIN_BUTTON], "SAFE: an input driven");
    printf("safe state: every bridge pin a plain low output, DRV8874s asleep, perches disabled\n");
}

static void test_pwm_math(void)
{
    /* coil_set_u on the levitation slice, at its frequency */
    static const float US[] = {-0.9f, -0.5f, -0.1f, -0.004f, 0.0f, 0.004f, 0.05f, 0.3f, 0.9f};
    static const float ALT[] = {0.0f, 0.012f, 0.3f};
    float worst = 0.0f;
    for (unsigned a = 0; a < 3; a++)
        for (unsigned k = 0; k < sizeof US / sizeof US[0]; k++) {
            coil_set_u(COIL_LEV, US[k], ALT[a]);
            float f, r, b, c;
            bridge(PWM_SLICE_LEV, &f, &r, &b, &c);
            float loss = DRV_PULSE_LOSS_S * coil_pwm_hz(COIL_LEV);
            float lim = ALT[a] > 0.0f ? 1.0f - 2.0f * (ALT[a] + loss) : 1.0f - loss;   /* coils.c's room */
            float want = fmaxf(-lim, fminf(lim, US[k]));
            float P = (float)(coil_top(COIL_LEV) + 1u);
            float got = seen(f, PWM_SLICE_LEV) - seen(r, PWM_SLICE_LEV);   /* after the bridge's loss */
            worst = fmaxf(worst, fabsf(got - want));
            CHECK(fabsf(got - want) <= 1.0f / P + 1e-6f, "PWM: u %.3f alt %.3f gave %.4f at the coil", (double)US[k],
                  (double)ALT[a], (double)got);
            CHECK(c == 0.0f, "PWM: coasts %.3f of the period while driving", (double)c);
            CHECK(seen(f, PWM_SLICE_LEV) + 1.0f / P >= ALT[a] && seen(r, PWM_SLICE_LEV) + 1.0f / P >= ALT[a],
                  "PWM: alternation below %.3f at the coil", (double)ALT[a]);
            if (ALT[a] == 0.0f && US[k] == 0.0f)
                CHECK(f == 0.0f && r == 0.0f && c == 0.0f, "PWM: nothing asked for drives %.4f / %.4f", (double)f,
                      (double)r);
        }
    /* the compensation itself: each pulse asked for comes out DRV_PULSE_LOSS_S longer */
    {
        float f, r, b, c;
        coil_set_u(COIL_LEV, 0.05f, 0.0f);
        bridge(PWM_SLICE_LEV, &f, &r, &b, &c);
        float loss = DRV_PULSE_LOSS_S * coil_pwm_hz(COIL_LEV), P = (float)(coil_top(COIL_LEV) + 1u);
        CHECK(fabsf(f - (0.05f + loss)) <= 1.0f / P + 1e-6f && r == 0.0f, "PWM: lev fwd %.4f, not %.4f", (double)f,
              (double)(0.05f + loss));
        coil_set_u(COIL_PEND1, -0.2f, 0.0f);
        bridge(PWM_SLICE_PEND1, &f, &r, &b, &c);
        loss = DRV_PULSE_LOSS_S * coil_pwm_hz(COIL_PEND1);
        P = (float)(coil_top(COIL_PEND1) + 1u);
        CHECK(fabsf(r - (0.2f + loss)) <= 1.0f / P + 1e-6f && f == 0.0f, "PWM: pend1 rev %.4f, not %.4f", (double)r,
              (double)(0.2f + loss));
        coil_set_u(COIL_LEV, 0.0f, DRV_MIN_PULSE_S * coil_pwm_hz(COIL_LEV));   /* rt.c's min_alt */
        bridge(PWM_SLICE_LEV, &f, &r, &b, &c);
        CHECK(seen(f, PWM_SLICE_LEV) > 0.0f && seen(r, PWM_SLICE_LEV) > 0.0f, "PWM: the min_alt pulses vanish");
        coil_set_u(COIL_LEV, 0.99f, 0.0f);                                     /* saturated: all forward */
        bridge(PWM_SLICE_LEV, &f, &r, &b, &c);
        CHECK(f == 1.0f && r == 0.0f, "PWM: full forward %.4f / %.4f", (double)f, (double)r);
        coil_set_fractions(COIL_LEV, 0.7f, 0.4f);              /* too much of both: the mean kept */
        bridge(PWM_SLICE_LEV, &f, &r, &b, &c);
        CHECK(fabsf((f - r) - 0.3f) <= 2.0f / (float)(coil_top(COIL_LEV) + 1u) && f + r <= 1.0f + 1e-6f,
              "PWM: an overfull request lost its mean: %.4f / %.4f", (double)f, (double)r);
        coil_coast(COIL_PEND1);
        printf("PWM: every pulse %.0f ns longer than asked (the bridge's loss); min_alt survives it\n",
               (double)(DRV_PULSE_LOSS_S * 1e9f));
    }
    coil_coast(COIL_LEV);
    float f, r, b, c;
    bridge(PWM_SLICE_LEV, &f, &r, &b, &c);
    CHECK(c == 1.0f, "PWM: coast is not coast");
    printf("PWM: mean voltage within %.5f of the request (1/P = %.5f), never coasting while driving\n",
           (double)worst, (double)(1.0f / (float)(coil_top(COIL_LEV) + 1u)));

    /* the perches: legs never high together, duty as asked, FAM_EN follows */
    perch_init();
    float got = perch_set(0, true, 150e3f, 0.25f);
    uint32_t top = stub_pwm.slice[PWM_SLICE_FAM1].top, cc = stub_pwm.slice[PWM_SLICE_FAM1].cc;
    unsigned both = 0, ha = 0, hb = 0;
    for (uint32_t v = 0; v <= top; v++) {
        bool la = (v < (cc & 0xffffu)) != stub_pwm_inv_a[PWM_SLICE_FAM1];
        bool lb = (v < (cc >> 16)) != stub_pwm_inv_b[PWM_SLICE_FAM1];
        both += la && lb;
        ha += la;
        hb += lb;
    }
    CHECK(fabsf(got - 150e3f) < 300.0f, "perch frequency %f", (double)got);
    CHECK(both == 0, "perch legs high together");
    CHECK(fabsf((float)ha / (float)(top + 1u) - 0.25f) < 0.01f && ha == hb, "perch duty %u/%u %u", ha, top + 1u, hb);
    CHECK(stub_gpio_out[PIN_FAM_EN], "FAM_EN not on");
    perch_set(0, true, 330e3f, 0.5f);                 /* the most: a square wave, still no overlap */
    top = stub_pwm.slice[PWM_SLICE_FAM1].top;
    cc = stub_pwm.slice[PWM_SLICE_FAM1].cc;
    both = 0;
    for (uint32_t v = 0; v <= top; v++)
        both += ((v < (cc & 0xffffu)) != stub_pwm_inv_a[PWM_SLICE_FAM1]) && ((v < (cc >> 16)) != stub_pwm_inv_b[PWM_SLICE_FAM1]);
    CHECK(both == 0, "perch legs overlap at duty 0.5");
    perch_set(0, false, 0.0f, 0.0f);
    CHECK(!stub_gpio_out[PIN_FAM_EN], "FAM_EN still on with both perches off");
    printf("perch bridge: legs never high together; 150 kHz at duty 0.25 set to %.0f Hz\n", (double)got);
}

static void test_no_12v(void)
{
    v12 = 0.0f;
    run_ms(1000);
    CHECK(!rt.power_ok, "power_ok without 12 V");
    bool accepted = rt_coil_request(COIL_PEND1, 0.3f, 500, RT_OWNER_CONSOLE);
    run_ms(100);
    CHECK(!accepted, "a request accepted on USB power alone");
    CHECK(asleep() && bridges_plain_low() && coil_current(COIL_PEND1) == 0.0f, "a coil driven on USB power");
    printf("USB power only: requests refused, bridges asleep\n");
}

static void test_request(void)
{
    v12 = 12.0f;
    v5 = 5.0f;
    run_ms(600);
    CHECK(rt.power_ok, "12 V not recognised after 0.6 s");
    CHECK(rt_coil_request(COIL_PEND1, 0.3f, 100, RT_OWNER_PEND), "request refused with 12 V");
    long t0 = ticks, woke = -1;
    float i_at = 0.0f;
    for (int k = 0; k < 50; k++) {
        tick();
        if (woke < 0 && fabsf(coil_current(COIL_PEND1)) > 0.01f) {
            woke = ticks - t0;
            break;
        }
    }
    run_ms(10);
    i_at = coil_current(COIL_PEND1);
    CHECK(woke > 0 && woke <= 20, "the coil started after %ld ticks", woke);
    CHECK(fabsf(i_at - 0.3f) < 0.01f, "0.3 A asked, %.3f A made", (double)i_at);
    CHECK(fabsf(rt.i_meas[COIL_PEND1] - 0.3f) < 0.02f, "the mirror reads %.3f", (double)rt.i_meas[COIL_PEND1]);
    run_ms(95);
    CHECK(coil_current(COIL_PEND1) == 0.0f, "still driven after the deadline: %.3f", (double)coil_current(COIL_PEND1));
    CHECK(!asleep(), "asleep too soon");
    run_ms(1100);
    CHECK(asleep() && bridges_plain_low(), "not asleep a second after the last request");
    printf("request: current after %.1f ms (tWAKE 1 ms), 0.3 A -> %.3f A, off at its deadline, asleep after 1 s\n",
           (double)woke / 10.0, (double)i_at);
}

static void test_limits(void)
{
    rt_coil_request(COIL_PEND2, 2.0f, 200, RT_OWNER_CONSOLE);
    run_ms(20);
    float ic = coil_current(COIL_PEND2);
    rt_coil_request(COIL_PEND2, -2.0f, 200, RT_OWNER_PEND);
    run_ms(20);
    float ip = coil_current(COIL_PEND2);
    rt_coil_request(COIL_PEND2, 2.0f, 200, RT_OWNER_FILM);
    run_ms(20);
    float iff = coil_current(COIL_PEND2);
    rt_coil_release_owner(RT_OWNER_FILM);
    run_ms(5);
    CHECK(fabsf(ic - CONSOLE_I_MAX_A) < 0.03f, "console 2 A -> %.3f", (double)ic);
    CHECK(fabsf(ip + PEND_I_MAX_A) < 0.03f, "pendulum -2 A -> %.3f", (double)ip);
    CHECK(fabsf(iff - FILM_I_MAX_A) < 0.03f, "film 2 A -> %.3f", (double)iff);
    CHECK(coil_current(COIL_PEND2) == 0.0f, "released, still driven");
    printf("limits: 2 A asked -> console %.2f A, pendulum %.2f A, film %.2f A\n", (double)ic, (double)ip, (double)iff);
}

static void test_brownout(void)
{
    rt_coil_request(COIL_PEND2, 0.4f, 5000, RT_OWNER_FILM);
    run_ms(20);
    CHECK(fabsf(coil_current(COIL_PEND2) - 0.4f) < 0.02f, "not driving before the brown-out");
    v12 = 9.0f;
    long t0 = ticks, off = -1;
    for (int k = 0; k < 100; k++) {
        tick();
        if (asleep() && bridges_plain_low()) {
            off = ticks - t0;
            break;
        }
    }
    CHECK(off > 0 && off <= 20, "brown-out: off after %ld ticks", off);
    CHECK(rt.faults & RT_FAULT_BROWNOUT, "no brown-out fault");
    v12 = 12.0f;
    run_ms(300);
    CHECK(!rt.power_ok && asleep(), "back on before 12 V held half a second");
    run_ms(400);
    CHECK(rt.power_ok, "12 V back but not recognised");
    run_ms(20);
    CHECK(fabsf(coil_current(COIL_PEND2) - 0.4f) < 0.02f, "the request did not resume: %.3f",
          (double)coil_current(COIL_PEND2));
    rt_coil_release_owner(RT_OWNER_FILM);
    rt.clear_req++;
    run_ms(5);
    printf("brown-out: 12 V -> 9 V, every coil off within %.1f ms; resumes after 0.5 s of good 12 V\n",
           (double)off / 10.0);
}

static void test_nfault(void)
{
    rt.clear_req++;
    run_ms(1);
    rt_coil_request(COIL_PEND3, 0.3f, 60000, RT_OWNER_FILM);
    run_ms(20);
    long worst = 0;
    for (int n = 0; n < 3; n++) {
        CHECK(fabsf(coil_current(COIL_PEND3) - 0.3f) < 0.02f, "nFAULT %d: not driving before", n);
        stub_gpio_in[PIN_DRV_nFAULT] = false;         /* a DRV8874 pulls it low */
        long t0 = ticks, off = -1;
        for (int k = 0; k < 100; k++) {
            tick();
            if (asleep()) {
                off = ticks - t0;
                break;
            }
        }
        if (off > worst)
            worst = off;
        CHECK(off > 0 && off <= 15, "nFAULT %d: asleep after %ld ticks", n, off);
        CHECK(rt.faults & RT_FAULT_NFAULT, "no nFAULT fault");
        stub_gpio_in[PIN_DRV_nFAULT] = true;          /* asleep: the DRV8874 lets go */
        run_ms(50);
        CHECK(asleep(), "nFAULT %d: retried before 100 ms", n);
        run_ms(60);
        if (n < 2)
            CHECK(!asleep() && fabsf(coil_current(COIL_PEND3) - 0.3f) < 0.02f, "nFAULT %d: no retry", n);
    }
    CHECK(rt.faults & RT_FAULT_LATCHED_OFF, "three nFAULTs in a minute did not latch");
    run_ms(200);
    CHECK(asleep() && coil_current(COIL_PEND3) == 0.0f, "latched off, but driving");
    CHECK(!rt_coil_request(COIL_PEND3, 0.3f, 1000, RT_OWNER_CONSOLE), "latched off, request accepted");
    rt.clear_req++;
    run_ms(20);
    CHECK(!(rt.faults & RT_FAULT_LATCHED_OFF) && fabsf(coil_current(COIL_PEND3) - 0.3f) < 0.02f,
          "after clear: %.3f A", (double)coil_current(COIL_PEND3));
    rt_coil_release_owner(RT_OWNER_FILM);
    rt_coil_release_owner(RT_OWNER_CONSOLE);
    run_ms(5);
    printf("nFAULT: off within %.1f ms, retried after 100 ms, latched after three; clear brings it back\n",
           (double)worst / 10.0);
}

static void test_mirrors(void)
{
    rt.clear_req++;
    coil_r[COIL_PEND1] = 0.3f;                        /* a short: far more current than asked */
    rt_coil_request(COIL_PEND1, 0.3f, 5000, RT_OWNER_FILM);
    run_ms(30);
    CHECK(rt.faults & RT_FAULT_OVERCURRENT, "a shorted coil not caught");
    CHECK(coil_current(COIL_PEND1) == 0.0f, "a shorted coil still driven: %.2f A", (double)coil_current(COIL_PEND1));
    coil_r[COIL_PEND1] = 1e6f;                        /* open */
    rt.clear_req++;
    run_ms(1);
    rt_coil_request(COIL_PEND1, 0.4f, 5000, RT_OWNER_FILM);
    run_ms(60);
    CHECK(rt.faults & RT_FAULT_OPEN_COIL, "an open coil not caught");
    CHECK(rt_coil_owner(COIL_PEND1) == RT_OWNER_NONE, "an open coil's request still held");
    coil_r[COIL_PEND1] = COIL_R20_OHM;
    rt.clear_req++;
    run_ms(1200);
    printf("mirrors: a shorted coil (overcurrent) and an open one are caught and released\n");
}

static void test_thermal(void)
{
    rt.clear_req++;
    float hottest = 0.0f, last_i = 0.0f;
    for (int s = 0; s < 600; s++) {                   /* ten minutes of 1 A asked for, continuously */
        rt_coil_request(COIL_PEND1, FILM_I_MAX_A, 1500, RT_OWNER_FILM);
        run_ms(1000);
        hottest = fmaxf(hottest, rt.temp_C[COIL_PEND1]);
        last_i = coil_current(COIL_PEND1);
    }
    CHECK(hottest <= COIL_SURFACE_LIMIT_C + 0.5f, "THERMAL: %.1f C", (double)hottest);
    CHECK(last_i < 0.6f, "THERMAL: still %.2f A at the limit", (double)last_i);
    rt_coil_release_owner(RT_OWNER_FILM);
    run_ms(1200);
    printf("thermal: 1 A asked for ten minutes: model hottest %.1f C (limit %.0f), the plant's coil %.1f C, derated to %.2f A\n",
           (double)hottest, (double)COIL_SURFACE_LIMIT_C, (double)coil_t[COIL_PEND1], (double)last_i);
    CHECK(coil_t[COIL_PEND1] <= COIL_SURFACE_LIMIT_C + 2.0f, "THERMAL: the plant's coil reached %.1f C",
          (double)coil_t[COIL_PEND1]);
}

static void test_lev_cal(void)
{
    rt.clear_req++;
    run_ms(5);
    lev_enable(&rt_lev, true);                        /* never calibrated: a coil CAL first, no bat */
    lev_state seen_cal = LEV_OFF;
    for (int k = 0; k < 30000 && rt_lev.state != LEV_WAIT; k++) {
        tick();
        if (rt_lev.state == LEV_CAL)
            seen_cal = LEV_CAL;
    }
    lev_telemetry t;
    lev_get_telemetry(&rt_lev, &t);
    CHECK(seen_cal == LEV_CAL, "LEV: no CAL on the first enable");
    CHECK(rt_lev.state == LEV_WAIT, "LEV: not waiting for the bat after CAL (%s: %s)", lev_state_name(rt_lev.state),
          t.cal ? t.cal : "");
    CHECK(t.cal && !strncmp(t.cal, "coil ok", 7), "LEV: CAL said '%s'", t.cal ? t.cal : "(null)");
    CHECK(fabsf(fabsf(t.kcs_mT_per_A) - hall_coil_mT_per_A) < 0.3f, "LEV: coil field %.3f mT/A",
          (double)t.kcs_mT_per_A);
    run_ms(200);
    CHECK(coil_current(COIL_LEV) == 0.0f, "LEV: no bat, but the coil drives %.3f A", (double)coil_current(COIL_LEV));
    rt.lev_eyes = 0.5f;
    run_ms(10);
    CHECK(!rt.carrier_on, "LEV: the eyes' carrier on with no bat floating");
    lev_enable(&rt_lev, false);
    run_ms(1200);
    CHECK(asleep(), "LEV: bridges awake after lev off");
    printf("levitation through the glue: CAL found %.3f mT/A (plant %.2f), waits with the coil off; no carrier without a bat\n",
           (double)t.kcs_mT_per_A, (double)hall_coil_mT_per_A);
}

/* THE LEVITATION COIL'S THERMOMETER (bench 2026-11-08): its model alone stopped every hover
 * after 2-3 minutes while the perch felt only warm.  Here the plant's coil loses heat three
 * times better than the model assumes (15 K/W, not 43) and its resistance is the pendulum
 * coils' 2.29 ohm, not the 2.56 the model starts from.  0.5 A for 150 s: the model
 * alone would read over 20 K of rise and derate near its 50 C board limit; with the V/I
 * readings it must follow the plant. */
static void test_lev_thermometer(void)
{
    rt.clear_req++;
    coil_rth[COIL_LEV] = 15.0f;
    run_ms(65000);                                    /* cold for a minute: the reference calibrates */
    uint32_t n0 = rt.lev_r_readings;
    float worst = 0.0f;
    for (int s = 0; s < 150; s++) {
        rt_coil_request(COIL_LEV, 0.5f, 2000, RT_OWNER_CONSOLE);
        run_ms(1000);
        if (s >= 60)
            worst = fmaxf(worst, fabsf(rt.temp_C[COIL_LEV] - coil_t[COIL_LEV]));
    }
    float model = rt.temp_C[COIL_LEV], plant = coil_t[COIL_LEV], i = coil_current(COIL_LEV);
    rt_coil_release_owner(RT_OWNER_CONSOLE);
    run_ms(1200);
    printf("lev thermometer: 0.5 A for 150 s: plant %.1f C, model %.1f C (worst %.1f K off after the first minute), "
           "%lu readings, last %.3f ohm, calibrated %d, %.3f A at the end\n",
           (double)plant, (double)model, (double)worst, (unsigned long)(rt.lev_r_readings - n0),
           (double)rt.lev_r_meas_ohm, (int)rt_thermal[COIL_LEV].r_calibrated, (double)i);
    CHECK(rt.lev_r_readings - n0 > 1000, "LEV THERMOMETER: only %lu readings", (unsigned long)(rt.lev_r_readings - n0));
    CHECK(rt_thermal[COIL_LEV].r_calibrated, "LEV THERMOMETER: the reference never calibrated");
    CHECK(worst < 4.0f, "LEV THERMOMETER: the model was %.1f K off the plant", (double)worst);
    CHECK(i > 0.45f, "LEV THERMOMETER: derated to %.3f A although the coil is only %.1f C", (double)i, (double)plant);
    coil_rth[COIL_LEV] = 43.0f;
}

/* CLOCK WRAP (bench 2026-11-08): with 32-bit deadlines and a signed difference, every coil
 * was forbidden from 2147.5 s of uptime (2^31 us) for the next 35.8 min, and an expired
 * request would have come back 2^31 us after its deadline.  The deadlines are 64-bit now:
 * jump the clock across 2^31 and 2^32 us and check both, and an nFAULT retry armed just
 * before time_us_32 wraps. */
static void test_clock_wrap(void)
{
    v12 = 12.0f;
    v5 = 5.0f;
    rt.clear_req++;
    run_ms(600);
    CHECK(rt.power_ok && rt.faults == 0, "WRAP: not ready (faults %#lx)", (unsigned long)rt.faults);
    /* a request that expires, then the clock 2^31 us + 1 s on: it must stay expired */
    rt_coil_request(COIL_PEND1, 0.3f, 50, RT_OWNER_CONSOLE);
    run_ms(20);
    CHECK(fabsf(coil_current(COIL_PEND1) - 0.3f) < 0.02f, "WRAP: the request did not drive");
    run_ms(1200);
    CHECK(asleep(), "WRAP: not asleep after the request");
    stub_now_us += (1ull << 31) + 1000000u;
    run_ms(1200);
    CHECK(asleep() && coil_current(COIL_PEND1) == 0.0f, "WRAP: an expired request came back after 2^31 us");
    CHECK(rt_coil_owner(COIL_PEND1) == RT_OWNER_NONE, "WRAP: core 0 sees the expired request's owner again");
    /* past 2^31 us of uptime: coils still allowed (a fresh request drives) */
    CHECK(stub_now_us > (1ull << 31), "WRAP: the clock is not past 2^31 us");
    rt_coil_request(COIL_PEND2, 0.3f, 100, RT_OWNER_PEND);
    run_ms(20);
    CHECK(fabsf(coil_current(COIL_PEND2) - 0.3f) < 0.02f, "WRAP: past 2^31 us a fresh request does not drive (%.3f A)",
          (double)coil_current(COIL_PEND2));
    CHECK(rt_coil_owner(COIL_PEND2) == RT_OWNER_PEND, "WRAP: core 0 does not see the fresh request");
    run_ms(1200);
    /* across time_us_32's wrap (2^32 us), with a request running through it */
    stub_now_us = (1ull << 32) - 30000u;
    run_ms(10);
    rt_coil_request(COIL_PEND1, 0.3f, 100, RT_OWNER_CONSOLE);
    run_ms(50);                                        /* across the wrap */
    CHECK(fabsf(coil_current(COIL_PEND1) - 0.3f) < 0.02f, "WRAP: a request across 2^32 us stopped (%.3f A)",
          (double)coil_current(COIL_PEND1));
    run_ms(60);
    CHECK(coil_current(COIL_PEND1) == 0.0f, "WRAP: a request across 2^32 us outlived its 100 ms");
    run_ms(1200);
    /* an nFAULT just before the wrap: asleep for 100 ms across it, then the retry */
    stub_now_us = (1ull << 33) - 60000u;
    rt.clear_req++;
    run_ms(5);
    rt_coil_request(COIL_PEND3, 0.3f, 2000, RT_OWNER_FILM);
    run_ms(20);
    CHECK(fabsf(coil_current(COIL_PEND3) - 0.3f) < 0.02f, "WRAP: not driving before the nFAULT");
    stub_gpio_in[PIN_DRV_nFAULT] = false;
    for (int k = 0; k < 100 && !asleep(); k++)
        tick();
    CHECK(asleep() && (rt.faults & RT_FAULT_NFAULT), "WRAP: the nFAULT did not stop the bridges");
    stub_gpio_in[PIN_DRV_nFAULT] = true;
    run_ms(50);                                        /* the retry deadline lies past the wrap */
    CHECK(asleep(), "WRAP: retried before 100 ms across the wrap");
    run_ms(60);
    CHECK(!asleep() && fabsf(coil_current(COIL_PEND3) - 0.3f) < 0.02f, "WRAP: no retry after the wrap");
    rt_coil_release_owner(RT_OWNER_FILM);
    rt_coil_release_owner(RT_OWNER_CONSOLE);
    rt_coil_release_owner(RT_OWNER_PEND);
    rt.clear_req++;
    run_ms(1200);
    CHECK(asleep(), "WRAP: not asleep at the end");
    printf("clock wrap: past 2^31 us coils run, an expired request stays expired; across 2^32 us a request "
           "keeps its length and an nFAULT retry its 100 ms\n");
}

int main(void)
{
    test_safe();
    rt_start(true, NULL);
    CHECK(stub_irq_handler[PWM_IRQ_WRAP_1] && stub_irq_handler[DMA_IRQ_1], "core 1 did not install its handlers");
    CHECK((stub_pwm.en & (1u << PWM_SLICE_LEV)) && (stub_pwm.en & (1u << PWM_SLICE_TICK)), "tick or LEV slice off");
    test_pwm_math();
    test_no_12v();
    test_request();
    test_limits();
    test_brownout();
    test_nfault();
    test_mirrors();
    test_thermal();
    test_lev_cal();
    test_lev_thermometer();
    CHECK(rt.overruns == 0, "%lu overruns", (unsigned long)rt.overruns);
    CHECK(!(rt.faults & RT_FAULT_ADC), "ADC fault after the ordinary tests");
    CHECK(stub_drain_while_running == 0, "the FIFO was drained %d times with the ADC running",
          stub_drain_while_running);
    /* the race of 2026-11-07: the burst has finished and its DMA interrupt is pending when
     * the tick runs.  The tick must not drain the FIFO with the ADC still free-running (that
     * spun for ever on rev A).  Since 2026-11-08 it does the completion's work itself (stop
     * the ADC, take the buffer), starts the next burst and runs the work; the completion
     * interrupt, when it then runs, does nothing (and above all does not stop the new burst) */
    {
        stub_now_us += 100u;
        stub_irq_handler[PWM_IRQ_WRAP_1]();               /* a burst starts */
        stub_adc_running = true;                          /* the ADC free-runs past the burst */
        stub_dma_busy = false;
        stub_dma_irq_pending = true;                      /* ... its completion not yet run */
        uint32_t before = rt.ticks, over = rt.overruns;
        stub_now_us += 100u;
        stub_irq_handler[PWM_IRQ_WRAP_1]();
        CHECK(stub_drain_while_running == 0, "RACE: drained the FIFO with the ADC running");
        CHECK(stub_dma_busy && stub_adc_running, "RACE: no new burst after a pending completion");
        CHECK(rt.ticks == before + 1, "RACE: the work did not run on the completed burst");
        CHECK(rt.overruns == over, "RACE: counted as an overrun");
        stub_irq_handler[DMA_IRQ_1]();                    /* the stale completion interrupt */
        CHECK(stub_adc_running, "RACE: the stale completion stopped the new burst");
        stub_dma_busy = false;
        stub_dma_irq_pending = true;
        stub_irq_handler[DMA_IRQ_1]();
        run_ms(10);
        CHECK(rt.ticks == before + 101, "ticks %lu after the race, expected %lu", (unsigned long)rt.ticks,
              (unsigned long)(before + 101));
    }
    /* ADC FAULT: a rate, not a count.  0.5 % of ticks lost for three seconds: no fault;
     * a flash write's 200 ms pause: a pause, no fault; 5 % lost: the fault */
    {
        run_ms(1100);
        rt.clear_req++;
        run_ms(1100);
        CHECK(!(rt.faults & RT_FAULT_ADC), "ADC: latched before anything was lost (%lu overruns)",
              (unsigned long)rt.overruns);
        for (int k = 0; k < 30000; k++) {
            tick();
            if (k % 200 == 0)
                stub_now_us += 100u;                      /* a wrap swallowed: one tick late */
        }
        CHECK(!(rt.faults & RT_FAULT_ADC), "ADC: latched at 0.5 %% lost (%lu in the last second)",
              (unsigned long)rt.skipped_last_s);
        unsigned long low_rate = (unsigned long)rt.skipped_last_s;
        CHECK(low_rate >= 40 && low_rate <= 60, "ADC: %lu skipped in a second at 0.5 %%", low_rate);
        uint32_t pauses = rt.pauses;
        stub_now_us += 200000u;                           /* core 1 parked by a flash write */
        run_ms(2100);
        CHECK(rt.pauses == pauses + 1, "ADC: the pause was not counted as one");
        CHECK(!(rt.faults & RT_FAULT_ADC), "ADC: latched by a flash write's pause");
        for (int k = 0; k < 30000; k++) {
            tick();
            if (k % 20 == 0)
                stub_now_us += 100u;
        }
        CHECK(rt.faults & RT_FAULT_ADC, "ADC: not latched at 5 %% lost (%lu in the last second)",
              (unsigned long)rt.skipped_last_s);
        rt.clear_req++;
        run_ms(2100);
        CHECK(!(rt.faults & RT_FAULT_ADC), "ADC: back after clear");
        printf("adc fault: a rate (0.5 %% lost: none, %lu a second; a 200 ms pause: none; 5 %%: latched)\n",
               low_rate);
    }
    test_clock_wrap();
    printf("%ld ticks (%.0f s of core 1)\n", ticks, (double)ticks / CTRL_TICK_HZ);
    if (failures) {
        printf("test_rt: %d FAILED\n", failures);
        return 1;
    }
    printf("test_rt: all passed\n");
    return 0;
}
