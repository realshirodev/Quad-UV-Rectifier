# -*- coding: utf-8 -*-
"""
Core algorithm for Quad UV Rectifier.
Handles CCW angular loop ordering, in-place rectification,
shared corner welding, and grid packing for rings/fans/overlapping quads.
"""

import math
from mathutils import Vector
from collections import defaultdict


class UnionFind:
    """Estructura Disjoint-Set para agrupar loops coincidentes en UV."""
    def __init__(self):
        self.parent = {}

    def find(self, item):
        if self.parent.setdefault(item, item) != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, item1, item2):
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 != root2:
            self.parent[root1] = root2


def angular_diff(a1, a2):
    """Calcula la distancia angular mínima en radianes entre dos ángulos."""
    d = (a1 - a2 + math.pi) % (2.0 * math.pi) - math.pi
    return abs(d)


def get_sorted_ccw_loops(face, uv_layer):
    """
    Ordena los 4 loops de una cara quad según su ángulo en sentido antihorario (CCW)
    respecto al centroide UV de la cara.
    
    Alinea cíclicamente los loops con las 4 esquinas ideales:
    - BL (Bottom-Left):  ideal -135° (-3pi/4)
    - BR (Bottom-Right): ideal  -45° (-pi/4)
    - TR (Top-Right):    ideal  +45° (+pi/4)
    - TL (Top-Left):     ideal +135° (+3pi/4)

    Retorna un diccionario: { 'BL': loop, 'BR': loop, 'TR': loop, 'TL': loop }
    Garantiza que el orden perimetral nunca se cruce (evita bowties y diagonales).
    """
    loops = list(face.loops)
    uvs = [loop[uv_layer].uv.copy() for loop in loops]

    c_u = sum(uv.x for uv in uvs) / 4.0
    c_v = sum(uv.y for uv in uvs) / 4.0

    loop_with_angle = []
    for loop in loops:
        uv = loop[uv_layer].uv
        ang = math.atan2(uv.y - c_v, uv.x - c_u)
        loop_with_angle.append((ang, loop))

    loop_with_angle.sort(key=lambda item: item[0])
    sorted_loops = [item[1] for item in loop_with_angle]
    sorted_angles = [item[0] for item in loop_with_angle]

    target_angles = [
        -0.75 * math.pi,  # BL
        -0.25 * math.pi,  # BR
         0.25 * math.pi,  # TR
         0.75 * math.pi,  # TL
    ]

    best_shift = 0
    min_cost = float('inf')
    for shift in range(4):
        cost = sum(angular_diff(sorted_angles[(i + shift) % 4], target_angles[i]) for i in range(4))
        if cost < min_cost:
            min_cost = cost
            best_shift = shift

    return {
        'BL': sorted_loops[best_shift % 4],
        'BR': sorted_loops[(best_shift + 1) % 4],
        'TR': sorted_loops[(best_shift + 2) % 4],
        'TL': sorted_loops[(best_shift + 3) % 4],
    }


def get_selected_quads(bm, uv_layer, is_sync):
    """
    Filtra de forma robusta las caras quad seleccionadas respetando UV Sync.
    Retorna (selected_quads, ignored_non_quads_count).
    """
    selected_quads = []
    ignored_count = 0

    def is_loop_selected(loop):
        if hasattr(loop, "uv_select_vert"):
            return bool(loop.uv_select_vert)
        return bool(loop[uv_layer].select)

    for face in bm.faces:
        if is_sync:
            face_sel = face.select
        else:
            face_sel = all(is_loop_selected(l) for l in face.loops)

        if face_sel:
            if len(face.loops) == 4:
                selected_quads.append(face)
            else:
                ignored_count += 1

    return selected_quads, ignored_count


def rectify_in_place(selected_quads, uv_layer, shape_mode, weld_shared, use_snap, snap_step):
    """
    Endereza cada quad en su posición actual (1:1 o rectangular).
    Opcionalmente promedia esquinas compartidas y aplica snap anti-colapso.
    """
    target_uvs = {}
    initial_uvs = {}

    for face in selected_quads:
        for loop in face.loops:
            initial_uvs[loop] = loop[uv_layer].uv.copy()

        corners = get_sorted_ccw_loops(face, uv_layer)
        uv_coords = [loop[uv_layer].uv for loop in face.loops]

        c_u = sum(uv.x for uv in uv_coords) / 4.0
        c_v = sum(uv.y for uv in uv_coords) / 4.0
        centroid = Vector((c_u, c_v))

        min_u = min(uv.x for uv in uv_coords)
        max_u = max(uv.x for uv in uv_coords)
        min_v = min(uv.y for uv in uv_coords)
        max_v = max(uv.y for uv in uv_coords)

        width = max(max_u - min_u, 1e-4)
        height = max(max_v - min_v, 1e-4)

        if shape_mode == 'SQUARE':
            avg_size = (width + height) * 0.5
            half_w = avg_size * 0.5
            half_h = avg_size * 0.5
        else:
            half_w = width * 0.5
            half_h = height * 0.5

        target_uvs[corners['BL']] = centroid + Vector((-half_w, -half_h))
        target_uvs[corners['BR']] = centroid + Vector((half_w, -half_h))
        target_uvs[corners['TR']] = centroid + Vector((half_w, half_h))
        target_uvs[corners['TL']] = centroid + Vector((-half_w, half_h))

    if weld_shared and len(selected_quads) > 1:
        loops_by_vert = defaultdict(list)
        for face in selected_quads:
            for loop in face.loops:
                loops_by_vert[loop.vert].append(loop)

        uf = UnionFind()
        for vert, loops in loops_by_vert.items():
            n = len(loops)
            for i in range(n):
                for j in range(i + 1, n):
                    l1, l2 = loops[i], loops[j]
                    if (initial_uvs[l1] - initial_uvs[l2]).length < 1e-3:
                        uf.union(l1, l2)

        cluster_targets = defaultdict(list)
        for face in selected_quads:
            for loop in face.loops:
                root = uf.find(loop)
                cluster_targets[root].append(target_uvs[loop])

        cluster_averages = {}
        for root, targets in cluster_targets.items():
            cluster_averages[root] = sum(targets, Vector((0.0, 0.0))) / len(targets)

        for face in selected_quads:
            for loop in face.loops:
                root = uf.find(loop)
                target_uvs[loop] = cluster_averages[root].copy()

    if use_snap and snap_step > 0.0:
        for loop in target_uvs:
            t = target_uvs[loop]
            target_uvs[loop] = Vector((
                round(t.x / snap_step) * snap_step,
                round(t.y / snap_step) * snap_step
            ))

        for face in selected_quads:
            u_coords = [target_uvs[l].x for l in face.loops]
            v_coords = [target_uvs[l].y for l in face.loops]
            if (max(u_coords) - min(u_coords)) < 1e-4:
                cu = sum(u_coords) / 4.0
                for l in face.loops:
                    if target_uvs[l].x >= cu:
                        target_uvs[l].x += snap_step
            if (max(v_coords) - min(v_coords)) < 1e-4:
                cv = sum(v_coords) / 4.0
                for l in face.loops:
                    if target_uvs[l].y >= cv:
                        target_uvs[l].y += snap_step

    for loop, target in target_uvs.items():
        loop[uv_layer].uv = target


def pack_in_grid_layout(selected_quads, uv_layer, shape_mode, padding_factor):
    """
    Resuelve casos de anillos radiales, abanicos y caras superpuestas.
    Acomoda todas las caras seleccionadas como un mosaico ordenado de filas x columnas
    dentro del bounding box de la selección, garantizando cero superposiciones.
    """
    n_faces = len(selected_quads)
    if n_faces == 0:
        return

    all_uvs = [l[uv_layer].uv for f in selected_quads for l in f.loops]
    min_u = min(uv.x for uv in all_uvs)
    max_u = max(uv.x for uv in all_uvs)
    min_v = min(uv.y for uv in all_uvs)
    max_v = max(uv.y for uv in all_uvs)

    span_u = max(max_u - min_u, 0.05)
    span_v = max(max_v - min_v, 0.05)

    aspect = span_u / span_v
    cols = max(1, round(math.sqrt(n_faces * aspect)))
    rows = math.ceil(n_faces / cols)

    cell_w = span_u / (cols + (cols - 1) * padding_factor)
    cell_h = span_v / (rows + (rows - 1) * padding_factor)

    if shape_mode == 'SQUARE':
        cell_size = min(cell_w, cell_h)
        cell_w = cell_size
        cell_h = cell_size

    step_x = cell_w * (1.0 + padding_factor)
    step_y = cell_h * (1.0 + padding_factor)

    face_centroids = []
    for f in selected_quads:
        uvs = [l[uv_layer].uv for l in f.loops]
        cu = sum(uv.x for uv in uvs) / 4.0
        cv = sum(uv.y for uv in uvs) / 4.0
        face_centroids.append((f, cu, cv))

    face_centroids.sort(key=lambda item: (-item[2], item[1]))

    for idx, (face, _, _) in enumerate(face_centroids):
        r = idx // cols
        c = idx % cols

        c_x = min_u + c * step_x + cell_w * 0.5
        c_y = max_v - r * step_y - cell_h * 0.5

        half_w = cell_w * 0.5
        half_h = cell_h * 0.5

        corners = get_sorted_ccw_loops(face, uv_layer)
        corners['BL'][uv_layer].uv = Vector((c_x - half_w, c_y - half_h))
        corners['BR'][uv_layer].uv = Vector((c_x + half_w, c_y - half_h))
        corners['TR'][uv_layer].uv = Vector((c_x + half_w, c_y + half_h))
        corners['TL'][uv_layer].uv = Vector((c_x - half_w, c_y + half_h))
