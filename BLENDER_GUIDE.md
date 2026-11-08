<!-- Guide de référence fourni par Marion De Souza (IROKO) pour reverse-motion. Appliqué par scripts/blender_object.py : voir METHODS.md § 14 pour ce qui est automatisé. -->

# TECHNIQUES DE MODÉLISATION 3D POUSSÉES

## Guide de référence pour une IA qui apprend à créer des objets photoréalistes dans Blender depuis un environnement de code

**Version :** 1.0\
**Cible :** agent IA / assistant de génération 3D pilotant Blender avec
Python (`bpy`)\
**Objectif :** apprendre à analyser, construire, texturer, éclairer,
rendre et contrôler des objets 3D réalistes de manière reproductible.

------------------------------------------------------------------------

# 1. Mission et philosophie de travail

Tu es un agent spécialisé en création 3D procédurale et en rendu
photoréaliste dans Blender. Tu dois être capable de transformer une
description, une image de référence ou un cahier des charges en scène 3D
propre, crédible, organisée et exploitable.

Ton objectif n'est pas seulement de produire une forme reconnaissable.
Tu dois construire un objet qui respecte autant que possible :

-   sa silhouette et ses proportions ;
-   sa géométrie et ses détails de fabrication ;
-   les propriétés physiques de ses matériaux ;
-   le comportement réel de la lumière ;
-   les conditions de prise de vue photographique ;
-   les exigences techniques du fichier final.

Le photoréalisme ne vient pas d'un nombre élevé de polygones ou d'un
rendu très brillant. Il résulte de la cohérence entre **forme, échelle,
matière, lumière, caméra et imperfections**.

## 1.1 Règles fondamentales

1.  **Observer avant de modéliser.** Identifier la silhouette, les
    volumes, les assemblages, les matériaux et les détails visibles.
2.  **Respecter l'échelle.** Travailler en unités cohérentes,
    généralement avec 1 unité Blender correspondant à 1 mètre.
3.  **Construire une géométrie maîtrisée.** Éviter les détails inutiles
    et les maillages désordonnés.
4.  **Donner une épaisseur réelle lorsque c'est nécessaire.** Une coque,
    une paroi, un rebord ou un tissu ne doit pas toujours être une
    simple surface.
5.  **Ne jamais utiliser un matériau uniforme pour simuler une matière
    complexe.**
6.  **Éviter la perfection artificielle.** Ajouter des variations
    discrètes et justifiées, jamais du bruit au hasard.
7.  **Éclairer l'objet comme un photographe.** Les reflets révèlent les
    formes autant que les ombres.
8.  **Valider par étapes.** Produire des rendus de contrôle avant le
    rendu final.
9.  **Automatiser sans sacrifier la lisibilité.** Le script doit être
    modulaire, paramétrable et réexécutable.
10. **Ne pas prétendre qu'un rendu est photoréaliste sans l'avoir
    inspecté.** Vérifier les images produites et corriger les défauts
    observés.

------------------------------------------------------------------------

# 2. Comprendre l'objet avant de lancer Blender

## 2.1 Décomposer la référence

Avant de créer la géométrie, établir une fiche d'analyse.

  -----------------------------------------------------------------------
  Élément                             Questions à résoudre
  ----------------------------------- -----------------------------------
  Catégorie                           Produit industriel, emballage,
                                      aliment, objet organique, mobilier,
                                      accessoire ?

  Silhouette                          Quelle est la forme générale ?
                                      Quelles sont les proportions ?

  Volumes                             Quels volumes principaux et
                                      secondaires composent l'objet ?

  Assemblage                          Quelles pièces sont séparées,
                                      vissées, collées, emboîtées ou
                                      soudées ?

  Matériaux                           Plastique, métal, verre, papier,
                                      carton, bois, caoutchouc, peau,
                                      liquide ?

  Épaisseur                           Quelles parties ont une épaisseur
                                      visible ou doivent être creuses ?

  Détails                             Coutures, joints, gravures,
                                      nervures, pores, rayures, bouchons,
                                      soudures ?

  Échelle                             Quelles dimensions réelles peut-on
                                      estimer ?

  Caméra                              Vue frontale, trois-quarts, profil,
                                      plongée, macro ?

  Éclairage                           Studio diffus, lumière dure,
                                      contre-jour, environnement naturel
                                      ?
  -----------------------------------------------------------------------

Si une dimension est inconnue, utiliser une estimation explicite et la
conserver comme paramètre modifiable. Ne pas inventer silencieusement
des détails déterminants.

## 2.2 Décomposition hiérarchique

Décomposer l'objet en trois niveaux :

-   **Niveau A : volumes principaux** --- corps, base, couvercle,
    poignée, contenant.
-   **Niveau B : composants secondaires** --- rebords, raccords,
    panneaux, reliefs, pièces d'assemblage.
-   **Niveau C : détails fins** --- micro-rayures, pores, gravures,
    petits chanfreins, irrégularités.

Construire et valider les volumes A avant de passer aux niveaux B et C.

## 2.3 Analyse multi-vues

Quand plusieurs références sont disponibles, les comparer pour
distinguer les caractéristiques réelles des effets de perspective ou
d'éclairage. Une seule photographie ne permet généralement pas de
déduire avec certitude toute la géométrie.

En l'absence de vues supplémentaires : - préserver les parties visibles
; - construire les parties cachées de manière plausible et sobre ; -
signaler les hypothèses importantes ; - éviter d'ajouter des détails
fantaisistes.

------------------------------------------------------------------------

# 3. Préparer l'environnement Blender piloté par code

## 3.1 Principes d'architecture

Utiliser Blender et son API Python `bpy`. Le script doit pouvoir être
exécuté depuis Blender en mode interface ou en mode arrière-plan, selon
l'environnement disponible.

Organiser le projet en modules logiques :

``` text
project/
├── main.py
├── config.py
├── geometry/
│   ├── primitives.py
│   ├── hard_surface.py
│   ├── organic.py
│   └── details.py
├── materials/
│   ├── library.py
│   ├── plastics.py
│   ├── metals.py
│   ├── glass.py
│   └── organic.py
├── scene/
│   ├── camera.py
│   ├── lighting.py
│   └── environment.py
├── rendering/
│   ├── settings.py
│   └── passes.py
└── output/
```

Pour un objet simple, un script unique peut suffire, mais il doit
conserver des fonctions séparées.

## 3.2 Configuration centrale

Définir les paramètres au début du script :

``` python
CONFIG = {
    "unit_scale": 1.0,
    "render_engine": "CYCLES",
    "resolution_x": 1600,
    "resolution_y": 1600,
    "resolution_percentage": 100,
    "samples_preview": 32,
    "samples_final": 256,
    "output_format": "PNG",
    "color_mode": "RGBA",
    "camera_focal_length": 70,
    "output_path": "//renders/final.png",
}
```

Ces valeurs sont des points de départ, pas des règles universelles. Les
ajuster selon la scène, le matériel et le temps de calcul.

## 3.3 Bonnes pratiques de scripting

-   Nommer les objets, matériaux, collections et caméras clairement.
-   Utiliser des fonctions réutilisables.
-   Éviter les valeurs numériques dispersées dans le code : centraliser
    les dimensions et paramètres.
-   Appliquer les transformations lorsque la suite du workflow l'exige.
-   Contrôler les unités, les normales et l'échelle.
-   Utiliser des collections distinctes : `PRODUCT`, `DETAILS`,
    `STUDIO`, `CAMERAS`, `LIGHTS`.
-   Prévoir un mode `PREVIEW` et un mode `FINAL`.
-   Nettoyer ou recréer la scène de manière déterministe.
-   Ne pas supprimer des objets utilisateur sans vérifier le contexte.
-   Gérer les erreurs et vérifier que les fichiers de sortie existent.

------------------------------------------------------------------------

# 4. Techniques de modélisation géométrique

## 4.1 Primitive Blocking

Commencer par les formes élémentaires : cube, cylindre, sphère, plan,
tore et courbe.

Objectif : - vérifier la silhouette ; - régler les proportions ; -
valider le cadrage ; - éviter de détailler une forme incorrecte.

À cette étape, utiliser des matériaux neutres et un éclairage simple.

## 4.2 Hard Surface Modeling

Technique destinée aux objets mécaniques, électroniques, industriels et
aux emballages rigides.

Méthodes : - modélisation par extrusion et boucle de coupe ; - bevel
contrôlé ; - opérations booléennes ; - gestion des normales ; -
séparation logique des pièces ; - contrôle des arêtes et des transitions
de surface.

### Bevel

Les arêtes parfaitement vives sont rares dans le monde réel. Un très
petit chanfrein capte la lumière et rend l'objet beaucoup plus crédible.

Utiliser : - le modificateur Bevel ; - un nombre de segments adapté à la
courbure ; - une largeur cohérente avec l'échelle ; - des limites par
angle ou poids de biseau lorsque cela convient.

Ne pas appliquer le même bevel à toutes les arêtes sans réflexion. Une
arête de verre, une arête de plastique moulé et une arête métallique
n'ont pas nécessairement le même rayon.

## 4.3 Subdivision Surface

La subdivision permet d'obtenir des surfaces lisses à partir d'un
maillage de contrôle.

À utiliser pour : - formes organiques ; - objets arrondis ; - bouteilles
et contenants ; - pièces dont la courbure doit être continue.

Bonnes pratiques : - construire une topologie propre ; - placer les edge
loops de soutien ; - éviter les pôles mal placés dans les zones très
visibles ; - contrôler le lissage et les normales ; - ne pas augmenter
le niveau de subdivision pour compenser une mauvaise topologie.

## 4.4 Weighted Normals et Auto Smooth

Les normales déterminent comment la lumière est interpolée sur la
surface.

Utiliser les normales pondérées pour conserver un aspect visuellement
plat sur les grandes faces tout en gardant des arêtes nettes. Vérifier
les versions de Blender, car les options de lissage et leur interface
ont évolué.

Toujours inspecter : - les facettes involontaires ; - les ombres
anormales ; - les normales inversées ; - les artefacts autour des
booléens.

## 4.5 Boolean Modeling

Les booléens servent à ajouter ou retirer des volumes.

Cas d'usage : - trous ; - ouvertures ; - rainures ; - découpes ; -
logements de vis ; - formes d'assemblage.

Procédure recommandée : 1. créer un objet opérateur propre ; 2. utiliser
une résolution suffisante ; 3. choisir un solveur adapté ; 4. appliquer
le modificateur lorsque la géométrie est validée ; 5. nettoyer les faces
dégénérées si nécessaire ; 6. ajouter de petits bevels aux arêtes créées
; 7. inspecter le maillage et les normales.

Les booléens ne dispensent pas de vérifier la topologie.

## 4.6 Courbes et profils

Les courbes sont utiles pour : - câbles ; - tuyaux ; - poignées ; -
joints ; - bordures ; - fils ; - contours décoratifs.

Contrôler le bevel de la courbe, la résolution et les raccords.
Convertir en mesh uniquement si une opération géométrique l'exige.

## 4.7 Solidify et épaisseur

Le modificateur Solidify donne une épaisseur à une surface.

À utiliser pour : - parois de contenants ; - feuilles ; - tissus
simplifiés ; - emballages ; - coques.

Vérifier la direction de l'épaisseur, les normales, les ouvertures et
les intersections.

## 4.8 Modélisation organique

Pour les formes organiques : - privilégier les volumes continus ; -
éviter les symétries trop parfaites lorsque la référence présente une
asymétrie ; - utiliser des déformations douces ; - construire les
reliefs à plusieurs échelles ; - employer sculpting, displacement ou
géométrie procédurale selon le besoin.

Les aliments, fruits et végétaux ont des variations de forme subtiles.
Une sphère parfaite avec une texture colorée ne suffit pas à représenter
un fruit crédible.

------------------------------------------------------------------------

# 5. Modélisation procédurale et Geometry Nodes

Geometry Nodes permet de construire des systèmes paramétriques et de
générer des géométries répétitives ou variables.

## 5.1 Cas d'utilisation

-   graines sur une fraise ;
-   pores ou petits reliefs sur une peau d'agrume ;
-   nervures de feuilles ;
-   fibres et brins ;
-   vis et éléments répétitifs ;
-   motifs perforés ;
-   variations de surface ;
-   assemblages paramétriques.

## 5.2 Logique générale

Un système procédural suit généralement ce flux :

1.  générer ou recevoir une géométrie de base ;
2.  créer des points de distribution ;
3.  filtrer les points selon une zone ou un masque ;
4.  instancier un élément ;
5.  varier rotation, échelle et position ;
6.  appliquer des contraintes pour éviter les collisions ;
7.  réaliser les instances uniquement si nécessaire ;
8.  vérifier le résultat à l'échelle de la caméra.

## 5.3 Variation contrôlée

Les variations doivent être déterministes et paramétrables.

Exemples de paramètres : - densité ; - rayon de distribution ; - taille
minimale et maximale ; - variation de rotation ; - graine aléatoire ; -
masque de distribution.

Ne pas disperser des éléments au hasard sur toutes les surfaces. La
distribution doit suivre la structure réelle de l'objet.

## 5.4 Performance

-   Préférer les instances aux copies de géométrie lorsque possible.
-   Limiter les détails invisibles à la caméra.
-   Réduire la densité en mode aperçu.
-   Utiliser des niveaux de détail.
-   Éviter les millions d'instances sans justification.
-   Contrôler la mémoire et le temps d'évaluation des nœuds.

------------------------------------------------------------------------

# 6. Matériaux physiques et Shader Engineering

## 6.1 Principled BSDF

Le shader Principled BSDF constitue une base polyvalente pour les
matériaux physiques.

Paramètres importants : - **Base Color** : couleur diffuse de base ; -
**Metallic** : caractère métallique ; - **Roughness** : dispersion des
reflets ; - **IOR** : indice de réfraction ; - **Transmission** :
transmission de la lumière ; - **Alpha** : opacité ; - **Normal** :
orientation locale de la surface ; - **Subsurface** : diffusion sous la
surface ; - **Coat** : couche de finition ; - **Emission** : lumière
émise par le matériau.

Les paramètres disponibles peuvent varier selon la version de Blender.
Le script doit vérifier les entrées du nœud avant de les modifier.

## 6.2 PBR : comprendre les cartes

  -----------------------------------------------------------------------
  Carte                   Fonction                Utilisation
  ----------------------- ----------------------- -----------------------
  Base Color / Albedo     Couleur sans ombrage    Couleur de la matière
                          intégré                 

  Roughness               Dispersion des reflets  Mat, satiné, brillant

  Metallic                Classification          Métal ou non-métal
                          métallique              

  Normal                  Détail d'orientation de Micro-relief sans
                          surface                 ajouter de géométrie

  Height                  Hauteur de surface      Relief ou displacement

  Displacement            Déformation géométrique Relief réel

  Ambient Occlusion       Occlusion locale        À utiliser avec
                                                  discernement, pas comme
                                                  substitut à l'éclairage
  -----------------------------------------------------------------------

Les textures de couleur, roughness et metallic doivent être interprétées
correctement. Les cartes de données telles que roughness, metallic,
normal et height sont généralement des données non colorimétriques et
doivent être traitées en espace **Non-Color**.

## 6.3 Procedural Texturing

Les textures procédurales sont générées dans le shader à partir de
nœuds.

Nœuds souvent utiles : - Texture Coordinate ; - Mapping ; - Noise
Texture ; - Voronoi Texture ; - Wave Texture ; - Musgrave ou ses
équivalents selon la version ; - Color Ramp ; - Mix ; - Bump ; -
Displacement.

Exemple de logique : - coordonnées UV ou Generated ; - Mapping pour
contrôler l'échelle ; - Noise pour créer une variation ; - Color Ramp
pour contrôler le contraste ; - branche Roughness pour varier les
reflets ; - branche Bump pour générer un relief subtil.

Une texture procédurale doit être calibrée selon la dimension réelle de
l'objet. Un bruit trop grand ressemble à des bosses ; un bruit trop fin
peut devenir du bruit visuel.

## 6.4 Imperfection Mapping

Les imperfections rendent une matière crédible, mais elles doivent
rester cohérentes avec son usage.

Exemples : - plastique : légère variation de roughness, lignes de
moulage, micro-rayures ; - métal : brossage directionnel, rayures fines,
traces d'usinage ; - verre : petites poussières ou traces discrètes,
sans salir systématiquement ; - carton : fibres, plis, variations de
papier ; - fruit : pores, irrégularités, taches naturelles ; - céramique
: variations très légères de glaçure.

Éviter l'effet « objet abandonné » sur un produit neuf. L'usure doit
correspondre à l'état demandé.

## 6.5 Bump, Normal et Displacement

Ces trois techniques ne sont pas interchangeables.

-   **Bump** : modifie l'apparence des normales à partir d'une hauteur ;
    rapide, sans changement réel de silhouette.
-   **Normal Map** : encode l'orientation des détails ; utile pour des
    détails sculptés ou cuits dans une texture.
-   **Displacement** : déplace réellement la surface ; utile pour les
    reliefs qui modifient la silhouette ou les ombres.

Les détails visibles de profil ou qui produisent une ombre géométrique
nette nécessitent souvent une véritable géométrie ou du displacement.

## 6.6 UV Mapping

Déplier les UV lorsque la texture doit être peinte, placée précisément
ou partagée avec d'autres logiciels.

Contrôler : - chevauchements non voulus ; - étirement ; - densité de
texels ; - orientation des îlots ; - coutures dans les zones visibles.

Pour les matériaux entièrement procéduraux, les coordonnées Generated ou
Object peuvent suffire, mais elles ne remplacent pas toujours un
dépliage UV propre.

------------------------------------------------------------------------

# 7. Bibliothèque de matériaux : recettes de départ

Ces recettes sont des bases de travail. Les valeurs doivent être
ajustées selon la référence, l'échelle, la lumière et la version du
shader.

## 7.1 Plastique mat

-   Metallic : 0
-   Roughness : environ 0,35 à 0,65
-   IOR : valeur adaptée au plastique si disponible
-   légère variation de roughness ;
-   micrograin discret ;
-   bevels visibles sur les arêtes.

Le plastique moulé présente souvent des transitions douces et des
détails de fabrication.

## 7.2 Plastique brillant

-   Metallic : 0
-   Roughness : environ 0,12 à 0,3
-   Coat modéré si la finition le justifie ;
-   reflets larges et contrôlés ;
-   micro-rayures très discrètes.

Ne pas confondre brillant et miroir.

## 7.3 Métal

-   Metallic : 1
-   Roughness selon la finition, souvent environ 0,15 à 0,5
-   texture de brossage directionnelle si nécessaire ;
-   variations de roughness ;
-   environnement suffisamment riche pour créer des reflets lisibles.

Un métal parfaitement uniforme dans un environnement vide paraît souvent
artificiel.

## 7.4 Verre

-   Transmission élevée ;
-   IOR adapté au type de verre ;
-   roughness faible pour un verre poli ;
-   épaisseur géométrique réelle ;
-   normales correctes ;
-   environnement et éclairage visibles dans les réflexions.

Le verre est difficile à lire sans objets ou sources lumineuses à
refléter. Un matériau transparent placé dans un environnement vide peut
sembler invisible.

## 7.5 Papier et carton

-   Metallic : 0
-   Roughness généralement élevée ;
-   texture fibreuse subtile ;
-   épaisseur réelle sur les bords ;
-   plis, découpes et arêtes crédibles ;
-   impression séparée de la matière du papier.

## 7.6 Caoutchouc

-   Metallic : 0
-   Roughness moyenne à élevée ;
-   microtexture fine ;
-   reflets larges et peu intenses ;
-   légère déformation si l'objet est souple.

## 7.7 Peau, fruits et matières organiques

-   Subsurface Scattering adapté ;
-   variation de couleur à plusieurs échelles ;
-   roughness non uniforme ;
-   pores ou micro-reliefs ;
-   silhouette légèrement irrégulière ;
-   petites variations de translucidité.

------------------------------------------------------------------------

# 8. Subsurface Scattering et matières translucides

Le Subsurface Scattering (SSS) simule la pénétration de la lumière dans
une matière, sa diffusion interne puis sa sortie.

À considérer pour : - peau ; - cire ; - fruits ; - légumes ; - feuilles
épaisses ; - certains aliments.

Règles : 1. utiliser une échelle cohérente ; 2. régler la distance de
diffusion selon la taille de l'objet ; 3. éviter une diffusion excessive
qui donne un aspect cireux ; 4. associer le SSS à une roughness réaliste
; 5. tester sous plusieurs angles de lumière.

Le SSS ne doit pas être activé par défaut sur tous les matériaux.

------------------------------------------------------------------------

# 9. Éclairage professionnel de studio

La lumière est une composante de la modélisation visuelle. Elle révèle
les volumes, la matière et la finition.

## 9.1 Three-Point Lighting

-   **Key Light** : source principale qui définit le volume.
-   **Fill Light** : réduit le contraste des ombres.
-   **Rim / Back Light** : sépare l'objet de l'arrière-plan et souligne
    son contour.

Les trois sources ne doivent pas nécessairement avoir la même puissance
ou la même taille.

## 9.2 Softbox et Area Lights

Les grandes sources Area produisent des reflets larges et doux. Les
petites sources produisent des reflets plus nets.

Pour les objets brillants, la forme des sources est particulièrement
importante : les reflets dessinent visuellement le produit.

## 9.3 HDRI

Une image HDRI peut fournir un éclairage d'environnement réaliste.

Utiliser une HDRI : - adaptée au type de scène ; - de résolution
suffisante ; - avec des zones lumineuses cohérentes ; - dont
l'orientation est réglée pour obtenir les reflets souhaités.

Une HDRI ne remplace pas toujours les sources de studio dédiées.

## 9.4 Éclairage par matériau

-   verre : bandes lumineuses et contre-jours contrôlés ;
-   métal : grandes surfaces de réflexion ;
-   plastique : reflets doux ou nets selon la finition ;
-   aliments : lumière latérale révélant texture et volume ;
-   papier : lumière plus diffuse pour éviter des reflets excessifs.

## 9.5 Contrôle de l'arrière-plan

L'arrière-plan doit soutenir la lecture de l'objet. Il peut être uni, en
dégradé physique obtenu par la lumière, ou appartenir à un environnement
construit.

Éviter les halos artificiels et les lumières colorées non justifiées. Le
fond doit être cohérent avec le brief.

------------------------------------------------------------------------

# 10. Caméra et photographie virtuelle

## 10.1 Focale et perspective

La focale influence la perspective apparente et la composition.

-   focale courte : perspective plus marquée ;
-   focale moyenne : rendu polyvalent ;
-   focale longue : perspective plus comprimée, souvent utile en
    photographie produit.

Ne pas choisir une focale uniquement par habitude. La distance
caméra-sujet compte également.

## 10.2 Camera Matching

Quand une photographie de référence existe : 1. identifier l'horizon ;
2. estimer la hauteur de caméra ; 3. estimer la focale ; 4. régler la
perspective ; 5. comparer les lignes verticales et horizontales ; 6.
ajuster la position et l'orientation ; 7. vérifier les proportions
apparentes.

## 10.3 Depth of Field

La profondeur de champ peut renforcer l'impression photographique.

Régler : - distance de mise au point ; - ouverture ; - focale ; -
distance entre caméra et objet.

Ne pas utiliser un flou extrême pour masquer une géométrie insuffisante.
En photographie produit, le produit entier doit souvent rester net.

## 10.4 Macro

Pour les rendus macro : - augmenter la précision des détails réellement
visibles ; - adapter la profondeur de champ ; - utiliser une lumière qui
révèle le relief ; - éviter le bruit et les textures surdimensionnées
; - contrôler l'échelle des imperfections.

------------------------------------------------------------------------

# 11. Rendu : Cycles, sampling et gestion de la couleur

## 11.1 Cycles

Cycles est adapté aux rendus où la qualité des interactions lumineuses
est prioritaire.

À contrôler : - nombre d'échantillons ; - méthode de sampling ; -
denoising ; - rebonds de lumière ; - caustiques selon les
fonctionnalités de la version ; - gestion de la mémoire ; - accélération
GPU ou CPU.

Les options exactes varient selon la version de Blender et le matériel.
Le script doit vérifier les propriétés disponibles avant de les définir.

## 11.2 Eevee

Eevee peut être pertinent pour les aperçus rapides, les animations et
certaines scènes optimisées. Il ne faut pas supposer que Cycles est
toujours le meilleur choix : le moteur dépend du rendu attendu et des
contraintes de calcul.

## 11.3 Adaptive Sampling

Concentre les calculs selon le bruit estimé. Utile pour optimiser les
rendus, mais doit être testé sur les zones difficiles : verre, ombres
douces, reflets complexes et surfaces sombres.

## 11.4 Denoising

Le denoising réduit le bruit, mais peut effacer les microdétails ou
créer des artefacts.

Comparer si possible : - image brute ; - image débruitée ; - détails à
100 % ; - zones de transparence et de reflets.

Ne pas augmenter le denoising pour compenser un nombre d'échantillons
insuffisant sans inspecter le résultat.

## 11.5 Color Management

Choisir un transformateur de vue adapté à l'intention visuelle et à la
version de Blender. AgX est un choix courant dans les versions récentes,
mais il faut vérifier le résultat plutôt que choisir aveuglément une
option.

Contrôler : - exposition ; - contraste ; - saturation ; - écrêtage des
hautes lumières ; - détails dans les ombres ; - cohérence entre les
matériaux.

------------------------------------------------------------------------

# 12. Compositing et Render Passes

Les passes peuvent séparer les composantes utiles en postproduction.

Exemples : - Combined ; - Diffuse ; - Glossy ; - Transmission ; - Normal
; - Depth / Z ; - Shadow ; - Ambient Occlusion selon le workflow.

Le Compositor permet : - correction colorimétrique ; - contraste ; -
ajustement de l'exposition ; - légère gestion du glow si le brief
l'autorise ; - compositing de plusieurs passes ; - export de masques.

Ne pas ajouter systématiquement du glow, du vignettage ou des effets
cinématographiques. La postproduction doit corriger ou améliorer le
rendu, pas le maquiller.

------------------------------------------------------------------------

# 13. Détails microscopiques et réalisme de surface

## 13.1 Les trois échelles de détail

Un matériau crédible combine souvent :

1.  **Macrostructure** : plis, bosses, nervures, forme générale.
2.  **Mésostructure** : grain, pores, reliefs intermédiaires.
3.  **Microstructure** : rayures fines, fibres, petits défauts.

Les trois échelles ne doivent pas avoir la même intensité.

## 13.2 Hiérarchie des détails

Prioriser les détails selon : - leur visibilité dans le cadrage ; - leur
importance pour reconnaître l'objet ; - leur influence sur les reflets
; - leur impact sur la silhouette ; - leur cohérence avec le matériau.

Ne pas modéliser des détails invisibles dans le rendu final, sauf s'ils
servent à d'autres vues ou à une réutilisation.

## 13.3 Imperfections plausibles

Les imperfections doivent avoir une cause crédible : - moulage ; -
usinage ; - frottement ; - manipulation ; - croissance naturelle ; -
pliage ; - vieillissement.

Un bruit aléatoire uniforme ne constitue pas une imperfection réaliste.

------------------------------------------------------------------------

# 14. Pipeline de production recommandé

Utiliser les étapes suivantes dans cet ordre.

## Étape 1 --- Brief et analyse

-   identifier l'objet ;
-   relever les dimensions ;
-   analyser les matériaux ;
-   définir les vues finales ;
-   identifier les détails essentiels ;
-   noter les inconnues.

**Livrable :** fiche de construction.

## Étape 2 --- Blocking

-   créer les volumes principaux ;
-   placer une caméra provisoire ;
-   vérifier la silhouette ;
-   comparer à la référence.

**Livrable :** modèle gris simple.

## Étape 3 --- Modélisation de précision

-   ajouter les composants ;
-   travailler les courbures ;
-   réaliser les découpes ;
-   ajouter les épaisseurs ;
-   corriger les normales.

**Livrable :** géométrie validée.

## Étape 4 --- Détails

-   ajouter les joints et assemblages ;
-   ajouter les détails de surface ;
-   employer Geometry Nodes si utile ;
-   supprimer les détails invisibles ou inutiles.

**Livrable :** modèle final.

## Étape 5 --- Matériaux

-   identifier chaque matière ;
-   construire les shaders ;
-   ajouter les textures ;
-   régler roughness, metallic, IOR et SSS ;
-   vérifier les échelles des textures.

**Livrable :** modèle texturé.

## Étape 6 --- Éclairage

-   définir le type de studio ;
-   installer la Key Light ;
-   ajouter Fill et Rim ;
-   ajouter HDRI si nécessaire ;
-   contrôler les reflets.

**Livrable :** éclairage de production.

## Étape 7 --- Caméra

-   choisir focale et cadrage ;
-   régler la perspective ;
-   contrôler la profondeur de champ ;
-   valider la composition.

**Livrable :** caméra finale.

## Étape 8 --- Rendu test

-   faible résolution ;
-   faible sampling ;
-   inspection des matériaux ;
-   inspection des ombres ;
-   inspection des reflets ;
-   corrections.

**Livrable :** rendu de validation.

## Étape 9 --- Rendu final

-   résolution finale ;
-   sampling adapté ;
-   denoising contrôlé ;
-   passes nécessaires ;
-   export dans le format demandé.

**Livrable :** image finale et fichier Blender.

## Étape 10 --- Contrôle qualité

Vérifier : - silhouette ; - proportions ; - intersections ; - normales
; - artefacts ; - textures ; - reflets ; - bruit ; - cadrage ; -
résolution ; - présence des fichiers attendus.

------------------------------------------------------------------------

# 15. Architecture d'un agent IA de modélisation Blender

L'agent doit fonctionner comme un système de production, et non comme un
générateur de script monolithique.

## 15.1 Modules de l'agent

### A. Analyseur de brief

Transforme la demande en spécifications : - type d'objet ; - dimensions
; - composants ; - matériaux ; - détails ; - vues ; - format final.

### B. Planificateur géométrique

Choisit les techniques adaptées : - primitives ; - hard surface ; -
subdivision ; - booléens ; - courbes ; - sculpting ; - Geometry Nodes.

### C. Constructeur de scène

Génère les objets et les collections avec `bpy`.

### D. Constructeur de matériaux

Crée les matériaux, les nœuds et les textures.

### E. Directeur de photographie virtuelle

Configure caméra, lumière et environnement.

### F. Moteur de rendu

Configure le moteur, les samples, le denoising et les sorties.

### G. Inspecteur qualité

Analyse les rendus, repère les défauts et formule des corrections.

### H. Gestionnaire de projet

Sauvegarde les fichiers, organise les versions et journalise les
paramètres.

## 15.2 Boucle d'amélioration

L'agent doit suivre une boucle itérative :

``` text
Brief
  ↓
Analyse de référence
  ↓
Plan de construction
  ↓
Génération du script Blender
  ↓
Exécution
  ↓
Rendu de contrôle
  ↓
Inspection de l'image
  ↓
Diagnostic des défauts
  ↓
Correction ciblée
  └──────────────→ nouvelle exécution
```

Une correction doit viser une cause identifiée. Ne pas modifier
simultanément la géométrie, les matériaux, la caméra et la lumière sans
savoir quel changement a amélioré ou dégradé le résultat.

## 15.3 Stratégie de correction

Exemples :

  -----------------------------------------------------------------------
  Défaut observé          Cause possible          Correction
  ----------------------- ----------------------- -----------------------
  Objet trop artificiel   Arêtes trop vives       Ajouter des bevels
                                                  réalistes

  Surface plastique       Roughness uniforme      Ajouter une variation
                                                  subtile

  Métal noir ou sans      Environnement pauvre    Ajouter des sources
  reflet                                          réfléchissantes

  Verre invisible         Absence de reflets ou   Corriger l'épaisseur et
                          épaisseur incorrecte    l'éclairage

  Objet trop lisse        Absence de              Ajouter bump, normal ou
                          microstructure          géométrie

  Forme incorrecte        Proportions mal         Revenir au blocking
                          analysées               

  Ombres trop dures       Source trop petite ou   Agrandir ou
                          mal placée              repositionner la source

  Rendu bruité            Sampling insuffisant ou Augmenter les samples
                          lumière complexe        et contrôler le
                                                  denoising

  Texture                 Mauvaise échelle de     Corriger Mapping et
  disproportionnée        coordonnées             coordonnées

  Reflets brûlés          Puissance ou exposition Ajuster lumière et
                          excessive               color management
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 16. Exemple de squelette Python Blender

Le code ci-dessous est un point de départ illustratif. Il doit être
adapté à la version de Blender et au cahier des charges.

``` python
import bpy
import math
from mathutils import Vector

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PREVIEW = True
OUTPUT_PATH = "//renders/product_preview.png"

SAMPLES = 32 if PREVIEW else 256
RESOLUTION = 900 if PREVIEW else 1800

# --------------------------------------------------
# UTILITAIRES
# --------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def create_collection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection

def move_to_collection(obj, collection):
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)

def apply_scale(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(
        location=False,
        rotation=False,
        scale=True
    )
    obj.select_set(False)

# --------------------------------------------------
# GÉOMÉTRIE
# --------------------------------------------------

def create_body(name, dimensions, location=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    apply_scale(obj)
    return obj

def add_bevel(obj, width=0.01, segments=4):
    modifier = obj.modifiers.new("Realistic_Edge_Bevel", "BEVEL")
    modifier.width = width
    modifier.segments = segments
    modifier.limit_method = "ANGLE"
    return modifier

# --------------------------------------------------
# MATÉRIAU
# --------------------------------------------------

def create_principled_material(
    name,
    color=(0.2, 0.2, 0.2, 1),
    roughness=0.35,
    metallic=0.0
):
    material = bpy.data.materials.new(name)
    material.use_nodes = True

    nodes = material.node_tree.nodes
    principled = next(
        node for node in nodes
        if node.type == "BSDF_PRINCIPLED"
    )

    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = metallic

    return material

# --------------------------------------------------
# ÉCLAIRAGE
# --------------------------------------------------

def create_area_light(name, location, target, power, size):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = power
    data.shape = "DISK"
    data.size = size

    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    return obj

# --------------------------------------------------
# CAMÉRA
# --------------------------------------------------

def create_camera(location, target, focal_length=70):
    camera_data = bpy.data.cameras.new("Product_Camera")
    camera = bpy.data.objects.new("Product_Camera", camera_data)
    bpy.context.scene.collection.objects.link(camera)

    camera.location = location
    camera.data.lens = focal_length

    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    bpy.context.scene.camera = camera
    return camera

# --------------------------------------------------
# RENDU
# --------------------------------------------------

def configure_render():
    scene = bpy.context.scene

    scene.render.engine = "CYCLES"
    scene.cycles.samples = SAMPLES

    scene.render.resolution_x = RESOLUTION
    scene.render.resolution_y = RESOLUTION
    scene.render.resolution_percentage = 100

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = OUTPUT_PATH

    # Activer le denoising si la propriété existe.
    if hasattr(scene.cycles, "use_denoising"):
        scene.cycles.use_denoising = True

# --------------------------------------------------
# SCÈNE
# --------------------------------------------------

def main():
    clear_scene()

    product_collection = create_collection("PRODUCT")

    body = create_body(
        "Product_Body",
        dimensions=(1.0, 0.35, 1.5),
        location=(0, 0, 0.75)
    )
    move_to_collection(body, product_collection)

    add_bevel(body, width=0.025, segments=5)

    material = create_principled_material(
        "Product_Material",
        color=(0.04, 0.12, 0.2, 1),
        roughness=0.28,
        metallic=0.0
    )
    body.data.materials.append(material)

    create_area_light(
        "Key_Light",
        location=(3, -4, 4),
        target=(0, 0, 0.8),
        power=900,
        size=3
    )

    create_area_light(
        "Fill_Light",
        location=(-3, -2, 2),
        target=(0, 0, 0.8),
        power=350,
        size=4
    )

    create_area_light(
        "Rim_Light",
        location=(0, 3, 3),
        target=(0, 0, 0.8),
        power=700,
        size=2
    )

    create_camera(
        location=(2.8, -4.5, 2.5),
        target=(0, 0, 0.8),
        focal_length=70
    )

    configure_render()

    bpy.ops.wm.save_as_mainfile(filepath="//product_scene.blend")
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    main()
```

**Important :** ce squelette ne représente pas un objet final
photoréaliste. Il illustre une architecture de base. Un véritable agent
doit adapter les dimensions, la topologie, les matériaux, les textures,
les lumières et la caméra à l'objet demandé.

------------------------------------------------------------------------

# 17. Exécution et validation depuis un environnement de code

## 17.1 Exécution en arrière-plan

Exemple de commande :

``` bash
blender -b --python main.py
```

Pour utiliser un fichier Blender existant :

``` bash
blender -b scene.blend --python main.py
```

Les options exactes dépendent de l'installation et de la version de
Blender. Vérifier que l'exécutable Blender est accessible depuis le
terminal.

## 17.2 Contrôles automatiques

Après l'exécution, vérifier : - que Blender s'est terminé sans erreur
; - que le fichier `.blend` existe ; - que l'image de rendu existe ; -
que sa résolution correspond à la demande ; - que les objets attendus
sont présents ; - que la caméra active existe ; - que le moteur de rendu
est correct.

## 17.3 Inspection visuelle

Un rendu doit être inspecté : - en vue globale ; - à 100 % ; - sur les
bords ; - sur les matériaux transparents ; - sur les zones fortement
réfléchissantes ; - sur les détails fins.

Un script qui se termine sans erreur ne garantit pas une image correcte.

------------------------------------------------------------------------

# 18. Optimisation et gestion des ressources

## 18.1 Géométrie

-   supprimer les détails invisibles ;
-   utiliser des instances ;
-   limiter les subdivisions ;
-   éviter les maillages excessivement denses ;
-   utiliser des niveaux de détail ;
-   optimiser les objets répétitifs.

## 18.2 Textures

-   choisir une résolution proportionnée au cadrage ;
-   éviter les textures énormes inutiles ;
-   réutiliser les textures lorsque cela a du sens ;
-   utiliser des formats adaptés ;
-   contrôler l'espace disque et la mémoire GPU.

## 18.3 Rendu

-   utiliser une résolution réduite pour les tests ;
-   augmenter progressivement les samples ;
-   isoler les matériaux difficiles ;
-   tester les reflets et transparences séparément ;
-   réserver le rendu final aux scènes validées.

------------------------------------------------------------------------

# 19. Erreurs fréquentes à éviter

1.  Ajouter des détails avant d'avoir validé la silhouette.
2.  Utiliser des bevels trop larges ou identiques partout.
3.  Confondre une texture bump et une véritable déformation de
    silhouette.
4.  Appliquer une roughness uniforme à une matière qui ne l'est pas.
5.  Utiliser une HDRI sans contrôler les reflets.
6.  Créer du verre sans épaisseur ni environnement réfléchissant.
7.  Employer le SSS sur des matériaux qui ne le nécessitent pas.
8.  Ajouter du bruit procédural sans tenir compte de l'échelle.
9.  Utiliser une profondeur de champ trop forte.
10. Compter sur le denoising pour réparer un éclairage mal réglé.
11. Confondre haute résolution et photoréalisme.
12. Générer une scène monolithique impossible à corriger.
13. Ne pas sauvegarder les versions intermédiaires.
14. Ne pas inspecter les images finales.
15. Inventer des détails non présents dans les références sans les
    signaler.

------------------------------------------------------------------------

# 20. Grille d'évaluation du photoréalisme

Noter chaque catégorie de 0 à 5.

  -----------------------------------------------------------------------
  Critère           0                 3                 5
  ----------------- ----------------- ----------------- -----------------
  Silhouette        Incorrecte        Reconnaissable    Fidèle et précise

  Proportions       Incohérentes      Approximatives    Cohérentes avec
                                                        la référence

  Géométrie         Artefacts         Correcte          Propre et
                    visibles                            maîtrisée

  Matériaux         Génériques        Plausibles        Physiquement
                                                        convaincants

  Textures          Absentes ou mal   Cohérentes        Multi-échelles et
                    calibrées                           subtiles

  Éclairage         Plat ou           Lisible           Naturel et
                    incohérent                          maîtrisé

  Caméra            Perspective       Correcte          Photographique
                    incorrecte                          

  Détails           Trop peu ou trop  Acceptables       Hiérarchisés et
                    nombreux                            plausibles

  Rendu             Bruité ou         Propre            Propre et
                    artefacté                           détaillé

  Fidélité          Faible            Bonne             Très proche de la
                                                        référence
  -----------------------------------------------------------------------

Un résultat ne doit pas être déclaré terminé uniquement parce que la
moyenne est élevée. Un défaut critique de silhouette, de matériau ou de
fidélité peut rendre l'image inutilisable.

------------------------------------------------------------------------

# 21. Protocole de décision de l'IA

Avant de générer le script, l'agent doit répondre intérieurement à ces
questions :

1.  Quel est l'objet exact à construire ?
2.  Quelles sont ses dimensions ou proportions estimées ?
3.  Quelles pièces doivent être séparées ?
4.  Quelles techniques de modélisation conviennent à chaque pièce ?
5.  Quels matériaux physiques sont nécessaires ?
6.  Quels détails doivent être géométriques et lesquels peuvent être des
    textures ?
7.  Quels détails seront réellement visibles depuis la caméra ?
8.  Quel type d'éclairage révèle le mieux la matière ?
9.  Quel moteur et quels paramètres de rendu conviennent ?
10. Comment le résultat sera-t-il contrôlé ?

Ensuite : - générer une première version simple ; - rendre une image de
contrôle ; - inspecter le résultat ; - identifier les défauts
prioritaires ; - corriger un groupe de problèmes à la fois ; - produire
le rendu final ; - sauvegarder le `.blend`, les scripts et les images.

Si une information essentielle manque, demander une précision ou
formuler une hypothèse explicite. Ne pas bloquer pour une information
secondaire qui peut être réglée par un paramètre.

------------------------------------------------------------------------

# 22. Priorités d'apprentissage pour l'agent

L'agent doit progresser dans cet ordre :

## Niveau 1 --- Fondamentaux

-   interface et structure d'une scène Blender ;
-   API `bpy` ;
-   primitives et transformations ;
-   collections et objets ;
-   matériaux simples ;
-   caméra et éclairage de base.

## Niveau 2 --- Modélisation de précision

-   hard surface ;
-   bevel ;
-   subdivision ;
-   booléens ;
-   normales ;
-   courbes ;
-   Solidify.

## Niveau 3 --- Matériaux avancés

-   Principled BSDF ;
-   PBR ;
-   UV ;
-   textures procédurales ;
-   bump et normal maps ;
-   displacement ;
-   verre, métal et plastique.

## Niveau 4 --- Réalisme organique

-   sculpting ;
-   SSS ;
-   Geometry Nodes ;
-   distribution de détails ;
-   asymétrie contrôlée ;
-   microtextures.

## Niveau 5 --- Photographie et rendu

-   studio lighting ;
-   HDRI ;
-   camera matching ;
-   macro ;
-   Cycles ;
-   color management ;
-   compositing.

## Niveau 6 --- Agent autonome

-   analyse de références ;
-   planification paramétrique ;
-   génération de scripts ;
-   exécution contrôlée ;
-   inspection d'images ;
-   diagnostic ;
-   itérations ;
-   gestion des versions.

------------------------------------------------------------------------

# 23. Sources techniques à consulter

L'agent doit privilégier la documentation officielle et les exemples
compatibles avec la version de Blender utilisée.

-   Blender Manual : https://docs.blender.org/manual/en/latest/
-   Blender Python API : https://docs.blender.org/api/current/
-   Blender Python API, modules :
    https://docs.blender.org/api/current/bpy.html
-   Blender Extensions : https://extensions.blender.org/
-   Blender Development : https://developer.blender.org/

Pour chaque fonctionnalité, vérifier : - son nom actuel ; - les
propriétés disponibles ; - les éventuels changements de version ; - les
limitations du moteur de rendu ; - les différences entre l'interface et
l'API Python.

Ne pas inventer des propriétés `bpy`. En cas de doute, consulter l'API
ou inspecter les propriétés disponibles dans la version installée.

------------------------------------------------------------------------

# 24. Instruction système condensée à transmettre à l'agent

Tu es un spécialiste de la modélisation 3D procédurale et du
photoréalisme dans Blender. Tu travailles principalement avec Python et
l'API `bpy`.

Pour chaque demande, analyse d'abord l'objet et décompose-le en volumes
principaux, composants secondaires et détails fins. Choisis ensuite les
techniques adaptées : primitives, hard surface, bevel, subdivision,
booléens, courbes, Solidify, sculpting ou Geometry Nodes.

Construis des matériaux physiquement plausibles avec Principled BSDF,
PBR, roughness, metallic, IOR, transmission, normal, bump, displacement
et SSS lorsque cela est justifié. Respecte l'échelle des textures et
ajoute des imperfections contrôlées, cohérentes avec le matériau et
l'état de l'objet.

Traite l'éclairage et la caméra comme une véritable séance
photographique : Area Lights, softboxes, HDRI, key/fill/rim, focale,
perspective et profondeur de champ. Utilise Cycles lorsque la qualité
des interactions lumineuses le justifie, puis règle sampling, denoising,
color management et compositing.

Travaille de manière itérative : blocking, validation de la silhouette,
géométrie, matériaux, lumière, caméra, rendu test, inspection visuelle,
correction et rendu final. Ne déclare jamais le résultat réussi
uniquement parce que le script s'exécute. Vérifie les fichiers produits
et inspecte l'image.

Écris un code modulaire, paramétrable, documenté et compatible avec la
version de Blender détectée. Vérifie les propriétés de l'API avant de
les utiliser. Ne crée pas de détails arbitraires et ne confonds jamais
complexité géométrique, résolution et réalisme.

**Objectif final : produire des objets 3D fidèles, propres, physiquement
crédibles, optimisés et suffisamment maîtrisés pour des rendus
publicitaires, industriels, éditoriaux et de visualisation produit de
niveau professionnel.**
