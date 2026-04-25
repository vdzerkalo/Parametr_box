import cadquery as cq

box1 = cq.Workplane().box(1,1,1)
box2 = cq.Workplane().box(1,1,1).translate((2,0,0))
comp = cq.Assembly().add(box1).add(box2).toCompound()

v, f = comp.tessellate(0.2)
print("Max face index:", max([max(face) for face in f]))
print("Number of vertices:", len(v))
