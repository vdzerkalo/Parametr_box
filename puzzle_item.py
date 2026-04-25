import sys
import numpy as np
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QMenu, QStyle, QApplication
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QFontMetricsF, QAction, QCursor, QPainterPath, QPixmap, QIcon
from PySide6.QtCore import Qt, QRectF, QTimer

class PuzzleBoxItem(QGraphicsRectItem):
    """A draggable flat rectangle with full XY-projection rendering."""
    SCALE = 1.5   # mm → pixels  (smaller preview)

    def __init__(self, placed_idx, app):
        item  = app.placed_items[placed_idx]
        data  = item["data"]
        rot   = item.get("rotation", 0)

        # Always use physical dims — Qt setRotation() handles the visual rotation
        L = data.get("length", 100) * self.SCALE
        W = data.get("width",  100) * self.SCALE

        # Expand bounding rect to include possible tab protrusions
        wt = max(data.get("wall_t", 3), 1.5) * self.SCALE
        super().__init__(-L/2 - wt, -W/2 - wt, L + 2*wt, W + 2*wt)
        self.placed_idx = placed_idx
        self.app = app
        self._L = L; self._W = W; self._wt = wt

        # Store palette color
        colors = app.assembly_palette
        cidx   = item.get("color_idx", 0) % len(colors)
        self._color = QColor(*[int(c * 255) for c in colors[cidx][:3]])
        
        self.group_id = item.get("group_id", None)

        self.setBrush(Qt.NoBrush)
        self.setPen(Qt.NoPen)

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setPos(item.get("x", 0) * self.SCALE,
                    item.get("y", 0) * self.SCALE)
        self.setRotation(rot)
        self.setToolTip(f"{item['name']}\n"
                        f"{data.get('length',0)}×{data.get('width',0)}×{data.get('height',0)} мм")

    # ---- real-time position sync ----
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            item = self.app.placed_items[self.placed_idx]
            item["x"] = value.x() / self.SCALE
            item["y"] = value.y() / self.SCALE
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            if self.group_id is not None and getattr(self, '_internal_selection', False) == False:
                # Synchronize group selection
                for other in self.scene().items():
                    if isinstance(other, (PuzzleBoxItem, CompoundPuzzleItem)) and other != self:
                        if getattr(other, 'group_id', None) == self.group_id:
                            other._internal_selection = True
                            other.setSelected(value)
                            other._internal_selection = False
        return super().itemChange(change, value)

    def mouseMoveEvent(self, ev):
        if not (hasattr(self.app, 'collision_cb') and self.app.collision_cb.isChecked()):
            return super().mouseMoveEvent(ev)
            
        scene = self.scene()
        if not scene: return super().mouseMoveEvent(ev)
        
        old_poses = {item: item.pos() for item in scene.selectedItems()}
        super().mouseMoveEvent(ev)
        
        conflict = False
        for item in scene.selectedItems():
            if not isinstance(item, (PuzzleBoxItem, CompoundPuzzleItem)): continue
            colliding = item.collidingItems()
            for c in colliding:
                if isinstance(c, (PuzzleBoxItem, CompoundPuzzleItem)) and not c.isSelected():
                    conflict = True
                    break
            if conflict: break
                
        if conflict:
            for item, pos in old_poses.items():
                item.setPos(pos)

    # ---- RMB Context Menu / Rotate ----
    def mousePressEvent(self, ev):
        merge_src = getattr(self.app, '_merge_source_idx', -1)
        flatten_mode = getattr(self.app, '_flatten_mode', False)

        if ev.button() == Qt.LeftButton:
            if flatten_mode:
                if QApplication.keyboardModifiers() & Qt.ShiftModifier:
                    # Режим "авто": всі вільні краї
                    if self.app.flatten_free_edges(self.placed_idx):
                        self.app.mark_dirty()
                        self.app.generate_box()
                        self.app.statusBar().showMessage(f"🔨 Всі вільні краї '{self.app.placed_items[self.placed_idx]['name']}' вирівняно", 3000)
                else:
                    # Режим "конкретний край"
                    lx, ly = ev.pos().x(), ev.pos().y()
                    L, W = self._L, self._W
                    
                    dists = [
                        abs(ly + W/2), # 0: Top
                        abs(ly - W/2), # 1: Bottom
                        abs(lx + L/2), # 2: Left
                        abs(lx - L/2)  # 3: Right
                    ]
                    side_idx = int(np.argmin(dists))
                    min_dist = dists[side_idx]
                    
                    if min_dist < 30:
                        if self.app.flatten_specific_edge(self.placed_idx, 0, side_idx):
                            self.app.mark_dirty()
                            self.app.generate_box()
                            side_name = ["Верхній", "Нижній", "Лівий", "Правий"][side_idx]
                            self.app.statusBar().showMessage(f"🔨 OK: {side_name} край вирівняно. ПКМ для виходу.", 3000)
                        else:
                            self.app.statusBar().showMessage("Цей край уже рівний.", 2000)
                    else:
                        self.app.statusBar().showMessage("Клікніть ближче до краю фігури.", 2000)
                
                # НЕ скидаємо _flatten_mode, щоб можна було клікати далі
                self.app.update_puzzle_view()
                ev.accept()
                return
                
            if merge_src >= 0:
                # ── Режим вибору цілі для злиття ──────────────────────────────
                if self.placed_idx == merge_src:
                    # Клік на ту саму фігуру — скасувати
                    self.app._merge_source_idx = -1
                    QApplication.restoreOverrideCursor()
                    self.app.update_puzzle_view()
                    self.app.statusBar().showMessage("Об'єднання скасовано", 2000)
                else:
                    self.app._merge_source_idx = -1
                    QApplication.restoreOverrideCursor()
                    self.app.merge_two_items(merge_src, self.placed_idx)
                ev.accept()
                return

        if ev.button() == Qt.RightButton:
            if flatten_mode:
                self.app._flatten_mode = False
                QApplication.restoreOverrideCursor()
                self.app.update_puzzle_view()
                self.app.statusBar().showMessage("Створення стінок скасовано", 2000)
                ev.accept()
                return
                
            # Якщо активний режим злиття — скасувати при ПКМ
            if merge_src >= 0:
                self.app._merge_source_idx = -1
                QApplication.restoreOverrideCursor()
                self.app.update_puzzle_view()
                self.app.statusBar().showMessage("Об'єднання скасовано", 2000)
                ev.accept()
                return

            self.app.placed_list.setCurrentRow(self.placed_idx)
            menu = QMenu()
            
            rotate_act = QAction("Повернути (90°)", self.app)
            rotate_act.setIcon(self.app.style().standardIcon(QStyle.SP_BrowserReload))
            rotate_act.triggered.connect(self.rotate_item)
            menu.addAction(rotate_act)
            
            menu.addSeparator()
            copy_menu = menu.addMenu("Копія...")
            copy_menu.setIcon(self.app.style().standardIcon(QStyle.SP_FileDialogNewFolder))
            
            sides = [
                ("Зверху", 0, QStyle.SP_ArrowUp), 
                ("Знизу", 1, QStyle.SP_ArrowDown), 
                ("Зліва", 2, QStyle.SP_ArrowLeft), 
                ("Справа", 3, QStyle.SP_ArrowRight)
            ]
            for label, side_idx, icon_type in sides:
                act = QAction(label, self.app)
                act.setIcon(self.app.style().standardIcon(icon_type))
                act.triggered.connect(lambda checked, s=side_idx: self.app.copy_to_side(self.placed_idx, s))
                copy_menu.addAction(act)
                
            menu.addSeparator()
            def create_split_icon(horizontal=True):
                pix = QPixmap(32, 32)
                pix.fill(Qt.transparent)
                painter = QPainter(pix)
                painter.setRenderHint(QPainter.Antialiasing)
                
                # Кольори
                border_color = QColor(150, 150, 150)
                line_color = QColor(255, 100, 100) # Червона лінія розрізу
                bg_color = QColor(60, 60, 60)
                
                # Квадрат (фігура)
                painter.setBrush(QBrush(bg_color))
                painter.setPen(QPen(border_color, 1.5))
                painter.drawRoundedRect(4, 4, 24, 24, 3, 3)
                
                # Лінія розрізу (схема)
                pen = QPen(line_color, 2, Qt.DashLine)
                painter.setPen(pen)
                if horizontal:
                    painter.drawLine(2, 16, 30, 16)
                else:
                    painter.drawLine(16, 2, 16, 30)
                
                painter.end()
                return QIcon(pix)

            split_menu = menu.addMenu("Розбити фігуру...")
            split_menu.setIcon(self.app.style().standardIcon(QStyle.SP_FileDialogContentsView))
            
            split_h_act = QAction("По горизонталі", self.app)
            split_h_act.setIcon(create_split_icon(True))
            split_h_act.triggered.connect(lambda checked=False: self.app.split_item(self.placed_idx, 'x'))
            split_menu.addAction(split_h_act)
            
            split_v_act = QAction("По вертикалі", self.app)
            split_v_act.setIcon(create_split_icon(False))
            split_v_act.triggered.connect(lambda checked=False: self.app.split_item(self.placed_idx, 'y'))
            split_menu.addAction(split_v_act)
            
            menu.addSeparator()
            merge_act = QAction("Об'єднати...", self.app)
            merge_act.setIcon(self.app.style().standardIcon(QStyle.SP_DialogYesButton))
            merge_act.triggered.connect(lambda checked=False: self._start_merge_mode())
            menu.addAction(merge_act)
            
            flatten_act = QAction("Стінки на вільних краях (авто)", self.app)
            flatten_act.setIcon(self.app.style().standardIcon(QStyle.SP_DialogResetButton))
            flatten_act.triggered.connect(lambda checked=False: self._start_flatten_mode())
            menu.addAction(flatten_act)

            menu.addSeparator()
            if hasattr(self.app, 'group_selected_items'):
                group_act = QAction("Згрупувати (Ctrl+G)", self.app)
                group_act.triggered.connect(lambda: self.app.group_selected_items())
                menu.addAction(group_act)

                ungroup_act = QAction("Розгрупувати (Ctrl+Shift+G)", self.app)
                ungroup_act.triggered.connect(lambda: self.app.ungroup_selected_items())
                menu.addAction(ungroup_act)
            
            menu.exec(ev.screenPos())
            ev.accept()

        else:
            self.app.placed_list.setCurrentRow(self.placed_idx)
            super().mousePressEvent(ev)

    def _start_merge_mode(self):
        """Активує режим вибору цільової фігури для злиття."""
        self.app._merge_source_idx = self.placed_idx
        # Скидаємо інший режим, якщо був
        self.app._flatten_mode = False
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))
        self.app.update_puzzle_view()  # перемалює з підсвіткою джерела
        self.app.statusBar().showMessage(
            f"🔗 Оберіть фігуру для об'єднання з '{self.app.placed_items[self.placed_idx]['name']}' — ЛКМ вибір, ПКМ скасувати"
        )

    def _start_flatten_mode(self):
        """Активує режим заповнення вільних країв."""
        self.app._flatten_mode = True
        self.app._merge_source_idx = -1
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))
        self.app.update_puzzle_view()
        self.app.statusBar().showMessage(
            "🔨 МОЛОТОК: Клікніть ЛКМ біля конкретного краю, щоб вирівняти його. Shift+ЛКМ — всі вільні краї. ПКМ — вихід."
        )


    def rotate_item(self):
        item = self.app.placed_items[self.placed_idx]
        item["rotation"] = (item.get("rotation", 0) + 90) % 360
        self.app.mark_dirty()
        QTimer.singleShot(0, lambda: (self.app.ensure_unique_colors_for_assembly(), self.app.update_puzzle_view(), self.app.generate_box()))

    # ---- snap & refresh on LMB release (deferred so scene isn't cleared mid-event) ----
    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.LeftButton:
            idx = self.placed_idx
            app = self.app
            # Defer: scene.clear() inside an item's own event causes Qt issues
            QTimer.singleShot(0, lambda: (app.try_auto_snap(idx), app.ensure_unique_colors_for_assembly(), app.mark_dirty(), app.generate_box(), app.update_puzzle_view()))

    # ---- full XY cross-section paint ----
    def paint(self, painter, option, widget=None):
        if self.placed_idx >= len(self.app.placed_items):
            return
        item = self.app.placed_items[self.placed_idx]
        data = item["data"]
        L, W, wt = self._L, self._W, self._wt

        c      = self._color
        wall_c = c.darker(130)
        cav_c  = c.darker(175)  # hollow cavity
        tab_c  = c.lighter(115) # tab protrusions

        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фокусування: тьмяність для неактивних елементів
        has_sel = self.app.placed_list.currentRow() >= 0
        if has_sel and not self.isSelected():
            painter.setOpacity(0.35)
        else:
            painter.setOpacity(1.0)

        # ── Outer wall fill ──────────────────────────────────────────────────
        outer = QRectF(-L/2, -W/2, L, W)
        inner = QRectF(-L/2 + wt, -W/2 + wt, L - 2*wt, W - 2*wt)

        # Draw walls
        painter.setBrush(QBrush(wall_c))
        painter.setPen(Qt.NoPen)
        painter.drawRect(outer)

        # Draw inner cavity
        painter.setBrush(QBrush(cav_c))
        painter.drawRect(inner)

        # Read tab parameters for accurate 2D rendering
        t_base  = data.get("tab_base", 20) * self.SCALE
        t_depth = data.get("tab_depth", 10) * self.SCALE

        # ── Tabs on each edge ────────────────────────────────────────────────
        def draw_tabs(edge, count, male):
            """Draw tab protrusions (male) or slots (female) on an edge.
            male=True  → rectangle protrudes outside the outer box boundary
            male=False → slot cut into the wall from the inner edge outward
            """
            if count <= 0:
                return
            
            # Match 3D model's centering logic
            if edge in ('top', 'bottom'):
                edge_len = L
                p_len = data.get(f"side_{edge}_parent_length", edge_len / self.SCALE) * self.SCALE
                p_count = int(data.get(f"side_{edge}_parent_count", count))
                p_offset = data.get(f"side_{edge}_parent_offset", 0.0) * self.SCALE

                seg_len = p_len / (2 * p_count + 1)
                tab_w = min(t_base, seg_len * 0.9)
                tab_h = t_depth
                for k in range(p_count):
                    parent_tab_start = -p_len/2 + seg_len * (2*k + 1)
                    local_tab_start = parent_tab_start - p_offset
                    ox = local_tab_start + (seg_len - tab_w)/2
                    
                    if -edge_len/2 - t_base/2 <= ox + tab_w/2 <= edge_len/2 + t_base/2:
                        if edge == 'top':
                            r = QRectF(ox, -W/2 - tab_h, tab_w, tab_h) if male \
                                else QRectF(ox, -W/2, tab_w, tab_h)
                        else:  # bottom
                            r = QRectF(ox, W/2, tab_w, tab_h) if male \
                                else QRectF(ox, W/2 - tab_h, tab_w, tab_h)
                        painter.setBrush(QBrush(tab_c if male else cav_c))
                        painter.setPen(QPen(wall_c.darker(150), 0.8))
                        painter.drawRect(r)
            else:  # left / right
                edge_len = W
                p_len = data.get(f"side_{edge}_parent_length", edge_len / self.SCALE) * self.SCALE
                p_count = int(data.get(f"side_{edge}_parent_count", count))
                p_offset = data.get(f"side_{edge}_parent_offset", 0.0) * self.SCALE

                seg_len = p_len / (2 * p_count + 1)
                tab_w = min(t_base, seg_len * 0.9)
                tab_h = t_depth
                for k in range(p_count):
                    parent_tab_start = -p_len/2 + seg_len * (2*k + 1)
                    local_tab_start = parent_tab_start - p_offset
                    oy = local_tab_start + (seg_len - tab_w)/2
                    
                    if -edge_len/2 - t_base/2 <= oy + tab_w/2 <= edge_len/2 + t_base/2:
                        if edge == 'left':
                            r = QRectF(-L/2 - tab_h, oy, tab_h, tab_w) if male \
                                else QRectF(-L/2, oy, tab_h, tab_w)
                        else:  # right
                            r = QRectF(L/2, oy, tab_h, tab_w) if male \
                                else QRectF(L/2 - tab_h, oy, tab_h, tab_w)
                        painter.setBrush(QBrush(tab_c if male else cav_c))
                        painter.setPen(QPen(wall_c.darker(150), 0.8))
                        painter.drawRect(r)


        # Read tab parameters from preset data
        # side_top/bottom/left/right: 0=Шип(male), 1=Паз(female/slot), 2=Пряма(none)
        # side_*_count: number of tabs on that side
        s_top    = int(data.get("side_top",    0))
        s_bottom = int(data.get("side_bottom", 1))
        s_left   = int(data.get("side_left",   1))
        s_right  = int(data.get("side_right",  0))

        c_top    = int(data.get("side_top_count",    1)) if s_top    < 2 else 0
        c_bottom = int(data.get("side_bottom_count", 1)) if s_bottom < 2 else 0
        c_left   = int(data.get("side_left_count",   1)) if s_left   < 2 else 0
        c_right  = int(data.get("side_right_count",  1)) if s_right  < 2 else 0

        # 0=Шип(protrudes out), 1=Паз(indented slot), 2=flat
        draw_tabs('top',    c_top,    s_top    == 0)
        draw_tabs('bottom', c_bottom, s_bottom == 0)
        draw_tabs('left',   c_left,   s_left   == 0)
        draw_tabs('right',  c_right,  s_right  == 0)

        # ── Outer border ─────────────────────────────────────────────────────
        merge_src = getattr(self.app, '_merge_source_idx', -1)
        flatten_mode = getattr(self.app, '_flatten_mode', False)
        
        if merge_src >= 0 and self.placed_idx == merge_src:
            # Джерело злиття — яскрава жовта рамка
            sel_color = QColor(255, 200, 0)
            painter.setPen(QPen(sel_color, 3.0))
        elif merge_src >= 0 and self.placed_idx != merge_src:
            # Потенційна ціль — блакитна пульсуюча рамка
            sel_color = QColor(100, 220, 255)
            painter.setPen(QPen(sel_color, 2.5))
        elif flatten_mode and QStyle.State_MouseOver in option.state:
            sel_color = QColor(255, 100, 100)
            painter.setPen(QPen(sel_color, 3.0))
        elif self.isSelected():
            # РАЙДУЖНА РАМКА
            from PySide6.QtGui import QConicalGradient
            grad = QConicalGradient(0, 0, self.app._rainbow_phase)
            grad.setColorAt(0.0, QColor(255, 0, 0))
            grad.setColorAt(0.2, QColor(255, 255, 0))
            grad.setColorAt(0.4, QColor(0, 255, 0))
            grad.setColorAt(0.6, QColor(0, 255, 255))
            grad.setColorAt(0.8, QColor(0, 0, 255))
            grad.setColorAt(1.0, QColor(255, 0, 255))
            
            pen = QPen(QBrush(grad), 3.0)
            painter.setPen(pen)
        else:
            sel_color = QColor(255, 255, 255, 180)
            painter.setPen(QPen(sel_color, 1.5))
        
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(outer)

        # ── Label (always horizontal) ────────────────────────────────────────
        hide_labels = getattr(self.app, 'hide_labels_cb', None)
        if not (hide_labels and hide_labels.isChecked()):
            painter.save()
            # Coordinate system is already rotated/scaled by QGraphicsItem.
            # We rotate back to keep text horizontal.
            painter.rotate(-self.rotation())
            
            # Determine visual dims for the text box (if rotated 90/270, the box is 'flipped' visually)
            rot = int(self.rotation()) % 360
            if rot in [90, 270]:
                text_rect = QRectF(-W/2, -L/2, W, L)
            else:
                text_rect = QRectF(-L/2, -W/2, L, W)
                
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(font)
            fm = QFontMetricsF(font)
            txt = item["name"]
            tw = fm.horizontalAdvance(txt)
            th = fm.height()
            
            # Only draw if it fits somewhat inside the box
            if tw < max(L, W) * 1.5:
                 painter.drawText(text_rect, Qt.AlignCenter, txt)
            painter.restore()

        # ── Hover highlight ──────────────────────────────────────────────────
        if QStyle.State_MouseOver in option.state:
            hover_c = QColor(255, 255, 255, 40)
            painter.setBrush(QBrush(hover_c))
            painter.setPen(Qt.NoPen)
            painter.drawRect(outer)


# ─────────────────────────────────────────────────────────────────────────────
class CompoundPuzzleItem(QGraphicsItem):
    """
    Складений пазл-об'єкт з кількох прямокутних частин.
    Дані: placed_items[placed_idx]["parts"] = [{"data": {...}, "rel_x": …, "rel_y": …}, …]
    """
    SCALE = 1.5

    def __init__(self, placed_idx, app):
        super().__init__()
        self.placed_idx = placed_idx
        self.app = app
        item = app.placed_items[placed_idx]

        colors = app.assembly_palette
        cidx = item.get("color_idx", 0) % len(colors)
        self._color = QColor(*[int(c * 255) for c in colors[cidx][:3]])
        
        self.group_id = item.get("group_id", None)

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setPos(item.get("x", 0) * self.SCALE,
                    item.get("y", 0) * self.SCALE)
        self.setRotation(item.get("rotation", 0))
        self.setToolTip(item["name"])

    def _parts(self):
        return self.app.placed_items[self.placed_idx].get("parts", [])

    def boundingRect(self):
        s = self.SCALE
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        for p in self._parts():
            d = p["data"]
            rx, ry = p["rel_x"] * s, p["rel_y"] * s
            L = d.get("length", 100) * s
            W = d.get("width",  100) * s
            wt = max(d.get("wall_t", 3), 1.5) * s
            min_x = min(min_x, rx - L/2 - wt)
            min_y = min(min_y, ry - W/2 - wt)
            max_x = max(max_x, rx + L/2 + wt)
            max_y = max(max_y, ry + W/2 + wt)
        if min_x == float('inf'):
            return QRectF(0, 0, 0, 0)
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def shape(self):
        path = QPainterPath()
        s = self.SCALE
        for p in self._parts():
            d = p["data"]
            rx, ry = p["rel_x"] * s, p["rel_y"] * s
            L = d.get("length", 100) * s
            W = d.get("width",  100) * s
            wt = max(d.get("wall_t", 3), 1.5) * s
            rect = QRectF(rx - L/2 - wt, ry - W/2 - wt, L + 2*wt, W + 2*wt)
            path.addRect(rect)
        return path

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            item = self.app.placed_items[self.placed_idx]
            item["x"] = value.x() / self.SCALE
            item["y"] = value.y() / self.SCALE
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            if getattr(self, "group_id", None) is not None and getattr(self, '_internal_selection', False) == False:
                # Synchronize group selection
                for other in self.scene().items():
                    if isinstance(other, (PuzzleBoxItem, CompoundPuzzleItem)) and other != self:
                        if getattr(other, 'group_id', None) == self.group_id:
                            other._internal_selection = True
                            other.setSelected(value)
                            other._internal_selection = False
        return super().itemChange(change, value)

    def mouseMoveEvent(self, ev):
        if not (hasattr(self.app, 'collision_cb') and self.app.collision_cb.isChecked()):
            return super().mouseMoveEvent(ev)
            
        scene = self.scene()
        if not scene: return super().mouseMoveEvent(ev)
        
        old_poses = {item: item.pos() for item in scene.selectedItems()}
        super().mouseMoveEvent(ev)
        
        conflict = False
        for item in scene.selectedItems():
            if not isinstance(item, (PuzzleBoxItem, CompoundPuzzleItem)): continue
            colliding = item.collidingItems()
            for c in colliding:
                if isinstance(c, (PuzzleBoxItem, CompoundPuzzleItem)) and not c.isSelected():
                    conflict = True
                    break
            if conflict: break
                
        if conflict:
            for item, pos in old_poses.items():
                item.setPos(pos)

    def mousePressEvent(self, ev):
        """Делегуємо ту саму логіку що й у PuzzleBoxItem."""
        merge_src = getattr(self.app, '_merge_source_idx', -1)
        flatten_mode = getattr(self.app, '_flatten_mode', False)
        
        if ev.button() == Qt.LeftButton:
            if flatten_mode:
                if QApplication.keyboardModifiers() & Qt.ShiftModifier:
                    # Режим "авто": всі вільні краї для всього compound
                    if self.app.flatten_free_edges(self.placed_idx):
                        self.app.mark_dirty()
                        self.app.generate_box()
                        self.app.statusBar().showMessage(f"🔨 Всі вільні краї секцій вирівняно (Shift)", 3000)
                else:
                    # Потрібно визначити, до якої саме частини і якого краю клікнули
                    lx, ly = ev.pos().x(), ev.pos().y()
                    s = self.SCALE
                    
                    best_part_idx = -1
                    best_side_idx = -1
                    min_d = float('inf')
                    
                    for p_idx, p in enumerate(self._parts()):
                        d = p["data"]
                        rx, ry = p["rel_x"] * s, p["rel_y"] * s
                        L, W = d.get("length", 100) * s, d.get("width", 100) * s
                        
                        p_dists = [
                            abs(ly - (ry - W/2)), # top
                            abs(ly - (ry + W/2)), # bottom
                            abs(lx - (rx - L/2)), # left
                            abs(lx - (rx + L/2))  # right
                        ]
                        
                        for s_idx, dist in enumerate(p_dists):
                            if dist < min_d:
                                min_d = dist
                                best_part_idx = p_idx
                                best_side_idx = s_idx
                    
                    if best_part_idx >= 0 and min_d < 30:
                        if self.app.flatten_specific_edge(self.placed_idx, best_part_idx, best_side_idx):
                            self.app.mark_dirty()
                            self.app.generate_box()
                            side_name = ["Верхній", "Нижній", "Лівий", "Правий"][best_side_idx]
                            self.app.statusBar().showMessage(f"🔨 OK: {side_name} край секції {best_part_idx+1} вирівняно. ПКМ вихід.", 3000)
                        else:
                            self.app.statusBar().showMessage("Цей край уже рівний.", 2000)
                    else:
                        self.app.statusBar().showMessage("Клікніть ближче до краю секції.", 2000)

                self.app.update_puzzle_view()
                ev.accept()
                return

            if merge_src >= 0:
                if self.placed_idx == merge_src:
                    self.app._merge_source_idx = -1
                    QApplication.restoreOverrideCursor()
                    self.app.update_puzzle_view()
                    self.app.statusBar().showMessage("Об'єднання скасовано", 2000)
                else:
                    self.app._merge_source_idx = -1
                    QApplication.restoreOverrideCursor()
                    self.app.merge_two_items(merge_src, self.placed_idx)
                ev.accept()
                return

        if ev.button() == Qt.RightButton:
            if flatten_mode:
                self.app._flatten_mode = False
                QApplication.restoreOverrideCursor()
                self.app.update_puzzle_view()
                self.app.statusBar().showMessage("Створення стінок скасовано", 2000)
                ev.accept()
                return
                
            if merge_src >= 0:
                self.app._merge_source_idx = -1
                QApplication.restoreOverrideCursor()
                self.app.update_puzzle_view()
                self.app.statusBar().showMessage("Об'єднання скасовано", 2000)
                ev.accept()
                return

            self.app.placed_list.setCurrentRow(self.placed_idx)
            menu = QMenu()
            merge_act = QAction("Об'єднати...", self.app)
            merge_act.setIcon(self.app.style().standardIcon(QStyle.SP_DialogYesButton))
            merge_act.triggered.connect(lambda: self._start_merge_mode())
            menu.addAction(merge_act)
            
            unmerge_act = QAction("Розділити", self.app)
            unmerge_act.setIcon(self.app.style().standardIcon(QStyle.SP_TrashIcon))
            unmerge_act.triggered.connect(lambda: self.app.unmerge_compound_item(self.placed_idx))
            menu.addAction(unmerge_act)
            
            flatten_act = QAction("Стінки на вільних краях (авто)", self.app)
            flatten_act.setIcon(self.app.style().standardIcon(QStyle.SP_DialogResetButton))
            flatten_act.triggered.connect(lambda: self._start_flatten_mode())
            menu.addAction(flatten_act)
            
            menu.addSeparator()
            if hasattr(self.app, 'group_selected_items'):
                group_act = QAction("Згрупувати (Ctrl+G)", self.app)
                group_act.triggered.connect(lambda: self.app.group_selected_items())
                menu.addAction(group_act)

                ungroup_act = QAction("Розгрупувати (Ctrl+Shift+G)", self.app)
                ungroup_act.triggered.connect(lambda: self.app.ungroup_selected_items())
                menu.addAction(ungroup_act)
            
            menu.exec(ev.screenPos())
            ev.accept()
        else:
            self.app.placed_list.setCurrentRow(self.placed_idx)
            super().mousePressEvent(ev)

    def _start_merge_mode(self):
        self.app._merge_source_idx = self.placed_idx
        self.app._flatten_mode = False
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))
        self.app.update_puzzle_view()
        self.app.statusBar().showMessage(
            f"🔗 Оберіть фігуру для об'єднання — ЛКМ вибір, ПКМ скасувати"
        )

    def _start_flatten_mode(self):
        self.app._flatten_mode = True
        self.app._merge_source_idx = -1
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))
        self.app.update_puzzle_view()
        self.app.statusBar().showMessage(
            "🔨 МОЛОТОК: Клікніть ЛКМ біля конкретного краю секції, щоб вирівняти його. Shift+ЛКМ — всі вільні краї. ПКМ — вихід."
        )

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.LeftButton:
            idx = self.placed_idx
            app = self.app
            QTimer.singleShot(0, lambda: (app.try_auto_snap(idx), app.ensure_unique_colors_for_assembly(), app.mark_dirty(),
                                          app.generate_box(), app.update_puzzle_view()))

    def _build_cache(self):
        s = self.SCALE
        self._cached_union_path = QPainterPath()
        self._cached_outer = []
        self._cached_inner = []
        self._cached_male_tabs = []
        self._cached_female_tabs = []

        for p in self._parts():
            d = p["data"]
            rx = p["rel_x"] * s
            ry = p["rel_y"] * s
            L  = d.get("length", 100) * s
            W  = d.get("width",  100) * s
            wt = max(d.get("wall_t", 3), 1.5) * s
            t_base  = d.get("tab_base",  20) * s
            t_depth = d.get("tab_depth", 10) * s

            outer = QRectF(rx - L/2, ry - W/2, L, W)
            inner = QRectF(rx - L/2 + wt, ry - W/2 + wt, L - 2*wt, W - 2*wt)

            self._cached_outer.append(outer)
            self._cached_inner.append(inner)

            part_path = QPainterPath()
            part_path.addRect(outer)
            self._cached_union_path = self._cached_union_path.united(part_path)

            s_top    = int(d.get("side_top",    0))
            s_bottom = int(d.get("side_bottom", 1))
            s_left   = int(d.get("side_left",   1))
            s_right  = int(d.get("side_right",  0))
            c_top    = int(d.get("side_top_count",    1)) if s_top    < 2 else 0
            c_bottom = int(d.get("side_bottom_count", 1)) if s_bottom < 2 else 0
            c_left   = int(d.get("side_left_count",   1)) if s_left   < 2 else 0
            c_right  = int(d.get("side_right_count",  1)) if s_right  < 2 else 0

            def is_internal(tx, ty):
                for other_p in self._parts():
                    if other_p is p: continue
                    o_d = other_p["data"]
                    o_rx = other_p["rel_x"] * s
                    o_ry = other_p["rel_y"] * s
                    o_L = o_d.get("length", 100) * s
                    o_W = o_d.get("width",  100) * s
                    if (o_rx - o_L/2 <= tx <= o_rx + o_L/2) and (o_ry - o_W/2 <= ty <= o_ry + o_W/2):
                        return True
                return False

            def collect_tabs(edge, count, male):
                if count <= 0: return
                if edge in ('top', 'bottom'):
                    edge_len = L
                    p_len    = d.get(f"side_{edge}_parent_length", edge_len / s) * s
                    p_count  = int(d.get(f"side_{edge}_parent_count", count))
                    p_offset = d.get(f"side_{edge}_parent_offset", 0.0) * s
                    seg_len  = p_len / (2 * p_count + 1)
                    tab_w    = min(t_base, seg_len * 0.9)
                    tab_h    = t_depth
                    for k in range(p_count):
                        ox = rx - p_offset - p_len/2 + seg_len*(2*k+1) + (seg_len - tab_w)/2
                        if -edge_len/2 - t_base/2 <= ox - rx + tab_w/2 <= edge_len/2 + t_base/2:
                            ty = ry - W/2 - 1.0 if edge == 'top' else ry + W/2 + 1.0
                            if is_internal(ox + tab_w/2, ty):
                                continue
                            if edge == 'top':
                                r = QRectF(ox, ry - W/2 - tab_h, tab_w, tab_h) if male else QRectF(ox, ry - W/2, tab_w, tab_h)
                            else:
                                r = QRectF(ox, ry + W/2, tab_w, tab_h) if male else QRectF(ox, ry + W/2 - tab_h, tab_w, tab_h)
                            if male: self._cached_male_tabs.append(r)
                            else: self._cached_female_tabs.append(r)
                else:
                    edge_len = W
                    p_len    = d.get(f"side_{edge}_parent_length", edge_len / s) * s
                    p_count  = int(d.get(f"side_{edge}_parent_count", count))
                    p_offset = d.get(f"side_{edge}_parent_offset", 0.0) * s
                    seg_len  = p_len / (2 * p_count + 1)
                    tab_w    = min(t_base, seg_len * 0.9)
                    tab_h    = t_depth
                    for k in range(p_count):
                        oy = ry - p_offset - p_len/2 + seg_len*(2*k+1) + (seg_len - tab_w)/2
                        if -edge_len/2 - t_base/2 <= oy - ry + tab_w/2 <= edge_len/2 + t_base/2:
                            tx = rx - L/2 - 1.0 if edge == 'left' else rx + L/2 + 1.0
                            if is_internal(tx, oy + tab_w/2):
                                continue
                            if edge == 'left':
                                r = QRectF(rx - L/2 - tab_h, oy, tab_h, tab_w) if male else QRectF(rx - L/2, oy, tab_h, tab_w)
                            else:
                                r = QRectF(rx + L/2, oy, tab_h, tab_w) if male else QRectF(rx + L/2 - tab_h, oy, tab_h, tab_w)
                            if male: self._cached_male_tabs.append(r)
                            else: self._cached_female_tabs.append(r)

            collect_tabs('top',    c_top,    s_top    == 0)
            collect_tabs('bottom', c_bottom, s_bottom == 0)
            collect_tabs('left',   c_left,   s_left   == 0)
            collect_tabs('right',  c_right,  s_right  == 0)

    def paint(self, painter, option, widget=None):
        if self.placed_idx >= len(self.app.placed_items):
            return
        if not hasattr(self, '_cached_union_path'):
            self._build_cache()

        s = self.SCALE
        c = self._color
        wall_c = c.darker(130)
        cav_c  = c.darker(175)
        tab_c  = c.lighter(115)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фокусування: тьмяність для неактивних елементів
        has_sel = self.app.placed_list.currentRow() >= 0
        if has_sel and not self.isSelected():
            painter.setOpacity(0.35)
        else:
            painter.setOpacity(1.0)

        painter.setBrush(QBrush(wall_c))
        painter.setPen(Qt.NoPen)
        for r in self._cached_outer: painter.drawRect(r)
        
        painter.setBrush(QBrush(cav_c))
        for r in self._cached_inner: painter.drawRect(r)
        
        painter.setPen(QPen(wall_c.darker(150), 0.8))
        painter.setBrush(QBrush(tab_c))
        for r in self._cached_male_tabs: painter.drawRect(r)
        
        painter.setBrush(QBrush(cav_c))
        for r in self._cached_female_tabs: painter.drawRect(r)



        # ── Зовнішня уніфікована рамка ──────────────────────────────────────
        merge_src = getattr(self.app, '_merge_source_idx', -1)
        flatten_mode = getattr(self.app, '_flatten_mode', False)
        
        if merge_src >= 0 and self.placed_idx == merge_src:
            painter.setPen(QPen(QColor(255, 200, 0), 3.0))
        elif merge_src >= 0:
            painter.setPen(QPen(QColor(100, 220, 255), 2.5))
        elif flatten_mode and QStyle.State_MouseOver in option.state:
            painter.setPen(QPen(QColor(255, 100, 100), 3.0))
        elif self.isSelected():
            from PySide6.QtGui import QConicalGradient
            br = self.boundingRect()
            grad = QConicalGradient(br.center(), self.app._rainbow_phase)
            grad.setColorAt(0.0, QColor(255, 0, 0)); grad.setColorAt(0.2, QColor(255, 255, 0))
            grad.setColorAt(0.4, QColor(0, 255, 0)); grad.setColorAt(0.6, QColor(0, 255, 255))
            grad.setColorAt(0.8, QColor(0, 0, 255)); grad.setColorAt(1.0, QColor(255, 0, 255))
            painter.setPen(QPen(QBrush(grad), 3.0))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1.5))

        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._cached_union_path)

        # ── Hover ────────────────────────────────────────────────────────────
        if QStyle.State_MouseOver in option.state:
            painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
            painter.setPen(Qt.NoPen)
            painter.drawPath(self._cached_union_path)
