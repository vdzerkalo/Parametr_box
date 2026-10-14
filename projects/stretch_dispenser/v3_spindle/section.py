#!/usr/bin/env python3
"""Cross-section picture of the LEFT end of the v3 assembly (plane through the roll axis). `python section.py [sigma=12] [alpha=0] [ID=46]` -> preview/section_left.png"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import check
from parts import g, V

sigma = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
alpha = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
ID = float(sys.argv[3]) if len(sys.argv) > 3 else 46.0
A, info = check.build(530.0, ID, alpha, 30, sigma)
sx = info["sx"]
colors = dict(holder_L="#8a8a8a", carrier_L="#2a9d8f", spindle_L="#e76f51", cone_L="#e9c46a", roll_core="#b08968", clamp_L="#bbbbbb")
fig, ax = plt.subplots(figsize=(11, 7))
for name, col in colors.items():
    t = g.to_trimesh(A[name])
    sec = t.section(plane_origin=[sx, 0, 0], plane_normal=[1, 0, 0])
    if sec is None:
        continue
    for ent in sec.discrete:
        ax.fill(ent[:, 2], ent[:, 1], color=col, alpha=0.9, lw=0.6, ec="k", label=name if name not in ax.get_legend_handles_labels()[1] else None)
G = info["G"]
ax.axhline(info["sy"], color="k", lw=0.5, ls="--")
ax.set_xlim(G["z_outer"] - 30, G["z_re"] + 40)
ax.set_ylim(info["sy"] - 70, info["sy"] + 50)
ax.set_aspect("equal"); ax.legend(loc="upper right")
ax.set_xlabel("z, mm (outer -> roll)"); ax.set_ylabel("y, mm")
ax.set_title(f"v3 left end, sigma={sigma:.0f} mm, holder angle {alpha:.0f} deg, core ID {ID:.0f}")
fig.savefig("preview/section_left.png", dpi=110, bbox_inches="tight")
print("saved preview/section_left.png")
