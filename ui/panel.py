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

        # Sección 1: Cuadrícula Continua Unida + Auto Canvas
        box_grid = layout.box()
        box_grid.label(text="Cuadrícula Continua Unida:", icon='MESH_GRID')
        col_g = box_grid.column(align=True)

        op_sq = col_g.operator("uv.quad_rectifier", text="Grilla Cuadrada + Canvas (1:1)", icon='GRID')
        op_sq.shape_mode = 'SQUARE'
        op_sq.fit_to_canvas = True

        op_rect = col_g.operator("uv.quad_rectifier", text="Grilla Rectangular + Canvas", icon='SNAP_FACE')
        op_rect.shape_mode = 'RECTANGLE'
        op_rect.fit_to_canvas = True

        row_raw = col_g.row(align=True)
        op_sq_raw = row_raw.operator("uv.quad_rectifier", text="Grilla 1:1 (Sin Canvas)", icon='STICKY_UVS_DISABLE')
        op_sq_raw.shape_mode = 'SQUARE'
        op_sq_raw.fit_to_canvas = False

        layout.separator()

        # Sección 2: Topología Circular / Anillos UV
        box_circ = layout.box()
        box_circ.label(text="Topología Circular / Anillos UV:", icon='FORCE_VORTEX')
        col_circ = box_circ.column(align=True)

        op_ann = col_circ.operator("uv.quad_to_circle", text="Convertir a Anillo UV", icon='SPHERE')
        op_ann.circle_mode = 'ANNULUS'
        op_ann.fit_to_canvas = True

        op_disc = col_circ.operator("uv.quad_to_circle", text="Convertir a Disco (Cerrado)", icon='MESH_CIRCLE')
        op_disc.circle_mode = 'DISC'
        op_disc.fit_to_canvas = True

        op_unroll = col_circ.operator("uv.quad_rectifier", text="Desenrollar Anillo a Grilla", icon='SNAP_EDGE')
        op_unroll.shape_mode = 'SQUARE'
        op_unroll.fit_to_canvas = True

        layout.separator()

        # Sección 3: Ajuste Dedicado al Canvas [0, 1]
        box_canvas = layout.box()
        box_canvas.label(text="Ajuste al Canvas [0, 1]:", icon='IMAGE_PLANE')
        col_c = box_canvas.column(align=True)
        col_c.operator("uv.fit_to_canvas", text="Ajustar al Canvas (0-1)", icon='FULLSCREEN_ENTER')

        layout.separator()

        # Sección 4: Autoría y Enlaces Oficiales
        box_author = layout.box()
        b_row = box_author.row(align=True)
        b_row.label(text=f"Dev: {_ADDON_INFO['author']}", icon='USER')

        url_op = box_author.operator("wm.url_open", text="YouTube Channel", icon='URL')
        url_op.url = _ADDON_INFO["youtube_channel"]

        site_op = box_author.operator("wm.url_open", text="Team Apricot", icon='GLOBE')
        site_op.url = _ADDON_INFO["website"]
