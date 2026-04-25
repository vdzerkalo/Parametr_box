import cadquery as cq

b1 = cq.Workplane("XY").box(20, 20, 20).translate((0, 0, 10))
b2 = cq.Workplane("XY").box(20, 20, 20).translate((20, 0, 10))

u1 = b1.union(b2, glue=True)
print("glue=True faces:", len(u1.faces().vals()))

u2 = b1.union(b2, glue=False)
print("glue=False faces:", len(u2.faces().vals()))

u3 = b1.union(b2, clean=True)
print("clean=True faces:", len(u3.faces().vals()))

b2_overlap = cq.Workplane("XY").box(20.002, 20, 20).translate((20, 0, 10))
u4 = b1.union(b2_overlap)
print("overlap faces:", len(u4.faces().vals()))

cq.exporters.export(u1, "u1.step")
cq.exporters.export(u2, "u2.step")
cq.exporters.export(u3, "u3.step")
cq.exporters.export(u4, "u4.step")
