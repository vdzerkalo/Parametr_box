import os
import shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, 
    QMessageBox, QComboBox, QRadioButton, QCheckBox, 
    QToolButton, QFrame, QStyle, QSizePolicy, QTreeWidget, 
    QDialog, QDialogButtonBox, QListWidget, QApplication, QGraphicsView
)
from PySide6.QtCore import Qt, QSize, QMimeData, QPoint
from PySide6.QtGui import QDrag, QPixmap

class PuzzleGraphicsView(QGraphicsView):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # Якщо після обробки події (можливо клік по ітему) нічого не виділено, 
        # або ми клікнули саме по фону
        if not self.scene().itemAt(self.mapToScene(event.pos()), self.transform()):
            if hasattr(self, 'main_app') and self.main_app:
                self.main_app.placed_list.clearSelection()
                self.main_app.placed_list.setCurrentRow(-1)
                self.main_app.update_assembly_ui_state()

class ToolboxListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self._drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not self._drag_start_pos:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        
        item = self.itemAt(self._drag_start_pos)
        if not item:
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        path = item.data(Qt.UserRole)
        # Передаємо шлях до JSON та назву
        mime_data.setText(path)
        mime_data.setData("application/x-toolbox-item-name", item.text().encode('utf-8'))
        drag.setMimeData(mime_data)
        
        icon = item.icon()
        if not icon.isNull():
            pixmap = icon.pixmap(QSize(64, 64))
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        
        drag.exec(Qt.CopyAction)

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
