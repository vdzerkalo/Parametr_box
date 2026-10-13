#!/usr/bin/env python3
"""
Writer of a REAL Bambu Studio project (.3mf): several plates in one file + per-object print settings + A1/PETG presets.

AI-READABLE NOTES (derived from the open-source BambuStudio importer: src/libslic3r/Format/bbs_3mf.cpp, GUI/PartPlate.cpp):
  * A 3MF counts as "from Bambu Lab" only if 3D/3dmodel.model has <metadata name="Application">BambuStudio-<ver></metadata>
    AND Metadata/project_settings.config exists with a non-empty config. Otherwise Studio shows
    "The 3mf is not from Bambu Lab, load geometry data..." and DROPS object settings and plates.
  * Plate membership is NOT stored by id: after load Studio calls PartPlateList::reload_all_objects(), which assigns each
    object to the plate whose box it intersects. Plate i origin = (col*stride, -row*stride), stride = 256*1.2 = 307.2 mm,
    cols = compute_colum_count(plate_count) = round-up(sqrt(count)). So we position every object in GLOBAL coordinates.
  * Object = <object id=2k> with <component objectid=2k-1> (mesh object); Metadata/model_settings.config has
    <object id=2k> (name + per-object overrides as <metadata key=value>) with <part id=2k-1 subtype=normal_part>.
  * project_settings.config is JSON; Studio fills every key NOT listed in different_settings_to_system from the named
    system presets (print_settings_id / filament_settings_id / printer_settings_id), so a minimal file is enough.
UNTESTED against the real application (no network access to a Studio build in the authoring sandbox).
"""
import json
import math
import zipfile
from xml.sax.saxutils import escape, quoteattr

import numpy as np

APP_VERSION = "02.00.00.00"          # >= 2.0.0 avoids legacy conversion branches; <= any current 2.x app => no "newer file" dialog
BED = 256.0
STRIDE = BED * (1.0 + 1.0 / 5.0)     # LOGICAL_PART_PLATE_GAP = 1/5

PRESETS = dict(
    printer="Bambu Lab A1 0.4 nozzle",
    process="0.20mm Standard @BBL A1",
    filament="Bambu PETG Basic @BBL A1",
)

IDENT = "1 0 0 0 1 0 0 0 1 0 0 0"
IDENT4 = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"


def plate_cols(count):
    v = math.sqrt(count)
    r = round(v)
    return int(r + 1) if v > r else int(r)


def plate_origin(index, count):
    cols = plate_cols(count)
    return (index % cols) * STRIDE, -(index // cols) * STRIDE


def _fmt(x):
    return f"{x:.6f}".rstrip("0").rstrip(".") if abs(x) > 1e-9 else "0"


def project_settings_json(filament_colour="#808080"):
    return json.dumps({
        "from": "project",
        "name": "project_settings",
        "version": APP_VERSION,
        "printer_settings_id": PRESETS["printer"],
        "print_settings_id": PRESETS["process"],
        "filament_settings_id": [PRESETS["filament"]],
        "filament_colour": [filament_colour],
        "inherits_group": ["", "", ""],
        "different_settings_to_system": ["", "", ""],
    }, indent=4)


def write_project(path, plates):
    """
    plates: list of {"name": str, "items": [ {"name": str, "mesh": trimesh.Trimesh, "settings": {key: str}} ... ]}
    Every mesh must already be positioned in single-plate coordinates (0..256, z>=0); this function shifts it to its plate.
    """
    n_plates = len(plates)
    obj_xml, build_xml = [], []
    cfg_objects, cfg_plates = [], []
    k = 0
    ident_counter = 1000
    for pi, plate in enumerate(plates):
        ox, oy = plate_origin(pi, n_plates)
        instances = []
        for item in plate["items"]:
            k += 1
            mesh_id, obj_id = 2 * k - 1, 2 * k
            m = item["mesh"]
            v = np.asarray(m.vertices, dtype=float)
            lo, hi = v.min(axis=0), v.max(axis=0)
            cx, cy = (lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0
            local = v - np.array([cx, cy, 0.0])
            if lo[2] < -1e-6 or lo[0] < 0 or lo[1] < 0 or hi[0] > BED or hi[1] > BED:
                raise ValueError(f"{item['name']} is outside the 256x256 plate: {lo} {hi}")
            vx = "".join(f'<vertex x="{_fmt(a)}" y="{_fmt(b)}" z="{_fmt(c)}"/>' for a, b, c in local)
            tx = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in np.asarray(m.faces))
            obj_xml.append(f'  <object id="{mesh_id}" type="model"><mesh><vertices>{vx}</vertices><triangles>{tx}</triangles></mesh></object>\n')
            obj_xml.append(f'  <object id="{obj_id}" type="model"><components><component objectid="{mesh_id}" transform="{IDENT}"/></components></object>\n')
            build_xml.append(f'  <item objectid="{obj_id}" transform="1 0 0 0 1 0 0 0 1 {_fmt(cx + ox)} {_fmt(cy + oy)} 0" printable="1"/>\n')

            meta = [f'    <metadata key="name" value={quoteattr(item["name"])}/>\n', '    <metadata key="extruder" value="1"/>\n']
            for key, val in item.get("settings", {}).items():
                meta.append(f'    <metadata key="{key}" value={quoteattr(str(val))}/>\n')
            cfg_objects.append(
                f'  <object id="{obj_id}">\n' + "".join(meta) +
                f'    <part id="{mesh_id}" subtype="normal_part">\n'
                f'      <metadata key="name" value={quoteattr(item["name"])}/>\n'
                f'      <metadata key="matrix" value="{IDENT4}"/>\n'
                f'    </part>\n  </object>\n')
            ident_counter += 1
            instances.append((obj_id, ident_counter))
        inst_xml = "".join(
            f'    <model_instance>\n      <metadata key="object_id" value="{o}"/>\n'
            f'      <metadata key="instance_id" value="0"/>\n      <metadata key="identify_id" value="{i}"/>\n    </model_instance>\n'
            for o, i in instances)
        cfg_plates.append(
            f'  <plate>\n    <metadata key="plater_id" value="{pi + 1}"/>\n'
            f'    <metadata key="plater_name" value={quoteattr(plate["name"])}/>\n'
            f'    <metadata key="locked" value="false"/>\n{inst_xml}  </plate>\n')

    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n'
             f' <metadata name="Application">BambuStudio-{APP_VERSION}</metadata>\n'
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             ' <metadata name="Title">Stretch film dispenser (clamp, all printed)</metadata>\n'
             ' <resources>\n' + "".join(obj_xml) + ' </resources>\n <build>\n' + "".join(build_xml) + ' </build>\n</model>\n')
    model_settings = '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "".join(cfg_objects) + "".join(cfg_plates) + '</config>\n'
    content_types = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                     ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                     ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
                     ' <Default Extension="png" ContentType="image/png"/>\n <Default Extension="gcode" ContentType="text/x.gcode"/>\n</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/project_settings.config", project_settings_json())
    return n_plates
