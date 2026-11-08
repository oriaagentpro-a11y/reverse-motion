#!/usr/bin/env bash
# Installation de reverse-motion (Linux, macOS, WSL). À lancer depuis n'importe où :
#   bash install.sh            installe tout
#   bash install.sh --check    vérifie seulement
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"

if [[ "${1:-}" != "--check" ]]; then
  command -v node >/dev/null || { echo "Node.js 18+ est requis : https://nodejs.org"; exit 1; }
  command -v "$PY" >/dev/null || { echo "Python 3.9+ est requis : https://python.org"; exit 1; }
  if ! command -v ffmpeg >/dev/null; then
    echo "ffmpeg manquant. Installez-le :"
    echo "  macOS : brew install ffmpeg   |   Ubuntu/Debian : sudo apt install ffmpeg   |   Windows : winget install ffmpeg"
    exit 1
  fi
  echo "== Moteur de rendu (Node) =="
  (cd "$HERE/engine" && npm install --no-audit --no-fund)
  echo "== Outils d'analyse (Python) =="
  "$PY" -m pip install -r "$HERE/requirements.txt" 2>/dev/null \
    || "$PY" -m pip install --break-system-packages -r "$HERE/requirements.txt" \
    || "$PY" -m pip install --user -r "$HERE/requirements.txt"
  echo "== Blender (objets 3D : modélisation et rendu Cycles) =="
  PYTHON="$PY" bash "$HERE/scripts/blender_setup.sh" || echo "(Blender non installé : les objets 3D seront rendus avec Three.js seulement)"
  echo "== Chromium (rendu et mesures) =="
  if [[ -z "${CHROME_PATH:-}" ]]; then
    (cd "$HERE/engine" && npx --yes playwright install chromium) || echo "(installation de Chromium impossible : définissez CHROME_PATH vers un Chrome existant)"
  fi
fi
"$PY" "$HERE/scripts/doctor.py"
