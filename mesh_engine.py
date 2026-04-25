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
