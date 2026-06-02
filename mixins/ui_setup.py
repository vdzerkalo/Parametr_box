import os
import sys

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFormLayout, QGroupBox, QComboBox, QCheckBox, QScrollArea, QGridLayout,
                             QToolButton, QFrame, QStyle, QSizePolicy, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QInputDialog, QMenu,
                             QDoubleSpinBox, QSpinBox, QColorDialog,
                             QRadioButton, QButtonGroup, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox, QProgressDialog,
                             QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem, QStackedWidget,
                             QSplitter)
from PySide6.QtGui import QPalette, QColor, QIcon, QAction, QPainter, QPixmap, QShortcut, QKeySequence, QPen, QBrush, QFont, QFontMetricsF
from PySide6.QtCore import Qt, QSettings, QFileInfo, QDir, QTimer, QSize, QRectF

import pyqtgraph.opengl as gl

from ui_widgets import CollapsibleBox, BookmarksTreeWidget, ToolboxListWidget, PuzzleGraphicsView

class UISetupMixin:
    def setup_ui(self):
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
            
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout_ui = QHBoxLayout(central_widget)
        self.main_layout_ui.setContentsMargins(0, 0, 0, 0)
        self.main_layout_ui.setSpacing(0)
        
        self.settings_pos = "right"
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedWidth(600)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #2d2d2d; }")

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        
        # Top utility bar
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
        # Поки нічого не виділяємо, зробимо це в кінці setup_ui
        mode_layout.addWidget(QLabel("Режим:"))
        mode_layout.addWidget(self.mode_gen_btn)
        mode_layout.addWidget(self.mode_assem_btn)
        mode_layout.addStretch()
        self.mode_gen_btn.toggled.connect(self.switch_mode)
        left_layout.addLayout(mode_layout)
        
        # Create presets folder if not exists
        self.presets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "presets")
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
        self.bookmarks_tree.currentItemChanged.connect(lambda curr, prev: self.on_bookmark_clicked(curr, 0) if (curr and self.bookmarks_tree.hasFocus()) else None)
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
        self.puzzle_mode_btn = QPushButton(" 2D")
        self.split_mode_btn = QPushButton(" 2D+3D")
        self.view_mode_btn = QPushButton(" 3D")
        self.puzzle_mode_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.split_mode_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.view_mode_btn.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.puzzle_mode_btn.setToolTip("Лише 2D-пазл: редагування комірок, перетягування стінок")
        self.split_mode_btn.setToolTip("Спліт: 2D-редактор ліворуч + 3D-перегляд праворуч.\nПравки видно у 3D у реальному часі")
        self.view_mode_btn.setToolTip("Лише 3D: вільне обертання моделі")
        for b in (self.puzzle_mode_btn, self.split_mode_btn, self.view_mode_btn):
            b.setCheckable(True)
        self.puzzle_mode_btn.setChecked(True)

        self.submode_group = QButtonGroup(self)
        self.submode_group.addButton(self.puzzle_mode_btn)
        self.submode_group.addButton(self.split_mode_btn)
        self.submode_group.addButton(self.view_mode_btn)
        self.submode_group.buttonClicked.connect(self.on_assem_submode_changed)

        submode_layout.addWidget(self.puzzle_mode_btn)
        submode_layout.addWidget(self.split_mode_btn)
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
        
        self.clear_assem_btn = QPushButton(" Очистити стіл")
        self.clear_assem_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        self.clear_assem_btn.clicked.connect(self.clear_assembly)
        
        assembly_layout.addWidget(self.clear_assem_btn)
        
        
        self.placed_list = QListWidget()
        self.placed_list.setFixedHeight(120)
        assembly_layout.addWidget(QLabel("Об'єкти в збірці:"))
        self.placed_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.placed_list.customContextMenuRequested.connect(self.show_placed_context_menu)
        self.placed_list.currentItemChanged.connect(self.on_placed_item_changed)
        self.placed_list.currentRowChanged.connect(self.update_assembly_ui_state)
        self.placed_list.currentRowChanged.connect(self.update_puzzle_selection)
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

        if hasattr(self, '_setup_grid_panel'):
            self._setup_grid_panel(left_layout)

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
        
        self.align_labels()

        self.scroll_area.setWidget(left_panel)
        
        # Right Panel for 3D View
        self.view = gl.GLViewWidget()
        self.view.setMouseTracking(True)
        self.view.opts['distance'] = 300
        
        self.view_container = QWidget()
        view_layout = QVBoxLayout(self.view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(0)
        
        self.view_tb = QHBoxLayout()
        self.view_tb.setContentsMargins(10, 5, 10, 5)
        self.pan_btn = QToolButton()
        self.pan_btn.setText(" 🖐 Рука (Сунути) ")
        self.pan_btn.setCheckable(True)
        self.pan_btn.setStyleSheet("QToolButton:checked { background-color: #4a7; color: white; border-radius: 3px; } QToolButton { padding: 4px; border-radius: 3px; }")
        self.view_tb.addWidget(self.pan_btn)

        self.ruler_btn = QToolButton()
        self.ruler_btn.setText(" 📐 Лінійка ")
        self.ruler_btn.setCheckable(True)
        self.ruler_btn.setStyleSheet("QToolButton:checked { background-color: #d82; color: white; border-radius: 3px; } QToolButton { padding: 4px; border-radius: 3px; }")
        self.ruler_btn.toggled.connect(lambda: self.update_ruler_mode())
        self.view_tb.addWidget(self.ruler_btn)

        self.view_tb.addWidget(QLabel(" Масштаб (камера):"))
        from PySide6.QtWidgets import QSlider
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 2000)
        self.zoom_slider.setValue(300)
        self.zoom_slider.setFixedWidth(200)
        
        def on_zoom_change(val):
            self.view.opts['distance'] = val
            self.view.update()
        self.zoom_slider.valueChanged.connect(on_zoom_change)
        self.view_tb.addWidget(self.zoom_slider)

        self.view_tb.addSpacing(20)
        self.hide_labels_cb = QCheckBox(" Прибрати написи")
        self.hide_labels_cb.setStyleSheet("QCheckBox { color: #ccc; font-weight: bold; }")
        
        def on_hide_labels_toggle(checked):
            if hasattr(self, 'puzzle_scene'): self.puzzle_scene.update()
            if hasattr(self, '_update_decorations'):
                is_assem = getattr(self, 'mode_assem_btn', None) and self.mode_assem_btn.isChecked()
                self._update_decorations(is_assem)

        self.hide_labels_cb.toggled.connect(on_hide_labels_toggle)
        self.view_tb.addWidget(self.hide_labels_cb)
        
        self.view_tb.addStretch()
        
        view_layout.addLayout(self.view_tb)
        view_layout.addWidget(self.view, stretch=1)
        
        self.view.setAcceptDrops(True)
        self.view.dragEnterEvent = lambda ev: self.view_dragEnterEvent(ev)
        self.view.dragMoveEvent = lambda ev: self.view_dragMoveEvent(ev)
        self.view.dropEvent = lambda ev: self.view_dropEvent(ev)
        
        self._gl_mousePressEvent = self.view.mousePressEvent
        self._gl_mouseMoveEvent = self.view.mouseMoveEvent
        self._gl_mouseReleaseEvent = self.view.mouseReleaseEvent
        self._gl_wheelEvent = self.view.wheelEvent
        
        from PySide6.QtGui import QMouseEvent
        
        def wrapped_mousePressEvent(ev):
            if hasattr(self, 'ruler_btn') and self.ruler_btn.isChecked():
                if hasattr(self, '_ruler_mouse_press'):
                    self._ruler_mouse_press(ev)
                return

            if self.pan_btn.isChecked() and ev.button() == Qt.MouseButton.LeftButton:
                fake_ev = QMouseEvent(ev.type(), ev.position(), ev.globalPosition(), Qt.MouseButton.MiddleButton, Qt.MouseButton.MiddleButton, ev.modifiers())
                self._gl_mousePressEvent(fake_ev)
            else:
                self._gl_mousePressEvent(ev)
                
        def wrapped_mouseMoveEvent(ev):
            if hasattr(self, 'ruler_btn') and self.ruler_btn.isChecked():
                if hasattr(self, '_ruler_mouse_move'):
                    self._ruler_mouse_move(ev)
                return

            if self.pan_btn.isChecked() and (ev.buttons() & Qt.MouseButton.LeftButton):
                fake_ev = QMouseEvent(ev.type(), ev.position(), ev.globalPosition(), Qt.MouseButton.MiddleButton, Qt.MouseButton.MiddleButton, ev.modifiers())
                self._gl_mouseMoveEvent(fake_ev)
            else:
                self._gl_mouseMoveEvent(ev)

        def wrapped_mouseReleaseEvent(ev):
            if self.pan_btn.isChecked() and ev.button() == Qt.MouseButton.LeftButton:
                fake_ev = QMouseEvent(ev.type(), ev.position(), ev.globalPosition(), Qt.MouseButton.MiddleButton, Qt.MouseButton.MiddleButton, ev.modifiers())
                self._gl_mouseReleaseEvent(fake_ev)
            else:
                self._gl_mouseReleaseEvent(ev)
                
        def wrapped_wheelEvent(ev):
            self._gl_wheelEvent(ev)
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(int(self.view.opts.get('distance', 300)))
            self.zoom_slider.blockSignals(False)
            
        self.view.mousePressEvent = wrapped_mousePressEvent
        self.view.mouseMoveEvent = wrapped_mouseMoveEvent
        self.view.mouseReleaseEvent = wrapped_mouseReleaseEvent
        self.view.wheelEvent = wrapped_wheelEvent
        
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
        
        import numpy as _np_init
        _empty_verts = _np_init.zeros((3, 3), dtype=_np_init.float32)
        _empty_faces  = _np_init.array([[0, 1, 2]], dtype=_np_init.uint32)
        self.mesh_item = gl.GLMeshItem(
            vertexes=_empty_verts, faces=_empty_faces,
            color=(0.1, 0.7, 1.0, 0.4), smooth=True, drawEdges=False, computeNormals=False
        )
        self.mesh_item.setGLOptions('translucent')
        self.view.addItem(self.mesh_item)
        
        self.edge_item = gl.GLLinePlotItem(color=(1.0, 1.0, 1.0, 0.8), width=1.5, mode='lines', antialias=True)
        self.edge_item.setGLOptions('translucent')
        self.view.addItem(self.edge_item)



        # Right Panel: 3D View + 2D Canvas + Toolbox
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Split-перегляд: 3D-в'юпорт ліворуч + 2D-пазл праворуч (можна обидва)
        self.view_split = QSplitter(Qt.Horizontal)
        self.view_split.setChildrenCollapsible(False)
        self.view_split.setHandleWidth(4)
        self.view_split.addWidget(self.view_container)

        self.puzzle_scene  = QGraphicsScene()
        self.puzzle_canvas = PuzzleGraphicsView(self.puzzle_scene)
        self.puzzle_canvas.main_app = self
        self.puzzle_canvas.setRenderHint(QPainter.Antialiasing)
        self.puzzle_canvas.setBackgroundBrush(QBrush(QColor(32, 32, 32)))
        self.puzzle_canvas.setDragMode(QGraphicsView.RubberBandDrag)
        self.puzzle_canvas.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.puzzle_canvas.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.puzzle_canvas.setAcceptDrops(True)
        self.puzzle_canvas.dragEnterEvent = lambda ev: self.puzzle_dragEnterEvent(ev)
        self.puzzle_canvas.dragMoveEvent = lambda ev: self.puzzle_dragMoveEvent(ev)
        self.puzzle_canvas.dropEvent = lambda ev: self.puzzle_dropEvent(ev)
        # Pass key events to the main window
        self.puzzle_canvas.keyPressEvent = self.keyPressEvent
        
        # Grid Drawing override
        def draw_grid(painter, rect):
            scale = 1.5
            left = int(rect.left())
            right = int(rect.right())
            top = int(rect.top())
            bottom = int(rect.bottom())
            
            pen10 = QPen(QColor(50, 50, 50), 0.5)
            pen100 = QPen(QColor(70, 70, 70), 0.8)
            
            for x in range((left // int(10*scale)) * int(10*scale), right, int(10*scale)):
                painter.setPen(pen100 if x % int(100*scale) == 0 else pen10)
                painter.drawLine(x, top, x, bottom)
            for y in range((top // int(10*scale)) * int(10*scale), bottom, int(10*scale)):
                painter.setPen(pen100 if y % int(100*scale) == 0 else pen10)
                painter.drawLine(left, y, right, y)
        
        self.puzzle_canvas.drawBackground = draw_grid
        
        # Enable wheel zoom
        self.puzzle_canvas.wheelEvent = getattr(self, '_puzzle_wheel_zoom', lambda ev: None)
        
        self.puzzle_container = QWidget()
        puzzle_layout = QVBoxLayout(self.puzzle_container)
        puzzle_layout.setContentsMargins(0, 0, 0, 0)
        puzzle_layout.setSpacing(0)
        
        self.puzzle_tb = QHBoxLayout()
        self.puzzle_tb.setContentsMargins(10, 5, 10, 5)
        
        self.collision_cb = QCheckBox(" Уникати зіткнень деталей (Колізії)")
        self.collision_cb.setStyleSheet("QCheckBox { color: #ccc; font-weight: bold; }")
        self.puzzle_tb.addWidget(self.collision_cb)
        self.puzzle_tb.addStretch()
        
        puzzle_layout.addLayout(self.puzzle_tb)
        puzzle_layout.addWidget(self.puzzle_canvas, stretch=1)
        
        self.view_split.addWidget(self.puzzle_container)
        self.view_split.setSizes([1000, 1000])
        right_layout.addWidget(self.view_split, stretch=1)
        # за замовчуванням (режим Генерація) показуємо лише 3D
        self.puzzle_container.setVisible(False)

        # Toolbox panel
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

        self.toolbox_list = ToolboxListWidget()
        self.toolbox_list.setFlow(QListWidget.LeftToRight)
        self.toolbox_list.setWrapping(True)
        self.toolbox_list.setFixedHeight(120)
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
        self.toolbox_frame.setVisible(False)
        right_layout.addWidget(self.toolbox_frame)

        self.selected_placed_idx = -1
        self._dragging = False
        self._drag_start_pos = None

        self.apply_ui_layout()
        
        self.connect_dirty_signals()
        
        try:
            self.load_auto_settings()
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        try:
            if hasattr(self, 'refresh_bookmarks'):
                self.refresh_bookmarks()
        except Exception as e:
            print(f"Error refreshing bookmarks: {e}")
        
        if hasattr(self, 'generate_box'):
            try:
                self.generate_box()
            except Exception as e:
                print(f"Error in initial generate_box: {e}")

        # Форсуємо відмальовування
        central_widget.show()
        self.centralWidget().update()

        if hasattr(self, 'get_preset_dict'):
            self.last_state = self.get_preset_dict()
        else:
            self.last_state = {}
        
        QShortcut(QKeySequence("Ctrl+Z"), self, getattr(self, 'undo', lambda: None))
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, getattr(self, 'redo', lambda: None))
        QShortcut(QKeySequence(Qt.Key_Delete), self, getattr(self, 'on_delete_key', lambda: None))
        QShortcut(QKeySequence(Qt.Key_Backspace), self, getattr(self, 'on_delete_key', lambda: None))
        QShortcut(QKeySequence("Ctrl+R"), self, getattr(self, 'next_rotation_step', lambda: None))
        QShortcut(QKeySequence("Ctrl+G"), self, getattr(self, 'group_selected_items', lambda: None))
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, getattr(self, 'ungroup_selected_items', lambda: None))

    def update_ruler_mode(self):
        active = self.ruler_btn.isChecked()
        if not active:
            # Cleanup ruler items
            if hasattr(self, '_ruler_items'):
                for it in self._ruler_items:
                    try: self.view.removeItem(it)
                    except: pass
                self._ruler_items = []
            self._ruler_points = []
            self.statusBar().showMessage("Режим лінійки вимкнено")
        else:
            self.statusBar().showMessage("📐 Лінійка: Клікніть у двох точках на моделі для вимірювання. ПКМ для скидання.")
            if self.pan_btn.isChecked():
                self.pan_btn.setChecked(False)

    def switch_mode(self):
        is_assembly = self.mode_assem_btn.isChecked()
        self.preset_box.toggle_button.setText(" Папки (Збирання)" if is_assembly else " Пресети (Закладки)")
        self.dim_box.setVisible(not is_assembly)
        self.tab_box.setVisible(not is_assembly)
        self.sides_box.setVisible(not is_assembly)
        self.bed_box.setVisible(not is_assembly)
        self.assembly_box.setVisible(is_assembly)
        if hasattr(self, 'grid_box'):
            self.grid_box.setVisible(is_assembly)
        if hasattr(self, 'cell_box') and not is_assembly:
            self.cell_box.setVisible(False)        # показується лише на 2-клік по комірці
        self.toolbox_frame.setVisible(is_assembly)
        if is_assembly:
            if hasattr(self, 'populate_toolbox'): self.populate_toolbox()
            if hasattr(self, 'install_assembly_mouse_handlers'): self.install_assembly_mouse_handlers()
            self.puzzle_mode_btn.setChecked(True)
            self.on_assem_submode_changed(self.puzzle_mode_btn)
            self.statusBar().showMessage("Режим конструктора: перетягуйте коробки мишкою", 5000)
        else:
            if hasattr(self, 'uninstall_assembly_mouse_handlers'): self.uninstall_assembly_mouse_handlers()
            self.statusBar().clearMessage()
            self._set_view_mode('3d')
        if hasattr(self, 'generate_box'): self.generate_box()

    def _set_view_mode(self, mode):
        """mode: '2d' | '3d' | 'split' — керує видимістю 2D-пазла та 3D-в'юпорта."""
        if not hasattr(self, 'view_split'):
            return
        self.view_container.setVisible(mode in ('3d', 'split'))
        self.puzzle_container.setVisible(mode in ('2d', 'split'))
        if mode == 'split':
            total = max(self.view_split.width(), 800)
            self.view_split.setSizes([total // 2, total // 2])

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

        self.sides_grid.setHorizontalSpacing(10)
        self.sides_grid.setVerticalSpacing(8)

    def connect_dirty_signals(self):
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
        if not getattr(self, '_suppress_history', False) and not self.regen_timer.isActive():
            if hasattr(self, 'last_state'): self.undo_stack.append(self.last_state)
            self.redo_stack.clear()
            if len(self.undo_stack) > self.max_history:
                self.undo_stack.pop(0)

        self.save_auto_settings()
        
        # Оновити last_state відразу, щоб наступний mark_dirty міг його захопити
        if hasattr(self, 'get_preset_dict'):
            self.last_state = self.get_preset_dict()
            
        self.regen_timer.start(500)
        
        if self.sender() in [self.bed_x_input, self.bed_y_input]:
            self.update_grid()

    def save_auto_settings(self):
        import json
        settings = QSettings("KasNew", "BoxGenerator")
        if hasattr(self, 'get_preset_dict'):
            data = self.get_preset_dict()
            # Додаємо поточний режим
            if hasattr(self, 'mode_assem_btn'):
                data["app_mode"] = "assembly" if self.mode_assem_btn.isChecked() else "generation"
            
            for key, val in data.items():
                if isinstance(val, (list, dict)):
                    # Серіалізуємо списки та словники для стабільності QSettings
                    settings.setValue(key, json.dumps(val))
                else:
                    settings.setValue(key, val)

    def load_auto_settings(self):
        import json
        settings = QSettings("KasNew", "BoxGenerator")
        if not settings.allKeys():
            # Якщо налаштувань немає, ставимо дефолтний режим "Збирання"
            if hasattr(self, 'mode_assem_btn'):
                self.mode_assem_btn.setChecked(True)
                self.switch_mode()
            return
        
        data = {}
        for key in settings.allKeys():
            val = settings.value(key)
            # Спробуємо десеріалізувати JSON
            if isinstance(val, str) and (val.startswith('[') or val.startswith('{')):
                try:
                    val = json.loads(val)
                except: pass
            data[key] = val
            
        if hasattr(self, 'set_preset_dict'): 
            self.set_preset_dict(data)
            
        # Відновлення режиму
        if "app_mode" in data:
            if data["app_mode"] == "assembly":
                self.mode_assem_btn.setChecked(True)
            else:
                self.mode_gen_btn.setChecked(True)
            self.switch_mode()
        else:
            # Дефолт якщо режим не збережено
            self.mode_assem_btn.setChecked(True)
            self.switch_mode()

    def update_grid(self):
        try:
            is_assembly = hasattr(self, 'mode_assem_btn') and self.mode_assem_btn.isChecked()
            
            if is_assembly:
                self.grid.show()
                if hasattr(self, 'update_adaptive_grid'): self.update_adaptive_grid()
                self.grid_lid.hide()
                return

            bx = self.bed_x_input.value()
            by = self.bed_y_input.value()
            L = self.len_input.value()
            t_d = self.tab_depth_input.value()
            
            self.grid.setSize(x=bx, y=by, z=0)
            self.grid.setSpacing(x=10, y=10, z=0)
            
            if self.generate_lid_cb.isChecked() and not getattr(self, 'is_single_bed', False):
                self.grid_lid.show()
                self.grid_lid.setSize(x=bx, y=by, z=0)
                self.grid_lid.setSpacing(x=10, y=10, z=0)
                
                self.grid_lid.resetTransform()
                self.grid_lid.translate(getattr(self, 'current_lid_offset_x', 0.0), 0, -0.1)
            else:
                self.grid_lid.hide()
                
        except ValueError:
            pass
