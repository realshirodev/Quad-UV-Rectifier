# -*- coding: utf-8 -*-
import bpy
import bmesh
from ..core.rectifier import (
    get_selected_quads,
    get_connected_islands,
    rectify_connected_island_grid,
    fit_uv_loops_to_canvas,
    is_loop_uv_selected,
)


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

    fit_to_canvas: bpy.props.BoolProperty(
        name="Ajustar al Canvas (0-1)",
        description="Escala y centra automáticamente las UVs rectificadas dentro del espacio [0, 1] de la textura",
        default=True,
    )

    canvas_margin: bpy.props.FloatProperty(
        name="Margen de Canvas",
        description="Margen respecto a los bordes del canvas [0, 1]",
        default=0.02,
        min=0.0,
        max=0.4,
        precision=3,
    )

    keep_aspect: bpy.props.BoolProperty(
        name="Mantener Proporción",
        description="Mantiene la proporción uniforme al escalar para no deformar las celdas cuadradas",
        default=True,
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
            all_processed_loops = []
            for island in islands:
                rectify_connected_island_grid(
                    island_faces=island,
                    uv_layer=uv_layer,
                    shape_mode=self.shape_mode,
                    active_face=active_face,
                )
                for f in island:
                    all_processed_loops.extend(f.loops)

            # 3. Acomodar opcionalmente al Canvas [0, 1]
            if self.fit_to_canvas and all_processed_loops:
                fit_uv_loops_to_canvas(
                    uv_loops=all_processed_loops,
                    uv_layer=uv_layer,
                    margin=self.canvas_margin,
                    keep_aspect=self.keep_aspect,
                )

            bmesh.update_edit_mesh(obj.data)
            total_quads += len(selected_quads)

        if total_quads == 0:
            self.report(
                {'WARNING'},
                f"No se procesaron quads. Caras no-quad ignoradas: {total_ignored}."
            )
            return {'CANCELLED'}

        msg = f"Quad UV Rectifier: {total_quads} quads unidos en {total_islands} cuadrícula(s)"
        if self.fit_to_canvas:
            msg += " y ajustados al canvas [0, 1]"
        msg += "."
        if total_ignored > 0:
            msg += f" ({total_ignored} caras no-quad ignoradas)."
        self.report({'INFO'}, msg)

        return {'FINISHED'}


class UV_OT_fit_to_canvas(bpy.types.Operator):
    """Escala y centra las caras UV seleccionadas dentro del canvas [0, 1]"""
    bl_idname = "uv.fit_to_canvas"
    bl_label = "Ajustar al Canvas UV"
    bl_description = "Escala y centra la selección UV dentro del espacio [0, 1] de la textura"
    bl_options = {'REGISTER', 'UNDO'}

    margin: bpy.props.FloatProperty(
        name="Margen",
        description="Margen respecto a los bordes del canvas [0, 1]",
        default=0.02,
        min=0.0,
        max=0.4,
        precision=3,
    )

    keep_aspect: bpy.props.BoolProperty(
        name="Mantener Proporción",
        description="Mantiene la proporción uniforme para no deformar las proporciones",
        default=True,
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

        total_loops = 0

        for obj in edit_objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            selected_loops = []
            for face in bm.faces:
                if is_sync:
                    if face.select:
                        selected_loops.extend(face.loops)
                else:
                    for loop in face.loops:
                        if is_loop_uv_selected(loop, uv_layer):
                            selected_loops.append(loop)

            if selected_loops:
                fit_uv_loops_to_canvas(
                    uv_loops=selected_loops,
                    uv_layer=uv_layer,
                    margin=self.margin,
                    keep_aspect=self.keep_aspect,
                )
                bmesh.update_edit_mesh(obj.data)
                total_loops += len(selected_loops)

        if total_loops == 0:
            self.report({'WARNING'}, "No hay vértices UV seleccionados para ajustar.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Selección UV ajustada al canvas [0, 1] ({total_loops} vértices).")
        return {'FINISHED'}
