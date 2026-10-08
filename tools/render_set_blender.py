"""The set, assembled, on a table: run by tools/render_3d.py inside Blender.

    blender -b -P tools/render_set_blender.py -- scene.json      (Blender 4.2 or later)

scene.json (written by tools/render_3d.py) lists each part: a .glb or .stl file, a
rotation (degrees, X then Y then Z) and a translation (mm) into the world frame, and a
material for the printed ones; and the views to render.  The world frame: x right as you
face the set (the base's KiCad x), y away from you (the base's KiCad y, negated), z up,
the base's top surface at z = 0.  A board's glTF from KiCad has its own frame's x and -y
in the plane and its bottom face at z = 0.
"""
import json, math, sys
import bpy
import mathutils

MM = 0.001


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def place(objs, rot, tr):
    """Parent the imported objects to an empty and move the empty into the world."""
    e = bpy.data.objects.new("part", None)
    bpy.context.scene.collection.objects.link(e)
    for o in objs:
        if o.parent is None:
            o.parent = e
    e.rotation_mode = "XYZ"
    e.rotation_euler = [math.radians(a) for a in rot]
    e.location = [v * MM for v in tr]
    return e


def import_glb(path):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.context.scene.objects if o not in before]


def import_stl(path, mat):
    before = set(bpy.context.scene.objects)
    bpy.ops.wm.stl_import(filepath=path, global_scale=MM)
    new = [o for o in bpy.context.scene.objects if o not in before]
    for o in new:
        o.data.materials.clear()
        o.data.materials.append(mat)
        for p in o.data.polygons:
            p.use_smooth = True
        o.modifiers.new("smooth", "EDGE_SPLIT").split_angle = math.radians(35)
    return new


def material(name, rgb, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def finish_materials(skip):
    """KiCad's glTF materials, made to look like the board that comes from JLCPCB: its
    solder mask is a translucent purple over pale FR4 (it read lilac), ENIG a flat yellow,
    and every component's body metallic and fully rough.  By colour, since they are named
    mat_0, mat_1..."""
    for m in bpy.data.materials:
        if m in skip or not m.use_nodes or "Principled BSDF" not in m.node_tree.nodes:
            continue
        b = m.node_tree.nodes["Principled BSDF"]
        r, g, bl, _ = b.inputs["Base Color"].default_value
        alpha = b.inputs["Alpha"].default_value
        metal = b.inputs["Metallic"].default_value
        rough = b.inputs["Roughness"].default_value
        if alpha < 0.95 and bl > r > g:                          # the solder mask
            b.inputs["Base Color"].default_value = (0.075, 0.008, 0.13, 1.0)
            b.inputs["Alpha"].default_value = 0.94
            b.inputs["Roughness"].default_value = 0.28
            b.inputs["Coat Weight"].default_value = 0.4
        elif metal > 0.5 and rough < 0.5 and r > 0.6 and bl < 0.1:   # ENIG
            b.inputs["Base Color"].default_value = (0.95, 0.74, 0.36, 1.0)
            b.inputs["Roughness"].default_value = 0.22
        elif metal > 0.5 and rough > 0.9:                         # a component's body
            grey = max(r, g, bl) - min(r, g, bl) < 0.08 and r > 0.45
            b.inputs["Metallic"].default_value = 1.0 if grey else 0.0
            b.inputs["Roughness"].default_value = 0.3 if grey else 0.45


def area(name, loc, target, size, power, rgb=(1.0, 1.0, 1.0)):
    d = bpy.data.lights.new(name, "AREA")
    d.size = size * MM
    d.energy = power
    d.color = rgb
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = [v * MM for v in loc]
    aim(o, target)


def aim(o, target):
    d = mathutils.Vector([v * MM for v in target]) - o.location
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main():
    spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
    clear()
    sc = bpy.context.scene
    mats = {k: material(k, v["rgb"], v["rough"], v.get("metal", 0.0))
            for k, v in spec["materials"].items()}
    for part in spec["parts"]:
        if part["file"].endswith(".glb"):
            objs = import_glb(part["file"])
        else:
            objs = import_stl(part["file"], mats[part["material"]])
        place(objs, part["rot"], part["at"])
    finish_materials(set(mats.values()))
    # the table
    t = spec["table"]
    bpy.ops.mesh.primitive_plane_add(size=t["size"] * MM, location=(t["at"][0] * MM, t["at"][1] * MM, t["z"] * MM))
    bpy.context.active_object.data.materials.append(mats["table"])
    # lights: a large soft key from the front left, a fill from the right, a rim from behind
    for l in spec["lights"]:
        area(l["name"], l["at"], l["target"], l["size"], l["power"], tuple(l.get("rgb", (1.0, 1.0, 1.0))))
    # a large soft panel overhead, unseen by the camera, for the gold to reflect
    sb = spec.get("softbox")
    if sb:
        bpy.ops.mesh.primitive_plane_add(size=sb["size"] * MM, location=[v * MM for v in sb["at"]])
        o = bpy.context.active_object
        m = bpy.data.materials.new("softbox")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.remove(nt.nodes["Principled BSDF"])
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Strength"].default_value = sb["strength"]
        nt.links.new(e.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
        o.data.materials.append(m)
        o.visible_camera = False
        o.visible_shadow = False
    w = sc.world or bpy.data.worlds.new("world")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (*spec["world"]["rgb"], 1.0)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = spec["world"]["strength"]
    # Cycles on the CPU
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = spec["samples"]
    sc.cycles.use_denoising = True
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_percentage = 100
    cam_data = bpy.data.cameras.new("camera")
    cam = bpy.data.objects.new("camera", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for v in spec["views"]:
        sc.render.resolution_x, sc.render.resolution_y = v["size"]
        cam_data.lens = v["lens"]
        cam.location = [c * MM for c in v["at"]]
        aim(cam, v["target"])
        cam_data.dof.use_dof = True
        cam_data.dof.focus_distance = (cam.location - mathutils.Vector([c * MM for c in v["target"]])).length
        cam_data.dof.aperture_fstop = v.get("fstop", 8.0)
        sc.render.filepath = v["out"]
        bpy.ops.render.render(write_still=True)
        print("RENDERED", v["out"])


main()
