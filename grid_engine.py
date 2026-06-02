"""grid_engine.py — параметрична сітка-органайзер (PARTITIONED) для ParametrBox.

Будує модулі зі СПІЛЬНИМИ внутрішніми стінками як polygon-with-holes, з опційним
дном (floor_t) та безклейовими dovetail-швами між модулями (вертикальний слайд-замок).
Чистий рушій — без Qt. Геометрія центрується навколо (0,0); низ на z=0.

Модель даних (grid_config):
    outer_L, outer_W, outer_H   — зовнішні габарити (мм). outer фіксований (drawer-divider).
    nx, ny                       — к-сть стовпців/рядів.
    wall                         — товщина стінок (зовнішніх і внутрішніх).
    floor_t                      — товщина дна (0 = без дна, наскрізні комірки).
    col_widths[nx], row_heights[ny] — ВНУТРІШНІ просвіти комірок (джерело істини розмірів).
    bed_x, bed_y                 — розмір столу для авто-сегментації.
    segment                      — 'none' | 'bed' | 'per_cell'.
    joint                        — 'dovetail' | 'none' (тип шва між модулями).
    seam_clear, seam_tab_w, seam_tab_ratio, seam_spacing — параметри dovetail-шва.
"""
import math
from shapely.geometry import Polygon, box as _box
from shapely.ops import unary_union

from mesh_engine import MeshData, extrude_polygon_with_holes

MIN_CELL = 6.0


# ────────────────────────────── конфіг / розміри ──────────────────────────────
def default_config(outer_L=240.0, outer_W=160.0, outer_H=40.0, nx=4, ny=3,
                   wall=2.0, floor_t=0.0, bed_x=220.0, bed_y=220.0,
                   segment='none', joint='dovetail'):
    cw = auto_sizes(outer_L, nx, wall) or [MIN_CELL] * int(nx)
    rh = auto_sizes(outer_W, ny, wall) or [MIN_CELL] * int(ny)
    return {
        'outer_L': float(outer_L), 'outer_W': float(outer_W), 'outer_H': float(outer_H),
        'nx': int(nx), 'ny': int(ny), 'wall': float(wall), 'floor_t': float(floor_t),
        'col_widths': cw, 'row_heights': rh,
        'col_locked': [False] * int(nx), 'row_locked': [False] * int(ny),
        'bed_x': float(bed_x), 'bed_y': float(bed_y),
        'cut_x': [], 'cut_y': [],
        'segment': segment, 'joint': joint, 'seam_clear': 0.25,
        'seam_tab_w': 6.0, 'seam_tab_ratio': 1.6, 'seam_spacing': 40.0,
    }


def inner_total(outer, n, wall):
    return outer - wall * (int(n) + 1)


def auto_sizes(outer, n, wall):
    n = int(n)
    tot = inner_total(outer, n, wall)
    if n <= 0 or tot <= 0:
        return None
    return [tot / float(n)] * n


def redistribute(sizes, idx, new_val, outer, wall, min_cell=MIN_CELL):
    """Drawer-divider: задати sizes[idx]=new_val, поглинути дельту рештою
    пропорційно, зберегти суму (outer фіксований). Кламп до min_cell."""
    n = len(sizes)
    tot = inner_total(outer, n, wall)
    if n == 1:
        return [max(min_cell, tot)]
    hi = tot - min_cell * (n - 1)
    new_val = max(min_cell, min(new_val, hi))
    others_sum = sum(s for i, s in enumerate(sizes) if i != idx)
    remaining = tot - new_val
    out = []
    for i, s in enumerate(sizes):
        if i == idx:
            out.append(new_val)
        elif others_sum > 1e-9:
            out.append(max(min_cell, remaining * s / others_sum))
        else:
            out.append(remaining / (n - 1))
    # залишок (від клампів) віддаємо першій не-idx комірці, щоб сума була точна
    diff = tot - sum(out)
    for i in range(n):
        if i != idx:
            out[i] = round(out[i] + diff, 6)
            break
    return out


def redistribute_locked(sizes, idx, new_val, outer, wall, locked, min_cell=MIN_CELL):
    """Встановити sizes[idx]=new_val; locked комірки лишаються незмінними; дельту
    поглинають лише вільні (не locked і не idx). Сума = inner_total (outer фікс.)."""
    n = len(sizes)
    tot = inner_total(outer, n, wall)
    locked = (list(locked) + [False] * n)[:n]
    other_locked_sum = sum(s for i, s in enumerate(sizes) if locked[i] and i != idx)
    free = [i for i in range(n) if not locked[i] and i != idx]
    out = list(sizes)
    if not free:
        out[idx] = max(min_cell, tot - other_locked_sum)   # idx визначається залишком
        return out
    max_new = tot - other_locked_sum - min_cell * len(free)
    new_val = max(min_cell, min(new_val, max_new))
    free_target = tot - new_val - other_locked_sum
    free_sum = sum(sizes[i] for i in free)
    out[idx] = new_val
    for i in free:
        out[i] = max(min_cell, free_target * (sizes[i] / free_sum) if free_sum > 1e-9
                     else free_target / len(free))
    out[free[-1]] = round(out[free[-1]] + (tot - sum(out)), 6)
    return out


def rescale_free(sizes, new_outer, wall, locked, min_cell=MIN_CELL):
    """Під новий outer: locked комірки незмінні, вільні масштабуються пропорційно.
    Повертає None, якщо locked комірки не влізають у новий outer."""
    n = len(sizes)
    tot = inner_total(new_outer, n, wall)
    if tot <= 0:
        return None
    locked = (list(locked) + [False] * n)[:n]
    locked_sum = sum(s for i, s in enumerate(sizes) if locked[i])
    free = [i for i in range(n) if not locked[i]]
    if not free:
        s = sum(sizes)
        return [x * tot / s for x in sizes] if s > 1e-9 else auto_sizes(new_outer, n, wall)
    free_target = tot - locked_sum
    if free_target < min_cell * len(free) - 1e-6:
        return None
    free_sum = sum(sizes[i] for i in free)
    out = list(sizes)
    for i in free:
        out[i] = max(min_cell, free_target * (sizes[i] / free_sum) if free_sum > 1e-9
                     else free_target / len(free))
    out[free[-1]] = round(out[free[-1]] + (tot - sum(out)), 6)
    return out


def redistribute_locked_multi(sizes, targets, outer, wall, locked, min_cell=MIN_CELL):
    """targets: {idx: value}. Встановити кілька комірок одночасно (вони фіксовані для
    цієї операції), вільні поглинають решту. Зберігає суму = inner_total."""
    n = len(sizes)
    tot = inner_total(outer, n, wall)
    locked = (list(locked) + [False] * n)[:n]
    fixed = set(targets.keys()) | {i for i in range(n) if locked[i]}
    free = [i for i in range(n) if i not in fixed]
    out = list(sizes)
    for i, v in targets.items():
        if 0 <= i < n:
            out[i] = max(min_cell, v)
    if not free:
        return out
    fixed_sum = sum(out[i] for i in fixed)
    free_target = tot - fixed_sum
    free_sum = sum(sizes[i] for i in free)
    for i in free:
        out[i] = max(min_cell, free_target * (sizes[i] / free_sum) if free_sum > 1e-9
                     else free_target / len(free))
    out[free[-1]] = round(out[free[-1]] + (tot - sum(out)), 6)
    return out


def add_split(sizes, locked, index, ratio, min_cell=MIN_CELL):
    """Розділити комірку index на дві (за ratio 0..1). Сума не змінюється (outer фікс.).
    Повертає (new_sizes, new_locked, ok)."""
    n = len(sizes)
    if not (0 <= index < n) or sizes[index] < 2 * min_cell:
        return list(sizes), list(locked), False
    w = sizes[index]
    ratio = max(0.1, min(0.9, ratio))
    w1 = max(min_cell, min(w - min_cell, w * ratio))
    w2 = w - w1
    locked = (list(locked) + [False] * n)[:n]
    return (sizes[:index] + [round(w1, 4), round(w2, 4)] + sizes[index + 1:],
            locked[:index] + [False, False] + locked[index + 1:], True)


def remove_line(sizes, locked, index, min_cell=MIN_CELL):
    """Видалити комірку index, додавши її розмір до сусідньої. (new_sizes, new_locked, ok)."""
    n = len(sizes)
    if n <= 1 or not (0 <= index < n):
        return list(sizes), list(locked), False
    locked = (list(locked) + [False] * n)[:n]
    out = list(sizes); ol = list(locked)
    w = out.pop(index); ol.pop(index)
    nb = index - 1 if index > 0 else 0
    out[nb] = round(out[nb] + w, 4)
    return out, ol, True


def resize_outer(sizes, new_outer, wall):
    """Перерахувати внутрішні розміри під новий outer (пропорційно)."""
    n = len(sizes)
    tot = inner_total(new_outer, n, wall)
    if tot <= 0:
        return None
    s = sum(sizes)
    if s <= 1e-9:
        return auto_sizes(new_outer, n, wall)
    return [x * tot / s for x in sizes]


def _intervals(sizes, wall):
    cav = []
    x = wall
    for s in sizes:
        a = x
        b = x + s
        cav.append((round(a, 4), round(b, 4)))
        x = b + wall
    return cav, round(x, 4)


def _groups(sizes, wall, bed, mode, cuts=None):
    n = len(sizes)
    if mode == 'per_cell':
        return [(i, i) for i in range(n)]
    if mode == 'manual':
        cut_set = sorted({int(c) for c in (cuts or []) if 0 < int(c) < n})
        groups, start = [], 0
        for c in cut_set:
            groups.append((start, c - 1))
            start = c
        groups.append((start, n - 1))
        return groups
    if mode != 'bed' or not bed or bed <= 0:
        return [(0, n - 1)]
    cav, _ = _intervals(sizes, wall)
    groups = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n:
            span = (cav[j + 1][1] + wall) - (cav[i][0] - wall)
            if span <= bed + 1e-6:
                j += 1
            else:
                break
        groups.append((i, j))
        i = j + 1
    return groups


def layout_info(config):
    wall = config['wall']
    cw = config['col_widths']
    rh = config['row_heights']
    nx, ny = len(cw), len(rh)
    outer_L = round(sum(cw) + wall * (nx + 1), 4)
    outer_W = round(sum(rh) + wall * (ny + 1), 4)
    cav_x, _ = _intervals(cw, wall)
    cav_y, _ = _intervals(rh, wall)
    seg = config.get('segment', 'none')
    cg = _groups(cw, wall, config.get('bed_x', 0), seg, config.get('cut_x'))
    rg = _groups(rh, wall, config.get('bed_y', 0), seg, config.get('cut_y'))
    return {'outer_L': outer_L, 'outer_W': outer_W, 'cav_x': cav_x, 'cav_y': cav_y,
            'col_groups': cg, 'row_groups': rg, 'n_modules': len(cg) * len(rg),
            'nx': nx, 'ny': ny}


def summary_data(config):
    info = layout_info(config)
    return {'length': info['outer_L'], 'width': info['outer_W'],
            'height': config['outer_H']}


def validate(config):
    wall = config['wall']
    cw = config['col_widths']
    rh = config['row_heights']
    if wall <= 0:
        return False, "Товщина стінки має бути > 0"
    if not cw or not rh:
        return False, "Порожня сітка"
    if min(cw) < MIN_CELL - 1e-6 or min(rh) < MIN_CELL - 1e-6:
        return False, f"Ячейка < {MIN_CELL:.0f}мм — зменшіть к-сть або збільшіть габарит"
    ft = config.get('floor_t', 0) or 0
    if ft >= config['outer_H']:
        return False, "Дно товще/рівне висоті"
    return True, ""


# ────────────────────────────── dovetail-шви ──────────────────────────────
def _tabs_vertical(x_edge, y0, y1, depth, bw, tw, spacing, clear, direction):
    """Трапеції-зубці на вертикальному ребрі x=x_edge, вздовж Y; +X якщо direction=+1."""
    L = y1 - y0
    n = max(1, int(round(L / spacing)))
    d = depth * direction
    out = []
    for k in range(n):
        yc = y0 + L * (k + 0.5) / n
        out.append(Polygon([
            (x_edge, yc - bw / 2 - clear),
            (x_edge + d, yc - tw / 2 - clear),
            (x_edge + d, yc + tw / 2 + clear),
            (x_edge, yc + bw / 2 + clear),
        ]))
    return out


def _tabs_horizontal(y_edge, x0, x1, depth, bw, tw, spacing, clear, direction):
    L = x1 - x0
    n = max(1, int(round(L / spacing)))
    d = depth * direction
    out = []
    for k in range(n):
        xc = x0 + L * (k + 0.5) / n
        out.append(Polygon([
            (xc - bw / 2 - clear, y_edge),
            (xc - tw / 2 - clear, y_edge + d),
            (xc + tw / 2 + clear, y_edge + d),
            (xc + bw / 2 + clear, y_edge),
        ]))
    return out


# ────────────────────────────── меш ──────────────────────────────
def _signed_area(c):
    a = 0.0
    n = len(c)
    for i in range(n):
        x0, y0 = c[i]
        x1, y1 = c[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a * 0.5


def _ccw(c):
    return c if _signed_area(c) > 0 else c[::-1]


def _cw(c):
    return c if _signed_area(c) < 0 else c[::-1]


def _poly_meshes(poly, height, z0, dx, dy):
    """Polygon (з отворами) / MultiPolygon → list[MeshData], зсунуті на (dx,dy)."""
    if poly is None or poly.is_empty or height <= 0:
        return []
    if poly.geom_type == 'Polygon':
        polys = [poly]
    else:
        polys = [g for g in poly.geoms
                 if getattr(g, 'geom_type', '') == 'Polygon' and not g.is_empty]
    meshes = []
    for p in polys:
        ext = _ccw([(px + dx, py + dy) for px, py in list(p.exterior.coords)[:-1]])
        holes = [_cw([(px + dx, py + dy) for px, py in list(r.coords)[:-1]])
                 for r in p.interiors]
        m = extrude_polygon_with_holes(ext, holes, height, z0=z0)
        if len(m.faces) > 0:
            meshes.append(m)
    return meshes


def build_modules(config):
    """Список модулів: {'mesh':MeshData,'color_idx':int,'cols':(c0,c1),'rows':(r0,r1),
    'bounds':(x0,y0,x1,y1)}. Геометрія центрована навколо (0,0), низ на z=0."""
    info = layout_info(config)
    wall = config['wall']
    cav_x, cav_y = info['cav_x'], info['cav_y']
    nx, ny = info['nx'], info['ny']
    outer_L, outer_W = info['outer_L'], info['outer_W']
    H = config['outer_H']
    ft = config.get('floor_t', 0) or 0.0
    joint = config.get('joint', 'dovetail')
    clr = config.get('seam_clear', 0.25)
    bw = config.get('seam_tab_w', 6.0)
    tw = bw * config.get('seam_tab_ratio', 1.6)
    sp = config.get('seam_spacing', 40.0)
    depth = wall * 0.5
    dx, dy = -outer_L / 2.0, -outer_W / 2.0

    modules = []
    cidx = 0
    for (c0, c1) in info['col_groups']:
        for (r0, r1) in info['row_groups']:
            x0 = cav_x[c0][0] - (wall if c0 == 0 else wall / 2.0)
            x1 = cav_x[c1][1] + (wall if c1 == nx - 1 else wall / 2.0)
            y0 = cav_y[r0][0] - (wall if r0 == 0 else wall / 2.0)
            y1 = cav_y[r1][1] + (wall if r1 == ny - 1 else wall / 2.0)
            shell = _box(x0, y0, x1, y1)

            male, female = [], []
            if joint == 'dovetail':
                if c1 < nx - 1:   # шов справа → male +X
                    male += _tabs_vertical(x1, y0, y1, depth, bw, tw, sp, 0.0, +1)
                if r1 < ny - 1:   # шов зверху → male +Y
                    male += _tabs_horizontal(y1, x0, x1, depth, bw, tw, sp, 0.0, +1)
                if c0 > 0:        # шов зліва → female (паз сусідського male)
                    female += _tabs_vertical(x0, y0, y1, depth, bw, tw, sp, clr, +1)
                if r0 > 0:        # шов знизу → female
                    female += _tabs_horizontal(y0, x0, x1, depth, bw, tw, sp, clr, +1)

            shell_m = shell if not male else unary_union([shell] + male)
            cavities = [_box(cav_x[c][0], cav_y[r][0], cav_x[c][1], cav_y[r][1])
                        for c in range(c0, c1 + 1) for r in range(r0, r1 + 1)]
            voids = cavities + female

            floor_poly = shell_m if not female else shell_m.difference(unary_union(female))
            walls_poly = shell_m.difference(unary_union(voids)) if voids else shell_m

            meshes = []
            if ft > 0:
                meshes += _poly_meshes(floor_poly, ft, 0.0, dx, dy)   # дно [0, ft]
            meshes += _poly_meshes(walls_poly, H, 0.0, dx, dy)         # стінки [0, H] (перекриття під дном — слайсер зварить)

            modules.append({
                'mesh': MeshData.combine(meshes),
                'color_idx': cidx,
                'cols': (c0, c1), 'rows': (r0, r1),
                'bounds': (x0 + dx, y0 + dy, x1 + dx, y1 + dy),
            })
            cidx += 1
    return modules
