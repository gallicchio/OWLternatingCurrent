/* owlternating.h: the Pico SDK's board description of OWLternating Current rev A.
 * RP2354A: the RP2350A die (QFN-60) with 2 MB of flash in the package, as on
 * GPiBridge (whose boards/gpibridge.h this follows). */
#ifndef _BOARDS_OWLTERNATING_H
#define _BOARDS_OWLTERNATING_H

#define OWLTERNATING_REV_A
#define PICO_RP2350A 1                       /* the QFN-60 package: GPIO 0-29 */

/* UART0 on GPIO12/13: the debug connector J5 (gen/pins.py) */
#define PICO_DEFAULT_UART 0
#define PICO_DEFAULT_UART_TX_PIN 12
#define PICO_DEFAULT_UART_RX_PIN 13

/* I2C0 on GPIO16/17: the LED drivers and the sensors */
#define PICO_DEFAULT_I2C 0
#define PICO_DEFAULT_I2C_SDA_PIN 16
#define PICO_DEFAULT_I2C_SCL_PIN 17

/* no LED of its own: every LED is on the LP5036s */

/* 12 MHz crystal (ABM8-272-T3, as on Raspberry Pi's boards): the SDK's default XOSC */
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64

/* the flash stacked in the package */
#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1
#define PICO_FLASH_SPI_CLKDIV 2
#define PICO_FLASH_SIZE_BYTES (2 * 1024 * 1024)

#define PICO_RP2350_A2_SUPPORTED 1
#endif
