_ADDON_INFO = {
    "name": "Quad UV Rectifier",
    "author": "ShiroDev",
    "version": (1, 5, 0),
    "blender": (4, 0, 0),
    "location": "UV Editor > Barra Lateral (N) > pestaña 'UV Square'",
    "description": "Endereza caras quad en una cuadrícula continua ortogonal conectada y acomoda al canvas [0, 1] sin montarse.",
    "category": "UV",
    "doc_url": "https://teamapricot.com",
    "website": "https://teamapricot.com",
    "youtube_channel": "https://www.youtube.com/@shiro_dev",
}

# Diccionario bl_info para compatibilidad con versiones legacy de Blender (4.0 - 4.1)
bl_info = _ADDON_INFO.copy()

import sys
import importlib

# Recarga dinámica automática si Blender ya tenía los submódulos en caché
if "bpy" in locals():
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith(__name__ + "."):
            try:
                importlib.reload(sys.modules[mod_name])
            except Exception:
                pass

import bpy
from .operators import operator_classes
from .ui.panel import UV_PT_quad_rectifier

classes = operator_classes + (
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
