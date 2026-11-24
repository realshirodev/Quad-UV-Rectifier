# -*- coding: utf-8 -*-
import bpy
import bmesh
from ..core.rectifier import process_mesh_quad_rectification


class UV_OT_quad_rectifier(bpy.types.Operator):
    """Endereza caras quad en el editor UV a cuadrados o rectángulos limpios"""
    bl_idname = "uv.quad_rectifier"
    bl_label = "Enderezar Quads UV"
    bl_description = "Endereza caras quad seleccionadas a cuadrícula limpia sin diagonales ni autointersecciones"
    bl_options = {'REGISTER', 'UNDO'}

    shape_mode: bpy.props.EnumProperty(
        name="Forma",
        description="Elige entre mantener la proporción rectangular o forzar un cuadrado 1:1",
        items=[
            ('RECTANGLE', "Rectangular", "Mantiene la proporción ancho/alto de cada cara"),
            ('SQUARE', "Cuadrado (1:1)", "Fuerza una forma de cuadrado perfecto"),
        ],
        default='RECTANGLE',
    )

    weld_shared_corners: bpy.props.BoolProperty(
        name="Soldar Esquinas Compartidas",
        description="Promedia las esquinas compartidas entre quads adyacentes para formar una grilla continua sin huecos",
        default=True,
    )

    use_snap: bpy.props.BoolProperty(
        name="Ajustar a Cuadrícula (Snap)",
        description="Ajusta las coordenadas UV resultantes a pasos regulares de cuadrícula",
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

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH'
            and context.space_data is not None
            and context.space_data.type == 'IMAGE_EDITOR'
        )

    def execute(self, context):
        # Sincronizar hacia Scene properties para que el panel mantenga los valores utilizados
        scene = context.scene
        if hasattr(scene, "uv_rectifier_shape_mode"):
            scene.uv_rectifier_shape_mode = self.shape_mode
            scene.uv_rectifier_weld_shared = self.weld_shared_corners
            scene.uv_rectifier_use_snap = self.use_snap
            scene.uv_rectifier_snap_step = self.snap_step

        is_sync = scene.tool_settings.use_uv_select_sync

        # Compatibilidad con Multi-Object Edit Mode en Blender 4.0+
        edit_objects = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not edit_objects and context.active_object and context.active_object.type == 'MESH':
            edit_objects = [context.active_object]

        if not edit_objects:
            self.report({'WARNING'}, "No hay objetos de tipo malla en modo edición.")
            return {'CANCELLED'}

        total_quads = 0
        total_ignored = 0

        for obj in edit_objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            quads, ignored = process_mesh_quad_rectification(
                bm=bm,
                uv_layer=uv_layer,
                is_sync=is_sync,
                shape_mode=self.shape_mode,
                weld_shared_corners=self.weld_shared_corners,
                use_snap=self.use_snap,
                snap_step=self.snap_step,
            )

            if quads > 0:
                bmesh.update_edit_mesh(obj.data)
                total_quads += quads
            total_ignored += ignored

        # Reporte claro para el usuario
        if total_quads == 0:
            self.report(
                {'WARNING'},
                f"No se procesaron caras quad. Caras no-quad ignoradas: {total_ignored}."
            )
            return {'CANCELLED'}

        msg = f"Quad UV Rectifier: {total_quads} caras quad enderezadas."
        if total_ignored > 0:
            msg += f" ({total_ignored} caras no-quad ignoradas)."
        self.report({'INFO'}, msg)

        return {'FINISHED'}
