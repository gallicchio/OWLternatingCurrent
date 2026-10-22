// OWLternating Current: the printed parts (one plate, PLA, no supports, one pause).
//
//   owl      - the perch's bias-magnet holder; snaps onto the perch's notches
//   cap      - the floating bat's magnet cap; hooks under the bat's head and tail
//   foot     - one of four snap-in feet for the base board
//
// Every number comes from out/params.scad, which print/build.py writes from
// gen/mech.py (boards, magnets) and print/design.py (printing); the shapes (body
// hulls, paths on the owl's surface) from out/shapes.scad.  Do not edit numbers
// here: change mech.py or design.py and run `python3 print/build.py`.
//
// Frames: owl - perch's coil centre on the perch's top surface; cap - bat's magnet
// axis on the bat's top surface; z up, y toward the back (KiCad y; viewer at -y).
// The *_print modules add Z0 and the part's breakaway stand-in.

include <out/params.scad>
include <out/shapes.scad>

PART = "plate";
OPEN = false;      // true: the no-pause version (build.py passes -D OPEN=true)
FN = 72;

// ---------------------------------------------------------------- helpers
module poly(P) polyhedron(points = P[0], faces = P[1], convexity = 4);
// a hole's polygon, circumscribed so its flats (not just its corners) are at r
module circle_c(r, n = FN) circle(r = r / cos(180 / n), $fn = n);
// a groove (or ridge) drawn along a polyline with a ball
module ball_chain(pts, r)
    for (i = [0 : len(pts) - 2])
        hull() { translate(pts[i]) sphere(r, $fn = 10); translate(pts[i + 1]) sphere(r, $fn = 10); }
// the (y, z) polygon P extruded along x, centred (width w)
module yz_extrude(w) rotate([90, 0, 90]) linear_extrude(height = w, center = true) children();
// the (x, z) polygon extruded along y, centred
module xz_extrude(w) rotate([90, 0, 0]) linear_extrude(height = w, center = true) children();

// ================================================================= the owl
module owl_wing_prism() rotate([90, 0, 90]) linear_extrude(height = 40) polygon(OWL_WING_2D);

module owl_arm_free() {        // +x: the flexing plate, from the lip up to its root
    intersection() {
        translate([0, 0, OWL_Z_BOTTOM])
            linear_extrude(OWL_ROOT_Z - OWL_Z_BOTTOM)
                offset(r = WING_RELIEF, $fn = 32) polygon(OWL_SECTION_2D);
        translate([OWL_ARM_IN, -30, OWL_Z_BOTTOM - 1]) cube([10, 60, 60]);
        owl_wing_prism();
    }
}

module owl_lip() {             // +x: the hook under the perch, and the talon outside
    xz_extrude(2 * OWL_ARM_HALF_W) {
        polygon([[OWL_ARM_IN + 0.3, OWL_Z_BOTTOM], [OWL_ARM_IN, OWL_Z_BOTTOM],
                 [OWL_LIP_TIP, OWL_Z_CATCH - OWL_LEADIN_LAND], [OWL_LIP_TIP, OWL_Z_CATCH],
                 [OWL_ARM_IN + 0.3, OWL_Z_CATCH]]);
        polygon([[OWL_ARM_IN + OWL_ARM_T - 0.3, OWL_Z_BOTTOM],
                 [OWL_ARM_IN + OWL_ARM_T + OWL_TALON, OWL_Z_BOTTOM],
                 [OWL_ARM_IN + OWL_ARM_T - 0.3, OWL_Z_BOTTOM + OWL_TALON + 0.3]]);
    }
}

module owl_arm_chamfers() {    // clear the router's fillets in the notch's inner corners
    for (s = [-1, 1])
        intersection() {
            translate([OWL_ARM_IN, s * OWL_ARM_HALF_W, 0]) rotate([0, 0, 45])
                cube([OWL_ARM_CHAMFER * sqrt(2), OWL_ARM_CHAMFER * sqrt(2), 20], center = true);
            translate([OWL_ARM_IN - 0.01, -10, OWL_Z_CATCH]) cube([5, 20, 0.4 - OWL_Z_CATCH]);
        }
}

module owl_wing_relief() {     // +x: the wing above its root, leaning in to the shoulder
    intersection() {
        poly(OWL_RELIEF);
        owl_wing_prism();
        translate([0, -30, OWL_ROOT_Z]) cube([30, 60, 30]);
        translate([OWL_WING_LEAN[0], 0, OWL_WING_LEAN[1]]) rotate([0, -OWL_WING_LEAN[2], 0])
            translate([-60, -30, -60]) cube([60, 60, 120]);
    }
}

module owl_wing() {
    difference() {
        union() { owl_arm_free(); owl_wing_relief(); owl_lip(); }
        owl_arm_chamfers();
    }
}

module owl_pupils() {          // [x, z, y of the face]
    for (e = OWL_EYES)
        translate([e[0], e[2] - 2, e[1]]) rotate([-90, 0, 0])
            cylinder(h = 2 + OWL_PUPIL_DEPTH, r = OWL_PUPIL_R, $fn = 40);
}

module owl_highlights() {      // a catch-light in each pupil, both lit from the upper right
    for (e = OWL_EYES)
        translate([e[0] + 0.8, e[2] + 0.3, e[1] + 0.85]) rotate([-90, 0, 0])
            cylinder(h = OWL_PUPIL_DEPTH, r = 0.6, $fn = 20);
}

module owl_beak() hull() for (s = OWL_BEAK) translate([s[0], s[1], s[2]]) sphere(s[3], $fn = 24);

module owl_tufts()
    for (m = [0, 1]) mirror([m, 0, 0]) hull() {
        translate([OWL_TUFT_BASE[0], OWL_TUFT_BASE[1], OWL_TUFT_BASE[2]])
            scale([1, 0.5, 1]) sphere(OWL_TUFT_BASE[3], $fn = 32);
        translate([OWL_TUFT_TIP[0], OWL_TUFT_TIP[1], OWL_TUFT_TIP[2]]) sphere(OWL_TUFT_TIP[3], $fn = 16);
    }

module owl_toes()
    for (t = OWL_TOES)
        hull() {
            translate([t[0], t[1], t[4]]) sphere(t[4], $fn = 16);
            translate([t[2], t[3], t[4]]) sphere(t[4], $fn = 16);
        }

module owl_recess()            // hollow under the base: only a rim touches the perch
    hull() {
        translate([0, 0, -1]) linear_extrude(1.001) polygon(OWL_RECESS_2D);
        for (s = [-1, 1]) translate([s * OWL_RECESS_RIDGE[0], 0, OWL_RECESS_RIDGE[1]]) cube(0.02, center = true);
    }

// OPEN: the no-pause version.  The owl's pocket runs out of its back as a slot (with a
// groove up each side wall for the epoxy to key into); the cap's pocket has no floor.
module owl_pocket()
    translate([0, 0, OWL_FLOOR])
        if (OPEN) linear_extrude(OPEN_GAP_T) {
            circle_c(POCKET_R);
            translate([-OPEN_SLOT_W / 2, 0]) square([OPEN_SLOT_W, OPEN_SLOT_END]);
            for (s = [-1, 1]) translate([s * (OPEN_SLOT_W + OPEN_KEY_D) / 2, OPEN_KEY_Y])
                square([OPEN_KEY_D + 0.02, OPEN_KEY_W], center = true);
        }
        else linear_extrude(POCKET_DEPTH) circle_c(POCKET_R);

module owl() {
    difference() {
        union() {
            poly(OWL_BODY);
            owl_wing();
            mirror([1, 0, 0]) owl_wing();
            owl_beak();
            owl_tufts();
            owl_toes();
        }
        owl_pocket();
        owl_recess();
        owl_pupils();
        for (g = OWL_EYE_RINGS) ball_chain(g, OWL_GROOVE_R + 0.05);
        for (g = OWL_BELLY_GROOVES) ball_chain(g, OWL_GROOVE_R);
        for (g = OWL_WING_GROOVES) { ball_chain(g, OWL_GROOVE_R); mirror([1, 0, 0]) ball_chain(g, OWL_GROOVE_R); }
    }
    owl_highlights();
}

module owl_standin()           // breakaway slab: the perch's place while printing
    linear_extrude(OWL_SLAB_TOP)
        offset(r = 2, $fn = 24) offset(delta = -2)
            translate([-OWL_SLAB_HALF_X, OWL_SLAB_Y[0]])
                square([2 * OWL_SLAB_HALF_X, OWL_SLAB_Y[1] - OWL_SLAB_Y[0]]);

module owl_print() { translate([0, 0, OWL_Z0]) owl(); owl_standin(); }

// ================================================================= the bat's cap
module cap_hook_2d(y_in, y_out, y_tip) {   // one end's drop, lip and foot, in (y, z)
    s = sign(y_tip - y_in);                 // +1 at the head (inward is +y), -1 at the tail
    polygon([[y_out - s * CAP_FOOT, CAP_Z_BOTTOM], [y_in, CAP_Z_BOTTOM],
             [y_tip, CAP_Z_CATCH - CAP_LEADIN_LAND], [y_tip, CAP_Z_CATCH],
             [y_in, CAP_Z_CATCH], [y_in, CAP_ARM_RAISE + CAP_ARM_T],
             [y_out, CAP_ARM_RAISE + CAP_ARM_T], [y_out, CAP_Z_BOTTOM + CAP_FOOT]]);
}

module cap_ears()
    for (e = CAP_EARS)
        hull() {
            translate([e[0], e[1], e[2]]) scale([1, 0.4, 1]) sphere(e[3], $fn = 24);
            translate([e[4], e[5], e[6]]) sphere(e[7], $fn = 12);
        }

module cap() {
    ends = [[CAP_HEAD_DROP_IN, CAP_HEAD_DROP_IN - CAP_DROP_T, CAP_HEAD_LIP_TIP],
            [CAP_TAIL_DROP_IN, CAP_TAIL_DROP_IN + CAP_DROP_T, CAP_TAIL_LIP_TIP]];
    difference() {
        union() {
            rotate_extrude($fn = FN) polygon(CAP_DOME_2D);
            for (e = ends) {
                translate([-M_CAP_ARM_W / 2, min(e[0], 0), CAP_ARM_RAISE]) cube([M_CAP_ARM_W, abs(e[0]), CAP_ARM_T]);
                yz_extrude(M_CAP_ARM_W) cap_hook_2d(e[0], e[1], e[2]);
            }
            cap_ears();
        }
        if (OPEN) translate([0, 0, -0.01]) linear_extrude(CAP_OPEN_DEPTH + 0.01) circle_c(POCKET_R);
        else translate([0, 0, CAP_FLOOR_T]) linear_extrude(POCKET_DEPTH) circle_c(POCKET_R);
    }
}

module cap_pedestal() {        // breakaway pedestal: the bat's place, and the height that
    y0 = CAP_HEAD_DROP_IN - CAP_DROP_T - CAP_FOOT - 0.8;   // closes the cap's pocket on the
    y1 = CAP_TAIL_DROP_IN + CAP_DROP_T + CAP_FOOT + 0.8;   // owl's layer: one pause
    translate([-CAP_PED_HALF_X, y0, 0]) cube([2 * CAP_PED_HALF_X, y1 - y0, CAP_PLATFORM_TOP]);
    translate([0, 0, CAP_PLATFORM_TOP - 0.01])
        cylinder(r = CAP_DOME_R + 0.3, h = CAP_PLATEAU_TOP - CAP_PLATFORM_TOP + 0.01, $fn = FN);
}

module cap_print() { translate([0, 0, CAP_Z0]) cap(); cap_pedestal(); }

// ================================================================= a foot
module foot() {
    base = M_FOOT_HEIGHT - FOOT_MOAT_DEPTH;
    difference() {
        union() {
            intersection() {
                union() {
                    cylinder(r = FOOT_CORE_R, h = M_FOOT_HEIGHT, $fn = 48);
                    for (i = [0 : FOOT_LOBES - 1]) rotate(i * 360 / FOOT_LOBES)
                        translate([FOOT_R - FOOT_LOBE_R, 0, M_FOOT_HEIGHT / 2])
                            scale([1, 0.9, FOOT_LOBE_RZ / FOOT_LOBE_R]) sphere(FOOT_LOBE_R, $fn = 32);
                }
                cylinder(r = FOOT_R + 1, h = M_FOOT_HEIGHT, $fn = 48);
            }
            translate([0, 0, base]) cylinder(d = FOOT_PEG_D, h = FOOT_CATCH_Z - base, $fn = 40);
            translate([0, 0, FOOT_CATCH_Z])
                cylinder(d1 = FOOT_BARB_D, d2 = FOOT_BARB_TOP_D, h = FOOT_BARB_H, $fn = 40);
        }
        translate([0, 0, base]) difference() {          // the moat frees the prongs
            cylinder(r = FOOT_MOAT_R, h = FOOT_MOAT_DEPTH + 0.01, $fn = 40);
            translate([0, 0, -1]) cylinder(d = FOOT_PEG_D, h = FOOT_MOAT_DEPTH + 2, $fn = 40);
        }
        translate([-FOOT_SLOT / 2, -FOOT_MOAT_R, base]) cube([FOOT_SLOT, 2 * FOOT_MOAT_R, 20]);
    }
}

// ================================================================= the boards (for the fit views)
module perch_2d()
    difference() {
        offset(r = 2, $fn = 24) offset(delta = -2)
            translate([-M_PERCH_W / 2, M_PERCH_FRONT]) square([M_PERCH_W, M_PERCH_BACK - M_PERCH_FRONT]);
        for (s = [-1, 1])        // the notches, routed: inside corners keep a 0.5 mm radius
            translate([s * (M_PERCH_W / 2 - M_OWL_NOTCH_D + 1), OWL_NOTCH_MID])
                offset(r = 0.5, $fn = 16) offset(delta = -0.5) square([2, OWL_NOTCH_LEN], center = true);
        translate(M_THREAD_HOLE) circle(d = M_THREAD_HOLE_D, $fn = 24);
    }

module perch() {
    color("#4b2a6b") translate([0, 0, -M_PCB_T]) linear_extrude(M_PCB_T) perch_2d();
    color("#c87533") translate([0, 0, -0.04]) linear_extrude(0.05)
        difference() { circle(r = M_COIL_R_OUT, $fn = 96); circle(r = M_COIL_R_IN, $fn = 48); }
}

module bat() {
    color("#2e1a47") translate([0, 0, -M_PCB_T]) linear_extrude(M_PCB_T) polygon(BAT_OUTLINE_2D);
    color("#c87533") translate([0, 0, -0.04]) linear_extrude(0.05)
        difference() { circle(r = M_RX_R_OUT, $fn = 96); circle(r = M_RX_R_IN, $fn = 48); }
}

// a magnet drawn in two colours, north (red) up: in the views both point the same way
module magnet(cut = false)
    for (h = [[0, "#3a6fd8"], [M_MAGNET_T / 2, "#d83a3a"]])
        color(h[1]) translate([0, 0, h[0]]) linear_extrude(M_MAGNET_T / 2)
            difference() { circle(d = M_MAGNET_D, $fn = 64); if (cut) quarter_2d(); }

module quarter_2d() translate([-60, -60]) square(60);       // the quarter toward the viewer

// ================================================================= views (import the built meshes)
C_OWL = "#d08a3c"; C_CAP = "#8a5cc8"; C_FOOT = "#f08a24"; C_SCRAP = "#c8c8c8";

module perch_cut() {
    color("#4b2a6b") translate([0, 0, -M_PCB_T]) linear_extrude(M_PCB_T)
        difference() { perch_2d(); quarter_2d(); }
    color("#c87533") translate([0, 0, -0.04]) linear_extrude(0.05) difference() {
        circle(r = M_COIL_R_OUT, $fn = 96); circle(r = M_COIL_R_IN, $fn = 48); quarter_2d(); }
}

module bat_cut() {
    color("#2e1a47") translate([0, 0, -M_PCB_T]) linear_extrude(M_PCB_T)
        difference() { polygon(BAT_OUTLINE_2D); quarter_2d(); }
    color("#c87533") translate([0, 0, -0.04]) linear_extrude(0.05) difference() {
        circle(r = M_RX_R_OUT, $fn = 96); circle(r = M_RX_R_IN, $fn = 48); quarter_2d(); }
}

module view_levitation() {     // quarter cut away: the owl's magnet over the bat's, same way up
    perch_cut();
    translate([0, 0, OWL_FLOOR]) magnet(true);
    color(C_OWL) import("build/owl_cut.stl", convexity = 10);
    translate([0, 0, BAT_Z_FLOATING]) {
        bat_cut();
        translate([0, 0, CAP_FLOOR_T + POCKET_DEPTH - M_MAGNET_T]) magnet(true);
        color(C_CAP) import("build/cap_cut.stl", convexity = 10);
    }
}

module view_assembly() {
    perch();
    color(C_OWL) import("out/assembled/owl_in_perch_frame.stl", convexity = 10);
    translate([0, 0, BAT_Z_FLOATING]) {
        bat();
        color(C_CAP) import("out/assembled/bat_cap_in_bat_frame.stl", convexity = 10);
    }
}

module view_plate() {
    color("#30343a") translate([0, 0, -0.6]) linear_extrude(0.6)
        offset(r = 4, $fn = 24) offset(delta = -4) square(BED, center = true);
    color(C_OWL) import("build/plate_owl.stl", convexity = 10);
    color(C_CAP) import("build/plate_cap.stl", convexity = 10);
    color(C_FOOT) import("build/plate_feet.stl", convexity = 10);
    color(C_SCRAP) import("build/plate_standins.stl", convexity = 10);
}

module view_plate_paused() {   // the plate at the pause: everything cut at the pause height
    color("#30343a") translate([0, 0, -0.6]) linear_extrude(0.6)
        offset(r = 4, $fn = 24) offset(delta = -4) square(BED, center = true);
    color(C_OWL) import("build/paused_owl.stl", convexity = 10);
    color(C_CAP) import("build/paused_cap.stl", convexity = 10);
    color(C_FOOT) import("build/plate_feet.stl", convexity = 10);
    color(C_SCRAP) import("build/plate_standins.stl", convexity = 10);
    for (p = [PLATE_OWL, PLATE_BAT_CAP]) translate([p[0], p[1], POCKET_FLOOR_Z]) magnet();
}

module cut_below(z) intersection() { children(); translate([-200, -200, -1]) cube([400, 400, z + 1]); }
module cut_quarter() difference() { children(); translate([-60, -60, -60]) cube([60, 60, 120]); }

// ================================================================= what to make
if (PART == "owl") owl();
else if (PART == "owl_standin") owl_standin();
else if (PART == "owl_print") owl_print();
else if (PART == "cap") cap();
else if (PART == "cap_pedestal") cap_pedestal();
else if (PART == "cap_print") cap_print();
else if (PART == "foot") foot();
else if (PART == "perch") perch();
else if (PART == "bat") bat();
// meshes for the pictures (CGAL cuts, so the cut faces keep the part's colour)
else if (PART == "owl_cut") cut_quarter() owl();
else if (PART == "cap_cut") cut_quarter() cap();
else if (PART == "paused_owl") translate([PLATE_OWL[0], PLATE_OWL[1], 0]) cut_below(PAUSE_Z - 0.01) translate([0, 0, OWL_Z0]) owl();
else if (PART == "paused_cap") translate([PLATE_BAT_CAP[0], PLATE_BAT_CAP[1], 0]) cut_below(PAUSE_Z - 0.01) translate([0, 0, CAP_Z0]) cap();
// the views
else if (PART == "view_levitation") view_levitation();
else if (PART == "view_assembly") view_assembly();
else if (PART == "view_plate") view_plate();
else if (PART == "view_plate_paused") view_plate_paused();
else if (PART == "view_owl") color(C_OWL) import("out/assembled/owl_in_perch_frame.stl", convexity = 10);
else if (PART == "view_cap") color(C_CAP) import("out/assembled/bat_cap_in_bat_frame.stl", convexity = 10);
else if (PART == "view_foot") color(C_FOOT) import("build/foot.stl", convexity = 10);
else if (PART == "view_owl_open") color(C_OWL) import("build/owl_open.stl", convexity = 10);
else if (PART == "view_cap_open") color(C_CAP) import("build/cap_open.stl", convexity = 10);
else if (PART == "view_owl_on_perch") {
    perch();
    color(C_OWL) import("out/assembled/owl_in_perch_frame.stl", convexity = 10);
}
else if (PART == "view_cap_on_bat") {
    bat();
    color(C_CAP) import("out/assembled/bat_cap_in_bat_frame.stl", convexity = 10);
}
