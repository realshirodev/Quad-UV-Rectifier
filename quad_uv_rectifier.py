# -*- coding: utf-8 -*-
"""
Quad UV Rectifier - Blender 4.0+ Add-on
========================================
Add-on para el UV Editor que endereza caras UV de tipo quad en cuadrículas limpias
(cuadrados o rectángulos), evitando diagonales, bowties, autointersecciones y
resolviendo problemas de anillos, abanicos y caras superpuestas.
"""

bl_info = {
    "name": "Quad UV Rectifier",
    "author": "ShiroDev",
    "version": (1, 2, 0),
    "blender": (4, 0, 0),
    "location": "UV Editor > Barra Lateral (N) > pestaña 'UV Square'",
    "description": "Endereza caras quad en UV sin diagonales ni cruces; incluye modo para desenredar anillos, abanicos y superposiciones.",
    "warning": "",
    "doc_url": "",
    "category": "UV",
}

import bpy
import bmesh
import math
from mathutils import Vector
from collections import defaultdict


# =========================================================================
# Utilidades Topológicas y Matemáticas
# =========================================================================

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

    # Calcular ángulo de cada loop respecto al centroide
    loop_with_angle = []
    for loop in loops:
        uv = loop[uv_layer].uv
        ang = math.atan2(uv.y - c_v, uv.x - c_u)
        loop_with_angle.append((ang, loop))

    # Ordenar estrictamente en sentido antihorario (CCW)
    loop_with_angle.sort(key=lambda item: item[0])
    sorted_loops = [item[1] for item in loop_with_angle]
    sorted_angles = [item[0] for item in loop_with_angle]

    target_angles = [
        -0.75 * math.pi,  # BL
        -0.25 * math.pi,  # BR
         0.25 * math.pi,  # TR
         0.75 * math.pi,  # TL
    ]

    # Probar las 4 rotaciones cíclicas válidas en CCW para hallar la alineación óptima
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
        # Compatibilidad con Blender 5.0+ (uv_select_vert) y 4.x (loop[uv_layer].select)
        if hasattr(loop, "uv_select_vert"):
            return bool(loop.uv_select_vert)
        return bool(loop[uv_layer].select)

    for face in bm.faces:
        if is_sync:
            face_sel = face.select
        else:
            # En Sync OFF: la cara está seleccionada si todos sus loops UV están seleccionados
            face_sel = all(is_loop_selected(l) for l in face.loops)

        if face_sel:
            if len(face.loops) == 4:
                selected_quads.append(face)
            else:
                ignored_count += 1

    return selected_quads, ignored_count


# =========================================================================
# Algoritmos de Rectificación y Acomodo (Anti-Anillos / Anti-Superposición)
# =========================================================================

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

        # Asignar loops ordenados en CCW a sus esquinas
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

    # Soldar/promediar esquinas compartidas
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

    # Snap opcional con prevención de colapso
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

    # Calcular bounding box global de la selección
    all_uvs = [l[uv_layer].uv for f in selected_quads for l in f.loops]
    min_u = min(uv.x for uv in all_uvs)
    max_u = max(uv.x for uv in all_uvs)
    min_v = min(uv.y for uv in all_uvs)
    max_v = max(uv.y for uv in all_uvs)

    span_u = max(max_u - min_u, 0.05)
    span_v = max(max_v - min_v, 0.05)

    # Determinar columnas y filas para una grilla armónica
    aspect = span_u / span_v
    cols = max(1, round(math.sqrt(n_faces * aspect)))
    rows = math.ceil(n_faces / cols)

    # Calcular tamaño de celda respetando el padding
    cell_w = span_u / (cols + (cols - 1) * padding_factor)
    cell_h = span_v / (rows + (rows - 1) * padding_factor)

    if shape_mode == 'SQUARE':
        cell_size = min(cell_w, cell_h)
        cell_w = cell_size
        cell_h = cell_size

    step_x = cell_w * (1.0 + padding_factor)
    step_y = cell_h * (1.0 + padding_factor)

    # Ordenar las caras por su centroide original (de arriba a abajo, izquierda a derecha)
    face_centroids = []
    for f in selected_quads:
        uvs = [l[uv_layer].uv for l in f.loops]
        cu = sum(uv.x for uv in uvs) / 4.0
        cv = sum(uv.y for uv in uvs) / 4.0
        face_centroids.append((f, cu, cv))

    face_centroids.sort(key=lambda item: (-item[2], item[1]))

    # Asignar cada quad a su celda en la cuadrícula ordenada
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


# =========================================================================
# Operador Principal de Blender
# =========================================================================

class UV_OT_quad_rectifier(bpy.types.Operator):
    """Endereza caras quad seleccionadas sin diagonales ni cruces"""
    bl_idname = "uv.quad_rectifier"
    bl_label = "Enderezar Quads UV"
    bl_description = "Endereza caras quad en el editor UV a cuadrados o rectángulos limpios"
    bl_options = {'REGISTER', 'UNDO'}

    action_mode: bpy.props.EnumProperty(
        name="Modo de Operación",
        description="Elige entre enderezar en su lugar o acomodar en cuadrícula sin superposiciones",
        items=[
            ('IN_PLACE', "En su Lugar", "Endereza cada quad en su propia ubicación"),
            ('GRID_PACK', "Acomodar Cuadrícula", "Acomoda todas las caras en una grilla ordenada (ideal para anillos/abanicos/superposiciones)"),
        ],
        default='IN_PLACE',
    )

    shape_mode: bpy.props.EnumProperty(
        name="Forma",
        description="Proporción del resultado",
        items=[
            ('RECTANGLE', "Rectangular", "Mantiene las proporciones ancho/alto"),
            ('SQUARE', "Cuadrado (1:1)", "Fuerza cuadrados perfectos con proporción 1:1"),
        ],
        default='RECTANGLE',
    )

    weld_shared_corners: bpy.props.BoolProperty(
        name="Soldar Esquinas Adyacentes",
        description="Promedia las esquinas compartidas entre quads vecinos para una grilla continua",
        default=True,
    )

    use_snap: bpy.props.BoolProperty(
        name="Ajustar a Cuadrícula (Snap)",
        description="Ajusta las coordenadas UV a pasos regulares de cuadrícula",
        default=False,
    )

    snap_step: bpy.props.FloatProperty(
        name="Paso de Cuadrícula",
        description="Tamaño de paso para el snap (ej. 0.0625 = 1/16, 0.03125 = 1/32)",
        default=0.0625,
        min=0.0001,
        max=1.0,
        precision=4,
    )

    grid_padding: bpy.props.FloatProperty(
        name="Espaciado (Padding)",
        description="Espacio relativo entre celdas al acomodar en cuadrícula",
        default=0.05,
        min=0.0,
        max=0.5,
        precision=3,
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

        for obj in edit_objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            selected_quads, ignored = get_selected_quads(bm, uv_layer, is_sync)
            total_ignored += ignored

            if not selected_quads:
                continue

            if self.action_mode == 'GRID_PACK':
                pack_in_grid_layout(
                    selected_quads=selected_quads,
                    uv_layer=uv_layer,
                    shape_mode=self.shape_mode,
                    padding_factor=self.grid_padding,
                )
            else:
                rectify_in_place(
                    selected_quads=selected_quads,
                    uv_layer=uv_layer,
                    shape_mode=self.shape_mode,
                    weld_shared=self.weld_shared_corners,
                    use_snap=self.use_snap,
                    snap_step=self.snap_step,
                )

            bmesh.update_edit_mesh(obj.data)
            total_quads += len(selected_quads)

        if total_quads == 0:
            self.report(
                {'WARNING'},
                f"No se procesó ningún quad. Caras no-quad ignoradas: {total_ignored}."
            )
            return {'CANCELLED'}

        msg = f"Quad UV Rectifier: {total_quads} caras quad procesadas con éxito."
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

        # Sección 1: Enderezar en su lugar
        box_place = layout.box()
        box_place.label(text="Enderezar en su Lugar:", icon='MESH_GRID')
        col_p = box_place.column(align=True)

        op_rect = col_p.operator("uv.quad_rectifier", text="Rectángulo en su Lugar", icon='SNAP_GRID')
        op_rect.action_mode = 'IN_PLACE'
        op_rect.shape_mode = 'RECTANGLE'
        op_rect.weld_shared_corners = True

        op_sq = col_p.operator("uv.quad_rectifier", text="Cuadrado (1:1) en su Lugar", icon='MESH_PLANE')
        op_sq.action_mode = 'IN_PLACE'
        op_sq.shape_mode = 'SQUARE'
        op_sq.weld_shared_corners = True

        # Sección 2: Solución de Anillos, Abanicos y Superposiciones
        box_pack = layout.box()
        box_pack.label(text="Anillos / Abanicos / Superpuestos:", icon='MOD_ARRAY')
        box_pack.label(text="Acomoda las caras en cuadrícula limpia:")
        col_pack = box_pack.column(align=True)

        op_grid_sq = col_pack.operator("uv.quad_rectifier", text="Acomodar Cuadrícula (1:1)", icon='GRID')
        op_grid_sq.action_mode = 'GRID_PACK'
        op_grid_sq.shape_mode = 'SQUARE'

        op_grid_rect = col_pack.operator("uv.quad_rectifier", text="Acomodar Cuadrícula (Rect)", icon='SNAP_FACE')
        op_grid_rect.action_mode = 'GRID_PACK'
        op_grid_rect.shape_mode = 'RECTANGLE'

        layout.separator()

        # Sección 3: Acciones Avanzadas / Opciones
        box_adv = layout.box()
        box_adv.label(text="Avanzado / Re-ejecutar:", icon='SETTINGS')
        col_adv = box_adv.column(align=True)
        col_adv.operator("uv.quad_rectifier", text="Ejecutar con Parámetros...", icon='PROPERTIES')


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
