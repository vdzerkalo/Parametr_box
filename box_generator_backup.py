import sys
import os
import json
import numpy as np
import shutil
import zipfile
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFormLayout, QGroupBox, QMessageBox, QFileDialog,
                             QComboBox, QCheckBox, QScrollArea, QGridLayout,
                             QToolButton, QFrame, QStyle, QSizePolicy, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QInputDialog, QMenu,
                             QDoubleSpinBox, QSpinBox, QColorDialog,
                             QRadioButton, QButtonGroup, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox, QProgressDialog,
                             QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem, QStackedWidget)
from PySide6.QtGui import QPalette, QColor, QIcon, QAction, QPainter, QPixmap, QShortcut, QKeySequence, QPen, QBrush, QFont, QFontMetricsF
from PySide6.QtCore import Qt, QSettings, QFileInfo, QDir, QTimer, QSize, QRectF

import pyqtgraph.opengl as gl
import cadquery as cq

class CollapsibleBox(QWidget):
    def __init__(self, title="", icon=None, header_color="#444", content_color="#333", parent=None):
        super().__init__(parent)
        self.toggle_button = QToolButton(text=f" {title}")
        if icon:
            self.toggle_button.setIcon(icon)
            self.toggle_button.setIconSize(self.toggle_button.sizeHint() * 1.2)
        
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setStyleSheet(f"""
            QToolButton {{ 
                border: none; 
                font-weight: bold; 
                font-size: 13px; 
                text-align: left; 
                padding: 6px 10px; 
                background-color: {header_color};
                border-radius: 5px;
                color: #eee;
            }}
            QToolButton:hover {{
                background-color: #555;
            }}
            QToolButton:checked {{
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                background-color: {content_color};
            }}
        """)
        self.toggle_button.setArrowType(Qt.DownArrow)
        self.toggle_button.pressed.connect(self.on_pressed)
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.content_area = QFrame()
        self.content_area.setStyleSheet(f"QFrame {{ border: 1px solid #444; border-top: none; border-bottom-left-radius: 5px; border-bottom-right-radius: 5px; background-color: {content_color}; }}")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 8, 10, 8)
        self.content_layout.setSpacing(4)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 8)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

    def is_expanded(self):
        return self.toggle_button.isChecked()

    def set_expanded(self, expanded):
        # We need to set the state and update UI
        if self.toggle_button.isChecked() != expanded:
            self.toggle_button.setChecked(expanded)
            self.on_pressed()

    def on_pressed(self):
        # Notify app to save settings BEFORE we change UI
        is_expanding = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(Qt.DownArrow if is_expanding else Qt.RightArrow)
        self.content_area.setVisible(is_expanding)
        
        if is_expanding:
            self.toggle_button.setStyleSheet(self.toggle_button.styleSheet().replace("border-radius: 5px;", "border-radius: 5px; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;"))
        else:
            self.toggle_button.setStyleSheet(self.toggle_button.styleSheet().replace("border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;", "border-radius: 5px;"))
        
        # Look for the window to call save
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'save_auto_settings'):
                parent.save_auto_settings()
                break
            parent = parent.parent()



    def setContentLayout(self, layout):
        self.content_layout.addLayout(layout)

class ExportFolderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Налаштування експорту папки")
        layout = QVBoxLayout(self)
        
        self.rb_separate = QRadioButton("Кожен файл окремо")
        self.rb_combined = QRadioButton("Всі в один файл (Combine)")
        self.rb_separate.setChecked(True)
        layout.addWidget(self.rb_separate)
        layout.addWidget(self.rb_combined)
        
        layout.addSpacing(10)
        self.cb_zip = QCheckBox("Упакувати в ZIP архів")
        layout.addWidget(self.cb_zip)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addSpacing(20)
        layout.addWidget(btns)

    def get_settings(self):
        return {
            "combine": self.rb_combined.isChecked(),
            "zip": self.cb_zip.isChecked()
        }

class SnapDialog(QDialog):
    def __init__(self, unplaced_info, placed_items_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Пристикування об'єкта")
        self.unplaced_info = unplaced_info
        self.placed_items_info = placed_items_info
        layout = QFormLayout(self)
        
        self.unplaced_cb = QComboBox()
        for item in unplaced_info:
            self.unplaced_cb.addItem(item["name"])
            
        self.unplaced_side_cb = QComboBox()
        
        self.placed_cb = QComboBox()
        for item in placed_items_info:
            self.placed_cb.addItem(item["name"])
            
        self.placed_side_cb = QComboBox()
        
        self.placed_cb.currentIndexChanged.connect(self.update_available_sides)
        self.placed_side_cb.currentIndexChanged.connect(self.update_unplaced_sides)
        self.unplaced_cb.currentIndexChanged.connect(self.update_unplaced_sides)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btns = btns
        btns.accepted.connect(self.handle_accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

        # Initial updates
        self.update_available_sides(0)
        
        layout.addRow("До якого (вже розміщений):", self.placed_cb)
        layout.addRow("До якої сторони:", self.placed_side_cb)
        layout.addRow("Що стикуємо (новий):", self.unplaced_cb)
        layout.addRow("Якою стороною:", self.unplaced_side_cb)

    def update_unplaced_sides(self, *args):
        # Basis is the selected placed side
        p_idx = self.placed_cb.currentIndex()
        if p_idx < 0: return
        
        p_side_val = self.placed_side_cb.currentData() # index 0-3
        if p_side_val is None or p_side_val < 0:
            self.unplaced_side_cb.clear()
            self.validate_buttons()
            return

        # Complementary mode for snapping (0 -> 1, 1 -> 0)
        p_mode = int(self.placed_items_info[p_idx]["side_modes"][p_side_val])
        target_u_mode = 1 - p_mode
        
        # New object info
        u_idx = self.unplaced_cb.currentIndex()
        if u_idx < 0: return
        info = self.unplaced_info[u_idx]
        all_sides = ["Верх (+Y)", "Низ (-Y)", "Ліво (-X)", "Право (+X)"]
        modes = info.get("side_modes", [2, 2, 2, 2])
        
        self.unplaced_side_cb.clear()
        ideal_side = p_side_val ^ 1 # Opposite direction is natural
        ideal_cb_idx = -1
        
        for i in range(4):
            mode = int(modes[i])
            if mode == target_u_mode:
                self.unplaced_side_cb.addItem(all_sides[i], i)
                if i == ideal_side:
                    ideal_cb_idx = self.unplaced_side_cb.count() - 1
        
        # Auto-select ideal side if available
        if ideal_cb_idx >= 0:
            self.unplaced_side_cb.setCurrentIndex(ideal_cb_idx)
            
        if not hasattr(self, '_initial_unplaced_conn'):
            self.unplaced_side_cb.currentIndexChanged.connect(self.validate_buttons)
            self._initial_unplaced_conn = True
        self.validate_buttons()

    def handle_accept(self):
        u_side = self.get_selected_unplaced_side()
        p_side = self.get_selected_placed_side()
        
        if u_side is None or u_side < 0:
            QMessageBox.warning(self, "Помилка", "Будь ласка, оберіть сумісну сторону для нового об'єкта.")
            return
        if p_side is None or p_side < 0:
            QMessageBox.warning(self, "Помилка", "Ви обрали некоректну сторону розміщеного об'єкта.")
            return
            
        self.accept()

    def update_available_sides(self, index):
        self.placed_side_cb.clear()
        info = self.placed_items_info[index]
        all_sides = ["Верх (+Y)", "Низ (-Y)", "Ліво (-X)", "Право (+X)"]
        modes = info.get("side_modes", [2, 2, 2, 2])
        
        for side_idx in range(4):
            mode = int(modes[side_idx])
            if mode == 2:  # Skip inactive
                continue
                
            if side_idx not in info["available_sides"]:
                self.placed_side_cb.addItem(all_sides[side_idx] + " [Зайнято]", -1)
            else:
                self.placed_side_cb.addItem(all_sides[side_idx], side_idx)
        
        if not hasattr(self, '_initial_placed_conn'):
            self.placed_side_cb.currentIndexChanged.connect(self.validate_buttons)
            self._initial_placed_conn = True
            
        self.validate_buttons()
        # Trigger unplaced filter update
        self.update_unplaced_sides()

    def validate_buttons(self):
        if not hasattr(self, 'btns'): return
        u_side = self.get_selected_unplaced_side()
        p_side = self.get_selected_placed_side()
        # Valid if both have a non-negative data (meaning they are real active sides)
        is_valid = (u_side is not None and u_side >= 0) and (p_side is not None and p_side >= 0)
        self.btns.button(QDialogButtonBox.Ok).setEnabled(is_valid)

    def get_selected_unplaced_side(self):
        return self.unplaced_side_cb.currentData()

    def get_selected_placed_side(self):
        return self.placed_side_cb.currentData()

class BookmarksTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.main_app = None # To call refresh_bookmarks

    def dropEvent(self, event):
        item = self.currentItem()
        if not item:
            super().dropEvent(event)
            return
            
        source_path = item.data(0, Qt.UserRole)
        target_item = self.itemAt(event.position().toPoint())
        
        # If dropped on empty space, move to root
        if not target_item:
            target_dir = self.main_app.presets_dir
        else:
            target_path = target_item.data(0, Qt.UserRole)
            if os.path.isdir(target_path):
                target_dir = target_path
            else:
                target_dir = os.path.dirname(target_path)
        
        if source_path and target_dir and source_path != target_dir:
            try:
                dest = os.path.join(target_dir, os.path.basename(source_path))
                if os.path.exists(dest):
                    QMessageBox.warning(self, "Помилка", f"Об'єкт з назвою '{os.path.basename(source_path)}' вже існує в цій папці.")
                else:
                    shutil.move(source_path, dest)
                    if self.main_app:
                        self.main_app.refresh_bookmarks()
            except Exception as e:
                QMessageBox.critical(self, "Помилка переміщення", str(e))
        
        event.accept()


# ─── 2D Puzzle Board Item ─────────────────────────────────────────────────────

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
        return super().itemChange(change, value)

    # ---- RMB Context Menu / Rotate ----
    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.app.placed_list.setCurrentRow(self.placed_idx)
            menu = QMenu()
            
            rotate_act = QAction("Повернути (90°)", self.app)
            rotate_act.setIcon(self.app.style().standardIcon(QStyle.SP_BrowserReload))
            rotate_act.triggered.connect(self.rotate_item)
            menu.addAction(rotate_act)
            
            menu.addSeparator()
            copy_menu = menu.addMenu("Копія...")
            
            sides = [("Зверху", 0), ("Знизу", 1), ("Зліва", 2), ("Справа", 3)]
            for label, side_idx in sides:
                act = QAction(label, self.app)
                act.triggered.connect(lambda checked, s=side_idx: self.app.copy_to_side(self.placed_idx, s))
                copy_menu.addAction(act)
                
            menu.addSeparator()
            split_menu = menu.addMenu("Розбити фігуру...")
            
            split_h_act = QAction("По горизонталі", self.app)
            split_h_act.triggered.connect(lambda checked=False: self.app.split_item(self.placed_idx, 'x'))
            split_menu.addAction(split_h_act)
            
            split_v_act = QAction("По вертикалі", self.app)
            split_v_act.triggered.connect(lambda checked=False: self.app.split_item(self.placed_idx, 'y'))
            split_menu.addAction(split_v_act)
            
            menu.exec(ev.screenPos())
            ev.accept()
        else:
            self.app.placed_list.setCurrentRow(self.placed_idx)
            super().mousePressEvent(ev)

    def rotate_item(self):
        item = self.app.placed_items[self.placed_idx]
        item["rotation"] = (item.get("rotation", 0) + 90) % 360
        QTimer.singleShot(0, lambda: (self.app.update_puzzle_view(), self.app.generate_box()))

    # ---- snap & refresh on LMB release (deferred so scene isn't cleared mid-event) ----
    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.LeftButton:
            idx = self.placed_idx
            app = self.app
            # Defer: scene.clear() inside an item's own event causes Qt issues
            QTimer.singleShot(0, lambda: (app.try_auto_snap(idx), app.update_puzzle_view()))

    # ---- full XY cross-section paint ----
    def paint(self, painter, option, widget=None):
        item = self.app.placed_items[self.placed_idx]
        data = item["data"]
        L, W, wt = self._L, self._W, self._wt

        c      = self._color
        wall_c = c.darker(130)
        cav_c  = c.darker(175)  # hollow cavity
        tab_c  = c.lighter(115) # tab protrusions

        painter.setRenderHint(QPainter.Antialiasing)

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

        # ── Tabs on each edge ────────────────────────────────────────────────
        def draw_tabs(edge, count, male):
            """Draw tab protrusions (male) or slots (female) on an edge.
            male=True  → rectangle protrudes outside the outer box boundary
            male=False → slot cut into the wall from the inner edge outward
            """
            if count <= 0:
                return
            if edge in ('top', 'bottom'):
                seg_len = L / (2 * count + 1)
                tab_w   = seg_len
                tab_h   = wt
                for k in range(count):
                    ox = -L/2 + seg_len * (2*k + 1)
                    if edge == 'top':
                        # male: protrudes ABOVE the box (−W/2 − tab_h)
                        # female: slot INTO the wall (−W/2 .. −W/2 + tab_h) = cavity color
                        r = QRectF(ox, -W/2 - tab_h, tab_w, tab_h) if male \
                            else QRectF(ox, -W/2, tab_w, tab_h)
                    else:  # bottom
                        r = QRectF(ox, W/2, tab_w, tab_h) if male \
                            else QRectF(ox, W/2 - tab_h, tab_w, tab_h)
                    painter.setBrush(QBrush(tab_c if male else cav_c))
                    painter.setPen(QPen(wall_c.darker(150), 0.8))
                    painter.drawRect(r)
            else:  # left / right
                seg_len = W / (2 * count + 1)
                tab_w   = seg_len
                tab_h   = wt
                for k in range(count):
                    oy = -W/2 + seg_len * (2*k + 1)
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
        sel_color = QColor(255, 220, 50) if self.isSelected() else QColor(255, 255, 255, 180)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(sel_color, 1.5))
        painter.drawRect(outer)

        # ── Label (always horizontal) ────────────────────────────────────────
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
        from PySide6.QtWidgets import QStyle
        if QStyle.State_MouseOver in option.state:
            hover_c = QColor(255, 255, 255, 40)
            painter.setBrush(QBrush(hover_c))
            painter.setPen(Qt.NoPen)
            painter.drawRect(outer)



class BoxGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор Коробок Вазового Режиму (Автономний)")
        self.resize(1300, 900)
        
        self.current_shape = None
        self.is_single_bed = False
        self.current_lid_offset_x = 0.0
        self.assembly_decorations = []  # To track labels and axes
        self.placed_items = []
        self.unplaced_items = []
        self.dimension_items = []
        
        # Color palette for assembly (translucent)
        self.assembly_palette = [
            (0.1, 0.7, 1.0, 0.4), # Blue (default)
            (1.0, 0.4, 0.4, 0.4), # Red
            (0.4, 1.0, 0.4, 0.4), # Green
            (1.0, 0.8, 0.2, 0.4), # Gold
            (0.8, 0.4, 1.0, 0.4), # Purple
            (0.2, 1.0, 0.8, 0.4), # Teal
            (1.0, 0.5, 0.0, 0.4), # Orange
            (0.7, 0.7, 0.7, 0.4)  # Grey
        ]
        
        # Timer for on-the-fly generation
        self.regen_timer = QTimer()
        self.regen_timer.setSingleShot(True)
        self.regen_timer.timeout.connect(self.generate_box)
        
        # Undo/Redo Stacks
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 50
        self._suppress_history = False
        self.last_state = {}
        self.assem_submode = 'puzzle' # puzzle or view
        
        # Central widget and Scroll Area for Left Panel
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout_ui = QHBoxLayout(central_widget)
        
        # Helper for SpinBoxes
        def create_dsb(val, min_v, max_v, step, decimals=2):
            sb = QDoubleSpinBox()
            sb.setRange(min_v, max_v)
            sb.setSingleStep(step)
            sb.setDecimals(decimals)
            sb.setValue(val)
            return sb

        def create_sb(val, min_v, max_v, step=1):
            sb = QSpinBox()
            sb.setRange(min_v, max_v)
            sb.setSingleStep(step)
            sb.setValue(val)
            return sb
        
        # Left Panel for Parameters (Scrollable)
        self.settings_pos = "left"
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedWidth(600)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #2d2d2d; }")

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        
        # Top utility bar (Two rows for better clarity)
        top_utility_layout = QVBoxLayout()
        top_utility_layout.setSpacing(6)
        
        row1 = QHBoxLayout()
        self.side_toggle_btn = QPushButton(" Змінити сторону панелі")
        self.side_toggle_btn.setIcon(self.style().standardIcon(QStyle.SP_CommandLink))
        self.side_toggle_btn.clicked.connect(self.toggle_panel_side)
        
        self.open_dir_btn = QPushButton(" Відкрити папку пресетів")
        self.open_dir_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.open_dir_btn.clicked.connect(self.open_presets_folder)
        row1.addWidget(self.side_toggle_btn)
        row1.addWidget(self.open_dir_btn)
        
        row2 = QHBoxLayout()
        self.export_zip_btn = QPushButton(" Експортувати бібліотеку (ZIP)")
        self.export_zip_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_zip_btn.clicked.connect(self.export_library_zip)
        
        self.import_zip_btn = QPushButton(" Імпортувати бібліотеку (ZIP)")
        self.import_zip_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.import_zip_btn.clicked.connect(self.import_library_zip)
        row2.addWidget(self.export_zip_btn)
        row2.addWidget(self.import_zip_btn)
        
        top_utility_layout.addLayout(row1)
        top_utility_layout.addLayout(row2)
        left_layout.addLayout(top_utility_layout)

        # Mode selector
        mode_layout = QHBoxLayout()
        self.mode_gen_btn = QRadioButton("Генерація")
        self.mode_assem_btn = QRadioButton("Збирання")
        self.mode_gen_btn.setChecked(True)
        mode_layout.addWidget(QLabel("Режим:"))
        mode_layout.addWidget(self.mode_gen_btn)
        mode_layout.addWidget(self.mode_assem_btn)
        mode_layout.addStretch()
        self.mode_gen_btn.toggled.connect(self.switch_mode)
        left_layout.addLayout(mode_layout)
        
        # Create presets folder if not exists
        self.presets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)

        self.preset_box = CollapsibleBox("Пресети (Закладки)", self.style().standardIcon(QStyle.SP_DirIcon), "#3f3f3f", "#333")
        preset_layout = QVBoxLayout()
        preset_layout.setSpacing(4)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(" Пошук закладок за назвою...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_bookmarks)
        search_icon = QLabel()
        search_icon.setPixmap(self.style().standardIcon(QStyle.SP_FileDialogContentsView).pixmap(16, 16))
        search_layout.addWidget(search_icon)
        search_layout.addWidget(self.search_input)
        preset_layout.addLayout(search_layout)

        # Bookmarks Tree
        self.bookmarks_tree = BookmarksTreeWidget()
        self.bookmarks_tree.main_app = self
        self.bookmarks_tree.setHeaderHidden(True)
        self.bookmarks_tree.setFixedHeight(200)
        self.bookmarks_tree.itemClicked.connect(self.on_bookmark_clicked)
        self.bookmarks_tree.currentItemChanged.connect(lambda curr, prev: self.on_bookmark_clicked(curr, 0) if curr else None)
        self.bookmarks_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmarks_tree.customContextMenuRequested.connect(self.show_bookmarks_context_menu)
        self.bookmarks_tree.setStyleSheet("QTreeWidget { background-color: #2a2a2a; border: 1px solid #444; border-radius: 3px; }")
        preset_layout.addWidget(self.bookmarks_tree)
        
        btns_row = QHBoxLayout()
        self.add_bookmark_btn = QPushButton(" Зберегти")
        self.add_bookmark_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.add_bookmark_btn.clicked.connect(self.save_as_bookmark)
        
        self.new_folder_btn = QPushButton(" Папка")
        self.new_folder_btn.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self.new_folder_btn.clicked.connect(self.create_preset_folder)
        
        self.overwrite_btn = QPushButton(" Замінити")
        self.overwrite_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.overwrite_btn.clicked.connect(self.overwrite_selected_bookmark)
        
        btns_row.addWidget(self.add_bookmark_btn)
        btns_row.addWidget(self.new_folder_btn)
        btns_row.addWidget(self.overwrite_btn)
        preset_layout.addLayout(btns_row)
        
        self.preset_box.setContentLayout(preset_layout)
        left_layout.addWidget(self.preset_box)

        # Секція: Розміри
        self.dim_box = CollapsibleBox("Розміри коробки (X, Y, Z)", self.style().standardIcon(QStyle.SP_FileDialogInfoView), "#4a4a4a", "#3a3a3a")
        dim_layout = QHBoxLayout()
        dim_layout.setSpacing(10)
        self.len_input = create_dsb(100.0, 1.0, 2000.0, 1.0)
        self.wid_input = create_dsb(100.0, 1.0, 2000.0, 1.0)
        self.hei_input = create_dsb(50.0, 1.0, 2000.0, 1.0)
        
        for label, widget in [("X:", self.len_input), ("Y:", self.wid_input), ("Z:", self.hei_input)]:
            lbl = QLabel(label)
            lbl.setFixedWidth(20)
            dim_layout.addWidget(lbl)
            dim_layout.addWidget(widget)
        dim_layout.addStretch()
        self.dim_box.setContentLayout(dim_layout)
        left_layout.addWidget(self.dim_box)
        
        # Секція: З'єднання
        self.tab_box = CollapsibleBox("Геометрія з'єднання", self.style().standardIcon(QStyle.SP_FileDialogContentsView), "#3f3f3f", "#333")
        tab_grid = QGridLayout()
        tab_grid.setSpacing(10)
        
        self.tab_wbase_input = create_dsb(20.0, 1.0, 500.0, 1.0)
        self.tab_wtip_input = create_dsb(30.0, 1.0, 500.0, 1.0)
        self.tab_depth_input = create_dsb(10.0, 1.0, 200.0, 1.0)
        self.tab_clearance_input = create_dsb(0.3, 0.0, 5.0, 0.05)
        self.tab_fillet_input = create_dsb(2.0, 0.0, 50.0, 0.5)

        tab_fields = [
            ("База:", self.tab_wbase_input),
            ("Кінчик:", self.tab_wtip_input),
            ("Глибина:", self.tab_depth_input),
            ("Зазор:", self.tab_clearance_input),
            ("Радіус:", self.tab_fillet_input)
        ]

        for i, (label_text, widget) in enumerate(tab_fields):
            row = i // 3
            col = (i % 3) * 2
            lbl = QLabel(label_text)
            lbl.setFixedWidth(65)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tab_grid.addWidget(lbl, row, col)
            tab_grid.addWidget(widget, row, col + 1)
        
        tab_grid.setColumnStretch(6, 1)
        
        self.tab_box.setContentLayout(tab_grid)
        left_layout.addWidget(self.tab_box)
        
        # Секція: Сторони
        self.sides_box = CollapsibleBox("Конфігурація сторін", self.style().standardIcon(QStyle.SP_FileDialogListView), "#4a4a4a", "#3a3a3a")
        self.sides_grid = QGridLayout()
        self.sides_grid.setSpacing(8)
        self.side_top = QComboBox(); self.side_bottom = QComboBox()
        self.side_left = QComboBox(); self.side_right = QComboBox()
        self.side_top_count = create_sb(1, 0, 50)
        self.side_bottom_count = create_sb(1, 0, 50)
        self.side_left_count = create_sb(1, 0, 50)
        self.side_right_count = create_sb(1, 0, 50)
        
        options = ["Шип", "Паз", "Пряма"]
        for i, (label, cb, count_in) in enumerate([
            ("Верх (+Y)", self.side_top, self.side_top_count),
            ("Низ (-Y)", self.side_bottom, self.side_bottom_count),
            ("Ліво (-X)", self.side_left, self.side_left_count),
            ("Право (+X)", self.side_right, self.side_right_count)
        ]):
            cb.addItems(options)
            row = i // 2
            col = (i % 2) * 4
            lbl = QLabel(label)
            lbl.setObjectName("side_label")
            lbl.setFixedWidth(70)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sides_grid.addWidget(lbl, row, col)
            self.sides_grid.addWidget(cb, row, col + 1)
            
            k_lbl = QLabel(" К:")
            k_lbl.setFixedWidth(20)
            k_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sides_grid.addWidget(k_lbl, row, col + 2)
            self.sides_grid.addWidget(count_in, row, col + 3)
            count_in.setFixedWidth(45)
            cb.setMinimumWidth(80)
        
        self.side_top.setCurrentIndex(0); self.side_bottom.setCurrentIndex(1)
        self.side_left.setCurrentIndex(1); self.side_right.setCurrentIndex(0)
        self.sides_box.setContentLayout(self.sides_grid)
        left_layout.addWidget(self.sides_box)

        # Секція: Стіл
        self.bed_box = CollapsibleBox("Робочий стіл принтера", self.style().standardIcon(QStyle.SP_DesktopIcon), "#3f3f3f", "#333")
        bed_main_layout = QVBoxLayout()
        bed_inputs_layout = QHBoxLayout()
        bed_inputs_layout.setSpacing(10)
        self.bed_x_input = create_dsb(256.0, 50.0, 2000.0, 10.0)
        self.bed_y_input = create_dsb(256.0, 50.0, 2000.0, 10.0)
        self.bed_status_label = QLabel("Розміщення: Авто")
        self.bed_status_label.setStyleSheet("color: #00ff7f; font-weight: bold; font-size: 10px;")
        
        lbl_x = QLabel("X (мм):"); lbl_x.setFixedWidth(50); lbl_x.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_y = QLabel("Y (мм):"); lbl_y.setFixedWidth(50); lbl_y.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        bed_inputs_layout.addWidget(lbl_x)
        bed_inputs_layout.addWidget(self.bed_x_input)
        bed_inputs_layout.addWidget(lbl_y)
        bed_inputs_layout.addWidget(self.bed_y_input)
        bed_inputs_layout.addStretch()
        
        bed_main_layout.addLayout(bed_inputs_layout)
        bed_main_layout.addWidget(self.bed_status_label)
        self.bed_box.setContentLayout(bed_main_layout)
        left_layout.addWidget(self.bed_box)

        # Секція: Кришка
        self.lid_box_coll = CollapsibleBox("Параметри кришки", self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "#4a4a4a", "#3a3a3a")
        lid_layout = QFormLayout()
        self.generate_lid_cb = QCheckBox("Генерувати кришку")
        self.generate_lid_cb.setChecked(True)
        self.lid_tolerance_input = create_dsb(0.1, 0.0, 5.0, 0.05)
        self.lid_extrusion_input = create_dsb(0.4, 0.1, 2.0, 0.05)
        self.lid_height_input = create_dsb(15.0, 1.0, 200.0, 1.0)
        
        lid_layout.addRow(self.generate_lid_cb)
        lid_layout.addRow("Ширина ліній:", self.lid_extrusion_input)
        lid_layout.addRow("Зазор вставки:", self.lid_tolerance_input)
        lid_layout.addRow("Висота кришки:", self.lid_height_input)
        self.lid_box_coll.setContentLayout(lid_layout)
        left_layout.addWidget(self.lid_box_coll)
        # Поки блокуємо на рівні коду
        self.lid_box_coll.hide()
        self.generate_lid_cb.setChecked(False)

        # Секція: Збирання
        self.assembly_box = CollapsibleBox("Сцена Збирання", self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "#4a4a4a", "#3a3a3a")
        assembly_layout = QVBoxLayout()
        
        # Sub-mode selection
        submode_layout = QHBoxLayout()
        self.puzzle_mode_btn = QPushButton(" Пазл (2D)")
        self.view_mode_btn = QPushButton(" Камера (3D)")
        self.puzzle_mode_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.view_mode_btn.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.puzzle_mode_btn.setCheckable(True)
        self.view_mode_btn.setCheckable(True)
        self.puzzle_mode_btn.setChecked(True)
        
        self.submode_group = QButtonGroup(self)
        self.submode_group.addButton(self.puzzle_mode_btn)
        self.submode_group.addButton(self.view_mode_btn)
        self.submode_group.buttonClicked.connect(self.on_assem_submode_changed)
        
        submode_layout.addWidget(self.puzzle_mode_btn)
        submode_layout.addWidget(self.view_mode_btn)
        assembly_layout.addLayout(submode_layout)

        spacer = QFrame()
        spacer.setFrameShape(QFrame.HLine)
        spacer.setFrameShadow(QFrame.Sunken)
        assembly_layout.addWidget(spacer)
        
        self.unplaced_list = QListWidget()
        self.unplaced_list.setFixedHeight(120)
        assembly_layout.addWidget(QLabel("Нерозміщені об'єкти:"))
        assembly_layout.addWidget(self.unplaced_list)
        
        self.place_first_btn = QPushButton(" Розмістити перший (в центр)")
        self.place_first_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.place_first_btn.clicked.connect(self.place_first_object)
        
        self.clear_assem_btn = QPushButton(" Очистити стіл")
        self.clear_assem_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        self.clear_assem_btn.clicked.connect(self.clear_assembly)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.place_first_btn)
        btn_layout.addWidget(self.clear_assem_btn)
        assembly_layout.addLayout(btn_layout)
        
        self.snap_btn = QPushButton(" Пристикувати обраний...")
        self.snap_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.snap_btn.clicked.connect(self.open_snap_dialog)
        assembly_layout.addWidget(self.snap_btn)

        self.add_n_btn = QPushButton(" Додати N копій...")
        self.add_n_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.add_n_btn.clicked.connect(self.add_n_copies_dialog)
        assembly_layout.addWidget(self.add_n_btn)

        self.remove_btn = QPushButton(" Прибрати зі збірки")
        self.remove_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.remove_btn.clicked.connect(self.remove_from_assembly)
        assembly_layout.addWidget(self.remove_btn)
        
        self.placed_list = QListWidget()
        self.placed_list.setFixedHeight(120)
        assembly_layout.addWidget(QLabel("Об'єкти в збірці:"))
        self.placed_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.placed_list.customContextMenuRequested.connect(self.show_placed_context_menu)
        self.placed_list.currentItemChanged.connect(self.on_placed_item_changed)
        self.placed_list.currentRowChanged.connect(self.update_assembly_ui_state)
        self.unplaced_list.currentRowChanged.connect(self.update_assembly_ui_state)
        self.unplaced_list.itemSelectionChanged.connect(self.update_assembly_ui_state)
        self.placed_list.itemSelectionChanged.connect(self.update_assembly_ui_state)
        assembly_layout.addWidget(self.placed_list)
        
        # Live Height Controller
        h_row = QHBoxLayout()
        self.h_label = QLabel("Висота об'єкта:")
        h_row.addWidget(self.h_label)
        self.live_height_sb = create_dsb(50, 1, 1000, 1)
        self.live_height_sb.valueChanged.connect(self.on_live_height_changed)
        h_row.addWidget(self.live_height_sb)
        assembly_layout.addLayout(h_row)

        # Rotation controls
        rot_row = QHBoxLayout()
        rot_row.addWidget(QLabel("Поворот:"))
        for angle in [0, 90, 180, 270]:
            btn = QPushButton(f"{angle}°")
            btn.setFixedWidth(50)
            btn.clicked.connect(lambda checked, a=angle: self.rotate_selected(a))
            rot_row.addWidget(btn)
        assembly_layout.addLayout(rot_row)
        
        # Assembly persistence row
        assem_persist_row = QHBoxLayout()
        self.save_assem_btn = QPushButton(" Зберегти збірку")
        self.save_assem_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.save_assem_btn.clicked.connect(self.save_assembly)
        self.load_assem_btn = QPushButton(" Завантажити збірку")
        self.load_assem_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.load_assem_btn.clicked.connect(self.load_assembly)
        assem_persist_row.addWidget(self.save_assem_btn)
        assem_persist_row.addWidget(self.load_assem_btn)
        assembly_layout.addLayout(assem_persist_row)
        
        self.assembly_box.setContentLayout(assembly_layout)
        left_layout.addWidget(self.assembly_box)
        self.assembly_box.setVisible(False)
        
        self.update_assembly_ui_state()

        # Export
        export_group = QWidget()
        export_layout = QHBoxLayout(export_group)
        export_layout.setContentsMargins(0, 5, 0, 0)
        
        self.export_step_btn = QPushButton(" STEP")
        self.export_step_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_step_btn.clicked.connect(lambda: self.export_file("step"))
        
        self.export_stl_btn = QPushButton(" STL")
        self.export_stl_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_stl_btn.clicked.connect(lambda: self.export_file("stl"))
        
        export_layout.addWidget(self.export_step_btn)
        export_layout.addWidget(self.export_stl_btn)
        left_layout.addWidget(export_group)

        self.show_dims_cb = QCheckBox(" Показати розміри стрілками на моделі")
        self.show_dims_cb.setStyleSheet("QCheckBox { color: #aaa; margin: 5px; }")
        self.show_dims_cb.stateChanged.connect(self.update_view)
        left_layout.addWidget(self.show_dims_cb)
        
        left_layout.addStretch()
        
        # Consistent alignment for all labels in forms
        self.align_labels()

        self.scroll_area.setWidget(left_panel)
        
        # Right Panel for 3D View
        self.view = gl.GLViewWidget()
        self.view.setMouseTracking(True)
        self.view.opts['distance'] = 300
        
        self.grid = gl.GLGridItem()
        self.grid.translate(0, 0, -0.1)
        self.view.addItem(self.grid)
        
        self.grid_lid = gl.GLGridItem()
        self.grid_lid.translate(0, 0, -0.1)
        self.view.addItem(self.grid_lid)
        
        self.update_grid()
        
        axis = gl.GLAxisItem()
        axis.scale(50, 50, 50)
        self.view.addItem(axis)
        
        self.mesh_item = gl.GLMeshItem(color=(0.1, 0.7, 1.0, 0.4), smooth=True, drawEdges=False, computeNormals=False)
        self.mesh_item.setGLOptions('translucent')
        self.view.addItem(self.mesh_item)
        
        self.edge_item = gl.GLLinePlotItem(color=(1.0, 1.0, 1.0, 0.8), width=1.5, mode='lines', antialias=True)
        self.edge_item.setGLOptions('translucent')
        self.view.addItem(self.edge_item)

        # === Right Panel: 3D View + 2D Canvas + Toolbox ===
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Stack: page 0 = 3D view, page 1 = 2D puzzle canvas
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.view)           # index 0

        self.puzzle_scene  = QGraphicsScene()
        self.puzzle_canvas = QGraphicsView(self.puzzle_scene)
        self.puzzle_canvas.setRenderHint(QPainter.Antialiasing)
        self.puzzle_canvas.setBackgroundBrush(QBrush(QColor(32, 32, 32)))
        self.puzzle_canvas.setDragMode(QGraphicsView.RubberBandDrag)
        self.puzzle_canvas.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.puzzle_canvas.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        
        # Grid Drawing override
        def draw_grid(painter, rect):
            scale = 1.5 # PuzzleBoxItem.SCALE
            left = int(rect.left())
            right = int(rect.right())
            top = int(rect.top())
            bottom = int(rect.bottom())
            
            # Subtle 10mm grid
            pen10 = QPen(QColor(50, 50, 50), 0.5)
            # 100mm grid
            pen100 = QPen(QColor(70, 70, 70), 0.8)
            
            # Vertical lines
            for x in range((left // int(10*scale)) * int(10*scale), right, int(10*scale)):
                painter.setPen(pen100 if x % int(100*scale) == 0 else pen10)
                painter.drawLine(x, top, x, bottom)
            # Horizontal lines
            for y in range((top // int(10*scale)) * int(10*scale), bottom, int(10*scale)):
                painter.setPen(pen100 if y % int(100*scale) == 0 else pen10)
                painter.drawLine(left, y, right, y)
        
        self.puzzle_canvas.drawBackground = draw_grid
        
        # Enable wheel zoom
        self.puzzle_canvas.wheelEvent = self._puzzle_wheel_zoom
        self.view_stack.addWidget(self.puzzle_canvas)  # index 1

        right_layout.addWidget(self.view_stack, stretch=1)

        # Toolbox panel (visible only in assembly mode)
        self.toolbox_frame = QFrame()
        self.toolbox_frame.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-top: 2px solid #555;
            }
        """)
        toolbox_layout = QVBoxLayout(self.toolbox_frame)
        toolbox_layout.setContentsMargins(8, 6, 8, 6)
        toolbox_layout.setSpacing(4)

        toolbox_header = QHBoxLayout()
        toolbox_icon = QLabel()
        toolbox_icon.setPixmap(self.style().standardIcon(QStyle.SP_FileDialogContentsView).pixmap(16, 16))
        toolbox_header.addWidget(toolbox_icon)
        toolbox_header.addWidget(QLabel("Панель інструментів (коробки з обраної папки):"))
        toolbox_header.addStretch()
        self.toolbox_add_btn = QPushButton(" Додати на стіл ↑")
        self.toolbox_add_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        self.toolbox_add_btn.clicked.connect(self.add_tool_to_assembly)
        self.toolbox_add_btn.setStyleSheet("QPushButton { background: #4a7; color: white; padding: 4px 12px; border-radius: 3px; font-weight: bold; }")
        toolbox_header.addWidget(self.toolbox_add_btn)
        toolbox_layout.addLayout(toolbox_header)

        self.toolbox_list = QListWidget()
        self.toolbox_list.setFlow(QListWidget.LeftToRight)
        self.toolbox_list.setWrapping(True)
        self.toolbox_list.setFixedHeight(120)  # Increased for icons
        self.toolbox_list.setIconSize(QSize(80, 80))
        self.toolbox_list.setSpacing(10)
        self.toolbox_list.setStyleSheet("""
            QListWidget {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 4px;
                margin: 2px;
                background: #3a3a3a;
                border: 1px solid #555;
                border-radius: 4px;
                color: #ddd;
            }
            QListWidget::item:selected {
                background: #4a7;
                border-color: #6c9;
                color: white;
            }
        """)
        toolbox_layout.addWidget(self.toolbox_list)
        self.toolbox_frame.setVisible(False)  # Hidden by default
        right_layout.addWidget(self.toolbox_frame)

        # Assembly interaction state
        self.selected_placed_idx = -1
        self._dragging = False
        self._drag_start_pos = None

        # Apply position
        self.apply_ui_layout()
        
        # Connection to mark dirty when changed
        self.connect_dirty_signals()
        
        # Load last settings
        self.load_auto_settings()
        
        # Init bookmarks
        self.refresh_bookmarks()
        
        # Generate initial geometry
        self.generate_box()
        self.last_state = self.get_preset_dict()
        
        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self.redo)

    def switch_mode(self):
        is_assembly = self.mode_assem_btn.isChecked()
        self.preset_box.toggle_button.setText(" Папки (Збирання)" if is_assembly else " Пресети (Закладки)")
        self.dim_box.setVisible(not is_assembly)
        self.tab_box.setVisible(not is_assembly)
        self.sides_box.setVisible(not is_assembly)
        self.bed_box.setVisible(not is_assembly)
        self.assembly_box.setVisible(is_assembly)
        self.toolbox_frame.setVisible(is_assembly)
        if is_assembly:
            self.populate_toolbox()
            self.install_assembly_mouse_handlers()
            self.puzzle_mode_btn.setChecked(True)
            self.on_assem_submode_changed(self.puzzle_mode_btn)
            self.statusBar().showMessage("Режим конструктора: перетягуйте коробки мишкою", 5000)
        else:
            self.uninstall_assembly_mouse_handlers()
            self.statusBar().clearMessage()
        self.generate_box()

    def toggle_panel_side(self):
        self.settings_pos = "right" if self.settings_pos == "left" else "left"
        self.apply_ui_layout()
        self.save_auto_settings()

    def apply_ui_layout(self):
        if self.settings_pos == "left":
            self.main_layout_ui.insertWidget(0, self.scroll_area)
            self.main_layout_ui.insertWidget(1, self.right_panel)
        else:
            self.main_layout_ui.insertWidget(0, self.right_panel)
            self.main_layout_ui.insertWidget(1, self.scroll_area)

    def align_labels(self):
        target_width = 120
        # Alignment for FormLayouts (Lid section, etc)
        for layout in self.findChildren(QFormLayout):
            layout.setLabelAlignment(Qt.AlignRight)
            layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            layout.setSpacing(5)
            for i in range(layout.rowCount()):
                item = layout.itemAt(i, QFormLayout.LabelRole)
                if item:
                    w = item.widget()
                    if isinstance(w, QLabel):
                        w.setFixedWidth(target_width)
                        w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Spacing for Grid Layouts
        self.sides_grid.setHorizontalSpacing(10)
        self.sides_grid.setVerticalSpacing(8)

    def connect_dirty_signals(self):
        # Numeric inputs
        for widget in [self.len_input, self.wid_input, self.hei_input,
                       self.tab_wbase_input, self.tab_wtip_input, self.tab_depth_input,
                       self.tab_clearance_input, self.tab_fillet_input,
                       self.lid_tolerance_input, self.lid_extrusion_input, self.lid_height_input,
                       self.bed_x_input, self.bed_y_input,
                       self.side_top_count, self.side_bottom_count, self.side_left_count, self.side_right_count]:
            widget.valueChanged.connect(self.mark_dirty)
            
        for cb in [self.side_top, self.side_bottom, self.side_left, self.side_right]:
            cb.currentIndexChanged.connect(self.mark_dirty)
            
        self.generate_lid_cb.stateChanged.connect(self.mark_dirty)

    def mark_dirty(self):
        # Save state for undo if this is the start of a change sequence
        if not self._suppress_history and not self.regen_timer.isActive():
            self.undo_stack.append(self.last_state)
            self.redo_stack.clear()
            if len(self.undo_stack) > self.max_history:
                self.undo_stack.pop(0)

        # Auto-save settings on change
        self.save_auto_settings()
        
        # Trigger on-the-fly regeneration with delay
        self.regen_timer.start(500)
        
        # Якщо змінилися розміри столу - можна відразу оновлювати сітку
        if self.sender() in [self.bed_x_input, self.bed_y_input]:
            self.update_grid()

    def save_auto_settings(self):
        settings = QSettings("KasNew", "BoxGenerator")
        data = self.get_preset_dict()
        for key, val in data.items():
            settings.setValue(key, val)

    def load_auto_settings(self):
        settings = QSettings("KasNew", "BoxGenerator")
        if not settings.allKeys(): return
        
        data = {}
        for key in settings.allKeys():
            data[key] = settings.value(key)
        self.set_preset_dict(data)

    def update_grid(self):
        try:
            is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
            
            if is_assembly:
                self.grid.show()
                self.update_adaptive_grid()
                self.grid_lid.hide()
                return

            bx = self.bed_x_input.value()
            by = self.bed_y_input.value()
            L = self.len_input.value()
            t_d = self.tab_depth_input.value()
            
            # Configure first grid (Box) - centered at (0,0)
            self.grid.setSize(x=bx, y=by, z=0)
            self.grid.setSpacing(x=10, y=10, z=0)
            
            # Configure second grid (Lid)
            if self.generate_lid_cb.isChecked() and not self.is_single_bed:
                self.grid_lid.show()
                self.grid_lid.setSize(x=bx, y=by, z=0)
                self.grid_lid.setSpacing(x=10, y=10, z=0)
                
                # Align second grid with lid position
                self.grid_lid.resetTransform()
                self.grid_lid.translate(self.current_lid_offset_x, 0, -0.1)
            else:
                self.grid_lid.hide()
                
        except ValueError:
            pass

    def get_preset_dict(self):
        return {
            "length": self.len_input.value(),
            "width": self.wid_input.value(),
            "height": self.hei_input.value(),
            "tab_base": self.tab_wbase_input.value(),
            "tab_tip": self.tab_wtip_input.value(),
            "tab_depth": self.tab_depth_input.value(),
            "clearance": self.tab_clearance_input.value(),
            "fillet": self.tab_fillet_input.value(),
            "side_top": self.side_top.currentIndex(),
            "side_bottom": self.side_bottom.currentIndex(),
            "side_left": self.side_left.currentIndex(),
            "side_right": self.side_right.currentIndex(),
            "side_top_count": self.side_top_count.value(),
            "side_bottom_count": self.side_bottom_count.value(),
            "side_left_count": self.side_left_count.value(),
            "side_right_count": self.side_right_count.value(),
            "gen_lid": self.generate_lid_cb.isChecked(),
            "lid_tol": self.lid_tolerance_input.value(),
            "lid_ext": self.lid_extrusion_input.value(),
            "lid_h": self.lid_height_input.value(),
            "bed_x": self.bed_x_input.value(),
            "bed_y": self.bed_y_input.value(),
            "exp_preset": self.preset_box.is_expanded(),
            "exp_dim": self.dim_box.is_expanded(),
            "exp_tab": self.tab_box.is_expanded(),
            "exp_sides": self.sides_box.is_expanded(),
            "exp_bed": self.bed_box.is_expanded(),
            "exp_lid": self.lid_box_coll.is_expanded(),
            "settings_pos": self.settings_pos
        }

    def set_preset_dict(self, data):
        # We use valueChanged.disconnect to avoid triggering regeneration for every field during batch load
        # However, regen_timer Debounce handles this well enough.
        def safe_set(widget, key, v_type=float):
            if key in data:
                try:
                    widget.setValue(v_type(data[key]))
                except: pass

        safe_set(self.len_input, "length")
        safe_set(self.wid_input, "width")
        safe_set(self.hei_input, "height")
        safe_set(self.tab_wbase_input, "tab_base")
        safe_set(self.tab_wtip_input, "tab_tip")
        safe_set(self.tab_depth_input, "tab_depth")
        safe_set(self.tab_clearance_input, "clearance")
        safe_set(self.tab_fillet_input, "fillet")
        
        if "side_top" in data: self.side_top.setCurrentIndex(int(data["side_top"]))
        if "side_bottom" in data: self.side_bottom.setCurrentIndex(int(data["side_bottom"]))
        if "side_left" in data: self.side_left.setCurrentIndex(int(data["side_left"]))
        if "side_right" in data: self.side_right.setCurrentIndex(int(data["side_right"]))
        
        safe_set(self.side_top_count, "side_top_count", int)
        safe_set(self.side_bottom_count, "side_bottom_count", int)
        safe_set(self.side_left_count, "side_left_count", int)
        safe_set(self.side_right_count, "side_right_count", int)

        if "gen_lid" in data:
            val = data["gen_lid"]
            if isinstance(val, str):
                bool_val = val.lower() == 'true'
            else:
                bool_val = bool(val)
            self.generate_lid_cb.setChecked(bool_val)

        if "lid_tol" in data: safe_set(self.lid_tolerance_input, "lid_tol")
        if "lid_ext" in data: safe_set(self.lid_extrusion_input, "lid_ext")
        if "lid_h" in data: safe_set(self.lid_height_input, "lid_h")
        if "bed_x" in data: safe_set(self.bed_x_input, "bed_x")
        if "bed_y" in data: safe_set(self.bed_y_input, "bed_y")
        
        # UI State (Expansion) - converting strings from QSettings to bool
        def to_bool(v):
            if isinstance(v, bool): return v
            return str(v).lower() == 'true'

        if "exp_preset" in data: self.preset_box.set_expanded(to_bool(data["exp_preset"]))
        if "exp_dim" in data: self.dim_box.set_expanded(to_bool(data["exp_dim"]))
        if "exp_tab" in data: self.tab_box.set_expanded(to_bool(data["exp_tab"]))
        if "exp_sides" in data: self.sides_box.set_expanded(to_bool(data["exp_sides"]))
        if "exp_bed" in data: self.bed_box.set_expanded(to_bool(data["exp_bed"]))
        if "exp_lid" in data: self.lid_box_coll.set_expanded(to_bool(data["exp_lid"]))
        
        if "settings_pos" in data:
            self.settings_pos = str(data["settings_pos"])
            self.apply_ui_layout()
        
        self.update_grid()

    def refresh_bookmarks(self):
        self.bookmarks_tree.clear()
        self._populate_tree(self.presets_dir, self.bookmarks_tree.invisibleRootItem())
        if self.search_input.text():
            self.filter_bookmarks(self.search_input.text())

    def get_colored_folder_icon(self, color_hex):
        base_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        if not color_hex:
            return base_icon
            
        try:
            color = QColor(color_hex)
            pixmap = base_icon.pixmap(24, 24)
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
            painter.end()
            return QIcon(pixmap)
        except:
            return base_icon

    def _populate_tree(self, path, parent_item):
        if not os.path.exists(path): return
        items = os.listdir(path)
        items.sort()
        
        # Folders first
        for name in items:
            if name.startswith('.'): continue
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                color_file = os.path.join(full_path, ".folder_color")
                icon_color = None
                if os.path.exists(color_file):
                    try:
                        with open(color_file, 'r') as f:
                            icon_color = f.read().strip()
                    except: pass

                folder_item = QTreeWidgetItem(parent_item, [name])
                folder_item.setIcon(0, self.get_colored_folder_icon(icon_color))
                folder_item.setData(0, Qt.UserRole, full_path)
                self._populate_tree(full_path, folder_item)
        
        # Files next
        for name in items:
            full_path = os.path.join(path, name)
            if os.path.isfile(full_path) and name.endswith(".json"):
                file_item = QTreeWidgetItem(parent_item, [name.replace(".json", "")])
                file_item.setIcon(0, self.style().standardIcon(QStyle.SP_FileIcon))
                file_item.setData(0, Qt.UserRole, full_path)
                
                # Add tooltip with dimensions
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if "placed_items" in data:
                        tt = f"Збірка: {len(data['placed_items'])} об'єктів"
                    else:
                        L = data.get("length", 0)
                        W = data.get("width", 0)
                        H = data.get("height", 0)
                        tt = f"Розміри: {L}x{W}x{H} мм"
                        if data.get("gen_lid"): tt += "\nЗ кришкою"
                    file_item.setToolTip(0, tt)
                except:
                    pass

    def on_bookmark_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        
        if is_assembly:
            if os.path.isdir(path):
                self.populate_toolbox(path)
            elif os.path.isfile(path) and path.endswith(".json"):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "placed_items" in data:
                        self.placed_items = data.get("placed_items", [])
                        self.unplaced_items = data.get("unplaced_items", [])
                        self.placed_list.clear()
                        for p in self.placed_items: self.placed_list.addItem(p["name"])
                        self.unplaced_list.clear()
                        for u in self.unplaced_items: self.unplaced_list.addItem(u["name"])
                        self.mark_dirty()
                        self.update_adaptive_grid()
                        self.update_assembly_ui_state()
                    else:
                        # Single preset -> add to assembly directly
                        item_name = os.path.basename(path).replace(".json", "")
                        new_item = {
                            "name": item_name,
                            "data": data,
                            "x": 0.0,
                            "y": 0.0,
                            "rotation": 0,
                            "color_idx": len(self.placed_items) % len(self.assembly_palette)
                        }
                        self.placed_items.append(new_item)
                        self.placed_list.addItem(item_name)
                        self.generate_box()
                        self.update_assembly_ui_state()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося завантажити:\n{e}")
        else:
            if os.path.isfile(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.set_preset_dict(data)
                    self.generate_box()
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити закладку:\n{str(e)}")

    def save_as_bookmark(self):
        # Determine parent folder from selected item or root
        selected = self.bookmarks_tree.currentItem()
        target_dir = self.presets_dir
        if selected:
            data_path = selected.data(0, Qt.UserRole)
            if os.path.isdir(data_path):
                target_dir = data_path
            else:
                target_dir = os.path.dirname(data_path)
        
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        title = "Нова збірка" if is_assembly else "Нова закладка"
        name, ok = QInputDialog.getText(self, title, "Введіть назву:")
        if ok and name:
            filename = name if name.endswith(".json") else name + ".json"
            full_path = os.path.join(target_dir, filename)
            
            if os.path.exists(full_path):
                confirm = QMessageBox.question(self, "Перезапис", f"'{name}' вже існує. Перезаписати існуючу?", 
                                               QMessageBox.Yes | QMessageBox.No)
                if confirm != QMessageBox.Yes:
                    return

            if is_assembly:
                self.save_assembly_to_path(full_path)
            else:
                try:
                    with open(full_path, 'w', encoding='utf-8') as f:
                        json.dump(self.get_preset_dict(), f, indent=4)
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти:\n{e}")

    def create_preset_folder(self):
        selected = self.bookmarks_tree.currentItem()
        target_dir = self.presets_dir
        if selected:
            data_path = selected.data(0, Qt.UserRole)
            if os.path.isdir(data_path):
                target_dir = data_path
            else:
                target_dir = os.path.dirname(data_path)
        
        name, ok = QInputDialog.getText(self, "Нова папка", "Назва папки:")
        if ok and name:
            full_path = os.path.join(target_dir, name)
            try:
                if not os.path.exists(full_path):
                    os.makedirs(full_path)
                self.refresh_bookmarks()
            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося створити папку:\n{e}")

    def overwrite_selected_bookmark(self):
        item = self.bookmarks_tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Помилка", "Будь ласка, спочатку оберіть закладку (файл .json) у списку.")
            return
            
        target_path = item.data(0, Qt.UserRole)
        if not os.path.isfile(target_path) or not target_path.endswith(".json"):
            QMessageBox.warning(self, "Помилка", "Оберіть саме файл закладки для заміни.")
            return

        name = item.text(0)
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        msg = f"Ви впевнені, що хочете перезаписати '{name}' поточними параметрами?"
        if is_assembly: msg = f"Ви впевнені, що хочете перезаписати збірку '{name}'?"
        
        confirm = QMessageBox.question(self, "Замінити", msg, QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            if is_assembly:
                self.save_assembly_to_path(target_path)
            else:
                try:
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(self.get_preset_dict(), f, indent=4)
                    QMessageBox.information(self, "Успіх", f"Закладку '{name}' успішно оновлено.")
                except Exception as e:
                    QMessageBox.critical(self, "Помилка", f"Не вдалося оновити:\n{e}")

    def show_bookmarks_context_menu(self, pos):
        item = self.bookmarks_tree.itemAt(pos)
        target_path = item.data(0, Qt.UserRole) if item else self.presets_dir
        is_file = os.path.isfile(target_path) if item else False
        is_dir = os.path.isdir(target_path) if item else True

        menu = QMenu()
        
        # Actions for folders or empty space
        new_bookmark_act = QAction(" Зберегти нову закладку сюди", self)
        new_bookmark_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        new_folder_act = QAction(" Створити папку тут", self)
        new_folder_act.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        
        # Specific actions for existing items
        save_assem_here_act = None
        is_assem_mode = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()

        if is_assem_mode and is_dir:
            save_assem_here_act = QAction(" Зберегти ПОТОЧНУ збірку сюди", self)
            save_assem_here_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
            menu.addAction(save_assem_here_act)
            menu.addSeparator()

        update_action = None
        rename_action = None
        delete_action = None
        copy_action = None
        color_action = None
        export_all_stl_act = None
        export_all_step_act = None
        
        if item:
            if is_file:
                update_action = QAction(" Перезаписати поточними параметрами", self)
                update_action.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
                menu.addAction(update_action)
                menu.addSeparator()
            
            if is_dir:
                color_action = QAction(" Колір папки", self)
                color_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
                menu.addAction(color_action)
                
                export_all_stl_act = QAction(" Експортувати все у STL", self)
                export_all_stl_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
                menu.addAction(export_all_stl_act)
                
                export_all_step_act = QAction(" Експортувати все у STEP", self)
                export_all_step_act.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
                menu.addAction(export_all_step_act)
 
            copy_action = QAction(" Копіювати", self)
            copy_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
            rename_action = QAction(" Перейменувати", self)
            rename_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
            delete_action = QAction(" Видалити", self)
            delete_action.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            
            menu.addAction(copy_action)
            menu.addAction(rename_action)
            menu.addAction(delete_action)
            menu.addSeparator()

        menu.addAction(new_bookmark_act)
        menu.addAction(new_folder_act)
        
        action = menu.exec(self.bookmarks_tree.viewport().mapToGlobal(pos))
        if not action: return

        if action == update_action:
            is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
            if is_assembly:
                self.save_assembly_to_path(target_path)
            else:
                try:
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(self.get_preset_dict(), f, indent=4)
                    QMessageBox.information(self, "Успіх", f"Закладку '{item.text(0)}' успішно оновлено.")
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося оновити:\n{e}")

        elif action == save_assem_here_act:
            name, ok = QInputDialog.getText(self, "Нова збірка", "Назва збірки:")
            if ok and name:
                filename = name if name.endswith(".json") else name + ".json"
                full_path = os.path.join(target_path, filename)
                self.save_assembly_to_path(full_path)

        elif action == color_action:
            color_file = os.path.join(target_path, ".folder_color")
            current_color = "#ffffff"
            if os.path.exists(color_file):
                try:
                    with open(color_file, 'r') as f: current_color = f.read().strip()
                except: pass
            
            color = QColorDialog.getColor(QColor(current_color), self, f"Колір для '{item.text(0)}'")
            if color.isValid():
                try:
                    with open(color_file, 'w') as f:
                        f.write(color.name())
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося зберегти колір:\n{e}")

        elif action == new_bookmark_act:
            self.save_as_bookmark() # It uses currentItem or root automatically
            
        elif action == new_folder_act:
            self.create_preset_folder()

        elif action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Перейменування", "Нова назва:", text=item.text(0))
            if ok and new_name:
                parent_dir = os.path.dirname(target_path)
                suffix = ".json" if os.path.isfile(target_path) else ""
                new_path = os.path.join(parent_dir, new_name + suffix)
                try:
                    os.rename(target_path, new_path)
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка", f"Не вдалося перейменувати:\n{e}")

        elif action == copy_action:
            parent_dir = os.path.dirname(target_path)
            base_name = os.path.basename(target_path)
            if is_file:
                name_part = base_name.replace(".json", "")
                suffix = ".json"
            else:
                name_part = base_name
                suffix = ""
            
            new_name = f"{name_part}_copy"
            new_path = os.path.join(parent_dir, new_name + suffix)
            
            counter = 2
            while os.path.exists(new_path):
                new_path = os.path.join(parent_dir, f"{name_part}_copy_{counter}{suffix}")
                counter += 1
            
            try:
                if is_file:
                    shutil.copy2(target_path, new_path)
                else:
                    shutil.copytree(target_path, new_path)
                self.refresh_bookmarks()
            except Exception as e:
                QMessageBox.warning(self, "Помилка", f"Не вдалося скопіювати:\n{e}")
        
        elif action == delete_action:
            confirm = QMessageBox.question(self, "Видалення", f"Ви впевнені, що хочете видалити '{item.text(0)}'?", 
                                           QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                try:
                    if os.path.isdir(target_path):
                        shutil.rmtree(target_path)
                    else:
                        os.remove(target_path)
                    self.refresh_bookmarks()
                except Exception as e:
                    QMessageBox.warning(self, "Помилка видалення:\n{e}")
        
        elif action == export_all_stl_act:
            self.export_folder_bookmarks(target_path, "stl")
        elif action == export_all_step_act:
            self.export_folder_bookmarks(target_path, "step")

    def undo(self):
        if not self.undo_stack:
            self.statusBar().showMessage("Немає дій для скасування", 2000)
            return
        
        # Save current to redo
        self.redo_stack.append(self.get_preset_dict())
        
        state = self.undo_stack.pop()
        self._apply_history_state(state)
        self.statusBar().showMessage("Скасовано (Undo)", 2000)

    def redo(self):
        if not self.redo_stack:
            self.statusBar().showMessage("Немає дій для повтору", 2000)
            return
            
        # Save current to undo
        self.undo_stack.append(self.get_preset_dict())
        
        state = self.redo_stack.pop()
        self._apply_history_state(state)
        self.statusBar().showMessage("Повторено (Redo)", 2000)

    def _apply_history_state(self, state):
        self._suppress_history = True
        try:
            self.set_preset_dict(state)
            self.generate_box()
            self.last_state = state
        finally:
            self._suppress_history = False

    def filter_bookmarks(self, text):
        text = text.lower()
        
        def filter_item(item):
            item_text = item.text(0).lower()
            matches = text in item_text
            
            any_child_matches = False
            for i in range(item.childCount()):
                if filter_item(item.child(i)):
                    any_child_matches = True
            
            should_show = matches or any_child_matches
            item.setHidden(not should_show)
            if matches and text:
                # Expand parents to show match
                p = item.parent()
                while p:
                    p.setExpanded(True)
                    p = p.parent()
            return should_show

        root = self.bookmarks_tree.invisibleRootItem()
        for i in range(root.childCount()):
            filter_item(root.child(i))

    def export_folder_bookmarks(self, folder_path, fmt):
        json_files = sorted([f for f in os.listdir(folder_path) if f.endswith(".json")])
        if not json_files:
            QMessageBox.information(self, "Інфо", "У цій папці немає закладок (.json)")
            return

        dlg = ExportFolderDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        settings = dlg.get_settings()

        if settings["zip"]:
            export_dest, _ = QFileDialog.getSaveFileName(self, "Зберегти ZIP", folder_path + ".zip", "ZIP Files (*.zip)")
            if not export_dest: return
            # Create a localized temp dir for zip contents
            output_dir = os.path.join(os.path.dirname(export_dest), "_tmp_export_" + str(os.getpid()))
            if os.path.exists(output_dir): shutil.rmtree(output_dir)
            os.makedirs(output_dir)
        else:
            output_dir = QFileDialog.getExistingDirectory(self, "Оберіть папку для експорту")
            if not output_dir: return
            export_dest = output_dir

        # UI state backup
        current_data = self.get_preset_dict()
        current_mode_is_assem = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        old_placed = list(getattr(self, 'placed_items', []))
        old_unplaced = list(getattr(self, 'unplaced_items', []))

        count = 0
        errors = []
        all_shapes_to_combine = []
        
        progress = QProgressDialog("Експорт закладок...", "Скасувати", 0, len(json_files), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for i, filename in enumerate(json_files):
                if progress.wasCanceled(): break
                
                progress.setValue(i)
                progress.setLabelText(f"Обробка {filename}...")
                QApplication.processEvents()
                
                full_path = os.path.join(folder_path, filename)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    is_assem_data = "placed_items" in data
                    if is_assem_data:
                        if hasattr(self, 'mode_assem_btn'): self.mode_assem_btn.setChecked(True)
                        self.placed_items = data.get("placed_items", [])
                        self.unplaced_items = data.get("unplaced_items", [])
                        shape = self.generate_assembly_geometry()
                    else:
                        if hasattr(self, 'mode_assem_btn'): self.mode_assem_btn.setChecked(False)
                        self.set_preset_dict(data)
                        shape = self.generate_geometry()
                    
                    if shape:
                        if is_assem_data and isinstance(shape, list):
                            objs = [s.val() if hasattr(s, 'val') else s for s, c in shape]
                            final_shape = cq.Compound.makeCompound(objs) if objs else None
                        else:
                            final_shape = shape.val() if hasattr(shape, "val") else shape
                        
                        if final_shape:
                            if settings["combine"]:
                                # Offset combined items to avoid overlap if desired, 
                                # but usually simple compound is expected.
                                all_shapes_to_combine.append(final_shape)
                            else:
                                out_name = filename.replace(".json", "." + fmt)
                                cq.exporters.export(final_shape, os.path.join(output_dir, out_name), fmt.upper())
                            count += 1
                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
            
            if settings["combine"] and all_shapes_to_combine:
                progress.setLabelText("Об'єднання та фінальний експорт...")
                combined = cq.Compound.makeCompound(all_shapes_to_combine)
                base_name = os.path.basename(folder_path) or "export"
                cq.exporters.export(combined, os.path.join(output_dir, f"{base_name}.{fmt}"), fmt.upper())

            if settings["zip"]:
                progress.setLabelText("Створення ZIP-архіву...")
                with zipfile.ZipFile(export_dest, 'w', zipfile.ZIP_DEFLATED) as z:
                    for root, dirs, files in os.walk(output_dir):
                        for f in files:
                            z.write(os.path.join(root, f), f)
                shutil.rmtree(output_dir)

            progress.setValue(len(json_files))
        finally:
            QApplication.restoreOverrideCursor()
            # Restore state
            if hasattr(self, 'mode_assem_btn'): 
                self.mode_assem_btn.setChecked(current_mode_is_assem)
            self.placed_items = old_placed
            self.unplaced_items = old_unplaced
            self.set_preset_dict(current_data)
            self.generate_box()
        
        finish_msg = f"Оброблено {count} файлів."
        if settings["zip"]: finish_msg += f"\nАрхів збережено: {export_dest}"
        if errors: finish_msg += "\n\nПомилки:\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "Експорт завершено", finish_msg)

    def open_presets_folder(self):
        import subprocess
        try:
            if sys.platform == 'win32':
                os.startfile(self.presets_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.presets_dir])
            else:
                subprocess.Popen(['xdg-open', self.presets_dir])
        except Exception as e:
            QMessageBox.warning(self, "Помилка", f"Не вдалося відкрити папку:\n{e}")

    def export_library_zip(self):
        path, _ = QFileDialog.getSaveFileName(self, "Експорт бібліотеки", "presets_backup.zip", "ZIP Files (*.zip)")
        if not path: return
        
        try:
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.presets_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.presets_dir)
                        zipf.write(full_path, rel_path)
            QMessageBox.information(self, "Успіх", f"Бібліотеку успішно експортовано у {path}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося експортувати ZIP:\n{e}")

    def import_library_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Імпорт бібліотеки", "", "ZIP Files (*.zip)")
        if not path: return
        
        confirm = QMessageBox.question(self, "Імпорт", 
                                       "Ви хочете ЗАМІНИТИ поточну бібліотеку (Yes) чи ДОДАТИ нові файли (No)?",
                                       QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        
        if confirm == QMessageBox.Cancel: return
        
        try:
            if confirm == QMessageBox.Yes:
                # Clear existing
                for item in os.listdir(self.presets_dir):
                    p = os.path.join(self.presets_dir, item)
                    if os.path.isdir(p): shutil.rmtree(p)
                    else: os.remove(p)
            
            with zipfile.ZipFile(path, 'r') as zipf:
                zipf.extractall(self.presets_dir)
            
            self.refresh_bookmarks()
            QMessageBox.information(self, "Успіх", "Бібліотеку успішно імпортовано.")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося імпортувати ZIP:\n{e}")

    def build_tab_2d(self, base, tip, depth, fillet, is_female):
        hw_b = base / 2.0
        hw_t = tip / 2.0
        
        s = cq.Workplane("XY").sketch().polygon([
            (-hw_b, 0.0),
            (-hw_t, depth),
            (hw_t, depth),
            (hw_b, 0.0)
        ])
        
        if fillet > 0.0:
            try:
                s = s.vertices().fillet(fillet)
            except Exception as e:
                pass
                
        return s.finalize()

    # Функція генерації базової коробки (завжди починається з (0,0,0) як центр XY)
    def create_box_geometry(self, length, width, height, tw_b, tw_t, t_d, clear, fillet, modes):
        box = cq.Workplane("XY").box(length, width, height)
        
        def apply_tab(base_body, side, mode, count, base_w, tip_w, depth, clearance, rad):
            if mode == 2 or count <= 0: # Пряма
                return base_body
                
            is_female = (mode == 1)
            
            if is_female:
                actual_base = base_w + clearance*2
                actual_tip = tip_w + clearance*2
                actual_depth = depth + clearance
            else:
                actual_base = base_w
                actual_tip = tip_w
                actual_depth = depth

            # Створюємо один майстер-шип
            tab_sketch = self.build_tab_2d(actual_base, actual_tip, actual_depth, rad, is_female)
            tab_3d = tab_sketch.extrude(height).translate((0, 0, -height/2))
            
            if is_female:
                # Повертаємо на 180, щоб шип дивився "всередину" для вирізу
                tab_3d = tab_3d.rotate((0,0,0), (0,0,1), 180)
            
            if side in ["top", "bottom"]:
                edge_len = length
            else:
                edge_len = width
                
            # Розподіляємо count шипів уздовж грані
            segment = edge_len / count
            start_pos = -edge_len/2 + segment/2
            
            tabs_list = []
            for i in range(count):
                pos = start_pos + i * segment
                current_tab = tab_3d # CadQuery objects are usually immutable in transformations
                
                if side == "top": # +Y
                    current_tab = current_tab.translate((pos, width/2, 0))
                elif side == "bottom": # -Y
                    current_tab = current_tab.rotate((0,0,0), (0,0,1), 180).translate((-pos, -width/2, 0))
                elif side == "right": # +X
                    current_tab = current_tab.rotate((0,0,0), (0,0,1), -90).translate((length/2, pos, 0))
                elif side == "left": # -X
                    current_tab = current_tab.rotate((0,0,0), (0,0,1), 90).translate((-length/2, -pos, 0))
                
                tabs_list.append(current_tab)
            
            # Union all tabs for one side
            all_tabs = tabs_list[0]
            for i in range(1, len(tabs_list)):
                all_tabs = all_tabs.union(tabs_list[i])
                
            if is_female: # Cut
                # Tiny shift to ensure clean boolean (push slightly into the body)
                if side == "top": all_tabs = all_tabs.translate((0, 0.01, 0))
                if side == "bottom": all_tabs = all_tabs.translate((0, -0.01, 0))
                if side == "right": all_tabs = all_tabs.translate((0.01, 0, 0))
                if side == "left": all_tabs = all_tabs.translate((-0.01, 0, 0))
                return base_body.cut(all_tabs)
            else: # Union
                return base_body.union(all_tabs)

        top_m, bot_m, left_m, right_m = [m[0] for m in modes]
        top_c, bot_c, left_c, right_c = [m[1] for m in modes]

        box = apply_tab(box, "top", top_m, top_c, tw_b, tw_t, t_d, clear, fillet)
        box = apply_tab(box, "bottom", bot_m, bot_c, tw_b, tw_t, t_d, clear, fillet)
        box = apply_tab(box, "left", left_m, left_c, tw_b, tw_t, t_d, clear, fillet)
        box = apply_tab(box, "right", right_m, right_c, tw_b, tw_t, t_d, clear, fillet)
        
        return box

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
        
        # 1. Draw Body
        painter.setPen(QPen(QColor("#4a7"), 1.5))
        painter.setBrush(QColor(74, 170, 112, 40))
        painter.drawRect(rect)
        
        # 2. Draw schematic joints
        tab_size = 4  # size of joint schematic
        
        def draw_joints(side, mode, count):
            if mode == 2: return # None
            painter.setPen(QPen(QColor("#6c9"), 1))
            if mode == 0: # male (tab)
                painter.setBrush(QColor("#6c9"))
            else: # female (socket)
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
                else: # right
                    jx = rect.right() - (tab_size/2 if mode==0 else -tab_size/2)
                    jy = rect.top() + rect.height() * pos_pct - tab_size/2
                
                painter.drawRect(QRectF(jx, jy, tab_size, tab_size))

        draw_joints("top", int(data.get("side_top", 0)), int(data.get("side_top_count", 1)))
        draw_joints("bottom", int(data.get("side_bottom", 1)), int(data.get("side_bottom_count", 1)))
        draw_joints("left", int(data.get("side_left", 1)), int(data.get("side_left_count", 1)))
        draw_joints("right", int(data.get("side_right", 0)), int(data.get("side_right_count", 1)))

        # 3. Text
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
                    if "placed_items" in data:
                        continue  # Skip assembly files in toolbox
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

    def add_tool_to_assembly(self):
        current = self.toolbox_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Увага", "Оберіть коробку з панелі інструментів.")
            return

        path = current.data(Qt.UserRole)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Помилка", f"Не вдалося завантажити пресет:\n{e}")
            return

        item_name = current.text()
        # Auto-offset new items to prevent overlap
        n = len(self.placed_items)
        L = data.get("length", 100)
        W = data.get("width", 100)
        # Lay them out in a row offset by the box width
        if n == 0:
            new_x, new_y = 0.0, 0.0
        else:
            # Find the rightmost edge among all placed items and add this box next to it
            max_right = max(p["x"] + p["data"].get("length", 100)/2 for p in self.placed_items)
            new_x = max_right + L/2 + 10  # 10mm gap
            new_y = 0.0
        new_item = {
            "name": f"{item_name}_{n + 1}",
            "data": dict(data),  # Copy to avoid shared references
            "x": new_x,
            "y": new_y,
            "rotation": 0,
            "color_idx": n % len(self.assembly_palette)
        }
        self.placed_items.append(new_item)
        self.placed_list.addItem(new_item["name"])
        self.placed_list.setCurrentRow(len(self.placed_items) - 1)
        self.selected_placed_idx = len(self.placed_items) - 1
        if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
            self.update_puzzle_view()
        else:
            self.generate_box()
        self.update_assembly_ui_state()

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
        self.update_assembly_ui_state()

    # ========= Mouse interaction for 3D assembly ==========

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
            ev.accept()  # Eat the event – no zoom in Puzzle mode

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
        # pyqtgraph viewMatrix: T(0,0,-dist) * Rx(el-90) * Rz(az) * T(-center)
        # Inverse (camera-to-world): T(center) * Rz(-az) * Rx(90-el) * T(0,0,dist)
        m.rotate(-azi,     0, 0, 1)   # Rz(-azimuth)
        m.rotate(90 - ele, 1, 0, 0)   # Rx(90 - elevation)  ← KEY FIX
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
        for i, item in enumerate(self.placed_items):
            H    = item["data"].get("height", 50)
            hit  = self.ray_hit_plane_z(ro, rd, H / 2)
            if hit is None:
                hit = self.ray_hit_plane_z(ro, rd, 0.0)
            if hit is None:
                continue
            hx, hy = hit
            ix, iy = item.get("x", 0.0), item.get("y", 0.0)
            data   = item["data"]
            rot    = item.get("rotation", 0)
            if rot in [90, 270]:
                L, W = data.get("width", 100), data.get("length", 100)
            else:
                L, W = data.get("length", 100), data.get("width", 100)
            if (ix - L/2 <= hx <= ix + L/2) and (iy - W/2 <= hy <= iy + W/2):
                return i
        return -1

    def assembly_mouse_press(self, ev):
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        submode = getattr(self, 'assem_submode', 'puzzle')

        if is_assembly and submode == 'puzzle':
            sx, sy = ev.position().x(), ev.position().y()
            idx = self.get_item_under_cursor(sx, sy)

            if ev.button() == Qt.LeftButton and idx >= 0:
                # Drag this item
                self.selected_placed_idx = idx
                self.placed_list.setCurrentRow(idx)
                self._dragging = True
                self._drag_offset = (0.0, 0.0)
                self.view.setCursor(Qt.ClosedHandCursor)
                ev.accept()
                return
            elif ev.button() == Qt.RightButton and idx >= 0:
                # Quick rotate in puzzle mode
                item = self.placed_items[idx]
                item["rotation"] = (item.get("rotation", 0) + 90) % 360
                self.generate_box()
                ev.accept()
                return
            else:
                # Consume ALL other buttons in Puzzle mode — no camera rotation/pan
                ev.accept()
                return

        # View mode: normal camera controls
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
            # In Puzzle mode: show hand cursor over items, block camera move otherwise
            sx, sy = ev.position().x(), ev.position().y()
            if self.get_item_under_cursor(sx, sy) >= 0:
                self.view.setCursor(Qt.OpenHandCursor)
            else:
                self.view.unsetCursor()
            # Always consume in Puzzle mode to block camera pan
            ev.accept()
            return

        # View mode: pass to original handler
        self.view.unsetCursor()
        self._orig_mouseMoveEvent(ev)


    def assembly_mouse_release(self, ev):
        if self._dragging:
            self._dragging = False
            self.view.unsetCursor()
            # Auto-snap on release
            if self.selected_placed_idx >= 0:
                self.try_auto_snap(self.selected_placed_idx)
                self.generate_box()
            ev.accept()
            return
        
        self._orig_mouseReleaseEvent(ev)

    def get_local_side_at_global_direction(self, rotation, global_dir):
        """
        global_dir: 0=top (-Y Qt), 1=bottom (+Y Qt), 2=left (-X), 3=right (+X)
        Returns: local side index (0=top, 1=bottom, 2=left, 3=right)
        Note: rotation is in degrees, clockwise (as in Qt).
        """
        rot = (int(rotation) % 360) // 90
        # mapping[rot_steps][global_dir] -> local_side
        # rot_steps: 0=0deg, 1=90deg CW, 2=180deg, 3=270deg CW
        mapping = {
            0: {0:0, 1:1, 2:2, 3:3},
            1: {0:2, 1:3, 2:1, 3:0}, # 90 CW: Top is Local Left
            2: {0:1, 1:0, 2:3, 3:2}, # 180: Top is Local Bottom
            3: {0:3, 1:2, 2:0, 3:1}  # 270 CW: Top is Local Right
        }
        return mapping.get(rot, {0:0, 1:1, 2:2, 3:3}).get(global_dir, global_dir)

    def get_side_info(self, item, global_dir):
        """Get joint mode and count for an item's side facing a global direction."""
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
        """Try to snap the item at index idx to the nearest neighbor with joint compatibility check."""
        item = self.placed_items[idx]
        data = item["data"]
        rot = item.get("rotation", 0)
        
        # Get dimensions (swap if rotated 90/270)
        if (int(rot) // 90) % 2 == 1:
            my_L, my_W = data.get("width", 100), data.get("length", 100)
        else:
            my_L, my_W = data.get("length", 100), data.get("width", 100)
        
        my_x, my_y = item.get("x", 0), item.get("y", 0)
        snap_gap = 0.1
        snap_threshold = 20.0  # Slightly increased threshold for easier snapping
        
        best_snap = None
        best_dist = float('inf')
        
        for j, other in enumerate(self.placed_items):
            if j == idx:
                continue
            other_data = other["data"]
            other_rot = other.get("rotation", 0)
            if (int(other_rot) // 90) % 2 == 1:
                o_L, o_W = other_data.get("width", 100), other_data.get("length", 100)
            else:
                o_L, o_W = other_data.get("length", 100), other_data.get("width", 100)
            
            ox, oy = other.get("x", 0), other.get("y", 0)
            
            # Check 4 possible snap positions: (target_x, target_y, my_global_dir, other_global_dir, my_edge, oth_edge)
            # Global Dir: 0=top (-Y Qt), 1=bottom (+Y Qt), 2=left (-X Qt), 3=right (+X Qt)
            snaps = [
                # 1. Target: I am ABOVE other (-Y). My Bottom (1) touches Their Top (0).
                (ox, oy - o_W/2 - my_W/2 - snap_gap, 1, 0, my_L, o_L),
                
                # 2. Target: I am BELOW other (+Y). My Top (0) touches Their Bottom (1).
                (ox, oy + o_W/2 + my_W/2 + snap_gap, 0, 1, my_L, o_L),
                
                # 3. Target: I am LEFT of other (-X). My Right (3) touches Their Left (2).
                (ox - o_L/2 - my_L/2 - snap_gap, oy, 3, 2, my_W, o_W),
                
                # 4. Target: I am RIGHT of other (+X). My Left (2) touches Their Right (3).
                (ox + o_L/2 + my_L/2 + snap_gap, oy, 2, 3, my_W, o_W),
            ]
            
            for sx, sy, my_dir, other_dir, my_edge_len, oth_edge_len in snaps:
                # 1. Distance check
                d = ((my_x - sx) ** 2 + (my_y - sy) ** 2) ** 0.5
                if d < snap_threshold and d < best_dist:
                    # 2. Joint compatibility check
                    my_mode, my_count = self.get_side_info(item, my_dir)
                    oth_mode, oth_count = self.get_side_info(other, other_dir)
                    
                    # Prevent snapping if either side is straight (mode 2)
                    if my_mode == 2 or oth_mode == 2:
                        continue
                    
                    # Must be Male <-> Female, same tab count, and matching edge length
                    if my_mode != oth_mode and my_count == oth_count:
                        if abs(my_edge_len - oth_edge_len) < 1.0:
                            best_dist = d
                            best_snap = (sx, sy)
        
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
        
        # Color first item
        item["color_idx"] = 0
        
        self.mark_dirty()
        self.update_adaptive_grid()
        self.update_assembly_ui_state()

    def remove_from_assembly(self):
        if not hasattr(self, 'placed_items') or not self.placed_items:
            return
        if self.placed_list.currentRow() < 0:
            QMessageBox.warning(self, "Помилка", "Оберіть об'єкт зі збірки.")
            return
            
        idx = self.placed_list.currentRow()
        item = self.placed_items.pop(idx)
        self.placed_list.takeItem(idx)
        
        # Return to unplaced
        self.unplaced_items.append(item)
        self.unplaced_list.addItem(item["name"])
        
        self.mark_dirty()
        self.update_adaptive_grid()
        self.update_assembly_ui_state()
        if getattr(self, 'assem_submode', 'puzzle') == 'puzzle':
            self.update_puzzle_view()
        else:
            self.generate_box()

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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
            if is_assembly:
                self.remove_from_assembly()
                return
        super().keyPressEvent(event)


    def update_assembly_ui_state(self, *args):
        # Robustly get lists and counts
        p_items = getattr(self, 'placed_items', [])
        u_items = getattr(self, 'unplaced_items', [])
        p_count = len(p_items)
        u_count = len(u_items)
        
        has_placed = p_count > 0
        has_unplaced = u_count > 0
        has_selection = self.placed_list.currentRow() >= 0

        # Enable snap if we have at least one target and something to snap
        self.snap_btn.setEnabled(has_placed and has_unplaced)
        # Enable remove only if an item is selected in the placed list
        self.remove_btn.setEnabled(has_placed and has_selection)
        # Place first is ONLY for starting a new assembly
        self.place_first_btn.setEnabled(p_count == 0 and has_unplaced)
        
        # Height control needs selection
        self.live_height_sb.setEnabled(has_selection)
        if hasattr(self, 'h_label'):
            self.h_label.setEnabled(has_selection)
        
        # Save assembly is only for non-empty assemblies
        self.save_assem_btn.setEnabled(has_placed)
        self.add_n_btn.setEnabled(has_unplaced or self.bookmarks_tree.currentItem() is not None)

    def add_n_copies_dialog(self):
        target_item_data = None
        target_name = "Копія"
        
        # Check if something is selected in unplaced or bookmarks
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
                    if "placed_items" not in data: # Only for single presets
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
            if not path.startswith(self.presets_dir):
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
            
            # Refresh UI lists
            self.placed_list.clear()
            for item in self.placed_items: self.placed_list.addItem(item["name"])
            self.unplaced_list.clear()
            for item in self.unplaced_items: self.unplaced_list.addItem(item["name"])
            
            self.mark_dirty()
            self.update_adaptive_grid()
            self.update_assembly_ui_state()

            # Refresh current view (2D or 3D)
            if self.assem_submode == 'puzzle':
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
            self.view_stack.setCurrentIndex(1)      # show 2D canvas
            self.update_puzzle_view()
            self.statusBar().showMessage(
                "🧩 Пазл: ЛКМ — переміщення, ПКМ — поворот на 90°, колесо — зум", 4000)
        else:
            self.assem_submode = 'view'
            self.view_stack.setCurrentIndex(0)      # show 3D view
            self.generate_box()
            self.statusBar().showMessage(
                "🎥 Камера: вільне обертання 3D-виду", 3000)

    def update_puzzle_view(self):
        """Repopulate the 2D puzzle scene from placed_items."""
        self.puzzle_scene.clear()
        for idx in range(len(self.placed_items)):
            item_gfx = PuzzleBoxItem(idx, self)
            self.puzzle_scene.addItem(item_gfx)
        # Fit view to all items with some margin
        sr = self.puzzle_scene.itemsBoundingRect()
        if not sr.isEmpty():
            self.puzzle_canvas.fitInView(
                sr.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)

    def _puzzle_wheel_zoom(self, ev):
        """Zoom the 2D canvas with mouse wheel."""
        factor = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.puzzle_canvas.scale(factor, factor)


    def on_placed_item_changed(self, current, previous):
        if current:
            idx = self.placed_list.row(current)
            if idx >= 0 and idx < len(self.placed_items):
                item = self.placed_items[idx]
                self.selected_placed_idx = idx
                # Update height slider
                val = item["data"].get("height", 50)
                self.live_height_sb.blockSignals(True)
                self.live_height_sb.setValue(val)
                self.live_height_sb.blockSignals(False)
        self.update_assembly_ui_state()

    def on_live_height_changed(self, val):
        idx = self.placed_list.currentRow()
        if idx < 0: return
        self.placed_items[idx]["data"]["height"] = val
        self.mark_dirty()

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
            dat = item["data"]
            L, W = dat.get("length", 100), dat.get("width", 100)
            ix, iy = item["x"], item["y"]
            min_x = min(min_x, ix - L/2)
            max_x = max(max_x, ix + L/2)
            min_y = min(min_y, iy - W/2)
            max_y = max(max_y, iy + W/2)
            
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        span_x = max_x - min_x
        span_y = max_y - min_y
        
        max_span = max(span_x, span_y, 200) + 100 # Margin
        
        # Round up to nearest 100
        max_span = ((int(max_span) // 100) + 1) * 100
        
        self.grid.setSize(x=max_span, y=max_span, z=0)
        self.grid.setSpacing(x=10, y=10, z=0)
        
        self.grid.resetTransform()
        self.grid.translate(center_x, center_y, -0.1)

    def change_box_height(self, idx):
        pl = self.placed_items[idx]
        old_h = pl["data"].get("height", 50)
        # This can stay as a fallback or be removed. I'll make it use the live SB
        new_h, ok = QInputDialog.getDouble(self, "Висота", f"Введіть нову висоту для '{pl['name']}':", old_h, 1, 1000, 1)
        if ok:
            self.live_height_sb.setValue(new_h) # This triggers on_live_height_changed

    def is_side_occupied(self, item, side_idx):
        L, W = item["data"].get("length", 100), item["data"].get("width", 100)
        sx, sy = self.get_edge_center(item["x"], item["y"], L, W, side_idx)
        for other in self.placed_items:
            if other is item: continue
            oL, oW = other["data"].get("length", 100), other["data"].get("width", 100)
            for os in range(4):
                ox, oy = self.get_edge_center(other["x"], other["y"], oL, oW, os)
                if ((sx - ox)**2 + (sy - oy)**2)**0.5 < 1.0:
                    return True
        return False

    def copy_to_side(self, idx, screen_side):
        """Creates a copy of the item and places it on the specified side relative to screen directions."""
        source = self.placed_items[idx]
        s_data = source["data"]
        s_rot = int(source.get("rotation", 0)) % 360
        
        # New base data for copy
        new_data = s_data.copy()
        
        # Mapping Screen Side -> Physical Side based on rotation
        # screen_side: 0=Top(Visual Up, -Y), 1=Bottom(Visual Down, +Y), 2=Left(-X), 3=Right(+X)
        # Rotation is CW: 0 deg (Normal), 90 deg (Right), 180 deg (Upside down), 270 deg (Left)
        
        # Rotation 0:   Screen Top = Phys Top (0)
        # Rotation 90:  Screen Top = Phys Right (3)
        # Rotation 180: Screen Top = Phys Bottom (1)
        # Rotation 270: Screen Top = Phys Left (2)
        
        rot_steps = (s_rot // 90) % 4
        
        # Mapping Screen Side -> Physical Side based on rotation
        # At Rotation 0: Visual Up is Phys Top (0)
        # At Rotation 90 (CW): Visual Up is Phys Left (2)
        # At Rotation 180: Visual Up is Phys Bottom (1)
        # At Rotation 270 (CW): Visual Up is Phys Right (3)
        phys_map = {
            0: [0, 2, 1, 3], # Screen Top (Visual Up)
            1: [1, 3, 0, 2], # Screen Bottom (Visual Down)
            2: [2, 1, 3, 0], # Screen Left
            3: [3, 0, 2, 1]  # Screen Right
        }
        
        phys_side = phys_map[screen_side][rot_steps]

        def flip_mode(m):
            if m == 0: return 1
            if m == 1: return 0
            return 2

        # side indices for data map: 0=top, 1=bottom, 2=left, 3=right
        data_keys = [
            ("side_top", "side_top_count"),       # 0
            ("side_bottom", "side_bottom_count"), # 1
            ("side_left", "side_left_count"),     # 2
            ("side_right", "side_right_count")    # 3
        ]

        # u_side is the side of NEW box that will touch OLD box.
        # If we copy to OLD.phys_side, then NEW.opposite_phys_side touches it.
        u_side = phys_side ^ 1
        
        # Match NEW.u_side to OLD.phys_side
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
        
        # Add to unplaced AND list widget to keep them in sync for do_snap
        self.unplaced_items.append(new_item)
        self.unplaced_list.addItem(new_item["name"])
        u_idx = len(self.unplaced_items) - 1
        
        try:
            # Snap new_item[u_side] to source[phys_side]
            self.do_snap(u_idx, u_side, idx, phys_side)
            self.update_puzzle_view()
            self.generate_box()
            self.statusBar().showMessage(f"Створено копію {new_item['name']}", 3000)
        except Exception as e:
            # Cleanup if failed
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

        n, ok = QInputDialog.getInt(self, "Розбити фігуру", "На скільки частин розбити?", 2, 2, 50)
        if not ok or n < 2:
            return

        orig_L = data.get("length", 100)
        orig_W = data.get("width", 100)
        orig_x = item["x"]
        orig_y = item["y"]
        
        new_items = []
        for i in range(n):
            new_data = data.copy()
            
            if logic_axis == 'length':
                new_data["length"] = orig_L / n
                
                for c_key in ["side_top_count", "side_bottom_count"]:
                    if int(data.get(c_key.replace("_count", ""), 2)) != 2:
                        new_data[c_key] = max(1, int(round(data.get(c_key, 1) / n)))
                
                if i > 0:
                    new_data["side_left"] = 1
                    new_data["side_left_count"] = 1
                if i < n - 1:
                    new_data["side_right"] = 0
                    new_data["side_right_count"] = 1
                
                local_dx = -orig_L / 2 + (orig_L / n) / 2 + i * (orig_L / n)
                local_dy = 0
            else:
                new_data["width"] = orig_W / n
                
                for c_key in ["side_left_count", "side_right_count"]:
                    if int(data.get(c_key.replace("_count", ""), 2)) != 2:
                        new_data[c_key] = max(1, int(round(data.get(c_key, 1) / n)))
                        
                if i > 0:
                    new_data["side_top"] = 1
                    new_data["side_top_count"] = 1
                if i < n - 1:
                    new_data["side_bottom"] = 0
                    new_data["side_bottom_count"] = 1
                
                local_dx = 0
                local_dy = -orig_W / 2 + (orig_W / n) / 2 + i * (orig_W / n)
            
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

    def get_edge_center(self, x, y, L, W, side, rotation=0):
        # Local offset before rotation
        # side: 0:Top(-Y visual), 1:Bottom(+Y visual), 2:Left(-X visual), 3:Right(+X visual)
        if side == 0: vx, vy = 0, -W/2
        elif side == 1: vx, vy = 0, W/2
        elif side == 2: vx, vy = -L/2, 0
        elif side == 3: vx, vy = L/2, 0
        else: return x, y
        
        # Rotate vector CW by 'rotation' degrees (Qt style)
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
        
        # 1. Position calculation (Rotation-Aware)
        p_L, p_W = p_data.get("length", 100), p_data.get("width", 100)
        p_ec_x, p_ec_y = self.get_edge_center(p_item["x"], p_item["y"], p_L, p_W, p_side, p_rot)
        
        u_L, u_W = u_data.get("length", 100), u_data.get("width", 100)
        # Vector from new item center to its snapping edge
        uv_x, uv_y = self.get_edge_center(0, 0, u_L, u_W, u_side, u_rot)
        
        # Unit normal of p_side for gap
        # Vector from p center to p edge
        pv_x, pv_y = self.get_edge_center(0, 0, p_L, p_W, p_side, p_rot)
        p_mag = (pv_x**2 + pv_y**2)**0.5
        gap_ux, gap_uy = pv_x/p_mag, pv_y/p_mag
        
        snap_gap = 0.1
        u_x = p_ec_x + gap_ux * snap_gap - uv_x
        u_y = p_ec_y + gap_uy * snap_gap - uv_y

        # 2. Aggregation (Rotation-Aware check)
        ux_center, uy_center = self.get_edge_center(u_x, u_y, u_L, u_W, u_side, u_rot)
        
        # Determine if the edge is visually horizontal or vertical
        # Side normal direction determines axis
        if abs(gap_uy) > abs(gap_ux): # Vertical normal -> Horizontal edge
            axis = "y"
            # The effective length of the edge depends on rotation
            effective_u_len = u_L if (u_rot // 90) % 2 == 0 else u_W
            seg_min, seg_max = ux_center - effective_u_len / 2, ux_center + effective_u_len / 2
        else: # Horizontal normal -> Vertical edge
            axis = "x"
            # The effective length of the edge depends on rotation
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
                # Check if the placed item's edge center is close to the unplaced item's snapping edge center
                if ((ux_center - plx_e)**2 + (uy_center - ply_e)**2)**0.5 < 1.0:
                    pm, pc, pe, po = keys_map[ps]
                    total_p_edge_len += pl_dat[pe]
                    total_p_tab_count += pl_dat[pc]
                    if p_mode_rep is None: p_mode_rep = pl_dat[pm]
                    # Track coordinates for re-centering
                    if axis == "y": seg_coords.extend([plx_e - pl_dat[pe]/2, plx_e + pl_dat[pe]/2])
                    else: seg_coords.extend([ply_e - pl_dat[pe]/2, ply_e + pl_dat[pe]/2])

        # 2.5 Re-center based on aggregated targets
        if seg_coords:
            combined_min = min(seg_coords)
            combined_max = max(seg_coords)
            combined_center = (combined_min + combined_max) / 2
            if axis == "y": u_x = combined_center
            else: u_y = combined_center

        # 3. Aggregated Validation
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

        # 4. Proximity for other sides
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
        
        # 5. Color selection (Neighbor-aware)
        used_colors = set()
        for pl_item in self.placed_items:
            # Simple bounding box overlap check for color neighbors
            pl_dat = pl_item["data"]
            pl_L, pl_W = pl_dat.get("length", 100), pl_dat.get("width", 100)
            
            # Check if boxes are "touching" (within 1mm)
            # Box-Box proximity logic
            dx = abs(u_x - pl_item["x"]) - (u_L + pl_L)/2
            dy = abs(u_y - pl_item["y"]) - (u_W + pl_W)/2
            
            if dx < 1.0 and dy < 1.0: # Touching or overlapping
                if "color_idx" in pl_item:
                    used_colors.add(pl_item["color_idx"])
        
        # Pick first available color from palette
        new_color = 0
        for i in range(len(self.assembly_palette)):
            if i not in used_colors:
                new_color = i
                break
        u_item["color_idx"] = new_color

        u_item["x"], u_item["y"] = u_x, u_y
        self.unplaced_items.pop(u_idx)
        
        # Safer sync of unplaced list: rebuild it
        self.unplaced_list.clear()
        for it in self.unplaced_items:
            self.unplaced_list.addItem(it["name"])

        self.placed_items.append(u_item)
        self.placed_list.addItem(u_item["name"])
        self.mark_dirty()
        self.update_assembly_ui_state()

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

        # Основна коробка
        main_box = self.create_box_geometry(L, W, H, tw_b, tw_t, t_d, clear, fillet, modes)
        main_box = main_box.translate((0, 0, H/2)) # На площину Z=0
        
        assembly = cq.Assembly()
        assembly.add(main_box, name="Box")

        if gen_lid:
            bx = self.bed_x_input.value()
            by = self.bed_y_input.value()
            # Для внутрішньої кришки в Vase Mode: 
            # Від зовнішнього габариту віднімаємо ширину стінки принтера (extrusion width),
            # плюс віднімаємо зазор (tolerance).  
            inset = lid_tol + lid_ext
            
            # Беремо нижній контур основної коробки
            try:
                bottom_wire = main_box.faces("<Z").wires().val()
                lid_wp = cq.Workplane("XY").add(bottom_wire).toPending().offset2D(-inset, kind='intersection')
                lid_box = lid_wp.extrude(lid_h)
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
                # Позиціонуємо кришку відносно коробки (тимчасово)
                offset_x = box_x_max + gap + lid_x_span/2
                lid_box = lid_box.translate((offset_x, 0, lid_h/2))
                assembly.add(lid_box, name="Lid")
                
                # Центруємо всю збірку на столі (0,0)
                # Поточні межі: [box_x_min, offset_x + lid_x_span/2]
                assembly_x_min = box_x_min
                assembly_x_max = offset_x + lid_x_span/2
                shift_x = -(assembly_x_min + assembly_x_max) / 2
                
                # По осі Y коробка вже центрована, але якщо кришка має інший габарит...
                # Але оскільки кришка базується на L,W - вона теж центрована по Y в (0,0)
                
                comp = assembly.toCompound().translate((shift_x, 0, 0))
                self.current_lid_offset_x = 0 
                self.update_grid()
                return comp
            else:
                self.is_single_bed = False
                self.bed_status_label.setText("Розміщення: Окремо")
                offset_x = bx + 40
                self.current_lid_offset_x = offset_x
                lid_box = lid_box.translate((offset_x, 0, lid_h/2))
                assembly.add(lid_box, name="Lid")
                self.update_grid()
                return assembly.toCompound()
        else:
            self.is_single_bed = False
            self.bed_status_label.setText("Статус: Без кришки")
            self.update_grid()
            return main_box


    def generate_assembly_geometry(self):
        if not hasattr(self, 'placed_items') or not self.placed_items:
            return []
            
        items_with_colors = []
        for i, item in enumerate(self.placed_items):
            data = item["data"]
            def dget(key, default): return data.get(key, default)
            box = self.create_box_geometry(
                dget("length", 100), dget("width", 100), dget("height", 50),
                dget("tab_base", 20), dget("tab_tip", 30), dget("tab_depth", 10),
                dget("clearance", 0.3), dget("fillet", 2.0),
                (
                    (int(dget("side_top", 0)), dget("side_top_count", 1)),
                    (int(dget("side_bottom", 1)), dget("side_bottom_count", 1)),
                    (int(dget("side_left", 1)), dget("side_left_count", 1)),
                    (int(dget("side_right", 0)), dget("side_right_count", 1))
                )
            )
            H = dget("height", 50)
            
            # Apply rotation (Qt uses clockwise, CadQuery rotate uses counter-clockwise)
            rotation = item.get("rotation", 0)
            if rotation != 0:
                box = box.rotate((0, 0, 0), (0, 0, 1), -rotation)
            
            box = box.translate((item["x"], item["y"], H/2))
            items_with_colors.append((box, item.get("color_idx", 0)))
        
        return items_with_colors

    def generate_box(self):
        try:
            self.statusBar().showMessage("Генерація 3D моделі...", 2000)
            QApplication.processEvents()
            
            if hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked():
                self.current_shape = self.generate_assembly_geometry()
            else:
                self.current_shape = self.generate_geometry()
                
            self.update_view()
            self.last_state = self.get_preset_dict()
            
            self.statusBar().showMessage("Успішно згенеровано!", 5000)
        except ValueError as e:
            QMessageBox.warning(self, "Помилка Вводу", str(e) + "\n(Можливо ви ввели текст замість числа)")
            self.statusBar().showMessage("Помилка вводу.", 5000)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Помилка Геометрії", f"Не вдалося згенерувати фігуру:\n{str(e)}")
            self.statusBar().showMessage("Помилка генерації.", 5000)

    def update_view(self):
        if self.current_shape is None: return
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        
        # Clear old decorations
        for item in self.assembly_decorations:
            self.view.removeItem(item)
        self.assembly_decorations = []

        # Clear old dimensions
        for item in self.dimension_items:
            self.view.removeItem(item)
        self.dimension_items = []

        def get_coords(v):
            if hasattr(v, 'x'): return [v.x, v.y, v.z]
            try: return [float(v[0]), float(v[1]), float(v[2])]
            except: return [0.0, 0.0, 0.0]

        try:
            all_verts = []
            all_faces = []
            all_v_colors = []
            all_edge_points = []
            
            if is_assembly:
                # current_shape is a list of (shape, color_idx)
                if not isinstance(self.current_shape, list):
                    # Fallback if somehow it's not a list
                    self.current_shape = [(self.current_shape, 0)]

                for shape_item, c_idx in self.current_shape:
                    v_list, f_list = shape_item.val().tessellate(0.2)
                    v_offset = len(all_verts)
                    
                    color = self.assembly_palette[c_idx % len(self.assembly_palette)]
                    
                    for v in v_list:
                        all_verts.append(get_coords(v))
                        all_v_colors.append(color)
                    
                    for f in f_list:
                        all_faces.append([f[0] + v_offset, f[1] + v_offset, f[2] + v_offset])

                    # Edges
                    for edge in shape_item.val().Edges():
                        pts = edge.tessellate(0.1)
                        for i in range(len(pts) - 1):
                            all_edge_points.append(get_coords(pts[i]))
                            all_edge_points.append(get_coords(pts[i+1]))
            else:
                shape_item = self.current_shape.val() if hasattr(self.current_shape, "val") else self.current_shape
                v_list, f_list = shape_item.tessellate(0.2)
                for v in v_list:
                    all_verts.append(get_coords(v))
                    
                for f in f_list:
                    all_faces.append([f[0], f[1], f[2]])
                
                # Edges
                for edge in shape_item.Edges():
                    pts = edge.tessellate(0.1)
                    for i in range(len(pts) - 1):
                        all_edge_points.append(get_coords(pts[i]))
                        all_edge_points.append(get_coords(pts[i+1]))

            # Set Mesh
            if all_verts:
                verts_np = np.array(all_verts)
                faces_np = np.array(all_faces)
                colors_np = np.array(all_v_colors) if is_assembly else None
                
                self.mesh_item.setMeshData(vertexes=verts_np, faces=faces_np, vertexColors=colors_np)
                self.edge_item.setData(pos=np.array(all_edge_points))

                # Draw Dimensions if requested
                if self.show_dims_cb.isChecked():
                    self.draw_dimensions(verts_np)
            else:
                # Clear view if nothing to show
                self.mesh_item.setMeshData(vertexes=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int))
                self.edge_item.setData(pos=np.zeros((0, 3)))

        except Exception as e:
            print(f"Update view error: {e}")
            import traceback
            traceback.print_exc()

        # Add markers for sides (Always)
        if not is_assembly and self.current_shape:
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
            if hasattr(self, 'placed_items'):
                for item in self.placed_items:
                    data = item["data"]
                    ox, oy = item["x"], item["y"]
                    L = data.get("length", 100)
                    W = data.get("width", 100)
                    H = data.get("height", 50)
                    
                    # Labels for sides of each box in assembly
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

                    # Local Axes
                    ax = gl.GLAxisItem()
                    ax.setSize(x=30, y=30, z=30)
                    ax.translate(ox, oy, H) # Place on top
                    self.view.addItem(ax)
                    self.assembly_decorations.append(ax)
                    
                    # Box Name Label
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

    def export_file(self, fmt):
        if self.current_shape is None:
            QMessageBox.warning(self, "Помилка експорту", "Спочатку згенеруйте 3D фігуру.")
            return
            
        is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
        
        if fmt == "step":
            filter_str = "STEP Files (*.step *.stp)"
            ext = ".step"
        else:
            filter_str = "STL Files (*.stl)"
            ext = ".stl"
            
        path, _ = QFileDialog.getSaveFileName(self, "Зберегти файл", "box_export" + ext, filter_str)
        if not path:
            return
            
        try:
            shape_to_export = None
            if is_assembly:
                if isinstance(self.current_shape, list):
                    # Combine all shapes that have colors (placed items)
                    shapes = [s.val() if hasattr(s, 'val') else s for s, c in self.current_shape]
                    if shapes:
                        shape_to_export = cq.Compound.makeCompound(shapes)
                else:
                    shape_to_export = self.current_shape
            else:
                shape_to_export = self.current_shape
                
            if shape_to_export:
                if fmt == "step":
                    cq.exporters.export(shape_to_export, path, "STEP")
                else:
                    cq.exporters.export(shape_to_export, path, "STL")
                QMessageBox.information(self, "Успіх", f"Успішно збережено у {path}")
            else:
                 QMessageBox.warning(self, "Помилка", "Немає об'єктів для експорту.")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти файл:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Dark Mode Palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    win = BoxGeneratorApp()
    win.show()
    sys.exit(app.exec())
