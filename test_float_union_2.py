import cadquery as cq

b1 = cq.Workplane("XY").box(20, 20, 20).translate((0, 0, 10))
b3 = cq.Workplane("XY").box(20, 20, 20).translate((20.00001, 0, 10))
u2 = b1.union(b3, glue=False, clean=True)
print("Tiny gap glue=False clean=True faces:", len(u2.faces().vals()))

b4 = cq.Workplane("XY").box(20.00002, 20, 20).translate((19.99999, 0, 10))
u3 = b1.union(b4, glue=False, clean=True)
print("Tiny overlap glue=False clean=True faces:", len(u3.faces().vals()))
