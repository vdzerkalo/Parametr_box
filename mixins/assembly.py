import os
import json
import numpy as np
from PySide6.QtWidgets import QMessageBox, QInputDialog, QMenu, QFileDialog, QStyle, QDialog, QListWidgetItem
from PySide6.QtGui import QAction, QPixmap, QPainter, QPen, QColor, QIcon
from PySide6.QtCore import Qt, QRectF

from ui_widgets import SnapDialog
from puzzle_item import PuzzleBoxItem

class AssemblyMixin:
    def install_assembly_mouse_handlers(self):
        """Install mouse handlers for drag interaction on the 3D view."""
        self._orig_mousePressEvent   = self.view.mousePressEvent
        self._orig_mouseMoveEvent    = self.view.mouseMoveEvent
        self._orig_mouseReleaseEvent = self.view.mouseReleaseEvent
        self._orig_wheelEvent        = self.view.wheelEvent
        self.view.mousePressEvent   = self.assembly_mouse_press
        self.view.mouseMoveEvent    = self.assembly_mouse_move
        self.view.mouseReleaseEvent = self.assembly_mouse_release
        self.view.wheelEvent        = self.assembly_wheel_event

    def uninstall_assembly_mouse_handlers(self):
        """Restore original mouse handlers."""
        if hasattr(self, '_orig_mousePressEvent'):
            self.view.mousePressEvent   = self._orig_mousePressEvent
            self.view.mouseMoveEvent    = self._orig_mouseMoveEvent
            self.view.mouseReleaseEvent = self._orig_mouseReleaseEvent
        if hasattr(self, '_orig_wheelEvent'):
            self.view.wheelEvent = self._orig_wheelEvent
        self.view.unsetCursor()

    def assembly_wheel_event(self, ev):
        """In Puzzle mode block zoom; in View mode allow it."""
        if getattr(self, 'assem_submode', 'puzzle') == 'view':
            self._orig_wheelEvent(ev)
        else:
            ev.accept()

    def compute_ray(self, sx, sy):
        """Analytically compute camera ray through screen pixel (sx, sy).
        Returns (ray_origin, ray_direction) as tuples."""
        import math
        from PySide6.QtGui import QMatrix4x4, QVector3D
        opts = self.view.opts
        dist = opts['distance']
        azi  = opts['azimuth']
        ele  = opts['elevation']
        ctr  = opts.get('center', QVector3D(0,0,0))
        fov  = opts.get('fov', 60)
        
        w, h = self.view.width(), self.view.height()
        if w <= 0 or h <= 0: return None, None
        
        # 1. NDC to camera space ray (looking at -Z)
        aspect = w / h
        tan_f = math.tan(math.radians(fov/2.0))
        nx = (2.0 * sx / w) - 1.0
        ny = 1.0 - (2.0 * sy / h)
        ray_dir_cam = QVector3D(nx * tan_f * aspect, ny * tan_f, -1.0).normalized()
        
        # 2. Camera-to-World Matrix (Inverse of pyqtgraph View Matrix)
        m = QMatrix4x4()
        if hasattr(ctr, 'x'):
            m.translate(ctr.x(), ctr.y(), ctr.z())
        else:
            m.translate(ctr[0], ctr[1], ctr[2])
        m.rotate(-azi,     0, 0, 1)
        m.rotate(90 - ele, 1, 0, 0)
        m.translate(0, 0, dist)
        
        cam_pos = m.map(QVector3D(0,0,0))
        ray_target_world = m.map(ray_dir_cam)
        ray_dir_world = (ray_target_world - cam_pos).normalized()
        
        return (cam_pos.x(), cam_pos.y(), cam_pos.z()), (ray_dir_world.x(), ray_dir_world.y(), ray_dir_world.z())

    def ray_hit_plane_z(self, ro, rd, plane_z):
        """Intersect ray with z=plane_z. Returns (x, y) or None."""
        if ro is None or rd is None:
            return None
        dz = rd[2]
        if abs(dz) < 1e-8:
            return None
        t = (plane_z - ro[2]) / dz
        if t < 0:
            return None
        return ro[0] + t * rd[0], ro[1] + t * rd[1]

    def get_item_under_cursor(self, sx, sy):
        """Return index of placed item whose XY bounding box the cursor ray hits, or -1."""
        if not self.placed_items:
            return -1
        ro, rd = self.compute_ray(sx, sy)
        if ro is None:
            return -1
            
        # Iterate backwards to pick the top-most item if they overlap
        for i in range(len(self.placed_items) - 1, -1, -1):
            item = self.placed_items[i]
            H = item["data"].get("height", 50)
            hit = self.ray_hit_plane_z(ro, rd, H / 2)
            if hit is None:
                hit = self.ray_hit_plane_z(ro, rd, 0.0)
            if hit is None:
                continue
                
            hx, hy = hit
            
            def check_hit(it):
                ix, iy = it.get("x", 0.0), it.get("y", 0.0)
                if it.get("type") == "compound":
                    rot = it.get("rotation", 0)
                    rad = np.radians(rot)
                    for p in it.get("parts", []):
                        pd = p["data"]
                        rx, ry = p["rel_x"], p["rel_y"]
                        # Відносні координати частини повернуті разом з об'єктом
                        rot_rx = rx * np.cos(rad) - ry * np.sin(rad)
                        rot_ry = rx * np.sin(rad) + ry * np.cos(rad)
                        gx, gy = ix + rot_rx, iy + rot_ry
                        
                        L, W = pd.get("length", 100), pd.get("width", 100)
                        if rot in [90, 270]:
                            L, W = W, L
                        if (gx - L/2 <= hx <= gx + L/2) and (gy - W/2 <= hy <= gy + W/2):
                            return True
                    return False
                else:
                    data = it["data"]
                    rot = it.get("rotation", 0)
                    if rot in [90, 270]:
                        L, W = data.get("width", 100), data.get("length", 100)
                    else:
                        L, W = data.get("length", 100), data.get("width", 100)
                    return (ix - L/2 <= hx <= ix + L/2) and (iy - W/2 <= hy <= iy + W/2)
                    
            if check_hit(item):
                return i
                
        return -1

    def assembly_mouse_press(self, ev):
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        submode = getattr(self, 'assem_submode', 'puzzle')

        if is_assembly and submode == 'puzzle':
            sx, sy = ev.position().x(), ev.position().y()
            idx = self.get_item_under_cursor(sx, sy)

            if ev.button() == Qt.LeftButton and idx >= 0:
                self.selected_placed_idx = idx
                self.placed_list.setCurrentRow(idx)
                self._dragging = True
                self._drag_offset = (0.0, 0.0)
                self.view.setCursor(Qt.ClosedHandCursor)
                ev.accept()
                return
            elif ev.button() == Qt.RightButton and idx >= 0:
                item = self.placed_items[idx]
                item["rotation"] = (item.get("rotation", 0) + 90) % 360
                self.generate_box()
                ev.accept()
                return
            else:
                ev.accept()
                return

        self._orig_mousePressEvent(ev)

    def assembly_mouse_move(self, ev):
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        submode = getattr(self, 'assem_submode', 'puzzle')

        if self._dragging and self.selected_placed_idx >= 0:
            item = self.placed_items[self.selected_placed_idx]
            H    = item["data"].get("height", 50)
            sx, sy = ev.position().x(), ev.position().y()
            ro, rd = self.compute_ray(sx, sy)
            hit = self.ray_hit_plane_z(ro, rd, H / 2)
            if hit:
                ox, oy = getattr(self, '_drag_offset', (0.0, 0.0))
                item["x"] = hit[0] + ox
                item["y"] = hit[1] + oy
                self.generate_box()
            ev.accept()
            return

        if is_assembly and submode == 'puzzle':
            sx, sy = ev.position().x(), ev.position().y()
            if self.get_item_under_cursor(sx, sy) >= 0:
                self.view.setCursor(Qt.OpenHandCursor)
            else:
                self.view.unsetCursor()
            ev.accept()
            return

        self.view.unsetCursor()
        self._orig_mouseMoveEvent(ev)

    def assembly_mouse_release(self, ev):
        if self._dragging:
            self._dragging = False
            self.view.unsetCursor()
            if self.selected_placed_idx >= 0:
                self.try_auto_snap(self.selected_placed_idx)
                self.ensure_unique_colors_for_assembly()
                self.generate_box()
            ev.accept()
            return
        
        self._orig_mouseReleaseEvent(ev)

    def get_local_side_at_global_direction(self, rotation, global_dir):
        rot = (int(rotation) % 360) // 90
        mapping = {
            0: {0:0, 1:1, 2:2, 3:3},
            1: {0:2, 1:3, 2:1, 3:0},
            2: {0:1, 1:0, 2:3, 3:2},
            3: {0:3, 1:2, 2:0, 3:1} 
        }
        return mapping.get(rot, {0:0, 1:1, 2:2, 3:3}).get(global_dir, global_dir)

    def get_side_info(self, item, global_dir):
        data = item["data"]
        rot = item.get("rotation", 0)
        local_side = self.get_local_side_at_global_direction(rot, global_dir)
        
        side_names = ["side_top", "side_bottom", "side_left", "side_right"]
        count_names = ["side_top_count", "side_bottom_count", "side_left_count", "side_right_count"]
        
        mode = int(data.get(side_names[local_side], 2))
        count = int(data.get(count_names[local_side], 0))
        if count <= 0: mode = 2
        return mode, count

    def try_auto_snap(self, idx):
        item = self.placed_items[idx]
        item_rot = item.get("rotation", 0)
        item_is_compound = item.get("type") == "compound"
        
        # Получаем список частин для поточного об'єкта у глобальних координатах
        def get_global_parts(it):
            rot = it.get("rotation", 0)
            rad = np.radians(rot)
            gx, gy = it.get("x", 0), it.get("y", 0)
            if it.get("type") == "compound":
                res = []
                for p in it.get("parts", []):
                    rx, ry = p["rel_x"], p["rel_y"]
                    # Обертаємо відносні координати навколо центру compound
                    rot_rx = rx * np.cos(rad) - ry * np.sin(rad)
                    rot_ry = rx * np.sin(rad) + ry * np.cos(rad)
                    res.append({
                        "data": p["data"],
                        "g_x": gx + rot_rx,
                        "g_y": gy + rot_ry,
                        "rot": rot
                    })
                return res
            else:
                return [{"data": it["data"], "g_x": gx, "g_y": gy, "rot": rot}]

        my_parts = get_global_parts(item)
        
        snap_gap = 0.1
        snap_threshold = 20.0
        
        best_snap = None
        best_dist = float('inf')
        
        for j, other in enumerate(self.placed_items):
            if j == idx:
                continue
                
            other_parts = get_global_parts(other)
            
            for my_p in my_parts:
                m_data = my_p["data"]
                m_rot = my_p["rot"]
                if (int(m_rot) // 90) % 2 == 1:
                    m_L, m_W = m_data.get("width", 100), m_data.get("length", 100)
                else:
                    m_L, m_W = m_data.get("length", 100), m_data.get("width", 100)
                m_x, m_y = my_p["g_x"], my_p["g_y"]
                
                for oth_p in other_parts:
                    o_data = oth_p["data"]
                    o_rot = oth_p["rot"]
                    if (int(o_rot) // 90) % 2 == 1:
                        o_L, o_W = o_data.get("width", 100), o_data.get("length", 100)
                    else:
                        o_L, o_W = o_data.get("length", 100), o_data.get("width", 100)
                    o_x, o_y = oth_p["g_x"], oth_p["g_y"]
                    
                    snaps = [
                        (o_x, o_y - o_W/2 - m_W/2 - snap_gap, 1, 0, m_L, o_L), # Я знизу від other (top my -> bottom other)
                        (o_x, o_y + o_W/2 + m_W/2 + snap_gap, 0, 1, m_L, o_L), # Я зверху від other
                        (o_x - o_L/2 - m_L/2 - snap_gap, o_y, 3, 2, m_W, o_W), # Я зліва від other
                        (o_x + o_L/2 + m_L/2 + snap_gap, o_y, 2, 3, m_W, o_W), # Я справа від other
                    ]
                    
                    for sx, sy, my_dir, other_dir, my_edge_len, oth_edge_len in snaps:
                        
                        my_local_side = self.get_local_side_at_global_direction(m_rot, my_dir)
                        oth_local_side = self.get_local_side_at_global_direction(o_rot, other_dir)
                        
                        snames = ["side_top", "side_bottom", "side_left", "side_right"]
                        cnames = ["side_top_count", "side_bottom_count", "side_left_count", "side_right_count"]
                        
                        my_mode = int(m_data.get(snames[my_local_side], 2))
                        my_count = int(m_data.get(cnames[my_local_side], 0))
                        if my_count <= 0: my_mode = 2
                        
                        oth_mode = int(o_data.get(snames[oth_local_side], 2))
                        oth_count = int(o_data.get(cnames[oth_local_side], 0))
                        if oth_count <= 0: oth_mode = 2
                        
                        if my_mode == 2 or oth_mode == 2:
                            continue
                            
                        def get_p_info(dat, loc_side, edge_len, count, rot_deg):
                            sname = snames[loc_side]
                            p_len = dat.get(f"{sname}_parent_length", edge_len)
                            p_count = int(dat.get(f"{sname}_parent_count", count))
                            p_off = dat.get(f"{sname}_parent_offset", 0.0)
                            dx, dy = (p_off, 0) if loc_side in [0,1] else (0, p_off)
                            r = np.radians(rot_deg)
                            gx = dx * np.cos(r) - dy * np.sin(r)
                            gy = dx * np.sin(r) + dy * np.cos(r)
                            return p_len, p_count, gx, gy

                        m_p_len, m_p_count, m_gx, m_gy = get_p_info(m_data, my_local_side, my_edge_len, my_count, m_rot)
                        o_p_len, o_p_count, o_gx, o_gy = get_p_info(o_data, oth_local_side, oth_edge_len, oth_count, o_rot)
                        
                        if my_mode != oth_mode and m_p_count == o_p_count:
                            if abs(m_p_len - o_p_len) < 1.0:
                                if my_dir in [0, 1]:  # parallel to X
                                    adjusted_sx = sx - o_gx + m_gx
                                    adjusted_sy = sy
                                else:                 # parallel to Y
                                    adjusted_sx = sx
                                    adjusted_sy = sy - o_gy + m_gy
                                    
                                # Оскільки ми знайшли куди має стати конкретна ЧАСТИНА (adjusted_sx, adjusted_sy),
                                # нам треба з'ясувати де має опинитися центр ЦІЛОГО об'єкта (item["x"], item["y"]).
                                # my_p["g_x"] = item["x"] + rot_rx
                                # отже, item_new_x = adjusted_sx - rot_rx
                                rot_rx = m_x - item.get("x", 0)
                                rot_ry = m_y - item.get("y", 0)
                                
                                item_new_x = adjusted_sx - rot_rx
                                item_new_y = adjusted_sy - rot_ry
                                
                                d = ((item.get("x", 0) - item_new_x) ** 2 + (item.get("y", 0) - item_new_y) ** 2) ** 0.5
                                if d < snap_threshold and d < best_dist:
                                    best_dist = d
                                    best_snap = (item_new_x, item_new_y)
        
        if best_snap:
            item["x"] = best_snap[0]
            item["y"] = best_snap[1]

    def place_first_object(self):
        if self.unplaced_list.currentRow() < 0:
            QMessageBox.warning(self, "Помилка", "Оберіть об'єкт з нерозміщених.")
            return
            
        idx = self.unplaced_list.currentRow()
        item = self.unplaced_items.pop(idx)
        self.unplaced_list.takeItem(idx)
        
        item["x"] = 0.0
        item["y"] = 0.0
        self.placed_items.append(item)
        self.placed_list.addItem(item["name"])
        
        item["color_idx"] = 0
        
        self.mark_dirty()
        self.update_adaptive_grid()
        self.update_assembly_ui_state()

    def remove_from_assembly(self, refresh=True):
        if not hasattr(self, 'placed_items') or not self.placed_items:
            return
        if self.placed_list.currentRow() < 0:
            if refresh:
                QMessageBox.warning(self, "Помилка", "Оберіть об'єкт зі збірки.")
            return
            
        idx = self.placed_list.currentRow()
        item = self.placed_items.pop(idx)
        self.placed_list.takeItem(idx)
        
        self.unplaced_items.append(item)
        self.unplaced_list.addItem(item["name"])
        
        self.mark_dirty()
        if refresh:
            self.update_all_views()

    def update_all_views(self):
        self.ensure_unique_colors_for_assembly()
        self.update_adaptive_grid()
        self.update_assembly_ui_state()
        if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
            self.update_puzzle_view()
        else:
            self.generate_box()

    def ensure_unique_colors_for_assembly(self):
        """Гарантує, що суміжні деталі у збірці мають різні кольори."""
        if not hasattr(self, 'placed_items') or not self.placed_items:
            return
            
        palette_len = len(getattr(self, 'assembly_palette', ['#ff0000']))
        
        def get_bbs(it):
            bbs = []
            if it.get("type") == "compound":
                for p in it.get("parts", []):
                    rad = np.radians(it.get("rotation", 0))
                    rx, ry = p["rel_x"], p["rel_y"]
                    gx = it["x"] + rx * np.cos(rad) - ry * np.sin(rad)
                    gy = it["y"] + rx * np.sin(rad) + ry * np.cos(rad)
                    L, W = p["data"].get("length", 100), p["data"].get("width", 100)
                    bbs.append((gx - L/2 - 2, gy - W/2 - 2, gx + L/2 + 2, gy + W/2 + 2))
            else:
                gx, gy = it["x"], it["y"]
                L, W = it["data"].get("length", 100), it["data"].get("width", 100)
                if int(it.get("rotation", 0)) % 180 != 0: L, W = W, L
                bbs.append((gx - L/2 - 2, gy - W/2 - 2, gx + L/2 + 2, gy + W/2 + 2))
            return bbs

        # Перефарбовування
        for i, item in enumerate(self.placed_items):
            bbs_i = get_bbs(item)
            used_colors = set()
            
            for j, other in enumerate(self.placed_items):
                if i == j: continue
                bbs_j = get_bbs(other)
                
                adjacent = False
                for b1 in bbs_i:
                    for b2 in bbs_j:
                        if not (b1[2] < b2[0] or b1[0] > b2[2] or b1[3] < b2[1] or b1[1] > b2[3]):
                            adjacent = True
                            break
                    if adjacent: break
                            
                if adjacent and "color_idx" in other:
                    used_colors.add(other["color_idx"])
            
            # Якщо поточний колір не використовується сусідами, залишаємо його
            curr_color = item.get("color_idx", -1)
            if curr_color >= 0 and curr_color not in used_colors:
                continue
                
            # Інакше шукаємо новий
            for c in range(palette_len):
                if c not in used_colors:
                    item["color_idx"] = c
                    break
            else:
                item["color_idx"] = 0 # fallback

    def group_selected_items(self):
        import uuid
        selected = self.puzzle_scene.selectedItems()
        target_items = [item for item in selected if hasattr(item, 'placed_idx')]
        if len(target_items) < 2:
            self.statusBar().showMessage("Виділіть принаймні 2 елементи для групування.", 2000)
            return
            
        new_group_id = str(uuid.uuid4())
        
        for item in target_items:
            data_item = self.placed_items[item.placed_idx]
            data_item["group_id"] = new_group_id
            item.group_id = new_group_id
            
        self.statusBar().showMessage(f"Згруповано {len(target_items)} елементів.", 2000)
        self.mark_dirty()

    def ungroup_selected_items(self):
        selected = self.puzzle_scene.selectedItems()
        target_items = [item for item in selected if hasattr(item, 'placed_idx') and getattr(item, 'group_id', None)]
        if not target_items:
            self.statusBar().showMessage("Немає згрупованих елементів серед виділених.", 2000)
            return

        count = 0
        for item in target_items:
            data_item = self.placed_items[item.placed_idx]
            if "group_id" in data_item:
                del data_item["group_id"]
            item.group_id = None
            count += 1
            
        self.statusBar().showMessage(f"Розгруповано {count} елементів.", 2000)
        self.mark_dirty()

    def clear_assembly(self):

        confirm = QMessageBox.question(self, "Очистити", "Ви дійсно хочете очистити стіл? Всі поточні об'єкти зникнуть зі збірки.", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.placed_items = []
            self.unplaced_items = []
            self.placed_list.clear()
            self.unplaced_list.clear()
            self.mark_dirty()
            self.update_adaptive_grid()
            self.update_assembly_ui_state()
            if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
                self.update_puzzle_view()
            else:
                self.generate_box()

    def on_delete_key(self):
        """Обробник гарячої клавіші Delete/Backspace."""
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        if not is_assembly: return
        
        if getattr(self, 'assem_submode', 'puzzle') == 'puzzle' and hasattr(self, 'puzzle_scene'):
            sel = self.puzzle_scene.selectedItems()
            if sel:
                idxs = sorted([it.placed_idx for it in sel if hasattr(it, 'placed_idx')], reverse=True)
                for idx in idxs:
                    self.placed_list.setCurrentRow(idx)
                    self.remove_from_assembly(refresh=False)
                self.update_all_views()
                return
        
        if self.placed_list.currentRow() >= 0:
            self.remove_from_assembly()

    def AssemblyMixin_keyPressEvent(self, event):
        if event.key() in [Qt.Key_Delete, Qt.Key_Backspace]:
            self.on_delete_key()
            return
            
        if hasattr(super(), 'AssemblyMixin_keyPressEvent'):
            super().AssemblyMixin_keyPressEvent(event)

    def update_assembly_ui_state(self, *args):
        p_items = getattr(self, 'placed_items', [])
        u_items = getattr(self, 'unplaced_items', [])
        p_count = len(p_items)
        u_count = len(u_items)
        
        has_placed = p_count > 0
        has_unplaced = u_count > 0
        has_selection = self.placed_list.currentRow() >= 0

        self.live_height_sb.setEnabled(has_selection)
        if hasattr(self, 'h_label'):
            self.h_label.setEnabled(has_selection)
        
        self.save_assem_btn.setEnabled(has_placed)

    def add_n_copies_dialog(self):
        target_item_data = None
        target_name = "Копія"
        
        if self.unplaced_list.currentRow() >= 0:
            idx = self.unplaced_list.currentRow()
            target_item_data = self.unplaced_items[idx]["data"]
            target_name = self.unplaced_items[idx]["name"]
        elif self.bookmarks_tree.currentItem():
            path = self.bookmarks_tree.currentItem().data(0, Qt.UserRole)
            if os.path.isfile(path) and path.endswith(".json"):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "placed_items" not in data:
                        target_item_data = data
                        target_name = self.bookmarks_tree.currentItem().text(0)
                except: pass
        
        if not target_item_data:
            QMessageBox.warning(self, "Увага", "Оберіть одиничний пресет (в списку нерозміщених або в закладках).")
            return
            
        n, ok = QInputDialog.getInt(self, "Додати копії", f"Скільки копій '{target_name}' додати?", 5, 1, 100)
        if ok:
            for i in range(n):
                name = f"{target_name}_{len(self.unplaced_items) + 1}"
                self.unplaced_items.append({"name": name, "data": target_item_data})
                self.unplaced_list.addItem(name)
            self.update_assembly_ui_state()

    def open_snap_dialog(self):
        if not hasattr(self, 'unplaced_items') or not self.unplaced_items:
            QMessageBox.warning(self, "Помилка", "Немає нерозміщених об'єктів.")
            return
        if not hasattr(self, 'placed_items') or not self.placed_items:
            QMessageBox.warning(self, "Помилка", "Немає розміщених об'єктів.")
            return
            
        un_names = [item["name"] for item in self.unplaced_items]
        
        placed_info = []
        for pl in self.placed_items:
            avail = []
            for s in range(4):
                if not self.is_side_occupied(pl, s):
                    avail.append(s)
            
            dat = pl["data"]
            m_keys = ["side_top", "side_bottom", "side_left", "side_right"]
            c_keys = ["side_top_count", "side_bottom_count", "side_left_count", "side_right_count"]
            modes = []
            for m_key, c_key in zip(m_keys, c_keys):
                mode = int(dat.get(m_key, 2))
                if int(dat.get(c_key, 0)) <= 0: mode = 2
                modes.append(mode)
            placed_info.append({"name": pl["name"], "available_sides": avail, "side_modes": modes})
            
        un_info = []
        for un in self.unplaced_items:
            dat = un["data"]
            m_keys = ["side_top", "side_bottom", "side_left", "side_right"]
            c_keys = ["side_top_count", "side_bottom_count", "side_left_count", "side_right_count"]
            modes = []
            for m_key, c_key in zip(m_keys, c_keys):
                mode = int(dat.get(m_key, 2))
                if int(dat.get(c_key, 0)) <= 0: mode = 2
                modes.append(mode)
            un_info.append({"name": un["name"], "side_modes": modes})
        
        dlg = SnapDialog(un_info, placed_info, self)
        if self.unplaced_list.currentRow() >= 0:
            dlg.unplaced_cb.setCurrentIndex(self.unplaced_list.currentRow())
        if self.placed_list.currentRow() >= 0:
            dlg.placed_cb.setCurrentIndex(self.placed_list.currentRow())
            
        if dlg.exec() == QDialog.Accepted:
            p_side = dlg.get_selected_placed_side()
            u_side = dlg.get_selected_unplaced_side()
            self.do_snap(dlg.unplaced_cb.currentIndex(), u_side,
                         dlg.placed_cb.currentIndex(), p_side)

        self.update_adaptive_grid()
        self.update_assembly_ui_state()

    def save_assembly(self):
        path, _ = QFileDialog.getSaveFileName(self, "Зберегти збірку", "my_assembly.json", "Assembly Files (*.json)")
        if not path: return
        self.save_assembly_to_path(path)

    def save_assembly_to_path(self, path):
        data = {
            "placed_items": self.placed_items,
            "unplaced_items": self.unplaced_items
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            if not getattr(self, 'presets_dir', None) or not path.startswith(self.presets_dir):
                 QMessageBox.information(self, "Успіх", f"Збірку збережено у {path}")
            self.refresh_bookmarks()
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти збірку:\n{e}")

    def load_assembly(self):
        path, _ = QFileDialog.getOpenFileName(self, "Завантажити збірку", "", "Assembly Files (*.json)")
        if not path: return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.placed_items = data.get("placed_items", [])
            self.unplaced_items = data.get("unplaced_items", [])
            
            self.placed_list.clear()
            for item in self.placed_items: self.placed_list.addItem(item["name"])
            self.unplaced_list.clear()
            for item in self.unplaced_items: self.unplaced_list.addItem(item["name"])
            
            self.mark_dirty()
            self.update_adaptive_grid()
            self.update_assembly_ui_state()

            if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
                self.update_puzzle_view()
            else:
                self.generate_box()

            QMessageBox.information(self, "Успіх", "Збірку успішно завантажено.")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити:\n{e}")

    def show_placed_context_menu(self, pos):
        item = self.placed_list.itemAt(pos)
        if not item: return
        idx = self.placed_list.row(item)
        
        menu = QMenu()
        height_act = QAction(" Змінити висоту", self)
        height_act.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        height_act.triggered.connect(lambda: self.change_box_height(idx))
        menu.addAction(height_act)
        menu.exec(self.placed_list.mapToGlobal(pos))

    def on_assem_submode_changed(self, btn):
        if btn == self.puzzle_mode_btn:
            self.assem_submode = 'puzzle'
            self.view_stack.setCurrentIndex(1)
            self.update_puzzle_view()
            self.statusBar().showMessage(
                "🧩 Пазл: ЛКМ — переміщення, ПКМ — поворот на 90°, колесо — зум", 4000)
        else:
            self.assem_submode = 'view'
            self.view_stack.setCurrentIndex(0)
            self.generate_box()
            self.statusBar().showMessage(
                "🎥 Камера: вільне обертання 3D-виду", 3000)

    def update_puzzle_view(self):
        from puzzle_item import PuzzleBoxItem, CompoundPuzzleItem
        self.puzzle_scene.clear()
        selected_row = self.placed_list.currentRow()
        
        for idx in range(len(self.placed_items)):
            item = self.placed_items[idx]
            if item.get("type") == "compound":
                item_gfx = CompoundPuzzleItem(idx, self)
            else:
                item_gfx = PuzzleBoxItem(idx, self)
            self.puzzle_scene.addItem(item_gfx)
            if idx == selected_row:
                item_gfx.setSelected(True)
                
        sr = self.puzzle_scene.itemsBoundingRect()
        if not sr.isEmpty():
            self.puzzle_canvas.fitInView(
                sr.adjusted(-100, -100, 100, 100), Qt.KeepAspectRatio)

    def update_puzzle_selection(self, row=None):
        """Синхронізує виділення в 2D-сцені при зміні вибору в списку."""
        if row is None:
            row = self.placed_list.currentRow()
        
        # Блокуємо сигнали, щоб не закільцювати
        self.puzzle_scene.blockSignals(True)
        for item in self.puzzle_scene.items():
            if hasattr(item, 'placed_idx'):
                item.setSelected(item.placed_idx == row)
        self.puzzle_scene.blockSignals(False)
        self.puzzle_scene.update()

    def _puzzle_wheel_zoom(self, ev):
        factor = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.puzzle_canvas.scale(factor, factor)

    def on_placed_item_changed(self, current, previous):
        if current:
            idx = self.placed_list.row(current)
            if idx >= 0 and idx < len(self.placed_items):
                item = self.placed_items[idx]
                self.selected_placed_idx = idx
                val = item["data"].get("height", 50)
                self.live_height_sb.blockSignals(True)
                self.live_height_sb.setValue(val)
                self.live_height_sb.blockSignals(False)
        self.update_assembly_ui_state()

    def on_live_height_changed(self, val):
        idx = self.placed_list.currentRow()
        if idx < 0 or idx >= len(self.placed_items): return
        
        item = self.placed_items[idx]
        item["data"]["height"] = val
        
        # Propagate to parts if compound
        if item.get("type") == "compound":
            for part in item.get("parts", []):
                part["data"]["height"] = val
                
        self.mark_dirty()
        # Trigger 3D view update via timer (debounce)
        if hasattr(self, 'regen_timer'):
            self.regen_timer.start(300)

    def update_adaptive_grid(self):
        if not hasattr(self, 'placed_items') or not self.placed_items:
            self.grid.setSize(x=400, y=400, z=0)
            self.grid.setSpacing(x=10, y=10, z=0)
            self.grid.resetTransform()
            self.grid.translate(0, 0, -0.1)
            return
            
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for item in self.placed_items:
            ix, iy = item["x"], item["y"]
            if item.get("type") == "compound":
                # Для compound — беремо bounding box всіх частин
                for part in item.get("parts", []):
                    pd = part["data"]
                    L = pd.get("length", 100)
                    W = pd.get("width",  100)
                    px = ix + part.get("rel_x", 0)
                    py = iy + part.get("rel_y", 0)
                    min_x = min(min_x, px - L/2)
                    max_x = max(max_x, px + L/2)
                    min_y = min(min_y, py - W/2)
                    max_y = max(max_y, py + W/2)
            else:
                dat = item["data"]
                L, W = dat.get("length", 100), dat.get("width", 100)
                min_x = min(min_x, ix - L/2)
                max_x = max(max_x, ix + L/2)
                min_y = min(min_y, iy - W/2)
                max_y = max(max_y, iy + W/2)

            
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        span_x = max_x - min_x
        span_y = max_y - min_y
        
        max_span = max(span_x, span_y, 200) + 100
        
        max_span = ((int(max_span) // 100) + 1) * 100
        
        self.grid.setSize(x=max_span, y=max_span, z=0)
        self.grid.setSpacing(x=10, y=10, z=0)
        
        self.grid.resetTransform()
        self.grid.translate(center_x, center_y, -0.1)

    def change_box_height(self, idx):
        pl = self.placed_items[idx]
        old_h = pl["data"].get("height", 50)
        new_h, ok = QInputDialog.getDouble(self, "Висота", f"Введіть нову висоту для '{pl['name']}':", old_h, 1, 1000, 1)
        if ok:
            self.live_height_sb.setValue(new_h)

    def is_side_occupied(self, item, side_idx):
        L, W = item["data"].get("length", 100), item["data"].get("width", 100)
        rot = item.get("rotation", 0)
        sx, sy = self.get_edge_center(item["x"], item["y"], L, W, side_idx, rot)
        for other in self.placed_items:
            if other is item: continue
            oL, oW = other["data"].get("length", 100), other["data"].get("width", 100)
            oRot = other.get("rotation", 0)
            for os in range(4):
                ox, oy = self.get_edge_center(other["x"], other["y"], oL, oW, os, oRot)
                if ((sx - ox)**2 + (sy - oy)**2)**0.5 < 1.0:
                    return True
        return False

    def copy_to_side(self, idx, screen_side):
        source = self.placed_items[idx]
        s_data = source["data"]
        s_rot = int(source.get("rotation", 0)) % 360
        
        p_L = s_data.get("length", 100)
        p_W = s_data.get("width", 100)
        r_mod = (s_rot // 90) % 2
        pw, ph = (p_W, p_L) if r_mod == 1 else (p_L, p_W)
        
        dx, dy = 0.0, 0.0
        if screen_side == 0: dy = -ph # Top
        elif screen_side == 1: dy = ph  # Bottom
        elif screen_side == 2: dx = -pw # Left
        elif screen_side == 3: dx = pw  # Right

        pushed_idxs = []
        if dx != 0 or dy != 0:
            eps = 5.0 # pixels tolerance
            for i, other in enumerate(self.placed_items):
                if i == idx: continue
                should_push = False
                if screen_side == 0 and other["y"] < source["y"] - eps: should_push = True
                elif screen_side == 1 and other["y"] > source["y"] + eps: should_push = True
                elif screen_side == 2 and other["x"] < source["x"] - eps: should_push = True
                elif screen_side == 3 and other["x"] > source["x"] + eps: should_push = True
                
                if should_push:
                    other["x"] += dx
                    other["y"] += dy
                    pushed_idxs.append(i)
        # -----------------------------------------------------------------

        new_data = s_data.copy()
        
        rot_steps = (s_rot // 90) % 4
        
        phys_map = {
            0: [0, 2, 1, 3],
            1: [1, 3, 0, 2],
            2: [2, 1, 3, 0],
            3: [3, 0, 2, 1]
        }
        
        phys_side = phys_map[screen_side][rot_steps]

        def flip_mode(m):
            if m == 0: return 1
            if m == 1: return 0
            return 2

        data_keys = [
            ("side_top", "side_top_count"),
            ("side_bottom", "side_bottom_count"),
            ("side_left", "side_left_count"),
            ("side_right", "side_right_count")
        ]

        u_side = phys_side ^ 1
        
        target_key, target_count_key = data_keys[u_side]
        source_key, source_count_key = data_keys[phys_side]
        
        new_data[target_key] = flip_mode(s_data.get(source_key, 0))
        new_data[target_count_key] = s_data.get(source_count_key, 1)

        new_item = {
            "name": f"{source['name']} (копія)",
            "data": new_data,
            "rotation": s_rot,
            "x": source["x"],
            "y": source["y"],
            "color_idx": (source.get("color_idx", 0) + 1) % len(self.assembly_palette)
        }
        
        self.unplaced_items.append(new_item)
        self.unplaced_list.addItem(new_item["name"])
        u_idx = len(self.unplaced_items) - 1
        
        try:
            self.do_snap(u_idx, u_side, idx, phys_side)
            self.update_puzzle_view()
            self.generate_box()
            self.statusBar().showMessage(f"Створено копію {new_item['name']}", 3000)
        except Exception as e:
            # Rollback pushes
            for p_idx in pushed_idxs:
                self.placed_items[p_idx]["x"] -= dx
                self.placed_items[p_idx]["y"] -= dy
            
            if len(self.unplaced_items) > 0 and self.unplaced_items[-1] is new_item:
                self.unplaced_items.pop()
                self.unplaced_list.takeItem(self.unplaced_list.count()-1)
            QMessageBox.warning(self, "Помилка копіювання", f"Не вдалося пристикувати копію:\n{e}")

    def split_item(self, idx, screen_axis):
        item = self.placed_items[idx]
        data = item["data"]
        rot = int(item.get("rotation", 0)) % 360
        
        rot_steps = (rot // 90) % 4
        if screen_axis == 'x':
            logic_axis = 'length' if rot_steps % 2 == 0 else 'width'
        else:
            logic_axis = 'width' if rot_steps % 2 == 0 else 'length'

        # Визначаємо ліміт на кількість частин: не більше ніж кількість замків на сторонах, які розрізаються
        if logic_axis == 'length':
            m1 = int(data.get("side_top", 2))
            m2 = int(data.get("side_bottom", 2))
            c1 = int(data.get("side_top_count", 0)) if m1 != 2 else 0
            c2 = int(data.get("side_bottom_count", 0)) if m2 != 2 else 0
        else:
            m1 = int(data.get("side_left", 2))
            m2 = int(data.get("side_right", 2))
            c1 = int(data.get("side_left_count", 0)) if m1 != 2 else 0
            c2 = int(data.get("side_right_count", 0)) if m2 != 2 else 0

        max_allowed = max(c1, c2)
        total_limit = max_allowed if max_allowed > 0 else 50

        if total_limit < 2:
            QMessageBox.warning(self, "Обмеження розбиття", 
                                "Недостатньо замків (отворів) для розбиття деталі за цією віссю.\n"
                                f"Наявна кількість замків: {max_allowed}. Для розбиття потрібно мінімум 2.")
            return

        n, ok = QInputDialog.getInt(self, "Розбити фігуру", 
                                    f"На скільки частин розбити? (макс. {total_limit})", 
                                    2, 2, total_limit)
        if not ok or n < 2:
            return

        orig_L = data.get("length", 100)
        orig_W = data.get("width", 100)
        orig_x = item["x"]
        orig_y = item["y"]
        
        def get_dist(C, count_parts):
            if count_parts <= 0: return []
            if C <= 0: return [0] * count_parts
            base = C // count_parts
            rem = C % count_parts
            res = [base] * count_parts
            for j in range(rem):
                res[j] += 1
            return res

        if logic_axis == 'length':
            dist1 = get_dist(c1, n)
            dist2 = get_dist(c2, n)
            W_val = max_allowed if max_allowed > 0 else n
            master_dist = get_dist(W_val, n)
            current_edge_start = -orig_L / 2.0
        else:
            dist1 = get_dist(c1, n) # left
            dist2 = get_dist(c2, n) # right
            W_val = max_allowed if max_allowed > 0 else n
            master_dist = get_dist(W_val, n)
            current_edge_start = -orig_W / 2.0
            
        new_items = []
        for i in range(n):
            new_data = data.copy()
            w_i = master_dist[i]
            
            if logic_axis == 'length':
                part_len = orig_L * (w_i / W_val)
                new_data["length"] = part_len
                local_dx = current_edge_start + part_len / 2.0
                local_dy = 0.0
                current_edge_start += part_len
                
                for border in ['top', 'bottom']:
                    if f"side_{border}_parent_length" not in new_data:
                        new_data[f"side_{border}_parent_length"] = orig_L
                    if f"side_{border}_parent_count" not in new_data:
                        new_data[f"side_{border}_parent_count"] = int(new_data.get(f"side_{border}_count", 1))
                    old_offset = data.get(f"side_{border}_parent_offset", 0.0)
                    new_data[f"side_{border}_parent_offset"] = old_offset + local_dx
                
                # Призначаємо розподілені замки
                new_data["side_top_count"] = dist1[i]
                if dist1[i] == 0 and m1 != 2: new_data["side_top"] = 2
                
                new_data["side_bottom_count"] = dist2[i]
                if dist2[i] == 0 and m2 != 2: new_data["side_bottom"] = 2
                
                if i > 0:
                    new_data["side_left"] = 1
                    boundary_count = max(int(data.get("side_left_count", 1)), int(data.get("side_right_count", 1)))
                    new_data["side_left_count"] = boundary_count
                if i < n - 1:
                    new_data["side_right"] = 0
                    boundary_count = max(int(data.get("side_left_count", 1)), int(data.get("side_right_count", 1)))
                    new_data["side_right_count"] = boundary_count
            else:
                part_len = orig_W * (w_i / W_val)
                new_data["width"] = part_len
                local_dx = 0.0
                local_dy = current_edge_start + part_len / 2.0
                current_edge_start += part_len
                
                for border in ['left', 'right']:
                    if f"side_{border}_parent_length" not in new_data:
                        new_data[f"side_{border}_parent_length"] = orig_W
                    if f"side_{border}_parent_count" not in new_data:
                        new_data[f"side_{border}_parent_count"] = int(new_data.get(f"side_{border}_count", 1))
                    old_offset = data.get(f"side_{border}_parent_offset", 0.0)
                    new_data[f"side_{border}_parent_offset"] = old_offset + local_dy
                
                # Призначаємо розподілені замки
                new_data["side_left_count"] = dist1[i]
                if dist1[i] == 0 and m1 != 2: new_data["side_left"] = 2
                
                new_data["side_right_count"] = dist2[i]
                if dist2[i] == 0 and m2 != 2: new_data["side_right"] = 2
                        
                if i > 0:
                    new_data["side_top"] = 1
                    boundary_count = max(int(data.get("side_top_count", 1)), int(data.get("side_bottom_count", 1)))
                    new_data["side_top_count"] = boundary_count
                if i < n - 1:
                    new_data["side_bottom"] = 0
                    boundary_count = max(int(data.get("side_top_count", 1)), int(data.get("side_bottom_count", 1)))
                    new_data["side_bottom_count"] = boundary_count
            
            rad = np.radians(rot)
            gx = local_dx * np.cos(rad) - local_dy * np.sin(rad)
            gy = local_dx * np.sin(rad) + local_dy * np.cos(rad)
            
            new_item = {
                "name": f"{item['name']}_split{i+1}",
                "data": new_data,
                "rotation": rot,
                "x": orig_x + gx,
                "y": orig_y + gy,
                "color_idx": (item.get("color_idx", 0) + i) % len(self.assembly_palette)
            }
            new_items.append(new_item)
            
        self.placed_items.pop(idx)
        self.placed_list.takeItem(idx)
        
        for ni in new_items:
            self.placed_items.append(ni)
            self.placed_list.addItem(ni["name"])
            
        self.mark_dirty()
        self.update_adaptive_grid()
        self.update_assembly_ui_state()
        self.update_puzzle_view()
        self.generate_box()
        self.statusBar().showMessage(f"Фігуру розбито на {n} частин.", 3000)


    def get_edge_center(self, x, y, L, W, side, rotation=0):
        if side == 0: vx, vy = 0, -W/2
        elif side == 1: vx, vy = 0, W/2
        elif side == 2: vx, vy = -L/2, 0
        elif side == 3: vx, vy = L/2, 0
        else: return x, y
        
        rad = np.radians(rotation) 
        rx = vx * np.cos(rad) - vy * np.sin(rad)
        ry = vx * np.sin(rad) + vy * np.cos(rad)
        return x + rx, y + ry

    def do_snap(self, u_idx, u_side, p_idx, p_side):
        u_item = self.unplaced_items[u_idx]
        p_item = self.placed_items[p_idx]
        u_data = u_item["data"]
        p_data = p_item["data"]
        u_rot = u_item.get("rotation", 0)
        p_rot = p_item.get("rotation", 0)
        
        keys_map = [
            ("side_top", "side_top_count", "length", "width"),
            ("side_bottom", "side_bottom_count", "length", "width"),
            ("side_left", "side_left_count", "width", "length"),
            ("side_right", "side_right_count", "width", "length"),
        ]
        
        p_L, p_W = p_data.get("length", 100), p_data.get("width", 100)
        p_ec_x, p_ec_y = self.get_edge_center(p_item["x"], p_item["y"], p_L, p_W, p_side, p_rot)
        
        u_L, u_W = u_data.get("length", 100), u_data.get("width", 100)
        uv_x, uv_y = self.get_edge_center(0, 0, u_L, u_W, u_side, u_rot)
        
        pv_x, pv_y = self.get_edge_center(0, 0, p_L, p_W, p_side, p_rot)
        p_mag = (pv_x**2 + pv_y**2)**0.5
        gap_ux, gap_uy = pv_x/p_mag, pv_y/p_mag
        
        snap_gap = 0.1
        u_x = p_ec_x + gap_ux * snap_gap - uv_x
        u_y = p_ec_y + gap_uy * snap_gap - uv_y

        ux_center, uy_center = self.get_edge_center(u_x, u_y, u_L, u_W, u_side, u_rot)
        
        if abs(gap_uy) > abs(gap_ux):
            axis = "y"
            effective_u_len = u_L if (u_rot // 90) % 2 == 0 else u_W
            seg_min, seg_max = ux_center - effective_u_len / 2, ux_center + effective_u_len / 2
        else:
            axis = "x"
            effective_u_len = u_W if (u_rot // 90) % 2 == 0 else u_L
            seg_min, seg_max = uy_center - effective_u_len / 2, uy_center + effective_u_len / 2

        total_p_edge_len = 0.0
        total_p_tab_count = 0
        p_mode_rep = None
        seg_coords = []

        for p_idx_other, pl_item in enumerate(self.placed_items):
            pl_dat = pl_item["data"]
            pl_L, pl_W = pl_dat.get("length", 100), pl_dat.get("width", 100)
            pl_rot = pl_item.get("rotation", 0)
            for ps in range(4):
                plx_e, ply_e = self.get_edge_center(pl_item["x"], pl_item["y"], pl_L, pl_W, ps, pl_rot)
                if ((ux_center - plx_e)**2 + (uy_center - ply_e)**2)**0.5 < 1.0:
                    pm, pc, pe, po = keys_map[ps]
                    total_p_edge_len += pl_dat[pe]
                    total_p_tab_count += pl_dat[pc]
                    if p_mode_rep is None: p_mode_rep = pl_dat[pm]
                    if axis == "y": seg_coords.extend([plx_e - pl_dat[pe]/2, plx_e + pl_dat[pe]/2])
                    else: seg_coords.extend([ply_e - pl_dat[pe]/2, ply_e + pl_dat[pe]/2])

        if seg_coords:
            combined_min = min(seg_coords)
            combined_max = max(seg_coords)
            combined_center = (combined_min + combined_max) / 2
            if axis == "y": u_x = combined_center
            else: u_y = combined_center

        u_m_k, u_c_k, u_e_k, u_o_k = keys_map[u_side]
        u_mode, u_count, u_edge = u_data[u_m_k], u_data[u_c_k], u_data[u_e_k]

        mismatch = False
        reasons = []
        p_mode = int(p_mode_rep) if p_mode_rep is not None else None
        u_mode_int = int(u_mode)
        
        if p_mode is not None and p_mode != 2 and u_mode_int != 2:
            if p_mode == u_mode_int:
                mismatch = True
                reasons.append(f"Однакові типи ({'Шип' if u_mode==0 else 'Паз'}).")
            if total_p_tab_count != u_count:
                mismatch = True
                reasons.append(f"Суммарна к-ть замків не співпадає ({total_p_tab_count} vs {u_count}).")
        
        if abs(total_p_edge_len - u_edge) > 0.1:
            mismatch = True
            reasons.append(f"Суммарна довжина ({total_p_edge_len} vs {u_edge}).")

        if mismatch:
            side_name = ["Верх", "Низ", "Ліво", "Право"][u_side]
            msg = f"Місткова невідповідність (сторона {side_name}):\n" + "\n".join(reasons) + "\n\nПідігнати?"
            if QMessageBox.question(self, "Геометрія", msg) == QMessageBox.Yes:
                if p_mode_rep is not None and p_mode_rep != 2:
                    u_data[u_m_k] = 1 if p_mode_rep == 0 else 0
                    u_data[u_c_k] = total_p_tab_count
                    u_data["tab_base"] = p_data.get("tab_base", 20)
                    u_data["tab_tip"] = p_data.get("tab_tip", 30)
                    u_data["tab_depth"] = p_data.get("tab_depth", 10)
                u_data[u_e_k] = total_p_edge_len
            else: return

        for pl_item in self.placed_items:
            pl_dat = pl_item["data"]
            pl_L, pl_W = pl_dat.get("length", 100), pl_dat.get("width", 100)
            for us in range(4):
                if us == u_side: continue
                ux_e, uy_e = self.get_edge_center(u_x, u_y, u_L, u_W, us)
                for pls in range(4):
                    plx_e, ply_e = self.get_edge_center(pl_item["x"], pl_item["y"], pl_L, pl_W, pls)
                    if ((ux_e - plx_e)**2 + (uy_e - ply_e)**2)**0.5 < 1.0:
                        pm, pc, pe, po = keys_map[pls]
                        um, uc, ue, uo = keys_map[us]
                        # Simply check primary compatibility for neighbors
                        if pl_dat[pm] == u_data[um] and pl_dat[pm] != 2: pass # Warn?
        
        used_colors = set()
        for pl_item in self.placed_items:
            pl_dat = pl_item["data"]
            pl_L, pl_W = pl_dat.get("length", 100), pl_dat.get("width", 100)
            
            dx = abs(u_x - pl_item["x"]) - (u_L + pl_L)/2
            dy = abs(u_y - pl_item["y"]) - (u_W + pl_W)/2
            
            if dx < 1.0 and dy < 1.0:
                if "color_idx" in pl_item:
                    used_colors.add(pl_item["color_idx"])
        
        new_color = 0
        for i in range(len(getattr(self, 'assembly_palette', ['#ff0000']))):
            if i not in used_colors:
                new_color = i
                break
        u_item["color_idx"] = new_color

        u_item["x"], u_item["y"] = u_x, u_y
        self.unplaced_items.pop(u_idx)
        
        self.unplaced_list.clear()
        for it in self.unplaced_items:
            self.unplaced_list.addItem(it["name"])

        self.placed_items.append(u_item)
        self.placed_list.addItem(u_item["name"])
        self.mark_dirty()
        self.update_assembly_ui_state()

    def load_assembly_folder(self, folder_path):
        self.unplaced_items = []
        self.placed_items = []
        self.unplaced_list.clear()
        self.placed_list.clear()
        
        for name in sorted(os.listdir(folder_path)):
            if name.endswith(".json"):
                full_path = os.path.join(folder_path, name)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    item_name = name.replace(".json", "")
                    self.unplaced_items.append({"name": item_name, "data": data})
                    self.unplaced_list.addItem(item_name)
                except:
                    pass
        self.generate_box()
        self.update_assembly_ui_state()

    def get_box_thumbnail(self, data):
        L = data.get("length", 100)
        W = data.get("width", 100)
        
        pix = QPixmap(100, 100)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        
        margin = 15
        max_dim = max(L, W)
        if max_dim == 0: max_dim = 1
        scale = (100 - 2 * margin) / max_dim
        
        draw_L = L * scale
        draw_W = W * scale
        
        rect = QRectF((100 - draw_L)/2, (100 - draw_W)/2, draw_L, draw_W)
        centerX = 50
        centerY = 50
        
        painter.setPen(QPen(QColor("#4a7"), 1.5))
        painter.setBrush(QColor(74, 170, 112, 40))
        painter.drawRect(rect)
        
        tab_size = 4
        
        def draw_joints(side, mode, count):
            if mode == 2: return
            painter.setPen(QPen(QColor("#6c9"), 1))
            if mode == 0:
                painter.setBrush(QColor("#6c9"))
            else:
                painter.setBrush(Qt.transparent)
            
            for i in range(count):
                pos_pct = (i + 1) / (count + 1)
                if side == "top":
                    jx = rect.left() + rect.width() * pos_pct - tab_size/2
                    jy = rect.top() - (tab_size/2 if mode==0 else -tab_size/2)
                elif side == "bottom":
                    jx = rect.left() + rect.width() * pos_pct - tab_size/2
                    jy = rect.bottom() - (tab_size/2 if mode==0 else -tab_size/2)
                elif side == "left":
                    jx = rect.left() - (tab_size/2 if mode==0 else -tab_size/2)
                    jy = rect.top() + rect.height() * pos_pct - tab_size/2
                else:
                    jx = rect.right() - (tab_size/2 if mode==0 else -tab_size/2)
                    jy = rect.top() + rect.height() * pos_pct - tab_size/2
                
                painter.drawRect(QRectF(jx, jy, tab_size, tab_size))

        draw_joints("top", int(data.get("side_top", 0)), int(data.get("side_top_count", 1)))
        draw_joints("bottom", int(data.get("side_bottom", 1)), int(data.get("side_bottom_count", 1)))
        draw_joints("left", int(data.get("side_left", 1)), int(data.get("side_left_count", 1)))
        draw_joints("right", int(data.get("side_right", 0)), int(data.get("side_right_count", 1)))

        if draw_L > 30 and draw_W > 30:
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, f"{int(L)}x{int(W)}")
            
        painter.end()
        return QIcon(pix)

    def populate_toolbox(self, folder_path=None):
        self.toolbox_list.clear()
        if folder_path is None:
            item = self.bookmarks_tree.currentItem()
            if item:
                path = item.data(0, Qt.UserRole)
                if os.path.isdir(path):
                    folder_path = path
        if not folder_path or not os.path.isdir(folder_path):
            return
        
        self._toolbox_folder = folder_path
        
        for name in sorted(os.listdir(folder_path)):
            if name.endswith(".json"):
                full_path = os.path.join(folder_path, name)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "placed_items" in data and len(data["placed_items"]) > 0:
                        continue
                    item_name = name.replace(".json", "")
                    list_item = QListWidgetItem(item_name)
                    list_item.setIcon(self.get_box_thumbnail(data))
                    L = data.get("length", 0)
                    W = data.get("width", 0)
                    H = data.get("height", 0)
                    list_item.setToolTip(f"{L}x{W}x{H} мм")
                    list_item.setData(Qt.UserRole, full_path)
                    self.toolbox_list.addItem(list_item)
                except:
                    pass

    def add_tool_to_assembly(self, world_pos=None):
        current = self.toolbox_list.currentItem()
        if not current and not getattr(self, '_pending_drop_path', None):
            QMessageBox.warning(self, "Увага", "Оберіть коробку з панелі інструментів.")
            return

        path = getattr(self, '_pending_drop_path', current.data(Qt.UserRole) if current else None)
        if not path: return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Помилка", f"Не вдалося завантажити пресет:\n{e}")
            return

        item_name = getattr(self, '_pending_drop_name', current.text() if current else "New Item")
        n = len(self.placed_items)
        L = data.get("length", 100)
        W = data.get("width", 100)
        
        if world_pos:
            new_x, new_y = world_pos
        elif n == 0:
            new_x, new_y = 0.0, 0.0
        else:
            max_right = max(p["x"] + p["data"].get("length", 100)/2 for p in self.placed_items)
            new_x = max_right + L/2 + 10
            new_y = 0.0
            
        new_item = {
            "name": f"{item_name}_{n + 1}",
            "data": dict(data),
            "x": new_x,
            "y": new_y,
            "rotation": 0,
            "color_idx": n % len(getattr(self, 'assembly_palette', ['#ff0000']))
        }
        self.placed_items.append(new_item)
        self.placed_list.addItem(new_item["name"])
        self.placed_list.setCurrentRow(len(self.placed_items) - 1)
        self.selected_placed_idx = len(self.placed_items) - 1
        
        if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
            self.update_puzzle_view()
        else:
            self.generate_box()
        self.mark_dirty()
        self.update_assembly_ui_state()

    def puzzle_dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def puzzle_dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def puzzle_dropEvent(self, event):
        path = event.mimeData().text()
        name_bytes = event.mimeData().data("application/x-toolbox-item-name").data()
        name = name_bytes.decode('utf-8') if name_bytes else "New Item"
        
        if path and os.path.exists(path):
            self._pending_drop_path = path
            self._pending_drop_name = name
            
            # 2D Scene -> World
            # scene_x = world_x * 1.5, scene_y = -world_y * 1.5
            scene_pos = self.puzzle_canvas.mapToScene(event.position().toPoint())
            world_pos = (scene_pos.x() / 1.5, -scene_pos.y() / 1.5)
            self.add_tool_to_assembly(world_pos=world_pos)
            
            self._pending_drop_path = None
            self._pending_drop_name = None
            event.acceptProposedAction()

    def view_dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def view_dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def view_dropEvent(self, event):
        path = event.mimeData().text()
        name_bytes = event.mimeData().data("application/x-toolbox-item-name").data()
        name = name_bytes.decode('utf-8') if name_bytes else "New Item"
        
        if path and os.path.exists(path):
            self._pending_drop_path = path
            self._pending_drop_name = name
            
            # 3D View -> World
            # Using raycasting to plane z=0
            p = event.position()
            ro, rd = self.compute_ray(p.x(), p.y())
            hit = self.ray_hit_plane_z(ro, rd, 0)
            if hit:
                self.add_tool_to_assembly(world_pos=(hit[0], hit[1]))
            else:
                self.add_tool_to_assembly()
            
            self._pending_drop_path = None
            self._pending_drop_name = None
            event.acceptProposedAction()

    def next_rotation_step(self):
        """Циклічний поворот обраного об'єкта під кожне натискання Ctrl+R (0 -> 90 -> 180 -> 270)."""
        idx = self.placed_list.currentRow()
        if idx < 0 or idx >= len(self.placed_items):
            return
            
        item = self.placed_items[idx]
        current_rot = int(item.get("rotation", 0)) % 360
        
        # Визначаємо наступний крок (кратний 90)
        new_rot = (current_rot + 90) % 360
        
        self.rotate_selected(new_rot)

    def rotate_selected(self, angle):
        idx = self.placed_list.currentRow()
        if idx < 0 or idx >= len(self.placed_items):
            QMessageBox.warning(self, "Увага", "Оберіть об'єкт зі збірки.")
            return

        item = self.placed_items[idx]
        item["rotation"] = angle

        if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
            self.update_puzzle_view()
        else:
            self.generate_box()
        self.mark_dirty()
        self.update_assembly_ui_state()

    def merge_two_items(self, src_idx, dst_idx):
        """
        Об'єднує дві деталі в один складений (compound) об'єкт.
        Кожна частина зберігає свій оригінальний прямокутник.
        Спільна внутрішня сторона між деталями прибирається (side = 2).
        """
        if src_idx < 0 or dst_idx < 0 or src_idx == dst_idx:
            QMessageBox.warning(self, "Об'єднання", "Оберіть іншу фігуру для об'єднання.")
            return

        item_a = self.placed_items[src_idx]
        item_b = self.placed_items[dst_idx]
        rot_a = item_a.get("rotation", 0) % 360
        rot_b = item_b.get("rotation", 0) % 360

        if rot_a != rot_b:
            QMessageBox.warning(self, "Об'єднання",
                                "Фігури мають різний кут повороту — об'єднання неможливе.")
            return

        rad = np.radians(-rot_a)

        # ── Всі "частини" обох елементів у локальних координатах ──────────────
        # Для compound-item беремо його підчастини; для простого — один прямокутник.
        def item_to_parts(item):
            """Повертає список {'data':…, 'loc_x':…, 'loc_y':…} у локальних (unrotated) координатах."""
            gx, gy = item["x"], item["y"]
            lx = gx * np.cos(rad) - gy * np.sin(rad)
            ly = gx * np.sin(rad) + gy * np.cos(rad)
            if item.get("type") == "compound":
                return [
                    {
                        "data": p["data"].copy(),
                        "loc_x": lx + p["rel_x"],
                        "loc_y": ly + p["rel_y"],
                    }
                    for p in item.get("parts", [])
                ]
            else:
                return [{"data": item["data"].copy(), "loc_x": lx, "loc_y": ly}]

        parts_a = item_to_parts(item_a)
        parts_b = item_to_parts(item_b)

        # ── Перевірка суміжності: шукаємо частини, що торкаються ─────────────
        tol_touch = 3.0
        merge_axis = None
        touching_a_pidx = None
        touching_b_pidx = None
        is_b_positive = None

        for ai, pa in enumerate(parts_a):
            La = pa["data"].get("length", 100)
            Wa = pa["data"].get("width", 100)
            for bi, pb in enumerate(parts_b):
                Lb = pb["data"].get("length", 100)
                Wb = pb["data"].get("width", 100)
                ddx = pb["loc_x"] - pa["loc_x"]
                ddy = pb["loc_y"] - pa["loc_y"]
                # по довжині?
                if abs(abs(ddx) - (La + Lb) / 2) < tol_touch and abs(ddy) < (Wa + Wb) / 2 - 0.5:
                    merge_axis = 'length'
                    is_b_positive = ddx > 0
                    touching_a_pidx = ai
                    touching_b_pidx = bi
                    break
                # по ширині?
                if abs(abs(ddy) - (Wa + Wb) / 2) < tol_touch and abs(ddx) < (La + Lb) / 2 - 0.5:
                    merge_axis = 'width'
                    is_b_positive = ddy > 0
                    touching_a_pidx = ai
                    touching_b_pidx = bi
                    break
            if merge_axis:
                break

        if merge_axis is None:
            QMessageBox.warning(self, "Об'єднання",
                                "Фігури не є сусідніми — жоден торець не торкається.\n"
                                "Підсуньте деталі впритул одна до одної і спробуйте знову.")
            return

        # ── Не прибираємо внутрішній конектор автоматично, щоб зберегти зварювання з іншими деталями ──
        # pa_touch і pb_touch зберігають свої оригінальні вкладки, а внутрішні будуть приховані під час рендерингу

        # ── Всі частини в локальних координатах ──────────────────────────────
        all_local_parts = parts_a + parts_b

        # ── Центр boundingbox всіх частин ─────────────────────────────────────
        min_lx = min(p["loc_x"] - p["data"].get("length", 100) / 2 for p in all_local_parts)
        max_lx = max(p["loc_x"] + p["data"].get("length", 100) / 2 for p in all_local_parts)
        min_ly = min(p["loc_y"] - p["data"].get("width",  100) / 2 for p in all_local_parts)
        max_ly = max(p["loc_y"] + p["data"].get("width",  100) / 2 for p in all_local_parts)
        cx = (min_lx + max_lx) / 2
        cy = (min_ly + max_ly) / 2

        # ── Compound-позиція у глобальних координатах ─────────────────────────
        # Inverse rotation: global = local * R^T
        new_gx =  cx * np.cos(rad) + cy * np.sin(rad)
        new_gy = -cx * np.sin(rad) + cy * np.cos(rad)

        parts_list = [
            {"data": p["data"], "rel_x": p["loc_x"] - cx, "rel_y": p["loc_y"] - cy}
            for p in all_local_parts
        ]

        # ── Зведений "data" для сумісності зі старим кодом ───────────────────
        # (bounding box розміри + параметри першої частини)
        first_data = all_local_parts[0]["data"] if all_local_parts else {}
        bbox_L = max_lx - min_lx
        bbox_W = max_ly - min_ly
        summary_data = dict(first_data)
        summary_data["length"] = bbox_L
        summary_data["width"]  = bbox_W

        new_item = {
            "name":      f"{item_a['name']}_merged",
            "x":         new_gx,
            "y":         new_gy,
            "rotation":  rot_a,
            "color_idx": item_a.get("color_idx", 0),
            "type":      "compound",
            "parts":     parts_list,
            "data":      summary_data,   # для сумісності з item["data"] скрізь
        }


        # ── Видаляємо обидва старі елементи ──────────────────────────────────
        idx1 = self.placed_items.index(item_a)
        idx2 = self.placed_items.index(item_b)
        for i in sorted([idx1, idx2], reverse=True):
            self.placed_items.pop(i)
            self.placed_list.takeItem(i)

        self.placed_items.append(new_item)
        self.placed_list.addItem(new_item["name"])

        self.mark_dirty()
        self.update_adaptive_grid()
        self.update_assembly_ui_state()
        self.update_puzzle_view()
        self.generate_box()
        self.statusBar().showMessage(
            f"✅ Фігури об'єднано у '{new_item['name']}'", 4000)

    def unmerge_compound_item(self, idx):
        """Розділяє compound-об'єкт на його складові частини."""
        if idx < 0 or idx >= len(self.placed_items):
            return
            
        item = self.placed_items[idx]
        if item.get("type") != "compound":
            return
            
        rot = item.get("rotation", 0)
        rad = np.radians(rot)
        gx, gy = item.get("x", 0), item.get("y", 0)
        
        new_items = []
        for i, p in enumerate(item.get("parts", [])):
            rx, ry = p["rel_x"], p["rel_y"]
            rot_rx = rx * np.cos(rad) - ry * np.sin(rad)
            rot_ry = rx * np.sin(rad) + ry * np.cos(rad)
            
            p_gx = gx + rot_rx
            p_gy = gy + rot_ry
            
            # Use original rotation plus any potential individual rotations if they were somehow individual
            # For now they inherently share the same orientation when merged, so original compound rotation
            new_item = {
                "name": f"{item['name'].replace('_merged', '')}_p{i+1}",
                "data": p["data"].copy(), 
                "rotation": rot,
                "x": p_gx,
                "y": p_gy,
                "color_idx": (item.get("color_idx", 0) + i) % len(getattr(self, 'assembly_palette', ['#ff0000']))
            }
            new_items.append(new_item)
            
        self.placed_items.pop(idx)
        self.placed_list.takeItem(idx)
        
        for ni in new_items:
            self.placed_items.append(ni)
            self.placed_list.addItem(ni["name"])
            
        self.mark_dirty()
        self.update_adaptive_grid()
        self.update_assembly_ui_state()
        self.update_puzzle_view()
        self.generate_box()
        self.statusBar().showMessage("✂️ Об'єднаний об'єкт успішно розділено.", 3000)

    def flatten_specific_edge(self, target_idx, p_idx, side_idx):
        """Робить конкретну грань фігури (або частини складеної фігури) рівною стінкою."""
        if target_idx < 0 or target_idx >= len(self.placed_items): return False
        
        target = self.placed_items[target_idx]
        side_names = ["side_top", "side_bottom", "side_left", "side_right"]
        
        if target.get("type") == "compound":
            parts = target.get("parts", [])
            if p_idx < 0 or p_idx >= len(parts): return False
            data_ref = parts[p_idx]["data"]
        else:
            data_ref = target["data"]
            
        s_name = side_names[side_idx]
        if int(data_ref.get(s_name, -1)) != 2:
            data_ref[s_name] = 2 # Пряма стінка
            return True
        return False

    def flatten_free_edges(self, target_idx):
        """Знаходить всі зовнішні грані вибраної фігури (чи складеної фігури), які не торкаються інших фігур, і робить їх рівними стінками."""
        if target_idx < 0 or target_idx >= len(self.placed_items): return False
        
        target = self.placed_items[target_idx]
        
        import numpy as np
        
        other_edges = []
        for i, other in enumerate(self.placed_items):
            if i == target_idx: continue
            rot = other.get("rotation", 0)
            rad = np.radians(rot)
            gx, gy = other.get("x", 0), other.get("y", 0)
            
            parts = other.get("parts", [{"data": other["data"], "rel_x": 0, "rel_y": 0}]) if other.get("type") == "compound" else [{"data": other["data"], "rel_x": 0, "rel_y": 0}]
            
            for p in parts:
                pL, pW = p["data"].get("length", 100), p["data"].get("width", 100)
                px = gx + (p["rel_x"] * np.cos(rad) - p["rel_y"] * np.sin(rad))
                py = gy + (p["rel_x"] * np.sin(rad) + p["rel_y"] * np.cos(rad))
                
                for side in range(4):
                    ex, ey = self.get_edge_center(px, py, pL, pW, side, rot)
                    other_edges.append((ex, ey))
                    
        t_rot = target.get("rotation", 0)
        t_rad = np.radians(t_rot)
        tx, ty = target.get("x", 0), target.get("y", 0)
        t_parts = target.get("parts", [{"data": target["data"], "rel_x": 0, "rel_y": 0}]) if target.get("type") == "compound" else [{"data": target["data"], "rel_x": 0, "rel_y": 0}]
        
        target_edge_centers = []
        for p_idx, p in enumerate(t_parts):
            pL, pW = p["data"].get("length", 100), p["data"].get("width", 100)
            px = tx + (p["rel_x"] * np.cos(t_rad) - p["rel_y"] * np.sin(t_rad))
            py = ty + (p["rel_x"] * np.sin(t_rad) + p["rel_y"] * np.cos(t_rad))
            
            for side in range(4):
                ex, ey = self.get_edge_center(px, py, pL, pW, side, t_rot)
                target_edge_centers.append({"p_idx": p_idx, "side": side, "ex": ex, "ey": ey, "p": p})

        changed_any = False
        side_names = ["side_top", "side_bottom", "side_left", "side_right"]
        
        for te in target_edge_centers:
            ex, ey = te["ex"], te["ey"]
            is_touching_external = any(((ex - ox)**2 + (ey - oy)**2)**0.5 < 1.0 for ox, oy in other_edges)
            
            is_touching_internal = False
            if target.get("type") == "compound":
                for other_te in target_edge_centers:
                    if other_te["p_idx"] != te["p_idx"]:
                        if ((ex - other_te["ex"])**2 + (ey - other_te["ey"])**2)**0.5 < 1.0:
                            is_touching_internal = True
                            break
                            
            if not is_touching_external and not is_touching_internal:
                data_ref = te["p"]["data"]
                s_name = side_names[te["side"]]
                
                if int(data_ref.get(s_name, -1)) != 2:
                    data_ref[s_name] = 2 # Пряма стінка
                    changed_any = True

        return changed_any

    # Залишаємо для сумісності зі старим кодом
    def merge_adjacent_items(self, idx):
        """Застарілий метод — активує режим вибору цілі."""
        self._merge_source_idx = idx
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))
        self.update_puzzle_view()
        self.statusBar().showMessage(
            f"🔗 Оберіть фігуру для об'єднання з '{self.placed_items[idx]['name']}' — ЛКМ вибір, ПКМ скасувати"
        )




