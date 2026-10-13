#!/usr/bin/env python3
"""
Virtual assembly + collision checks + preview renders.
AI-READABLE: run `python assemble.py [W] [CORE_ID] [ALPHA_DEG]`
  W        film width = core length, mm (default 500)
  CORE_ID  core inner diameter, mm (default 38)
  ALPHA    holder rotation about pivot in 15-deg steps (default 0 = slot opens straight up)
Outputs: assembly_preview.stl, preview/*.png, prints intersection volumes (mm^3, ~0 = OK).
World frame: Z = axle direction; clamp_L occupies z in [0, clamp_w]; Y up; table top plane y = arm_lo+jaw_gap.
"""
import sys
import numpy as np
import trimesh
from manifold3d import Manifold
import generate as g
from generate import P, extrude, circle, to_trimesh

W = float(sys.argv[1]) if len(sys.argv) > 1 else 500.0
CORE_ID = float(sys.argv[2]) if len(sys.argv) > 2 else 38.0
ALPHA = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
FILM_OD = 130.0
CORE_WALL = 3.0
ROD_PAST_NUT = 12.0  # rod end sticks this far past the cone top face (nut pocket 8.8 + roof)


def cyl(r, z0, z1, c=(0, 0), n=64):
    return extrude(circle(r, c, n), z1 - z0).translate((0, 0, z0))


def calc(W, core_id):
    parts, info = g.build_all()
    ci = info["cone"]
    z_ins = g.cone_insertion(core_id)
    D_n = ci["z_neck_mid"] - z_ins                    # roll end -> groove mid-plane
    spacing = W + 2 * D_n                             # holder plate mid-plane to mid-plane
    rod = W + 2 * (ci["z_top"] + ROD_PAST_NUT - z_ins)
    return dict(z_ins=z_ins, D_n=D_n, spacing=spacing, rod=rod, ci=ci)


def build_assembly(W, core_id, alpha):
    parts, info = g.build_all()
    c = calc(W, core_id)
    ci = c["ci"]
    ring_c = info["ring_c"]
    clamp_w = P["clamp_w"]
    ht = P["holder_t"]
    hh = P["teeth_h"] + P["teeth_gap"]

    A = {}
    # ---- left side ----
    A["clamp_L"] = parts["clamp_L"]
    z_valley = clamp_w + hh                     # holder's tooth-valley plane in world
    z0 = z_valley + ht                          # holder roll-facing face
    holder = parts["holder"].rotate((0, 180, 0)).rotate((0, 0, alpha)).translate((ring_c[0], ring_c[1], z0))
    A["holder_L"] = holder
    a = np.radians(alpha)
    sx = ring_c[0] - P["holder_L"] * np.sin(a)  # slot centre in world XY
    sy = ring_c[1] + P["holder_L"] * np.cos(a)
    z_plate_mid = z_valley + ht / 2
    cone, _ = g.part_cone()
    z_off = z_plate_mid + ci["z_neck_mid"]      # world z = z_off - z_local
    A["cone_L"] = cone.rotate((180, 0, 0)).translate((sx, sy, z_off))
    cone_top = z_off - ci["z_top"]
    knob = g.part_knob_nut()
    A["axle_knob_L"] = knob.rotate((180, 0, 0)).translate((sx, sy, cone_top))
    A["pivot_knob_L"] = knob.rotate((180, 0, 0)).translate((ring_c[0], ring_c[1], 0))
    # hardware (simple cylinders / hex heads)
    z_head = z0 - P["head_depth"]
    # pivot bolt M10x50: head sits in the holder pocket (floor at z_valley+head_depth), shank goes out through the clamp
    z_hf = z_valley + P["head_depth"]
    head_pivot = extrude(g.hexagon(17.0), 6.4).translate((0, 0, z_hf - 6.4)).rotate((0, 0, alpha)).translate((ring_c[0], ring_c[1], 0))
    A["pivot_bolt_L"] = cyl(5.0, -10.0, z_hf - 6.4 + 0.01, ring_c) + head_pivot
    xs = P["screw_x"]
    # clamp screw (M10x100) with pad + knob; table thickness T
    T = 30.0
    y_table_top = P["arm_lo"] + P["jaw_gap"]
    pad_top = y_table_top - T
    tip = pad_top - 3.0
    pad = g.part_pad()
    # pad local: contact face z=0, boss up to z=15. World: contact face at pad_top, boss pointing down (-Y)
    A["pad_L"] = pad.rotate((90, 0, 0)).translate((xs, pad_top, P["clamp_w"] / 2))
    bolt_len = 100.0
    shaft = extrude(circle(5.0, n=48), bolt_len).rotate((90, 0, 0)).translate((xs, tip, P["clamp_w"] / 2))
    head = extrude(g.hexagon(17.0), 6.4).rotate((90, 0, 0)).translate((xs, tip - bolt_len, P["clamp_w"] / 2))
    A["screw_L"] = shaft + head
    kh = g.part_knob_head()
    # knob: pocket opens on its +z (top) -> world +y; head under-head plane = knob top
    y_uh = tip - bolt_len                         # under-head plane of the clamp bolt
    A["screw_knob_L"] = kh.rotate((-90, 0, 0)).translate((xs, y_uh - 24.0, P["clamp_w"] / 2))
    # ---- mirror to the right side across z = z_mid ----
    z_mid = z_plate_mid + c["spacing"] / 2
    right = {}
    for k, v in list(A.items()):
        right[k.replace("_L", "_R")] = v.mirror((0, 0, 1)).translate((0, 0, 2 * z_mid))
    A.update(right)
    # ---- roll & rod & table ----
    z_end_L = z_plate_mid + (ci["z_neck_mid"] - c["z_ins"])   # roll end plane (left)
    z_end_R = z_end_L + W
    A["roll_film"] = cyl(FILM_OD / 2, z_end_L, z_end_R, (sx, sy)) - cyl(core_id / 2 + CORE_WALL - 0.01, z_end_L - 1, z_end_R + 1, (sx, sy))
    A["roll_core"] = cyl(core_id / 2 + CORE_WALL, z_end_L, z_end_R, (sx, sy)) - cyl(core_id / 2, z_end_L - 1, z_end_R + 1, (sx, sy))
    rod_L = cone_top - ROD_PAST_NUT
    rod_R = 2 * z_mid - rod_L
    A["rod"] = cyl(5.0, rod_L, rod_R, (sx, sy), 48)
    A["table"] = Manifold.cube((1500, T, 700)).translate((P["spine"] + 10.0, y_table_top - T, -300))  # edge clears R9 inner fillet
    return A, dict(c, sx=sx, sy=sy, z_mid=z_mid, z_end_L=z_end_L, z_end_R=z_end_R, rod_len=rod_R - rod_L)


def vol(a, b):
    return (a ^ b).volume()


def main():
    A, info = build_assembly(W, CORE_ID, ALPHA)
    print(f"W={W:.0f}  core ID={CORE_ID:.0f}  alpha={ALPHA:.0f}")
    print(f"  taper insertion      : {info['z_ins']:.1f} mm")
    print(f"  holder plate spacing : {info['spacing']:.1f} mm (mid-plane to mid-plane)")
    print(f"  rod length           : {info['rod_len']:.1f} mm")
    print(f"  slot centre world    : x={info['sx']:.1f} y={info['sy']:.1f}")
    checks = [
        ("clamp_L ^ holder_L", "clamp_L", "holder_L"),
        ("holder_L ^ cone_L", "holder_L", "cone_L"),
        ("clamp_L ^ cone_L", "clamp_L", "cone_L"),
        ("clamp_L ^ axle_knob_L", "clamp_L", "axle_knob_L"),
        ("clamp_L ^ pivot_knob_L", "clamp_L", "pivot_knob_L"),
        ("holder_L ^ pivot_bolt_L (hole free?)", "holder_L", "pivot_bolt_L"),
        ("clamp_L ^ pivot_bolt_L (hole free?)", "clamp_L", "pivot_bolt_L"),
        ("cone_L ^ rod (bore free?)", "cone_L", "rod"),
        ("knob_L ^ rod (bore free?)", "axle_knob_L", "rod"),
        ("roll_core ^ holder_L", "roll_core", "holder_L"),
        ("roll_film ^ holder_L", "roll_film", "holder_L"),
        ("roll_film ^ holder_R", "roll_film", "holder_R"),
        ("roll_core ^ cone_L (taper in core)", "roll_core", "cone_L"),
        ("roll_film ^ clamp_L", "roll_film", "clamp_L"),
        ("roll_film ^ table", "roll_film", "table"),
        ("clamp_L ^ table", "clamp_L", "table"),
        ("clamp_R ^ holder_R", "clamp_R", "holder_R"),
        ("pad_L ^ table (touching only)", "pad_L", "table"),
        ("pad_L ^ clamp_L", "pad_L", "clamp_L"),
        ("screw_L ^ clamp_L (nut hole free?)", "screw_L", "clamp_L"),
        ("screw_knob_L ^ clamp_L", "screw_knob_L", "clamp_L"),
    ]
    print("Interference volumes (mm^3):")
    for label, a, b in checks:
        print(f"  {label:40s} {vol(A[a], A[b]):10.1f}")
    out = trimesh.util.concatenate([to_trimesh(v) for k, v in A.items() if k != "table"])
    out.export(g.HERE + "/assembly_preview.stl")
    return A, info


if __name__ == "__main__":
    main()
