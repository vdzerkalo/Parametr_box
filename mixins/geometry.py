import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtCore import Qt

from workers import GeometryWorker, MeshCache
from mesh_engine import extrude_polygon, offset_polygon_2d, MeshData
from shapely.geometry import Polygon
from shapely.ops import unary_union

class GeometryMixin:
    # -----------------------------------------------------------------------
    # Ініціалізація кешу та посилання на поточний воркер.
    # Викликається автоматично при першому використанні методів (lazy init).
    # -----------------------------------------------------------------------
    def _ensure_worker_infra(self):
        if not hasattr(self, '_mesh_cache'):
            self._mesh_cache = MeshCache(max_size=32)
        if not hasattr(self, '_active_worker'):
            self._active_worker = None
        if not hasattr(self, '_background_workers'):
            self._background_workers = []

    # Функція генерації базової коробки (завжди починається з (0,0,0) як центр XY)
    def create_box_geometry(self, length, width, height, tw_b, tw_t, t_d, clear, fillet, modes, parent_info=None, compound_parts=None, my_rel_x=0.0, my_rel_y=0.0):
        if parent_info is None: parent_info = {}
        
        def is_internal(tx, ty, side_name):
            if not compound_parts: return False
            for p in compound_parts:
                if p["rel_x"] == my_rel_x and -p["rel_y"] == my_rel_y: 
                    continue
                o_d = p["data"]
                o_rx = p["rel_x"]
                o_ry = -p["rel_y"]
                o_L = o_d.get("length", 100)
                o_W = o_d.get("width",  100)
                
                # Перевіряємо, чи інша частина знаходиться з потрібної сторони і чи перекриває вона tab
                if side_name == "top":
                    # Інша частина має бути зверху (її низ ~ ty) і перекривати по X
                    # Її низ: o_ry - o_W/2
                    if abs((o_ry - o_W/2) - ty) <= 1.5 and (o_rx - o_L/2 - 0.5 <= tx <= o_rx + o_L/2 + 0.5):
                        return True
                elif side_name == "bottom":
                    # Інша частина має бути знизу (її верх ~ ty) і перекривати по X
                    # Її верх: o_ry + o_W/2
                    if abs((o_ry + o_W/2) - ty) <= 1.5 and (o_rx - o_L/2 - 0.5 <= tx <= o_rx + o_L/2 + 0.5):
                        return True
                elif side_name == "right":
                    # Інша частина має бути справа (її лівий край ~ tx) і перекривати по Y
                    # Її лівий край: o_rx - o_L/2
                    if abs((o_rx - o_L/2) - tx) <= 1.5 and (o_ry - o_W/2 - 0.5 <= ty <= o_ry + o_W/2 + 0.5):
                        return True
                elif side_name == "left":
                    # Інша частина має бути зліва (її правий край ~ tx) і перекривати по Y
                    # Її правий край: o_rx + o_L/2
                    if abs((o_rx + o_L/2) - tx) <= 1.5 and (o_ry - o_W/2 - 0.5 <= ty <= o_ry + o_W/2 + 0.5):
                        return True
            return False

        # Метод генерації контуру (Polyline) за один прохід
        pts = []
        
        import math
        def rotate_pt(px, py, angle_deg):
            rad = math.radians(angle_deg)
            return (px * math.cos(rad) - py * math.sin(rad),
                    px * math.sin(rad) + py * math.cos(rad))

        def generate_edge_points(edge_len, mode, count, rot_angle, side_name):
            edge_pts = []
            
            if mode == 2 or count <= 0:
                # Пряма лінія, від кута до кута додаватиметься зовні
                return edge_pts
                
            is_female = (mode == 1)
            actual_base = tw_b + (clear*2 if is_female else 0)
            actual_tip = tw_t + (clear*2 if is_female else 0)
            actual_depth = t_d + (clear if is_female else 0)
            
            hw_b = actual_base / 2.0
            hw_t = actual_tip / 2.0
            
            # Напрямок Y для зубця
            dir_y = -actual_depth if is_female else actual_depth
            
            p_len = parent_info.get(f"side_{side_name}_parent_length", edge_len)
            p_count = int(parent_info.get(f"side_{side_name}_parent_count", count))
            p_offset = parent_info.get(f"side_{side_name}_parent_offset", 0.0)
            
            seg_len = p_len / (2 * p_count + 1)
            
            # Визначаємо напрямок перебору k та локальну координату px для кожної сторони,
            # щоб зберегти CCW-обхід полігону та правильну відповідність 2D-центрам.
            side_cfg = {
                "top":    {"k_range": range(p_count),      "px_func": lambda c: c},
                "right":  {"k_range": range(p_count),      "px_func": lambda c: c},
                "bottom": {"k_range": range(p_count-1, -1, -1), "px_func": lambda c: -c},
                "left":   {"k_range": range(p_count-1, -1, -1), "px_func": lambda c: -c}
            }
            cfg = side_cfg.get(side_name)
            
            for k in cfg["k_range"]:
                parent_center = -p_len/2 + seg_len * (2*k + 1.5)
                center = parent_center - p_offset
                px = cfg["px_func"](center)
                
                if -edge_len/2 - actual_base/2 <= center <= edge_len/2 + actual_base/2:
                    if side_name == "top":
                        tx, ty = my_rel_x + px, my_rel_y + width/2
                    elif side_name == "bottom":
                        tx, ty = my_rel_x - px, my_rel_y - width/2
                    elif side_name == "right":
                        tx, ty = my_rel_x + length/2, my_rel_y - px
                    elif side_name == "left":
                        tx, ty = my_rel_x - length/2, my_rel_y + px

                    if is_internal(tx, ty, side_name):
                        continue
                        
                    # 4 точки зубця: px тут - це центр зубця в локальній системі координат грані
                    t_pts = [
                        (px - hw_b, 0.0),
                        (px - hw_t, dir_y),
                        (px + hw_t, dir_y),
                        (px + hw_b, 0.0)
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
        # Порядок: Top (+Y) -> йде зліва направо (від -L/2 до L/2)
        # Отже почнемо з верхнього лівого кута і підемо ЗА годинниковою стрілкою
        
        # 1. Top Left -> Top Right (y = W/2, йдемо від -L/2 до L/2)
        pts.append((-length/2, width/2))
        top_pts = generate_edge_points(length, modes[0][0], modes[0][1], 0, "top")
        pts.extend(top_pts)
        
        # 2. Top Right -> Bottom Right (x = L/2, йдемо від W/2 до -W/2)
        pts.append((length/2, width/2))
        right_pts = generate_edge_points(width, modes[3][0], modes[3][1], -90, "right")
        pts.extend(right_pts)
        
        # 3. Bottom Right -> Bottom Left (y = -W/2, йдемо від L/2 до -L/2)
        pts.append((length/2, -width/2))
        bot_pts = generate_edge_points(length, modes[1][0], modes[1][1], 180, "bottom")
        pts.extend(bot_pts)
        
        # 4. Bottom Left -> Top Left (x = -L/2, йдемо від -W/2 до W/2)
        pts.append((-length/2, -width/2))
        left_pts = generate_edge_points(width, modes[2][0], modes[2][1], 90, "left")
        pts.extend(left_pts)
        
        # Гарантуємо CCW (Counter-Clockwise) для правильних нормалей екструзії
        pts = pts[::-1]
        
        # Скруглення (fillet) для зубців та пазів
        if fillet > 0.01:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            # Скруглення зовнішніх кутів (convex)
            poly = poly.buffer(fillet, join_style=1).buffer(-fillet, join_style=1)
            # Скруглення внутрішніх кутів (concave)
            poly = poly.buffer(-fillet, join_style=1).buffer(fillet, join_style=1)
            
            if not poly.is_empty:
                # Якщо після скруглення утворився MultiPolygon (наприклад, через мікро-острови),
                # беремо найбільший за площею полігон
                if poly.geom_type == 'MultiPolygon':
                    poly = max(poly.geoms, key=lambda p: p.area)
                
                if poly.geom_type == 'Polygon':
                    # Відтворюємо pts зі скругленого полігону
                    pts = list(poly.exterior.coords)[:-1]

        mesh = extrude_polygon(pts, height)
        mesh.translate(0, 0, -height/2)
        return mesh, pts

    def generate_geometry(self):
        L = self.len_input.value()
        W = self.wid_input.value()
        H = self.hei_input.value()
        
        tw_b = self.tab_wbase_input.value()
        tw_t = self.tab_wtip_input.value()
        t_d = self.tab_depth_input.value()
        clear = self.tab_clearance_input.value()
        fillet = self.tab_fillet_input.value()
        
        modes = (
            (self.side_top.currentIndex(), self.side_top_count.value()),
            (self.side_bottom.currentIndex(), self.side_bottom_count.value()),
            (self.side_left.currentIndex(), self.side_left_count.value()),
            (self.side_right.currentIndex(), self.side_right_count.value())
        )

        gen_lid = self.generate_lid_cb.isChecked()
        lid_tol = self.lid_tolerance_input.value()
        lid_ext = self.lid_extrusion_input.value()
        lid_h = self.lid_height_input.value()

        if tw_b <= 0 or tw_t <= 0 or t_d <= 0:
            raise ValueError("Розміри з'єднань повинні бути додатніми числами.")
        if L <= 0 or W <= 0 or H <= 0:
            raise ValueError("Розміри коробки повинні бути додатніми числами.")
        if fillet < 0:
            fillet = 0.0

        main_mesh, main_pts = self.create_box_geometry(L, W, H, tw_b, tw_t, t_d, clear, fillet, modes)
        main_mesh.translate(0, 0, H/2) # На площину Z=0
        
        assembly_meshes = [main_mesh]

        if gen_lid:
            bx = self.bed_x_input.value()
            by = self.bed_y_input.value()
            inset = lid_tol + lid_ext
            
            try:
                lid_pts = offset_polygon_2d(main_pts, -inset)
                if not lid_pts:
                    raise Exception("Offset is empty")
                lid_mesh = extrude_polygon(lid_pts, lid_h)
            except Exception as e:
                # Якщо offset2D не спрацює через надважкі геометричні помилки (наприклад завеликий зазор)
                raise ValueError(f"Не вдалося згенерувати внутрішню кришку. Завелике значення зазору/екструзії ({inset}мм) для поточних розмірів з'єднань.") from e
                
            # Розрахунок габаритів для автоматичного розміщення
            is_right_male = (modes[3][0] == 0)
            is_left_male = (modes[2][0] == 0)
            box_x_max = L/2 + (t_d if is_right_male else 0)
            box_x_min = -L/2 - (t_d if is_left_male else 0)
            
            is_top_male = (modes[0][0] == 0)
            is_bot_male = (modes[1][0] == 0)
            box_y_max = W/2 + (t_d if is_top_male else 0)
            box_y_min = -W/2 - (t_d if is_bot_male else 0)

            lid_x_span = L - inset*2
            lid_y_span = W - inset*2
            
            gap = 5.0
            total_x_span = (box_x_max - box_x_min) + gap + lid_x_span
            max_y_span = max(box_y_max - box_y_min, lid_y_span)
            
            if total_x_span <= bx and max_y_span <= by:
                self.is_single_bed = True
                self.bed_status_label.setText("Розміщення: Одне (Авто)")
                offset_x = box_x_max + gap + lid_x_span/2
                lid_mesh.translate(offset_x, 0, lid_h/2)
                assembly_meshes.append(lid_mesh)
                
                assembly_x_min = box_x_min
                assembly_x_max = offset_x + lid_x_span/2
                shift_x = -(assembly_x_min + assembly_x_max) / 2
                
                comp = MeshData.combine(assembly_meshes)
                comp.translate(shift_x, 0, 0)
                self.current_lid_offset_x = 0 
                self.update_grid()
                return comp, []
            else:
                self.is_single_bed = False
                self.bed_status_label.setText("Розміщення: Окремо")
                offset_x = bx + 40
                self.current_lid_offset_x = offset_x
                lid_mesh.translate(offset_x, 0, lid_h/2)
                assembly_meshes.append(lid_mesh)
                
                comp = MeshData.combine(assembly_meshes)
                self.update_grid()
                return comp, []
        else:
            self.is_single_bed = False
            self.bed_status_label.setText("Статус: Без кришки")
            self.update_grid()
            return main_mesh, []

    def generate_assembly_geometry(self):
        if not hasattr(self, 'placed_items') or not self.placed_items:
            return []
        
        return self._generate_assembly_from_params({"placed_items": self.placed_items})

    # -----------------------------------------------------------------------
    # Tessellate helper — виконується у фоновому потоці
    # -----------------------------------------------------------------------
    def _do_tessellate(self, shape, is_assembly):
        """Конвертує MeshData у numpy-масиви для pyqtgraph."""
        all_verts = []
        all_faces = []
        all_v_colors = []

        if is_assembly:
            if not isinstance(shape, list):
                shape = [(shape, 0)]
            for mesh, c_idx in shape:
                if not hasattr(mesh, 'verts') or len(mesh.verts) == 0:
                    continue
                v_offset = len(all_verts)
                color = self.assembly_palette[c_idx % len(self.assembly_palette)]
                
                v_len = len(mesh.verts)
                all_verts.extend(mesh.verts)
                all_v_colors.extend([color] * v_len)
                all_faces.extend(mesh.faces + v_offset)
        else:
            if hasattr(shape, 'verts') and len(shape.verts) > 0:
                all_verts.extend(shape.verts)
                all_faces.extend(shape.faces)

        verts_np  = np.array(all_verts, dtype=np.float32) if all_verts else np.zeros((0, 3), dtype=np.float32)
        faces_np  = np.array(all_faces, dtype=np.int32)   if all_faces else np.zeros((0, 3), dtype=np.int32)
        colors_np = np.array(all_v_colors, dtype=np.float32) if all_v_colors else None
        edges_np  = np.zeros((0, 3), dtype=np.float32)

        return verts_np, faces_np, colors_np, edges_np

    # -----------------------------------------------------------------------
    # Публічний метод generate_box — асинхронний, thread-safe
    # -----------------------------------------------------------------------
    def generate_box(self):
        self._ensure_worker_infra()

        # Скасувати попередній воркер, якщо ще виконується
        if self._active_worker is not None and self._active_worker.isRunning():
            self._active_worker.cancel()
            self._active_worker.quit()

        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()

        # ── Крок 1: захопити всі Qt-параметри В UI-ПОТОЦІ ──────────────────
        # generate_geometry() звертається до Qt-віджетів — тому ми
        # попередньо знімаємо всі значення тут, і передаємо у воркер чистий dict.
        if is_assembly:
            import copy
            params = {
                "mode": "assembly",
                "placed_items": copy.deepcopy(self.placed_items),
                "assembly_palette": list(self.assembly_palette),
            }
        else:
            params = {
                "mode": "single",
                "L": self.len_input.value(),
                "W": self.wid_input.value(),
                "H": self.hei_input.value(),
                "tw_b": self.tab_wbase_input.value(),
                "tw_t": self.tab_wtip_input.value(),
                "t_d":  self.tab_depth_input.value(),
                "clear": self.tab_clearance_input.value(),
                "fillet": self.tab_fillet_input.value(),
                "modes": (
                    (self.side_top.currentIndex(),    self.side_top_count.value()),
                    (self.side_bottom.currentIndex(), self.side_bottom_count.value()),
                    (self.side_left.currentIndex(),   self.side_left_count.value()),
                    (self.side_right.currentIndex(),  self.side_right_count.value()),
                ),
                "gen_lid": self.generate_lid_cb.isChecked(),
                "lid_tol": self.lid_tolerance_input.value(),
                "lid_ext": self.lid_extrusion_input.value(),
                "lid_h":   self.lid_height_input.value(),
                "bx":      self.bed_x_input.value(),
                "by":      self.bed_y_input.value(),
            }
            self.update_grid()  # Qt side-effect — безпечно тут

        # ── Перевірка кешу ────────────────────────────────────────────────
        self._current_cache_key = self._mesh_cache.make_key(params)
        cached = self._mesh_cache.get(self._current_cache_key)
        if cached is not None:
            self.statusBar().showMessage("⚡ Відновлено з кешу.")
            self._on_geometry_ready(*cached, is_assembly)
            return

        # ── Крок 2: важкі CadQuery-обчислення у фоновому потоці ────────────
        def _generate():
            """Виконується у QThread — лише CadQuery, жодних Qt-об'єктів."""
            if params["mode"] == "assembly":
                return self._generate_assembly_from_params(params), True
            else:
                return self._generate_single_from_params(params), False

        def _tessellate(shape, is_assembly_flag):
            return self._do_tessellate(shape, is_assembly_flag)

        worker = GeometryWorker(
            generate_func=_generate,
            tessellate_func=_tessellate,
            parent=self
        )
        self._background_workers.append(worker)
        worker.started_work.connect(self._on_worker_started)
        worker.result_ready.connect(self._on_geometry_ready)
        worker.error_occurred.connect(self._on_geometry_error)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        worker.finished.connect(worker.deleteLater)

        self._active_worker = worker
        worker.start()

    # -----------------------------------------------------------------------
    # Чисті CadQuery-функції (без Qt) — безпечні для фонового потоку
    # -----------------------------------------------------------------------
    def _generate_single_from_params(self, p):
        """Генерує одну коробку з dict параметрів. Без звернень до Qt."""
        L, W, H      = p["L"], p["W"], p["H"]
        tw_b, tw_t   = p["tw_b"], p["tw_t"]
        t_d, clear   = p["t_d"], p["clear"]
        fillet       = max(p["fillet"], 0.0)
        modes        = p["modes"]
        gen_lid      = p["gen_lid"]
        lid_tol, lid_ext, lid_h = p["lid_tol"], p["lid_ext"], p["lid_h"]
        bx, by       = p["bx"], p["by"]

        if tw_b <= 0 or tw_t <= 0 or t_d <= 0:
            raise ValueError("Розміри з'єднань повинні бути додатніми числами.")
        if L <= 0 or W <= 0 or H <= 0:
            raise ValueError("Розміри коробки повинні бути додатніми числами.")

        main_mesh, main_pts = self.create_box_geometry(L, W, H, tw_b, tw_t, t_d, clear, fillet, modes)
        main_mesh.translate(0, 0, H / 2)

        if not gen_lid:
            return main_mesh

        inset = lid_tol + lid_ext
        try:
            lid_pts = offset_polygon_2d(main_pts, -inset)
            if not lid_pts:
                raise Exception("Offset is empty")
            lid_mesh = extrude_polygon(lid_pts, lid_h)
        except Exception as e:
            raise ValueError(
                f"Не вдалося згенерувати внутрішню кришку. "
                f"Завелике значення зазору/екструзії ({inset}мм) для поточних розмірів з'єднань."
            ) from e

        is_right_male = (modes[3][0] == 0)
        is_left_male  = (modes[2][0] == 0)
        box_x_max = L / 2 + (t_d if is_right_male else 0)
        box_x_min = -L / 2 - (t_d if is_left_male else 0)

        is_top_male = (modes[0][0] == 0)
        is_bot_male = (modes[1][0] == 0)
        box_y_max = W / 2 + (t_d if is_top_male else 0)
        box_y_min = -W / 2 - (t_d if is_bot_male else 0)

        lid_x_span = L - inset * 2
        lid_y_span = W - inset * 2
        gap = 5.0
        total_x_span = (box_x_max - box_x_min) + gap + lid_x_span
        max_y_span   = max(box_y_max - box_y_min, lid_y_span)

        assembly_meshes = [main_mesh]

        if total_x_span <= bx and max_y_span <= by:
            offset_x = box_x_max + gap + lid_x_span / 2
            lid_mesh.translate(offset_x, 0, lid_h / 2)
            assembly_meshes.append(lid_mesh)
            assembly_x_min = box_x_min
            assembly_x_max = offset_x + lid_x_span / 2
            shift_x = -(assembly_x_min + assembly_x_max) / 2
            comp = MeshData.combine(assembly_meshes)
            comp.translate(shift_x, 0, 0)
            return comp
        else:
            offset_x = bx + 40
            lid_mesh.translate(offset_x, 0, lid_h / 2)
            assembly_meshes.append(lid_mesh)
            return MeshData.combine(assembly_meshes)

    def _generate_assembly_from_params(self, p):
        """Генерує геометрію збірки з dict параметрів. Без звернень до Qt."""
        
        placed_items = p["placed_items"]
        if not placed_items:
            return []
        items_with_colors = []
        for item in placed_items:
            rotation = item.get("rotation", 0)

            if item.get("type") == "compound":
                polygons = []
                H_main = 50
                for part in item.get("parts", []):
                    pdata = part["data"]
                    def pdget(key, default, _d=pdata): return _d.get(key, default)
                    H = pdget("height", 50)
                    H_main = H
                    L = pdget("length", 100)
                    W = pdget("width", 100)
                    _, box_pts = self.create_box_geometry(
                        length=L, width=W, height=H,
                        tw_b=pdget("tab_base", 20),
                        tw_t=pdget("tab_tip", 30),
                        t_d=pdget("tab_depth", 10),
                        clear=pdget("clearance", 0.0),
                        fillet=pdget("fillet", 0.0),
                        modes=(
                            (int(pdget("side_top", 0)), pdget("side_top_count", 1)),
                            (int(pdget("side_bottom", 1)), pdget("side_bottom_count", 1)),
                            (int(pdget("side_left", 1)), pdget("side_left_count", 1)),
                            (int(pdget("side_right", 0)), pdget("side_right_count", 1)),
                        ),
                        parent_info=pdata,
                        compound_parts=item.get("parts", []),
                        my_rel_x=part.get("rel_x", 0.0),
                        my_rel_y=-part.get("rel_y", 0.0)
                    )
                    rel_x = part.get("rel_x", 0.0)
                    rel_y = -part.get("rel_y", 0.0)
                    translated_pts = [(px + rel_x, py + rel_y) for px, py in box_pts]
                    
                    poly = Polygon(translated_pts)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    polygons.append(poly)
                    
                # Додаємо вузькі містки (bridges), щоб перекрити мікрощілини (clearance)
                # між сусідніми деталями, не спотворюючи зовнішні зубці функцією buffer()
                parts_list = item.get("parts", [])
                bridges = []
                for i in range(len(parts_list)):
                    for j in range(i + 1, len(parts_list)):
                        A = parts_list[i]
                        B = parts_list[j]
                        A_x, A_y = A.get("rel_x", 0.0), -A.get("rel_y", 0.0)
                        A_L, A_W = A.get("data", {}).get("length", 100), A.get("data", {}).get("width", 100)
                        B_x, B_y = B.get("rel_x", 0.0), -B.get("rel_y", 0.0)
                        B_L, B_W = B.get("data", {}).get("length", 100), B.get("data", {}).get("width", 100)
                        
                        minX_A, maxX_A = A_x - A_L/2, A_x + A_L/2
                        minY_A, maxY_A = A_y - A_W/2, A_y + A_W/2
                        minX_B, maxX_B = B_x - B_L/2, B_x + B_L/2
                        minY_B, maxY_B = B_y - B_W/2, B_y + B_W/2
                        
                        # Вертикальне сусідство
                        if abs(minY_A - maxY_B) <= 1.5 or abs(maxY_A - minY_B) <= 1.5:
                            minX_ab, maxX_ab = max(minX_A, minX_B), min(maxX_A, maxX_B)
                            if minX_ab < maxX_ab:
                                if abs(minY_A - maxY_B) <= 1.5:
                                    bridges.append(Polygon([(minX_ab, maxY_B - 0.75), (maxX_ab, maxY_B - 0.75), (maxX_ab, minY_A + 0.75), (minX_ab, minY_A + 0.75)]))
                                elif abs(maxY_A - minY_B) <= 1.5:
                                    bridges.append(Polygon([(minX_ab, maxY_A - 0.75), (maxX_ab, maxY_A - 0.75), (maxX_ab, minY_B + 0.75), (minX_ab, minY_B + 0.75)]))
                                    
                        # Горизонтальне сусідство
                        if abs(minX_A - maxX_B) <= 1.5 or abs(maxX_A - minX_B) <= 1.5:
                            minY_ab, maxY_ab = max(minY_A, minY_B), min(maxY_A, maxY_B)
                            if minY_ab < maxY_ab:
                                if abs(minX_A - maxX_B) <= 1.5:
                                    bridges.append(Polygon([(maxX_B - 0.75, minY_ab), (maxX_B - 0.75, maxY_ab), (minX_A + 0.75, maxY_ab), (minX_A + 0.75, minY_ab)]))
                                elif abs(maxX_A - minX_B) <= 1.5:
                                    bridges.append(Polygon([(maxX_A - 0.75, minY_ab), (maxX_A - 0.75, maxY_ab), (minX_B + 0.75, maxY_ab), (minX_B + 0.75, minY_ab)]))
                
                polygons.extend(bridges)

                if polygons:
                    # Тепер використовуємо звичайний union без buffer, бо мікрощілини закриті містками!
                    union_poly = unary_union(polygons)
                    
                    poly_list = []
                    if union_poly.geom_type == 'Polygon':
                        poly_list = [union_poly]
                    elif union_poly.geom_type == 'MultiPolygon':
                        poly_list = list(union_poly.geoms)
                        
                    parts_meshes = []
                    for poly in poly_list:
                        if poly.is_empty:
                            continue
                        merged_pts = list(poly.exterior.coords)[:-1]
                        mesh = extrude_polygon(merged_pts, H_main)
                        mesh.translate(0, 0, -H_main / 2)
                        parts_meshes.append(mesh)
                        
                    if parts_meshes:
                        compound_mesh = MeshData.combine(parts_meshes)
                        if rotation != 0:
                            compound_mesh.rotate_z(-rotation)
                        compound_mesh.translate(item["x"], -item["y"], H_main / 2)
                        items_with_colors.append((compound_mesh, item.get("color_idx", 0)))

            else:
                # ── Звичайна коробка ──────────────────────────────────────────
                data = item["data"]
                def dget(key, default): return data.get(key, default)
                box_mesh, _ = self.create_box_geometry(
                    length=dget("length", 100), width=dget("width", 100), height=dget("height", 50),
                    tw_b=dget("tab_base", 20), tw_t=dget("tab_tip", 30), t_d=dget("tab_depth", 10),
                    clear=dget("clearance", 0.0), fillet=dget("fillet", 0.0),
                    modes=(
                        (int(dget("side_top",    0)), dget("side_top_count",    1)),
                        (int(dget("side_bottom", 1)), dget("side_bottom_count", 1)),
                        (int(dget("side_left",   1)), dget("side_left_count",   1)),
                        (int(dget("side_right",  0)), dget("side_right_count",  1)),
                    ),
                    parent_info=data
                )
                H = dget("height", 50)
                if rotation != 0:
                    box_mesh.rotate_z(-rotation)
                box_mesh.translate(item["x"], -item["y"], H / 2)
                items_with_colors.append((box_mesh, item.get("color_idx", 0)))

        return items_with_colors


    # -----------------------------------------------------------------------
    # Слоти для сигналів воркера — виконуються в UI-потоці
    # -----------------------------------------------------------------------
    def _on_worker_started(self):
        self.statusBar().showMessage("⏳ Обчислення 3D моделі...")

    def _on_geometry_ready(self, shape, verts_np, faces_np, colors_np, edges_np, is_assembly):
        """Викликається у UI-потоці після завершення фонового обчислення."""
        self.current_shape = shape
        
        # Кешуємо результат
        if hasattr(self, '_current_cache_key') and self._current_cache_key:
            self._mesh_cache.put(self._current_cache_key, (shape, verts_np, faces_np, colors_np, edges_np))
            
        try:
            if verts_np is not None and len(verts_np) > 0:
                self.mesh_item.setMeshData(
                    vertexes=verts_np,
                    faces=faces_np,
                    vertexColors=colors_np
                )
                self.edge_item.setData(pos=edges_np if edges_np is not None and len(edges_np) > 0
                                       else np.zeros((0, 3), dtype=np.float32))
                if self.show_dims_cb.isChecked():
                    self.draw_dimensions(verts_np)
            else:
                self.mesh_item.setMeshData(
                    vertexes=np.zeros((0, 3), dtype=np.float32),
                    faces=np.zeros((0, 3), dtype=np.int32)
                )
                self.edge_item.setData(pos=np.zeros((0, 3), dtype=np.float32))
        except Exception as e:
            print(f"_on_geometry_ready error: {e}")

        # Оновити декорації (тексти осей, підписи) — легка операція
        self._update_decorations(is_assembly)

        # Зберегти стан для undo
        if hasattr(self, 'get_preset_dict'):
            self.last_state = self.get_preset_dict()

        self.statusBar().showMessage("✅ Успішно згенеровано!", 4000)

    def _on_geometry_error(self, error_msg):
        """Викликається у UI-потоці при помилці у воркері."""
        if "Розміри" in error_msg or "повинні" in error_msg:
            QMessageBox.warning(self, "Помилка Вводу",
                                error_msg + "\n(Можливо ви ввели текст замість числа)")
            self.statusBar().showMessage("Помилка вводу.", 5000)
        else:
            QMessageBox.critical(self, "Помилка Геометрії",
                                 f"Не вдалося згенерувати фігуру:\n{error_msg}")
            self.statusBar().showMessage("Помилка генерації.", 5000)

    def _cleanup_worker(self, worker):
        """Звільнити посилання на завершений воркер."""
        if hasattr(self, '_background_workers') and worker in self._background_workers:
            self._background_workers.remove(worker)
        if getattr(self, '_active_worker', None) is worker:
            self._active_worker = None

    def update_view(self):
        """Публічний метод-заглушка для сумісності. Просто перезапускає generate_box."""
        self.generate_box()

    def _update_decorations(self, is_assembly):
        """Оновлює легкі декорації (підписи осей). Завжди у UI-потоці."""
        # Видалити старі декорації
        for item in self.assembly_decorations:
            self.view.removeItem(item)
        self.assembly_decorations = []
        for item in self.dimension_items:
            self.view.removeItem(item)
        self.dimension_items = []

        # Перевірка чекбокса "Прибрати написи"
        hide_labels = getattr(self, 'hide_labels_cb', None)
        if hide_labels and hide_labels.isChecked():
            return

        if not is_assembly:
            L = self.len_input.value()
            W = self.wid_input.value()
            H = self.hei_input.value()
            side_positions = [
                (0, W/2 + 5, H, "+Y"),
                (0, -W/2 - 5, H, "-Y"),
                (-L/2 - 5, 0, H, "-X"),
                (L/2 + 5, 0, H, "+X")
            ]
            for sx, sy, sz, stxt in side_positions:
                txt = gl.GLTextItem(text=stxt, pos=(sx, sy, sz), color=(255, 200, 0, 255))
                self.view.addItem(txt)
                self.assembly_decorations.append(txt)
        else:
                for item in self.placed_items:
                    data = item["data"]
                    ox, oy = item["x"], -item["y"]
                    L = data.get("length", 100)
                    W = data.get("width", 100)
                    H = data.get("height", 50)
                    side_labels = [
                        (ox, oy + W/2 + 5, H, "+Y"),
                        (ox, oy - W/2 - 5, H, "-Y"),
                        (ox - L/2 - 5, oy, H, "-X"),
                        (ox + L/2 + 5, oy, H, "+X")
                    ]
                    for sx, sy, sz, stxt in side_labels:
                        stxt_item = gl.GLTextItem(text=stxt, pos=(sx, sy, sz), color=(255, 200, 0, 255))
                        self.view.addItem(stxt_item)
                        self.assembly_decorations.append(stxt_item)
                    ax = gl.GLAxisItem()
                    ax.setSize(x=30, y=30, z=30)
                    ax.translate(ox, oy, H)
                    self.view.addItem(ax)
                    self.assembly_decorations.append(ax)
                    name_txt = gl.GLTextItem(text=item["name"], pos=(ox, oy, H + 15), color=(255, 255, 255, 255))
                    self.view.addItem(name_txt)
                    self.assembly_decorations.append(name_txt)

    def draw_dimensions(self, verts):
        if len(verts) == 0: return
        
        vmin = verts.min(axis=0)
        vmax = verts.max(axis=0)
        size = vmax - vmin
        
        # Offset to draw lines outside the object
        off = 20.0
        
        # X Dimension (Length) - bottom front
        p1 = [vmin[0], vmin[1] - off, vmin[2]]
        p2 = [vmax[0], vmin[1] - off, vmin[2]]
        self.add_dim_arrow(p1, p2, f"{size[0]:.1f}")
        
        # Y Dimension (Width) - left bottom
        p1 = [vmin[0] - off, vmin[1], vmin[2]]
        p2 = [vmin[0] - off, vmax[1], vmin[2]]
        self.add_dim_arrow(p1, p2, f"{size[1]:.1f}")
        
        # Z Dimension (Height) - back right
        p1 = [vmax[0] + off, vmax[1], vmin[2]]
        p2 = [vmax[0] + off, vmax[1], vmax[2]]
        self.add_dim_arrow(p1, p2, f"{size[2]:.1f}")

    def add_dim_arrow(self, p1, p2, label):
        # Main line
        line = gl.GLLinePlotItem(pos=np.array([p1, p2]), color=(1, 1, 0, 1), width=2, antialias=True)
        self.view.addItem(line)
        self.dimension_items.append(line)
        
        # End ticks
        v = np.array(p2) - np.array(p1)
        dist = np.linalg.norm(v)
        if dist < 0.001: return
        
        tick_size = 5.0
        # For simplicity, just horizontal/vertical ticks
        # X-aligned
        if abs(v[0]) > abs(v[1]) and abs(v[0]) > abs(v[2]):
            t1 = [ [p1[0], p1[1]-tick_size, p1[2]], [p1[0], p1[1]+tick_size, p1[2]] ]
            t2 = [ [p2[0], p2[1]-tick_size, p2[2]], [p2[0], p2[1]+tick_size, p2[2]] ]
        # Y-aligned
        elif abs(v[1]) > abs(v[0]) and abs(v[1]) > abs(v[2]):
            t1 = [ [p1[0]-tick_size, p1[1], p1[2]], [p1[0]+tick_size, p1[1], p1[2]] ]
            t2 = [ [p2[0]-tick_size, p2[1], p2[2]], [p2[0]+tick_size, p2[1], p2[2]] ]
        # Z-aligned
        else:
            t1 = [ [p1[0]-tick_size, p1[1], p1[2]], [p1[0]+tick_size, p1[1], p1[2]] ]
            t2 = [ [p2[0]-tick_size, p2[1], p2[2]], [p2[0]+tick_size, p2[1], p2[2]] ]
            
        tick_item1 = gl.GLLinePlotItem(pos=np.array(t1), color=(1, 1, 0, 1), width=2)
        tick_item2 = gl.GLLinePlotItem(pos=np.array(t2), color=(1, 1, 0, 1), width=2)
        self.view.addItem(tick_item1)
        self.view.addItem(tick_item2)
        self.dimension_items.append(tick_item1)
        self.dimension_items.append(tick_item2)

    def _ruler_mouse_press(self, ev):
        if ev.button() == Qt.RightButton:
            self.ruler_btn.setChecked(False) # Це викличе update_ruler_mode і очистить все
            return

        if ev.button() == Qt.LeftButton:
            if not hasattr(self, '_ruler_points'): self._ruler_points = []
            if not hasattr(self, '_ruler_items'): self._ruler_items = []
            
            # 1. Get 3D hit point
            ro, rd = self.compute_ray(ev.position().x(), ev.position().y())
            pos = self.ray_hit_plane_z(ro, rd, 0) # Base at Z=0
            
            # Покращення: Перевірка чи ми попали в деталь (пріоритет вершкам/площинам)
            # В даній версії обмежимося Z=0 для стабільності, або спробуємо знайти Z висоту
            if pos is None: return
            
            hit_pt = np.array([pos[0], pos[1], 0.0])
            
            if len(self._ruler_points) >= 2:
                # Починаємо новий вимір
                for it in self._ruler_items: self.view.removeItem(it)
                self._ruler_items = []
                self._ruler_points = [hit_pt]
            else:
                self._ruler_points.append(hit_pt)
                
            if len(self._ruler_points) == 2:
                self.statusBar().showMessage(f"📐 Відстань: {np.linalg.norm(self._ruler_points[1] - self._ruler_points[0]):.2f} мм")
            else:
                self.statusBar().showMessage("📐 Оберіть другу точку...")

    def _ruler_mouse_move(self, ev):
        if not hasattr(self, '_ruler_points') or len(self._ruler_points) == 0: return
        if len(self._ruler_points) >= 2 and not (ev.buttons() & Qt.LeftButton): return # Вже фіксовано
        
        # Динамічне оновлення лінії при русі
        ro, rd = self.compute_ray(ev.position().x(), ev.position().y())
        pos = self.ray_hit_plane_z(ro, rd, 0)
        if pos is None: return
        curr_pt = np.array([pos[0], pos[1], 0.0])
        
        p1 = self._ruler_points[0]
        p2 = curr_pt
        dist = np.linalg.norm(p2 - p1)
        
        # Створюємо/оновлюємо візуалізацію
        if not hasattr(self, '_ruler_items'): self._ruler_items = []
        for it in self._ruler_items: 
            try: self.view.removeItem(it)
            except: pass
        self._ruler_items = []
        
        # Лінія
        line = gl.GLLinePlotItem(pos=np.array([p1, p2]), color=(1, 1, 0, 1), width=2, antialias=True)
        line.setGLOptions('translucent')
        self.view.addItem(line)
        self._ruler_items.append(line)
        
        # Точки на кінцях
        pts = gl.GLScatterPlotItem(pos=np.array([p1, p2]), color=(1, 0.5, 0, 1), size=5)
        self.view.addItem(pts)
        self._ruler_items.append(pts)
        
        # Текст (спробуємо використати GLTextItem якщо доступний, інакше статус бар)
        try:
            mid = (p1 + p2) / 2
            txt = gl.GLTextItem(pos=mid, text=f"{dist:.1f} mm", color=(255, 255, 255, 255))
            self.view.addItem(txt)
            self._ruler_items.append(txt)
        except:
            pass
            
        self.statusBar().showMessage(f"📐 Вимірювання: {dist:.1f} мм")

    def export_file(self, fmt):
        if self.current_shape is None:
            QMessageBox.warning(self, "Помилка експорту", "Спочатку згенеруйте 3D фігуру.")
            return
            
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        
        if fmt == "step":
            QMessageBox.warning(self, "STEP не підтримується", "Новий Mesh-рушій працює виключно з даними для 3D друку (STL/OBJ). Експорт до STEP (соліди) наразі недоступний.")
            return
        else:
            filter_str = "STL Files (*.stl)"
            ext = ".stl"

        default_name = "assembly" if is_assembly else "box_export"
        if is_assembly and hasattr(self, 'placed_items') and self.placed_items:
            if len(self.placed_items) == 1:
                default_name = self.placed_items[0].get("name", "assembly")
            else:
                default_name = "assembly_export"
                
        # sanitize default_name
        import re
        default_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', default_name)

        path, _ = QFileDialog.getSaveFileName(self, "Зберегти файл", default_name + ext, filter_str)
        if not path:
            return
            
        try:
            verts, faces = [], []
            if is_assembly:
                if isinstance(self.current_shape, list):
                    meshes = [s[0] for s in self.current_shape]
                    combined = MeshData.combine(meshes)
                    verts = combined.verts
                    faces = combined.faces
                else:
                    verts = self.current_shape.verts
                    faces = self.current_shape.faces
            else:
                verts = self.current_shape.verts
                faces = self.current_shape.faces
                
            if len(faces) > 0:
                with open(path, 'w') as f:
                    import os
                    model_name = os.path.basename(path).replace('.stl', '')
                    f.write(f"solid {model_name}\n")
                    import math
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
                    f.write(f"endsolid {model_name}\n")
                QMessageBox.information(self, "Успіх", f"Успішно збережено у {path}")
            else:
                 QMessageBox.warning(self, "Помилка", "Немає полігонів для експорту.")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти файл:\n{str(e)}")
