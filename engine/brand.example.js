// Exemple de fichier de marque (rebranding). Le copier en work/brand.js puis l'inclure dans les
// scènes AVANT rm.js :  <script src="../brand.js"></script>
// - colors : chaque couleur source (clé) est remplacée par la couleur de la marque (valeur),
//            dans les formes, les textes ET les plaques WebGL.
// - texts  : id de l'élément -> nouveau texte (même taille, même ancrage que l'original).
// - mode   : 'decalque' (plaques mesurées, fidélité maximale) ou 'code' (formes 100 % paramétriques).
window.BRAND = {
  mode: 'decalque',
  colors: { '#5000B0': '#0B6E4F', '#FFFFFF': '#FFF8EC', '#C9C9C9': '#C8C2B4' },
  texts: { every: 'Chaque', brand: 'marque', starts: 'commence', come: 'prend', alive: 'vie' },
};
