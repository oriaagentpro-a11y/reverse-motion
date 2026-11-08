#!/usr/bin/env bash
# Install Blender for reverse-motion (3D objects modelled and rendered with Cycles: scripts/blender_object.py).
# 1. Blender as a Python module: `pip install bpy` (wheel ~400 MB, Python version must match the wheel:
#    bpy 4.x/5.x -> Python 3.11 / 3.13; check https://pypi.org/project/bpy/). Works headless, no display needed.
# 2. Otherwise a Blender executable: system package or official archive; blender_object.py re-launches itself with
#    `blender -b --python ... --` when `import bpy` fails (set BLENDER_PATH if it is not on the PATH).
set -u
PY=${PYTHON:-python3}
if $PY -c "import bpy" 2>/dev/null; then
  echo "Blender déjà disponible : module bpy $($PY -c 'import bpy; print(bpy.app.version_string)')"; exit 0
fi
echo "Installation de Blender comme module Python (pip install bpy)..."
if $PY -m pip install bpy 2>/dev/null || $PY -m pip install --break-system-packages bpy; then
  $PY -c "import bpy; print('OK : bpy', bpy.app.version_string)" && exit 0
fi
echo "pip install bpy a échoué (version de Python sans wheel ?). Tentative avec un exécutable Blender..."
if command -v blender >/dev/null; then echo "OK : $(blender -v | head -1) (blender_object.py l'utilisera)"; exit 0; fi
if command -v apt-get >/dev/null; then sudo apt-get install -y blender && exit 0; fi
if command -v brew >/dev/null; then brew install --cask blender && echo "export BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender" && exit 0; fi
if command -v winget >/dev/null; then winget install -e --id BlenderFoundation.Blender && exit 0; fi
echo "Installez Blender (https://www.blender.org/download/) puis : export BLENDER_PATH=/chemin/vers/blender"; exit 1
