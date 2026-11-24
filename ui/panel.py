# -*- coding: utf-8 -*-
import bpy


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
