#!/usr/bin/env python3
"""
Parametric generator: clamp-mounted stretch-film dispenser (Bambu Lab A1, PETG).

AI-READABLE SUMMARY
  Run:     python generate.py            -> writes stl/, 3mf/, assembly_preview.stl
  Deps:    manifold3d shapely numpy trimesh
  Units:   millimetres. All STL are in PRINT ORIENTATION (flat on bed, z=0 is bed face).
  Parts:   clamp_L, clamp_R(mirror of L), holder x2, cone x2, knob_nut x4, knob_head x2, pad x2
  Hardware (not printed): M10 threaded rod (axle, cut to length, see calc.py),
           M10x100 hex bolt x2 (clamp screw), M10x50 hex bolt x2 (pivot), M10 hex nut x8.
  Everything is defined in the PARAMS dict below; change a value and re-run.
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

# ----------------------------------------------------------------------------
# PARAMETERS
# ----------------------------------------------------------------------------
PARAMS = dict(
    # --- hardware fit ---
    bore=10.6,          # clearance hole for M10
    nut_af=17.5,        # hex pocket across-flats for M10 nut (DIN 934 = 17, ISO = 16)
    nut_depth=8.8,      # M10 nut height 8.0-8.4 + slack
    head_af=17.4,       # pocket for M10 bolt head
    head_depth=7.2,     # M10 bolt head height 6.4 + slack
    # --- clamp (C-frame) ---
    clamp_w=30.0,       # width along the axle direction (Z)
    spine=20.0,         # spine thickness
    arm_lo=18.0,        # lower arm thickness (holds the nut)
    arm_up=16.0,        # upper arm thickness
    jaw_gap=75.0,       # inner opening between arms (max table thickness ~ gap-15)
    arm_len=92.0,       # x length of arms
    screw_x=68.0,       # screw axis distance from the back face of the spine
    ring_r=29.0,        # pivot disc radius (teeth ring lives here)
    # --- tooth ring (pivot lock, 15 deg steps) ---
    teeth_n=24,
    teeth_h=2.0,
    teeth_r1=14.0,
    teeth_r2=27.0,
    teeth_gap=0.25,     # axial clearance between mating tooth tips and valleys
    # --- holder arm ---
    holder_t=12.0,      # plate thickness (also hub groove width - 1)
    holder_L=60.0,      # pivot -> slot centre
    slot_r=13.5,        # slot radius (hub neck radius 13.0 + 0.5 clearance)
    # --- cone hub (centres the roll, rides in holder slot) ---
    cone_r_tip=16.0,    # tip radius (diam 32)
    cone_r_max=29.0,    # max radius (diam 58)
    cone_len=36.0,
    neck_r=13.0,
    neck_w=13.0,
    flare_r=21.0,
    top_cyl=3.0,
    # --- pad ---
    pad_r=18.0,
    # --- printing bed ---
    bed=250.0,          # usable plate (A1 = 256, keep margin)
    gap=7.0,
)
P = PARAMS
SEG = 96  # circle segments


# ----------------------------------------------------------------------------
# GEOMETRY HELPERS
# ----------------------------------------------------------------------------
def _rings(poly):
    out = [np.array(poly.exterior.coords[:-1], dtype=float)]
    for i in poly.interiors:
        out.append(np.array(i.coords[:-1], dtype=float))
    return out


def extrude(geom, h):
    """Shapely (Multi)Polygon -> Manifold extruded along +Z from z=0."""
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    rings = [r for p in polys for r in _rings(p)]
    cs = CrossSection(rings, fillrule=FillRule.EvenOdd)
    return Manifold.extrude(cs, h)


def revolve(profile, segs=SEG):
    """profile: [(r, z), ...] -> solid of revolution around Z."""
    return Manifold.revolve(CrossSection([np.array(profile, dtype=float)]), segs)


def circle(r, c=(0, 0), n=SEG):
    return Point(*c).buffer(r, quad_segs=n // 4)


def hexagon(af):
    R = af / np.sqrt(3)
    return Polygon([(R * np.cos(np.radians(a)), R * np.sin(np.radians(a))) for a in range(0, 360, 60)])


def closing(g, r):  # fillet concave corners
    return g.buffer(r, quad_segs=16).buffer(-r, quad_segs=16)


def opening(g, r):  # round convex corners
    return g.buffer(-r, quad_segs=16).buffer(r, quad_segs=16)


def teardrop(r):
    k = r / np.sqrt(2)
    tri = Polygon([(0, r * np.sqrt(2)), (-k, k), (k, k)])
    return unary_union([circle(r, n=48), tri])


def prism_along_y(poly_xz, y0, y1):
    """Extrude polygon given in world (x,z) coordinates along world Y from y0 to y1."""
    flipped = Polygon([(x, -z) for x, z in poly_xz.exterior.coords[:-1]])
    sol = extrude(flipped, y1 - y0).rotate((-90, 0, 0))  # local (u,v,w)->(u,w,-v)
    return sol.translate((0, y0, 0))


def teeth_ring(r1, r2, n, h, z0, ridge_deg, base=0.8, mirror_diag=False):
    """Radial triangular ridges (n of them) on top of plane z=z0; ridge crest at ridge_deg."""
    M = 2 * n
    ang = [np.radians(ridge_deg + k * 180.0 / n) for k in range(M)]
    V = []
    for rr, zz in ((r1, "t"), (r2, "t"), (r1, "b"), (r2, "b")):
        for k in range(M):
            z = z0 + (h if k % 2 == 0 else 0.0) if zz == "t" else z0 - base
            V.append((rr * np.cos(ang[k]), rr * np.sin(ang[k]), z))
    TI = lambda k: k % M
    TO = lambda k: M + k % M
    BI = lambda k: 2 * M + k % M
    BO = lambda k: 3 * M + k % M
    T = []
    for k in range(M):
        # k even = ridge->valley (descending in angle), k odd = valley->ridge. Diagonal choice is mirror-symmetric
        # about the crest; mating parts use opposite parity (mirror_diag) so their flank meshes coincide exactly.
        asc = (k % 2 == 1) != mirror_diag
        if asc:
            T += [(TI(k), TO(k), TO(k + 1)), (TI(k), TO(k + 1), TI(k + 1))]      # top, diagonal I(k)-O(k+1)
        else:
            T += [(TI(k), TO(k), TI(k + 1)), (TO(k), TO(k + 1), TI(k + 1))]      # top, diagonal O(k)-I(k+1)
        T += [(BI(k), BO(k + 1), BO(k)), (BI(k), BI(k + 1), BO(k + 1))]          # bottom
        T += [(TO(k), BO(k), BO(k + 1)), (TO(k), BO(k + 1), TO(k + 1))]          # outer wall
        T += [(TI(k), BI(k + 1), BI(k)), (TI(k), TI(k + 1), BI(k + 1))]          # inner wall
    mesh = m.Mesh(vert_properties=np.array(V, dtype=np.float32), tri_verts=np.array(T, dtype=np.uint32))
    out = Manifold(mesh)
    if out.volume() < 0:
        raise RuntimeError("teeth ring has inverted orientation")
    return out


def to_trimesh(man):
    mesh = man.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                           faces=np.asarray(mesh.tri_verts), process=True)


# ----------------------------------------------------------------------------
# PARTS (print orientation)
# ----------------------------------------------------------------------------
def part_clamp():
    p = P
    top_y = p["arm_lo"] + p["jaw_gap"] + p["arm_up"]        # top of upper arm
    ring_c = (p["ring_r"], top_y + 14.0)                    # pivot centre
    spine = box(0, 0, p["spine"], top_y)
    lo = box(0, 0, p["arm_len"], p["arm_lo"])
    up = box(0, p["arm_lo"] + p["jaw_gap"], p["arm_len"], top_y)
    disc = circle(p["ring_r"], ring_c)
    head = unary_union([disc, box(0, top_y - 16, p["spine"], ring_c[1])]).convex_hull
    prof = unary_union([spine, lo, up, head])
    prof = opening(closing(prof, 9.0), 3.0)
    prof = prof.difference(circle(p["bore"] / 2, ring_c, 48))
    body = extrude(prof, p["clamp_w"])

    # tooth ring on +Z face. valley points to +Y (90 deg), ridges at 90 +/- 7.5
    ridge0 = 90.0 - 180.0 / p["teeth_n"]
    t = teeth_ring(p["teeth_r1"], p["teeth_r2"], p["teeth_n"], p["teeth_h"], p["clamp_w"], ridge0)
    t = t.translate((ring_c[0], ring_c[1], 0))
    # keep the bore clear
    body = body + t
    body = body - extrude(circle(p["bore"] / 2, ring_c, 48), p["clamp_w"] + 5).translate((0, 0, -1))

    # clamp screw: teardrop through-hole along Y + hex nut pocket opening on the jaw side
    zc = p["clamp_w"] / 2
    xs = p["screw_x"]
    td = teardrop(p["bore"] / 2)
    td_xz = Polygon([(xs + x, zc + z) for x, z in td.exterior.coords[:-1]])
    body = body - prism_along_y(td_xz, -1, p["arm_lo"] + 1)
    hx = hexagon(p["nut_af"])
    hx_xz = Polygon([(xs + x, zc + y) for x, y in hx.exterior.coords[:-1]])
    body = body - prism_along_y(hx_xz, p["arm_lo"] - p["nut_depth"], p["arm_lo"] + 1)
    return body, ring_c


def part_holder():
    p = P
    L = p["holder_L"]
    t = p["holder_t"]
    outer = unary_union([circle(p["ring_r"], (0, 0)), circle(26.0, (0, L))]).convex_hull
    slot = unary_union([
        circle(p["slot_r"], (0, L)),
        Polygon([(-p["slot_r"], L), (p["slot_r"], L), (p["slot_r"] + 3.2, L + 32), (-p["slot_r"] - 3.2, L + 32)]),
    ])
    prof = opening(outer.difference(slot), 1.5)
    body = extrude(prof, t)
    # teeth on the +Z face. ridge crest on the arm axis (+Y = 90 deg)
    tr = teeth_ring(p["teeth_r1"], p["teeth_r2"], p["teeth_n"], p["teeth_h"], t, 90.0, mirror_diag=True)
    body = body + tr
    # M10 bolt-head pocket, open on the tooth face (print-up => no bridging). The head is trapped between
    # holder and clamp; the shank goes through the clamp. No through-hole => roll-facing face stays flat.
    body = body - extrude(hexagon(p["head_af"]), p["head_depth"] + 0.5).translate((0, 0, t - p["head_depth"]))
    return body


def _scalloped(r, n, sc_r, sc_off):
    g = circle(r)
    cuts = unary_union([circle(sc_r, (sc_off * np.cos(2 * np.pi * i / n), sc_off * np.sin(2 * np.pi * i / n)), 48)
                        for i in range(n)])
    return opening(g.difference(cuts), 1.2)


def part_knob_nut():
    """Wing knob with captured M10 nut (nut pocket on the bed face)."""
    p = P
    h = 14.0
    body = extrude(_scalloped(22.0, 6, 7.0, 25.0), h)
    body = body - extrude(hexagon(p["nut_af"]), p["nut_depth"]).translate((0, 0, -0.01))
    body = body - extrude(circle(p["bore"] / 2, n=48), h + 2).translate((0, 0, -1))
    return body


def part_knob_head():
    """Big knob for the clamp screw; M10 bolt head sits in a hex pocket on top (print upright)."""
    p = P
    h = 24.0
    body = extrude(_scalloped(26.0, 8, 8.0, 28.0), h)
    body = body - extrude(hexagon(p["head_af"] - 0.1), p["head_depth"] + 0.8).translate((0, 0, h - p["head_depth"] - 0.8))
    return body


def part_pad():
    """Swivel-ish pad on the clamp screw tip. Table-contact face prints on the bed."""
    p = P
    r = p["pad_r"]
    prof = [(0, 0), (r - 1.2, 0), (r, 1.2), (r, 5), (10, 5), (10, 15), (0, 15)]
    body = revolve(prof)
    body = body - extrude(circle(5.1, n=48), 13).translate((0, 0, 3))
    return body


def part_cone():
    """Hub: taper centres in any core 34..54 mm ID, groove rides in the holder slot. Prints tip-down."""
    p = P
    b = p["bore"] / 2
    z1 = p["cone_len"]
    z2 = z1 + p["neck_w"]
    z3 = z2 + (p["flare_r"] - p["neck_r"])
    z4 = z3 + p["top_cyl"]
    prof = [(b, 0), (p["cone_r_tip"], 0), (p["cone_r_max"], z1), (p["neck_r"], z1), (p["neck_r"], z2),
            (p["flare_r"], z3), (p["flare_r"], z4), (b, z4)]
    return revolve(prof), dict(z_neck_mid=(z1 + z2) / 2, z_top=z4, z_neck0=z1, z_neck1=z2)


def cone_insertion(core_id):
    """Depth (from tip) at which the taper has diameter == core_id."""
    p = P
    return (core_id / 2 - p["cone_r_tip"]) / ((p["cone_r_max"] - p["cone_r_tip"]) / p["cone_len"])


# ----------------------------------------------------------------------------
# EXPORT HELPERS
# ----------------------------------------------------------------------------
def write_3mf(path, items):
    """items: list of (name, trimesh.Trimesh) already positioned on the plate (x,y in 0..256)."""
    objs, build = [], []
    for i, (name, tm) in enumerate(items, start=1):
        v = tm.vertices
        vx = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in v)
        tx = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tm.faces)
        objs.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>{vx}</vertices>'
                    f'<triangles>{tx}</triangles></mesh></object>')
        build.append(f'<item objectid="{i}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             '<metadata name="Application">tmp_stretch_dispenser/generate.py</metadata>'
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
    """parts: list of (name, trimesh). Returns positioned copies, raises if not fit. Simple shelf packing."""
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
    # centre the group on the 256 bed
    allb = np.array([t.bounds for _, t in placed])
    off = [(256 - (allb[:, 1, 0].max() + allb[:, 0, 0].min())) / 2, (256 - (allb[:, 1, 1].max() + allb[:, 0, 1].min())) / 2]
    for _, t in placed:
        t.apply_translation([off[0], off[1], 0])
    return placed


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def build_all():
    clamp, ring_c = part_clamp()
    holder = part_holder()
    cone, cone_info = part_cone()
    knob_nut = part_knob_nut()
    knob_head = part_knob_head()
    pad = part_pad()
    # print orientation of mirrored clamp = in-plane mirror
    clamp_R = clamp.mirror((1, 0, 0))
    return dict(clamp_L=clamp, clamp_R=clamp_R, holder=holder, cone=cone, knob_nut=knob_nut,
                knob_head=knob_head, pad=pad), dict(ring_c=ring_c, cone=cone_info)


PLATES = {
    "plate1_clamps": [("clamp_L", "clamp_L"), ("clamp_R", "clamp_R")],
    "plate2_holders_cones": [("holder_1", "holder"), ("holder_2", "holder"), ("cone_1", "cone"), ("cone_2", "cone")],
    "plate3_knobs_pads": [("knob_nut_1", "knob_nut"), ("knob_nut_2", "knob_nut"), ("knob_nut_3", "knob_nut"),
                          ("knob_nut_4", "knob_nut"), ("knob_head_1", "knob_head"), ("knob_head_2", "knob_head"),
                          ("pad_1", "pad"), ("pad_2", "pad")],
}


def print_orientation(parts):
    """Design/assembly orientation -> print orientation (only knob_nut differs: pocket up, no bridging)."""
    out = dict(parts)
    out["knob_nut"] = parts["knob_nut"].rotate((180, 0, 0)).translate((0, 0, 14.0))
    return out


def main():
    parts, info = build_all()
    tms = {k: to_trimesh(v) for k, v in print_orientation(parts).items()}
    report = {}
    for k, tm in tms.items():
        tm.export(os.path.join(HERE, "stl", f"{k}.stl"))
        report[k] = dict(size=[round(x, 1) for x in tm.extents], volume_cm3=round(tm.volume / 1000, 1),
                         watertight=bool(tm.is_watertight))
    for plate, items in PLATES.items():
        placed = shelf_pack([(n, tms[src]) for n, src in items], P["bed"], P["gap"])
        write_3mf(os.path.join(HERE, "3mf", f"{plate}.3mf"), placed)
        b = np.array([t.bounds for _, t in placed])
        print(f"{plate}: {len(placed)} objects, footprint X {b[:,0,0].min():.0f}..{b[:,1,0].max():.0f}"
              f"  Y {b[:,0,1].min():.0f}..{b[:,1,1].max():.0f}")
    for k, v in report.items():
        print(f"{k:11s} {v}")
    return parts, info


if __name__ == "__main__":
    main()
