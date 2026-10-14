#!/usr/bin/env python3
"""
Calculator: what to cut / how to place for a given film roll.
AI-READABLE: `python calc.py [FILM_WIDTH_mm] [CORE_ID_mm]`  (defaults: table of common widths, ID 38 and 50)
Definitions
  FILM_WIDTH = core length (mm). Roll core is assumed as long as the film is wide.
  ROD        = length of the M10 threaded rod to cut (ends stick 12 mm out of the knobs).
  SPACING    = distance between the two holder plate MID-PLANES along the axle (mm). Plates are 12 mm thick.
  GAP        = clear gap between the INNER faces of the two holder plates = SPACING - 12.
  EDGE_LEN   = minimum straight table-edge length needed for both clamps (clamp 30 + holder 12 + spacing + ...).
Valid core inner diameters: 34..54 mm (taper 32->58 mm). Film OD up to ~140 mm fits over the table at default angle.
"""
import sys
import generate as g

P = g.P
ROD_PAST_NUT = 12.0


def compute(width, core_id):
    cone, ci = g.part_cone()
    z_ins = g.cone_insertion(core_id)
    d_n = ci["z_neck_mid"] - z_ins
    spacing = width + 2 * d_n
    rod = width + 2 * (ci["z_top"] + ROD_PAST_NUT - z_ins)
    gap = spacing - P["holder_t"]
    # clamp (30) + teeth/holder offset (~2.25) + half plate to the plate mid-plane (6), each side
    edge = spacing + 2 * (P["clamp_w"] + P["teeth_h"] + P["teeth_gap"] + P["holder_t"] / 2)
    return dict(width=width, core_id=core_id, taper_depth=round(z_ins, 1), rod=round(rod, 1),
                spacing=round(spacing, 1), gap=round(gap, 1), edge_len=round(edge, 1))


def main():
    if len(sys.argv) >= 2:
        widths = [float(sys.argv[1])]
        ids = [float(sys.argv[2])] if len(sys.argv) >= 3 else [38.0, 50.0]
    else:
        widths = [300, 400, 450, 500]
        ids = [38.0, 50.0]
    print(f"{'W':>5} {'ID':>4} | {'taper depth':>11} {'ROD cut':>8} {'SPACING':>8} {'GAP':>7} {'EDGE_LEN':>9}")
    for w in widths:
        for i in ids:
            r = compute(w, i)
            print(f"{r['width']:5.0f} {r['core_id']:4.0f} | {r['taper_depth']:11.1f} {r['rod']:8.1f} "
                  f"{r['spacing']:8.1f} {r['gap']:7.1f} {r['edge_len']:9.1f}")


if __name__ == "__main__":
    main()
