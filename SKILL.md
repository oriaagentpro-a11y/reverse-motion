---
name: reverse-motion
description: Reproduit une vidéo motion design fournie en code HTML/SVG/WebGL + GSAP éditable, image par image, avec mesure automatique de fidélité (SSIM, Delta E, garde anti-fantômes) et version rebrandée. À utiliser quand on donne une vidéo motion et qu'on veut la décalquer, en reprendre la recette ou la décliner aux couleurs d'une marque.
---

# reverse-motion

Tu reçois une vidéo motion design. Tu la reconstruis en code (HTML + SVG/Canvas/WebGL + GSAP),
rendue image par image, et tu prouves la fidélité par des mesures, jamais à l'œil seul.
Méthode : enquêter, mesurer, reconstruire, vérifier, corriger, re-vérifier.

**Avant tout travail, lire `METHODS.md`** : ordre impératif des étapes, résultats mesurés de
chaque technique, pièges déjà rencontrés (P1–P24).

## 0. Installation (une fois par machine)

`bash install.sh` (Linux, macOS, WSL) ou `install.ps1` (Windows), puis `python3 scripts/doctor.py`
doit finir par « Tout est prêt ». Requis : Node 18+, Python 3.9+, ffmpeg. Chromium est trouvé tout
seul (Playwright, Chrome, Chromium ou Edge ; sinon `CHROME_PATH`). Si un élément manque, le dire
à l'utilisateur avec la commande exacte affichée par `doctor.py`.

## Outils (chemins relatifs au dossier du skill)

| Fichier | Rôle |
| --- | --- |
| `scripts/doctor.py` | Vérifie l'installation et fait un rendu de test |
| `scripts/beats.py` | Tempo, temps, accents forts de la musique (en numéros d'image) |
| `scripts/get_fonts.sh` + `font_search.py` / `match_font.py` | Catalogue Google Fonts, police la plus proche |
| `scripts/track_elements.py` / `track_template.py` | Boîtes des éléments ; suivi par gabarit (curseur, icône) |
| `scripts/track_textbox.py` / `track_quad.py` | Boîte d'encre d'un texte ; 4 coins d'une carte (perspective) |
| `scripts/text_inventory.py` | Inventaire OCR (tesseract) de tous les mots : quand, où, couleur |
| `scripts/track_words.py` | Suivi de chaque mot image par image depuis une image de référence (corrélation + échelle) |
| `scripts/track_lines.py` | Homographie par image de chaque ligne de texte (ECC) : perspective 3D exacte |
| `scripts/fit_text_pose.py` | Taille et inclinaison réelles d'un mot à partir de sa boîte et de son encre |
| `scripts/fit_easing.py` | Ease GSAP, début, durée, valeurs d'un mouvement mesuré |
| `scripts/fit_globe.py` / `globe_js.py` | Pose 3D d'un globe par image |
| `engine/render.mjs` | Rendu image par image (`--fps --w --h --start --end`, `--transparent`, `--holes`, `--brand`, flou `blurAt`) |
| `engine/rm.js` | Texte par boîte d'encre (`fitInk`), pistes (`trackAt`), homographie, recalage (`applyReg`), marque (`applyBrand`, `brandColor`) |
| `engine/rm-gl.js` | Plaques WebGL, shaders (ondes, mosaïque), mode décalque par scène, garde anti-fantômes |
| `scripts/compare.py` | SSIM, Delta E, pixels fantômes par image, vidéo côte à côte, pires images |
| `scripts/register.py` | Recalage image par image (dx, dy, échelle, rotation, opacité), mode encre |
| `scripts/extract_plate.py` | Plaque d'effet 2 ou 3 couleurs par image, ou **en couleurs réelles** (`--rgb`) pour le verre, les halos, la 3D |
| `scripts/ghost_guard.py` | Cache un élément en code là où il ne colle pas à l'original (la plaque montre l'original) |
| `scripts/optimize.py` | Réglage automatique des paramètres d'une scène |
| `scripts/compose.py` / `assemble.py` | Calques ; vidéo complète + rapport (segments, coupes, anomalies, fantômes) |
| `scripts/recolor.py` / `rhythm.py` | Rebrand des segments extraits ; contrôle que le rythme est identique |

Exemple complet et libre de droits : `examples/demo/` (64 s, 25 i/s, 640×360, musique).
S'en servir comme modèle de structure (`manifest.json`, `scenes/`, `analysis/`).

## Méthode

1. **Cartographier** : `ffprobe` (i/s et taille : ne jamais supposer 30 i/s ni 736×414),
   planches-contact horodatées, coupes, palette exacte (couleur modale), `beats.py`.
   Écrire `analysis/scenes.json` : une entrée par scène (fond, type, contenu).
2. **Police** : `font_search.py` sur 3-4 mots nets. Garder la plus proche sans interrompre
   l'utilisateur ; la nommer dans le rapport. Préférer une police variable.
3. **Mesurer** chaque élément (`track_*`), puis `fit_easing.py` sur chaque piste. Utiliser les
   valeurs **ajustées** (départ 48,2133 s, pas 48,2), jamais des valeurs rondes « à l'œil ».
4. **Reconstruire** : un HTML par scène, temps global de la source. Réglages dans un objet `P`
   (surchargé par `TUNED` puis par l'URL `#{...}`). La page expose
   `window.__rm = { ready, seek(t) { ... } }` — **seek ne renvoie rien** (P20).
   Mouvement irrégulier → décalque direct (positions mesurées rejouées à chaque image).
   Effet qui n'est pas une formule → plaque (`extract_plate.py`) dans `RMGL.decalque`.
   Vidéo « 3D » (verre, reflets, halos, dégradés) → plaques `--rgb` ; textes : `text_inventory.py`
   → liste des mots → `track_words.py` → `fit_text_pose.py` (taille, inclinaison) → `track_lines.py`
   (homographie des lignes, CSS matrix3d). Exemple : METHODS.md § 12.
5. **Comparer** : `render.mjs` puis `compare.py`. Regarder les pires images ET la vidéo côte à côte.
6. **Corriger** dans cet ordre : recalage (`register.py`, mode encre) → trous → plaque →
   **garde anti-fantômes** (`ghost_guard.py`, puis trous et plaque à nouveau, 2 passes) → rendu.
7. **Assembler** : `assemble.py manifest.json out/` → `reproduction.mp4` (avec le son),
   `compare/side_by_side.mp4`, `report.json`, et `ghosts.png` s'il reste des plages suspectes.
8. **Contrôle final obligatoire** : 0 anomalie, chaque plage de `ghost_runs` regardée à l'œil et
   corrigée ou expliquée, puis relecture de la vidéo côte à côte en entier. Un score global élevé
   ne prouve rien : un texte en double couvre 2 % de l'image et coûte 0,01 de SSIM.
9. **Rebrand** (si demandé) : `brand.js` (`colors`, `texts`, `mode`), puis
   `assemble.py manifest.json out_brand/ --brand brand.js`. Le rapport `rhythm.json` doit dire
   « identique » (même décalage 0, événements à l'image près).

## Règles

- Rien n'est ignoré ni « à peu près » : chaque défaut vu ou mesuré est corrigé ou signalé.
- Ne jamais annoncer un score sans l'avoir mesuré ; donner le score par segment et la liste
  des défauts restants.
- Visuels non recréables (rendus 3D d'autres projets, logos de tiers, dessin animé à la main) :
  les **extraire** de la vidéo (segment `extract`) et le signaler dans le rapport.
- Couleurs dessinées en JavaScript (canvas) : toujours via `RM.brandColor('#...')`, sinon le
  rebrand ne les voit pas.
- Droits : la copie exacte d'une œuvre d'autrui n'est pas à publier ; pour un usage commercial,
  livrer la version **rebrandée**. Le rappeler une fois à l'utilisateur.
