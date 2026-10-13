#!/usr/bin/env python3
"""Independent checker of the Bambu project 3MF: mimics the rules of BambuStudio's importer (see bambu_project.py docstring)."""
import sys, json, math, zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh

path = sys.argv[1] if len(sys.argv) > 1 else "3mf/Stretch_Dispenser_A1_PETG.3mf"
NS = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
ok = True
def check(cond, msg):
    global ok
    print(("  OK   " if cond else "  FAIL ") + msg)
    ok &= bool(cond)

z = zipfile.ZipFile(path)
names = z.namelist()
print("files:", names)
for req in ["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model", "Metadata/model_settings.config", "Metadata/project_settings.config"]:
    check(req in names, f"contains {req}")

model = ET.fromstring(z.read("3D/3dmodel.model"))
meta = {m.get("name"): (m.text or "") for m in model.findall("c:metadata", NS)}
check(meta.get("Application", "").startswith("BambuStudio-"), f"Application tag = {meta.get('Application')!r} (must start with 'BambuStudio-')")
check(meta.get("BambuStudio:3mfVersion") == "1", "BambuStudio:3mfVersion = 1")

proj = json.loads(z.read("Metadata/project_settings.config"))
check(proj.get("name") == "project_settings" and len(proj) > 0, "project_settings.config is JSON, name=project_settings (config non-empty => no 'not from Bambu Lab' dialog)")
check(isinstance(proj.get("filament_colour"), list) and len(proj["filament_colour"]) == 1, "filament_colour has 1 entry (num_filaments=1)")
print("  presets:", proj["printer_settings_id"], "|", proj["print_settings_id"], "|", proj["filament_settings_id"])

objs = {}
for o in model.find("c:resources", NS).findall("c:object", NS):
    oid = int(o.get("id"))
    mesh = o.find("c:mesh", NS)
    comps = o.find("c:components", NS)
    if mesh is not None:
        v = np.array([[float(x.get(a)) for a in "xyz"] for x in mesh.find("c:vertices", NS)])
        f = np.array([[int(t.get(a)) for a in ("v1", "v2", "v3")] for t in mesh.find("c:triangles", NS)])
        objs[oid] = dict(kind="mesh", v=v, f=f)
    else:
        objs[oid] = dict(kind="comp", comps=[int(c.get("objectid")) for c in comps.findall("c:component", NS)])
check(all(not (o["kind"] == "mesh" and (o["f"].max() >= len(o["v"]))) for o in objs.values()), "all triangle indices valid")
items = model.find("c:build", NS).findall("c:item", NS)
check(all(int(i.get("objectid")) in objs and objs[int(i.get("objectid"))]["kind"] == "comp" for i in items), f"{len(items)} build items reference component objects")
check(all(c in objs and objs[c]["kind"] == "mesh" for i in items for c in objs[int(i.get("objectid"))]["comps"]), "every component references an existing mesh object")

cfg = ET.fromstring(z.read("Metadata/model_settings.config"))
cfg_objects = {int(o.get("id")): o for o in cfg.findall("object")}
check(set(cfg_objects) == {int(i.get("objectid")) for i in items}, "model_settings objects == build objects")
bad = [oid for oid, o in cfg_objects.items() if [int(p.get("id")) for p in o.findall("part")] != objs[oid]["comps"]]
check(not bad, "every <part id> equals its component's mesh-object id (required by _generate_volumes_new)")
check(all(any(m.get("key") == "name" for m in o.findall("metadata")) for o in cfg_objects.values()), "all objects named")

plates = cfg.findall("plate")
n = len(plates)
v = math.sqrt(n); r = round(v); cols = r + 1 if v > r else r
stride = 256 * 1.2
print(f"plates: {n}, cols={cols}, stride={stride}")
def box(p):
    ox, oy = (p % cols) * stride, -(p // cols) * stride
    return np.array([ox, oy, 0]), np.array([ox + 256, oy + 256, 256])
item_by_obj = {int(i.get("objectid")): i for i in items}
placed_total = 0
for pi, pl in enumerate(plates):
    md = {m.get("key"): m.get("value") for m in pl.findall("metadata")}
    check(int(md["plater_id"]) == pi + 1, f"plate {pi+1}: plater_id ok, name={md['plater_name']!r}")
    lo_b, hi_b = box(pi)
    for inst in pl.findall("model_instance"):
        oid = int(next(m.get("value") for m in inst.findall("metadata") if m.get("key") == "object_id"))
        tr = [float(x) for x in item_by_obj[oid].get("transform").split()]
        t = np.array(tr[9:12])
        mv = objs[objs[oid]["comps"][0]]["v"] + t
        lo, hi = mv.min(0), mv.max(0)
        inside = (lo >= lo_b - 1e-6).all() and (hi <= hi_b + 1e-6).all()
        other = [q for q in range(n) if q != pi and ((lo <= box(q)[1]).all() and (hi >= box(q)[0]).all())]
        name = next(m.get("value") for m in cfg_objects[oid].findall("metadata") if m.get("key") == "name")
        if not inside or other or lo[2] < -1e-6:
            check(False, f"object {name}: inside={inside}, intersects other plates {other}, zmin={lo[2]:.3f}")
        placed_total += 1
print(f"  all {placed_total} objects lie fully inside their own plate and touch no other plate")
check(placed_total == len(items), "every object belongs to exactly one plate")

tm = trimesh.load(path)
geoms = list(tm.geometry.values())
check(len(geoms) == len(items) and all(g.is_watertight for g in geoms), f"trimesh loads {len(geoms)} watertight meshes")
print("PER-OBJECT SETTINGS (sample):")
for oid in list(cfg_objects)[:2] + list(cfg_objects)[-2:]:
    print("  ", {m.get("key"): m.get("value") for m in cfg_objects[oid].findall("metadata")})
print("RESULT:", "ALL CHECKS PASSED" if ok else "FAILURES")
sys.exit(0 if ok else 1)
