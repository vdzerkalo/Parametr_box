import cadquery as cq

b1 = cq.Workplane("XY").box(20, 20, 20).translate((0, 0, 10))
b3 = cq.Workplane("XY").box(20, 20, 20).translate((20.00001, 0, 10))

try:
    u2 = b1.union(b3, tol=1e-3, glue=False)
    print("Tiny gap union with tol:", len(u2.faces().vals()))
except Exception as e:
    print("Exception with tol:", e)
