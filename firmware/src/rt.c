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

rt_shared rt;
lev_ctrl rt_lev;
thermal_coil rt_thermal[COIL_COUNT];

#define BURST ((int)(3 * ADC_OVERSAMPLE))   /* the three ADC lines (ADC_SLOT_*), ADC_OVERSAMPLE times */
static uint16_t burst[BURST];
static int dma_ch;
static unsigned mux_ch;                     /* the channel this burst's ADC2 samples carry */

/* ---- requests from core 0 ---------------------------------------------------------- */
typedef struct {
    volatile uint32_t seq;                  /* odd while core 0 writes */
    volatile float amps;
    volatile uint32_t until_us;
    volatile uint8_t owner;
} coil_req;
static coil_req req[COIL_COUNT];

typedef struct {
    float amps;
    uint32_t until_us;
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
    r->until_us = time_us_32() + ms * 1000u;
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
            r->until_us = time_us_32();
            __dmb();
            r->seq++;
        }
}

int rt_coil_owner(int coil)
{
    if (coil < 0 || coil >= COIL_COUNT)
        return RT_OWNER_NONE;
    uint32_t now = time_us_32();
    return (int32_t)(req[coil].until_us - now) > 0 ? req[coil].owner : RT_OWNER_NONE;
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

static void tick_isr(void)
{
    pwm_clear_irq(PWM_SLICE_TICK);
    if (dma_channel_is_busy((uint)dma_ch)) {
        rt.overruns++;
        return;
    }
    if (resync == 1) {
        align_lev_and_tick();
        resync = 0;
    } else {
        bool want = rt.lev_eyes > 0.0f && rt_lev.state == LEV_HOLD;
        if (want != carrier_now) {
            coil_lev_frequency(want);       /* both TOPs latch at their next wraps */
            pwm_set_wrap(PWM_SLICE_TICK, (uint16_t)TOP_TICK(coil_top(COIL_LEV)));
            carrier_now = want;
            rt.carrier_on = want;
            resync = 1;
        }
    }
    adc_fifo_drain();                       /* waits for the last conversion, drops strays */
    adc_select_input(ADC_RR_FIRST);
    dma_channel_transfer_to_buffer_now((uint)dma_ch, burst, BURST);
    adc_run(true);
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

static void control(void)
{
    uint32_t t_start = time_us_32();
    uint32_t now = t_start;

    /* 1. the burst's averages; ADC2 is this tick's multiplexer channel */
    uint32_t sum[3] = {0, 0, 0}, n[3] = {0, 0, 0};
    for (int i = 0; i < BURST; i++) {
        uint16_t v = burst[i];
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
    mux_sample(mux_ch, adc_volts(avg[ADC_SLOT_MUX_OUT]));
    mux_ch = (mux_ch + 1u) % MUX_CHANNELS;
    board_mux_select(mux_ch);
    rt.hall_mT = (float)HALL_POLARITY * (adc_volts(avg[ADC_SLOT_HALL]) - HALL_VQ_FRACTION * ADC_VREF_V) /
                 (HALL_MV_PER_MT * 1e-3f);
    rt.i_meas[COIL_LEV] = adc_volts(avg[ADC_SLOT_LEV_IPROPI]) / IPROPI_V_PER_A;

    /* 2. faults and power */
    static uint32_t last_clear, v12_good, nf_ticks, nf_retry_at, nf_window_at;
    static int nf_count;
    if (rt.clear_req != last_clear) {
        last_clear = rt.clear_req;
        rt.faults = 0;
        nf_count = 0;
        nf_retry_at = now;
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
            if (now - nf_window_at > 60000000u) {
                nf_window_at = now;
                nf_count = 0;
            }
            if (++nf_count >= 3)
                rt.faults |= RT_FAULT_LATCHED_OFF;
            nf_retry_at = now + 100000u;  /* asleep for 100 ms clears the DRV8874's latch */
            nf_ticks = 0;
        }
    } else {
        nf_ticks = 0;
    }
    bool allowed = rt.power_ok && !(rt.faults & RT_FAULT_LATCHED_OFF) && (int32_t)(now - nf_retry_at) >= 0;

    /* 3. what each coil should do */
    float u[COIL_COUNT] = {0.0f, 0.0f, 0.0f, 0.0f};
    bool want[COIL_COUNT] = {false, false, false, false};
    for (int c = 0; c < COIL_COUNT; c++) {
        take_request(c);
        cmd[c].steady_ticks++;
    }
    for (int c = 0; c < PEND_COILS; c++) {
        coil_cmd *k = &cmd[c];
        if (k->owner == RT_OWNER_NONE || (int32_t)(k->until_us - now) <= 0)
            continue;
        float lim = owner_limit(k->owner) * thermal_derate(&rt_thermal[c]);
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
        .thermal_trip = thermal_derate(&rt_thermal[COIL_LEV]) <= 0.0f,
    };
    lev_output lo;
    lev_step(&rt_lev, &li, &lo);
    bool lev_wants = rt_lev.state != LEV_OFF && rt_lev.state != LEV_FAULT;
    if (lo.active) {
        u[COIL_LEV] = lo.u;
        want[COIL_LEV] = true;
    } else if (rt_lev.state == LEV_OFF) {   /* the console may test the coil while the loop is off */
        coil_cmd *k = &cmd[COIL_LEV];
        if (k->owner == RT_OWNER_CONSOLE && (int32_t)(k->until_us - now) > 0 && rt.v12 > 1.0f) {
            float lim = CONSOLE_I_MAX_A * thermal_derate(&rt_thermal[COIL_LEV]);
            float a = clampf_(k->amps, -lim, lim);
            u[COIL_LEV] = a * (thermal_r_ohm(&rt_thermal[COIL_LEV]) + DRV_RDSON_OHM) / rt.v12;
            want[COIL_LEV] = a != 0.0f;
        }
    }

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

    /* 5. the PWM.  The levitation coil always switches both ways a little (every output
     * pulse at least DRV_MIN_PULSE_S: the mean stays linear down to zero); with the
     * carrier, a lot, but never so much that the loop's mean voltage cannot be made:
     * the carrier yields to the control for as long as the control needs it. */
    float lev_alt = DRV_MIN_PULSE_S * coil_pwm_hz(COIL_LEV);
    if (carrier_now) {
        float room = 0.5f * (1.0f - fabsf(u[COIL_LEV])) - 0.02f;
        lev_alt = fmaxf(lev_alt, fminf(0.5f * clampf_(rt.lev_eyes, 0.0f, LEV_EYES_MAX), room));
    }
    for (int c = 0; c < COIL_COUNT; c++) {
        bool on = drv == DRV_AWAKE && want[c];
        if (drv == DRV_AWAKE) {
            if (on)
                coil_set_u(c, u[c], c == COIL_LEV ? lev_alt : 0.0f);
            else
                coil_coast(c);
        }
        rt.u[c] = on ? u[c] : 0.0f;
    }

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

    /* 7. the thermal models, at 1 kHz */
    static float i2[COIL_COUNT];
    static int th_n;
    for (int c = 0; c < COIL_COUNT; c++) {
        if (rt.u[c] == 0.0f && !(c == COIL_LEV && want[c]))
            continue;
        float model = fabsf(rt.u[c]) * rt.v12 / (thermal_r_ohm(&rt_thermal[c]) + DRV_RDSON_OHM);
        float i = fmaxf(model, rt.i_meas[c]);
        float extra = 0.0f;
        if (c == COIL_LEV && carrier_now) {
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
            if (thermal_derate(&rt_thermal[c]) <= 0.0f)
                rt.faults |= RT_FAULT_THERMAL;
        }
        th_n = 0;
    }

    rt.ticks++;
    uint32_t dt_us = time_us_32() - t_start;
    if (dt_us > rt.tick_cycles_max)
        rt.tick_cycles_max = dt_us;
    if (rt.overruns > 10u)
        rt.faults |= RT_FAULT_ADC;
}

static void adc_done_isr(void)
{
    dma_irqn_acknowledge_channel(1, (uint)dma_ch);
    adc_run(false);
    control();
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
    dma_channel_configure((uint)dma_ch, &c, burst, &adc_hw->fifo, BURST, false);
    dma_irqn_set_channel_enabled(1, (uint)dma_ch, true);
    irq_set_exclusive_handler(DMA_IRQ_1, adc_done_isr);
    irq_set_priority(DMA_IRQ_1, PICO_HIGHEST_IRQ_PRIORITY);
    irq_set_enabled(DMA_IRQ_1, true);

    pwm_config pc = pwm_get_default_config();
    pwm_config_set_wrap(&pc, (uint16_t)TOP_TICK(TOP_LEV));
    pwm_init(PWM_SLICE_TICK, &pc, false);
    pwm_clear_irq(PWM_SLICE_TICK);
    pwm_irqn_set_slice_enabled(1, PWM_SLICE_TICK, true);
    irq_set_exclusive_handler(PWM_IRQ_WRAP_1, tick_isr);
    irq_set_priority(PWM_IRQ_WRAP_1, PICO_HIGHEST_IRQ_PRIORITY);
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
        thermal_init(&rt_thermal[c], &tp, AMBIENT_DEFAULT_C);
        if (cold_boot)                      /* after a power-on, not after a watchdog reset */
            thermal_assume_cold(&rt_thermal[c]);
    }
    lev_init(&rt_lev);
    if (cal && (cal->coil_valid || cal->zero_valid))
        lev_set_cal(&rt_lev, cal);          /* before core 1 runs the loop */
    coils_init();
    multicore_launch_core1(core1_main);
}
