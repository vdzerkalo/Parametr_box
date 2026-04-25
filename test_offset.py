import sys
sys.path.append('.')
from box_generator import BoxGeneratorApp
from PySide6.QtWidgets import QApplication
import cadquery as cq

app = QApplication(sys.argv)
win = BoxGeneratorApp()

try:
    # Set to some basic params
    L, W, H = 50, 50, 10
    tw_b, tw_t, t_d = 10, 15, 5
    clear = 0.3
    fillet = 1.0
    modes = (0, 1, 1, 0)
    
    lid_tol = 0.5
    lid_h = 5
    
    print("Generating main box...")
    main_box = win.create_box_geometry(L, W, H, tw_b, tw_t, t_d, clear, fillet, modes)
    
    print("Extracting bottom wire...")
    # Get the bottom face wire
    bottom_wire = main_box.faces("<Z").wires().val()
    
    print("Offsetting wire...")
    lid_wp = cq.Workplane("XY").add(bottom_wire).toPending().offset2D(-lid_tol, kind='intersection')
    
    print("Extruding lid...")
    lid_box = lid_wp.extrude(lid_h)
    
    print("Success. Lid solid is valid.")
    print("Volume:", lid_box.val().Volume())
except Exception as e:
    import traceback
    traceback.print_exc()

