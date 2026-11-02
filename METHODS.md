# reverse-motion — Méthodes, résultats et leçons

Ce document est la mémoire technique de l'outil. Chaque méthode est décrite avec : **quand**
l'utiliser, **comment**, le **résultat mesuré** sur la vidéo de référence (publicité d'un studio de motion design,
47 s, 736×414, 30 i/s), et les **pièges** rencontrés. Règle absolue : rien n'est ignoré ni
banalisé ; toute zone sous le seuil est analysée, corrigée, puis re-mesurée.

Mesures : SSIM moyen par image (0–1), Delta E 2000 moyen. Seuil visé : SSIM ≥ 0,98 par image.

---

## 0. Ordre de travail (pipeline)

1. **Cartographier** (planches horodatées, coupes, palette, tempo) → `analysis/scenes.json`.
2. **Police** : `font_search.py` sur tout le catalogue Google Fonts (742 familles sans-serif).
3. **Mesurer** chaque élément : boîtes (`track_elements.py`), gabarits (`track_template.py`),
   quadrilatères (`track_quad.py`), courbes (`fit_easing.py`), globe (`fit_globe.py`).
4. **Reconstruire** chaque scène en HTML/SVG/WebGL + GSAP (réglages dans `P`).
5. **Recaler** chaque texte/élément image par image en **mode encre** (`register.py`).
6. **Percer les trous** : rendu `--holes` des éléments reconstruits.
7. **Extraire les plaques** d'effet (`extract_plate.py`) en perçant ces trous.
8. **Rendre** (`render.mjs`, flou de mouvement si besoin), **comparer** (`compare.py`).
9. **Corriger** les zones faibles (retour en 3–7), **assembler** (`assemble.py`).

L'ordre 5 → 6 → 7 est impératif (voir piège P7).

---

## 1. Cartographie

- `ffprobe` pour le format ; planches-contact `fps=3..10` avec horodatage `drawtext`.
- Coupes : `select='gte(scene,0)',metadata=print` → score de changement par image ;
  > 0,12 = coupe ou transition rapide.
- Palette : couleur **modale exacte** (np.unique) sur des zones plates, pas une moyenne.
- Tempo : `librosa.beat.beat_track` (118 BPM ici) ; les coupes tombent sur les temps.

## 2. Police (méthode « catalogue complet »)

- `font_search.py` : clone *sparse* de google/fonts, toutes les familles sans-serif latines
  (895 fichiers), polices variables réglées à la graisse demandée ±100.
- Score par mot = IoU des formes – pénalité de rapport largeur/hauteur ; moyenne sur 4 mots.
- **Toujours valider à l'œil** les 5 premières (planche `font_panel.png`) : le score seul
  a classé Mona Sans 1er, l'œil a retenu **Outfit** (a à une boucle, e, y identiques).
- Une police **variable** fait de la graisse un paramètre continu réglable.
- Placement du texte par **boîte d'encre** (`RM.fitInk`) : largeur d'encre mesurée → taille
  de police calculée ; position par coin haut-gauche de l'encre. Erreur résiduelle ≤ 1 px.

## 3. Mesure du mouvement

| Outil | Mesure | Quand |
| --- | --- | --- |
| `track_elements.py` | boîtes des composantes claires/foncées | textes, formes nettes |
| `track_template.py` | position + échelle par gabarit | curseurs, icônes |
| `track_quad.py` | 4 coins (perspective) | cartes, boutons, étiquettes rigides |
| `fit_easing.py` | ease GSAP + début + durée + valeurs | transformer une piste en courbe éditable |
| `fit_globe.py` | pose 3D complète d'un globe | sphères texturées |

`fit_easing.py` a retrouvé, avec une erreur < 1 px : descente de « Every » `power3.out` 1,37 s,
glissement du bouton `circ.inOut` 0,73 s, pop de « as » `expo.out` 0,27 s, zoom `circ.inOut`.

## 4. Décalque des trajectoires (mesuré à chaque image)

Quand une courbe ne suffit pas, la scène rejoue la mesure image par image :
- **Pistes directes** (`RM.trackAt`) : valeurs mesurées par image, interpolées entre images
  (sous-images pour le flou de mouvement). Ex. échelle du zoom arrière, entrée de la carte.
- **Homographie** (`RM.quadMatrix3d`) : un élément est plaqué sur les 4 coins mesurés
  (`track_quad.py`) → position, rotation, échelle et perspective exactes.
- **Caméra mesurée** (S06) : centre et rayon de la bulle mesurés par image pilotent tout le
  « monde » des orbites.

## 5. Recalage image par image (`register.py`)

Pour chaque image et chaque élément : correction (dx, dy, échelle, rotation) qui maximise la
ressemblance dans la zone de l'élément. Départ = solution de l'image précédente ; grille
grossière (±12 px) à la première image ou si le score décroche ; pas décroissants ensuite.
Rejoué par `RM.applyReg(t)` en propriétés CSS `translate/scale/rotate` (se composent avec GSAP).

- **Mode encre** (`"ink": {"color", "tol"}`) : ne compare que les pixels de la couleur de
  l'élément (masque doux) → indépendant du fond, des plaques et des trous. **Obligatoire**
  avant d'extraire les plaques.
- **Garde-fous** : échelle ∈ [0,8 ; 1,25], décalage ∈ ±40 px (réglables par élément). Un
  élément peut être déplacé, **jamais caché** (piège P5).
- Éléments occultés (étiquette derrière une autre) : limiter la plage d'images à la
  partie visible, sinon le recalage dérive (piège P8).
- **Robustesse** (obligatoire, intégrée) :
  1. image **sautée** si l'encre de l'élément est quasi absente de l'original (< 35 % de la
     sienne) : élément masqué, en fondu ou pas encore apparu ;
  2. correction **rejetée** si le score < 0,45 ou si un paramètre touche une borne ;
  3. une image rejetée ne sert pas de départ à la suivante ;
  4. **filtre d'aberrations** : correction à plus de 4 px de la médiane de ses voisines (±3 images)
     supprimée ;
  5. `postfilter.py` applique les mêmes règles a posteriori à un recalage déjà calculé
     (S04 : 179 corrections douteuses retirées sur 336).
- **Toujours re-mesurer après recalage** : sur S05, les corrections restantes faisaient
  *baisser* la phase zoomée (0,94 → 0,86) ; elles ont été retirées (score revenu à 0,94).

## 6. Plaques d'effet WebGL (`extract_plate.py` + `rm-gl.js`)

**Pourquoi** : certains effets sont des traitements d'image (mosaïque zoomée dont la taille
de bloc change à chaque image : 24 → 12 → 13 px ; lumière liquide ; ondes déformant la
grille ; bords flous irréguliers) dont la forme exacte n'est pas une formule.

**Comment** :
1. Pour chaque image, chaque pixel est projeté sur la droite couleur A → couleur B
   (ex. violet #5000B0 → blanc) : on obtient une **matte** 0–1. Le modèle deux couleurs
   reproduit l'original à SSIM 0,997.
2. Les éléments reconstruits en code (textes, icônes, curseurs, boutons) sont **retirés** :
   rendu `--holes` de ces éléments, masque dilaté de 3–6 px, comblement par inpainting.
3. La matte est stockée image par image (PNG en data-URL dans un .js : pas de souci
   `file://` ni de texture « tainted »).
4. Un **shader WebGL** recompose `mix(A, B, matte)` en échantillonnage exact (NEAREST, aucun
   flou ni décalage). Les couleurs A et B restent **modifiables** (rebranding).

**Deux modes par scène** (`RMGL.decalque`) : `usePlates: true` (décalque, fidélité maximale)
ou `false` (code pur, formes paramétriques, pour changer les visuels).

Résultats :
| Zone | Avant (formes dessinées) | Après (plaque WebGL) |
| --- | --- | --- |
| Ondes d'intro (0–1,3 s) | 0,89–0,94 | **0,98–0,99** |
| Mosaïque (2,6–3,2 s) | 0,86 | **0,97** |
| Sortie de la carte « blank space » | 0,81–0,89 | **0,97+** |
| S04 poubelle/étiquettes + S05 lumière | 0,92 / 0,93 | **0,967** (plaques + recalage filtré) |
| S05 surlignage + contour pointillé (plaque) | 0,94 | **0,95** (reste : forme des lettres) |

### Perçage anti-fantômes (`--holes-ink COULEUR:TOL:RAYON`)
Si un texte reconstruit est décalé de quelques pixels, les trous (percés là où il est) laissent un
morceau du texte original dans la plaque → **lettres doublées**. L'extracteur perce aussi les pixels
de la couleur du texte dans l'original, à moins de RAYON px d'un élément reconstruit (marge 11 px pour
que le comblement ne traîne pas de liseré). Les scores baissent un peu (S15 0,957 → 0,9385,
S07 0,986 → 0,983, S14 0,967 → 0,961) : c'est la valeur **honnête**, les fantômes « gagnaient » des
points en recouvrant l'original. Rendu sans aucun doublon : règle obligatoire.

### Décalque des boîtes de texte (`track_textbox.py`)
Pour un texte qui change de taille/position au-delà de ce que le recalage local accepte (±40 px) :
la boîte d'encre de l'original est mesurée à chaque image et rejouée par `RM.fitInk` — ajustement
sur la **hauteur** (la largeur est gonflée par le flou et dépend de la police). Ex. « +400% » géant
(596 px de large réels, 558 px dans la première version).

### Plaques trois couleurs (`--third`)
Chaque pixel = A + wB·(B−A) + wC·(C−A) (moindres carrés, poids bornés), stocké sur 2 canaux, rendu par
le même shader (3 couleurs modifiables). **Mesuré** sur S14 (bille lavande) : pas de gain (0,967 → 0,925)
car la transition d'entrée contient des éclats bruns hors palette et le dégradé de la bille n'est pas
mieux représenté que par le code. **Gain** en revanche pour la main-curseur de S20 (gant blanc, contour
noir, fond violet : palette {violet, blanc, noir}) — le suivi par gabarit y échouait (gant blanc sur
bouton blanc) : S20 0,978 → 0,980. À réserver aux teintes vraiment planes ; toujours comparer.

### Effets typographiques non rigides
« BRANDS » (S08) : les lettres glissent chacune de leur côté et s'estompent une à une. Méthodes essayées :
piste d'échelle mesurée (hauteur des lettres), recalage par lettre (position + opacité), modèle de mot
(centre + espacement + opacité par lettre, opacités par moindres carrés). Le modèle rigide casse quand
les lettres défilent indépendamment → **mode décalque : plaque** sur ces 26 images, texte en code dès
que le mot est posé ; **mode code** : modèle de mot ajusté. Résultat S07-S08 : 0,921 → **0,986**.

### Synchronisation mesurée (S14)
Les instants viennent de mesures sur l'original, pas de l'œil : apparition du compteur (image 836,
valeur finale en 0,15 s), retournement de la bille centré image 875, « CTR up » image 882,
compteur 3.2x images 886–900.

## 6 bis. Rebranding (`brand.js`)

`window.BRAND = { mode, colors, texts }` chargé avant `rm.js` :
- `colors` : couleur source → couleur de marque, appliqué aux formes, aux textes **et aux
  plaques WebGL** (le shader reçoit les couleurs remappées) ;
- `texts` : id → nouveau texte ; la taille vient du mot **original** (même corps), l'ancrage
  (bord gauche ou centre) est conservé ; le recalage ne s'applique plus à ce texte ;
- `mode: 'code'` force les formes paramétriques (aucune plaque) pour changer aussi les formes.
Exemple : `engine/brand.example.js`.

## 7. Flou de mouvement (`render.mjs`, `__rm.blurAt(t)`)

La scène déclare `[échantillons, obturateur]` ; l'image = moyenne de N rendus répartis sur
l'obturateur (comme une caméra / After Effects). **Ne l'activer que si l'original est flou** :
sur la source, le zoom arrière et l'entrée de « blank space » sont **nets** (le flou y faisait
perdre des points). Vérifier à l'œil chaque plage avant d'activer.

## 8. Globe 3D (`fit_globe.py` + shader)

1. Carte du monde `world-atlas land-50m` (TopoJSON) rastérisée en équirectangulaire 4096×2048
   (anneaux déroulés à l'antiméridien, Antarctique fermé par le pôle).
2. Modèle de caméra **perspective** : rayon depuis une caméra à `dist` rayons de la sphère ;
   `dist → ∞` = orthographique. Pose = (longitude, latitude, roulis, rayon, cx, cy, dist).
3. Recalage par image (Nelder-Mead, départ = image précédente) sur le masque des continents,
   en masquant le texte « worldwide. ».
4. La scène dessine le globe avec **la même formule** en GLSL (16 échantillons/pixel).

Modèles disponibles dans `fit_globe.py` :
| Modèle | Fonction | Paramètres |
| --- | --- | --- |
| Orthographique / perspective centrée | `render` | lon, lat, roulis, rayon, cx, cy, [dist] |
| Scène 3D vraie (caméra au centre de l'image) | `render_offaxis` | lon, lat, roulis, X, Y, Z, focale |
| « Sphérisation » radiale (effet 2D) | `render_radial` | lon, lat, roulis, rayon, cx, cy, angle au bord, profil, aplatissement |

Enquête menée sur la vidéo de référence (erreur = part de pixels mal classés, image 1163) :
| Modèle | Erreur |
| --- | --- |
| Orthographique (départ grille) | 0,12 — partait sur l'Asie |
| Perspective centrée (dist ≈ 2,2 puis 9) | 0,052 |
| Scène 3D vraie, globe décentré | 0,044 |
| Sphérisation radiale | 0,037 |
| Carte 1:110 M / 1:50 M / 1:10 M | identique (0,052) → le détail des côtes n'est pas en cause |

Conclusion mesurée : le globe source **n'est pas une sphère géométrique** — l'Alaska et la Russie y
sont séparés d'une large bande, impossible sur une vraie sphère (détroit de Béring). C'est une carte
déformée par un effet. Donc :
- **mode code** : globe 3D WebGL recalé image par image (53 poses), même formule que le Python
  (écart shader/Python 0,007), SSIM 0,852 ; idéal pour un rebranding ;
- **mode décalque** : plaque mesurée du globe et des arcs d'orbite, « worldwide. » en code recalé.
- L'original est **net** (aucun flou de mouvement sur le globe) : vérifié, flou désactivé (+0,02).
- Les « anneaux » sont deux arcs d'une orbite 3D (capsules blanches à contour violet) qui passent
  derrière la sphère : modélisés comme tels en mode code.

## 9. Pièges rencontrés (à ne jamais refaire)

- **P1** GSAP + SVG : `scale/rotation` tournent autour du coin de la boîte → `svgOrigin`.
- **P2** `fromTo` affiche ses valeurs de départ immédiatement → `immediateRender: false`.
- **P3** `fetch()` interdit en `file://` → données en `<script>` (.js).
- **P4** Un cercle plus grand que l'écran reste visible après son animation → le masquer.
- **P5** L'optimiseur « gagne » en cachant un élément (échelle → 0, ondes effacées) :
  score combiné SSIM + erreur de pixels, bornes sur les paramètres, contrôle à l'œil.
- **P6** Plusieurs programmes WebGL sur un même canvas : chaque dessin doit réactiver
  **son** programme et **son** quad (sinon « location is not from the associated program »).
- **P7** Plaque percée avant recalage : les trous sont au mauvais endroit, il reste un
  fantôme du texte original dans la plaque, puis le recalage le poursuit → toujours
  recaler (mode encre) **avant** de percer.
- **P8** Recaler un élément occulté le fait dériver vers les bornes → plage visible seulement.
- **P9** Mode trous : le fond de `<html>` doit être transparent, sinon les PNG n'ont pas
  d'alpha et **aucun trou n'est percé** (l'extracteur s'arrête désormais en erreur).
- **P10** Calques composés (`--transparent`) ≠ rendu des trous (`--holes`) : deux modes séparés.
- **P11** Un réglage automatique peut dégrader une autre zone (« starts » réduit à 165 px en
  extra-gras) : re-mesurer sur l'original et défaire.
- **P12** Raccords : chaque segment doit couvrir exactement ses images ; vérifier les
  images de coupe une par une (la carte « blank space » dure 2 images de plus que prévu ;
  l'original ne finit pas sur du noir).
- **P14** Vérifier qu'un shader reproduit exactement le modèle mesuré (comparer Python ↔ WebGL
  sur la même pose) avant de chercher l'erreur ailleurs.
- **P15** Passer `--init valeur` (pas `--init=valeur`) : l'outil ignore la forme avec « = ».
- **P16** Un identifiant de forme mal recopié (`band` au lieu de `shape`) : la forme en code reste
  dessinée par-dessus la plaque ET perce la plaque. Vérifier dans le navigateur que chaque id de
  `shapeIds`/`fgIds` existe (S14 : 0,950 → 0,967 après correction).
- **P17** Recaler plusieurs éléments dans le même processus peut fausser les suivants (constaté avec le
  paramètre d'opacité sur les lettres de BRANDS : « encre visible 0 » à tort) → un processus par élément
  quand un résultat paraît incohérent ; les images sont désormais lues une seule fois, dans l'ordre.
- **P18** Extraits découpés par temps (`-ss`) : une image de décalage possible au raccord (anomalie
  image 1190, SSIM 0,92 au lieu de 0,99) → découpe par **numéro d'image** (`select=between(n,a,b)`).
- **P19** Lire la séquence originale image par image avant de modéliser une transition : la fin de S21
  n'est pas une carte qui monte avec son texte, mais un **rideau** qui monte devant un texte qui glisse
  de 36 px → bord du rideau et glissement mesurés, texte masqué par le bord (clipPath).
- **P13** `pkill -f motif` tue aussi le shell dont la ligne contient le motif → lister les
  PID par un script séparé.

- **P20** `seek: t => tl.seek(t)` renvoie la timeline GSAP : Playwright tente de la sérialiser et le
  rendu se fige sans erreur. `seek(t) { tl.seek(t, false); }` (rien renvoyé) ; les outils appellent
  désormais `void window.__rm.seek(t)`.
- **P21** Une animation qui commence pile au début d'un segment (`fromTo` dans une timeline imbriquée)
  n'est pas rendue à la première image du segment → calculer l'état dans `seek` (ex. `gsap.parseEase`).
- **P22** En décalque, la plaque est SOUS le DOM : un texte en code qui devrait être caché par une forme
  (carte posée par-dessus, vague, lumière) flotte au premier plan → texte en double. Gérer la visibilité
  des textes masqués (S04 : texte de l'étiquette de derrière ; S05/S04 : lumière) et passer la garde.
- **P23** Le même élément doit avoir la même visibilité dans le rendu normal et dans le rendu `--holes` :
  sinon la plaque est percée là où le code ne dessine rien (texte manquant, pilote « Every brand »).
- **P26** `brandColor` sur `rgba(…, ${a})` : un alpha écrit `1e-7` n'était pas reconnu → halo opaque
  autour du texte rebrandé. Toute syntaxe d'alpha est désormais conservée.
- **P27** Une plaque deux couleurs rend toute autre teinte sur la droite A→B : gris → lavande, beige →
  violet. Avant de laisser la plaque montrer l'original, vérifier la palette (`--third`, plaque dédiée, ou
  segment extrait).
- **P28** Texte penché par une caméra 3D : ne pas le dimensionner par la hauteur de sa boîte
  (`fit_text_pose.py`, § 12).
- **P29** Ne jamais faire `seek` avant que la plaque soit créée (`window.__rm` défini APRÈS `RMGL.decalque`).
- **P30** Chaque ré-encodage coûte en fidélité sur des dégradés sombres (0,9886 → 0,9824 après découpe +
  composition) : livrer le rendu direct avec le son ajouté sans ré-encoder (`-c:v copy`).
- **P25** Centre mesuré en indices de pixels (minAreaRect, moments) : ajouter 0,5 pour passer en
  coordonnées SVG/canvas (le pixel i couvre [i, i+1]). Sinon tout l'objet est décalé d'un demi-pixel et
  ses bords en diagonale « clignotent » dans le détecteur de fantômes.
- **P24** Un score global élevé (0,975) cachait une vingtaine de plages à textes doublés ou en avance.
  SSIM sur l'image entière ≠ absence de défaut : mesurer les **pixels fantômes** (contours présents dans
  la copie, absents de l'original) et regarder chaque plage signalée.

## 9 bis. Garde anti-fantômes (`ghost_guard.py`)

**Problème** : en décalque, chaque élément en code (texte, icône, bouton) est posé sur la plaque. S'il
est décalé, en avance, en retard, ou si ses lettres diffèrent trop (police, flou de l'original), on voit
**deux** versions. Le SSIM global ne le voit presque pas.

**Méthode** : pour chaque image et chaque élément visible de `fgIds`, on compare la zone de l'élément
(boîte + 6 px) dans l'original et la copie : SSIM local, et part des contours de la copie sans contour
à moins de 2 px dans l'original. Fantôme si SSIM < 0,75 ou contours en trop > 12 %. Les images
fautives vont dans `window.HIDE` ; `RMGL.decalque` cache l'élément dans ces images (plaque active, et
aussi dans le rendu `--holes`) : la plaque, ré-extraite, garde alors les pixels **de l'original**.
Boucle : garde → trous → plaque → rendu → garde (2 passes ; la 2e ne doit presque rien ajouter).

En mode code (rebrand avec `mode: 'code'`) la garde ne s'applique pas. En décalque rebrandé, une image
« gardée » montre le texte d'origine recoloré (pas le texte de `BRAND.texts`) : pour changer un texte
dans une plage gardée, corriger l'animation de ce texte (recalage) jusqu'à ce que la garde le relâche.

Contrôle global, trois détecteurs dans `report.json` (+ `ghosts.png`, original | copie) :
- `ghost_runs` : contours de la copie absents de l'original (doublons, élément en avance/en retard) ;
- `missing_runs` : contours de l'original absents de la copie (lettre manquante, trou de plaque — ex.
  « trust. » effacé quand la garde cachait un texte APRÈS l'extraction : la boucle doit converger) ;
- `colour_runs` : Delta E (95e centile) > 10 — le SSIM, calculé en niveaux de gris, ne voit pas un gris
  rendu lavande ni des éclats beiges rendus violets.
Chaque plage est regardée et corrigée ou expliquée. Cas traités : « alive » gris → plaque trois couleurs
dédiée aux images gardées (S07) ; fin de l'éclatement en verre → segment extrait prolongé jusqu'à l'image
816 (S14) ; bord de carte en sous-pixel (pilote 140-145) → coins re-mesurés sur les liserés.

## 9 ter. Portabilité (skill partagé)

- i/s et taille lus dans la vidéo (`rmcommon.probe`), passés aux scènes par `?fps=` (`RM.FPS`) ;
  aucun 30 i/s ni 736×414 dans le moteur.
- Chromium : `CHROME_PATH`, sinon celui de Playwright, sinon Chrome / Chromium / Edge installés.
- Les rendus intermédiaires (PNG) sont effacés après encodage (`--keep-frames` pour les garder) :
  une vidéo longue ne remplit pas le disque.
- `extract_plate.py` écrit sa ligne de commande en tête de la plaque : toute plaque se ré-extrait à
  l'identique.
- Test long : `examples/demo` (64 s, 25 i/s, 640×360) → 0,991, 0 anomalie, 0 fantôme ; rebrand : rythme identique.

## 9 quater. Contrôle final obligatoire

`assemble.py` produit `report.json` avec : score par segment, score de chaque **raccord** (image avant /
après), et la liste des **anomalies** (image plus de 0,05 sous la médiane de ses voisines). Toute anomalie
est examinée à l'œil et corrigée (cause réelle), jamais ignorée. Exemples traités : entrée/sortie de
« come alive » (boîtes rejouées), extrait décalé d'une image, rideau de fin de S21.

## 10. Scores finaux (vidéo complète, mode décalque, mesurés par `assemble.py`)

| Segment | Passe 1 | Passe 2 (« 0,975 ») | **Passe 3 : garde anti-fantômes** | Pire image |
| --- | --- | --- | --- | --- |
| S01-S03 pilote | 0,941 | 0,977 | **0,984** | 0,947 |
| S04 (+ lumière S05) | 0,918 | 0,968 | **0,989** | 0,982 |
| S06 orbites | 0,881 | 0,983 | **0,994** | 0,984 |
| S07-S08 BRANDS / come alive | 0,921 | 0,983 | **0,990** (gris juste) | 0,968 |
| S09-S13 extraits clients | 0,991 | 0,991 | 0,991 | 0,983 |
| S14 bille (depuis l'image 817) | 0,876 | 0,961 | **0,997** | 0,994 |
| S15-S16 chiffres / More | 0,916 | 0,940 | **0,993** | 0,976 |
| S17 logos (extrait) | 0,997 | 0,997 | 0,997 | 0,996 |
| S18 globe | 0,800 | 0,988 | **0,996** | 0,987 |
| S19 mascotte (extrait) | 0,996 | 0,997 | 0,997 | 0,991 |
| S20-S22 fin | 0,936 | 0,978 | **0,995** | 0,984 |
| **Vidéo entière** | 0,929 | 0,975 | **0,9919** | 0,947 |
| Images ≥ 0,98 | 31 % | 58 % | **94 %** | — |
| Anomalies / fantômes / manques / couleurs | 9 / — | 0 / **≈ 20 non vues** | **0 / 0 / 1 / 0** | — |

La plage « manque » restante (pilote 4,70 s, images 140-142) est un liseré de bord de carte de moins
d'un pixel (couverture 0,2–0,6 px) : regardée, invisible à l'œil, laissée et signalée.
Rebrand de test (palette provisoire IROKO) : rythme **identique** (décalage 0, corrélation 0,997).

Leçon de la passe 3 : la passe 2 annonçait 0,975 et « 0 anomalie », mais une vingtaine de plages avaient
des textes en double ou en avance (S04 étiquettes, S05 lumière, S15 « More… », S20 bouton, pilote
« starts »). Elles n'ont été vues qu'en regardant les images. D'où la garde et le contrôle `ghost_runs`.
Pilote, autres corrections de la passe 3 : bouton visible au bord droit avant son entrée (caché avant
1,70 s), piste de dézoom fausse aux images 99-101 (re-mesurée par la largeur), flou de mouvement réel
de l'original sur le glissé du bouton (58-66) et l'image 129, recalage de « Every brand » (28-70).

Limite restante : la forme des lettres (police originale payante ; Outfit = la plus proche). En
décalque, la garde laisse la plaque montrer l'original là où l'écart est trop grand.

## 12. Vidéo « 3D » : pub verticale (9:16, 24 i/s, 720×1280, 24,75 s)

Cas : fond en dégradé avec balayages de lumière, cartes en verre à reflets, personnage lumineux, barres 3D,
logo 3D, caméra qui bascule en perspective, ~70 mots animés. Aucun effet n'est en 2-3 couleurs plates.

1. **Plaques en couleurs réelles** (`extract_plate.py --rgb 95`) : l'image d'origine, trous des éléments en
   code comblés par inpainting, stockée en WebP. Plafond mesuré du procédé seul (compression) : **0,995**.
   Les images sont décodées à la demande (`window.__rmWait` : le rendu attend puis recale) — sinon
   600 images 720×1280 décodées d'un coup = 2 Go.
2. **Police** : `font_search.py` sur 5 mots → **Poppins** (0,71 contre 0,56 pour la suivante).
3. **Mots** : inventaire OCR (`text_inventory.py`, 278 détections brutes, bruitées : graduations, mots
   coupés) → liste propre de 69 mots avec une image de référence chacun → `track_words.py` (corrélation
   normalisée, échelle 0,9–1,1 par image, arrêt sous 0,55).
4. **Piège P28** : placer le mot par la HAUTEUR de sa boîte donne des lettres trop grosses dès que le texte
   est incliné (la caméra 3D penche les lignes de 2 à 18°) : la boîte d'un mot penché est plus haute.
   `fit_text_pose.py` résout taille + angle à partir de la boîte et du sens de l'encre ; angle commun par
   ligne (médiane). Écart visuel supprimé (avant : mots 10–30 % trop larges).
5. **Lignes en perspective** : `track_lines.py` (ECC, homographie) — la ligne est posée comme sur l'image
   de référence puis reçoit `RM.homographyMatrix3d(H)`.
6. **Compteurs** lus par OCR puis modélisés : solde 87 628 → 100 000 linéaire sur 28 images (écart 0 sur
   les 7 valeurs lues), anneau 20 % (image 450) → 90 % (image 489), linéaire.
7. **Logo** redessiné en vecteur (contours mesurés, dégradé mesuré en 7 bandes) : SSIM local 0,91 seulement
   (l'original a un éclairage 3D) → en mode décalque la garde montre l'original ; le vecteur sert au mode code.
8. **Garde** : boucle trous → plaque → rendu → garde jusqu'à stabilité (5 passes).

Résultats : passe 1 (mots placés par la hauteur) 0,967 ; avec la pose et les lignes 0,976 ; après garde
convergente **0,9886** (87 % des images ≥ 0,98), 0 anomalie, 0 fantôme, 0 manque, 0 couleur fausse.

## 11. Journal des scores du pilote

| Étape | Pilote 0–5 s | Remarque |
| --- | --- | --- |
| v1 courbes posées | 0,928 | |
| v6 easings mesurés + optimiseur | 0,942 | |
| v8 plaques WebGL (ondes, mosaïque) | 0,971 | |
| v12 trous réels + recalage « starts » | 0,973 | |
| v13 plaque sortie de carte + recalage texte | **0,979** (pire image 0,925, avant 0,59) | |
