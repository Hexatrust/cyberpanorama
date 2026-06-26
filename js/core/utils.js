"use strict";

/**
 * Utilitaires partages (namespace.utils) : normalisation de texte (minuscule + sans accents),
 * filtrage (matchesQuery, hasIntersection), helpers SVG/DOM, initiales, et detection des logos clairs
 * (tagLightLogo) pour leur poser un fond fonce.
 */
(function attachUtils(namespace) {
  const { view } = namespace.config;

  function svgElement(name) {
    return document.createElementNS("http://www.w3.org/2000/svg", name);
  }

  function pointAt(angleDeg, radius, cx = view.cx, cy = view.cy) {
    const angle = angleDeg * Math.PI / 180;
    return {
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    };
  }

  function polygonPoints(points) {
    return points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
  }

  function assetPath(repoPath) {
    if (!repoPath) {
      return "";
    }
    if (/^(https?:|data:|file:)/i.test(repoPath)) {
      return repoPath;
    }
    // L'app est a la racine du site : les assets sont relatifs (assets/logos/...), pas un cran au-dessus.
    return repoPath;
  }

  function initials(value) {
    return value
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase();
  }

  function buildCounts(solutions, keyGetter) {
    const counts = new Map();
    solutions.forEach((solution) => {
      keyGetter(solution).forEach((value) => {
        counts.set(value, (counts.get(value) || 0) + 1);
      });
    });
    return counts;
  }

  function hasIntersection(values, activeSet) {
    if (!activeSet.size) {
      return true;
    }
    return values.some((value) => activeSet.has(value));
  }

  function normalize(text) {
    return (text || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "");
  }

  function matchesQuery(solution, normalizedQuery) {
    if (!normalizedQuery) return true;
    // Recherche tolérante (index maison tokens + synonymes) si prêt ; sinon repli sous-chaîne.
    const idx = namespace.searchIndex;
    if (idx) {
      const ids = idx.idsFor(normalizedQuery);
      if (ids) return ids.has(solution.id);
    }
    const data = window.CYBERPANORAMA_DATA || {};
    const l2Catalog = data.level2_catalog || {};
    const l3Catalog = data.level3_catalog || {};
    const l2Labels = (solution.nist?.level2 || []).map((c) => l2Catalog[c]?.label || "");
    const l3Labels = (solution.nist?.level3 || []).map((c) => l3Catalog[c] || "");
    // NB : on EXCLUT `solution.description` du repli. Sinon une requete comme "thales" matche toutes
    // les fiches qui citent Thales en reference client/partenaire. On cherche dans le nom, l'entreprise,
    // les mots-cles d'indexation et les libelles NIST.
    const haystacks = [
      solution.solution_name,
      solution.company_name,
      ...(solution.indexation || []),
      solution.nist?.level1,
      ...(solution.nist?.level2 || []),
      ...(solution.nist?.level3 || []),
      ...l2Labels,
      ...l3Labels,
    ];
    return haystacks.some((value) => normalize(value).includes(normalizedQuery));
  }

  /**
   * Détecte automatiquement les logos "blancs" (clairs et quasi sans pixel foncé) et, le cas
   * échéant, ajoute la classe `logo-on-dark` sur le conteneur le CSS lui met un fond foncé
   * pour que le logo reste visible (ex : YesWeHack, tout blanc, invisible sur fond clair).
   *
   * Principe (simple) : on dessine le logo dans un petit canvas 20x20, on parcourt les pixels
   * OPAQUES (on ignore la transparence) et on calcule leur luminance perçue
   * (formule standard 0.2126*R + 0.7152*V + 0.0722*B). Si la grande majorité des pixels sont
   * très clairs et qu'il n'y a presque aucun pixel foncé logo "blanc" fond foncé.
   */
  // Overrides manuels (la detection auto ne peut pas tout trancher) :
  // FORCE_ON_DARK : logos a fond fonce force (texte blanc + pictos colores, ex CrowdSec : le blanc
  //   est invisible sur clair mais dilue par les couleurs -> sous le seuil auto).
  // FORCE_ON_LIGHT : logos que l'auto met a tort sur fond fonce (a laisser sur clair).
  const FORCE_ON_DARK = new Set([
    "crowdsec",
  ]);
  const FORCE_ON_LIGHT = new Set([]);

  function tagLightLogo(img, container, solutionId) {
    if (solutionId && FORCE_ON_DARK.has(solutionId)) { container.classList.add("logo-on-dark"); return; }
    if (solutionId && FORCE_ON_LIGHT.has(solutionId)) return;
    const analyze = () => {
      try {
        const W = 20;
        const H = 20;
        const canvas = document.createElement("canvas");
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, W, H);
        const px = ctx.getImageData(0, 0, W, H).data;
        let opaque = 0;
        let light = 0;
        let darkNeutral = 0;
        let darkColor = 0;
        for (let i = 0; i < px.length; i += 4) {
          if (px[i + 3] < 40) continue;                       // pixel transparent ignoré
          opaque += 1;
          const r = px[i];
          const g = px[i + 1];
          const b = px[i + 2];
          const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
          const sat = Math.max(r, g, b) - Math.min(r, g, b);  // chroma approx
          if (lum > 200) light += 1;                          // quasi blanc (invisible sur fond clair)
          else if (lum < 120 && sat < 60) darkNeutral += 1;   // noir/gris fonce (perdu sur fonce ET visible sur clair)
          else if (lum < 120) darkColor += 1;                 // couleur SOMBRE (bleu nuit, violet...) : se perd aussi sur fonce
        }
        // Logo a passer sur fond fonce : le blanc DOMINE (sinon visible tel quel sur clair) et l'emporte
        // sur le contenu sombre (neutre ou colore) qui, lui, disparaitrait sur le fond fonce. On exige donc
        // light > 45% ET light > (sombres) ET quasiment aucun noir/gris neutre. Les couleurs CLAIRES/moyennes
        // (orange, rouge vif...) restent visibles sur les deux fonds : neutres dans la decision.
        const fLight = light / opaque;
        if (opaque > 8 && fLight > 0.45 && darkNeutral / opaque < 0.05
            && fLight > (darkNeutral + darkColor) / opaque) {
          container.classList.add("logo-on-dark");
        }
      } catch (e) {
        // canvas "tainté" (image cross-origin, ex en file://) on ne peut pas lire les pixels,
        // on ignore silencieusement (le logo reste affiché normalement).
      }
    };
    if (img.complete && img.naturalWidth > 0) analyze();
    else img.addEventListener("load", analyze, { once: true });
  }

  namespace.utils = {
    assetPath,
    buildCounts,
    hasIntersection,
    initials,
    matchesQuery,
    normalize,
    pointAt,
    polygonPoints,
    svgElement,
    tagLightLogo,
  };
})(window.CP);
