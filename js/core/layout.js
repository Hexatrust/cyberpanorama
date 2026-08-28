"use strict";

/**
 * Disposition "camembert hexagonal" : UN seul grand hexagone (contour hexagonal strict) decoupe
 * en 6 parts triangulaires, une par fonction NIST. L'ANGLE de chaque part est proportionnel a son
 * nombre de logos (avec un minimum pour rester lisible). Les logos sont packes dans chaque part,
 * clippes au perimetre de l'hexagone. Aucune coordonnee n'est persistee cote donnees.
 */
(function attachLayout(namespace) {
  const { sectors, view, hexagon, logos, sizeScale } = namespace.config;

  const SIN60 = Math.sqrt(3) / 2;
  const DEG = Math.PI / 180;
  const sizePriority = { very_large: 0, large: 1, medium: 2, small: 3 };

  const hexGeom = new Map();
  let bigHex = { cx: view.cx, cy: view.cy, R: 900 };
  let maxTotalSeen = 0;                                // nb total d'acteurs (pour l'echelle adaptative)

  // Hexagone REGULIER flat-top de circumrayon R (sommets gauche/droite, aretes plates haut/bas).
  function hexPoints(cx, cy, R) {
    const h = R * SIN60;
    return [
      [cx + R, cy], [cx + R / 2, cy - h], [cx - R / 2, cy - h],
      [cx - R, cy], [cx - R / 2, cy + h], [cx + R / 2, cy + h],
    ];
  }

  // Distance du centre au PERIMETRE de l'hexagone flat-top a l'angle theta (deg). Les normales
  // d'aretes sont a 30 + 60k deg ; r = apotheme / cos(ecart a la normale la plus proche).
  function hexRadiusAt(R, thetaDeg) {
    const apo = R * SIN60;
    const k = Math.round((thetaDeg - 30) / 60);
    const normal = 30 + 60 * k;
    return apo / Math.cos((thetaDeg - normal) * DEG);
  }
  function boundaryPoint(cx, cy, R, thetaDeg) {
    const r = hexRadiusAt(R, thetaDeg);
    return [cx + r * Math.cos(thetaDeg * DEG), cy + r * Math.sin(thetaDeg * DEG)];
  }

  // Polygone d'une part [a0,a1] en COURONNE : bord exterieur = hexagone Router, bord interieur =
  // hexagone Rinner (trou central blanc). En incluant les sommets des deux hexagones, les bords
  // suivent EXACTEMENT les hexagones (contour hexagonal strict, dedans comme dehors).
  function sectorPolygon(cx, cy, Router, Rinner, a0, a1, straightInner) {
    const pts = [];
    pts.push(boundaryPoint(cx, cy, Router, a0));
    const firstO = Math.ceil((a0 + 0.001) / 60) * 60;
    for (let v = firstO; v < a1 - 0.001; v += 60) pts.push(boundaryPoint(cx, cy, Router, v));
    pts.push(boundaryPoint(cx, cy, Router, a1));
    pts.push(boundaryPoint(cx, cy, Rinner, a1));
    // Bord interieur : par defaut suit l'hexagone central (les parts se touchent proprement). Pour un
    // quartier SEUL (straightInner), on le laisse droit -> fond plat, sans l'encoche en "W" du sommet central.
    if (!straightInner) {
      const lastI = Math.floor((a1 - 0.001) / 60) * 60;
      for (let v = lastI; v > a0 + 0.001; v -= 60) pts.push(boundaryPoint(cx, cy, Rinner, v));
    }
    pts.push(boundaryPoint(cx, cy, Rinner, a0));
    return pts;
  }

  // Decalage angulaire (deg) pour obtenir un ecart PERPENDICULAIRE constant `g` (unites viewBox) au
  // rayon r : sin(offset) = g / r. Pres du centre (r petit) l'angle est plus grand qu'au bord -> le
  // blanc garde la MEME largeur du centre au perimetre (au lieu de s'evaser comme un retrait angulaire fixe).
  function gapDegAt(r, g) { return Math.asin(Math.min(0.5, g / Math.max(1, r))) / DEG; }

  // Comme sectorPolygon mais l'ecart entre parts est une LARGEUR CONSTANTE `gapPx` de chaque cote
  // (frontiere radiale rentree perpendiculairement), au lieu d'un angle fixe. Le bord de la part reste
  // ainsi parallele a la frontiere -> blanc d'epaisseur reguliere sur toute la separation.
  function sectorPolygonGap(cx, cy, Router, Rinner, a0, a1, gapPx, straightInner) {
    const bo0 = a0 + gapDegAt(hexRadiusAt(Router, a0), gapPx);   // bord exterieur, cote a0
    const bo1 = a1 - gapDegAt(hexRadiusAt(Router, a1), gapPx);   // bord exterieur, cote a1
    const bi0 = a0 + gapDegAt(hexRadiusAt(Rinner, a0), gapPx);   // bord interieur, cote a0
    const bi1 = a1 - gapDegAt(hexRadiusAt(Rinner, a1), gapPx);   // bord interieur, cote a1
    const pts = [];
    pts.push(boundaryPoint(cx, cy, Router, bo0));
    const firstO = Math.ceil((bo0 + 0.001) / 60) * 60;
    for (let v = firstO; v < bo1 - 0.001; v += 60) pts.push(boundaryPoint(cx, cy, Router, v));
    pts.push(boundaryPoint(cx, cy, Router, bo1));
    pts.push(boundaryPoint(cx, cy, Rinner, bi1));
    if (!straightInner) {
      const lastI = Math.floor((bi1 - 0.001) / 60) * 60;
      for (let v = lastI; v > bi0 + 0.001; v -= 60) pts.push(boundaryPoint(cx, cy, Rinner, v));
    }
    pts.push(boundaryPoint(cx, cy, Rinner, bi0));
    return pts;
  }

  function chipSize(size, fit) {
    // Option "logos a taille egale" (filtre Affichage, page /hexatrust) : on neutralise le facteur
    // taille d'entreprise -> tous les logos partagent le meme gabarit dans un secteur (l'ajustement
    // fit par secteur reste applique). Par defaut la taille d'entreprise s'applique, ici comme ailleurs.
    const scale = namespace.config.uniformChipSize ? 1 : (sizeScale[size] || 1);
    const s = logos.baseChip * scale * fit;
    return logos.maxChip ? Math.min(logos.maxChip, s) : s;     // plafond : pas de logo geant
  }

  function sortedForPlacement(list) {
    return list.slice().sort((a, b) => {
      const da = sizePriority[a.size] ?? 3;
      const db = sizePriority[b.size] ?? 3;
      if (da !== db) return da - db;
      return a.solution_name.localeCompare(b.solution_name);
    });
  }

  function bboxOf(poly) {
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    poly.forEach((p) => { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); });
    return [x0, y0, x1, y1];
  }
  // Intervalles [x0,x1] ou la ligne horizontale y est DANS le polygone (scanline, even-odd).
  function intervalsAt(poly, y) {
    const xs = [];
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const yi = poly[i][1];
      const yj = poly[j][1];
      if ((yi > y) !== (yj > y)) {
        const xi = poly[i][0];
        const xj = poly[j][0];
        xs.push(xi + ((xj - xi) * (y - yi)) / (yj - yi));
      }
    }
    xs.sort((p, q) => p - q);
    const iv = [];
    for (let i = 0; i + 1 < xs.length; i += 2) iv.push([xs[i], xs[i + 1]]);
    return iv;
  }
  function intersectIntervals(a, b) {
    const out = [];
    a.forEach((u) => b.forEach((v) => {
      const lo = Math.max(u[0], v[0]);
      const hi = Math.min(u[1], v[1]);
      if (hi - lo > 0) out.push([lo, hi]);
    }));
    return out;
  }

  // Packe les logos en RANGEES qui REMPLISSENT toute la part : pour chaque rangee, on calcule les
  // segments ou le carre tient (haut ET bas dans le polygone) et on aligne les logos dedans. Le
  // binaire sur `fit` maximise la taille -> les logos remplissent vraiment la part (pas un cercle).
  function packSector(sorted, poly, fit) {
    const [, minY, , maxY] = bboxOf(poly);
    const gap = logos.gap;
    const placements = [];
    let idx = 0;
    let guard = 0;
    let y = minY;
    while (idx < sorted.length) {
      if (guard++ > 4000) return null;
      const rowH = chipSize(sorted[idx].size, fit);
      const cy = y + rowH / 2;
      if (cy + rowH / 2 > maxY) return null;             // plus de place verticale : fit trop grand
      // Epsilon : sans lui, une ligne de scan PILE sur un bord horizontal (haut/bas plat du quartier)
      // est degeneree (aucun croisement detecte) -> la premiere/derniere rangee est sautee, d'ou une
      // grosse marge en haut. On rentre les scanlines d'un poil pour que le bord plat se remplisse.
      const valid = intersectIntervals(intervalsAt(poly, cy - rowH / 2 + 0.7), intervalsAt(poly, cy + rowH / 2 - 0.7));
      for (const seg of valid) {
        let x = seg[0];
        while (idx < sorted.length) {
          const s = chipSize(sorted[idx].size, fit);
          if (s > rowH + 0.5) break;
          if (x + s > seg[1]) break;
          placements.push({ solution: sorted[idx], x: x + s / 2, y: cy, chip: { width: s, height: s } });
          idx += 1;
          x += s + gap;
        }
      }
      y += rowH + gap;
    }
    return placements;
  }

  function packSectorBest(sorted, poly) {
    if (!sorted.length) return [];
    let lo = 0.05;
    let hi = 5.0;
    let best = packSector(sorted, poly, lo) || [];
    for (let it = 0; it < 22; it += 1) {
      const fit = (lo + hi) / 2;
      const placed = packSector(sorted, poly, fit);
      if (placed) { best = placed; lo = fit; } else { hi = fit; }
    }
    return best;
  }

  function computeSectorGeometry(allSolutions) {
    const grouped = new Map();
    Object.keys(sectors).forEach((l1) => grouped.set(l1, []));
    allSolutions.forEach((s) => {
      const l1 = s.nist && s.nist.level1;
      if (grouped.has(l1)) grouped.get(l1).push(s);
    });
    const countOf = (l1) => (grouped.get(l1) || []).length;

    const cfg = namespace.config.hexBig || {};
    const order = namespace.config.sectorOrder
      || ["Gouverner", "Récupérer", "Protéger", "Répondre", "Détecter", "Identifier"];
    const visibleOrder = order.filter((l1) => countOf(l1) > 0);
    const total = visibleOrder.reduce((sum, l1) => sum + countOf(l1), 0) || 1;

    const cx = view.cx;
    const cy = view.cy;
    const maxR = cfg.radius || 950;
    const innerRbase = cfg.innerRadius || 360;        // hexagone blanc central (branding) a pleine echelle
    // ECHELLE ADAPTATIVE : tout (hexagone + trou central + branding) retrecit uniformement quand il y a
    // moins de logos (ex. filtre sur une part). Plein -> 1 ; peu de logos -> proche de minScale.
    maxTotalSeen = Math.max(maxTotalSeen, total);
    const isFull = total >= maxTotalSeen;             // vue d'ensemble (tous les acteurs) ?
    const single = visibleOrder.length === 1;         // un seul secteur : on montre SON quartier agrandi
    const fMin = cfg.minScale || 0.42;
    // Echelle adaptative : le quartier (ou l'hexagone) est dimensionne au nombre de logos, pour que
    // les logos (plafonnes a maxChip) le REMPLISSENT au lieu de flotter dans un trop grand espace.
    // fitViewBox recadre ensuite pour occuper l'ecran : un seul secteur apparait donc bien agrandi.
    const fRaw = Math.min(1, Math.sqrt(total / Math.max(1, maxTotalSeen)));
    // Un seul secteur : on laisse la taille descendre selon le nb de logos (plancher bas) pour qu'ils
    // remplissent le quartier ; fitToScreen le recadre ensuite. Multi/plein : plancher normal.
    const f = single ? Math.max(0.2, fRaw) : Math.max(fMin, fRaw);
    const R = maxR * f;
    // Vue pleine : trou hexagonal central (branding). Un seul secteur : petit trou (vrai quartier de
    // camembert qui pointe vers le centre). Filtre multi-secteurs : quasi pas de trou.
    const innerR = single ? R * 0.18 : (isFull ? innerRbase * f : 8);
    const xs = cfg.xStretch || 1;                     // etirement horizontal (cotes)
    const ys = cfg.yStretch || 1;                     // etirement vertical (haut/bas)
    // maxR sert au CADRAGE (constant) : un hexagone filtre (plus petit) est dessine plus petit et
    // CENTRE dans le meme cadre, au lieu d'etre re-zoome pour remplir l'ecran. `scale` = f (branding).
    bigHex = { cx, cy, R, innerR, xs, ys, maxR, scale: f, full: isFull };
    hexGeom.clear();
    // Etire un point autour du centre (logos restent carres, l'hexagone s'agrandit / s'allonge).
    const stretch = (p) => [cx + (p[0] - cx) * xs, cy + (p[1] - cy) * ys];

    // Angle d'une part = minimum + part proportionnelle du reste (selon le nb de logos).
    const minDeg = cfg.minAngle != null ? cfg.minAngle : 26;
    const remain = Math.max(0, 360 - minDeg * visibleOrder.length);
    // Un seul secteur : quartier large fixe (pas 360 -> evite l'hexagone plein et la fente centrale).
    const SINGLE_SPAN = cfg.singleSpan != null ? cfg.singleSpan : 132;
    const spanOf = (l1) => (single ? SINGLE_SPAN : minDeg + remain * (countOf(l1) / total));

    // Premiere part visible CENTREE en haut (-90), on tourne dans le sens horaire.
    let a = -90 - (visibleOrder.length ? spanOf(visibleOrder[0]) / 2 : 0);
    order.forEach((l1) => {
      const sec = sectors[l1];
      const c = countOf(l1);
      if (c === 0) {
        hexGeom.set(l1, { l1, visible: false, count: 0, placed: [], color: sec.color, accent: sec.accent, ink: sec.ink });
        return;
      }
      const span = spanOf(l1);
      const a0 = a;
      const a1 = a + span;
      a = a1;
      // Marge entre les parts : ECART BLANC de largeur CONSTANTE de chaque cote (centre -> bord).
      const gapPx = cfg.sectorGapPx != null ? cfg.sectorGapPx : 7;
      const drawPoly = sectorPolygonGap(cx, cy, R, innerR, a0, a1, gapPx, single).map(stretch);
      // Polygone de packing un peu plus RENTRE (radial + ecart plus large) -> aucun logo ne deborde.
      const packPoly = sectorPolygonGap(cx, cy, R - hexagon.innerPad * 1.6, innerR + hexagon.innerPad * 1.6, a0, a1, gapPx + 8, single).map(stretch);
      const placed = packSectorBest(sortedForPlacement(grouped.get(l1)), packPoly);
      const am = (a0 + a1) / 2;
      // Onglet du libelle A L'EXTERIEUR de l'hexagone + ancre sur le bord (pour le trait de liaison).
      const outR = hexRadiusAt(R, am) + R * 0.16;     // espacement proportionnel (plus proche si quartier petit)
      const outPt = stretch([cx + outR * Math.cos(am * DEG), cy + outR * Math.sin(am * DEG)]);
      const anchorPt = stretch(boundaryPoint(cx, cy, R, am));
      hexGeom.set(l1, {
        l1, a0, a1, cx, cy, R, innerR,
        color: sec.color, accent: sec.accent, ink: sec.ink,
        count: c, placed, visible: true,
        polygon: drawPoly,
        labelX: outPt[0], labelY: outPt[1],
        anchorX: anchorPt[0], anchorY: anchorPt[1],
      });
    });
    return hexGeom;
  }

  function computeLayout() {
    const placed = [];
    hexGeom.forEach((g) => { if (g.visible) placed.push(...g.placed); });
    return { placed, unplaced: [] };
  }

  // Quartier AUTONOME pour la popup secteur : meme forme que dans le camembert (large en haut, pointe
  // vers le centre, fond plat) mais isole et dimensionne au nombre de logos. La popup recadre via viewBox.
  function popupSector(level1, solutions) {
    const sec = sectors[level1] || {};
    const cx = view.cx;
    const cy = view.cy;
    const R = 700;
    const innerR = R * 0.16;
    const span = 150;
    const a0 = -90 - span / 2;
    const a1 = -90 + span / 2;
    const gapPx = (namespace.config.hexBig && namespace.config.hexBig.sectorGapPx) || 7;
    const pad = hexagon.innerPad * 1.6;
    const polygon = sectorPolygonGap(cx, cy, R, innerR, a0, a1, gapPx, true);
    const packPoly = sectorPolygonGap(cx, cy, R - pad, innerR + pad, a0, a1, gapPx + 8, true);
    const placed = packSectorBest(sortedForPlacement(solutions || []), packPoly);
    let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
    polygon.forEach((p) => { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); });
    const m = 40;
    return {
      polygon, placed, color: sec.color, accent: sec.accent, ink: sec.ink,
      viewBox: { x: x0 - m, y: y0 - m, w: (x1 - x0) + 2 * m, h: (y1 - y0) + 2 * m },
    };
  }

  function getGeom(level1) { return hexGeom.get(level1); }
  function allGeom() { return hexGeom; }
  function getBigHex() { return bigHex; }
  function sectorCount(level1) { const g = hexGeom.get(level1); return g ? g.count : 0; }

  namespace.layout = {
    computeSectorGeometry, computeLayout, getGeom, allGeom, getBigHex, sectorCount, hexPoints, popupSector,
  };
})(window.CP);
