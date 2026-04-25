import cadquery as cq

hw_b = 20 / 2.0
hw_t = 30 / 2.0
depth = 10.0
fillet = 2.0

# Current buggy way:
s1 = cq.Workplane("XY").sketch().polygon([
    (-hw_b, 0.0),
    (-hw_t, depth),
    (hw_t, depth),
    (hw_b, 0.0)
]).vertices().fillet(fillet).finalize().extrude(10).translate((0, 20, 0))

# Fixed way: extending base into the negative Y
s2 = cq.Workplane("XY").sketch().polygon([
    (-hw_b, -5.0), # Extended 5mm downwards
    (-hw_b, 0.0),  # We need the vertex here? If we just use 4 points, the base is at -5.0. 
    # Wait, if we use 4 points, the sides will slope from -5.0!
    # The slope should start from 0.0!
    (-hw_t, depth),
    (hw_t, depth),
    (hw_b, -5.0)
])

# Wait! If we do:
s2_poly = cq.Workplane("XY").sketch().polygon([
    (-hw_b, -5.0),
    (-hw_b, 0.0),     # start of neck
    (-hw_t, depth),   # tip
    (hw_t, depth),    # tip
    (hw_b, 0.0),      # start of neck
    (hw_b, -5.0)      # base into the box
]).vertices().fillet(fillet).finalize().extrude(10).translate((0, -20, 0))

print("Script compiled.")
