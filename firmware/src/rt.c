/* rt.c: core 1's 10 kHz tick.  See rt.h. */
#include "rt.h"
#include "board.h"
#include "board_pins.h"
#include "coils.h"
#include "config.h"
#include "hardware/adc.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/pwm.h"
#include "hardware/sync.h"
#include "pico/flash.h"
#include "pico/multicore.h"
#include "pico/time.h"
#include <math.h>
#include <string.h>

#ifdef OWL_DIAG
/* the boot-diagnostic build (cmake -DOWL_DIAG=1): where core 1's tick is, and what a hard
 * fault on either core stacked.  The SDK's default handler is a breakpoint, which with no
 * debugger attached locks the core up silently; this one records the fault and parks. */
volatile uint32_t rt_diag_stage, rt_diag_fault_core = 99u, rt_diag_pc, rt_diag_lr, rt_diag_cfsr, rt_diag_hfsr,
    rt_diag_bfar, rt_diag_mmfar, rt_diag_sp;
void rt_diag_fault_c(uint32_t *sp)
{
    rt_diag_sp = (uint32_t)sp;
    rt_diag_lr = sp[5];
    rt_diag_pc = sp[6];
    rt_diag_cfsr = *(volatile uint32_t *)0xE000ED28u;
    rt_diag_hfsr = *(volatile uint32_t *)0xE000ED2Cu;
    rt_diag_mmfar = *(volatile uint32_t *)0xE000ED34u;
    rt_diag_bfar = *(volatile uint32_t *)0xE000ED38u;
    rt_diag_fault_core = get_core_num();
    for (;;)
        __wfi();
}
__attribute__((naked)) void isr_hardfault(void)
{
    __asm volatile("tst lr, #4\n"
                   "ite eq\n"
                   "mrseq r0, msp\n"
                   "mrsne r0, psp\n"
                   "b rt_diag_fault_c\n");
}
#define STAGE(n) (rt_diag_stage = (n))
#else
#define STAGE(n) ((void)0)
#endif

rt_shared rt;
lev_ctrl rt_lev;
thermal_coil rt_thermal[COIL_COUNT];

#define BURST ((int)(3 * ADC_OVERSAMPLE))   /* the three ADC lines (ADC_SLOT_*), ADC_OVERSAMPLE times */
/* Two bursts' buffers: the DMA fills one while control() reads the other (rt.h). */
static uint16_t burst[2][BURST];
static unsigned burst_mux[2];               /* the multiplexer channel each buffer's ADC2 samples carry */
static int filling = 0;                     /* the buffer the DMA is filling, or last filled */
static volatile int ready = -1;             /* a completed buffer not yet given to control(), or -1 */
static int dma_ch;
static unsigned mux_ch;                     /* the channel the multiplexer is on now */
static uint32_t last_tick_us;
static bool ticked;

/* ---- requests from core 0 ---------------------------------------------------------- */
/* Every deadline here is 64-bit microseconds (time_us_64: 584 000 years).  Until
 * 2026-11-08 they were 32-bit with a signed difference, which reads a deadline 2^31 us
 * (35.8 min) in the past as one in the future: at 2147.5 s of uptime the nFAULT retry
 * deadline (0, never armed) forbade every coil for the next 35.8 min, and an expired coil
 * request would have come back to life for as long (bringup/REVB.md 1.8). */
typedef struct {
    volatile uint32_t seq;                  /* odd while core 0 writes */
    volatile float amps;
    volatile uint64_t until_us;             /* two words: read under seq */
    volatile uint8_t owner;
} coil_req;
static coil_req req[COIL_COUNT];

typedef struct {
    float amps;
    uint64_t until_us;
    int owner;
    uint32_t steady_ticks;
} coil_cmd;
static coil_cmd cmd[COIL_COUNT];            /* core 1's copy */

bool rt_coil_request(int coil, float amps, uint32_t ms, int owner)
{
    if (coil < 0 || coil >= COIL_COUNT || !(amps == amps) || owner == RT_OWNER_NONE)
        return false;
    coil_req *r = &req[coil];
    r->seq++;
    __dmb();
    r->amps = amps;
    r->owner = (uint8_t)owner;
    r->until_us = time_us_64() + (uint64_t)ms * 1000u;
    __dmb();
    r->seq++;
    return rt.power_ok && !(rt.faults & RT_FAULT_LATCHED_OFF);
}

void rt_coil_release_owner(int owner)
{
    for (int c = 0; c < COIL_COUNT; c++)
        if (req[c].owner == owner) {
            coil_req *r = &req[c];
            r->seq++;
            __dmb();
            r->amps = 0.0f;
            r->owner = RT_OWNER_NONE;
            r->until_us = 0;                /* expired for good */
            __dmb();
            r->seq++;
        }
}

int rt_coil_owner(int coil)
{
    if (coil < 0 || coil >= COIL_COUNT)
        return RT_OWNER_NONE;
    for (;;) {                              /* a consistent (owner, until) pair */
        uint32_t s = req[coil].seq;
        if (s & 1u)
            continue;
        __dmb();
        int owner = req[coil].owner;
        uint64_t until = req[coil].until_us;
        __dmb();
        if (req[coil].seq == s)
            return until > time_us_64() ? owner : RT_OWNER_NONE;
    }
}

/* core 1: refresh its copy if core 0 is not in the middle of writing */
static void take_request(int c)
{
    uint32_t s = req[c].seq;
    if (s & 1u)
        return;
    __dmb();
    coil_cmd n = {req[c].amps, req[c].until_us, req[c].owner, cmd[c].steady_ticks};
    __dmb();
    if (req[c].seq != s)
        return;
    if (n.amps != cmd[c].amps || n.owner != cmd[c].owner)
        n.steady_ticks = 0;
    cmd[c] = n;
}

static void cancel_request(int c)
{
    cmd[c].owner = RT_OWNER_NONE;
    cmd[c].amps = 0.0f;
    req[c].owner = RT_OWNER_NONE;           /* core 0 sees it gone */
}

const char *rt_fault_name(unsigned bit)
{
    static const char *const NAMES[] = RT_FAULT_NAMES;
    return bit < sizeof NAMES / sizeof NAMES[0] ? NAMES[bit] : "?";
}

/* ---- the bridges' sleep -------------------------------------------------------------- */
enum { DRV_ASLEEP, DRV_WAKING, DRV_AWAKE };
static int drv = DRV_ASLEEP;
static uint32_t drv_ticks, idle_ticks;

static void drv_off(void)
{
    for (int c = 0; c < COIL_COUNT; c++)
        coil_coast(c);
    coils_connect(false);                   /* the pins plain and low */
    board_drv_sleep(true);
    drv = DRV_ASLEEP;
    rt.drv_awake = false;
}

/* the thermal derate, or 1 while the bench has the cutoff off (rt.thermal_cut_off) */
static float derate_of(int c) { return rt.thermal_cut_off ? 1.0f : thermal_derate(&rt_thermal[c]); }

bool rt_coils_idle(void) { return !rt.drv_awake && rt_lev.state == LEV_OFF; }

/* ---- the levitation PWM and the tick, in step ---------------------------------------- */
static bool carrier_now;
static int resync;                          /* 1: new TOPs written, re-align on the next tick */

static void align_lev_and_tick(void)
{
    /* the EN register's atomic clear and set aliases: one write stops both, one starts both
     * (the tick then wraps at the coil period's start), and core 0 enabling its own slices
     * meanwhile (perch_init) cannot be undone by a read-modify-write here */
    uint32_t both = (1u << PWM_SLICE_LEV) | (1u << PWM_SLICE_TICK);
    hw_clear_bits(&pwm_hw->en, both);
    pwm_set_counter(PWM_SLICE_LEV, 0);
    pwm_set_counter(PWM_SLICE_TICK, 0);
    hw_set_bits(&pwm_hw->en, both);
}

static void control(const uint16_t *b, unsigned mux);
static float eye_env;                       /* the eyes' carrier, 0..1 (the blink's envelope) */

/* the ADC fault's one-second window (end of control()); a clear restarts it, so that
 * overruns from before the clear cannot latch the fault again (test_rt, 2026-11-08) */
static uint64_t win_at;
static uint32_t win_over, win_err;

/* The coils' PWM as the last control() left it, applied once the burst it overlapped is
 * over: every burst then runs under one u from start to end, the one computed in the
 * previous tick (the levitation's model allows for that: lev_ctrl.u_lag = 1). */
static struct {
    bool pending, awake;
    bool on[COIL_COUNT];
    float u[COIL_COUNT];
    float lev_alt;
} pwm_next;

static void apply_pwm(void)
{
    if (!pwm_next.pending)
        return;
    pwm_next.pending = false;
    if (!pwm_next.awake || drv != DRV_AWAKE)   /* the bridges went to sleep meanwhile: nothing */
        return;
    for (int c = 0; c < COIL_COUNT; c++) {
        if (pwm_next.on[c])
            coil_set_u(c, pwm_next.u[c], c == COIL_LEV ? pwm_next.lev_alt : 0.0f);
        else
            coil_coast(c);
    }
}

/* the burst's completion: stop the ADC (it free-runs) and move the multiplexer on, so it
 * settles for the rest of the period before the next burst.  Nothing else: control()
 * runs from the tick, not from here.  Idempotent, because the tick may have done this
 * itself (burst_done from tick_isr) and left this interrupt pending. */
static void burst_done(void)
{
    if (!dma_irqn_get_channel_status(1, (uint)dma_ch))
        return;
    dma_irqn_acknowledge_channel(1, (uint)dma_ch);
    adc_run(false);
    burst_mux[filling] = mux_ch;
    ready = filling;
    mux_ch = (mux_ch + 1u) % MUX_CHANNELS;
    board_mux_select(mux_ch);
    apply_pwm();                            /* the last control()'s, if it finished during the burst */
}

static void adc_done_isr(void) { burst_done(); }

static void tick_isr(void)
{
    STAGE(100);
    pwm_clear_irq(PWM_SLICE_TICK);
    uint32_t now = time_us_32();
    if (ticked) {
        /* ticks lost since the last one: the wrap's interrupt pends once, so a tick handled
         * late swallows the wraps in between.  A long gap is core 1 parked on purpose (a
         * flash write: flash_safe_execute), not an overrun. */
        uint32_t gap = now - last_tick_us, period = 1000000u / CTRL_TICK_HZ;
        if (gap > RT_PAUSE_US)
            rt.pauses++;
        else if (gap > period + period / 2u)
            rt.overruns += (gap + period / 2u) / period - 1u;
    }
    last_tick_us = now;
    ticked = true;
    if (dma_channel_is_busy((uint)dma_ch)) {
        rt.overruns++;                      /* the burst is still running: no new one, no work */
        return;
    }
    /* the burst is done; if its completion interrupt has not run yet (it outranks this
     * one, so only if it became pending a moment ago), do its work here.  The ADC is then
     * stopped either way, so the drain below cannot spin (the lock-up of 2026-11-07) */
    uint32_t irq = save_and_disable_interrupts();   /* not interleaved with adc_done_isr's own */
    burst_done();
    restore_interrupts(irq);
    if (resync == 1) {
        align_lev_and_tick();
        resync = 0;
    } else {
        /* the eyes' carrier while the bat is held, blinking (Jason, 2026-11-09): every 2 s
         * the eyes close over 0.2 s, stay closed 0.5 s, open over 0.2 s.  The carrier stays
         * on through the blink, only its strength (eye_env) going to nothing: switching it
         * off and on changes the coil's PWM frequency and jolted the loop every blink (the
         * gap's sd 0.34 mm against 0.23 without eyes).  So the thermometer (6b) does not
         * read while the eyes are on; it read 17 K high in the blinks anyway, and the
         * fitted model matched the IR camera (bringup/REVB.md 1.11) */
        static uint32_t eye_ticks;
        bool held = rt.lev_eyes > 0.0f && rt_lev.state == LEV_HOLD;
        eye_ticks = held ? eye_ticks + 1u : 0u;
        uint32_t ph = eye_ticks % LEV_EYE_PERIOD_TICKS;
        const uint32_t open_end = LEV_EYE_PERIOD_TICKS - 2u * LEV_EYE_FADE_TICKS - LEV_EYE_OFF_TICKS;
        if (ph < open_end)
            eye_env = 1.0f;
        else if (ph < open_end + LEV_EYE_FADE_TICKS)
            eye_env = 1.0f - (float)(ph - open_end) / (float)LEV_EYE_FADE_TICKS;
        else if (ph < open_end + LEV_EYE_FADE_TICKS + LEV_EYE_OFF_TICKS)
            eye_env = 0.0f;
        else
            eye_env = (float)(ph - open_end - LEV_EYE_FADE_TICKS - LEV_EYE_OFF_TICKS) / (float)LEV_EYE_FADE_TICKS;
        bool want = held;
        if (want != carrier_now) {
            coil_lev_frequency(want);       /* both TOPs latch at their next wraps */
            pwm_set_wrap(PWM_SLICE_TICK, (uint16_t)TOP_TICK(coil_top(COIL_LEV)));
            carrier_now = want;
            rt.carrier_on = want;
            resync = 1;
        }
    }
    STAGE(101);
    adc_fifo_drain();                       /* waits for the last conversion, drops strays */
    STAGE(102);
    /* the next burst first, at the period's start, into the other buffer ... */
    int done = ready;
    ready = -1;
    filling = done >= 0 ? 1 - done : filling;
    adc_select_input(ADC_RR_FIRST);
    dma_channel_transfer_to_buffer_now((uint)dma_ch, burst[filling], BURST);
    adc_run(true);
    STAGE(103);
    /* ... then this tick's work on the last one, while it converts: the whole period for
     * control() instead of what the burst left of it (the samples are 50 us older) */
    if (done >= 0)
        control(burst[done], burst_mux[done]);
}

/* ---- the tick's work ------------------------------------------------------------------ */
static float avg[3];
static uint32_t fresh_mux_tick[COIL_COUNT];   /* when each pendulum coil's mirror was last read */

static void mux_sample(unsigned ch, float v)
{
    rt.raw_mux[ch] = (uint16_t)(v * (4096.0f / ADC_VREF_V));
    if (ch == MUX_CH_PEND1_IPROPI) {
        rt.i_meas[COIL_PEND1] = v / IPROPI_V_PER_A;
        fresh_mux_tick[COIL_PEND1] = rt.ticks;
    } else if (ch == MUX_CH_PEND2_IPROPI) {
        rt.i_meas[COIL_PEND2] = v / IPROPI_V_PER_A;
        fresh_mux_tick[COIL_PEND2] = rt.ticks;
    } else if (ch == MUX_CH_PEND3_IPROPI) {
        rt.i_meas[COIL_PEND3] = v / IPROPI_V_PER_A;
        fresh_mux_tick[COIL_PEND3] = rt.ticks;
    } else if (ch == MUX_CH_FAM1_ISENSE) {
        rt.fam_isense[0] = v / FAM_ISENSE_V_PER_A;
    } else if (ch == MUX_CH_FAM2_ISENSE) {
        rt.fam_isense[1] = v / FAM_ISENSE_V_PER_A;
    } else if (ch == MUX_CH_V12_SENSE) {
        rt.v12 = v / V12_DIVIDER;
    } else if (ch == MUX_CH_V5_SENSE) {
        rt.v5 = v / V5_DIVIDER;
    } else if (ch == MUX_CH_VBUS_SENSE) {
        rt.vbus = v / VBUS_DIVIDER;
    }
}

static float clampf_(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

static float owner_limit(int owner)
{
    switch (owner) {
    case RT_OWNER_FILM: return FILM_I_MAX_A;
    case RT_OWNER_CONSOLE: return CONSOLE_I_MAX_A;
    case RT_OWNER_PEND: return PEND_I_MAX_A;
    default: return 0.0f;
    }
}

static void control(const uint16_t *b, unsigned mux)
{
    uint32_t t_start = time_us_32();        /* for this step's duration only */
    uint64_t now64 = time_us_64();          /* for every deadline (see coil_req) */

    STAGE(1);
    /* 1. the burst's averages; ADC2 is that burst's multiplexer channel */
    uint32_t sum[3] = {0, 0, 0}, n[3] = {0, 0, 0};
    for (int i = 0; i < BURST; i++) {
        uint16_t v = b[i];
        if (v & 0x8000u) {                  /* the FIFO's conversion-error flag */
            rt.adc_errors++;
            continue;
        }
        sum[i % 3] += v & 0x0FFFu;
        n[i % 3]++;
    }
    for (int k = 0; k < 3; k++) {
        if (n[k])
            avg[k] = (float)sum[k] / (float)n[k];
        rt.raw_adc[k] = (uint16_t)avg[k];
    }
    mux_sample(mux, adc_volts(avg[ADC_SLOT_MUX_OUT]));
    rt.hall_mT = (float)HALL_POLARITY * (adc_volts(avg[ADC_SLOT_HALL]) - HALL_VQ_FRACTION * ADC_VREF_V) /
                 (HALL_MV_PER_MT * 1e-3f);
    rt.i_meas[COIL_LEV] = adc_volts(avg[ADC_SLOT_LEV_IPROPI]) / IPROPI_V_PER_A;

    STAGE(2);
    /* 2. faults and power */
    static uint32_t last_clear, v12_good, nf_ticks;
    static uint64_t nf_retry_at, nf_window_at;      /* 0: none (see coil_req) */
    static int nf_count;
    if (rt.clear_req != last_clear) {
        last_clear = rt.clear_req;
        win_at = 0;                         /* the ADC fault's window starts afresh */
        win_over = rt.overruns;
        win_err = rt.adc_errors;
        rt.faults = 0;
        nf_count = 0;
        nf_retry_at = now64;
    }
    bool driving = drv == DRV_AWAKE;
    if (rt.v12 < V12_BROWNOUT_V) {
        if (rt.power_ok && driving)
            rt.faults |= RT_FAULT_BROWNOUT;
        rt.power_ok = false;
        v12_good = 0;
    } else if (rt.v12 > V12_PRESENT_V && !rt.power_ok) {
        if (++v12_good > CTRL_TICK_HZ / 2)   /* half a second of good 12 V */
            rt.power_ok = true;
    }
    if (drv != DRV_ASLEEP && board_drv_fault()) {
        if (++nf_ticks >= CTRL_TICK_HZ / 1000) {      /* 1 ms */
            drv_off();
            driving = false;
            rt.faults |= RT_FAULT_NFAULT;
            rt.nfault_events++;
            if (now64 - nf_window_at > 60000000u) {
                nf_window_at = now64;
                nf_count = 0;
            }
            if (++nf_count >= 3)
                rt.faults |= RT_FAULT_LATCHED_OFF;
            nf_retry_at = now64 + 100000u;  /* asleep for 100 ms clears the DRV8874's latch */
            nf_ticks = 0;
        }
    } else {
        nf_ticks = 0;
    }
    bool allowed = rt.power_ok && !(rt.faults & RT_FAULT_LATCHED_OFF) && now64 >= nf_retry_at;

    STAGE(3);
    /* 3. what each coil should do */
    float u[COIL_COUNT] = {0.0f, 0.0f, 0.0f, 0.0f};
    bool want[COIL_COUNT] = {false, false, false, false};
    for (int c = 0; c < COIL_COUNT; c++) {
        take_request(c);
        cmd[c].steady_ticks++;
    }
    for (int c = 0; c < PEND_COILS; c++) {
        coil_cmd *k = &cmd[c];
        if (k->owner == RT_OWNER_NONE || k->until_us <= now64)
            continue;
        float lim = owner_limit(k->owner) * derate_of(c);
        float a = clampf_(k->amps, -lim, lim);
        if (a == 0.0f || rt.v12 < 1.0f)
            continue;
        u[c] = a * (thermal_r_ohm(&rt_thermal[c]) + DRV_RDSON_OHM) / rt.v12;
        want[c] = true;
    }
    lev_input li = {
        .hall_mT = rt.hall_mT,
        .iprop_A = rt.i_meas[COIL_LEV],
        .v12_V = rt.v12,
        .coil_R_ohm = thermal_r_ohm(&rt_thermal[COIL_LEV]),
        /* allowed, not "awake": the bridges wake within 1.2 ms of the loop wanting them, and
         * nothing the loop asks for in that time matters (WAIT drives nothing; a CAL starts
         * with tens of ms of measuring with the coil off) */
        .coil_allowed = allowed,
        .thermal_trip = derate_of(COIL_LEV) <= 0.0f,
    };
    lev_output lo;
    STAGE(31);
    lev_step(&rt_lev, &li, &lo);
    STAGE(32);
    bool lev_wants = rt_lev.state != LEV_OFF && rt_lev.state != LEV_FAULT;
    if (lo.active) {
        u[COIL_LEV] = lo.u;
        want[COIL_LEV] = true;
    } else if (rt_lev.state == LEV_OFF) {   /* the console may test the coil while the loop is off */
        coil_cmd *k = &cmd[COIL_LEV];
        if (k->owner == RT_OWNER_CONSOLE && k->until_us > now64 && rt.v12 > 1.0f) {
            float lim = CONSOLE_I_MAX_A * derate_of(COIL_LEV);
            float a = clampf_(k->amps, -lim, lim);
            u[COIL_LEV] = a * (thermal_r_ohm(&rt_thermal[COIL_LEV]) + DRV_RDSON_OHM) / rt.v12;
            want[COIL_LEV] = a != 0.0f;
        }
    }

    STAGE(4);
    /* 4. wake the bridges when needed, put them to sleep when not (or not allowed) */
    bool need = lev_wants || want[0] || want[1] || want[2] || want[3];
    switch (drv) {
    case DRV_ASLEEP:
        if (need && allowed) {
            for (int c = 0; c < COIL_COUNT; c++)
                coil_coast(c);
            board_drv_sleep(false);
            coils_connect(true);
            drv = DRV_WAKING;
            drv_ticks = 0;
        }
        break;
    case DRV_WAKING:                        /* tWAKE: 1 ms before the inputs count */
        if (!allowed)
            drv_off();
        else if (++drv_ticks > (DRV_WAKE_US * CTRL_TICK_HZ) / 1000000u + 2u) {
            drv = DRV_AWAKE;
            rt.drv_awake = true;
            idle_ticks = 0;
        }
        break;
    case DRV_AWAKE:
        if (!allowed) {
            if (want[0] || want[1] || want[2] || want[3])
                rt.faults |= rt.power_ok ? 0u : RT_FAULT_BROWNOUT;
            drv_off();
        } else if (!need && ++idle_ticks > CTRL_TICK_HZ) {
            drv_off();                      /* a second with nothing to do: sleep */
        } else if (need) {
            idle_ticks = 0;
        }
        break;
    }

    STAGE(5);
    /* 5. the PWM.  The levitation coil always switches both ways a little (every output
     * pulse at least DRV_MIN_PULSE_S: the mean stays linear down to zero); with the
     * carrier, a lot, but never so much that the loop's mean voltage cannot be made:
     * the carrier yields to the control for as long as the control needs it. */
    float lev_alt = DRV_MIN_PULSE_S * coil_pwm_hz(COIL_LEV);
    if (carrier_now) {
        /* each pulse also carries the bridge's loss, put back by coils.c */
        float room = 0.5f * (1.0f - fabsf(u[COIL_LEV])) - 0.02f - DRV_PULSE_LOSS_S * coil_pwm_hz(COIL_LEV);
        lev_alt = fmaxf(lev_alt, fminf(0.5f * eye_env * clampf_(rt.lev_eyes, 0.0f, LEV_EYES_MAX), room));
    }
    uint32_t irq = save_and_disable_interrupts();   /* not half-written when burst_done applies it */
    pwm_next.awake = drv == DRV_AWAKE;
    pwm_next.lev_alt = lev_alt;
    for (int c = 0; c < COIL_COUNT; c++) {
        bool on = drv == DRV_AWAKE && want[c];
        pwm_next.on[c] = on;
        pwm_next.u[c] = u[c];
        rt.u[c] = on ? u[c] : 0.0f;
    }
    pwm_next.pending = true;
    if (!dma_channel_is_busy((uint)dma_ch))
        apply_pwm();                        /* the burst is already over: now */
    restore_interrupts(irq);

    STAGE(6);
    /* 6. the mirrors against the requests: overcurrent, open coil */
    static uint8_t over[PEND_COILS], open_[PEND_COILS];
    static uint32_t seen[PEND_COILS];
    for (int c = 0; c < PEND_COILS; c++) {
        if (fresh_mux_tick[c] == seen[c])
            continue;                       /* no new reading of this coil */
        seen[c] = fresh_mux_tick[c];
        if (!(drv == DRV_AWAKE && want[c] && cmd[c].steady_ticks > 20)) {
            over[c] = open_[c] = 0;
            continue;
        }
        float expect = fabsf(u[c]) * rt.v12 / (thermal_r_ohm(&rt_thermal[c]) + DRV_RDSON_OHM);
        float got = rt.i_meas[c];
        over[c] = (got > 0.4f && got > 1.5f * expect + 0.2f) ? over[c] + 1u : 0u;
        open_[c] = (expect > 0.25f && got < 0.05f) ? open_[c] + 1u : 0u;
        if (over[c] >= 3) {
            rt.faults |= RT_FAULT_OVERCURRENT;
            cancel_request(c);
        }
        if (open_[c] >= 25) {
            rt.faults |= RT_FAULT_OPEN_COIL;
            cancel_request(c);
        }
        /* the coil as its own thermometer: steady DC, enough current for V / I */
        if (cmd[c].steady_ticks > 50 && expect > THERMAL_MEAS_MIN_A && got > THERMAL_MEAS_MIN_A)
            thermal_measure_r(&rt_thermal[c], fabsf(u[c]) * rt.v12 / got - DRV_RDSON_OHM,
                              (float)MUX_CHANNELS / (float)CTRL_TICK_HZ);
    }

    /* 6b. the levitation coil as its own thermometer (since 2026-11-08: its model alone
     * stopped every hover after 2-3 minutes while the perch felt only warm, REVB.md 1.11).
     * The hover's current is never steady from tick to tick, so the reading is a ratio of
     * means over LEV_RMEAS_TICKS: mean(u V12) / mean(I), the mirror's current signed by
     * the drive's direction.  Means make the one or two ticks between a command and the
     * burst that measures it irrelevant, and the 0.5 us pulse loss cancels between the
     * forward pulse and the alternation's reverse pulse.  Only while the bridge drives the
     * coil the whole window, without the carrier, at THERMAL_MEAS_MIN_A or more, one way
     * at least 95 % of the ticks.  thermal_measure_r() calibrates its reference on the
     * first readings of a cold coil, which cancels the mirror's gain error. */
    {
        static float lv_uv, lv_i;
        static uint32_t lv_n, lv_fwd, lv_hold;
        /* from a second into a hold (the catch's current climbs from nothing).  Not
         * because a catch spoils V/I: the coil is 30 uH (0.3 mV for 0.5 A in a window,
         * against ~1.5 V), and the catch read the same 4.4-4.5 ohm as a steady drive with
         * no bat (bringup/REVB.md 1.11) */
        lv_hold = rt_lev.state == LEV_HOLD ? lv_hold + 1u : 0u;
        bool lv_steady = rt_lev.state == LEV_OFF || lv_hold >= CTRL_TICK_HZ;
        bool lv_ok = drv == DRV_AWAKE && want[COIL_LEV] && !carrier_now && rt.v12 > V12_PRESENT_V && lv_steady;
        if (!lv_ok) {
            lv_uv = lv_i = 0.0f;
            lv_n = lv_fwd = 0;
        } else {
            float uu = u[COIL_LEV];
            lv_uv += uu * rt.v12;
            lv_i += (uu >= 0.0f ? 1.0f : -1.0f) * rt.i_meas[COIL_LEV];
            lv_fwd += uu >= 0.0f ? 1u : 0u;
            if (++lv_n >= LEV_RMEAS_TICKS) {
                float mi = lv_i / (float)lv_n, muv = lv_uv / (float)lv_n;
                uint32_t one_way = lv_fwd > lv_n - lv_fwd ? lv_fwd : lv_n - lv_fwd;
                if (fabsf(mi) >= THERMAL_MEAS_MIN_A && one_way * 100u >= lv_n * 95u && muv * mi > 0.0f) {
                    rt.lev_r_meas_ohm = muv / mi - DRV_RDSON_OHM;
                    thermal_measure_r(&rt_thermal[COIL_LEV], rt.lev_r_meas_ohm,
                                      (float)LEV_RMEAS_TICKS / (float)CTRL_TICK_HZ);
                    rt.lev_r_readings++;
                }
                lv_uv = lv_i = 0.0f;
                lv_n = lv_fwd = 0;
            }
        }
    }

    STAGE(7);
    /* 7. the thermal models, at 1 kHz */
    static float i2[COIL_COUNT];
    static int th_n;
    for (int c = 0; c < COIL_COUNT; c++) {
        if (rt.u[c] == 0.0f && !(c == COIL_LEV && want[c]))
            continue;
        float model = fabsf(rt.u[c]) * rt.v12 / (thermal_r_ohm(&rt_thermal[c]) + DRV_RDSON_OHM);
        /* the larger of the drive's and the mirror's current, except under the eyes' carrier:
         * the mirror then reads the carrier's swing as current (a hover with the eyes on was
         * modelled at about 2.7 W and stopped, 2026-11-09), and `extra` below counts the
         * carrier itself */
        bool carrier_here = c == COIL_LEV && carrier_now;
        float i = carrier_here ? model : fmaxf(model, rt.i_meas[c]);
        float extra = 0.0f;
        if (carrier_here) {
            /* the carrier's triangular ripple: about V (m T) / L peak to peak, rms / (2 sqrt 3) */
            float ipp = rt.v12 * lev_alt / (coil_pwm_hz(COIL_LEV) * LEV_COIL_L_H);
            extra = ipp * ipp / 12.0f;
        }
        i2[c] += i * i + extra;
    }
    if (++th_n >= (int)(CTRL_TICK_HZ / 1000u)) {
        float dt = (float)th_n / (float)CTRL_TICK_HZ;
        for (int c = 0; c < COIL_COUNT; c++) {
            thermal_update(&rt_thermal[c], dt, i2[c] / (float)th_n, rt.ambient_C);
            i2[c] = 0.0f;
            rt.temp_C[c] = thermal_surface_C(&rt_thermal[c]);
            rt.r_ohm[c] = thermal_r_ohm(&rt_thermal[c]);
            if (derate_of(c) <= 0.0f)
                rt.faults |= RT_FAULT_THERMAL;
        }
        th_n = 0;
    }

    STAGE(8);
    rt.ticks++;
    uint32_t dt_us = time_us_32() - t_start;
    if (dt_us > rt.tick_cycles_max)
        rt.tick_cycles_max = dt_us;
    /* bursts overrunning or conversions failing: a rate over a second, not a count (a
     * few overruns are normal: a USB burst on core 0's side of the bus, a flash write) */
    if (now64 - win_at >= 1000000u) {
        uint32_t over = rt.overruns - win_over, err = rt.adc_errors - win_err;
        if (win_at != 0 &&
            (over > (uint32_t)(RT_ADC_FAULT_FRACTION * (float)CTRL_TICK_HZ) ||
             err > (uint32_t)(RT_ADC_FAULT_FRACTION * (float)(CTRL_TICK_HZ * BURST))))
            rt.faults |= RT_FAULT_ADC;
        rt.skipped_last_s = over;
        win_at = now64;
        win_over = rt.overruns;
        win_err = rt.adc_errors;
    }
}

/* ---- start ----------------------------------------------------------------------------- */
static void core1_main(void)
{
    flash_safe_execute_core_init();         /* settings writes pause us (only with every coil off) */

    adc_set_round_robin(ADC_RR_MASK);
    adc_select_input(ADC_RR_FIRST);
    adc_fifo_setup(true, true, 1, true, false);   /* FIFO, DREQ at 1, error bit, 12 bits */
    adc_set_clkdiv(0.0f);                   /* back to back: 2 us a conversion */

    dma_ch = dma_claim_unused_channel(true);
    dma_channel_config c = dma_channel_get_default_config((uint)dma_ch);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_16);
    channel_config_set_read_increment(&c, false);
    channel_config_set_write_increment(&c, true);
    channel_config_set_dreq(&c, DREQ_ADC);
    dma_channel_configure((uint)dma_ch, &c, burst[0], &adc_hw->fifo, BURST, false);
    dma_irqn_set_channel_enabled(1, (uint)dma_ch, true);
    irq_set_exclusive_handler(DMA_IRQ_1, adc_done_isr);
    irq_set_priority(DMA_IRQ_1, PICO_HIGHEST_IRQ_PRIORITY);   /* outranks the tick: it is short,
                                                                 and must stop the ADC on time */
    irq_set_enabled(DMA_IRQ_1, true);

    pwm_config pc = pwm_get_default_config();
    pwm_config_set_wrap(&pc, (uint16_t)TOP_TICK(TOP_LEV));
    pwm_init(PWM_SLICE_TICK, &pc, false);
    pwm_clear_irq(PWM_SLICE_TICK);
    pwm_irqn_set_slice_enabled(1, PWM_SLICE_TICK, true);
    irq_set_exclusive_handler(PWM_IRQ_WRAP_1, tick_isr);
    irq_set_priority(PWM_IRQ_WRAP_1, PICO_HIGHEST_IRQ_PRIORITY + 0x40u);
    irq_set_enabled(PWM_IRQ_WRAP_1, true);
    align_lev_and_tick();

    for (;;)
        __wfi();
}

void rt_start(bool cold_boot, const lev_cal_data *cal)
{
    memset(&rt, 0, sizeof rt);
    rt.ambient_C = AMBIENT_DEFAULT_C;
    thermal_params tp;
    thermal_default_params(&tp);
    for (int c = 0; c < COIL_COUNT; c++) {
        /* the levitation coil's own resistance (three layers, 2.56 ohm), not the pendulum
         * coils' 2.29: until the cold calibration measures it, u = i R / V12 would have
         * been 10 % short of the current asked for (review 2026-10-09) */
        tp.r20_ohm = (c == COIL_LEV) ? LEV_COIL_R20_OHM : COIL_R20_OHM;
        /* the levitation coil sits in the perch under the printed owl, out of a hand's
         * reach: its own limits, the copper's higher and the board's for the owl's PLA
         * (config.h, LEV_COIL_*_LIMIT_C) */
        tp.limit_C = (c == COIL_LEV) ? LEV_COIL_SURFACE_LIMIT_C : COIL_SURFACE_LIMIT_C;
        tp.derate_from_C = (c == COIL_LEV) ? LEV_COIL_DERATE_FROM_C : COIL_DERATE_FROM_C;
        tp.board_limit_C = (c == COIL_LEV) ? LEV_COIL_BOARD_LIMIT_C : COIL_SURFACE_LIMIT_C;
        tp.uncal_up_only = c != COIL_LEV;
        if (c == COIL_LEV) {                /* fitted on the bench (config.h) */
            tp.c_board_J_per_K = LEV_THERMAL_C_BOARD_J_PER_K;
            tp.r_cu_board_K_per_W = LEV_THERMAL_R_CU_BOARD_K_PER_W;
            tp.r_board_amb_K_per_W = LEV_THERMAL_R_BOARD_AMB_K_PER_W;
        }
        tp.board_derate_from_C = (c == COIL_LEV) ? LEV_COIL_BOARD_DERATE_C : COIL_DERATE_FROM_C;
        thermal_init(&rt_thermal[c], &tp, AMBIENT_DEFAULT_C);
        if (cold_boot)                      /* after a power-on, not after a watchdog reset */
            thermal_assume_cold(&rt_thermal[c]);
    }
    lev_init(&rt_lev);
    rt_lev.u_lag = 1;                       /* the u applies after the burst it overlapped (rt.h) */
    if (cal && (cal->coil_valid || cal->zero_valid))
        lev_set_cal(&rt_lev, cal);          /* before core 1 runs the loop */
    coils_init();
    multicore_launch_core1(core1_main);
}
