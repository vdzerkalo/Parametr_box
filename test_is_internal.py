def is_internal(compound_parts, my_rel_x, my_rel_y, tx, ty):
    for p in compound_parts:
        if p["rel_x"] == my_rel_x and -p["rel_y"] == my_rel_y: 
            continue
        o_d = p["data"]
        o_rx = p["rel_x"]
        o_ry = -p["rel_y"]
        o_L = o_d.get("length", 100)
        o_W = o_d.get("width",  100)
        if (o_rx - o_L/2 <= tx <= o_rx + o_L/2) and (o_ry - o_W/2 <= ty <= o_ry + o_W/2):
            return True
    return False

compound_parts = [
    { "rel_x": 0.0, "rel_y": 0.0, "data": { "length": 50, "width": 100 } },
    { "rel_x": 50.0, "rel_y": 0.0, "data": { "length": 50, "width": 100 } }
]

tx = 0.0 + 50/2 + 1.0  # right side of part 0, pushed 1mm right -> x=26
ty = 0.0               # center offset 0
print(is_internal(compound_parts, 0.0, 0.0, tx, ty))
