# 📐 Quad UV Rectifier for Blender

[![Blender Version](https://img.shields.io/badge/Blender-4.0%20a%205.3%2B-orange?logo=blender&logoColor=white)](https://www.blender.org/)
[![Extensions Platform](https://img.shields.io/badge/Blender%20Extensions-Compatible-green?logo=blender&logoColor=white)](https://extensions.blender.org/)
[![Developer](https://img.shields.io/badge/Developer-ShiroDev-red?logo=youtube&logoColor=white)](https://www.youtube.com/@shiro_dev)

**Quad UV Rectifier** es un add-on y extensión para el **UV Editor** de Blender (compatible con Blender 4.0+) diseñado para enderezar caras UV de tipo quad en cuadrículas limpias (cuadrados o rectángulos perfectos), eliminando cualquier tipo de distorsión rara, diagonal interna o autointersección ("bowties").

---

## ✨ Características Principales

- 🔄 **Topología Anti-Bowtie Matemática**: Evalúa las configuraciones cíclicas válidas (en sentido horario y antihorario) para asignar cada loop a su cuadrante natural sin cruzar nunca aristas o diagonales.
- 🔗 **Soporte UV Sync Selection**: Funciona tanto si tienes activada la sincronización de selección UV (`UV Sync Selection ON`) como si está desactivada (`OFF`).
- 📏 **Proporción 1:1 o Rectangular**:
  - **Rectangular**: Conserva las dimensiones relativas de ancho y alto de cada cara.
  - **Cuadrado (1:1)**: Fuerza cada cara a un cuadrado perfecto.
- 🧩 **Soldado Continuo de Esquinas Compartidas**: Promedia las esquinas adyacentes de quads vecinos para crear tiras y grillas continuas sin huecos ni fisuras.
- 🎯 **Ajuste Opcional a Cuadrícula (Snap)**: Encaja los vértices UV resultantes en múltiplos de paso configurables (ej. 1/16 = 0.0625, 1/32 = 0.03125).
- 🛡️ **Filtrado Seguro de No-Quads**: Ignora triángulos y n-gons de forma no destructiva e informa cuántas caras fueron procesadas y cuántas ignoradas.
- 📦 **Arquitectura Modular Moderna**: Soporte dual para `bl_info` (Blender 4.0 - 4.1) y `blender_manifest.toml` (Blender 4.2+ Extensions Platform).

---

## 📁 Estructura del Proyecto

```text
Quad UV Rectifier/
├── core/
│   ├── __init__.py
│   └── rectifier.py        # Algoritmo matemático, anti-bowtie y unión de esquinas
├── operators/
│   ├── __init__.py
│   └── rectify_ops.py      # Operadores de Blender y soporte multi-objeto
├── ui/
│   ├── __init__.py
│   └── panel.py            # Panel del Sidebar (N) > UV Square
├── .gitignore
├── blender_manifest.toml   # Manifiesto de Blender Extensions (4.2+)
├── properties.py           # Propiedades de escena persistentes
├── README.md
└── __init__.py             # Punto de entrada y registro dinámico
```

---

## 📥 Instalación

### Método 1: Carpeta de Add-ons / Extensiones
1. Copia o enlaza la carpeta `Quad UV Rectifier` dentro de tu directorio de addons o extensiones de Blender:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\<versión>\scripts\addons\`
2. En Blender, ve a **Edit > Preferences > Add-ons**, busca **Quad UV Rectifier** y actívalo.

### Método 2: Como archivo .zip
1. Comprime todo el contenido de la carpeta en un archivo `.zip`.
2. En Blender ve a **Edit > Preferences > Add-ons > Install from Disk** (o **Extensions > Install from Disk** en 4.2+) y selecciona el `.zip`.

---

## 🎮 Modo de Uso

1. Selecciona tu objeto y entra en **Edit Mode** (`Tab`).
2. Abre el **UV Editor** y despliega la barra lateral derecha (`N`).
3. Haz clic en la pestaña **UV Square**.
4. Selecciona las caras quad que deseas alinear.
5. Elige tus opciones (Proporción, Soldar esquinas, Snap a cuadrícula) y pulsa **Enderezar Quads UV** o **Forzar Cuadrado (1:1)**.
