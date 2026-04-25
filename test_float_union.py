import cadquery as cq

# Perfect match
b1 = cq.Workplane("XY").box(20, 20, 20).translate((0, 0, 10))
b2 = cq.Workplane("XY").box(20, 20, 20).translate((20, 0, 10))
u1 = b1.union(b2, glue=True)
print("Perfect match glue=True faces:", len(u1.faces().vals()))

# Tiny gap
b3 = cq.Workplane("XY").box(20, 20, 20).translate((20.00001, 0, 10))
u2 = b1.union(b3, glue=True)
print("Tiny gap glue=True faces:", len(u2.faces().vals()))

# Tiny overlap
b4 = cq.Workplane("XY").box(20, 20, 20).translate((19.99999, 0, 10))
u3 = b1.union(b4, glue=True)
print("Tiny overlap glue=True faces:", len(u3.faces().vals()))
