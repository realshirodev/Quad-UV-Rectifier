# -*- coding: utf-8 -*-
"""
Core algorithm for Quad UV Rectifier.
Handles geometric quad rectification, anti-bowtie cyclic mapping,
shared corner welding (Union-Find), and grid snapping.
"""

from mathutils import Vector
from collections import defaultdict


class UnionFind:
    """Estructura Disjoint-Set (Union-Find) para agrupar loops coincidentes en UV."""
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


def rectify_quad_face(face, uv_layer, shape_mode):
    """
    Calcula las posiciones UV rectificadas para los 4 loops de una cara quad.

    Estrategia anti-bowtie (sin autointersección):
    1. Calcula el centroide (U, V) y las dimensiones del bounding box local.
    2. Define las 4 esquinas ideales de la cuadrícula respecto al centroide:
       - Bottom-Left  (BL): (-half_w, -half_h) [Cuadrante III]
       - Bottom-Right (BR): (+half_w, -half_h) [Cuadrante IV]
       - Top-Right    (TR): (+half_w, +half_h) [Cuadrante I]
       - Top-Left     (TL): (-half_w, +half_h) [Cuadrante II]
    3. Para preservar estrictamente la topología de la cara y evitar que los lados
       se crucen formando un "bowtie", se evalúan las 8 configuraciones cíclicas válidas
       (4 en sentido antihorario y 4 en sentido horario).
    4. Se selecciona la configuración cíclica que minimiza la distancia total de los
       loops a su respectivo cuadrante/esquina.
    """
    loops = list(face.loops)
    uv_coords = [loop[uv_layer].uv.copy() for loop in loops]

    # Centroide (U, V) de la cara
    c_u = sum(uv.x for uv in uv_coords) / 4.0
    c_v = sum(uv.y for uv in uv_coords) / 4.0
    centroid = Vector((c_u, c_v))

    # Dimensiones originales en UV
    min_u = min(uv.x for uv in uv_coords)
    max_u = max(uv.x for uv in uv_coords)
    min_v = min(uv.y for uv in uv_coords)
    max_v = max(uv.y for uv in uv_coords)

    width = max(max_u - min_u, 1e-5)
    height = max(max_v - min_v, 1e-5)

    if shape_mode == 'SQUARE':
        avg_size = (width + height) * 0.5
        half_w = avg_size * 0.5
        half_h = avg_size * 0.5
    else:
        half_w = width * 0.5
        half_h = height * 0.5

    # 4 esquinas objetivo en coordenadas UV globales
    corner_BL = centroid + Vector((-half_w, -half_h))
    corner_BR = centroid + Vector((half_w, -half_h))
    corner_TR = centroid + Vector((half_w, half_h))
    corner_TL = centroid + Vector((-half_w, half_h))

    # 8 configuraciones cíclicas válidas (preservan aristas perimetrales, eliminan diagonales cruzadas)
    cyclic_candidates = [
        # Sentido antihorario (CCW)
        (corner_BL, corner_BR, corner_TR, corner_TL),
        (corner_BR, corner_TR, corner_TL, corner_BL),
        (corner_TR, corner_TL, corner_BL, corner_BR),
        (corner_TL, corner_BL, corner_BR, corner_TR),
        # Sentido horario (CW)
        (corner_BL, corner_TL, corner_TR, corner_BR),
        (corner_TL, corner_TR, corner_BR, corner_BL),
        (corner_TR, corner_BR, corner_BL, corner_TL),
        (corner_BR, corner_BL, corner_TL, corner_TR),
    ]

    best_config = None
    min_total_dist_sq = float('inf')

    for candidate in cyclic_candidates:
        dist_sq = sum((uv_coords[i] - candidate[i]).length_squared for i in range(4))
        if dist_sq < min_total_dist_sq:
            min_total_dist_sq = dist_sq
            best_config = candidate

    return {loops[i]: best_config[i].copy() for i in range(4)}


def process_mesh_quad_rectification(
    bm,
    uv_layer,
    is_sync,
    shape_mode='RECTANGLE',
    weld_shared_corners=True,
    use_snap=False,
    snap_step=0.0625,
):
    """
    Ejecuta el enderezamiento de quads sobre un objeto bmesh en modo edición.
    Retorna una tupla (quads_procesados, caras_no_quad_ignoradas).
    """
    # 1. Identificar caras seleccionadas respetando UV Sync Selection
    selected_quads = []
    ignored_faces = 0

    for face in bm.faces:
        if is_sync:
            face_selected = face.select
        else:
            face_selected = all(loop[uv_layer].select for loop in face.loops)

        if face_selected:
            if len(face.loops) == 4:
                selected_quads.append(face)
            else:
                ignored_faces += 1

    if not selected_quads:
        return 0, ignored_faces

    # 2. Calcular posiciones objetivo iniciales por quad
    target_uvs = {}
    initial_uvs = {}
    for face in selected_quads:
        for loop in face.loops:
            initial_uvs[loop] = loop[uv_layer].uv.copy()
        quad_targets = rectify_quad_face(face, uv_layer, shape_mode)
        target_uvs.update(quad_targets)

    # 3. Soldar / promediar esquinas compartidas entre quads adyacentes
    if weld_shared_corners and len(selected_quads) > 1:
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
                    if (initial_uvs[l1] - initial_uvs[l2]).length < 1e-4:
                        uf.union(l1, l2)

        cluster_targets = defaultdict(list)
        for face in selected_quads:
            for loop in face.loops:
                root = uf.find(loop)
                cluster_targets[root].append(target_uvs[loop])

        cluster_averages = {}
        for root, targets in cluster_targets.items():
            avg_uv = sum(targets, Vector((0.0, 0.0))) / len(targets)
            cluster_averages[root] = avg_uv

        for face in selected_quads:
            for loop in face.loops:
                root = uf.find(loop)
                target_uvs[loop] = cluster_averages[root].copy()

    # 4. Ajustar opcionalmente a pasos de cuadrícula (Snap)
    if use_snap and snap_step > 0.0:
        for loop, target in target_uvs.items():
            u = round(target.x / snap_step) * snap_step
            v = round(target.y / snap_step) * snap_step
            target_uvs[loop] = Vector((u, v))

    # 5. Aplicar las nuevas coordenadas a la capa UV activa
    for loop, target in target_uvs.items():
        loop[uv_layer].uv = target

    return len(selected_quads), ignored_faces
