# 📐 Quad UV Rectifier for Blender

[![Blender Version](https://img.shields.io/badge/Blender-4.0%20a%205.3%2B-orange?logo=blender&logoColor=white)](https://www.blender.org/)
[![Extensions Platform](https://img.shields.io/badge/Blender%20Extensions-Compatible-green?logo=blender&logoColor=white)](https://extensions.blender.org/)
[![Developer](https://img.shields.io/badge/Developer-ShiroDev-red?logo=youtube&logoColor=white)](https://www.youtube.com/@shiro_dev)
[![Website](https://img.shields.io/badge/Website-Team%20Apricot-success?logo=google-chrome&logoColor=white)](https://teamapricot.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Quad UV Rectifier** es un add-on y extensión profesional para el **UV Editor** de Blender (compatible desde Blender 4.0 hasta 5.3+) diseñado para alinear y unir caras UV de tipo quad en una **cuadrícula continua ortogonal perfecta** (cuadrados 1:1 o rectángulos limpios), propagando la topología real a través de las aristas compartidas sin huecos, márgenes, diagonales ni autointersecciones (*bowties*).

---

## ✨ Características Principales

- 🔗 **Cuadrícula Continua Conectada (Sin Huecos ni Márgenes)**: A diferencia de los empaquetadores de mosaicos sueltos, propaga fila por fila y columna por columna a través de las aristas compartidas en BMesh, garantizando que las caras adyacentes compartan exactamente las mismas coordenadas UV en sus bordes comunes.
- 📐 **Geometría Ortogonal Estricta**: Cada celda se transforma en un rectángulo o cuadrado 1:1 con ángulos rectos de $90^\circ$ ($\Delta V = 0$ en aristas horizontales y $\Delta U = 0$ en aristas verticales).
- 🔄 **Topología Anti-Bowtie Matemática**: Ordena los loops perimetrales en sentido antihorario (CCW) respecto al centroide de la cara para evitar inversiones, diagonales cruzadas y caras retorcidas.
- 🎯 **Soporte UV Sync Selection**: Detección robusta de caras quad seleccionadas tanto con **UV Sync Selection** activado (`ON`) como desactivado (`OFF`), sin alterar jamás caras adyacentes no seleccionadas.
- 🛡️ **Filtrado Seguro de No-Quads**: Ignora triángulos y n-gons sin romper la malla y reporta cuántas caras fueron procesadas y cuántas ignoradas.
- ↩️ **Soporte Completo de UNDO**: Integración nativa con el sistema de deshacer de Blender (`Ctrl + Z`) y actualización en tiempo real con `bmesh.update_edit_mesh`.
- 🧩 **Soporte Moderno de Extensiones**: Compatible con la arquitectura moderna de **Blender Extensions** (`blender_manifest.toml`) y con versiones legacy mediante `bl_info`.

---

## 📁 Estructura del Proyecto

```text
Quad UV Rectifier/
├── core/
│   ├── __init__.py
│   └── rectifier.py        # Algoritmo BFS de propagación topológica y ordenación CCW
├── operators/
│   ├── __init__.py
│   └── rectify_ops.py      # Operadores de Blender y soporte multi-objeto
├── ui/
│   ├── __init__.py
│   └── panel.py            # Panel del Sidebar (N) > UV Square con enlaces oficiales
├── .gitignore
├── blender_manifest.toml   # Manifiesto de Blender Extensions (4.2+)
├── LICENSE                 # Licencia MIT (English / Español)
├── properties.py           # Propiedades de escena persistentes
├── README.md               # Documentación y guía de uso
├── quad_uv_rectifier.py    # Versión completa en un único archivo autónomo
└── __init__.py             # Punto de entrada modular y recarga dinámica
```

---

## 📥 Instalación

### Opción A: Archivo Único `.py`
1. En Blender, ve a **Edit > Preferences > Add-ons**.
2. Haz clic en la esquina superior derecha en **Install from Disk...** (o **Instalar...**).
3. Selecciona el archivo `quad_uv_rectifier.py` y activa la casilla del add-on.

### Opción B: Paquete `.zip` (Recomendado)
1. Descarga o genera el archivo `quad_uv_rectifier.zip`.
2. En Blender ve a **Edit > Preferences > Add-ons > Install from Disk...** (o **Extensions > Install from Disk...** en Blender 4.2+).
3. Selecciona el `.zip` y actívalo.

---

## 🎮 Modo de Uso

1. Selecciona tu objeto y entra en **Modo Edición** (`Tab`).
2. Abre el **UV Editor** y presiona `N` para desplegar la barra lateral.
3. Haz clic en la pestaña **UV Square**.
4. Selecciona las caras quad que deseas alinear.
5. Elige tu modo de grilla:
   - **Grilla Cuadrada (1:1)**: Fuerza cada celda a un cuadrado perfecto conectado.
   - **Grilla Rectangular**: Mantiene las proporciones relativas de ancho y alto de cada cara.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.

Desarrollado con ❤️ por **[ShiroDev](https://www.youtube.com/@shiro_dev)** | **[Team Apricot](https://teamapricot.com)**.
