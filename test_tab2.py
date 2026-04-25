import cadquery as cq

base = 20.0
tip = 30.0
depth = 10.0
fillet = 2.0
hw_b = base / 2.0
hw_t = tip / 2.0

s = cq.Workplane("XY").sketch().polygon([
    (-hw_b, -10.0),
    (-hw_b, 0.0),
    (-hw_t, depth),
    (hw_t, depth),
    (hw_b, 0.0),
    (hw_b, -10.0)
])

# Try fillet
s = s.vertices().fillet(fillet)

part = s.finalize().extrude(10).translate((0, 0, -5))

box = cq.Workplane("XY").box(40, 20, 10).translate((0, -10, 0))
union = box.union(part)

print("Union faces:", len(union.faces().vals()))
cq.exporters.export(union, "union_test_tab.step")
