import json, sys
from app import BoxGeneratorApp
from PySide6.QtWidgets import QApplication

app_qt = QApplication(sys.argv)
app = BoxGeneratorApp()
with open("my_assembly3.json", "r") as f:
    data = json.load(f)
    app.placed_items = data.get("items", [])

shapes = app._generate_assembly_from_params({"placed_items": app.placed_items})
print("Number of compound items:", sum(1 for item in app.placed_items if item.get("type") == "compound"))

import cadquery as cq
asm = cq.Assembly()
for i, (s, c) in enumerate(shapes):
    print(f"Shape {i} faces: {len(s.faces().vals())}")
    asm.add(s, name=f"Shape_{i}")

asm.save("test_out.step", "STEP")
print("Saved test_out.step")
