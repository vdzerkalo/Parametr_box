#!/usr/bin/env python3
"""
v3 SPINDLE: new parts only. Everything else (clamp, holder, nut, screw, pad, pivot knob) is imported unchanged from ../v2_all_printed/generate.py.

AI-READABLE CONCEPT
  v2 had one long axle through the roll (segments + couplers). v3 has NO axle: each holder carries a short stationary spindle
  (a "dead centre" like a lathe tailstock) that pushes a cone into the roll core. The roll + two cones turn freely on the spindle pins.
  carrier : sits in the v2 holder U-slot instead of the v2 cone neck; stadium-shaped neck (anti-rotation) + 2 flanges + internal T20 thread
  spindle : knob + T20 thread + small smooth PIN (d9) with dome. Turned only to adjust (travel 24 mm = 4 turns); never turns with the roll
  cone_v3 : v2 cone but solid, with a blind seat (countersink + d9.8 hole) for the pin. Pin-seat torque arm is tiny (r~4 mm), so the roll
            cannot back-drive the spindle thread (needs mu*r_pin < r_m*tan(phi-lambda): 0.3*4.5=1.35 < 2.8 mm)
  Holder-to-holder spacing = W + 2*(carrier inner face + sigma + cone_len - z_ins); sigma in [0, travel] is set by the spindle => +-12 mm tolerance.
"""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "v2_all_printed"))
import generate as g                                   # v2 module (parts, thread, helpers)
from generate import P, extrude, revolve, circle
from shapely.geometry import box
from shapely.ops import unary_union

V3 = dict(
    # carrier (print: inner flange on bed, outer flange chamfered on top; axis = thread axis)
    car_inner=5.0, car_neck=13.0, car_flare=8.0, car_cyl=3.0, car_hw=15.5, car_straight=14.0,
    # spindle
    travel=24.0, pin_r=4.5, pin_len=14.0, knob_r=24.0, knob_h=20.0,
    # cone_v3 seat
    cone_len=36.0, cone_rim=6.0, seat_r=4.9, seat_depth=15.0, seat_entry_r=11.0,   # seat = 90deg countersink cone, apex at seat_depth
    pin_tip_r=1.5,       # pin = d9 cylinder + 60deg point ending in a flat r1.5: touches the 90deg seat on a r1.5 circle (tiny friction radius)
)
V = V3
V["car_th"] = V["car_inner"] + V["car_neck"] + V["car_flare"] + V["car_cyl"]          # 29: thread length inside carrier
V["spindle_thread"] = V["travel"] + V["car_th"] + 1.0                                  # 54
V["cone_total"] = V["cone_len"] + V["cone_rim"]                                        # 42
V["seat_contact"] = V["seat_depth"] - V["pin_tip_r"]                                # depth (from cone back face) where the pin tip rests


def stadium(hw, ell):
    return unary_union([circle(hw), circle(hw, (0, ell)), box(-hw, 0, hw, ell)])


def part_carrier():
    z, v = 0.0, V
    body = extrude(stadium(v["car_hw"] + v["car_flare"], v["car_straight"]), v["car_inner"])
    z = v["car_inner"]
    body = body + extrude(stadium(v["car_hw"], v["car_straight"]), v["car_neck"] + 0.02).translate((0, 0, z - 0.01))
    z += v["car_neck"]
    n = 16
    for k in range(n):
        o = v["car_flare"] * (k + 1) / n
        body = body + extrude(stadium(v["car_hw"] + o, v["car_straight"]), v["car_flare"] / n + 0.02).translate((0, 0, z + k * v["car_flare"] / n - 0.01))
    z += v["car_flare"]
    body = body + extrude(stadium(v["car_hw"] + v["car_flare"], v["car_straight"]), v["car_cyl"]).translate((0, 0, z))
    return body - g.int_void(v["car_th"])


def part_spindle():
    v = V
    knob = extrude(g._scalloped(v["knob_r"], 6, 7.5, v["knob_r"] + 3.5), v["knob_h"])
    z0 = v["knob_h"]
    thread = g.ext_thread(v["spindle_thread"], 0.0, 2.7).translate((0, 0, z0 - 0.3))
    top = z0 - 0.3 + v["spindle_thread"]
    r, L = v["pin_r"], v["pin_len"]
    tr = v["pin_tip_r"]
    tl = (r - tr) / np.tan(np.radians(30.0))
    pin = revolve([(0, top - 0.5), (r, top - 0.5), (r, top + L - tl), (tr, top + L), (0, top + L)])
    return knob + thread + pin


def part_cone_v3():
    v = V
    T = v["cone_total"]
    outer = revolve([(0, 0), (P["cone_r_tip"], 0), (P["cone_r_max"], v["cone_len"]), (P["cone_r_max"], T), (0, T)])
    sr, sd, er = v["seat_r"], v["seat_depth"], v["seat_entry_r"]
    ent = er - sr
    seat = revolve([(0, T - sd), (sr, T - sd + sr), (sr, T - ent), (er + 0.01, T + 0.01), (0, T + 0.01)])   # CCW in (r,z)
    return outer - seat


def pin_tip_local_z():
    return V["knob_h"] - 0.3 + V["spindle_thread"] + V["pin_len"]


def build_new():
    return dict(carrier=part_carrier(), spindle=part_spindle(), cone_v3=part_cone_v3())


if __name__ == "__main__":
    for k, mf in build_new().items():
        t = g.to_trimesh(mf)
        print(f"{k:9s} size {np.round(t.extents, 1)} vol {t.volume/1000:6.1f} cm3 watertight={t.is_watertight}")
