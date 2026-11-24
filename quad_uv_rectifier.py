# -*- coding: utf-8 -*-
"""
Quad UV Rectifier - Blender 4.0+ Add-on
========================================
Add-on para el UV Editor que endereza caras UV de tipo quad en cuadrículas limpias
y continuas (cuadrados o rectángulos), soldando y compartiendo los bordes entre
caras adyacentes sin huecos ni márgenes, respetando la topología de conexión de bmesh.
"""

_ADDON_INFO = {
    "name": "Quad UV Rectifier",
    "author": "ShiroDev",
    "version": (1, 3, 0),
    "blender": (4, 0, 0),
    "location": "UV Editor > Barra Lateral (N) > pestaña 'UV Square'",
    "description": "Endereza caras quad en una cuadrícula continua ortogonal conectada, sin diagonales, huecos ni cruces.",
    "category": "UV",
    "doc_url": "https://teamapricot.com",
    "website": "https://teamapricot.com",
    "youtube_channel": "https://www.youtube.com/@shiro_dev",
}

# Diccionario bl_info para compatibilidad con versiones legacy de Blender (4.0 - 4.1)
bl_info = _ADDON_INFO.copy()

import bpy
import bmesh
import math
from mathutils import Vector
from collections import defaultdict


# =========================================================================
# Utilidades de Selección y Topología
# =========================================================================

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
            # En Sync OFF: la cara está seleccionada si todos sus loops UV están seleccionados
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
                        # Verificar que comparten arista en UV (no es una costura abierta)
                        l_curr = loop
                        l_linked = next((l for l in linked.loops if l.vert == loop.vert), None)
                        if l_linked and (l_curr[uv_layer].uv - l_linked[uv_layer].uv).length < 1e-3:
                            face_set.remove(linked)
                            queue.append(linked)

        islands.append(island)

    return islands


# =========================================================================
# Lógica de Transformación: Cuadrícula Continua Topológica (Sin Huecos)
# =========================================================================

def rectify_connected_island_grid(island_faces, uv_layer, shape_mode='SQUARE', active_face=None):
    """
    Propaga las coordenadas de cuadrícula fila por fila y columna por columna
    a través de las aristas compartidas en BMesh.

    - Las caras adyacentes comparten EXACTAMENTE las mismas coordenadas UV en los
      bordes compartidos (0 huecos, 0 margen, cuadrícula pegada continua).
    - Cada celda queda como un rectángulo o cuadrado 1:1 ortogonal perfecto.
    - Cero diagonales y cero torsiones internas.
    """
    if not island_faces:
        return

    # 1. Determinar cara base inicial (la cara activa si está en la isla, o la primera)
    start_face = island_faces[0]
    if active_face and active_face in island_faces:
        start_face = active_face

    # 2. Inicializar la cara base con cuadrantes CCW limpios
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

    # 3. Propagación topológica por BFS
    visited_faces = {start_face}
    queue = [start_face]
    island_set = set(island_faces)

    while queue:
        curr_face = queue.pop(0)

        # Recorrer las 4 aristas perimetrales de la cara actual
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

            # Buscar cara vecina que comparta esta arista
            for next_face in bm_edge.link_faces:
                if next_face == curr_face or next_face not in island_set or next_face in visited_faces:
                    continue

                # Localizar los loops en next_face correspondientes a v_A y v_B
                m_A = next((l for l in next_face.loops if l.vert == v_A), None)
                m_B = next((l for l in next_face.loops if l.vert == v_B), None)

                if not m_A or not m_B:
                    continue

                # Verificar conexión continua en UV (respetar costuras abiertas)
                if (m_A[uv_layer].uv - l_A[uv_layer].uv).length > 1e-3 or (m_B[uv_layer].uv - l_B[uv_layer].uv).length > 1e-3:
                    continue

                # 4. Asignar EXACTAMENTE las mismas coordenadas UV en el borde compartido (0 huecos)
                target_uvs[m_A] = T_A.copy()
                target_uvs[m_B] = T_B.copy()

                # Identificar los otros 2 loops opuestos de next_face
                next_loops = list(next_face.loops)
                idx_A = next_loops.index(m_A)
                idx_B = next_loops.index(m_B)

                if idx_B == (idx_A + 1) % 4:
                    # Orden cíclico: m_A -> m_B -> m_C -> m_D
                    m_C = next_loops[(idx_B + 1) % 4]
                    m_D = next_loops[(idx_B + 2) % 4]
                    is_direct = True
                else:
                    # Orden cíclico: m_B -> m_A -> m_C -> m_D
                    m_C = next_loops[(idx_A + 1) % 4]
                    m_D = next_loops[(idx_A + 2) % 4]
                    is_direct = False

                # 5. Proyección perpendicular ortogonal para los dos vértices opuestos
                u_hat = V_edge / edge_len
                # Dos vectores unitarios perpendiculares: izquierda y derecha
                P_left = Vector((-u_hat.y, u_hat.x))
                P_right = Vector((u_hat.y, -u_hat.x))

                # Determinar cuál dirección perpendicular apunta hacia el interior de next_face
                orig_mid_shared = (m_A[uv_layer].uv + m_B[uv_layer].uv) * 0.5
                orig_mid_opp = (m_C[uv_layer].uv + m_D[uv_layer].uv) * 0.5
                dir_orig = orig_mid_opp - orig_mid_shared

                orig_edge_vec = m_B[uv_layer].uv - m_A[uv_layer].uv
                cross_2d = orig_edge_vec.x * dir_orig.y - orig_edge_vec.y * dir_orig.x

                if cross_2d >= 0.0:
                    n_perp = P_left
                else:
                    n_perp = P_right

                # Longitud del paso de celda
                if shape_mode == 'SQUARE':
                    step_len = edge_len
                else:
                    step_len = dir_orig.length
                    if step_len < 1e-4:
                        step_len = edge_len

                V_perp = n_perp * step_len

                # Asignar los dos vértices opuestos para completar la celda rectangular ortogonal
                if is_direct:
                    target_uvs[m_D] = T_A + V_perp
                    target_uvs[m_C] = T_B + V_perp
                else:
                    target_uvs[m_C] = T_A + V_perp
                    target_uvs[m_D] = T_B + V_perp

                visited_faces.add(next_face)
                queue.append(next_face)

    # Aplicar coordenadas finales sobre la capa UV activa
    for loop, target in target_uvs.items():
        loop[uv_layer].uv = target


# =========================================================================
# Operador Principal de Blender
# =========================================================================

class UV_OT_quad_rectifier(bpy.types.Operator):
    """Endereza caras quad seleccionadas en una cuadrícula continua ortogonal sin huecos ni diagonales"""
    bl_idname = "uv.quad_rectifier"
    bl_label = "Enderezar Cuadrícula UV"
    bl_description = "Alinea y une caras quad seleccionadas en una cuadrícula continua ortogonal perfecta sin huecos"
    bl_options = {'REGISTER', 'UNDO'}

    shape_mode: bpy.props.EnumProperty(
        name="Forma de Celda",
        description="Elige entre celdas cuadradas perfectas o mantener proporción rectangular",
        items=[
            ('SQUARE', "Cuadrado (1:1)", "Fuerza cada celda de la cuadrícula a un cuadrado perfecto 1:1"),
            ('RECTANGLE', "Rectangular", "Mantiene las proporciones ancho/alto de las celdas"),
        ],
        default='SQUARE',
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH'
            and context.space_data is not None
            and context.space_data.type == 'IMAGE_EDITOR'
        )

    def execute(self, context):
        is_sync = context.scene.tool_settings.use_uv_select_sync

        edit_objects = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not edit_objects and context.active_object and context.active_object.type == 'MESH':
            edit_objects = [context.active_object]

        if not edit_objects:
            self.report({'WARNING'}, "No hay mallas activas en modo edición.")
            return {'CANCELLED'}

        total_quads = 0
        total_ignored = 0
        total_islands = 0

        for obj in edit_objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            selected_quads, ignored = get_selected_quads(bm, uv_layer, is_sync)
            total_ignored += ignored

            if not selected_quads:
                continue

            active_face = bm.faces.active if bm.faces.active in selected_quads else None

            # 1. Separar los quads en islas conectadas topológicamente
            islands = get_connected_islands(selected_quads, uv_layer)
            total_islands += len(islands)

            # 2. Rectificar cada isla conectada propagando la cuadrícula continua
            for island in islands:
                rectify_connected_island_grid(
                    island_faces=island,
                    uv_layer=uv_layer,
                    shape_mode=self.shape_mode,
                    active_face=active_face,
                )

            bmesh.update_edit_mesh(obj.data)
            total_quads += len(selected_quads)

        if total_quads == 0:
            self.report(
                {'WARNING'},
                f"No se procesaron quads. Caras no-quad ignoradas: {total_ignored}."
            )
            return {'CANCELLED'}

        msg = f"Quad UV Rectifier: {total_quads} quads unidos en {total_islands} cuadrícula(s) continua(s)."
        if total_ignored > 0:
            msg += f" ({total_ignored} caras no-quad ignoradas)."
        self.report({'INFO'}, msg)

        return {'FINISHED'}


# =========================================================================
# Panel de Interfaz de Usuario
# =========================================================================

class UV_PT_quad_rectifier(bpy.types.Panel):
    """Panel en la barra lateral (N) del UV Editor bajo la pestaña 'UV Square'"""
    bl_label = "Quad UV Rectifier"
    bl_idname = "UV_PT_quad_rectifier"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "UV Square"

    @classmethod
    def poll(cls, context):
        sdata = context.space_data
        return (
            sdata is not None
            and sdata.type == 'IMAGE_EDITOR'
            and sdata.mode == 'UV'
        )

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object

        if not obj or obj.type != 'MESH' or context.mode != 'EDIT_MESH':
            box = layout.box()
            box.label(text="Modo Edición Requerido", icon='INFO')
            box.label(text="Selecciona una malla y entra en Edit Mode.")
            return

        # Estado del objeto y UV Sync Selection
        h_box = layout.box()
        h_row = h_box.row(align=True)
        h_row.label(text=f"Malla: {obj.name}", icon='MESH_DATA')
        is_sync = scene.tool_settings.use_uv_select_sync
        h_row.label(text="Sync: ON" if is_sync else "Sync: OFF", icon='LINKED' if is_sync else 'UNLINKED')

        # Botones Principales de Cuadrícula Continua
        box_grid = layout.box()
        box_grid.label(text="Cuadrícula Continua (Unida):", icon='MESH_GRID')
        col_g = box_grid.column(align=True)

        op_sq = col_g.operator("uv.quad_rectifier", text="Grilla Cuadrada (1:1)", icon='GRID')
        op_sq.shape_mode = 'SQUARE'

        op_rect = col_g.operator("uv.quad_rectifier", text="Grilla Rectangular", icon='SNAP_FACE')
        op_rect.shape_mode = 'RECTANGLE'

        layout.separator()

        box_info = layout.box()
        box_info.label(text="Topología:", icon='INFO')
        box_info.label(text="Une y alinea bordes compartidos")
        box_info.label(text="sin huecos ni diagonales.")

        layout.separator()

        # Sección de autoría y enlaces oficiales
        box_author = layout.box()
        b_row = box_author.row(align=True)
        b_row.label(text=f"Dev: {_ADDON_INFO['author']}", icon='USER')

        url_op = box_author.operator("wm.url_open", text="YouTube Channel", icon='URL')
        url_op.url = _ADDON_INFO["youtube_channel"]

        site_op = box_author.operator("wm.url_open", text="Team Apricot", icon='GLOBE')
        site_op.url = _ADDON_INFO["website"]


# =========================================================================
# Registro y Desregistro
# =========================================================================

classes = (
    UV_OT_quad_rectifier,
    UV_PT_quad_rectifier,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
