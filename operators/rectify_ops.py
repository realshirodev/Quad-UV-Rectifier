# -*- coding: utf-8 -*-
import bpy
import bmesh
from ..core.rectifier import (
    get_selected_quads,
    rectify_in_place,
    pack_in_grid_layout,
)


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
