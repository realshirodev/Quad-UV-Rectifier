# -*- coding: utf-8 -*-
import bpy


class UV_PT_quad_rectifier(bpy.types.Panel):
    """Panel en la Barra Lateral (N) del UV Editor bajo la pestaña 'UV Square'"""
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

        # 1. Validación de estado en Modo Edición
        if not obj or obj.type != 'MESH' or context.mode != 'EDIT_MESH':
            box = layout.box()
            box.label(text="Modo Edición Requerido", icon='INFO')
            box.label(text="Selecciona una malla y entra en Edit Mode.")
            return

        # 2. Información del objeto activo y estado de Sync
        header_box = layout.box()
        h_row = header_box.row(align=True)
        h_row.label(text=f"Malla: {obj.name}", icon='MESH_DATA')
        
        is_sync = scene.tool_settings.use_uv_select_sync
        sync_label = "Sync: ON" if is_sync else "Sync: OFF"
        sync_icon = 'LINKED' if is_sync else 'UNLINKED'
        h_row.label(text=sync_label, icon=sync_icon)

        # 3. Configuración de Forma
        shape_box = layout.box()
        shape_box.label(text="Proporción de Forma:", icon='MESH_GRID')
        shape_col = shape_box.column(align=True)
        shape_col.prop(scene, "uv_rectifier_shape_mode", expand=True)

        # 4. Opciones de Topología y Ajuste
        topo_box = layout.box()
        topo_box.label(text="Topología & Cuadrícula:", icon='MOD_EDGESPLIT')
        topo_col = topo_box.column(align=True)
        topo_col.prop(scene, "uv_rectifier_weld_shared", text="Soldar esquinas adyacentes")
        topo_col.prop(scene, "uv_rectifier_use_snap", text="Ajustar a cuadrícula (Snap)")
        if scene.uv_rectifier_use_snap:
            topo_col.separator()
            topo_col.prop(scene, "uv_rectifier_snap_step", text="Paso")

        layout.separator()

        # 5. Botones de Ejecución
        main_col = layout.column(align=True)
        main_row = main_col.row()
        main_row.scale_y = 1.4
        op = main_row.operator("uv.quad_rectifier", text="Enderezar Quads UV", icon='SNAP_GRID')
        op.shape_mode = scene.uv_rectifier_shape_mode
        op.weld_shared_corners = scene.uv_rectifier_weld_shared
        op.use_snap = scene.uv_rectifier_use_snap
        op.snap_step = scene.uv_rectifier_snap_step

        # Botón directo para cuadrado perfecto 1:1
        sub_row = main_col.row(align=True)
        op_sq = sub_row.operator("uv.quad_rectifier", text="Forzar Cuadrado (1:1)", icon='MESH_PLANE')
        op_sq.shape_mode = 'SQUARE'
        op_sq.weld_shared_corners = scene.uv_rectifier_weld_shared
        op_sq.use_snap = scene.uv_rectifier_use_snap
        op_sq.snap_step = scene.uv_rectifier_snap_step
