#!/usr/bin/env python3
"""
v3 spacing calculator. `python plan.py [FILM_WIDTH] [CORE_ID]` (no args = table). No axle, no sections: only where to put the clamps.
  S_min/S_rec/S_max = distance between the two holder-plate MID planes along the roll axis (spindles fully retracted / recommended / fully advanced)
  S_rec = S_min + 32 (sigma = 16 mm): with spindles fully retracted the pins stick out 13.8 mm, so the roll with both cones drops in from above
  only if sigma >= 14. Anything in S_min..S_max works for a roll that is already on one pin; the spindles take up the difference.
  EDGE = minimum straight table-edge length for both clamps at S_rec.
"""
import sys
import parts as v3
from parts import g, P, V


def compute(W, ID):
    z_ins = g.cone_insertion(ID)
    base = V["car_neck"] / 2 + V["car_inner"] + V["cone_total"] - z_ins          # plate mid -> roll end at sigma = 0
    smin, smax = W + 2 * base, W + 2 * (base + V["travel"])
    srec = smin + 32.0
    edge = srec + 2 * (P["clamp_w"] + P["teeth_h"] + P["teeth_gap"] + P["holder_t"] / 2)
    return dict(W=W, ID=ID, smin=smin, srec=srec, smax=smax, edge=edge)


def main():
    rows = [(float(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 46.0)] if len(sys.argv) > 1 else \
        [(w, i) for w in (300, 400, 500, 530) for i in (38, 46, 50)]
    print(f"{'W':>4} {'ID':>3} | {'S_min':>6} {'S_rec':>6} {'S_max':>6} | {'EDGE':>5}   (mm; place holders at S_rec (any S_min..S_max works))")
    for w, i in rows:
        r = compute(w, i)
        print(f"{w:4.0f} {i:3.0f} | {r['smin']:6.1f} {r['srec']:6.1f} {r['smax']:6.1f} | {r['edge']:5.0f}")


if __name__ == "__main__":
    main()
