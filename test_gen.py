import json
import sys
from PySide6.QtWidgets import QApplication
from app import BoxGeneratorApp

app_qt = QApplication(sys.argv)
app = BoxGeneratorApp()
import json
with open("my_assembly3.json", "r") as f:
    data = json.load(f)
app.placed_items = data.get("placed_items", [])

try:
    shapes = app._generate_assembly_from_params({"placed_items": app.placed_items})
    print("Number of compound items generated:", sum(1 for item in app.placed_items if item.get("type") == "compound"))
    from mesh_engine import MeshData
    meshes = [s for s, c in shapes]
    combined = MeshData.combine(meshes)
    print(f"Total verts: {len(combined.verts)}, faces: {len(combined.faces)}")
except Exception as e:
    import traceback
    traceback.print_exc()
