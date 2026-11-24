import bpy

def register_properties():
    bpy.types.Scene.uv_rectifier_shape_mode = bpy.props.EnumProperty(
        name="Forma",
        description="Elige entre mantener la proporción rectangular o forzar un cuadrado 1:1",
        items=[
            ('RECTANGLE', "Rectangular", "Mantiene la proporción ancho/alto de cada cara"),
            ('SQUARE', "Cuadrado (1:1)", "Fuerza una forma de cuadrado perfecto"),
        ],
        default='RECTANGLE'
    )

    bpy.types.Scene.uv_rectifier_weld_shared = bpy.props.BoolProperty(
        name="Soldar Esquinas Compartidas",
        description="Promedia las esquinas compartidas entre quads adyacentes para formar una grilla continua sin huecos",
        default=True
    )

    bpy.types.Scene.uv_rectifier_use_snap = bpy.props.BoolProperty(
        name="Ajustar a Cuadrícula (Snap)",
        description="Ajusta las coordenadas UV resultantes a pasos regulares de cuadrícula",
        default=False
    )

    bpy.types.Scene.uv_rectifier_snap_step = bpy.props.FloatProperty(
        name="Paso de Cuadrícula",
        description="Tamaño de paso para el snap (ej. 0.0625 = 1/16, 0.03125 = 1/32)",
        default=0.0625,
        min=0.0001,
        max=1.0,
        precision=4
    )


def unregister_properties():
    props = [
        "uv_rectifier_shape_mode",
        "uv_rectifier_weld_shared",
        "uv_rectifier_use_snap",
        "uv_rectifier_snap_step",
    ]
    for prop in props:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
