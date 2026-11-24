# -*- coding: utf-8 -*-
"""
Core algorithm for Quad UV Rectifier.
Topological grid propagation across shared edges in BMesh,
and canvas fitting/centering in [0, 1] texture space.
"""

import math
from mathutils import Vector


def is_loop_uv_selected(loop, uv_layer):
    """Comprueba si un loop está seleccionado en el UV Editor (compatible con 4.x y 5.x)."""
    if hasattr(loop, "uv_select_vert"):
        return bool(loop.uv_select_vert)
    return bool(loop[uv_layer].select)


def get_selected_quads(bm, uv_layer, is_sync):
    """
    Filtra de forma robusta las caras quad seleccionadas respetando UV Sync Selection.
    Retorna (selected_quads, ignored_non_quads_count).
    """
    selected_quads = []
    ignored_count = 0

    for face in bm.faces:
        if is_sync:
            face_sel = face.select
        else:
            face_sel = all(is_loop_uv_selected(l, uv_layer) for l in face.loops)

        if face_sel:
            if len(face.loops) == 4:
                selected_quads.append(face)
            else:
                ignored_count += 1

    return selected_quads, ignored_count


def get_sorted_ccw_loops(face, uv_layer):
    """
    Ordena los 4 loops de una cara quad según su ángulo en sentido antihorario (CCW)
    respecto al centroide UV de la cara.
    Retorna un diccionario: { 'BL': loop, 'BR': loop, 'TR': loop, 'TL': loop }
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
        -0.75 * math.pi,  # BL: -135°
        -0.25 * math.pi,  # BR:  -45°
         0.25 * math.pi,  # TR:  +45°
         0.75 * math.pi,  # TL: +135°
    ]

    def ang_diff(a1, a2):
        d = (a1 - a2 + math.pi) % (2.0 * math.pi) - math.pi
        return abs(d)

    best_shift = 0
    min_cost = float('inf')
    for shift in range(4):
        cost = sum(ang_diff(sorted_angles[(i + shift) % 4], target_angles[i]) for i in range(4))
        if cost < min_cost:
            min_cost = cost
            best_shift = shift

    return {
        'BL': sorted_loops[best_shift % 4],
        'BR': sorted_loops[(best_shift + 1) % 4],
        'TR': sorted_loops[(best_shift + 2) % 4],
        'TL': sorted_loops[(best_shift + 3) % 4],
    }


def get_connected_islands(selected_quads, uv_layer):
    """
    Agrupa los quads seleccionados en islas conectadas topológicamente a través de
    sus aristas compartidas en BMesh (respetando costuras/seams en UV).
    """
    face_set = set(selected_quads)
    islands = []

    while face_set:
        start_face = next(iter(face_set))
        island = []
        queue = [start_face]
        face_set.remove(start_face)

        while queue:
            f = queue.pop(0)
            island.append(f)

            for loop in f.loops:
                edge = loop.edge
                for linked in edge.link_faces:
                    if linked in face_set:
                        l_curr = loop
                        l_linked = next((l for l in linked.loops if l.vert == loop.vert), None)
                        if l_linked and (l_curr[uv_layer].uv - l_linked[uv_layer].uv).length < 1e-3:
                            face_set.remove(linked)
                            queue.append(linked)

        islands.append(island)

    return islands


def fit_uv_loops_to_canvas(uv_loops, uv_layer, margin=0.02, keep_aspect=True):
    """
    Escala y centra una colección de loops UV dentro del canvas [0.0, 1.0].
    """
    if not uv_loops:
        return

    coords = [l[uv_layer].uv for l in uv_loops]
    min_u = min(c.x for c in coords)
    max_u = max(c.x for c in coords)
    min_v = min(c.y for c in coords)
    max_v = max(c.y for c in coords)

    w = max_u - min_u
    h = max_v - min_v

    if w < 1e-6 or h < 1e-6:
        return

    margin = max(0.0, min(margin, 0.45))
    avail_w = 1.0 - 2.0 * margin
    avail_h = 1.0 - 2.0 * margin

    if keep_aspect:
        scale = min(avail_w / w, avail_h / h)
        scale_u = scale
        scale_v = scale
    else:
        scale_u = avail_w / w
        scale_v = avail_h / h

    final_w = w * scale_u
    final_h = h * scale_v

    offset_u = margin + (avail_w - final_w) * 0.5 - min_u * scale_u
    offset_v = margin + (avail_h - final_h) * 0.5 - min_v * scale_v

    for l in uv_loops:
        uv = l[uv_layer].uv
        l[uv_layer].uv = Vector((
            uv.x * scale_u + offset_u,
            uv.y * scale_v + offset_v
        ))


def rectify_connected_island_grid(island_faces, uv_layer, shape_mode='SQUARE', active_face=None):
    """
    Propaga las coordenadas de cuadrícula fila por fila y columna por columna
    a través de las aristas compartidas en BMesh.
    """
    if not island_faces:
        return

    start_face = island_faces[0]
    if active_face and active_face in island_faces:
        start_face = active_face

    corners = get_sorted_ccw_loops(start_face, uv_layer)
    uv_coords = [loop[uv_layer].uv for loop in start_face.loops]

    c_u = sum(uv.x for uv in uv_coords) / 4.0
    c_v = sum(uv.y for uv in uv_coords) / 4.0
    centroid = Vector((c_u, c_v))

    min_u = min(uv.x for uv in uv_coords)
    max_u = max(uv.x for uv in uv_coords)
    min_v = min(uv.y for uv in uv_coords)
    max_v = max(uv.y for uv in uv_coords)

    w = max(max_u - min_u, 1e-4)
    h = max(max_v - min_v, 1e-4)

    if shape_mode == 'SQUARE':
        base_size = (w + h) * 0.5
        w = base_size
        h = base_size

    half_w = w * 0.5
    half_h = h * 0.5

    target_uvs = {}
    target_uvs[corners['BL']] = centroid + Vector((-half_w, -half_h))
    target_uvs[corners['BR']] = centroid + Vector((half_w, -half_h))
    target_uvs[corners['TR']] = centroid + Vector((half_w, half_h))
    target_uvs[corners['TL']] = centroid + Vector((-half_w, half_h))

    visited_faces = {start_face}
    queue = [start_face]
    island_set = set(island_faces)

    while queue:
        curr_face = queue.pop(0)
        f_loops = list(curr_face.loops)

        for i in range(4):
            l_A = f_loops[i]
            l_B = f_loops[(i + 1) % 4]

            if l_A not in target_uvs or l_B not in target_uvs:
                continue

            T_A = target_uvs[l_A]
            T_B = target_uvs[l_B]
            V_edge = T_B - T_A
            edge_len = V_edge.length

            if edge_len < 1e-6:
                continue

            v_A = l_A.vert
            v_B = l_B.vert
            bm_edge = curr_face.edges[i]

            for next_face in bm_edge.link_faces:
                if next_face == curr_face or next_face not in island_set or next_face in visited_faces:
                    continue

                m_A = next((l for l in next_face.loops if l.vert == v_A), None)
                m_B = next((l for l in next_face.loops if l.vert == v_B), None)

                if not m_A or not m_B:
                    continue

                if (m_A[uv_layer].uv - l_A[uv_layer].uv).length > 1e-3 or (m_B[uv_layer].uv - l_B[uv_layer].uv).length > 1e-3:
                    continue

                target_uvs[m_A] = T_A.copy()
                target_uvs[m_B] = T_B.copy()

                next_loops = list(next_face.loops)
                idx_A = next_loops.index(m_A)
                idx_B = next_loops.index(m_B)

                if idx_B == (idx_A + 1) % 4:
                    m_C = next_loops[(idx_B + 1) % 4]
                    m_D = next_loops[(idx_B + 2) % 4]
                    is_direct = True
                else:
                    m_C = next_loops[(idx_A + 1) % 4]
                    m_D = next_loops[(idx_A + 2) % 4]
                    is_direct = False

                u_hat = V_edge / edge_len
                P_left = Vector((-u_hat.y, u_hat.x))
                P_right = Vector((u_hat.y, -u_hat.x))

                orig_mid_shared = (m_A[uv_layer].uv + m_B[uv_layer].uv) * 0.5
                orig_mid_opp = (m_C[uv_layer].uv + m_D[uv_layer].uv) * 0.5
                dir_orig = orig_mid_opp - orig_mid_shared

                orig_edge_vec = m_B[uv_layer].uv - m_A[uv_layer].uv
                cross_2d = orig_edge_vec.x * dir_orig.y - orig_edge_vec.y * dir_orig.x

                if cross_2d >= 0.0:
                    n_perp = P_left
                else:
                    n_perp = P_right

                if shape_mode == 'SQUARE':
                    step_len = edge_len
                else:
                    step_len = dir_orig.length
                    if step_len < 1e-4:
                        step_len = edge_len

                V_perp = n_perp * step_len

                if is_direct:
                    target_uvs[m_D] = T_A + V_perp
                    target_uvs[m_C] = T_B + V_perp
                else:
                    target_uvs[m_C] = T_A + V_perp
                    target_uvs[m_D] = T_B + V_perp

                visited_faces.add(next_face)
                queue.append(next_face)

    for loop, target in target_uvs.items():
        loop[uv_layer].uv = target
