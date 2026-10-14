#!/usr/bin/env python3
"""
v2 virtual assembly + collision + thread-fit checks.  `python assemble.py [W=500] [CORE_ID=38] [ALPHA=0] [TABLE_T=30]`
World: Z = axle, Y up, clamp_L z in [0, clamp_w], table top plane y = arm_lo + jaw_gap. Interference volumes in mm^3.
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
TBL = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
FILM_OD, CORE_WALL, STUB = 130.0, 3.0, 110.0


def cyl(r, z0, z1, c=(0, 0), n=64):
    return extrude(circle(r, c, n), z1 - z0).translate((0, 0, z0))


def build(W, core_id, alpha, T):
    parts, info = g.build_all()
    ci, ring_c = info["cone"], info["ring_c"]
    needed, z_ins, _ = g.axle_needed(W, core_id)
    D_n = ci["z_neck_mid"] - z_ins
    spacing = W + 2 * D_n
    cw, ht = P["clamp_w"], P["holder_t"]
    z_valley = cw + P["teeth_h"] + P["teeth_gap"]
    z0 = z_valley + ht
    A = {}
    A["clamp_L"] = parts["clamp_L"]
    A["holder_L"] = parts["holder"].rotate((0, 180, 0)).rotate((0, 0, alpha)).translate((ring_c[0], ring_c[1], z0))
    a = np.radians(alpha)
    sx, sy = ring_c[0] - P["holder_L"] * np.sin(a), ring_c[1] + P["holder_L"] * np.cos(a)
    z_plate_mid = z_valley + ht / 2
    cone, _ = g.part_cone()
    z_off = z_plate_mid + ci["z_neck_mid"]
    A["cone_L"] = cone.rotate((180, 0, 0)).translate((sx, sy, z_off))
    cone_top = z_off - ci["z_top"]
    A["axle_knob_L"] = parts["knob"].translate((sx, sy, cone_top - P["knob_h"]))
    A["pivot_knob_L"] = parts["knob"].translate((ring_c[0], ring_c[1], -P["knob_h"]))
    # printed clamp nut (hex) in lower-arm pocket, standing 10 mm above the arm
    xs, zc = P["screw_x"], cw / 2
    floor = P["arm_lo"] - P["nut_pocket"]
    A["nut_L"] = parts["clamp_nut"].rotate((-90, 0, 0)).translate((xs, floor, zc))
    # clamp screw: thread top (local z = knob_h-0.3+L) sits at pad bottom
    y_top = P["arm_lo"] + P["jaw_gap"]
    pad_top = y_top - T
    pad_bot = pad_top - P["pad_h"]
    th_top = P["screw_knob_h"] - 0.3 + P["screw_thread_len"]
    A["screw_L"] = parts["clamp_screw"].rotate((-90, 0, 0)).translate((xs, pad_bot - th_top, zc))
    A["pad_L"] = parts["pad"].rotate((90, 0, 0)).translate((xs, pad_top, zc))
    # mirror to the right
    z_mid = z_plate_mid + spacing / 2
    for k in list(A):
        A[k.replace("_L", "_R")] = A[k].mirror((0, 0, 1)).translate((0, 0, 2 * z_mid))
    # roll, axle stubs (real threads) + plain mid section, table
    z_end_L = z_plate_mid + D_n
    z_end_R = z_end_L + W
    A["roll_film"] = cyl(FILM_OD / 2, z_end_L, z_end_R, (sx, sy)) - cyl(core_id / 2 + CORE_WALL - 0.01, z_end_L - 1, z_end_R + 1, (sx, sy))
    A["roll_core"] = cyl(core_id / 2 + CORE_WALL, z_end_L, z_end_R, (sx, sy)) - cyl(core_id / 2, z_end_L - 1, z_end_R + 1, (sx, sy))
    rod_L = cone_top - g.ROD_PAST_KNOB
    rod_R = 2 * z_mid - rod_L
    A["rod_stub_L"] = g.ext_thread(STUB, 2.7, 0).translate((sx, sy, rod_L))
    A["rod_stub_R"] = g.ext_thread(STUB, 2.7, 0).rotate((180, 0, 0)).translate((sx, sy, rod_R))
    A["rod_mid"] = cyl(9.0, rod_L + STUB, rod_R - STUB, (sx, sy), 48)
    A["table"] = Manifold.cube((1500, T, 700)).translate((P["spine"] + 10.0, y_top - T, -300))
    return A, dict(spacing=spacing, rod=rod_R - rod_L, needed=needed, sx=sx, sy=sy, z_ins=z_ins)


def vol(a, b):
    return (a ^ b).volume()


def scan(a, b, centre, axis, step=10):
    """Rotate b about a line through `centre` along `axis` ('x','y','z'); return (min_vol, free_degrees)."""
    best, free = 1e18, 0
    for ang in range(0, 360, step):
        rv = {"x": (ang, 0, 0), "y": (0, ang, 0), "z": (0, 0, ang)}[axis]
        br = b.translate(tuple(-c for c in centre)).rotate(rv).translate(centre)
        v = vol(a, br)
        best = min(best, v)
        free += step if v < 1.0 else 0
    return best, free


def thread_fit(A):
    print("Thread mating: rotate the screwed part through 360 deg; need min interference ~0 (free = degrees of play):")
    cl = P["clamp_w"] / 2
    ring_c = (P["ring_r"], P["arm_lo"] + P["jaw_gap"] + P["arm_up"] + 14.0)
    pairs = [("pivot stud <-> knob   ", A["holder_L"], A["pivot_knob_L"], (ring_c[0], ring_c[1], 0), "z"),
             ("axle rod  <-> knob    ", A["rod_stub_L"], A["axle_knob_L"], (A["_sx"], A["_sy"], 0), "z"),
             ("clamp screw <-> nut   ", A["screw_L"], A["nut_L"], (P["screw_x"], 0, cl), "y")]
    for label, x, y, c, ax in pairs:
        mn, free = scan(x, y, c, ax)
        print(f"  {label} min interference {mn:7.2f} mm^3, free rotation window {free:3d} deg")


def main():
    A, info = build(W, CORE_ID, ALPHA, TBL)
    A["_sx"], A["_sy"] = info["sx"], info["sy"]
    thread_fit(A)
    del A["_sx"], A["_sy"]
    print(f"\nW={W:.0f} ID={CORE_ID:.0f} alpha={ALPHA:.0f} table T={TBL:.0f}: spacing {info['spacing']:.1f}, "
          f"rod needed {info['needed']:.1f}, slot centre x={info['sx']:.1f} y={info['sy']:.1f}")
    checks = [("clamp_L ^ holder_L", "clamp_L", "holder_L"), ("holder_L ^ cone_L", "holder_L", "cone_L"),
              ("clamp_L ^ cone_L", "clamp_L", "cone_L"), ("clamp_L ^ axle_knob_L", "clamp_L", "axle_knob_L"),
              ("clamp_L ^ pivot_knob_L", "clamp_L", "pivot_knob_L"), ("holder_L(stud) ^ pivot_knob_L", "holder_L", "pivot_knob_L"),
              ("cone_L ^ rod_stub_L", "cone_L", "rod_stub_L"), ("axle_knob_L ^ rod_stub_L", "axle_knob_L", "rod_stub_L"),
              ("axle_knob_L ^ cone_L", "axle_knob_L", "cone_L"),
              ("nut_L ^ clamp_L", "nut_L", "clamp_L"), ("screw_L ^ nut_L (thread mesh)", "screw_L", "nut_L"),
              ("screw_L ^ clamp_L", "screw_L", "clamp_L"), ("pad_L ^ screw_L (swivel head)", "pad_L", "screw_L"),
              ("pad_L ^ clamp_L", "pad_L", "clamp_L"), ("pad_L ^ table", "pad_L", "table"), ("screw_L ^ table", "screw_L", "table"),
              ("roll_core ^ holder_L", "roll_core", "holder_L"), ("roll_film ^ holder_R", "roll_film", "holder_R"),
              ("roll_film ^ clamp_L", "roll_film", "clamp_L"), ("roll_film ^ table", "roll_film", "table"),
              ("roll_core ^ cone_L", "roll_core", "cone_L"), ("clamp_L ^ table", "clamp_L", "table"),
              ("clamp_R ^ holder_R", "clamp_R", "holder_R"), ("holder_R ^ cone_R", "holder_R", "cone_R"),
              ("axle_knob_R ^ rod_stub_R", "axle_knob_R", "rod_stub_R"), ("screw_R ^ nut_R", "screw_R", "nut_R")]
    for label, a, b in checks:
        print(f"  {label:36s} {vol(A[a], A[b]):10.2f}")
    out = trimesh.util.concatenate([to_trimesh(v) for k, v in A.items() if k != "table"])
    out.export(g.HERE + "/assembly_preview.stl")
    return A, info


if __name__ == "__main__":
    main()
