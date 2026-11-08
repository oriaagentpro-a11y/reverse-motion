---
name: reverse-motion
description: Reproduit une vidéo motion design fournie en code HTML/SVG/WebGL + GSAP éditable, image par image, avec mesure automatique de fidélité (SSIM, Delta E, garde anti-fantômes) et version rebrandée. À utiliser quand on donne une vidéo motion et qu'on veut la décalquer, en reprendre la recette ou la décliner aux couleurs d'une marque.
---

# reverse-motion

Tu reçois une vidéo motion design. Tu la reconstruis en code (HTML + SVG/Canvas/WebGL + GSAP),
rendue image par image, et tu prouves la fidélité par des mesures, jamais à l'œil seul.
Méthode : enquêter, mesurer, reconstruire, vérifier, corriger, re-vérifier.

> **RÈGLE N° 1 — TOUT RECRÉER.** Tout ce qui est à l'écran est recréé : fonds, dégradés, formes,
> textes, icônes, objets 3D, effets, transitions, particules. Le résultat doit être si identique
> qu'on croirait la même vidéo dupliquée. Seules exceptions, coupées dans l'original et intégrées
> telles quelles : les **images ou vidéos de personnes réelles** et d'**objets réels filmés ou
> photographiés**. Rien d'autre ne garde des pixels de la vidéo d'origine dans le livrable final.
> Raison : quand on réadapte au brief ou au script de l'utilisateur (textes, couleurs, durées,
> rebrand), un élément resté en pixels ne se modifie pas et décale le rendu ; un élément recréé
> se change en une ligne. Détails : section « Tout recréer » plus bas.

**Avant tout travail, lire `METHODS.md`** : ordre impératif des étapes, résultats mesurés de
chaque technique, pièges déjà rencontrés (P1–P38). Pour tout objet 3D, lire aussi `BLENDER_GUIDE.md`
(techniques de modélisation, matériaux, lumière, rendu Cycles, boucle de correction).

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
| `scripts/fit_object_pose.py` | Pose 3D (rotation, position) d'un objet par image : homographie ECC + solvePnP, ambiguïté levée par la silhouette réelle |
| `scripts/blender_setup.sh` | Installe Blender (`pip install bpy`, sinon exécutable Blender) |
| `scripts/blender_object.py` | Modélise l'objet dans Blender depuis `object.json`, calibre ses matières sur la vidéo, le rend avec Cycles sur sa pose (flou de mouvement, fondu), exporte le GLB |
| `scripts/object_score.py` | Fidélité locale d'un objet 3D (SSIM, Delta E dans sa zone) + planche vidéo / modèle / écart |
| `engine/rm-3d.js` | Objet 3D dans la scène : images Cycles (`frames`) ou modèle Three.js en direct (`live`), sur la pose mesurée |
| `engine/render.mjs` | Rendu image par image (`--fps --w --h --start --end`, `--transparent`, `--holes`, `--brand`, flou `blurAt`) |
| `engine/rm.js` | Texte par boîte d'encre (`fitInk`), pistes (`trackAt`), homographie, recalage (`applyReg`), marque (`applyBrand`, `brandColor`) |
| `engine/rm-gl.js` | Plaques WebGL, shaders (ondes, mosaïque), mode décalque par scène, garde anti-fantômes |
| `scripts/compare.py` | SSIM, Delta E, pixels fantômes par image, vidéo côte à côte, pires images |
| `scripts/register.py` | Recalage image par image (dx, dy, échelle, rotation, opacité), mode encre |
| `scripts/extract_plate.py` | Plaque d'effet 2 ou 3 couleurs par image, ou **en couleurs réelles** (`--rgb`) pour le verre, les halos, la 3D |
| `scripts/ghost_guard.py` | Repère les éléments en code qui ne collent pas à l'original (pendant le travail, la plaque les remplace ; au livrable, chaque élément repéré est à recréer mieux) |
| `scripts/optimize.py` | Réglage automatique des paramètres d'une scène |
| `scripts/compose.py` / `assemble.py` | Calques ; vidéo complète + rapport (segments, coupes, anomalies, fantômes) |
| `scripts/recolor.py` / `rhythm.py` | Rebrand des segments extraits ; contrôle que le rythme est identique |

Exemple complet et libre de droits : `examples/demo/` (64 s, 25 i/s, 640×360, musique).
S'en servir comme modèle de structure (`manifest.json`, `scenes/`, `analysis/`).

## Méthode

1. **Cartographier** : `ffprobe` (i/s et taille : ne jamais supposer 30 i/s ni 736×414),
   planches-contact horodatées, coupes, palette exacte (couleur modale), `beats.py`.
   Écrire `analysis/scenes.json` : une entrée par scène (fond, type, contenu).
   **Inventaire 3D** : chaque icône ou objet en relief (faces latérales, ombres propres, reflets,
   rotation qui montre l'épaisseur) va dans `analysis/objects_3d.json` : nom, images début-fin,
   image de référence nette, boîte, pièces (corps, pictogramme, badge, texte), matières.
2. **Police** : `font_search.py` sur 3-4 mots nets. Garder la plus proche sans interrompre
   l'utilisateur ; la nommer dans le rapport. Préférer une police variable.
3. **Mesurer** chaque élément (`track_*`), puis `fit_easing.py` sur chaque piste. Utiliser les
   valeurs **ajustées** (départ 48,2133 s, pas 48,2), jamais des valeurs rondes « à l'œil ».
4. **Reconstruire** : un HTML par scène, temps global de la source. Réglages dans un objet `P`
   (surchargé par `TUNED` puis par l'URL `#{...}`). La page expose
   `window.__rm = { ready, seek(t) { ... } }` — **seek ne renvoie rien** (P20).
   Mouvement irrégulier → décalque direct (positions mesurées rejouées à chaque image).
   Effet qui n'est pas une formule → **recréé** : shader WebGL (`rm-gl.js`), particules ou formes
   animées en code, ajustés sur la mesure. Verre, reflets, halos, dégradés → shaders ou Blender
   (règle n° 1). Les plaques (`extract_plate.py`) ne servent plus qu'à **mesurer** et
   d'échafaudage pendant le travail : aucune ne reste dans le livrable, sauf pour une personne
   ou un objet réel filmé (zone découpée dans l'original). Textes : `text_inventory.py`
   → liste des mots → `track_words.py` → `fit_text_pose.py` (taille, inclinaison) → `track_lines.py`
   (homographie des lignes, CSS matrix3d). Exemple : METHODS.md § 12.

4 bis. **Objets 3D** (automatique pour tout l'inventaire 3D, sans que l'utilisateur le demande) :
   `fit_object_pose.py` (pose par image, `--depth`, `--radius`, `--ignore` pour un badge collé) →
   `object.json` (formes et couleurs mesurées sur l'image de référence) → `blender_object.py
   --only-ref --calibrate video:3` (matières calibrées) → rendu de toutes les images avec `--glb`
   → `object_score.py` → corriger UNE cause à la fois (BLENDER_GUIDE § 15) → `RM3D.object` dans la
   scène (canvas dans `fgIds`). Exemple et chiffres : METHODS.md § 14.
5. **Comparer** : `render.mjs` puis `compare.py`. Regarder les pires images ET la vidéo côte à côte.
   Chaque objet 3D a son propre score (`object_score.py`) et sa planche, au rapport.
6. **Corriger** dans cet ordre : recalage (`register.py`, mode encre) → trous → plaque →
   **garde anti-fantômes** (`ghost_guard.py`, puis trous et plaque à nouveau, 2 passes) → rendu.
   Pendant le travail, la garde montre l'original là où un élément ne colle pas. Pour le
   livrable, chaque élément caché par la garde est un **défaut à corriger en recréant mieux**
   (pose, forme, matière, timing), jamais un état final (règle n° 1).
7. **Assembler** : `assemble.py manifest.json out/` → `reproduction.mp4` (avec le son),
   `compare/side_by_side.mp4`, `report.json`, et `ghosts.png` s'il reste des plages suspectes.
8. **Contrôle final obligatoire** : 0 anomalie, chaque plage de `ghost_runs` regardée à l'œil et
   corrigée ou expliquée, puis relecture de la vidéo côte à côte en entier. Le rapport
   `recreation` de `assemble.py` doit dire **« recréé » pour chaque segment** ; seuls les
   extraits de personnes ou d'objets réels (`"footage"` déclaré) gardent des pixels d'origine. Un score global élevé
   ne prouve rien : un texte en double couvre 2 % de l'image et coûte 0,01 de SSIM.
9. **Rebrand** (si demandé) : `brand.js` (`colors`, `texts`, `mode`), puis
   `assemble.py manifest.json out_brand/ --brand brand.js`. Le rapport `rhythm.json` doit dire
   « identique » (même décalage 0, événements à l'image près).

## Tout recréer (règle n° 1)

Pourquoi : le skill sert ensuite à **réadapter** la vidéo au brief ou au script de l'utilisateur
(autres textes, autres durées, autres couleurs, autre marque). Un élément gardé en pixels de
l'original ne bouge pas avec le reste : il décale le rendu, garde l'ancien texte ou l'ancienne
couleur, laisse des fantômes. Tout ce qui est recréé se modifie en code.

| Élément de la vidéo | Comment le recréer |
| --- | --- |
| Fond uni, dégradé, vignettage, grain | CSS / canvas / shader, couleurs modales mesurées |
| Formes, cartes, boutons, cadres, traits | SVG ou canvas, poses mesurées (`track_*`, `track_quad.py`) |
| Textes (même en perspective 3D) | vraie police, `track_words` → `fit_text_pose` → `track_lines` |
| Icônes plates, logos, pictogrammes | redessinés en SVG (tracé vectoriel sur l'image de référence) |
| Icônes et objets 3D | Blender + Three.js (étape 4 bis) |
| Effets (ondes, verre, halos, lumières, particules, flous) | shaders WebGL, Blender, flou de mouvement mesuré |
| Illustrations, dessin animé | redessinés en SVG, animés image par image si besoin |
| **Photo ou vidéo d'une personne réelle, d'un objet réel filmé** | **coupé dans l'original** (seule exception) |

Couper un extrait réel : boîte et images mesurées, découpe `ffmpeg` (crop + plage) ou segment
`extract` avec `"footage": "personne"` / `"objet réel"` dans `manifest.json` ; la découpe est posée
dans la scène à sa position mesurée, sous ou sur les éléments recréés. Tout ce qui l'entoure
(fond, cadre, texte, ombre) est recréé.

Le rapport (`assemble.py`, clé `recreation`) dit pour chaque segment « recréé », « extrait réel
(…) » ou « PIXELS DE L'ORIGINAL » ; ce dernier état bloque la livraison.

## Règles

- **Tout recréer (règle n° 1)** : voir l'encadré en tête et la section « Tout recréer ».
- **Fidélité maximale = indiscernable** : côte à côte, on doit croire à la même vidéo dupliquée.
  Mêmes positions à l'image près, mêmes couleurs (Delta E), mêmes courbes, même rythme.
- Rien n'est ignoré ni « à peu près » : chaque défaut vu ou mesuré est corrigé ou signalé.
- Ne jamais annoncer un score sans l'avoir mesuré ; donner le score par segment et la liste
  des défauts restants.
- **Objets et icônes 3D** : toujours reproduits en 3D (Blender + Three.js), à fidélité maximale,
  même si l'utilisateur ne le demande pas. Score local par objet au rapport. Une image où la
  garde cache le modèle est un défaut à corriger (meilleure pose, forme, matière), pas un état final.
- Seuls peuvent être **coupés dans l'original** (segment `extract` avec `"footage"`, ou zone
  découpée dans une scène) : les images et vidéos de **personnes réelles** et d'**objets réels**
  filmés ou photographiés. Le reste (y compris un dessin animé ou une illustration) est recréé.
- Couleurs dessinées en JavaScript (canvas) : toujours via `RM.brandColor('#...')`, sinon le
  rebrand ne les voit pas.
- Droits : la copie exacte d'une œuvre d'autrui n'est pas à publier ; pour un usage commercial,
  livrer la version **rebrandée**. Le rappeler une fois à l'utilisateur.
