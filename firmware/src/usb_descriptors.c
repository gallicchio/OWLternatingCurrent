/* usb_descriptors.c: what OWLternating Current says it is on USB.
 *
 *   interfaces 0-1  CDC "OWLternating console"   the JSON console (console.h)
 *   interface 2     Raspberry Pi's reset interface: `picotool reboot -u -f` reaches
 *                   BOOTSEL with nobody touching the board
 *
 * As GPiBridge's (its usb_descriptors.c): Windows binds usbser to the serial port and
 * WinUSB to the reset interface through the Microsoft OS 2.0 descriptors, so
 * picotool works there with nothing installed; that needs bcdUSB 2.1.
 *
 * VID:PID 1209:0001 is pid.codes' test PID, for development only; a public release
 * needs a PID of its own.  Serial number: the flash's unique ID.
 */
#include "tusb.h"
#include "pico/unique_id.h"
#include "pico/usb_reset_interface.h"
#include "usb_descriptors.h"

#define VID 0x1209
#define PID 0x0001

enum { STR_LANG = 0, STR_MANUFACTURER, STR_PRODUCT, STR_SERIAL, STR_CONSOLE, STR_RESET };

#define EP_CONSOLE_NOTIF 0x81
#define EP_CONSOLE_OUT   0x02
#define EP_CONSOLE_IN    0x82
#define TUD_RPI_RESET_DESC_LEN 9
#define MAX_POWER_MA 500            /* on USB alone the LEDs are dimmed and the coils off */

static const tusb_desc_device_t device = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0210,                    /* 2.1: Windows then reads the BOS descriptor */
    .bDeviceClass = TUSB_CLASS_MISC,     /* composite with interface associations */
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = VID,
    .idProduct = PID,
    .bcdDevice = 0x0010,
    .iManufacturer = STR_MANUFACTURER,
    .iProduct = STR_PRODUCT,
    .iSerialNumber = STR_SERIAL,
    .bNumConfigurations = 1,
};

static const uint8_t config[] = {
    TUD_CONFIG_DESCRIPTOR(1, 3, 0, TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN + TUD_RPI_RESET_DESC_LEN, 0,
                          MAX_POWER_MA),
    TUD_CDC_DESCRIPTOR(0, STR_CONSOLE, EP_CONSOLE_NOTIF, 8, EP_CONSOLE_OUT, EP_CONSOLE_IN, 64),
    TUD_RPI_RESET_DESC_LEN, TUSB_DESC_INTERFACE, 2, 0, 0, TUSB_CLASS_VENDOR_SPECIFIC,
    RESET_INTERFACE_SUBCLASS, RESET_INTERFACE_PROTOCOL, STR_RESET,
};

const uint8_t *tud_descriptor_device_cb(void) { return (const uint8_t *)&device; }

const uint8_t *tud_descriptor_configuration_cb(uint8_t index)
{
    (void)index;
    return config;
}

/* ---- Microsoft OS 2.0: WinUSB for the reset interface ----------------------- */
#define MS_OS_20_VENDOR_CODE 1
#define MS_OS_20_DESC_LEN 166
#define BOS_TOTAL_LEN (TUD_BOS_DESC_LEN + TUD_BOS_MICROSOFT_OS_DESC_LEN)

static const uint8_t bos[] = {
    TUD_BOS_DESCRIPTOR(BOS_TOTAL_LEN, 1),
    TUD_BOS_MS_OS_20_DESCRIPTOR(MS_OS_20_DESC_LEN, MS_OS_20_VENDOR_CODE),
};

const uint8_t *tud_descriptor_bos_cb(void) { return bos; }

/* As the Pico SDK's own (pico_stdio_usb/reset_interface.c), for interface 2. */
static const uint8_t ms_os_20[MS_OS_20_DESC_LEN] = {
    U16_TO_U8S_LE(0x000A), U16_TO_U8S_LE(MS_OS_20_SET_HEADER_DESCRIPTOR), U32_TO_U8S_LE(0x06030000),
    U16_TO_U8S_LE(MS_OS_20_DESC_LEN),
    /* function subset header for the reset interface (2) */
    U16_TO_U8S_LE(0x0008), U16_TO_U8S_LE(MS_OS_20_SUBSET_HEADER_FUNCTION), 2, 0, U16_TO_U8S_LE(0x009C),
    U16_TO_U8S_LE(0x0014), U16_TO_U8S_LE(MS_OS_20_FEATURE_COMPATBLE_ID), 'W', 'I', 'N', 'U', 'S', 'B', 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    U16_TO_U8S_LE(0x0080), U16_TO_U8S_LE(MS_OS_20_FEATURE_REG_PROPERTY), U16_TO_U8S_LE(0x0001),
    U16_TO_U8S_LE(0x0028),
    'D', 0, 'e', 0, 'v', 0, 'i', 0, 'c', 0, 'e', 0, 'I', 0, 'n', 0, 't', 0, 'e', 0,
    'r', 0, 'f', 0, 'a', 0, 'c', 0, 'e', 0, 'G', 0, 'U', 0, 'I', 0, 'D', 0, 0, 0,
    U16_TO_U8S_LE(0x004E),
    '{', 0, 'b', 0, 'c', 0, '7', 0, '3', 0, '9', 0, '8', 0, 'c', 0, '1', 0, '-', 0,
    '7', 0, '3', 0, 'c', 0, 'd', 0, '-', 0, '4', 0, 'c', 0, 'b', 0, '7', 0, '-', 0,
    '9', 0, '8', 0, 'b', 0, '8', 0, '-', 0, '9', 0, '1', 0, '3', 0, 'a', 0, '8', 0,
    'f', 0, 'c', 0, 'a', 0, '7', 0, 'b', 0, 'f', 0, '6', 0, '}', 0, 0, 0,
};
TU_VERIFY_STATIC(sizeof(ms_os_20) == MS_OS_20_DESC_LEN, "MS OS 2.0 descriptor size");

bool tud_vendor_control_xfer_cb(uint8_t rhport, uint8_t stage, tusb_control_request_t const *request)
{
    if (stage != CONTROL_STAGE_SETUP)
        return true;
    if (request->bRequest == MS_OS_20_VENDOR_CODE && request->wIndex == 7)
        return tud_control_xfer(rhport, request, (void *)(uintptr_t)ms_os_20, sizeof ms_os_20);
    return false;
}

/* ---- strings -------------------------------------------------------------------- */
static const char *strings[] = {
    [STR_MANUFACTURER] = "OWLternating Current (open hardware)",
    [STR_PRODUCT] = "OWLternating Current",
    [STR_CONSOLE] = "OWLternating console",
    [STR_RESET] = "Reset",
};

const uint16_t *tud_descriptor_string_cb(uint8_t index, uint16_t langid)
{
    (void)langid;
    static uint16_t desc[40];
    char serial[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
    const char *s;
    if (index == STR_LANG) {
        desc[1] = 0x0409;
        desc[0] = (uint16_t)((TUSB_DESC_STRING << 8) | 4);
        return desc;
    }
    if (index == STR_SERIAL) {
        pico_get_unique_board_id_string(serial, sizeof serial);
        s = serial;
    } else if (index < sizeof strings / sizeof strings[0] && strings[index]) {
        s = strings[index];
    } else {
        return NULL;
    }
    size_t n = 0;
    while (s[n] && n < 39) {
        desc[1 + n] = (uint8_t)s[n];
        n++;
    }
    desc[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * n + 2));
    return desc;
}
