import time
import math
import cadquery as cq

def create_box_geometry_old(length, width, height, tw_b, tw_t, t_d, clear, fillet, modes):
    box = cq.Workplane("XY").box(length, width, height)

    def apply_tab(base_body, side, count, is_female):
        actual_base = tw_b + (clear*2 if is_female else 0)
        actual_tip = tw_t + (clear*2 if is_female else 0)
        actual_depth = t_d + (clear if is_female else 0)

        # Build tab 2D
        hw_b = actual_base / 2.0
        hw_t = actual_tip / 2.0
        ext = max(fillet * 2.5, 2.0)
        tab_sketch = cq.Workplane("XY").sketch().polygon([
            (-hw_b, -ext), (-hw_b, 0.0), (-hw_t, actual_depth),
            (hw_t, actual_depth), (hw_b, 0.0), (hw_b, -ext)
        ])
        if fillet > 0.0:
            try: tab_sketch = tab_sketch.vertices().fillet(fillet)
            except Exception: pass
        tab_sketch = tab_sketch.finalize()
        
        tab_3d = tab_sketch.extrude(height).translate((0, 0, -height/2))

        if is_female:
            tab_3d = tab_3d.rotate((0,0,0), (0,0,1), 180)

        edge_len = length if side in ["top", "bottom"] else width
        seg_len = edge_len / (2 * count + 1)
        
        tabs = cq.Workplane("XY")
        tabs_added = 0
        for k in range(count):
            center = -edge_len/2 + seg_len * (2*k + 1)
            t = tab_3d
            
            if side == "top":
                t = t.translate((center, width/2, 0))
            elif side == "bottom":
                t = t.rotate((0,0,0), (0,0,1), 180).translate((center, -width/2, 0))
            elif side == "left":
                t = t.rotate((0,0,0), (0,0,1), 90).translate((-length/2, center, 0))
            elif side == "right":
                t = t.rotate((0,0,0), (0,0,1), -90).translate((length/2, center, 0))
            
            tabs.add(t)
            tabs_added += 1
                
        if tabs_added == 0:
            return base_body
            
        tabs = tabs.combine()
        
        if is_female:
            return base_body.cut(tabs)
        else:
            return base_body.union(tabs)

    box = apply_tab(box, "top", modes[0][1], modes[0][0] == 1)
    box = apply_tab(box, "bottom", modes[1][1], modes[1][0] == 1)
    box = apply_tab(box, "left", modes[2][1], modes[2][0] == 1)
    box = apply_tab(box, "right", modes[3][1], modes[3][0] == 1)
    
    return box

def create_box_geometry_points(length, width, height, tw_b, tw_t, t_d, clear, fillet, modes):
    # Метод генерації контуру (Polyline) за один прохід
    pts = []
    
    # helper для повороту точки
    def rotate_pt(px, py, angle_deg):
        rad = math.radians(angle_deg)
        return (px * math.cos(rad) - py * math.sin(rad),
                px * math.sin(rad) + py * math.cos(rad))

    def generate_edge_points(edge_len, mode, count, rot_angle):
        # Генерує точки для сторони від -edge_len/2 до edge_len/2 на осі X (y=0)
        edge_pts = []
        
        if mode == 2 or count <= 0:
            # Пряма лінія, лише точки кутів додамо пізніше
            return edge_pts
            
        is_female = (mode == 1)
        actual_base = tw_b + (clear*2 if is_female else 0)
        actual_tip = tw_t + (clear*2 if is_female else 0)
        actual_depth = t_d + (clear if is_female else 0)
        
        hw_b = actual_base / 2.0
        hw_t = actual_tip / 2.0
        
        # Напрямок Y для зубця
        dir_y = -actual_depth if is_female else actual_depth
        
        seg_len = edge_len / (2 * count + 1)
        
        for k in range(count):
            center = -edge_len/2 + seg_len * (2*k + 1)
            
            # 4 точки зубця: початок основи, початок вершини, кінець вершини, кінець основи
            t_pts = [
                (center - hw_b, 0.0),
                (center - hw_t, dir_y),
                (center + hw_t, dir_y),
                (center + hw_b, 0.0)
            ]
            edge_pts.extend(t_pts)
            
        # Трансформація точок на відповідну сторону
        final_pts = []
        for px, py in edge_pts:
            # Зсув на край
            py += width/2 if rot_angle in [0, 180] else length/2
            # Поворот
            fx, fy = rotate_pt(px, py, rot_angle)
            final_pts.append((fx, fy))
            
        return final_pts

    # Кутові точки і сторони
    # Порядок: Top (+Y), Left (-X), Bottom (-Y), Right (+X) - проти годинникової
    # Точки:
    # 1. Top Right (L/2, W/2) -> йдемо вліво до (-L/2, W/2) [Top edge, rot 0]
    pts.append((length/2, width/2))
    
    # Генеруємо Top edge (від X=L/2 до X=-L/2, але функція генерує зліва направо, тому ми маємо її розвернути, 
    # або генерувати правильно від початку. Простіше генерувати від -L/2 до L/2 і розвернути порядок)
    top_pts = generate_edge_points(length, modes[0][0], modes[0][1], 0)
    pts.extend(reversed(top_pts)) # reversed тому що ми йдемо справа наліво
    
    pts.append((-length/2, width/2))
    
    # Left edge (від Y=W/2 до Y=-W/2)
    left_pts = generate_edge_points(width, modes[2][0], modes[2][1], 90)
    pts.extend(reversed(left_pts))
    
    pts.append((-length/2, -width/2))
    
    # Bottom edge (від X=-L/2 до X=L/2)
    bot_pts = generate_edge_points(length, modes[1][0], modes[1][1], 180)
    pts.extend(reversed(bot_pts))
    
    pts.append((length/2, -width/2))
    
    # Right edge (від Y=-W/2 до Y=W/2)
    right_pts = generate_edge_points(width, modes[3][0], modes[3][1], 270)
    pts.extend(reversed(right_pts))
    
    # Закриваємо полігон
    wp = cq.Workplane("XY").polyline(pts).close()
    return wp.extrude(height).translate((0,0,-height/2))

def test_speed():
    L, W, H = 100, 100, 50
    tw_b, tw_t, t_d = 20, 15, 10
    clear = 0.3
    fillet = 0.0 # Для цього тесту пропускаємо скруглення, щоб об'єктивно порівняти Boolean vs Polyline
    
    modes = [(0, 5), (1, 5), (0, 5), (1, 5)]
    
    print("Testing OLD method (3D Boolean operations)...")
    start = time.time()
    for _ in range(5):
        box_old = create_box_geometry_old(L, W, H, tw_b, tw_t, t_d, clear, fillet, modes)
    old_time = time.time() - start
    print(f"OLD method took: {old_time:.4f} seconds (for 5 boxes)")
    
    print("\nTesting NEW method (2D Polyline + Extrude)...")
    start = time.time()
    for _ in range(5):
        box_new = create_box_geometry_points(L, W, H, tw_b, tw_t, t_d, clear, fillet, modes)
    new_time = time.time() - start
    print(f"NEW method took: {new_time:.4f} seconds (for 5 boxes)")
    
    print(f"\nSpeedup: {old_time / new_time:.2f}x")

if __name__ == '__main__':
    test_speed()
