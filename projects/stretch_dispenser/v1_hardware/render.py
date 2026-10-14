#!/usr/bin/env python3
"""
Tiny orthographic painter's-algorithm renderer (matplotlib PolyCollection) for previews.
AI-READABLE: `python render.py` -> preview/assembly_iso.png, assembly_zoom.png, assembly_front.png, parts_sheet.png
"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import generate as g
import assemble as asm

COL = {
    "clamp": "#2f3640", "holder": "#2f3640", "cone": "#f1c40f", "knob": "#f39c12", "pad": "#7f8c8d",
    "rod": "#bdc3c7", "bolt": "#95a5a6", "screw": "#95a5a6", "roll_film": "#dfe9f3", "roll_core": "#a98467",
    "table": "#c8a97e", "bed": "#d9c7a8",
}


def color_for(name):
    for k, v in COL.items():
        if name.startswith(k):
            return v
    return "#999999"


def rot(az, el):
    a, e = np.radians(az), np.radians(el)
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    return Rx @ Rz


def render(items, path, az=-35, el=25, size=(1600, 1000), crop=None, zup=False, title=None):
    """items: list of (name, trimesh). World Y is up, so remap to Z-up for viewing."""
    R = rot(az, el)
    light = np.array([0.4, -0.5, 0.8])
    light /= np.linalg.norm(light)
    polys, cols, depth = [], [], []
    for name, tm in items:
        v = np.asarray(tm.vertices)
        if not zup:  # world: Y up, Z axle -> view: X=x, Y=z(depth), Z=y(up)
            v = np.column_stack([v[:, 0], v[:, 2], v[:, 1]])
        vr = v @ R.T
        f = np.asarray(tm.faces)
        tri = vr[f]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        nn = np.linalg.norm(n, axis=1, keepdims=True)
        nn[nn == 0] = 1
        n = n / nn
        facing = n[:, 1] < 0.0    # camera looks along +Y in view space
        shade = np.clip(n @ light, -1, 1) * 0.5 + 0.55
        base = np.array(matplotlib.colors.to_rgb(color_for(name)))
        c = np.clip(base[None, :] * shade[:, None], 0, 1)
        sel = facing
        polys.append(tri[sel][:, :, [0, 2]])
        cols.append(c[sel])
        d = tri[sel][:, :, 1].mean(axis=1)
        if name == "bed":
            d = d + 1e6          # far away: painted first, parts always on top
        depth.append(d)
    polys = np.concatenate(polys)
    cols = np.concatenate(cols)
    depth = np.concatenate(depth)
    order = np.argsort(-depth)
    fig = plt.figure(figsize=(size[0] / 100, size[1] / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    pc = PolyCollection(polys[order], facecolors=cols[order], edgecolors=cols[order], linewidths=0.15)
    ax.add_collection(pc)
    allp = polys.reshape(-1, 2)
    lo, hi = allp.min(0), allp.max(0)
    if crop is not None:
        lo, hi = np.array(crop[:2]), np.array(crop[2:])
    pad = 0.04 * (hi - lo).max()
    ax.set_xlim(lo[0] - pad, hi[0] + pad)
    ax.set_ylim(lo[1] - pad, hi[1] + pad)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")
    if title:
        ax.text(0.01, 0.98, title, transform=ax.transAxes, va="top", fontsize=13, color="#222")
    fig.savefig(path, dpi=100)
    plt.close(fig)


def main():
    import trimesh
    from manifold3d import Manifold
    W = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    A, info = asm.build_assembly(W, 38.0, 0.0)
    # visual table slab (short, so the camera frames the dispenser)
    T, y_top = 30.0, g.P["arm_lo"] + g.P["jaw_gap"]
    A["table"] = Manifold.cube((260, T, W + 400)).translate((g.P["spine"] + 10.0, y_top - T, -200))
    items = [(k, g.to_trimesh(v)) for k, v in A.items()]
    out = g.HERE + "/preview/"
    render(items, out + "assembly_iso.png", az=-38, el=22, title=f"Full assembly, film width {W:.0f} mm, core ID 38")
    left = [(k, t) for k, t in items if not k.endswith("_R") and k not in ("roll_film", "roll_core", "table")]
    render(left, out + "assembly_zoom.png", az=-40, el=22, size=(1400, 1100),
           title="Left end: clamp + 15-deg pivot + holder + cone hub + knobs")
    front = [(k, t) for k, t in items if k in ("clamp_L", "holder_L", "cone_L", "axle_knob_L", "pivot_knob_L", "pad_L",
                                                "screw_L", "screw_knob_L", "table", "roll_film", "roll_core")]
    render(front, out + "assembly_side.png", az=0, el=0, size=(1100, 1100), crop=(-60, -80, 290, 270),
           title="View along the axle (30 mm table top)")


def plates():
    import glob
    import trimesh
    for f in sorted(glob.glob(g.HERE + "/3mf/*.3mf")):
        sc = trimesh.load(f)
        items = []
        for i, (name, geom) in enumerate(sc.geometry.items()):
            items.append((name, geom))
        # add bed outline as a thin plate for scale (256 x 256)
        bed = trimesh.creation.box(extents=(256, 256, 1.0))
        bed.apply_translation((128, 128, -0.5))
        items.append(("bed", bed))
        base = f.split("/")[-1].replace(".3mf", "")
        render(items, g.HERE + f"/preview/{base}.png", az=-25, el=40, size=(1200, 900), zup=True,
               title=base.replace("_", " ") + "  (Bambu A1 plate 256x256, print orientation)")


if __name__ == "__main__":
    main()
    plates()
