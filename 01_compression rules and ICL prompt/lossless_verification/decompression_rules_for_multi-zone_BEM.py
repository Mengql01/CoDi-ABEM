import re

# Vertex index mapping rules (based on cube vertex order)
vertex_rules = {
    'b': [0, 1, 2, 3],  # Bottom surface
    't': [7, 6, 5, 4],  # Top surface
    'w': [1, 0, 4, 5],  # West wall
    'e': [6, 7, 3, 2],  # East wall
    's': [0, 3, 7, 4],  # South wall
    'n': [2, 1, 5, 6]  # North wall
}

# Default parameters for types
type_defaults = {
    'GROUND_FLOOR': {'boundary_cond': 'Ground', 'sun': False, 'wind': False},
    'EXT_ROOF': {'boundary_cond': 'Outdoors'},
    'EXT_WALL': {'boundary_cond': 'Outdoors'},
    'ADJ_WALL': {'boundary_cond': 'Zone', 'sun': False, 'wind': False},
    'ADJ_CEILING': {'boundary_cond': 'Zone', 'sun': False, 'wind': False},
    'EXT_WINDOW1': {}
}


def generate_building(zones):
    """
    Generate IDF format text for multi-zone building.
    """
    output = ""

    for zone_name, vertices, *surface_defs in zones:
        output += _generate_zone_output(zone_name, vertices, surface_defs) + "\n"

    return output.strip()


def _generate_zone_output(zone_name, vertices, surface_defs):
    """
    Generate IDF format text for a single zone
    """
    surfaces = []
    fenestration = []

    for def_item in surface_defs:
        parts = [p.strip() for p in def_item.split(',', 3)]
        surface_id = parts[0]
        cons_type = parts[1]

        # If it's a regular surface
        if cons_type in ['GROUND_FLOOR', 'EXT_ROOF', 'EXT_WALL', 'ADJ_WALL', 'ADJ_CEILING']:
            combined_str = ",".join(parts[2:]) if len(parts) > 2 else ""
            position = None
            boundary_obj = None

            # Parse parameters
            for p in combined_str.split(','):
                p = p.strip()
                if p in vertex_rules:
                    position = p
                elif p.startswith('zone'):
                    boundary_obj = p

            # Default position is the bottom surface (b)
            position = position or 'b'
            if position not in vertex_rules:
                raise ValueError(f"Invalid position: {position}")

            # Get vertices and construct the surface
            selected_vertices = [vertices[i] for i in vertex_rules[position]]
            surface = {
                'id': surface_id,
                'construction': cons_type,
                'vertices': selected_vertices,
                'boundary_obj': boundary_obj or '',
                'position': position
            }
            surface.update(type_defaults[cons_type])
            surfaces.append(surface)

        # If it's a window (EXT_WINDOW1), append to the list
        elif cons_type == 'EXT_WINDOW1':
            parent_surface = parts[2]
            vertices_str = parts[3]
            window_vertices = [
                tuple(map(float, v.strip('()').split(',')))
                for v in re.findall(r'\([^)]+\)', vertices_str)
            ]
            fenestration.append({
                'id': surface_id,
                'construction': cons_type,
                'parent_surface': parent_surface,
                'vertices': window_vertices
            })

    return _generate_output(zone_name, surfaces, fenestration)


def _generate_output(zone_name, surfaces, fenestration):
    """
    Generate the final IDF text for a single zone
    """
    zone_template = f"""  Zone,
    {zone_name},  !- Name
    0.0,  !- Direction of Relative North {{deg}}
    0.0,  !- X Origin {{m}}
    0.0,  !- Y Origin {{m}}
    0.0,  !- Z Origin {{m}}
    ,  !- ZONE_TYPE
    1;  !- Multiplier

"""

    def build_surface(s):
        vertices_str = ""
        num_verts = len(s['vertices'])
        for i, v in enumerate(s['vertices'], 1):
            x, y, z = v
            terminator = ";" if i == num_verts else ","
            vertices_str += f"""    {x:.3f},  !- Vertex {i} X-coordinate {{m}}
    {y:.3f},  !- Vertex {i} Y-coordinate {{m}}
    {z:.3f}{terminator}  !- Vertex {i} Z-coordinate {{m}}
"""
        boundary_obj_str = (
            s['boundary_obj'] + ","
            if s['boundary_obj'] and s['construction'] != 'GROUND_FLOOR'
            else "BOUNDARY=INPUT 1*TGROUND,"
            if s['construction'] == 'GROUND_FLOOR'
            else ","
        )
        surface_type = _get_surface_type(s['construction'], s['position'])

        return f"""  BuildingSurface:Detailed,
    {s['id']},  !- Name
    {surface_type},  !- Surface Type
    {s['construction']},  !- Construction Name
    {zone_name},  !- Zone Name
    {s['boundary_cond']},  !- Outside Boundary Condition
    {boundary_obj_str}  !- Outside Boundary Condition Object
    {'SunExposed' if s.get('sun', True) else 'NoSun'},  !- Sun Exposure
    {'WindExposed' if s.get('wind', True) else 'NoWind'},  !- Wind Exposure
    ,  !- TRNSYS 17 - additional surface data
    {num_verts},  !- Number of Vertices
{vertices_str.rstrip()}

"""

    def build_fenestration(f):
        vertices_str = ""
        num_verts = len(f['vertices'])
        for i, v in enumerate(f['vertices'], 1):
            x, y, z = v
            terminator = ";" if i == num_verts else ","
            vertices_str += f"""    {x:.3f},  !- Vertex {i} X-coordinate {{m}}
    {y:.3f},  !- Vertex {i} Y-coordinate {{m}}
    {z:.3f}{terminator}  !- Vertex {i} Z-coordinate {{m}}
"""
        return f"""  FenestrationSurface:Detailed,
    {f['id']},  !- Name
    Window,  !- Surface Type
    {f['construction']},  !- Construction Name
    {f['parent_surface']},  !- Building Surface Name
    ,  !- Outside Boundary Condition Object
    ,  !- TRNSYS 17 - additional surface data
    ,  !- Shading Control Name
    ,  !- Frame and Divider Name
    ,  !- Multiplier
    {num_verts},  !- Number of Vertices
{vertices_str.rstrip()}

"""

    def _get_surface_type(cons, position=None):
        if cons == 'GROUND_FLOOR':
            return 'Floor'
        if cons == 'EXT_ROOF':
            return 'Roof'
        if cons == 'ADJ_CEILING':
            return 'Ceiling' if position == 't' else 'Floor'
        return 'Wall'

    output = zone_template
    for s in surfaces:
        output += build_surface(s)

    # Traverse all windows and generate
    for f in fenestration:
        output += build_fenestration(f)

    return output


# ---- Test example ----
if __name__ == "__main__":
    zones = [

        ("zone01",
         [(0, 0, 0), (0, 5.9, 0), (10.6, 5.9, 0), (10.6, 0, 0), (0, 0, 7.5), (0, 5.9, 7.5), (10.6, 5.9, 7.5), (10.6, 0, 7.5)],
         "s1_b, GROUND_FLOOR, b",
         "s1_t, ADJ_CEILING, t, zone06",
         "s1_e, ADJ_WALL, e, zone02",
         "s1_w, EXT_WALL, w",
         "s1_n, EXT_WALL, n",
         "s1_s, EXT_WALL, s",
         "s1_1, EXT_WINDOW1, s1_s, (0.3,0,3.05), (0.3,0,1.25), (2.2,0,1.25), (2.2,0,3.05)",
         "s1_2, EXT_WINDOW1, s1_s, (3.1,0,3.05), (3.1,0,1.25), (5.0,0,1.25), (5.0,0,3.05)",
         "s1_3, EXT_WINDOW1, s1_n, (0.3,5.9,1.25), (0.3,5.9,3.75), (2.7,5.9,3.75), (2.7,5.9,1.25)",
         "s1_4, EXT_WINDOW1, s1_n, (3.3,5.9,1.25), (3.3,5.9,3.75), (5.7,5.9,3.75), (5.7,5.9,1.25)"
         ),
        ("zone02",
         [(10.6, 0, 0), (10.6, 5.9, 0), (21.5, 5.9, 0), (21.5, 0, 0), (10.6, 0, 7.5), (10.6, 5.9, 7.5), (21.5, 5.9, 7.5), (21.5, 0, 7.5)],
         "s2_b, GROUND_FLOOR, b",
         "s2_t, ADJ_CEILING, t, zone07",
         "s2_e, ADJ_WALL, e, zone03",
         "s2_w, ADJ_WALL, w, zone01",
         "s2_n, EXT_WALL, n",
         "s2_s, EXT_WALL, s",
         "s2_1, EXT_WINDOW1, s2_s, (10.9,0,3.05), (10.9,0,1.25), (12.8,0,1.25), (12.8,0,3.05)",
         "s2_2, EXT_WINDOW1, s2_s, (13.7,0,3.05), (13.7,0,1.25), (15.6,0,1.25), (15.6,0,3.05)",
         "s2_3, EXT_WINDOW1, s2_n, (10.9,5.9,1.25), (10.9,5.9,3.75), (13.3,5.9,3.75), (13.3,5.9,1.25)",
         "s2_4, EXT_WINDOW1, s2_n, (13.9,5.9,1.25), (13.9,5.9,3.75), (16.3,5.9,3.75), (16.3,5.9,1.25)"
         ),
        ("zone03",
         [(21.5, 0, 0), (21.5, 5.9, 0), (29.6, 5.9, 0), (29.6, 0, 0), (21.5, 0, 7.5), (21.5, 5.9, 7.5), (29.6, 5.9, 7.5), (29.6, 0, 7.5)],
         "s3_b, GROUND_FLOOR, b",
         "s3_t, ADJ_CEILING, t, zone08",
         "s3_e, ADJ_WALL, e, zone04",
         "s3_w, ADJ_WALL, w, zone02",
         "s3_n, EXT_WALL, n",
         "s3_s, EXT_WALL, s",
         "s3_1, EXT_WINDOW1, s3_s, (21.8,0,3.05), (21.8,0,1.25), (23.7,0,1.25), (23.7,0,3.05)",
         "s3_2, EXT_WINDOW1, s3_s, (24.6,0,3.05), (24.6,0,1.25), (26.5,0,1.25), (26.5,0,3.05)",
         "s3_3, EXT_WINDOW1, s3_n, (21.8,5.9,1.25), (21.8,5.9,3.75), (24.2,5.9,3.75), (24.2,5.9,1.25)",
         "s3_4, EXT_WINDOW1, s3_n, (24.8,5.9,1.25), (24.8,5.9,3.75), (27.2,5.9,3.75), (27.2,5.9,1.25)"
         ),
        ("zone04",
         [(29.6, 0, 0), (29.6, 5.9, 0), (41.0, 5.9, 0), (41.0, 0, 0), (29.6, 0, 7.5), (29.6, 5.9, 7.5), (41.0, 5.9, 7.5), (41.0, 0, 7.5)],
         "s4_b, GROUND_FLOOR, b",
         "s4_t, ADJ_CEILING, t, zone09",
         "s4_e, ADJ_WALL, e, zone05",
         "s4_w, ADJ_WALL, w, zone03",
         "s4_n, EXT_WALL, n",
         "s4_s, EXT_WALL, s",
         "s4_1, EXT_WINDOW1, s4_s, (29.9,0,3.05), (29.9,0,1.25), (31.8,0,1.25), (31.8,0,3.05)",
         "s4_2, EXT_WINDOW1, s4_s, (32.7,0,3.05), (32.7,0,1.25), (34.6,0,1.25), (34.6,0,3.05)",
         "s4_3, EXT_WINDOW1, s4_n, (29.9,5.9,1.25), (29.9,5.9,3.75), (32.3,5.9,3.75), (32.3,5.9,1.25)",
         "s4_4, EXT_WINDOW1, s4_n, (33.1,5.9,1.25), (33.1,5.9,3.75), (35.5,5.9,3.75), (35.5,5.9,1.25)"
         ),
        ("zone05",
         [(41.0, 0, 0), (41.0, 5.9, 0), (49.5, 5.9, 0), (49.5, 0, 0), (41.0, 0, 7.5), (41.0, 5.9, 7.5), (49.5, 5.9, 7.5), (49.5, 0, 7.5)],
         "s5_b, GROUND_FLOOR, b",
         "s5_t, ADJ_CEILING, t, zone10",
         "s5_e, EXT_WALL, e",
         "s5_w, ADJ_WALL, w, zone04",
         "s5_n, EXT_WALL, n",
         "s5_s, EXT_WALL, s",
         "s5_1, EXT_WINDOW1, s5_s, (41.3,0,3.05), (41.3,0,1.25), (43.2,0,1.25), (43.2,0,3.05)",
         "s5_2, EXT_WINDOW1, s5_s, (44.1,0,3.05), (44.1,0,1.25), (46.0,0,1.25), (46.0,0,3.05)",
         "s5_3, EXT_WINDOW1, s5_n, (41.3,5.9,1.25), (41.3,5.9,3.75), (43.7,5.9,3.75), (43.7,5.9,1.25)",
         "s5_4, EXT_WINDOW1, s5_n, (44.3,5.9,1.25), (44.3,5.9,3.75), (46.7,5.9,3.75), (46.7,5.9,1.25)"
         ),
        ("zone06",
         [(0, 0, 7.5), (0, 5.9, 7.5), (10.6, 5.9, 7.5), (10.6, 0, 7.5), (0, 0, 15), (0, 5.9, 15), (10.6, 5.9, 15), (10.6, 0, 15)],
         "s6_b, ADJ_CEILING, b, zone01",
         "s6_t, EXT_ROOF, t",
         "s6_e, ADJ_WALL, e, zone07",
         "s6_w, EXT_WALL, w",
         "s6_n, EXT_WALL, n",
         "s6_s, EXT_WALL, s",
         "s6_1, EXT_WINDOW1, s6_s, (0.3,0,10.55), (0.3,0,8.75), (2.2,0,8.75), (2.2,0,10.55)",
         "s6_2, EXT_WINDOW1, s6_s, (3.1,0,10.55), (3.1,0,8.75), (5.0,0,8.75), (5.0,0,10.55)",
         "s6_3, EXT_WINDOW1, s6_n, (0.3,5.9,8.75), (0.3,5.9,11.25), (2.7,5.9,11.25), (2.7,5.9,8.75)",
         "s6_4, EXT_WINDOW1, s6_n, (3.3,5.9,8.75), (3.3,5.9,11.25), (5.7,5.9,11.25), (5.7,5.9,8.75)"
         ),
        ("zone07",
         [(10.6, 0, 7.5), (10.6, 5.9, 7.5), (21.5, 5.9, 7.5), (21.5, 0, 7.5), (10.6, 0, 15), (10.6, 5.9, 15), (21.5, 5.9, 15), (21.5, 0, 15)],
         "s7_b, ADJ_CEILING, b, zone02",
         "s7_t, EXT_ROOF, t",
         "s7_e, ADJ_WALL, e, zone08",
         "s7_w, ADJ_WALL, w, zone06",
         "s7_n, EXT_WALL, n",
         "s7_s, EXT_WALL, s",
         "s7_1, EXT_WINDOW1, s7_s, (10.9,0,10.55), (10.9,0,8.75), (12.8,0,8.75), (12.8,0,10.55)",
         "s7_2, EXT_WINDOW1, s7_s, (13.7,0,10.55), (13.7,0,8.75), (15.6,0,8.75), (15.6,0,10.55)",
         "s7_3, EXT_WINDOW1, s7_n, (10.9,5.9,8.75), (10.9,5.9,11.25), (13.3,5.9,11.25), (13.3,5.9,8.75)",
         "s7_4, EXT_WINDOW1, s7_n, (13.9,5.9,8.75), (13.9,5.9,11.25), (16.3,5.9,11.25), (16.3,5.9,8.75)"
         ),
        ("zone08",
         [(21.5, 0, 7.5), (21.5, 5.9, 7.5), (29.6, 5.9, 7.5), (29.6, 0, 7.5), (21.5, 0, 15), (21.5, 5.9, 15), (29.6, 5.9, 15), (29.6, 0, 15)],
         "s8_b, ADJ_CEILING, b, zone03",
         "s8_t, EXT_ROOF, t",
         "s8_e, ADJ_WALL, e, zone09",
         "s8_w, ADJ_WALL, w, zone07",
         "s8_n, EXT_WALL, n",
         "s8_s, EXT_WALL, s",
         "s8_1, EXT_WINDOW1, s8_s, (21.8,0,10.55), (21.8,0,8.75), (23.7,0,8.75), (23.7,0,10.55)",
         "s8_2, EXT_WINDOW1, s8_s, (24.6,0,10.55), (24.6,0,8.75), (26.5,0,8.75), (26.5,0,10.55)",
         "s8_3, EXT_WINDOW1, s8_n, (21.8,5.9,8.75), (21.8,5.9,11.25), (24.2,5.9,11.25), (24.2,5.9,8.75)",
         "s8_4, EXT_WINDOW1, s8_n, (24.8,5.9,8.75), (24.8,5.9,11.25), (27.2,5.9,11.25), (27.2,5.9,8.75)"
         ),
        ("zone09",
         [(29.6, 0, 7.5), (29.6, 5.9, 7.5), (41.0, 5.9, 7.5), (41.0, 0, 7.5), (29.6, 0, 15), (29.6, 5.9, 15), (41.0, 5.9, 15), (41.0, 0, 15)],
         "s9_b, ADJ_CEILING, b, zone04",
         "s9_t, EXT_ROOF, t",
         "s9_e, ADJ_WALL, e, zone10",
         "s9_w, ADJ_WALL, w, zone08",
         "s9_n, EXT_WALL, n",
         "s9_s, EXT_WALL, s",
         "s9_1, EXT_WINDOW1, s9_s, (29.9,0,10.55), (29.9,0,8.75), (31.8,0,8.75), (31.8,0,10.55)",
         "s9_2, EXT_WINDOW1, s9_s, (32.7,0,10.55), (32.7,0,8.75), (34.6,0,8.75), (34.6,0,10.55)",
         "s9_3, EXT_WINDOW1, s9_n, (29.9,5.9,8.75), (29.9,5.9,11.25), (32.3,5.9,11.25), (32.3,5.9,8.75)",
         "s9_4, EXT_WINDOW1, s9_n, (33.1,5.9,8.75), (33.1,5.9,11.25), (35.5,5.9,11.25), (35.5,5.9,8.75)"
         ),
        ("zone10",
         [(41.0, 0, 7.5), (41.0, 5.9, 7.5), (49.5, 5.9, 7.5), (49.5, 0, 7.5), (41.0, 0, 15), (41.0, 5.9, 15), (49.5, 5.9, 15), (49.5, 0, 15)],
         "s10_b, ADJ_CEILING, b, zone05",
         "s10_t, EXT_ROOF, t",
         "s10_e, EXT_WALL, e",
         "s10_w, ADJ_WALL, w, zone09",
         "s10_n, EXT_WALL, n",
         "s10_s, EXT_WALL, s",
         "s10_1, EXT_WINDOW1, s10_s, (41.3,0,10.55), (41.3,0,8.75), (43.2,0,8.75), (43.2,0,10.55)",
         "s10_2, EXT_WINDOW1, s10_s, (44.1,0,10.55), (44.1,0,8.75), (46.0,0,8.75), (46.0,0,10.55)",
         "s10_3, EXT_WINDOW1, s10_n, (41.3,5.9,8.75), (41.3,5.9,11.25), (43.7,5.9,11.25), (43.7,5.9,8.75)",
         "s10_4, EXT_WINDOW1, s10_n, (44.3,5.9,8.75), (44.3,5.9,11.25), (46.7,5.9,11.25), (46.7,5.9,8.75)"
         )

    ]

    output = generate_building(zones)
    print(output)