import numpy as np
import mapbox_earcut as earcut
from shapely.geometry import Polygon
import math

class MeshData:
    def __init__(self, verts, faces):
        self.verts = np.array(verts, dtype=np.float32) if len(verts) > 0 else np.zeros((0,3), dtype=np.float32)
        self.faces = np.array(faces, dtype=np.int32) if len(faces) > 0 else np.zeros((0,3), dtype=np.int32)
        
    def translate(self, dx, dy, dz):
        if len(self.verts) > 0:
            self.verts += np.array([dx, dy, dz], dtype=np.float32)
        return self
        
    def rotate_z(self, angle_deg):
        if len(self.verts) > 0:
            rad = math.radians(angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            
            x = self.verts[:, 0]
            y = self.verts[:, 1]
            
            new_x = x * cos_a - y * sin_a
            new_y = x * sin_a + y * cos_a
            
            self.verts[:, 0] = new_x
            self.verts[:, 1] = new_y
        return self

    @classmethod
    def combine(cls, meshes):
        if not meshes:
            return cls([], [])
            
        all_verts = []
        all_faces = []
        v_offset = 0
        
        for m in meshes:
            if len(m.verts) == 0:
                continue
            all_verts.append(m.verts)
            all_faces.append(m.faces + v_offset)
            v_offset += len(m.verts)
            
        if not all_verts:
            return cls([], [])
            
        return cls(np.vstack(all_verts), np.vstack(all_faces))


def extrude_polygon(pts_2d, height):
    """
    Екструдує 2D контур у 3D Mesh.
    pts_2d: список або масив точок [[x,y], ...]
    Повертає MeshData.
    """
    pts = np.array(pts_2d, dtype=np.float32)
    N = len(pts)
    if N < 3:
        return MeshData([], [])
        
    rings = np.array([N], dtype=np.uint32)
    
    # mapbox_earcut приймає numpy масив точок (N, 2)
    triangles = earcut.triangulate_float32(pts, rings)
    triangles = triangles.reshape(-1, 3)
    
    verts_bottom = np.column_stack((pts, np.zeros(N, dtype=np.float32)))
    verts_top = np.column_stack((pts, np.full(N, height, dtype=np.float32)))
    verts = np.vstack((verts_bottom, verts_top))
    
    # Нижня грань
    faces_bottom = triangles[:, ::-1]
    
    # Верхня грань 
    faces_top = triangles + N
    
    # Бокові грані (квади з розбиттям на 2 трикутники)
    sides = []
    for i in range(N):
        nxt = (i + 1) % N
        sides.append([i, nxt, nxt + N])
        sides.append([i, nxt + N, i + N])
        
    faces_side = np.array(sides, dtype=np.int32)
    
    faces = np.vstack((faces_bottom, faces_top, faces_side))
    return MeshData(verts, faces)


def extrude_polygon_with_holes(exterior, holes, height, z0=0.0):
    """Екструдує 2D-контур з отворами (внутрішніми кільцями) у 3D Mesh.

    exterior: список точок зовнішнього кільця [[x,y], ...] (CCW).
    holes: список кілець-отворів, кожне — список точок (CW).
    height: висота екструзії; z0: нижня площина (за замовч. 0).
    Дає замкнену оболонку: нижня грань (з отворами), верхня, бічні стінки
    зовнішнього кільця та кожного отвору. Повертає MeshData.
    """
    ext = np.asarray(exterior, dtype=np.float32)
    if len(ext) < 3:
        return MeshData([], [])

    all_pts = [ext]
    rings = [len(ext)]
    for h in (holes or []):
        h = np.asarray(h, dtype=np.float32)
        if len(h) < 3:
            continue
        all_pts.append(h)
        rings.append(rings[-1] + len(h))

    pts = np.concatenate(all_pts, axis=0)
    rings_np = np.array(rings, dtype=np.uint32)

    triangles = earcut.triangulate_float32(pts, rings_np)
    if len(triangles) == 0:
        return MeshData([], [])
    triangles = triangles.reshape(-1, 3)

    N = len(pts)
    verts_bottom = np.column_stack((pts, np.full(N, z0, dtype=np.float32)))
    verts_top = np.column_stack((pts, np.full(N, z0 + height, dtype=np.float32)))
    verts = np.vstack((verts_bottom, verts_top))

    faces_bottom = triangles[:, ::-1]   # нормаль вниз
    faces_top = triangles + N           # нормаль вгору

    # Бічні стінки — окремо для кожного кільця (замикання в межах кільця)
    sides = []
    start = 0
    for end in rings:
        cnt = end - start
        for k in range(cnt):
            i = start + k
            nxt = start + ((k + 1) % cnt)
            sides.append([i, nxt, nxt + N])
            sides.append([i, nxt + N, i + N])
        start = end

    faces_side = np.array(sides, dtype=np.int32)
    faces = np.vstack((faces_bottom, faces_top, faces_side))
    return MeshData(verts, faces)


def offset_polygon_2d(pts_2d, offset_distance):
    """
    Створює внутрішній полігон (offset_distance < 0) за допомогою Shapely.
    Повертає новий список точок. Якщо результат вироджується - повертає порожній список.
    """
    if len(pts_2d) < 3:
        return []
    
    # shapely потребує замкненого контуру, але Polygon(pts) автоматично замикає
    poly = Polygon(pts_2d)
    if not poly.is_valid:
        poly = poly.buffer(0)
        
    # Робимо зсув
    offset_poly = poly.buffer(offset_distance, join_style=2) # 2 = mitre / flat
    
    if offset_poly.is_empty:
        return []
        
    # Якщо зсув утворив кілька полігонів (MultiPolygon), беремо найбільший
    if offset_poly.geom_type == 'MultiPolygon':
        offset_poly = max(offset_poly.geoms, key=lambda a: a.area)
        
    if offset_poly.geom_type != 'Polygon':
        return []
        
    # Повертаємо координати зовнішнього кільця (без останньої точки, яка дублює першу)
    coords = list(offset_poly.exterior.coords)[:-1]
    return coords


def write_ascii_stl(path, verts, faces, name="model"):
    """Записує ASCII STL з масивів вершин/граней. Спільний хелпер для
    одиночного та пакетного експорту (mesh-рушій не використовує cadquery)."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"solid {name}\n")
        for face in faces:
            v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
            ux, uy, uz = v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]
            vx, vy, vz = v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]
            nx = uy*vz - uz*vy
            ny = uz*vx - ux*vz
            nz = ux*vy - uy*vx
            l = math.sqrt(nx*nx + ny*ny + nz*nz) + 1e-9
            nx, ny, nz = nx/l, ny/l, nz/l
            f.write(f"  facet normal {nx} {ny} {nz}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {v0[0]} {v0[1]} {v0[2]}\n")
            f.write(f"      vertex {v1[0]} {v1[1]} {v1[2]}\n")
            f.write(f"      vertex {v2[0]} {v2[1]} {v2[2]}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write(f"endsolid {name}\n")
