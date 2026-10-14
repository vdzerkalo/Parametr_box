#!/usr/bin/env python3
"""
Exports the v3 assembly (left end, world coordinates) for the animated guide: assets/parts.json (compact: float32 verts + uint32 faces, base64+zlib)
and assets/layout.json (numbers for the scene). Run from this folder with the project's Python venv: `python export_assets.py`.
"""
import base64, json, os, sys, zlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "v3_spindle"))
import check                               # v3 assembly builder
from parts import g, P, V

W, ID, ALPHA, TABLE_T, SIGMA = 530.0, 46.0, 0.0, 30.0, 16.0
KEEP = 0.3
A, info = check.build(W, ID, ALPHA, TABLE_T, SIGMA)
G = info["G"]
NAMES = ["clamp_L", "holder_L", "carrier_L", "spindle_L", "cone_L", "pivot_knob_L", "nut_L", "screw_L", "pad_L"]
out = {}
tot = 0
for n in NAMES:
    t = g.to_trimesh(A[n])
    t.merge_vertices()
    if len(t.faces) > 5000:                      # video only: ~30 % of the faces keeps threads readable and makes software WebGL ~3x faster
        t = t.simplify_quadric_decimation(face_count=max(3000, int(len(t.faces) * KEEP)))
    v = np.asarray(t.vertices, dtype=np.float32)
    f = np.asarray(t.faces, dtype=np.uint32)
    blob = zlib.compress(v.tobytes() + f.tobytes(), 9)
    out[n] = dict(nv=len(v), nf=len(f), data=base64.b64encode(blob).decode())
    tot += len(blob)
    print(f"{n:13s} verts {len(v):6d} faces {len(f):6d} compressed {len(blob)/1024:7.1f} KiB")
os.makedirs(os.path.join(HERE, "assets"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "assets", "parts.json"), "w"))
lay = dict(W=W, ID=ID, sx=info["sx"], sy=info["sy"], z_pm=G["z_pm"], z_re=G["z_re"], z_mid=G["z_pm"] + info["S"] / 2, S=info["S"],
           z_inner=G["z_inner"], z_outer=G["z_outer"], z_cb=G["z_cb"], ring=list(info["ring_c"]), screw_x=P["screw_x"], clamp_w=P["clamp_w"],
           arm_lo=P["arm_lo"], jaw_gap=P["jaw_gap"], table_t=TABLE_T, film_od=check.FILM_OD, core_wall=check.CORE_WALL,
           z_valley=G["z_valley"], nut_h=P["nut_h"], nut_pocket=P["nut_pocket"], spindle_len=V["knob_h"] - 0.3 + V["spindle_thread"] + V["pin_len"])
json.dump(lay, open(os.path.join(HERE, "assets", "layout.json"), "w"), indent=1)
print("total compressed", round(tot / 1024), "KiB"); print(lay)
