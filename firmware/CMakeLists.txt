# OWLternating Current firmware: Pico SDK 2.1.1 + TinyUSB, for the RP2354A.
#
#   ./fetch_sdk.sh                         once: the pinned Pico SDK into external/
#   cmake -S . -B build && cmake --build build -j8
#   picotool load -x build/owlternating.uf2 -f   (or copy the .uf2 to the RP2350 drive)
#
# make -C test: the host tests of the portable modules (the light show, the quantum
# ghost, the levitation loop against its plant, the pendulum, the familiars, the
# thermal model, film mode, the console, the theremin).  README.md says more.
cmake_minimum_required(VERSION 3.13)

set(PICO_SDK_PATH ${CMAKE_CURRENT_LIST_DIR}/external/pico-sdk CACHE PATH "the Pico SDK")
set(PICO_PLATFORM rp2350-arm-s)
set(PICO_BOARD owlternating)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(owlternating C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

add_executable(owlternating
    # core 0: start-up, the scheduler, the console, USB
    src/main.c
    src/usb_descriptors.c
    src/console.c
    src/settings.c
    # the board
    src/board.c
    src/i2c_bus.c
    src/lp5036.c
    src/sensors.c
    src/coils.c
    src/audio.c
    src/theremin_hw.c
    # core 1: the 10 kHz tick (ADC, levitation, safety, coil drive)
    src/rt.c
    # portable modules (host-tested in test/)
    src/led_engine.c
    src/scenes.c
    src/noise.c
    src/quantum.c
    src/lev_ctrl.c
    src/thermal.c
    src/pendulum.c
    src/familiar.c
    src/film.c
    src/theremin.c
    src/voice.c
    # Raspberry Pi's reset interface (picotool reboot), without the rest of stdio_usb
    ${PICO_SDK_PATH}/src/rp2_common/pico_stdio_usb/reset_interface.c
)
pico_generate_pio_header(owlternating ${CMAKE_CURRENT_LIST_DIR}/src/edge_count.pio)
target_include_directories(owlternating PRIVATE src ${PICO_SDK_PATH}/src/rp2_common/pico_stdio_usb/include)
target_compile_definitions(owlternating PRIVATE
    PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_BOOTSEL=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_FLASH_BOOT=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_MS_OS_20_DESCRIPTOR=0
    PICO_STDIO_USB_RESET_BOOTSEL_INTERFACE_DISABLE_MASK=0
    PICO_STDIO_USB_RESET_RESET_TO_FLASH_DELAY_MS=100
    PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE=0
    PICO_STDIO_UART_SUPPORT_CHARS_AVAILABLE_CALLBACK=0
    PICO_STACK_SIZE=0x1000          # core 0: 4 kB (SCRATCH_Y)
    PICO_CORE1_STACK_SIZE=0x1000    # core 1: 4 kB (SCRATCH_X), its 10 kHz interrupts run on it
)
if(OWL_DIAG)                                   # cmake -DOWL_DIAG=1: the boot-diagnostic image (main.c)
    target_compile_definitions(owlternating PRIVATE OWL_DIAG=1)
endif()
target_compile_options(owlternating PRIVATE -Wall -Wextra -Wno-unused-parameter -Wdouble-promotion)
target_link_libraries(owlternating
    pico_stdlib
    pico_unique_id
    pico_usb_reset_interface
    pico_flash
    pico_multicore
    hardware_adc
    hardware_dma
    hardware_flash
    hardware_i2c
    hardware_pio
    hardware_pwm
    hardware_watchdog
    tinyusb_device
    tinyusb_board
)
pico_enable_stdio_uart(owlternating 1)
pico_enable_stdio_usb(owlternating 0)
pico_add_extra_outputs(owlternating)

# ---- owl_bringup: the bring-up image (src/bringup_main.c, src/bringup_cmd.c) -------------
# For the first power-up of an untested board: the console, the ADC, I2C, single LEDs,
# bounded coil and perch pulses, a test tone, the theremin's counters.  No watchdog, no
# core 1, no DMA, nothing automatic.  The same USB IDs and reset interface as the main
# image, named "OWL bring-up".
add_executable(owl_bringup
    src/bringup_main.c
    src/bringup_cmd.c
    src/usb_descriptors.c
    src/board.c
    src/i2c_bus.c
    src/coils.c
    ${PICO_SDK_PATH}/src/rp2_common/pico_stdio_usb/reset_interface.c
)
pico_generate_pio_header(owl_bringup ${CMAKE_CURRENT_LIST_DIR}/src/edge_count.pio)
target_include_directories(owl_bringup PRIVATE src ${PICO_SDK_PATH}/src/rp2_common/pico_stdio_usb/include)
target_compile_definitions(owl_bringup PRIVATE
    PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_BOOTSEL=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_FLASH_BOOT=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_MS_OS_20_DESCRIPTOR=0
    PICO_STDIO_USB_RESET_BOOTSEL_INTERFACE_DISABLE_MASK=0
    PICO_STDIO_USB_RESET_RESET_TO_FLASH_DELAY_MS=100
    PICO_STDIO_USB_ENABLE_RESET_VIA_BAUD_RATE=0
    PICO_STDIO_UART_SUPPORT_CHARS_AVAILABLE_CALLBACK=0
    PERCH_F_CLAMP_MAX_HZ=500000.0f
    OWL_USB_PRODUCT="OWL bring-up"
    OWL_USB_CONSOLE="OWL bring-up console"
)
target_compile_options(owl_bringup PRIVATE -Wall -Wextra -Wno-unused-parameter -Wdouble-promotion)
target_link_libraries(owl_bringup
    pico_stdlib
    pico_unique_id
    pico_usb_reset_interface
    hardware_adc
    hardware_i2c
    hardware_pio
    hardware_pwm
    hardware_watchdog
    tinyusb_device
    tinyusb_board
)
pico_enable_stdio_uart(owl_bringup 1)
pico_enable_stdio_usb(owl_bringup 0)
pico_add_extra_outputs(owl_bringup)
