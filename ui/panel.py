# -*- coding: utf-8 -*-
import bpy
from .. import _ADDON_INFO


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
