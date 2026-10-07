/* led_map.h: every LED on OWLternating Current rev A: driver, channel, name, colour, board, position.
 * WRITTEN BY gen/firmware_leds.py FROM gen/leds.py (and the placement's
 * hardware/checks/led_positions.json, when it exists): edit those, not this. */
#pragma once
#include <stdint.h>

enum { LED_DRV_BASE = 0, LED_DRV_TREE = 1, LED_DRIVERS = 2 };
#define LED_DRIVER_CHANNELS 36   /* LP5036: 12 banks of 3 */
#define LED_DRIVER_BANKS    12
static const uint8_t LED_DRIVER_ADDR[LED_DRIVERS] = {0x30, 0x31};

/* colours (gen/leds.py's docstring has the parts) */
enum { LED_COL_ORANGE = 0, LED_COL_AMBER5050 = 1, LED_COL_VIOLET = 2, LED_COL_PURPLE = 3, LED_COLOURS };
enum { LED_BOARD_BASE = 0, LED_BOARD_TREE = 1, LED_BOARD_PERCH = 2 };

typedef struct {
    uint8_t driver;      /* LED_DRV_* */
    uint8_t channel;     /* OUTn, 0-35; its bank is channel / 3 */
    const char *name;
    uint8_t colour;      /* LED_COL_* */
    float x_mm, y_mm;    /* on its board (KiCad coordinates); 0, 0 until placed */
    uint8_t board;       /* LED_BOARD_* */
} led_info;

#define LED_COUNT 49
#define LED_UNPLACED 49   /* positions no hardware/checks/led_positions.json yet; TODO: x/y = 0 until the placement writes them */

enum {
    LED_STAR0 = 0,
    LED_STAR1 = 1,
    LED_STAR2 = 2,
    LED_STAR3 = 3,
    LED_STAR4 = 4,
    LED_STAR5 = 5,
    LED_STAR6 = 6,
    LED_STAR7 = 7,
    LED_STAR8 = 8,
    LED_STAR9 = 9,
    LED_STAR10 = 10,
    LED_STAR11 = 11,
    LED_PUMPKIN0 = 12,
    LED_PUMPKIN1 = 13,
    LED_PUMPKIN2 = 14,
    LED_OWLRING0 = 15,
    LED_OWLRING1 = 16,
    LED_OWLRING2 = 17,
    LED_CATRING0 = 18,
    LED_CATRING1 = 19,
    LED_CATRING2 = 20,
    LED_WISP0 = 21,
    LED_WISP1 = 22,
    LED_WISP2 = 23,
    LED_WISP3 = 24,
    LED_WISP4 = 25,
    LED_WISP5 = 26,
    LED_STARX0 = 27,
    LED_STARX1 = 28,
    LED_STARX2 = 29,
    LED_STARX3 = 30,
    LED_OWLA_L = 31,
    LED_OWLA_R = 32,
    LED_OWLB_L = 33,
    LED_OWLB_R = 34,
    LED_OWLC_L = 35,
    LED_OWLC_R = 36,
    LED_TSTAR0 = 37,
    LED_TSTAR1 = 38,
    LED_TSTAR2 = 39,
    LED_TSTAR3 = 40,
    LED_TSTAR4 = 41,
    LED_TSTAR5 = 42,
    LED_PERCH_DOWN0 = 43,
    LED_PERCH_DOWN1 = 44,
    LED_TWISP0 = 45,
    LED_TWISP1 = 46,
    LED_TWISP2 = 47,
    LED_TWISP3 = 48,
};

static const led_info LED_MAP[LED_COUNT] = {
    {LED_DRV_BASE,  0, "STAR0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 0 of 12, left to right */
    {LED_DRV_BASE,  1, "STAR1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 1 of 12, left to right */
    {LED_DRV_BASE,  2, "STAR2", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 2 of 12, left to right */
    {LED_DRV_BASE,  3, "STAR3", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 3 of 12, left to right */
    {LED_DRV_BASE,  4, "STAR4", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 4 of 12, left to right */
    {LED_DRV_BASE,  5, "STAR5", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 5 of 12, left to right */
    {LED_DRV_BASE,  6, "STAR6", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 6 of 12, left to right */
    {LED_DRV_BASE,  7, "STAR7", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 7 of 12, left to right */
    {LED_DRV_BASE,  8, "STAR8", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 8 of 12, left to right */
    {LED_DRV_BASE,  9, "STAR9", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 9 of 12, left to right */
    {LED_DRV_BASE, 10, "STAR10", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 10 of 12, left to right */
    {LED_DRV_BASE, 11, "STAR11", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 11 of 12, left to right */
    {LED_DRV_BASE, 12, "PUMPKIN0", LED_COL_AMBER5050, 0.00f, 0.00f, LED_BOARD_BASE},   /* pumpkin 0's face, left to right */
    {LED_DRV_BASE, 13, "PUMPKIN1", LED_COL_AMBER5050, 0.00f, 0.00f, LED_BOARD_BASE},   /* pumpkin 1's face, left to right */
    {LED_DRV_BASE, 14, "PUMPKIN2", LED_COL_AMBER5050, 0.00f, 0.00f, LED_BOARD_BASE},   /* pumpkin 2's face, left to right */
    {LED_DRV_BASE, 15, "OWLRING0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the owl's perch, at 0 degrees */
    {LED_DRV_BASE, 16, "OWLRING1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the owl's perch, at 120 degrees */
    {LED_DRV_BASE, 17, "OWLRING2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the owl's perch, at 240 degrees */
    {LED_DRV_BASE, 18, "CATRING0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the cat's perch, at 0 degrees */
    {LED_DRV_BASE, 19, "CATRING1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the cat's perch, at 120 degrees */
    {LED_DRV_BASE, 20, "CATRING2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the cat's perch, at 240 degrees */
    {LED_DRV_BASE, 21, "WISP0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 0 of 6 */
    {LED_DRV_BASE, 22, "WISP1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 1 of 6 */
    {LED_DRV_BASE, 23, "WISP2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 2 of 6 */
    {LED_DRV_BASE, 24, "WISP3", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 3 of 6 */
    {LED_DRV_BASE, 25, "WISP4", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 4 of 6 */
    {LED_DRV_BASE, 26, "WISP5", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 5 of 6 */
    {LED_DRV_BASE, 27, "STARX0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 0 */
    {LED_DRV_BASE, 28, "STARX1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 1 */
    {LED_DRV_BASE, 29, "STARX2", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 2 */
    {LED_DRV_BASE, 30, "STARX3", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 3 */
    {LED_DRV_TREE,  0, "OWLA_L", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl A, left eye */
    {LED_DRV_TREE,  1, "OWLA_R", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl A, right eye */
    {LED_DRV_TREE,  3, "OWLB_L", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl B, left eye */
    {LED_DRV_TREE,  4, "OWLB_R", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl B, right eye */
    {LED_DRV_TREE,  6, "OWLC_L", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl C, left eye */
    {LED_DRV_TREE,  7, "OWLC_R", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl C, right eye */
    {LED_DRV_TREE,  9, "TSTAR0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 0 */
    {LED_DRV_TREE, 10, "TSTAR1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 1 */
    {LED_DRV_TREE, 11, "TSTAR2", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 2 */
    {LED_DRV_TREE, 12, "TSTAR3", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 3 */
    {LED_DRV_TREE, 13, "TSTAR4", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 4 */
    {LED_DRV_TREE, 14, "TSTAR5", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 5 */
    {LED_DRV_TREE, 15, "PERCH_DOWN0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_PERCH},   /* perch underside, left of the coil */
    {LED_DRV_TREE, 16, "PERCH_DOWN1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_PERCH},   /* perch underside, right of the coil */
    {LED_DRV_TREE, 18, "TWISP0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 0 */
    {LED_DRV_TREE, 19, "TWISP1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 1 */
    {LED_DRV_TREE, 20, "TWISP2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 2 */
    {LED_DRV_TREE, 21, "TWISP3", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 3 */
};

/* each driver's outputs: the LED on OUTn, or -1 */
static const int8_t LED_OF_CHANNEL[LED_DRIVERS][LED_DRIVER_CHANNELS] = {
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, -1, -1, -1, -1, -1},   /* BASE */
    {31, 32, -1, 33, 34, -1, 35, 36, -1, 37, 38, 39, 40, 41, 42, 43, 44, -1, 45, 46, 47, 48, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1},   /* TREE */
};

/* named groups, in order (the scenes walk these) */
#define LED_N_STAR         12
static const uint8_t LED_GROUP_STAR[LED_N_STAR] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};
#define LED_N_PUMPKIN      3
static const uint8_t LED_GROUP_PUMPKIN[LED_N_PUMPKIN] = {12, 13, 14};
#define LED_N_OWLRING      3
static const uint8_t LED_GROUP_OWLRING[LED_N_OWLRING] = {15, 16, 17};
#define LED_N_CATRING      3
static const uint8_t LED_GROUP_CATRING[LED_N_CATRING] = {18, 19, 20};
#define LED_N_WISP         6
static const uint8_t LED_GROUP_WISP[LED_N_WISP] = {21, 22, 23, 24, 25, 26};
#define LED_N_STARX        4
static const uint8_t LED_GROUP_STARX[LED_N_STARX] = {27, 28, 29, 30};
#define LED_N_OWLEYE       6
static const uint8_t LED_GROUP_OWLEYE[LED_N_OWLEYE] = {31, 32, 33, 34, 35, 36};
#define LED_N_TSTAR        6
static const uint8_t LED_GROUP_TSTAR[LED_N_TSTAR] = {37, 38, 39, 40, 41, 42};
#define LED_N_PERCH_DOWN   2
static const uint8_t LED_GROUP_PERCH_DOWN[LED_N_PERCH_DOWN] = {43, 44};
#define LED_N_TWISP        4
static const uint8_t LED_GROUP_TWISP[LED_N_TWISP] = {45, 46, 47, 48};
