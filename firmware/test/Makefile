# The firmware's portable modules on the host: `make` builds and runs every test
# (`make run_test_lev` runs one).  No hardware and no Pico SDK: the modules under
# test include only config.h and their own headers.  AddressSanitizer and UBSan
# are on, so an out-of-bounds write or an overflow fails the test.
#
#   test_leds      the LED engine on every scene: no LED steps faster than a 0-to-full
#                  fade of 300 ms, L* curve, dithering, the LP5036 bank split
#   test_quantum   the quantum ghost: Crank-Nicolson keeps the norm, the packet tunnels
#   test_lev       the levitation controller against the plant from sim/physics:
#                  catch range, zero-power current, loss detection
#   test_pendulum  the pendulum estimator and drive against a simulated pendulum
#   test_familiar  the perch sweep finds and names a familiar on a simulated perch
#   test_thermal   the coil thermal model and its derating
#   test_film      film mode keeps every coil under its limits
#   test_console   the JSON console's commands and their limits
#   test_theremin  the theremin's mapping and the "woo" voice
#   test_rt        core 1 (rt.c, coils.c, board.c) with the SDK modelled: the safe pin
#                  state, the PWM's meaning, no coil without 12 V, deadlines, limits,
#                  brown-out, nFAULT, shorted and open coils, the thermal limit, and the
#                  levitation CAL through the glue
CC ?= cc
CFLAGS = -std=c11 -O1 -g -Wall -Wextra -Wno-unused-parameter -I../src -I. \
         -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer
LDLIBS = -lm
HEADERS = $(wildcard ../src/*.h) $(wildcard *.h)

TESTS = test_leds test_quantum test_lev test_pendulum test_familiar test_thermal test_film \
        test_console test_theremin test_rt

SRC_test_leds     = ../src/led_engine.c ../src/scenes.c ../src/noise.c ../src/quantum.c
SRC_test_quantum  = ../src/quantum.c
SRC_test_lev      = ../src/lev_ctrl.c
SRC_test_pendulum = ../src/pendulum.c
SRC_test_familiar = ../src/familiar.c
SRC_test_thermal  = ../src/thermal.c
SRC_test_film     = ../src/film.c ../src/thermal.c
SRC_test_console  = ../src/console.c ../src/led_engine.c ../src/scenes.c ../src/noise.c ../src/quantum.c
SRC_test_theremin = ../src/theremin.c ../src/voice.c
SRC_test_rt       = ../src/rt.c ../src/coils.c ../src/board.c ../src/lev_ctrl.c ../src/thermal.c stubs/sdk_stub.c

all: $(TESTS:%=run_%)

.SECONDEXPANSION:
$(TESTS): %: %.c $$(SRC_%) $(HEADERS)
	$(CC) $(CFLAGS) $(CFLAGS_$@) -o $@ $< $(SRC_$@) $(LDLIBS)

# core 1's code with the SDK modelled (stubs/): the stubs come first on the include path
CFLAGS_test_rt = -Istubs

run_%: %
	./$<

clean:
	rm -f $(TESTS)
	rm -rf out
.PHONY: all clean
