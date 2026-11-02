# Exemple : démo de 64 s (libre de droits)

| Fichier | Rôle |
| --- | --- |
| `make_source.py` | Génère la vidéo « originale » `src/source.mp4` (64 s, 640×360, 25 i/s, musique 120 BPM), dessinée avec Pillow — un autre moteur que le navigateur, donc un vrai test |
| `analysis/measure.py` | Les mesures faites sur la vidéo (boîtes, ease, rotation, volet…) → `analysis/measures.json` |
| `analysis/beats.json` | Sortie de `beats.py` : 120 BPM, un mot par temps en S2 |
| `scenes/demo.html` | La reproduction : chaque valeur vient des mesures (commentaires dans `P`) |
| `manifest.json` | Les 4 segments à assembler |
| `brand.example.js` | Un rebrand (couleurs + textes) |

```bash
python3 make_source.py
python3 ../../scripts/assemble.py manifest.json out                                  # copie fidèle
python3 ../../scripts/assemble.py manifest.json out_brand --brand brand.example.js   # version rebrandée
```

Résultats mesurés : copie **SSIM 0,991** (S1 0,994 · S2 0,986 · S3 0,995 · S4 0,988), 0 anomalie,
0 plage à fantômes ; rebrand : rythme **identique** (décalage optimal 0 image).
