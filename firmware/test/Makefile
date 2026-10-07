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
CC ?= cc
CFLAGS = -std=c11 -O1 -g -Wall -Wextra -Wno-unused-parameter -I../src -I. \
         -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer
LDLIBS = -lm
HEADERS = $(wildcard ../src/*.h) $(wildcard *.h)

TESTS = test_leds test_quantum test_lev test_pendulum test_familiar test_thermal test_film \
        test_console test_theremin

SRC_test_leds     = ../src/led_engine.c ../src/scenes.c ../src/noise.c ../src/quantum.c
SRC_test_quantum  = ../src/quantum.c
SRC_test_lev      = ../src/lev_ctrl.c
SRC_test_pendulum = ../src/pendulum.c
SRC_test_familiar = ../src/familiar.c
SRC_test_thermal  = ../src/thermal.c
SRC_test_film     = ../src/film.c ../src/thermal.c
SRC_test_console  = ../src/console.c ../src/led_engine.c ../src/scenes.c ../src/noise.c ../src/quantum.c
SRC_test_theremin = ../src/theremin.c ../src/voice.c

all: $(TESTS:%=run_%)

.SECONDEXPANSION:
$(TESTS): %: %.c $$(SRC_%) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ $< $(SRC_$@) $(LDLIBS)

run_%: %
	./$<

clean:
	rm -f $(TESTS)
	rm -rf out
.PHONY: all clean
