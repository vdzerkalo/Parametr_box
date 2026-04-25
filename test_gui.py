import sys
from PySide6.QtWidgets import QApplication

if not QApplication.instance():
    app = QApplication(sys.argv)
from box_generator import BoxGeneratorApp

bg = BoxGeneratorApp()
bg.mode_assem_btn.setChecked(True)
bg.switch_mode()
print("Puzzle is hidden:", bg.puzzle_mode_btn.isHidden())
print("View is hidden:", bg.view_mode_btn.isHidden())
print("Unplaced is hidden:", bg.unplaced_list.isHidden())
print("Placed is hidden:", bg.placed_list.isHidden())
print("Save is hidden:", bg.save_assem_btn.isHidden())
