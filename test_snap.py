import sys
from PySide6.QtWidgets import QApplication

# Initialize app before importing BoxGeneratorApp to satisfy QPixmap
app = QApplication(sys.argv)
from box_generator import BoxGeneratorApp

bg = BoxGeneratorApp()

item1 = {
    "name": "Box_1",
    "x": 0, "y": 0, "rotation": 0,
    "data": {
        "length": 100, "width": 100, "height": 50,
        "side_top": 0, "side_top_count": 1,
        "side_bottom": 0, "side_bottom_count": 1,
        "side_left": 0, "side_left_count": 1,
        "side_right": 0, "side_right_count": 1
    }
}
item2 = {
    "name": "Box_2",
    "x": 0, "y": 120, "rotation": 0,
    "data": {
        "length": 100, "width": 100, "height": 50,
        "side_top": 2, "side_top_count": 0,
        "side_bottom": 2, "side_bottom_count": 0,
        "side_left": 2, "side_left_count": 0,
        "side_right": 2, "side_right_count": 0
    }
}

bg.placed_items = [item1, item2]
print("Before Top:", bg.placed_items[1]["x"], bg.placed_items[1]["y"])
bg.try_auto_snap(1)
print("After Top: ", bg.placed_items[1]["x"], bg.placed_items[1]["y"])

bg.placed_items[1]["y"] = -120 # Move to Bottom of item1
print("Before Bottom:", bg.placed_items[1]["x"], bg.placed_items[1]["y"])
bg.try_auto_snap(1)
print("After Bottom: ", bg.placed_items[1]["x"], bg.placed_items[1]["y"])
