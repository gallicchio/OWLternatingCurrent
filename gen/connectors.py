"""The two board-to-board joints, pin by pin: the one source of truth for the sheets that
draw them and the boards that carry them.

Both joints use the same two parts (one setup fee each): a 2 x 8, 2.54 mm right-angle
header on the tree (its pins point down into the base and up into the perch) and a
vertical 2 x 8 socket on the base and under the perch.  Pin N of a header meets pin N
of its socket; the board generator places the footprints so (gen/board.py checks it).

The levitation coil's two ends take two pins each (3.3 A at most; the parts are rated
3 A a pin) and sit across the rows from grounds.  The Hall sensor's line sits at the far
end from them, across from 3.3 V.  The even pins are the same on both joints, so on
the tree the coil's and the supplies' lines run straight across from one header to the
other.
"""

BASE_TREE = {1: "HALL", 2: "+3V3", 3: "SDA", 4: "+5V", 5: "SCL", 6: "GND", 7: "GND", 8: "LEV_B",
             9: "GND", 10: "LEV_B", 11: "GND", 12: "GND", 13: "GND", 14: "LEV_A", 15: "GND", 16: "LEV_A"}

TREE_PERCH = {1: "HALL", 2: "+3V3", 3: "GND", 4: "+5V", 5: "GND", 6: "GND", 7: "GND", 8: "LEV_B",
              9: "GND", 10: "LEV_B", 11: "GND", 12: "GND", 13: "DOWN0", 14: "LEV_A", 15: "DOWN1", 16: "LEV_A"}

assert all(BASE_TREE[p] == TREE_PERCH[p] for p in range(2, 17, 2))
