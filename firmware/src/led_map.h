/* led_map.h: every LED on OWLternating Current rev A: driver, channel, name, colour, board, position.
 * WRITTEN BY gen/firmware_leds.py FROM gen/leds.py (and the placement's
 * hardware/checks/led_positions.json, when it exists): edit those, not this. */
#pragma once
#include <stdint.h>

enum { LED_DRV_BASE = 0, LED_DRV_TREE = 1, LED_DRIVERS = 2 };
#define LED_DRIVER_CHANNELS 36   /* LP5036: 12 banks of 3 */
#define LED_DRIVER_BANKS    12
static const uint8_t LED_DRIVER_ADDR[LED_DRIVERS] = {0x30, 0x32};

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
    LED_WISP0 = 0,
    LED_PUMPKIN1 = 1,
    LED_WISP2 = 2,
    LED_PUMPKIN0 = 3,
    LED_WISP1 = 4,
    LED_OWLRING0 = 5,
    LED_STAR3 = 6,
    LED_OWLRING2 = 7,
    LED_STAR2 = 8,
    LED_STAR1 = 9,
    LED_STAR0 = 10,
    LED_OWLRING1 = 11,
    LED_STARX2 = 12,
    LED_STARX0 = 13,
    LED_STARX1 = 14,
    LED_STAR8 = 15,
    LED_STAR7 = 16,
    LED_STAR9 = 17,
    LED_STAR10 = 18,
    LED_STARX3 = 19,
    LED_STAR11 = 20,
    LED_CATRING2 = 21,
    LED_STAR6 = 22,
    LED_WISP4 = 23,
    LED_WISP3 = 24,
    LED_WISP5 = 25,
    LED_PUMPKIN2 = 26,
    LED_CATRING0 = 27,
    LED_CATRING1 = 28,
    LED_STAR5 = 29,
    LED_STAR4 = 30,
    LED_OWLC_L = 31,
    LED_TWISP0 = 32,
    LED_TSTAR3 = 33,
    LED_OWLA_L = 34,
    LED_OWLA_R = 35,
    LED_TWISP2 = 36,
    LED_TSTAR0 = 37,
    LED_TSTAR2 = 38,
    LED_PERCH_DOWN1 = 39,
    LED_PERCH_DOWN0 = 40,
    LED_TSTAR1 = 41,
    LED_OWLB_L = 42,
    LED_OWLB_R = 43,
    LED_TWISP3 = 44,
    LED_TSTAR4 = 45,
    LED_TWISP1 = 46,
    LED_TSTAR5 = 47,
    LED_OWLC_R = 48,
};

static const led_info LED_MAP[LED_COUNT] = {
    {LED_DRV_BASE,  0, "WISP0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 0 of 6 */
    {LED_DRV_BASE,  1, "PUMPKIN1", LED_COL_AMBER5050, 0.00f, 0.00f, LED_BOARD_BASE},   /* pumpkin 1's face, left to right */
    {LED_DRV_BASE,  2, "WISP2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 2 of 6 */
    {LED_DRV_BASE,  3, "PUMPKIN0", LED_COL_AMBER5050, 0.00f, 0.00f, LED_BOARD_BASE},   /* pumpkin 0's face, left to right */
    {LED_DRV_BASE,  4, "WISP1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 1 of 6 */
    {LED_DRV_BASE,  5, "OWLRING0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the owl's perch, at 0 degrees */
    {LED_DRV_BASE,  6, "STAR3", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 3 of 12, left to right */
    {LED_DRV_BASE,  7, "OWLRING2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the owl's perch, at 240 degrees */
    {LED_DRV_BASE,  8, "STAR2", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 2 of 12, left to right */
    {LED_DRV_BASE,  9, "STAR1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 1 of 12, left to right */
    {LED_DRV_BASE, 10, "STAR0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 0 of 12, left to right */
    {LED_DRV_BASE, 11, "OWLRING1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the owl's perch, at 120 degrees */
    {LED_DRV_BASE, 12, "STARX2", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 2 */
    {LED_DRV_BASE, 13, "STARX0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 0 */
    {LED_DRV_BASE, 19, "STARX1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 1 */
    {LED_DRV_BASE, 20, "STAR8", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 8 of 12, left to right */
    {LED_DRV_BASE, 21, "STAR7", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 7 of 12, left to right */
    {LED_DRV_BASE, 22, "STAR9", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 9 of 12, left to right */
    {LED_DRV_BASE, 23, "STAR10", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 10 of 12, left to right */
    {LED_DRV_BASE, 24, "STARX3", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* scattered sky star 3 */
    {LED_DRV_BASE, 25, "STAR11", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 11 of 12, left to right */
    {LED_DRV_BASE, 26, "CATRING2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the cat's perch, at 240 degrees */
    {LED_DRV_BASE, 27, "STAR6", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 6 of 12, left to right */
    {LED_DRV_BASE, 28, "WISP4", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 4 of 6 */
    {LED_DRV_BASE, 29, "WISP3", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 3 of 6 */
    {LED_DRV_BASE, 30, "WISP5", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_BASE},   /* along the hill, left to right, 5 of 6 */
    {LED_DRV_BASE, 31, "PUMPKIN2", LED_COL_AMBER5050, 0.00f, 0.00f, LED_BOARD_BASE},   /* pumpkin 2's face, left to right */
    {LED_DRV_BASE, 32, "CATRING0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the cat's perch, at 0 degrees */
    {LED_DRV_BASE, 33, "CATRING1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_PERCH},   /* round the cat's perch, at 120 degrees */
    {LED_DRV_BASE, 34, "STAR5", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 5 of 12, left to right */
    {LED_DRV_BASE, 35, "STAR4", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_BASE},   /* sky arc, position 4 of 12, left to right */
    {LED_DRV_TREE,  0, "OWLC_L", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl C, left eye */
    {LED_DRV_TREE,  1, "TWISP0", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 0 */
    {LED_DRV_TREE,  2, "TSTAR3", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 3 */
    {LED_DRV_TREE, 10, "OWLA_L", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl A, left eye */
    {LED_DRV_TREE, 11, "OWLA_R", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl A, right eye */
    {LED_DRV_TREE, 12, "TWISP2", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 2 */
    {LED_DRV_TREE, 13, "TSTAR0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 0 */
    {LED_DRV_TREE, 14, "TSTAR2", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 2 */
    {LED_DRV_TREE, 15, "PERCH_DOWN1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_PERCH},   /* perch underside, right of the coil */
    {LED_DRV_TREE, 16, "PERCH_DOWN0", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_PERCH},   /* perch underside, left of the coil */
    {LED_DRV_TREE, 21, "TSTAR1", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 1 */
    {LED_DRV_TREE, 22, "OWLB_L", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl B, left eye */
    {LED_DRV_TREE, 23, "OWLB_R", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl B, right eye */
    {LED_DRV_TREE, 24, "TWISP3", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 3 */
    {LED_DRV_TREE, 31, "TSTAR4", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 4 */
    {LED_DRV_TREE, 33, "TWISP1", LED_COL_PURPLE, 0.00f, 0.00f, LED_BOARD_TREE},   /* in the tree's branches 1 */
    {LED_DRV_TREE, 34, "TSTAR5", LED_COL_VIOLET, 0.00f, 0.00f, LED_BOARD_TREE},   /* tree sky star 5 */
    {LED_DRV_TREE, 35, "OWLC_R", LED_COL_ORANGE, 0.00f, 0.00f, LED_BOARD_TREE},   /* owl C, right eye */
};

/* each driver's outputs: the LED on OUTn, or -1 */
static const int8_t LED_OF_CHANNEL[LED_DRIVERS][LED_DRIVER_CHANNELS] = {
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, -1, -1, -1, -1, -1, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30},   /* BASE */
    {31, 32, 33, -1, -1, -1, -1, -1, -1, -1, 34, 35, 36, 37, 38, 39, 40, -1, -1, -1, -1, 41, 42, 43, 44, -1, -1, -1, -1, -1, -1, 45, -1, 46, 47, 48},   /* TREE */
};

/* named groups, in order (the scenes walk these) */
#define LED_N_WISP         6
static const uint8_t LED_GROUP_WISP[LED_N_WISP] = {0, 2, 4, 23, 24, 25};
#define LED_N_PUMPKIN      3
static const uint8_t LED_GROUP_PUMPKIN[LED_N_PUMPKIN] = {1, 3, 26};
#define LED_N_OWLRING      3
static const uint8_t LED_GROUP_OWLRING[LED_N_OWLRING] = {5, 7, 11};
#define LED_N_STAR         12
static const uint8_t LED_GROUP_STAR[LED_N_STAR] = {6, 8, 9, 10, 15, 16, 17, 18, 20, 22, 29, 30};
#define LED_N_STARX        4
static const uint8_t LED_GROUP_STARX[LED_N_STARX] = {12, 13, 14, 19};
#define LED_N_CATRING      3
static const uint8_t LED_GROUP_CATRING[LED_N_CATRING] = {21, 27, 28};
#define LED_N_OWLEYE       6
static const uint8_t LED_GROUP_OWLEYE[LED_N_OWLEYE] = {31, 34, 35, 42, 43, 48};
#define LED_N_TWISP        4
static const uint8_t LED_GROUP_TWISP[LED_N_TWISP] = {32, 36, 44, 46};
#define LED_N_TSTAR        6
static const uint8_t LED_GROUP_TSTAR[LED_N_TSTAR] = {33, 37, 38, 41, 45, 47};
#define LED_N_PERCH_DOWN   2
static const uint8_t LED_GROUP_PERCH_DOWN[LED_N_PERCH_DOWN] = {39, 40};
