"""Регресійний тест конструктора сітки-органайзера (grid_engine + інтеграція).
Запуск:  .venv\\Scripts\\python.exe test_grid_constructor.py
"""
import os, sys, time, json, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import grid_engine as ge
from mesh_engine import MeshData, write_ascii_stl


def test_engine():
    cfg = ge.default_config(outer_L=240, outer_W=160, outer_H=40, nx=4, ny=3, wall=2.0)
    ok, _ = ge.validate(cfg); assert ok
    info = ge.layout_info(cfg)
    assert abs(info['outer_L'] - 240) < 1e-3 and abs(info['outer_W'] - 160) < 1e-3
    mods = ge.build_modules(cfg)
    assert len(mods) == 1
    v = mods[0]['mesh'].verts
    assert abs((v[:, 0].max() - v[:, 0].min()) - 240) < 1e-2
    assert abs(v[:, 2].max() - 40) < 1e-2 and abs(v[:, 2].min()) < 1e-2

    # segmentation
    assert len(ge.build_modules({**cfg, 'segment': 'per_cell'})) == 12
    bed = {**cfg, 'segment': 'bed', 'bed_x': 120, 'bed_y': 120}
    assert ge.layout_info(bed)['n_modules'] > 1
    # manual grouping: cut_x=[2] on nx=4 → 2 column groups
    man = {**cfg, 'segment': 'manual', 'cut_x': [2], 'cut_y': []}
    assert ge.layout_info(man)['n_modules'] == 2
    assert len(ge.build_modules(man)) == 2

    # drawer-divider: outer fixed
    cw = cfg['col_widths'][:]
    cw2 = ge.redistribute(cw, 0, cw[0] + 30, cfg['outer_L'], cfg['wall'])
    assert abs(sum(cw) - sum(cw2)) < 1e-4 and abs(cw2[0] - (cw[0] + 30)) < 1e-6
    assert min(ge.redistribute(cw, 0, 9999, cfg['outer_L'], cfg['wall'])) >= ge.MIN_CELL - 1e-6
    # lock-aware: lock col 1, change col 0 → col 1 stays, outer fixed
    locked = [False, True, False, False]
    base = cfg['col_widths'][:]
    out = ge.redistribute_locked(base, 0, base[0] + 25, cfg['outer_L'], cfg['wall'], locked)
    assert abs(sum(base) - sum(out)) < 1e-4, "locked redistribute changed outer"
    assert abs(out[1] - base[1]) < 1e-6, "locked col moved on redistribute"
    # rescale_free: locked col stays when outer grows
    out2 = ge.rescale_free(base, cfg['outer_L'] + 60, cfg['wall'], locked)
    assert out2 is not None and abs(out2[1] - base[1]) < 1e-6, "locked col rescaled"
    assert abs(sum(out2) - ge.inner_total(cfg['outer_L'] + 60, 4, cfg['wall'])) < 1e-3
    # split / merge / multi-set
    s2, l2, ok = ge.add_split([60, 60, 60], [False, False, False], 1, 0.5)
    assert ok and len(s2) == 4 and abs(sum(s2) - 180) < 1e-6, "add_split"
    s3, l3, ok2 = ge.remove_line([40, 50, 60], [False, True, False], 0)
    assert ok2 and len(s3) == 2 and abs(sum(s3) - 150) < 1e-6, "remove_line"
    bm = ge.auto_sizes(300, 4, 2.0)
    om = ge.redistribute_locked_multi(bm, {0: 70, 2: 70}, 300, 2.0, [False] * 4)
    assert abs(om[0] - 70) < 1e-6 and abs(om[2] - 70) < 1e-6, "multi-set values"
    assert abs(sum(om) - ge.inner_total(300, 4, 2.0)) < 1e-3, "multi-set outer"
    print("  engine + locks + split/multi: OK")


def test_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from app import BoxGeneratorApp
    w = BoxGeneratorApp()

    def pump(secs=3.0):
        t = time.time()
        while time.time() - t < secs:
            app.processEvents(); time.sleep(0.03)
            if w.current_shape is not None:
                return True
        return w.current_shape is not None

    # (a) звичайна коробка (Генерація) ще працює — регресія
    w.current_shape = None
    w.generate_box()
    assert pump(), "single-box generation broke"
    print("  regression (single box): OK")

    # (b) grid constructor
    assert hasattr(w, 'grid_box') and hasattr(w, 'create_or_update_grid')
    w.mode_assem_btn.setChecked(True); app.processEvents()
    w.grid_outer_l.setValue(300); w.grid_outer_w.setValue(200); w.grid_outer_h.setValue(45)
    w.grid_nx.setValue(5); w.grid_ny.setValue(4); w.grid_wall.setValue(2.0)
    w.grid_floor_cb.setChecked(True); w.grid_floor_t.setValue(2.4)
    w.grid_segment.setCurrentIndex(1); w.grid_bed_x.setValue(150); w.grid_bed_y.setValue(150)
    w._live_update_grid(); app.processEvents()   # real-time path (no button)
    g = [it for it in w.placed_items if it.get("type") == "grid"][0]
    nmod = ge.layout_info(g["grid_config"])['n_modules']
    assert nmod > 1
    w.current_shape = None; w.generate_box(); assert pump()
    assert isinstance(w.current_shape, list) and len(w.current_shape) >= nmod
    print(f"  grid render: OK ({len(w.current_shape)} meshes)")

    # (c) per-cell edit auto-locks; outer fixed; locked col stays when others change
    gi = next(i for i, it in enumerate(w.placed_items) if it.get("type") == "grid")
    cw = w.placed_items[gi]["grid_config"]["col_widths"][:]
    w.set_grid_cell(gi, c=0, new_w=cw[0] + 40); app.processEvents()
    cfg2 = w.placed_items[gi]["grid_config"]
    assert abs(sum(cw) - sum(cfg2["col_widths"])) < 1e-3, "outer changed"
    assert abs(cfg2["col_widths"][0] - (cw[0] + 40)) < 1.0, "cell0 not set"
    assert cfg2["col_locked"][0] is True, "edit did not auto-lock"
    locked_val = cfg2["col_widths"][0]
    w.set_grid_cell(gi, c=1, new_w=cfg2["col_widths"][1] + 20); app.processEvents()
    assert abs(w.placed_items[gi]["grid_config"]["col_widths"][0] - locked_val) < 1e-6, "locked col moved!"
    print("  per-cell edit + lock: OK")

    # (d) save/load round-trip
    data2 = json.loads(json.dumps(w.get_preset_dict()))
    w.placed_items = []; w.placed_list.clear()
    w.set_preset_dict(data2); app.processEvents()
    g2 = [it for it in w.placed_items if it.get("type") == "grid"]
    assert len(g2) == 1 and g2[0]["grid_config"]["nx"] == 5
    print("  save/load: OK")

    # (e) wall-drag resize via PuzzleGridItem (detect boundary + redistribute pair)
    from puzzle_item import PuzzleGridItem
    gi = next(i for i, it in enumerate(w.placed_items) if it.get("type") == "grid")
    pit = PuzzleGridItem(gi, w)
    cfg = w.placed_items[gi]["grid_config"]
    info = ge.layout_info(cfg); wall = cfg["wall"]
    bx = info["cav_x"][0][1] + wall / 2            # стінка між колонками 0 і 1 (мм)
    hit = pit._wall_at(bx, info["outer_W"] / 2)
    assert hit and hit[0] == 'x' and hit[1] == 0, f"wall not detected: {hit}"
    cw = cfg["col_widths"][:]; b, delta = 0, 20.0
    delta = max(-(cw[b] - ge.MIN_CELL), min(delta, cw[b + 1] - ge.MIN_CELL))
    new = list(cw); new[b] += delta; new[b + 1] -= delta
    cfg["col_widths"] = new
    w._finalize_grid_resize(gi); app.processEvents()
    cw2 = cfg["col_widths"]
    assert abs(sum(cw) - sum(cw2)) < 1e-3 and abs(cw2[0] - (cw[0] + delta)) < 1e-6
    print("  wall-drag resize: OK (boundary detect + outer preserved)")

    # (f) right-click split + Ctrl multi-set
    gi = next(i for i, it in enumerate(w.placed_items) if it.get("type") == "grid")
    nx0 = len(w.placed_items[gi]["grid_config"]["col_widths"])
    w.add_grid_split(gi, 'x', 0, 0.5); app.processEvents()
    assert len(w.placed_items[gi]["grid_config"]["col_widths"]) == nx0 + 1, "split didn't add column"
    w.toggle_cell_selection(gi, 0, 0); w.toggle_cell_selection(gi, 1, 0)
    assert len(getattr(w, "_selected_cells", set())) == 2, "multi-select failed"
    w.set_grid_cells(gi, cols=[0, 1], new_w=48); app.processEvents()
    cwf = w.placed_items[gi]["grid_config"]["col_widths"]
    assert abs(cwf[0] - 48) < 1.0 and abs(cwf[1] - 48) < 1.0, "multi-set width failed"
    w.add_grid_split(gi, 'y', 0, 0.5); app.processEvents()
    print("  split + remove + Ctrl multi-set: OK")


if __name__ == "__main__":
    print("test_engine:"); test_engine()
    print("test_app:"); test_app()
    print("\nALL_PASSED")
