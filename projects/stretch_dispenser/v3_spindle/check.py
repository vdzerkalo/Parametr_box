#!/usr/bin/env python3
"""
v3 virtual assembly + collision + thread-fit checks.  `python check.py [W=530] [CORE_ID=46]`
World (same as v2): Z = roll axis, Y up, clamp_L z in [0, clamp_w], table top plane y = arm_lo + jaw_gap. Volumes in mm^3.
Sweeps: spindle position sigma (cone back-face standoff from carrier inner face) 0..travel, holder angles, table thickness.
"""
import sys
import numpy as np
from manifold3d import Manifold
import parts as v3
from parts import g, P, V

FILM_OD, CORE_WALL = 130.0, 3.0
GEN = {}


def cyl(r, z0, z1, c=(0, 0), n=64):
    return g.extrude(g.circle(r, c, n), z1 - z0).translate((0, 0, z0))


def base_parts():
    if not GEN:
        p, info = g.build_all()
        GEN.update(p=p, info=info, new=v3.build_new())
    return GEN["p"], GEN["info"], GEN["new"]


def geometry(core_id, alpha, sigma):
    p, info, new = base_parts()
    ring_c = info["ring_c"]
    z_ins = g.cone_insertion(core_id)
    ht = P["holder_t"]
    z_valley = P["clamp_w"] + P["teeth_h"] + P["teeth_gap"]
    z_pm = z_valley + ht / 2
    a = np.radians(alpha)
    sx, sy = ring_c[0] - P["holder_L"] * np.sin(a), ring_c[1] + P["holder_L"] * np.cos(a)
    z_inner = z_pm + V["car_neck"] / 2 + V["car_inner"]              # carrier inner flange face
    z_outer = z_pm - V["car_neck"] / 2 - V["car_flare"] - V["car_cyl"]
    z_cb = z_inner + sigma                                             # cone back face
    z_re = z_cb + V["cone_total"] - z_ins                              # roll end face (left)
    return dict(ring_c=ring_c, z_ins=z_ins, z_valley=z_valley, z_pm=z_pm, sx=sx, sy=sy, z_inner=z_inner, z_outer=z_outer,
                z_cb=z_cb, z_re=z_re, spacing=0.0, a=alpha)


def build(W, core_id, alpha, T, sigma):
    p, info, new = base_parts()
    G = geometry(core_id, alpha, sigma)
    ring_c, sx, sy, z_pm = G["ring_c"], G["sx"], G["sy"], G["z_pm"]
    S = W + 2 * (G["z_re"] - z_pm)
    z0 = G["z_valley"] + P["holder_t"]
    A = {"clamp_L": p["clamp_L"]}
    A["holder_L"] = p["holder"].rotate((0, 180, 0)).rotate((0, 0, alpha)).translate((ring_c[0], ring_c[1], z0))
    A["pivot_knob_L"] = p["knob"].translate((ring_c[0], ring_c[1], -P["knob_h"]))
    A["carrier_L"] = new["carrier"].rotate((0, 180, 0)).rotate((0, 0, alpha)).translate((sx, sy, G["z_inner"]))
    z_pin = G["z_cb"] + V["seat_contact"]
    z_sp = z_pin - v3.pin_tip_local_z()
    A["spindle_L"] = new["spindle"].translate((sx, sy, z_sp))
    dk = G["z_outer"] - (z_sp + V["knob_h"])
    A["cone_L"] = new["cone_v3"].rotate((180, 0, 0)).translate((sx, sy, G["z_cb"] + V["cone_total"]))
    xs, zc = P["screw_x"], P["clamp_w"] / 2
    floor = P["arm_lo"] - P["nut_pocket"]
    A["nut_L"] = p["clamp_nut"].rotate((-90, 0, 0)).translate((xs, floor, zc))
    y_top = P["arm_lo"] + P["jaw_gap"]
    pad_top = y_top - T
    pad_bot = pad_top - P["pad_h"]
    th_top = P["screw_knob_h"] - 0.3 + P["screw_thread_len"]
    A["screw_L"] = p["clamp_screw"].rotate((-90, 0, 0)).translate((xs, pad_bot - th_top, zc))
    A["pad_L"] = p["pad"].rotate((90, 0, 0)).translate((xs, pad_top, zc))
    z_mid = z_pm + S / 2
    for k in list(A):
        A[k.replace("_L", "_R")] = A[k].mirror((0, 0, 1)).translate((0, 0, 2 * z_mid))
    z_end_R = G["z_re"] + W
    A["roll_film"] = cyl(FILM_OD / 2, G["z_re"], z_end_R, (sx, sy)) - cyl(core_id / 2 + CORE_WALL - 0.01, G["z_re"] - 1, z_end_R + 1, (sx, sy))
    A["roll_core"] = cyl(core_id / 2 + CORE_WALL, G["z_re"], z_end_R, (sx, sy)) - cyl(core_id / 2, G["z_re"] - 1, z_end_R + 1, (sx, sy))
    A["table"] = Manifold.cube((1500, T, 700)).translate((P["spine"] + 10.0, y_top - T, -300))
    return A, dict(S=S, dk=dk, sx=sx, sy=sy, ring_c=ring_c, G=G)


def vol(a, b):
    return (a ^ b).volume()


def scan(a, b, centre, axis, step=10):
    best, free = 1e18, 0
    for ang in range(0, 360, step):
        rv = {"x": (ang, 0, 0), "y": (0, ang, 0), "z": (0, 0, ang)}[axis]
        br = b.translate(tuple(-c for c in centre)).rotate(rv).translate(centre)
        v = vol(a, br)
        best, free = min(best, v), free + (step if v < 1.0 else 0)
    return best, free


SOLID = [("clamp_L", "holder_L"), ("clamp_L", "carrier_L"), ("clamp_L", "spindle_L"), ("clamp_L", "cone_L"), ("clamp_L", "pivot_knob_L"),
         ("holder_L", "carrier_L"), ("holder_L", "spindle_L"), ("holder_L", "cone_L"), ("carrier_L", "cone_L"),
         ("spindle_L", "cone_L"), ("cone_L", "roll_core"), ("carrier_L", "roll_core"), ("carrier_L", "roll_film"),
         ("holder_L", "roll_core"), ("holder_L", "roll_film"), ("spindle_L", "roll_core"),
         ("roll_film", "holder_R"), ("roll_film", "clamp_L"), ("roll_film", "clamp_R"), ("roll_film", "table"),
         ("nut_L", "clamp_L"), ("screw_L", "clamp_L"), ("pad_L", "clamp_L"), ("pad_L", "table"), ("screw_L", "table"),
         ("clamp_L", "table"), ("pad_L", "screw_L"),
         ("clamp_R", "holder_R"), ("clamp_R", "spindle_R"), ("clamp_R", "carrier_R"), ("clamp_R", "cone_R"),
         ("holder_R", "carrier_R"), ("holder_R", "cone_R"), ("holder_R", "spindle_R"), ("cone_R", "roll_core"), ("spindle_R", "cone_R")]
THREADS = [("holder_L", "pivot_knob_L"), ("screw_L", "nut_L"), ("carrier_L", "spindle_L")]


def main():
    W = float(sys.argv[1]) if len(sys.argv) > 1 else 530.0
    ID = float(sys.argv[2]) if len(sys.argv) > 2 else 46.0
    worst = 0.0
    print(f"W={W:.0f} ID={ID:.0f}  travel={V['travel']:.0f} mm  carrier thread {V['car_th']:.0f} mm  spindle thread {V['spindle_thread']:.0f} mm")
    for sigma in (0.0, V["travel"] / 2, V["travel"]):
        for alpha, T in ((0, 30), (15, 5), (-30, 60), (45, 30)):
            A, info = build(W, ID, alpha, T, sigma)
            res = {f"{a} ^ {b}": vol(A[a], A[b]) for a, b in SOLID}
            bad = {k: v for k, v in res.items() if v > 1.0}
            worst = max(worst, max(res.values()))
            print(f"sigma={sigma:4.1f} (knob gap Dk={info['dk']:5.1f}) alpha={alpha:4d} table={T:2d} spacing={info['S']:6.1f} "
                  f"max solid interference {max(res.values()):7.2f}  {bad if bad else ''}")
    A, info = build(W, ID, 0, 30, V["travel"] / 2)
    sx, sy = info["sx"], info["sy"]
    cl, rc = P["clamp_w"] / 2, info["ring_c"]
    print("Thread mating (rotate through 360 deg; need min ~0):")
    for (a, b), c, ax in zip(THREADS, [(rc[0], rc[1], 0), (P["screw_x"], 0, cl), (sx, sy, 0)], ["z", "y", "z"]):
        mn, free = scan(A[a], A[b], c, ax)
        print(f"  {a:9s} <-> {b:12s} min {mn:7.2f} mm^3, free window {free:3d} deg")
    print(f"worst solid interference over sweep: {worst:.2f} mm^3")


if __name__ == "__main__":
    main()
