#!/usr/bin/env python3
"""
v2 calculator.  `python calc.py [FILM_WIDTH_mm] [CORE_ID_mm]`  (no args = table of common sizes)
Outputs per roll: how many printed axle pieces (rod_long / rod_short / coupler) to print, and where to put holders.
  NEED   = minimal axle length (ends stick 17 mm out of the cone tops => ~3 thread turns inside each knob)
  PIECES = n x rod_long + m x rod_short, (n+m-1) couplers; total length >= NEED, excess is harmless (centre it)
  SPACING= distance between the two holder plate MID-planes along the axle; GAP = clear gap between plate inner faces
  EDGE   = minimum straight table-edge length for both clamps
To print the axle plate for a given roll:  python generate.py FILM_WIDTH CORE_ID   (writes 3mf/plate4_axle.3mf)
"""
import sys
import generate as g

P = g.P


def compute(width, core_id):
    need, z_ins, ci = g.axle_needed(width, core_id)
    plan = g.plan_axle(need)
    spacing = width + 2 * (ci["z_neck_mid"] - z_ins)
    edge = spacing + 2 * (P["clamp_w"] + P["teeth_h"] + P["teeth_gap"] + P["holder_t"] / 2)
    return dict(width=width, core_id=core_id, need=need, plan=plan, spacing=spacing, gap=spacing - P["holder_t"], edge=edge)


def main():
    if len(sys.argv) >= 2:
        rows = [(float(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 50.0)]
    else:
        rows = [(w, i) for w in (300, 360, 400, 450, 500) for i in (38, 50)]
    print(f"{'W':>4} {'ID':>3} | {'NEED':>5} | {'rod_200':>7} {'rod_120':>7} {'coupler':>7} {'total':>5} | {'SPACING':>7} {'GAP':>6} {'EDGE':>5}")
    for w, i in rows:
        r = compute(w, i)
        p = r["plan"]
        print(f"{w:4.0f} {i:3.0f} | {r['need']:5.0f} | {p['n_long']:7d} {p['n_short']:7d} {p['couplers']:7d} {p['total']:5.0f} | "
              f"{r['spacing']:7.1f} {r['gap']:6.1f} {r['edge']:5.0f}")


if __name__ == "__main__":
    main()
