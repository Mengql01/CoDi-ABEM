"""
compression_rules_for_multi-zone_BEM.py
========================================
Compression program for multi-zone BEM IDF files.
This is the exact inverse of the decompression program (decompression_rules_for_multi-zone_BEM.py).

Usage:
    Place this file in the SAME directory as decompression_rules_for_multi-zone_BEM.py,
    then run:  python compression_rules_for_multi-zone_BEM.py

Round-trip verification workflow:
    Compressed representation
      -> [decompression_rules_for_multi-zone_BEM.py] -> Full IDF file
      -> [compression_rules_for_multi-zone_BEM.py]   -> Reconstructed compressed representation
      -> [decompression_rules_for_multi-zone_BEM.py] -> Reconstructed IDF file
      -> Character-by-character comparison with original IDF
"""

import re
import os
import sys


# Vertex index mapping rules (identical to the decompression code)
vertex_rules = {
    'b': [0, 1, 2, 3],  # Bottom surface
    't': [7, 6, 5, 4],  # Top surface
    'w': [1, 0, 4, 5],  # West wall
    'e': [6, 7, 3, 2],  # East wall
    's': [0, 3, 7, 4],  # South wall
    'n': [2, 1, 5, 6]   # North wall
}


def parse_idf_text(idf_text):
    """
    Parse IDF text and extract Zone, BuildingSurface:Detailed,
    and FenestrationSurface:Detailed blocks.
    """
    zones = []
    surfaces = []
    fenestrations = []

    blocks = re.split(r'\n\s*\n', idf_text.strip())

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith('Zone,'):
            zones.append(parse_zone_block(block))
        elif block.startswith('BuildingSurface:Detailed,'):
            surfaces.append(parse_surface_block(block))
        elif block.startswith('FenestrationSurface:Detailed,'):
            fenestrations.append(parse_fenestration_block(block))

    return zones, surfaces, fenestrations


def parse_zone_block(block):
    """Parse a Zone block and extract the zone name."""
    lines = block.strip().split('\n')
    name_line = lines[1].strip()
    name = name_line.split(',')[0].strip()
    return {'name': name}


def parse_surface_block(block):
    """Parse a BuildingSurface:Detailed block."""
    lines = block.strip().split('\n')
    fields = []
    for line in lines[1:]:
        value = line.split('!-')[0].strip().rstrip(',').rstrip(';')
        fields.append(value)

    surface = {
        'name': fields[0],
        'surface_type': fields[1],
        'construction': fields[2],
        'zone_name': fields[3],
        'boundary_cond': fields[4],
        'boundary_obj': fields[5],
        'sun_exposure': fields[6],
        'wind_exposure': fields[7],
        'trnsys_data': fields[8],
        'num_vertices': int(fields[9]),
        'vertices': []
    }

    idx = 10
    for i in range(surface['num_vertices']):
        x = float(fields[idx])
        y = float(fields[idx + 1])
        z = float(fields[idx + 2])
        surface['vertices'].append((x, y, z))
        idx += 3

    return surface


def parse_fenestration_block(block):
    """Parse a FenestrationSurface:Detailed block."""
    lines = block.strip().split('\n')
    fields = []
    for line in lines[1:]:
        value = line.split('!-')[0].strip().rstrip(',').rstrip(';')
        fields.append(value)

    fen = {
        'name': fields[0],
        'surface_type': fields[1],
        'construction': fields[2],
        'parent_surface': fields[3],
        'boundary_obj': fields[4],
        'trnsys_data': fields[5],
        'shading_control': fields[6],
        'frame_divider': fields[7],
        'multiplier': fields[8],
        'num_vertices': int(fields[9]),
        'vertices': []
    }

    idx = 10
    for i in range(fen['num_vertices']):
        x = float(fields[idx])
        y = float(fields[idx + 1])
        z = float(fields[idx + 2])
        fen['vertices'].append((x, y, z))
        idx += 3

    return fen


def determine_position(surface_vertices, cuboid_vertices):
    """
    Given the 4 vertices of a surface and the 8 cuboid vertices,
    determine which position (b/t/e/w/n/s) this surface corresponds to.
    """
    def normalize(v):
        return tuple(round(c, 3) for c in v)

    surf_verts = [normalize(v) for v in surface_vertices]
    cube_verts = [normalize(v) for v in cuboid_vertices]

    for position, indices in vertex_rules.items():
        expected = [cube_verts[i] for i in indices]
        if surf_verts == expected:
            return position

    raise ValueError(f"Cannot determine position for vertices: {surface_vertices}")


def recover_cuboid_vertices(surfaces_for_zone):
    """
    Recover the 8 cuboid vertices from the surfaces of a zone.
    Uses the bottom surface (b) and top surface (t) to get all 8 vertices.
    """
    cuboid = [None] * 8

    for surface in surfaces_for_zone:
        construction = surface['construction']
        surface_type = surface['surface_type']
        verts = surface['vertices']

        if construction == 'GROUND_FLOOR' or (construction == 'ADJ_CEILING' and surface_type == 'Floor'):
            for i, idx in enumerate(vertex_rules['b']):
                cuboid[idx] = verts[i]
        elif construction == 'EXT_ROOF' or (construction == 'ADJ_CEILING' and surface_type == 'Ceiling'):
            for i, idx in enumerate(vertex_rules['t']):
                cuboid[idx] = verts[i]

    if all(v is not None for v in cuboid):
        return cuboid

    # Fallback: fill from wall surfaces if needed
    for surface in surfaces_for_zone:
        if surface['surface_type'] == 'Wall':
            for position in ['w', 'e', 'n', 's']:
                indices = vertex_rules[position]
                expected_verts = [cuboid[i] for i in indices if cuboid[i] is not None]
                if len(expected_verts) < 4:
                    continue
                match = True
                for i, idx in enumerate(indices):
                    if cuboid[idx] is not None:
                        v1 = tuple(round(c, 3) for c in cuboid[idx])
                        v2 = tuple(round(c, 3) for c in surface['vertices'][i])
                        if v1 != v2:
                            match = False
                            break
                if match:
                    for i, idx in enumerate(indices):
                        if cuboid[idx] is None:
                            cuboid[idx] = surface['vertices'][i]

    return cuboid


def format_coord(v):
    """Format a coordinate value, removing trailing zeros."""
    if v == int(v):
        return str(int(v))
    else:
        s = f"{v:.3f}".rstrip('0').rstrip('.')
        return s


def format_vertex_tuple(v):
    """Format a vertex as a tuple string like (x,y,z)."""
    parts = [format_coord(c) for c in v]
    return f"({','.join(parts)})"


def compress_building(idf_text):
    """
    Compress IDF text back to the compressed tuple format.
    Returns a list of (zone_name, vertices_str, surface_defs).
    """
    zones, surfaces, fenestrations = parse_idf_text(idf_text)

    # Group surfaces and fenestrations by zone
    zone_surfaces = {}
    for s in surfaces:
        zone_name = s['zone_name']
        if zone_name not in zone_surfaces:
            zone_surfaces[zone_name] = []
        zone_surfaces[zone_name].append(s)

    surface_to_zone = {}
    for s in surfaces:
        surface_to_zone[s['name']] = s['zone_name']

    zone_fenestrations = {}
    for f in fenestrations:
        parent_zone = surface_to_zone.get(f['parent_surface'], '')
        if parent_zone not in zone_fenestrations:
            zone_fenestrations[parent_zone] = []
        zone_fenestrations[parent_zone].append(f)

    result_zones = []

    for zone_info in zones:
        zone_name = zone_info['name']
        zone_surfs = zone_surfaces.get(zone_name, [])

        # Recover cuboid vertices
        cuboid_vertices = recover_cuboid_vertices(zone_surfs)

        # Format vertices
        formatted_vertices = []
        for v in cuboid_vertices:
            parts = [format_coord(c) for c in v]
            formatted_vertices.append(f"({', '.join(parts)})")
        vertices_str = f"[{', '.join(formatted_vertices)}]"

        # Generate surface definitions
        surface_defs = []
        for s in zone_surfs:
            pos = determine_position(s['vertices'], cuboid_vertices)
            name = s['name']
            construction = s['construction']

            boundary_obj = s['boundary_obj'].strip()
            if boundary_obj == 'BOUNDARY=INPUT 1*TGROUND':
                boundary_obj = ''

            if construction in ['ADJ_WALL', 'ADJ_CEILING']:
                def_str = f'"{name}, {construction}, {pos}, {boundary_obj}"'
            else:
                def_str = f'"{name}, {construction}, {pos}"'

            surface_defs.append(def_str)

        # Generate fenestration definitions
        zone_fens = zone_fenestrations.get(zone_name, [])
        for f in zone_fens:
            name = f['name']
            construction = f['construction']
            parent = f['parent_surface']
            verts_strs = [format_vertex_tuple(v) for v in f['vertices']]
            verts_joined = ', '.join(verts_strs)
            def_str = f'"{name}, {construction}, {parent}, {verts_joined}"'
            surface_defs.append(def_str)

        result_zones.append((zone_name, vertices_str, surface_defs))

    return result_zones


def generate_compressed_output(result_zones):
    """
    Generate the Python source code string for the compressed zones list.
    """
    lines = []
    lines.append("    zones = [")
    lines.append("")

    for i, (zone_name, vertices_str, surface_defs) in enumerate(result_zones):
        lines.append(f'        ("{zone_name}",')
        lines.append(f'         {vertices_str},')
        for j, sd in enumerate(surface_defs):
            if j < len(surface_defs) - 1:
                lines.append(f'         {sd},')
            else:
                if i < len(result_zones) - 1:
                    lines.append(f'         {sd}')
                    lines.append(f'         ),')
                else:
                    lines.append(f'         {sd}')
                    lines.append(f'         )')
        lines.append("")

    lines.append("    ]")
    return '\n'.join(lines)


# ---- Main entry point: round-trip verification ----
if __name__ == "__main__":
    import subprocess
    import importlib.util

    # Locate the decompression script in the SAME directory as this file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    decompress_script = os.path.join(script_dir, "decompression_rules_for_multi-zone_BEM.py")

    if not os.path.exists(decompress_script):
        print(f"ERROR: Decompression script not found at: {decompress_script}")
        print(f"Please place 'decompression_rules_for_multi-zone_BEM.py' in the same directory.")
        sys.exit(1)

    # Step 1: Run the decompression code to get the IDF text
    print("Step 1: Running decompression program to generate IDF...")
    result = subprocess.run([sys.executable, decompress_script], capture_output=True, text=True)
    idf_text = result.stdout

    # Step 2: Compress the IDF text back to compressed representation
    print("Step 2: Running compression program to reconstruct compressed representation...")
    compressed_zones = compress_building(idf_text)
    compressed_output = generate_compressed_output(compressed_zones)

    print("=" * 80)
    print("COMPRESSED OUTPUT (reconstructed from IDF):")
    print("=" * 80)
    print(compressed_output)
    print()

    # Step 3: Reconstruct zones data structure and decompress again
    print("Step 3: Re-running decompression on reconstructed compressed representation...")
    reconstructed_zones = []
    for zone_name, vertices_str, surface_defs in compressed_zones:
        vertices = eval(vertices_str)
        plain_defs = [sd.strip('"') for sd in surface_defs]
        zone_tuple = (zone_name, vertices, *plain_defs)
        reconstructed_zones.append(zone_tuple)

    # Import the decompression module dynamically
    spec_obj = importlib.util.spec_from_file_location("decompress_module", decompress_script)
    decompress_module = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(decompress_module)

    # Generate IDF from reconstructed zones
    regenerated_idf = decompress_module.generate_building(reconstructed_zones)

    # Step 4: Character-by-character comparison
    print("Step 4: Performing character-by-character comparison...")
    print("=" * 80)
    print("ROUND-TRIP VERIFICATION RESULT:")
    print("=" * 80)

    original_idf = idf_text.strip()
    regenerated_idf = regenerated_idf.strip()

    if original_idf == regenerated_idf:
        print("SUCCESS: Round-trip verification PASSED!")
        print("The compression is LOSSLESS.")
        print(f"  Original IDF length:      {len(original_idf)} characters")
        print(f"  Regenerated IDF length:    {len(regenerated_idf)} characters")
        print(f"  Character-by-character match: 100%")
    else:
        print("MISMATCH detected! Analyzing differences...")
        orig_lines = original_idf.split('\n')
        regen_lines = regenerated_idf.split('\n')
        print(f"  Original lines: {len(orig_lines)}, Regenerated lines: {len(regen_lines)}")

        diff_count = 0
        for i, (o, r) in enumerate(zip(orig_lines, regen_lines)):
            if o != r:
                diff_count += 1
                if diff_count <= 10:
                    print(f"  Line {i+1}:")
                    print(f"    Original:    [{o}]")
                    print(f"    Regenerated: [{r}]")

        if len(orig_lines) != len(regen_lines):
            print(f"  Line count difference: {abs(len(orig_lines) - len(regen_lines))}")
        print(f"  Total differing lines: {diff_count}")
