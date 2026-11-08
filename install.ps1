# Installation de reverse-motion sous Windows (PowerShell). Lancer :  powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($c in @("node", "python", "ffmpeg")) {
  if (-not (Get-Command $c -ErrorAction SilentlyContinue)) {
    Write-Host "$c manquant. Installez-le (par exemple : winget install OpenJS.NodeJS.LTS / Python.Python.3.12 / Gyan.FFmpeg)"; exit 1
  }
}
Write-Host "== Moteur de rendu (Node) =="
Push-Location "$Here\engine"; npm install --no-audit --no-fund; npx --yes playwright install chromium; Pop-Location
Write-Host "== Outils d'analyse (Python) =="
python -m pip install -r "$Here\requirements.txt"
# Blender (objets 3D) : module bpy, sinon l'application Blender (BLENDER_PATH)
python -m pip install bpy; if ($LASTEXITCODE -ne 0) { winget install -e --id BlenderFoundation.Blender; Write-Host 'Définir BLENDER_PATH vers blender.exe si besoin' }
python "$Here\scripts\doctor.py"
