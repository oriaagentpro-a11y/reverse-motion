# reverse-motion

**Donnez une vidéo de motion design à Claude : il la reconstruit en code HTML/SVG/WebGL + GSAP
éditable, image par image, et prouve la fidélité par des mesures.**

*English summary below.*

## Ce que fait le skill

1. **Analyse** la vidéo : découpage en scènes, palette exacte, police la plus proche, tempo et
   temps forts de la musique, trajectoires et courbes d'animation (ease GSAP retrouvée par calcul).
2. **Reconstruit** chaque scène en HTML/GSAP : textes placés par leur boîte d'encre mesurée,
   mouvements recalés image par image, effets complexes (mosaïques, liquides, ondes) gardés en
   *plaques WebGL* aux couleurs modifiables.
3. **Vérifie** : rendu image par image (Chromium), comparaison avec l'original (SSIM, Delta E),
   **garde anti-fantômes** (textes en double, éléments en avance ou en retard), rapport par segment.
4. **Rebrande** : un fichier `brand.js` change couleurs et textes sans toucher au rythme
   (contrôle automatique : chaque mouvement doit rester sur la même image).

## Installation

Il faut **Node.js 18+**, **Python 3.9+** et **ffmpeg**.

```bash
# Linux / macOS / WSL
bash install.sh
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File install.ps1
```

Le script installe le moteur (npm), les outils d'analyse (pip) et Chromium, puis lance
`scripts/doctor.py`, qui vérifie tout et fait un rendu de test. Pour vérifier plus tard :
`python3 scripts/doctor.py`.

### L'ajouter à Claude

- **Claude Code** : copier le dossier dans `~/.claude/skills/reverse-motion/` (ou dans
  `.claude/skills/` d'un projet), puis lancer `bash install.sh` une fois.
- **Claude (app)** : importer le zip du dossier comme skill. Les outils ont besoin d'un
  environnement qui exécute du code (Node, Python, ffmpeg).

Ensuite, il suffit de donner une vidéo : « reproduis cette vidéo motion trait pour trait ».

## Essai rapide : l'exemple fourni

`examples/demo/` contient un exemple complet et libre de droits : une vidéo de **64 s**
(640×360, 25 i/s, avec musique) générée par `make_source.py`, sa reproduction
(`scenes/demo.html`), les mesures qui ont servi à l'écrire (`analysis/`) et le manifeste.

```bash
cd examples/demo
python3 make_source.py                       # crée src/source.mp4
python3 ../../scripts/assemble.py manifest.json out
python3 ../../scripts/assemble.py manifest.json out_brand --brand brand.example.js   # version rebrandée
```

Résultat attendu : `out/reproduction.mp4`, `out/compare/side_by_side.mp4` (original | copie |
différences) et `out/report.json` (scores par segment, anomalies, fantômes possibles).

## Les outils

| Étape | Outil |
| --- | --- |
| Vérifier l'installation | `scripts/doctor.py` |
| Musique : tempo, temps, accents | `scripts/beats.py` |
| Police la plus proche | `scripts/get_fonts.sh` puis `scripts/font_search.py` |
| Mesurer des éléments, retrouver les ease | `track_elements.py`, `track_template.py`, `track_textbox.py`, `track_quad.py`, `fit_easing.py` |
| Rendre une scène | `engine/render.mjs` |
| Comparer | `scripts/compare.py` |
| Recaler image par image | `scripts/register.py` |
| Plaques d'effet WebGL | `scripts/extract_plate.py` |
| Garde anti-fantômes | `scripts/ghost_guard.py` |
| Objets et icônes 3D : pose, modèle Blender, rendu Cycles, Three.js | `scripts/fit_object_pose.py`, `scripts/blender_setup.sh`, `scripts/blender_object.py`, `scripts/object_score.py`, `engine/rm-3d.js` (guide : `BLENDER_GUIDE.md`) |
| Régler automatiquement | `scripts/optimize.py` |
| Assembler + rapport | `scripts/assemble.py` |
| Rebrand : recolorer, vérifier le rythme | `scripts/recolor.py`, `scripts/rhythm.py` |

La méthode complète, les résultats mesurés de chaque technique et la liste des pièges sont
dans **`METHODS.md`**. `SKILL.md` est la fiche que Claude lit.

## Usage responsable

Une vidéo que vous reproduisez reste l'œuvre de son auteur. Le skill sert à apprendre,
analyser une animation, refaire **vos** vidéos dont vous avez perdu les sources, ou produire une
version **rebrandée** et originale. Ne publiez pas la copie exacte d'une œuvre d'autrui sans
autorisation. Les segments que le skill « extrait » directement de la vidéo (rendus 3D, logos,
illustrations dessinées à la main) sont signalés dans le rapport.

## Licence

Code sous licence MIT (`LICENSE`). Police Outfit sous SIL OFL 1.1 (`engine/OFL.txt`).
Crédits des dépendances : `CREDITS.md`.

---

## English summary

**reverse-motion** is a Claude skill that rebuilds a motion design video as editable
HTML/SVG/WebGL + GSAP code, frame by frame, and proves fidelity with measurements (SSIM, Delta E,
a ghost detector for doubled or mistimed elements). Effects that are not formulas (mosaics,
liquid light, ripples) are kept as WebGL *plates* with editable colours. A `brand.js` file
rebrands colours and texts while an automatic check guarantees the timing stays identical.

Install: Node 18+, Python 3.9+, ffmpeg, then `bash install.sh` (or `install.ps1` on Windows);
`python3 scripts/doctor.py` checks everything. Try `examples/demo/` (a 64 s royalty-free video and
its reproduction). Docs are in French; `METHODS.md` holds every technique with measured results.
MIT licence; Outfit font under OFL 1.1. Please only reproduce videos you have the rights to, or
publish a rebranded, original version.
