import numpy as np
import time
import mapbox_earcut as earcut

def extrude_polygon(pts_2d, height):
    """
    Екструдування 2D-полігону (списку точок [x, y]) на задану висоту.
    Повертає verts (N, 3) і faces (M, 3).
    """
    pts = np.array(pts_2d, dtype=np.float32)
    N = len(pts)
    
    # 1. Триангуляція нижньої/верхньої граней (earcut)
    # Зверніть увагу: earcut приймає 2D масив координат для контурів
    rings = np.array([N], dtype=np.uint32)
    
    # Earcut повертає масив індексів трикутників
    triangles = earcut.triangulate_float32(pts, rings)
    triangles = triangles.reshape(-1, 3)
    
    # 2. Формуємо вершини 3D
    verts_bottom = np.column_stack((pts, np.zeros(N, dtype=np.float32)))
    verts_top = np.column_stack((pts, np.full(N, height, dtype=np.float32)))
    verts = np.vstack((verts_bottom, verts_top))
    
    # 3. Формуємо грані
    
    # Нижня грань (нормалі вниз, тому розвертаємо порядок обходу індексів)
    faces_bottom = triangles[:, ::-1]
    
    # Верхня грань (зсуваємо індекси на N)
    faces_top = triangles + N
    
    # Бокові грані (стягування периметру)
    # Для кожного ребра i -> (i+1)%N
    sides = []
    for i in range(N):
        nxt = (i + 1) % N
        # Два трикутники для прямокутної стінки
        # Тр 1: i(bottom), nxt(bottom), nxt(top)
        # Тр 2: i(bottom), nxt(top), i(top)
        sides.append([i, nxt, nxt + N])
        sides.append([i, nxt + N, i + N])
        
    faces_side = np.array(sides, dtype=np.int32)
    
    # Об'єднуємо всі грані
    faces = np.vstack((faces_bottom, faces_top, faces_side))
    
    return verts, faces

def test_speed():
    # Проста коробка (наприклад, 1000 вершин контуру)
    N = 1000
    r = 50.0
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False)
    pts_2d = np.column_stack((r * np.cos(angles), r * np.sin(angles)))
    
    print("Testing Custom Mesh Generator (earcut + numpy)...")
    start = time.time()
    for _ in range(500):
        verts, faces = extrude_polygon(pts_2d, 10.0)
    end = time.time()
    print(f"Time for 500 extrusions of {N}-vertex polygon: {end - start:.4f} seconds.")
    print(f"Generated {len(verts)} verts, {len(faces)} faces per box.")

if __name__ == '__main__':
    test_speed()
