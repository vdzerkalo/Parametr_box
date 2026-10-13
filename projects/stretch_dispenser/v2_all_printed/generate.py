#!/usr/bin/env python3
"""
v2 ALL-PRINTED: clamp-mounted stretch-film dispenser. NO hardware (no bolts, nuts, rods). Bambu Lab A1, PETG.

AI-READABLE SUMMARY
  Run:     python generate.py [FILM_WIDTH_mm=530] [CORE_ID_mm=46] [PROFILE=light|strong]   (defaults = owner's roll; 46 = worst case of a 50 mm tube, covers ID 46..54)   -> stl/, 3mf/ (plate4 depends on width/ID)
  Deps:    manifold3d shapely numpy trimesh
  Units:   mm. All STL are in PRINT ORIENTATION (z=0 = bed). Right-hand thread everywhere (twist +360*h/pitch).
  Thread:  one universal printed thread T20x6 (major 20, pitch 6, 45deg flanks, depth 1.9), internal void =
           external profile + thr_clr radial. Used by: clamp screw, pivot stud, axle rods, knobs, couplers.
  Parts:   clamp_L, clamp_R(mirror) | clamp_nut x2 | clamp_screw x2 | pad x2 | holder(+stud) x2 | cone x2 |
           knob x4 (2 pivot + 2 axle) | rod_<long>/rod_<short>/coupler (count from calc, plate4)
  Axle:    segmented printed threaded rod joined by couplers => any length (printer is only 256 mm tall)
"""
import os
import sys
import zipfile
import numpy as np
import trimesh
import manifold3d as m
from manifold3d import Manifold, CrossSection, FillRule
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))

PARAMS = dict(
    # --- universal printed thread T20x6 ---
    thr_major=20.0, thr_pitch=6.0, thr_depth=1.9, thr_crest=1.0,
    thr_clr=0.35,        # radial clearance of internal thread (FDM, 0.4 nozzle). Loose? -0.1. Tight? +0.1
    # --- clamp C-frame ---
    clamp_w=36.0, spine=20.0, arm_lo=18.0, arm_up=16.0, jaw_gap=86.0, arm_len=92.0,
    screw_x=68.0, ring_r=29.0,
    nut_af=26.0, nut_h=20.0, nut_clr=1.2, nut_pocket=10.0,    # printed nut: hex AF26, pocket AF+1.2, 10 deep
    screw_hole_r=11.0,
    # --- pivot tooth ring (15 deg steps) ---
    teeth_n=24, teeth_h=2.0, teeth_r1=14.0, teeth_r2=27.0, teeth_gap=0.25,
    pivot_bore_r=10.8,
    # --- holder ---
    holder_t=12.0, holder_L=60.0, slot_r=16.0, stud_len=57.0,
    # --- cone hub ---
    cone_r_tip=16.0, cone_r_max=29.0, cone_len=36.0, neck_r=15.5, neck_w=13.0, flare_r=23.5, top_cyl=3.0,
    cone_bore_r=11.2,
    # --- knobs ---
    knob_r=24.0, knob_h=20.0,
    screw_knob_r=28.0, screw_knob_h=24.0, screw_thread_len=110.0,
    # --- pad (swivel on mushroom head) ---
    pad_r=20.0, pad_h=16.0,
    # --- axle ---
    rod_lengths=(60, 80, 100, 120, 150, 180, 200),   # library of axle sections (mm). EDIT to your printer/shelf height (A1 max 256)
    axle_margin=10.0,    # extra axle length on top of the computed need (film width tolerance); excess just sticks out past the knob
    rod_end_min=120,     # the two END sections must be >= this (coupler stays >=75 mm from axle end, outside the cone)
    coupler_od=30.0, coupler_len=44.0,
    # --- plates ---
    bed=250.0, gap=7.0,
)
P = PARAMS
SEG = 96
ROD_PAST_KNOB = 17.0      # rod end sticks this far past the cone top face (= ~3 thread turns inside the knob)


# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def _rings(poly):
    out = [np.array(poly.exterior.coords[:-1], dtype=float)]
    for i in poly.interiors:
        out.append(np.array(i.coords[:-1], dtype=float))
    return out


def extrude(geom, h):
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    rings = [r for p in polys for r in _rings(p)]
    return Manifold.extrude(CrossSection(rings, fillrule=FillRule.EvenOdd), h)


def revolve(profile, segs=SEG):
    return Manifold.revolve(CrossSection([np.array(profile, dtype=float)]), segs)


def circle(r, c=(0, 0), n=SEG):
    return Point(*c).buffer(r, quad_segs=n // 4)


def hexagon(af):
    R = af / np.sqrt(3)
    return Polygon([(R * np.cos(np.radians(a)), R * np.sin(np.radians(a))) for a in range(0, 360, 60)])


def closing(g, r):
    return g.buffer(r, quad_segs=16).buffer(-r, quad_segs=16)


def opening(g, r):
    return g.buffer(-r, quad_segs=16).buffer(r, quad_segs=16)


def teardrop(r):
    k = r / np.sqrt(2)
    return unary_union([circle(r, n=48), Polygon([(0, r * np.sqrt(2)), (-k, k), (k, k)])])


def prism_along_y(poly_xz, y0, y1):
    flipped = Polygon([(x, -z) for x, z in poly_xz.exterior.coords[:-1]])
    return extrude(flipped, y1 - y0).rotate((-90, 0, 0)).translate((0, y0, 0))


def teeth_ring(r1, r2, n, h, z0, ridge_deg, base=0.8, mirror_diag=False):
    M = 2 * n
    ang = [np.radians(ridge_deg + k * 180.0 / n) for k in range(M)]
    V = []
    for rr, zz in ((r1, "t"), (r2, "t"), (r1, "b"), (r2, "b")):
        for k in range(M):
            z = z0 + (h if k % 2 == 0 else 0.0) if zz == "t" else z0 - base
            V.append((rr * np.cos(ang[k]), rr * np.sin(ang[k]), z))
    TI, TO = (lambda k: k % M), (lambda k: M + k % M)
    BI, BO = (lambda k: 2 * M + k % M), (lambda k: 3 * M + k % M)
    T = []
    for k in range(M):
        asc = (k % 2 == 1) != mirror_diag
        if asc:
            T += [(TI(k), TO(k), TO(k + 1)), (TI(k), TO(k + 1), TI(k + 1))]
        else:
            T += [(TI(k), TO(k), TI(k + 1)), (TO(k), TO(k + 1), TI(k + 1))]
        T += [(BI(k), BO(k + 1), BO(k)), (BI(k), BI(k + 1), BO(k + 1))]
        T += [(TO(k), BO(k), BO(k + 1)), (TO(k), BO(k + 1), TO(k + 1))]
        T += [(TI(k), BI(k + 1), BI(k)), (TI(k), TI(k + 1), BI(k + 1))]
    out = Manifold(m.Mesh(vert_properties=np.array(V, dtype=np.float32), tri_verts=np.array(T, dtype=np.uint32)))
    if out.volume() < 0:
        raise RuntimeError("teeth ring inverted")
    return out


def to_trimesh(man):
    mesh = man.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)


# ----------------------------------------------------------------------------
# PRINTED THREAD  T20x6  (polar profile twisted along Z; right-hand)
# ----------------------------------------------------------------------------
def _thread_polygon(extra, n=72):
    p, d, c = P["thr_pitch"], P["thr_depth"], P["thr_crest"]
    r_root = P["thr_major"] / 2 - d + extra
    root_w = p - 2 * d - c
    pts = []
    for i in range(n):
        s = p * i / n
        sc = ((s + p / 2) % p) - p / 2          # root centred at s=0
        r = r_root + min(max(abs(sc) - root_w / 2, 0.0), d)
        phi = 2 * np.pi * s / p
        pts.append((r * np.cos(phi), r * np.sin(phi)))
    return np.array(pts)


def _twisted(h, extra):
    twist = 360.0 * h / P["thr_pitch"]
    ndiv = int(np.ceil(abs(twist) / 10.0))
    return Manifold.extrude(CrossSection([_thread_polygon(extra)], fillrule=FillRule.EvenOdd), h, ndiv, twist)


def ext_thread(h, chamfer_bot=0.0, chamfer_top=0.0):
    """External thread rod z in [0,h]. chamfer_* = 45 deg lead-in size at that end (0 = none)."""
    R = P["thr_major"] / 2 + 0.3
    t = _twisted(h, 0.0)
    cb, ct = chamfer_bot, chamfer_top
    prof = [(0, 0), (R if cb == 0 else R - cb - 0.3, 0)]
    if cb:
        prof.append((R, cb + 0.3))
    if ct:
        prof += [(R, h - ct - 0.3), (R - ct - 0.3, h)]
    else:
        prof.append((R, h))
    prof.append((0, h))
    return t ^ revolve(prof)


def int_void(h, countersink=1.8):
    """Void for an internal thread through a body of height h (z in [0,h]); extended 1 mm beyond both ends.
    Entry cones are 45 deg and run down to below the thread's minor radius, so no horizontal ledge is left."""
    v = _twisted(h + 2, P["thr_clr"]).translate((0, 0, -1))
    r0 = P["thr_major"] / 2 + P["thr_clr"]
    r_min = P["thr_major"] / 2 - P["thr_depth"] + P["thr_clr"] - 0.3
    Rt = r0 + countersink
    dz = Rt - r_min
    cone_lo = revolve([(0, -0.01), (Rt, -0.01), (r_min, dz - 0.01), (0, dz - 0.01)])
    cone_hi = revolve([(0, h - dz + 0.01), (r_min, h - dz + 0.01), (Rt, h + 0.01), (0, h + 0.01)])
    return v + cone_lo + cone_hi


# ----------------------------------------------------------------------------
# PARTS (print orientation)
# ----------------------------------------------------------------------------
def part_clamp():
    p = P
    top_y = p["arm_lo"] + p["jaw_gap"] + p["arm_up"]
    ring_c = (p["ring_r"], top_y + 14.0)
    spine = box(0, 0, p["spine"], top_y)
    lo = box(0, 0, p["arm_len"], p["arm_lo"])
    up = box(0, p["arm_lo"] + p["jaw_gap"], p["arm_len"], top_y)
    head = unary_union([circle(p["ring_r"], ring_c), box(0, top_y - 16, p["spine"], ring_c[1])]).convex_hull
    prof = opening(closing(unary_union([spine, lo, up, head]), 9.0), 3.0)
    prof = prof.difference(circle(p["pivot_bore_r"], ring_c, 64))
    body = extrude(prof, p["clamp_w"])
    ridge0 = 90.0 - 180.0 / p["teeth_n"]
    t = teeth_ring(p["teeth_r1"], p["teeth_r2"], p["teeth_n"], p["teeth_h"], p["clamp_w"], ridge0).translate((ring_c[0], ring_c[1], 0))
    body = body + t
    body = body - extrude(circle(p["pivot_bore_r"], ring_c, 64), p["clamp_w"] + 5).translate((0, 0, -1))
    # screw hole (teardrop, horizontal in print) + hex nut pocket open on the jaw side
    zc, xs = p["clamp_w"] / 2, p["screw_x"]
    floor = p["arm_lo"] - p["nut_pocket"]
    td = teardrop(p["screw_hole_r"])
    body = body - prism_along_y(Polygon([(xs + x, zc + z) for x, z in td.exterior.coords[:-1]]), -1, floor + 1)
    hx = hexagon(p["nut_af"] + p["nut_clr"])
    body = body - prism_along_y(Polygon([(xs + x, zc + y) for x, y in hx.exterior.coords[:-1]]), floor, p["arm_lo"] + 1)
    return body, ring_c


def part_clamp_nut():
    p = P
    return extrude(hexagon(p["nut_af"]), p["nut_h"]) - int_void(p["nut_h"])


def part_clamp_screw():
    """Knob (bottom) + threaded shaft + mushroom head for the swivel pad. Print upright."""
    p = P
    n, sr, off = 8, 9.0, p["screw_knob_r"] + 3.0
    g = circle(p["screw_knob_r"])
    cuts = unary_union([circle(sr, (off * np.cos(2 * np.pi * i / n), off * np.sin(2 * np.pi * i / n)), 48) for i in range(n)])
    knob = extrude(opening(g.difference(cuts), 1.5), p["screw_knob_h"])
    L = p["screw_thread_len"]
    z0 = p["screw_knob_h"]
    thread = ext_thread(L, 0.0, 0.8).translate((0, 0, z0 - 0.3))
    top = z0 - 0.3 + L
    head = revolve([(0, top - 0.5), (5, top - 0.5), (5, top + 5.0), (7.5, top + 7.5), (7.5, top + 10.0), (6.5, top + 11.0), (0, top + 11.0)])
    return knob + thread + head


def part_pad():
    """Swivel pad: keyhole T-slot slides sideways onto the mushroom head. Contact face on the bed."""
    p = P
    r, h = p["pad_r"], p["pad_h"]
    body = revolve([(0, 0), (r - 1.2, 0), (r, 1.2), (r, h - 1.2), (r - 1.2, h), (0, h)])
    key = lambda w: unary_union([circle(w / 2, n=48), box(0, -w / 2, r + 2, w / 2)])
    chan_z0, cav_z0 = h - 4.5, h - 11.5
    body = body - extrude(key(11.0), 4.5 + 1).translate((0, 0, chan_z0))      # channel for the stem (lip zone)
    body = body - extrude(key(16.0), 7.0).translate((0, 0, cav_z0))           # cavity for the mushroom head
    return body


def part_holder():
    p = P
    L, t = p["holder_L"], p["holder_t"]
    outer = unary_union([circle(p["ring_r"], (0, 0)), circle(p["ring_r"], (0, L))]).convex_hull
    sr = p["slot_r"]
    slot = unary_union([circle(sr, (0, L)), Polygon([(-sr, L), (sr, L), (sr + 3.2, L + 36), (-sr - 3.2, L + 36)])])
    body = extrude(opening(outer.difference(slot), 1.5), t)
    body = body + teeth_ring(p["teeth_r1"], p["teeth_r2"], p["teeth_n"], p["teeth_h"], t, 90.0, mirror_diag=True)
    stud = ext_thread(p["stud_len"], 0.0, 2.7).translate((0, 0, t - 0.5))
    return body + stud


def _scalloped(r, n, sc_r, sc_off):
    cuts = unary_union([circle(sc_r, (sc_off * np.cos(2 * np.pi * i / n), sc_off * np.sin(2 * np.pi * i / n)), 48) for i in range(n)])
    return opening(circle(r).difference(cuts), 1.5)


def part_knob():
    p = P
    return extrude(_scalloped(p["knob_r"], 6, 7.5, p["knob_r"] + 3.5), p["knob_h"]) - int_void(p["knob_h"])


def part_cone():
    p = P
    b = p["cone_bore_r"]
    z1 = p["cone_len"]
    z2 = z1 + p["neck_w"]
    z3 = z2 + (p["flare_r"] - p["neck_r"])
    z4 = z3 + p["top_cyl"]
    prof = [(b, 0), (p["cone_r_tip"], 0), (p["cone_r_max"], z1), (p["neck_r"], z1), (p["neck_r"], z2),
            (p["flare_r"], z3), (p["flare_r"], z4), (b, z4)]
    return revolve(prof), dict(z_neck_mid=(z1 + z2) / 2, z_top=z4)


def cone_insertion(core_id):
    p = P
    return (core_id / 2 - p["cone_r_tip"]) / ((p["cone_r_max"] - p["cone_r_tip"]) / p["cone_len"])


def part_rod(length):
    return ext_thread(length, 2.7, 2.7)


def part_coupler():
    p = P
    return extrude(circle(p["coupler_od"] / 2), p["coupler_len"]) - int_void(p["coupler_len"])


# ----------------------------------------------------------------------------
# AXLE PLANNING (any film width)
# ----------------------------------------------------------------------------
def axle_needed(width, core_id):
    _, ci = part_cone()
    z_ins = cone_insertion(core_id)
    return width + 2 * (ci["z_top"] + ROD_PAST_KNOB - z_ins) + P["axle_margin"], z_ins, ci


def plan_axle(needed):
    """Cheapest set of library sections whose total >= needed. cost = excess + 60 mm per extra piece (a coupler = more
    parts/print time). Constraint: two END sections (>= rod_end_min); a single piece has no constraint.
    Returns dict(pieces=[len,...] in assembly order, counts={len: n}, couplers, total, excess)."""
    from itertools import combinations_with_replacement
    lib, em = sorted(P["rod_lengths"]), P["rod_end_min"]
    best = None
    for n in range(1, 8):
        for c in combinations_with_replacement(lib, n):
            L = sum(c)
            if L < needed or (n > 1 and sum(1 for x in c if x >= em) < 2):
                continue
            cost = (L - needed) + 60 * (n - 1)
            if best is None or cost < best[0]:
                best = (cost, c, L)
    _, c, L = best
    pc = sorted(c)
    ends = [x for x in pc if x >= em][:2] if len(pc) > 1 else pc[:1]
    mid = list(pc)
    for e in ends:
        mid.remove(e)
    order = ([ends[0]] + sorted(mid, reverse=True) + ends[1:]) if len(pc) > 1 else pc
    counts = {}
    for x in order:
        counts[x] = counts.get(x, 0) + 1
    return dict(pieces=order, counts=counts, total=L, couplers=len(order) - 1, excess=L - needed)


# ----------------------------------------------------------------------------
# EXPORT
# ----------------------------------------------------------------------------
def write_3mf(path, items):
    objs, build = [], []
    for i, (name, tm) in enumerate(items, start=1):
        vx = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in tm.vertices)
        tx = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tm.faces)
        objs.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>{vx}</vertices><triangles>{tx}</triangles></mesh></object>')
        build.append(f'<item objectid="{i}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources>{"".join(objs)}</resources><build>{"".join(build)}</build></model>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


def shelf_pack(parts, bed, gap):
    parts = sorted(parts, key=lambda a: -a[1].extents[1])
    placed, x, y, row_h = [], gap, gap, 0.0
    for name, tm in parts:
        w, d = tm.extents[0], tm.extents[1]
        if x + w + gap > bed:
            x, y, row_h = gap, y + row_h + gap, 0.0
        if y + d + gap > bed:
            raise RuntimeError(f"plate overflow at {name}")
        t = tm.copy()
        t.apply_translation([x - t.bounds[0][0], y - t.bounds[0][1], -t.bounds[0][2]])
        placed.append((name, t))
        x += w + gap
        row_h = max(row_h, d)
    allb = np.array([t.bounds for _, t in placed])
    off = [(256 - (allb[:, 1, 0].max() + allb[:, 0, 0].min())) / 2, (256 - (allb[:, 1, 1].max() + allb[:, 0, 1].min())) / 2]
    for _, t in placed:
        t.apply_translation([off[0], off[1], 0])
    return placed



# ----------------------------------------------------------------------------
# PER-PART PRINT SETTINGS (written as per-object overrides into the Bambu Studio project)
# keys are real Bambu Studio option names (PrintRegionConfig / PrintObjectConfig). Everything else = preset
# "0.20mm Standard @BBL A1" + "Bambu PETG Basic @BBL A1".
# ----------------------------------------------------------------------------
def _S(walls, infill, brim=0, shells=5, pattern="gyroid"):
    d = dict(wall_loops=walls, sparse_infill_density=f"{infill}%", sparse_infill_pattern=pattern,
             top_shell_layers=shells, bottom_shell_layers=shells, enable_support=0)
    if brim:
        d.update(brim_type="outer_only", brim_width=brim)
    return d


# (walls, infill %, brim mm) per part. Threaded parts keep >= 4 walls: a thread tooth is 1.9 mm deep, 3 walls (1.35 mm) leave a sparse-infill core.
PROFILES = {
    # "light" (default): ~38 % less plastic than "strong"; fine for hand-tightened household use
    "light":  dict(shells=4, parts={
        "clamp_L": (3, 12, 0), "clamp_R": (3, 12, 0), "holder": (4, 15, 6), "cone": (3, 10, 6), "clamp_screw": (4, 15, 8),
        "clamp_nut": (4, 15, 0), "pad": (3, 10, 0), "knob": (4, 15, 0), "rod": (4, 12, 8), "coupler": (4, 20, 5),
        "carrier": (4, 15, 0), "spindle": (4, 15, 6), "cone_v3": (3, 10, 6)}),
    # "strong": heavy-duty (the original v2 settings)
    "strong": dict(shells=5, parts={
        "clamp_L": (5, 35, 0), "clamp_R": (5, 35, 0), "holder": (5, 35, 6), "cone": (4, 25, 6), "clamp_screw": (5, 40, 8),
        "clamp_nut": (5, 40, 0), "pad": (4, 25, 0), "knob": (4, 30, 0), "rod": (5, 20, 8), "coupler": (5, 40, 5),
        "carrier": (5, 40, 0), "spindle": (5, 30, 6), "cone_v3": (4, 25, 6)}),
}


def print_settings(profile="light"):
    pr = PROFILES[profile]
    return {k: _S(w, i, brim=b, shells=pr["shells"]) for k, (w, i, b) in pr["parts"].items()}


PROFILE = "light"
PRINT_SETTINGS = print_settings(PROFILE)


def _settings(src):
    return PRINT_SETTINGS["rod" if src.startswith("rod_") else src]


def build_all():
    clamp, ring_c = part_clamp()
    cone, ci = part_cone()
    parts = dict(clamp_L=clamp, clamp_R=clamp.mirror((1, 0, 0)), clamp_nut=part_clamp_nut(), clamp_screw=part_clamp_screw(),
                 pad=part_pad(), holder=part_holder(), cone=cone, knob=part_knob(),
                 coupler=part_coupler())
    for L in P["rod_lengths"]:
        parts[f"rod_{int(L)}"] = part_rod(float(L))
    return parts, dict(ring_c=ring_c, cone=ci)


def main():
    width = float(sys.argv[1]) if len(sys.argv) > 1 else 530.0
    core_id = float(sys.argv[2]) if len(sys.argv) > 2 else 46.0
    if len(sys.argv) > 3:
        PRINT_SETTINGS.clear()
        PRINT_SETTINGS.update(print_settings(sys.argv[3]))
    parts, info = build_all()
    tms = {k: to_trimesh(v) for k, v in parts.items()}
    for k, tm in tms.items():
        tm.export(os.path.join(HERE, "stl", f"{k}.stl"))
        print(f"{k:12s} size {np.round(tm.extents, 1)}  vol {tm.volume/1000:6.1f} cm3  watertight={tm.is_watertight}")
    needed, _, _ = axle_needed(width, core_id)
    ax = plan_axle(needed)
    print(f"axle for W={width:.0f}, ID={core_id:.0f}: need {needed:.0f} mm -> {ax}")
    plates = {
        "plate1_clamps": [("clamp_L", "clamp_L"), ("clamp_R", "clamp_R")],
        "plate2_holders_cones": [("holder_1", "holder"), ("holder_2", "holder"), ("cone_1", "cone"), ("cone_2", "cone")],
        "plate3_screws_nuts_knobs": [("clamp_screw_1", "clamp_screw"), ("clamp_screw_2", "clamp_screw"),
                                     ("clamp_nut_1", "clamp_nut"), ("clamp_nut_2", "clamp_nut"),
                                     ("pad_1", "pad"), ("pad_2", "pad")] + [(f"knob_{i}", "knob") for i in range(1, 5)],
        "plate4_axle": ([(f"axle{i + 1}_rod_{L}", f"rod_{L}") for i, L in enumerate(ax["pieces"])] +
                        [(f"coupler_{i + 1}", "coupler") for i in range(ax["couplers"])]),
    }
    library = [(f"rod_{int(L)}", f"rod_{int(L)}") for L in P["rod_lengths"]] + [(f"coupler_{i + 1}", "coupler") for i in range(3)]
    import bambu_project
    project_plates = []
    plate_titles = {"plate1_clamps": "1 Clamps", "plate2_holders_cones": "2 Holders + cones",
                    "plate3_screws_nuts_knobs": "3 Screws, nuts, knobs, pads", "plate4_axle": "4 Axle (rods + couplers)"}
    for plate, items in plates.items():
        placed = shelf_pack([(n, tms[src]) for n, src in items], P["bed"], P["gap"])
        write_3mf(os.path.join(HERE, "3mf", "plain", f"{plate}.3mf"), placed)          # fallback: geometry only
        src_of = dict(items)
        project_plates.append(dict(name=plate_titles[plate], items=[
            dict(name=n, mesh=t, settings=_settings(src_of[n])) for n, t in placed]))
        b = np.array([t.bounds for _, t in placed])
        print(f"{plate}: {len(placed)} objs  X {b[:,0,0].min():.0f}..{b[:,1,0].max():.0f}  Y {b[:,0,1].min():.0f}..{b[:,1,1].max():.0f}  Hmax {b[:,1,2].max():.0f}")
    out = os.path.join(HERE, "3mf", "Stretch_Dispenser_A1_PETG.3mf")
    bambu_project.write_project(out, project_plates)
    print(f"Bambu project: {out} ({len(project_plates)} plates, {sum(len(p['items']) for p in project_plates)} objects)")
    # separate rod-library project: one of every section length + spare couplers (delete what you do not need, copy what you do)
    placed = shelf_pack([(n, tms[src]) for n, src in library], P["bed"], P["gap"])
    write_3mf(os.path.join(HERE, "3mf", "plain", "rod_library.3mf"), placed)
    lib_out = os.path.join(HERE, "3mf", "Axle_Rod_Library_A1_PETG.3mf")
    src_of = dict(library)
    bambu_project.write_project(lib_out, [dict(name="Axle rod library", items=[
        dict(name=n, mesh=t, settings=_settings(src_of[n])) for n, t in placed])])
    print(f"Rod library: {lib_out} (lengths {list(P['rod_lengths'])} + 3 couplers)")
    return parts, info


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "3mf", "plain"), exist_ok=True)
    main()
