#!/usr/bin/env python3
"""
v3 build: writes stl/ (NEW parts only), 3mf/Stretch_Dispenser_Spindle_A1_PETG.3mf (FULL set, 3 plates) and
3mf/NEW_parts_only_A1_PETG.3mf (carrier x2, spindle x2, cone_v3 x2: for people who already printed v2 clamps/holders/screws/nuts/pads/knobs).
`python build.py [light|strong]`   (no film width needed: there is no axle; spacing from `python plan.py W ID`)
"""
import os
import numpy as np
import parts as v3
from parts import g, P, V

HERE = os.path.dirname(os.path.abspath(__file__))
sys_path_v2 = os.path.abspath(os.path.join(HERE, "..", "v2_all_printed"))
import sys
sys.path.insert(0, sys_path_v2)
import bambu_project

PROFILE = sys.argv[1] if len(sys.argv) > 1 else g.PROFILE          # light (default) | strong
SET = g.print_settings(PROFILE)


def main():
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "3mf", "plain"), exist_ok=True)
    base, _ = g.build_all()
    new = v3.build_new()
    tms = {k: g.to_trimesh(mf) for k, mf in {**{k: base[k] for k in ("clamp_L", "clamp_R", "clamp_nut", "clamp_screw", "pad", "holder", "knob")}, **new}.items()}
    for k in new:
        tms[k].export(os.path.join(HERE, "stl", f"{k}.stl"))
    for k, t in tms.items():
        print(f"{k:12s} size {np.round(t.extents, 1)}  vol {t.volume/1000:6.1f} cm3  watertight={t.is_watertight}")
    plates = [
        ("1 Clamps", [("clamp_L", "clamp_L"), ("clamp_R", "clamp_R")]),
        ("2 Holders + carriers + cones", [("holder_1", "holder"), ("holder_2", "holder"), ("carrier_1", "carrier"), ("carrier_2", "carrier"),
                                          ("cone_1", "cone_v3"), ("cone_2", "cone_v3")]),
        ("3 Screws, nuts, pads, knobs, spindles", [("clamp_screw_1", "clamp_screw"), ("clamp_screw_2", "clamp_screw"),
                                                   ("clamp_nut_1", "clamp_nut"), ("clamp_nut_2", "clamp_nut"), ("pad_1", "pad"), ("pad_2", "pad"),
                                                   ("pivot_knob_1", "knob"), ("pivot_knob_2", "knob"), ("spindle_1", "spindle"), ("spindle_2", "spindle")]),
    ]
    new_only = [("NEW parts only (v3)", [("carrier_1", "carrier"), ("carrier_2", "carrier"), ("spindle_1", "spindle"), ("spindle_2", "spindle"),
                                         ("cone_1", "cone_v3"), ("cone_2", "cone_v3")])]

    def project(plate_defs, out, plain_prefix):
        pp = []
        for i, (title, items) in enumerate(plate_defs):
            placed = g.shelf_pack([(n, tms[s]) for n, s in items], P["bed"], P["gap"])
            g.write_3mf(os.path.join(HERE, "3mf", "plain", f"{plain_prefix}{i + 1}.3mf"), placed)
            src = dict(items)
            pp.append(dict(name=title, items=[dict(name=n, mesh=t, settings=SET[src[n]]) for n, t in placed]))
            b = np.array([t.bounds for _, t in placed])
            print(f"  plate '{title}': {len(placed)} objs, Hmax {b[:, 1, 2].max():.0f}")
        bambu_project.write_project(out, pp)
        print("wrote", out)

    project(plates, os.path.join(HERE, "3mf", "Stretch_Dispenser_Spindle_A1_PETG.3mf"), "plate")
    project(new_only, os.path.join(HERE, "3mf", "NEW_parts_only_A1_PETG.3mf"), "new_only")


if __name__ == "__main__":
    main()
