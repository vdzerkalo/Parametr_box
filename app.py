import os
import sys

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QTimer

from mixins.ui_setup import UISetupMixin
from mixins.geometry import GeometryMixin
from mixins.assembly import AssemblyMixin
from mixins.bookmarks import BookmarksMixin
from mixins.grid_constructor import GridConstructorMixin

class BoxGeneratorApp(QMainWindow, UISetupMixin, GeometryMixin, AssemblyMixin, BookmarksMixin, GridConstructorMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор Коробок Вазового Режиму (Автономний)")
        
        self.current_shape = None
        self.is_single_bed = False
        self.current_lid_offset_x = 0.0
        self.assembly_decorations = []
        self.placed_items = []
        self.unplaced_items = []
        self.dimension_items = []
        
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
        
        self.regen_timer = QTimer()
        self.regen_timer.setSingleShot(True)
        self.regen_timer.timeout.connect(self.generate_box)
        
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 50
        self._suppress_history = False
        self.last_state = {}
        self.assem_submode = 'puzzle'
        
        # Rainbow animation state
        self._rainbow_phase = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_rainbow_anim)
        self.anim_timer.start(50) # 20 FPS for smoothness

        # Ініціалізуємо UI ПЕРЕД тим, як щось показувати чи завантажувати налаштування
        self.setup_ui()
        self.showMaximized()


    def _update_rainbow_anim(self):
        self._rainbow_phase = (self._rainbow_phase + 5) % 360
        # Перемальовуємо лише якщо 2D видно І вибрано елемент із райдужною рамкою
        # (сітка має статичну рамку — не вантажимо залізо її перемалюванням 20 раз/с).
        if not hasattr(self, 'puzzle_scene'):
            return
        if hasattr(self, 'puzzle_container') and not self.puzzle_container.isVisible():
            return
        sel = self.puzzle_scene.selectedItems()
        if sel and any(type(it).__name__ in ('PuzzleBoxItem', 'CompoundPuzzleItem')
                       for it in sel):
            self.puzzle_scene.update()

    def keyPressEvent(self, event):
        # Делегуємо логіку видалення та інше
        if hasattr(self, 'AssemblyMixin_keyPressEvent'):
            self.AssemblyMixin_keyPressEvent(event)
        super().keyPressEvent(event)

    def closeEvent(self, event):
        # Зберігаємо налаштування перед виходом
        if hasattr(self, 'save_auto_settings'):
            self.save_auto_settings()
        super().closeEvent(event)
