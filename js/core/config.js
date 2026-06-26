"use strict";

window.CP = window.CP || {};

/**
 * Configuration du panorama (fond blanc) : un seul grand hexagone decoupe en 6 parts (camembert
 * hexagonal), une par fonction NIST CSF 2.0, trou hexagonal central pour le branding. Tout est CALCULE :
 * l'ANGLE de chaque part est proportionnel a son nombre d'acteurs ; la taille des logos depend du palier
 * d'entreprise. Ce module ne fait que declarer les constantes ; la geometrie est dans js/core/layout.js.
 */
window.CP.config = {
  level1Order: ["Détecter", "Répondre", "Récupérer", "Gouverner", "Identifier", "Protéger"],
  view: {
    width: 1800,
    height: 1300,
    cx: 900,
    cy: 600,
    pxPerUnit: 0.45,              // echelle FIXE : px ecran par unite viewBox (taille reelle des hexagones)
  },
  // Camembert hexagonal : 1 grand hexagone, 6 parts a ANGLE proportionnel au nb de logos,
  // trou hexagonal blanc au centre (branding). Ordre des parts dans le sens horaire depuis le haut.
  hexBig: {
    radius: 950,                   // circumrayon du grand hexagone
    innerRadius: 360,              // hexagone blanc central (branding)
    minAngle: 26,                  // angle minimum d'une part (lisibilite des petites fonctions)
    sectorGapPx: 7,                // ECART BLANC entre parts, en unites viewBox, CONSTANT du centre au bord
                                   // (largeur perpendiculaire fixe ; l'offset angulaire s'adapte au rayon)
    xStretch: 1.18,                // etirement horizontal de l'hexagone (cotes ; logos restent carres)
    yStretch: 1.18,                // etirement vertical de l'hexagone (haut/bas ; logos restent carres)
  },
  sectorOrder: ["Gouverner", "Récupérer", "Protéger", "Répondre", "Détecter", "Identifier"],
  // Couleurs NIST exactes. fill = intérieur translucide de l'hexagone ; accent = bordure + onglet d'entête.
  sectors: {
    "Détecter":   { color: "#fab746", ink: "#1a1a1a", accent: "#fab746" },
    "Répondre":   { color: "#ed7368", ink: "#1a1a1a", accent: "#ed7368" },
    "Récupérer":  { color: "#92c78f", ink: "#1a1a1a", accent: "#92c78f" },
    "Gouverner":  { color: "#f7f19e", ink: "#1a1a1a", accent: "#f7f19e" },
    "Identifier": { color: "#4ab2df", ink: "#1a1a1a", accent: "#4ab2df" },
    "Protéger":   { color: "#9190c6", ink: "#1a1a1a", accent: "#9190c6" },
  },
  sectorFillOpacity: 0.32,        // intérieur translucide pastel (thème clair)
  hexagon: {
    minRadius: 330,               // rayon mini d'un hexagone (fonction la moins peuplée)
    maxRadius: 780,               // rayon maxi (Protéger, le plus peuplé) : domine nettement
    refCount: 150,                // nombre d'acteurs de reference (~Protéger) pour le calcul du rayon
    headerHeight: 44,             // hauteur du bandeau d'entête (à l'intérieur, en haut)
    headerGap: 8,
    headerFontSize: 22,
    innerPad: 16,                 // marge intérieure des logos vs les arêtes
  },
  // Échelle des logos par palier d'entreprise. Écart marqué mais borné pour que les petits
  // restent lisibles (les très grands groupes ressortent sans rendre les startups invisibles).
  sizeScale: { small: 1.0, medium: 1.55, large: 2.4, very_large: 3.6 },
  logos: {
    baseChip: 42,                 // taille de référence (palier small) ; multipliée par sizeScale
    gap: 8,
    maxChip: 120,                 // plafond : un logo ne grossit pas a l'infini (part peu peuplee)
  },
  zoom: {
    initial: 1.0,                 // taille fixe a l'echelle pxPerUnit (deborde/scrolle ; "Ajuster" = fit ecran)
    min: 0.2,                     // bas pour que "Ajuster" puisse reduire un grand panorama au format ecran
    max: 4,                       // plafond releve : un quartier filtre peu peuple peut etre agrandi pour remplir l'ecran
    step: 0.2,
  },
};
