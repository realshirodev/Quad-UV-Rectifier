# -*- coding: utf-8 -*-
import bpy
import bmesh
from ..core.rectifier import (
    get_selected_quads,
    get_connected_islands,
    rectify_connected_island_grid,
    pack_islands_to_canvas,
    is_loop_uv_selected,
)


class UV_OT_quad_rectifier(bpy.types.Operator):
    """Endereza caras quad seleccionadas en una cuadrícula continua ortogonal y acomoda al canvas sin superposiciones"""
    bl_idname = "uv.quad_rectifier"
    bl_label = "Enderezar Cuadrícula UV"
    bl_description = "Alinea y une caras quad seleccionadas en una cuadrícula continua perfecta y las acomoda al canvas sin montarse"
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
        description="Empaqueta y acomoda automáticamente las islas en el canvas [0, 1] sin superponerse",
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

    island_spacing: bpy.props.FloatProperty(
        name="Espaciado entre Islas",
        description="Separación entre islas para que no se toquen ni se monten",
        default=0.02,
        min=0.001,
        max=0.2,
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

            # 3. Empaquetar y acomodar todas las islas en el canvas [0, 1] sin montarse
            if self.fit_to_canvas and islands:
                pack_islands_to_canvas(
                    islands=islands,
                    uv_layer=uv_layer,
                    margin=self.canvas_margin,
                    spacing=self.island_spacing,
                )

            bmesh.update_edit_mesh(obj.data)
            total_quads += len(selected_quads)

        if total_quads == 0:
            self.report(
                {'WARNING'},
                f"No se procesaron quads. Caras no-quad ignoradas: {total_ignored}."
            )
            return {'CANCELLED'}

        msg = f"Quad UV Rectifier: {total_quads} quads procesados en {total_islands} isla(s)"
        if self.fit_to_canvas:
            msg += " acomodados al canvas [0, 1] sin superposiciones"
        msg += "."
        if total_ignored > 0:
            msg += f" ({total_ignored} caras no-quad ignoradas)."
        self.report({'INFO'}, msg)

        return {'FINISHED'}


class UV_OT_fit_to_canvas(bpy.types.Operator):
    """Empaqueta y acomoda las islas UV seleccionadas dentro del canvas [0, 1] sin superponerse"""
    bl_idname = "uv.fit_to_canvas"
    bl_label = "Ajustar al Canvas UV"
    bl_description = "Acomoda y empaqueta las islas UV seleccionadas dentro del canvas [0, 1] sin montarse"
    bl_options = {'REGISTER', 'UNDO'}

    margin: bpy.props.FloatProperty(
        name="Margen",
        description="Margen respecto a los bordes del canvas [0, 1]",
        default=0.02,
        min=0.0,
        max=0.4,
        precision=3,
    )

    spacing: bpy.props.FloatProperty(
        name="Espaciado entre Islas",
        description="Separación entre islas para que no se toquen ni se monten",
        default=0.02,
        min=0.001,
        max=0.2,
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

        total_islands = 0

        for obj in edit_objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            selected_faces = []
            for face in bm.faces:
                if is_sync:
                    if face.select:
                        selected_faces.append(face)
                else:
                    if all(is_loop_uv_selected(l, uv_layer) for l in face.loops):
                        selected_faces.append(face)

            if selected_faces:
                islands = get_connected_islands(selected_faces, uv_layer)
                total_islands += len(islands)

                pack_islands_to_canvas(
                    islands=islands,
                    uv_layer=uv_layer,
                    margin=self.margin,
                    spacing=self.spacing,
                )
                bmesh.update_edit_mesh(obj.data)

        if total_islands == 0:
            self.report({'WARNING'}, "No hay islas UV seleccionadas para ajustar.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"{total_islands} isla(s) UV acomodada(s) al canvas [0, 1] sin superposiciones.")
        return {'FINISHED'}
