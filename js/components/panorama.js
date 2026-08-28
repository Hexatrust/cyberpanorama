"use strict";

/**
 * Rendu SVG du camembert hexagonal : les 6 parts (couleurs NIST), leurs onglets de libelle, l'hexagone
 * central de branding, et l'overlay HTML des logos (positionnes en % du viewBox). Gere aussi le survol,
 * l'attenuation des parts filtrees et le clic (ouverture de la popup d'un secteur). La geometrie vient
 * de js/core/layout.js ; ce module ne fait que dessiner.
 */
(function attachPanorama(namespace) {
  const { level1Order, sectors, view, hexagon } = namespace.config;
  const sectorFillOpacity = namespace.config.sectorFillOpacity ?? 0.32;
  const { assetPath, initials, svgElement, tagLightLogo } = namespace.utils;

  const SIN60 = Math.sqrt(3) / 2;

  const sectorElements = new Map();
  const logoNodes = new Map();
  let logoLayerCache = null;
  let currentVB = { x: 0, y: 0, w: view.width, h: view.height };

  function clearLayer(svg, id) {
    const layer = svg.querySelector(`#${id}`);
    layer.replaceChildren();
    return layer;
  }

  function pointsAttr(points) {
    return points.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  }

  // Cadrage : etendue du GRAND hexagone (+ petite marge). Taille FIXE reglable (pxPerUnit) ; si ca
  // depasse la fenetre, on scrolle/pan, et "Ajuster" fait le fit ecran.
  function fitViewBox(svg, focusLevel1) {
    const hx = namespace.layout.getBigHex();
    let bb = null;
    // FOCUS sur une part : on cadre sur SON polygone (+ son onglet), le camembert garde sa forme et la
    // part selectionnee remplit l'ecran (les voisines debordent sur les cotes). Avec fitToScreen ensuite.
    if (focusLevel1 && namespace.layout.getGeom) {
      const g = namespace.layout.getGeom(focusLevel1);
      if (g && g.polygon && g.polygon.length) {
        let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
        g.polygon.forEach((p) => { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); });
        if (g.labelX != null) { x0 = Math.min(x0, g.labelX); x1 = Math.max(x1, g.labelX); y0 = Math.min(y0, g.labelY); y1 = Math.max(y1, g.labelY); }
        bb = { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
      }
    }
    // Sinon : contenu reel complet (getBBox) -> la vue pleine occupe tout le cadre.
    if (!bb || !bb.width || !bb.height) { try { bb = svg.getBBox(); } catch (e) { bb = null; } }
    if (!bb || !bb.width || !bb.height) {
      const xs = hx.xs || 1;
      const ys = hx.ys || 1;
      const frameR = hx.maxR || hx.R;
      bb = { x: hx.cx - frameR * xs, y: hx.cy - frameR * SIN60 * ys, width: 2 * frameR * xs, height: 2 * frameR * SIN60 * ys };
    }
    const pad = Math.max(40, Math.min(bb.width, bb.height) * (focusLevel1 ? 0.12 : 0.05));
    currentVB = { x: bb.x - pad, y: bb.y - pad, w: bb.width + 2 * pad, h: bb.height + 2 * pad };
    svg.setAttribute("viewBox",
      `${currentVB.x.toFixed(1)} ${currentVB.y.toFixed(1)} ${currentVB.w.toFixed(1)} ${currentVB.h.toFixed(1)}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    const frame = document.getElementById("hexFrame");
    if (frame) {
      const scale = (view && view.pxPerUnit) || 0.45;
      frame.style.setProperty("--frame-w", Math.round(currentVB.w * scale) + "px");
      frame.style.setProperty("--frame-h", Math.round(currentVB.h * scale) + "px");
      frame.style.setProperty("--vb-aspect", (currentVB.w / currentVB.h).toFixed(4));
    }
  }

  function attachToggle(group, level1, onToggle) {
    const onActivate = (event) => { event.stopPropagation(); onToggle(level1); };
    group.addEventListener("click", onActivate);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onActivate(event); }
    });
    // Survol : met ce secteur en avant (le CSS attenue les autres parts, onglets et logos).
    group.addEventListener("mouseenter", () => {
      const frame = document.getElementById("hexFrame");
      if (frame) frame.setAttribute("data-hovered-sector", level1);
    });
    group.addEventListener("mouseleave", () => {
      const frame = document.getElementById("hexFrame");
      if (frame) frame.removeAttribute("data-hovered-sector");
    });
  }

  // Une part (couronne triangulaire) du camembert hexagonal : polygone deja calcule par layout.
  function buildPieSector(level1, geom, onToggle) {
    const group = svgElement("g");
    group.setAttribute("class", "sector");
    group.setAttribute("data-level1", level1);
    group.setAttribute("data-sector", level1);
    group.setAttribute("role", "button");
    group.setAttribute("tabindex", "0");
    group.setAttribute("aria-label", `Filtrer ${level1}`);

    const poly = svgElement("polygon");
    poly.setAttribute("class", "sector-fill");
    poly.setAttribute("points", pointsAttr(geom.polygon));
    poly.setAttribute("fill", geom.color);
    poly.setAttribute("fill-opacity", String(sectorFillOpacity));
    poly.setAttribute("stroke", geom.accent);
    poly.setAttribute("stroke-width", "3");
    poly.setAttribute("stroke-linejoin", "round");
    group.appendChild(poly);

    attachToggle(group, level1, onToggle);
    return group;
  }

  // Libelle de la fonction : onglet colore A L'EXTERIEUR de l'hexagone (comme avant), au mid-angle.
  function buildPieLabel(level1, geom, onToggle) {
    const group = svgElement("g");
    group.setAttribute("class", "banner");
    group.setAttribute("data-sector", level1);
    group.setAttribute("role", "button");
    group.setAttribute("tabindex", "0");
    group.setAttribute("aria-label", `Filtrer ${level1}`);

    const label = level1.toUpperCase();
    const fontSize = 30;
    const tabH = 50;
    // Largeur genereuse : tient compte du gras + letter-spacing pour que le texte rentre ENTIER.
    const tabW = label.length * fontSize * 0.78 + 44;
    const x = geom.labelX - tabW / 2;
    const y = geom.labelY - tabH / 2;

    // Trait propre reliant l'onglet a sa part (du bord de l'hexagone jusqu'a l'onglet).
    if (geom.anchorX != null) {
      const link = svgElement("line");
      link.setAttribute("class", "banner-link");
      link.setAttribute("x1", geom.anchorX.toFixed(1));
      link.setAttribute("y1", geom.anchorY.toFixed(1));
      link.setAttribute("x2", geom.labelX.toFixed(1));
      link.setAttribute("y2", geom.labelY.toFixed(1));
      link.setAttribute("stroke", geom.accent);
      group.appendChild(link);
    }

    const rect = svgElement("rect");
    rect.setAttribute("class", "banner-fill");
    rect.setAttribute("x", x.toFixed(1));
    rect.setAttribute("y", y.toFixed(1));
    rect.setAttribute("width", tabW.toFixed(1));
    rect.setAttribute("height", String(tabH));
    rect.setAttribute("rx", "12");
    rect.setAttribute("fill", geom.accent);
    group.appendChild(rect);

    const text = svgElement("text");
    text.setAttribute("class", "banner-text");
    text.setAttribute("x", geom.labelX.toFixed(1));
    text.setAttribute("y", geom.labelY.toFixed(1));
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("dominant-baseline", "central");
    text.setAttribute("font-size", String(fontSize));
    text.textContent = label;
    group.appendChild(text);

    attachToggle(group, level1, onToggle);
    return group;
  }

  // Hexagone BLANC central + branding (CYBERPANORAMA BY HEXATRUST / CESIN) a l'interieur.
  function buildCenter(svg, onReset) {
    const layer = clearLayer(svg, "coreLayer");
    const hx = namespace.layout.getBigHex();
    // Vue FILTREE : rien au centre (juste les parts qui remplissent l'hexagone).
    if (!hx.full) return;
    const cx = hx.cx;
    const cy = hx.cy;
    const R = hx.innerR || 340;
    const xs = hx.xs || 1;
    const ys = hx.ys || 1;

    const hexa = svgElement("polygon");
    hexa.setAttribute("class", "center-hex");
    const pts = namespace.layout.hexPoints(cx, cy, R).map((p) => [cx + (p[0] - cx) * xs, cy + (p[1] - cy) * ys]);
    hexa.setAttribute("points", pointsAttr(pts));
    // Clic sur le coeur CYBERPANORAMA : retour a la vue de base (reset des filtres).
    if (onReset) {
      hexa.style.cursor = "pointer";
      hexa.setAttribute("role", "button");
      hexa.setAttribute("aria-label", "Revenir a la vue complete");
      hexa.addEventListener("click", (event) => { event.stopPropagation(); onReset(); });
    }
    layer.appendChild(hexa);

    const title = svgElement("text");
    title.setAttribute("class", "brand-title");
    title.setAttribute("x", cx.toFixed(1));
    title.setAttribute("y", (cy - 95).toFixed(1));           // CYBERPANORAMA (descendu)
    title.setAttribute("text-anchor", "middle");
    title.setAttribute("dominant-baseline", "middle");
    title.textContent = "CYBERPANORAMA";
    layer.appendChild(title);

    const by = svgElement("text");
    by.setAttribute("class", "brand-by");
    by.setAttribute("x", cx.toFixed(1));
    by.setAttribute("y", (cy - 58).toFixed(1));
    by.setAttribute("text-anchor", "middle");
    by.textContent = "BY";
    layer.appendChild(by);

    // Logos partenaires EMPILES (l'un au-dessus de l'autre) et AGRANDIS -> plus lisibles.
    const add = (href, w, h, top) => {
      const img = svgElement("image");
      img.setAttributeNS("http://www.w3.org/1999/xlink", "href", href);
      img.setAttribute("href", href);
      img.setAttribute("x", (cx - w / 2).toFixed(1));
      img.setAttribute("y", top.toFixed(1));
      img.setAttribute("height", String(h));
      img.setAttribute("width", String(w));
      img.setAttribute("preserveAspectRatio", "xMidYMid meet");
      layer.appendChild(img);
    };
    // Page /hexatrust : SEUL le logo HexaTrust (pas de CESIN), recentre puisqu'il est seul.
    const soloHexatrust = namespace.config.hexatrustPage;
    add("assets/hexatrust-logo.png", 420, 104, soloHexatrust ? cy + 8 : cy - 28);
    if (!soloHexatrust) add("assets/cesin-logo.svg", 260, 128, cy + 96);
  }

  function renderPanoramaBase(svg, onSectorToggle, onReset) {
    sectorElements.clear();
    const hexLayer = clearLayer(svg, "sectorLayer");
    const headerLayer = clearLayer(svg, "bannerLayer");

    level1Order.forEach((level1) => {
      const geom = namespace.layout.getGeom(level1);
      if (!geom || !geom.visible) return;
      const sectorGroup = buildPieSector(level1, geom, onSectorToggle);
      hexLayer.appendChild(sectorGroup);
      const labelGroup = buildPieLabel(level1, geom, onSectorToggle);
      headerLayer.appendChild(labelGroup);
      sectorElements.set(level1, { sectorGroup, bannerGroup: labelGroup });
    });

    buildCenter(svg, onReset);                  // hexagone blanc central + branding AU-DESSUS (clic = retour)
  }

  function buildLogo(solution, openModal) {
    const div = document.createElement("div");
    div.className = "logo";
    div.dataset.solutionId = solution.id;
    div.dataset.sector = solution.nist.level1;
    div.setAttribute("role", "button");
    div.setAttribute("tabindex", "-1");
    div.setAttribute("aria-label", solution.solution_name);
    div.title = solution.solution_name;
    div.style.display = "none";

    if (solution.logo_path) {
      div.classList.add("is-loading");
      const img = document.createElement("img");
      img.src = assetPath(solution.logo_path);
      img.alt = "";
      img.loading = "lazy";
      img.decoding = "async";
      img.addEventListener("load", () => div.classList.remove("is-loading"), { once: true });
      img.addEventListener("error", () => {
        div.classList.remove("is-loading");
        img.remove();
        div.textContent = initials(solution.solution_name);
        div.classList.add("logo-missing");
      }, { once: true });
      if (img.complete && img.naturalWidth > 0) div.classList.remove("is-loading");
      div.appendChild(img);
      tagLightLogo(img, div, solution.id);
    } else {
      div.textContent = initials(solution.solution_name);
      div.classList.add("logo-missing");
    }

    const onActivate = (event) => { event.stopPropagation(); openModal(solution.id); };
    div.addEventListener("click", onActivate);
    div.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onActivate(event); }
    });
    return div;
  }

  function ensureLogos(svg, allSolutions, openModal) {
    if (logoNodes.size > 0) return;
    logoLayerCache = document.getElementById("logoLayer");
    const fragment = document.createDocumentFragment();
    allSolutions.forEach((solution) => {
      const node = buildLogo(solution, openModal);
      logoNodes.set(solution.id, node);
      fragment.appendChild(node);
    });
    logoLayerCache.appendChild(fragment);
  }

  function renderLogos(svg, layout) {
    const visibleIds = new Set();
    layout.placed.forEach((placement) => {
      const node = logoNodes.get(placement.solution.id);
      if (!node) return;
      const left = ((placement.x - currentVB.x) / currentVB.w) * 100;
      const top = ((placement.y - currentVB.y) / currentVB.h) * 100;
      node.style.left = `${left.toFixed(3)}%`;
      node.style.top = `${top.toFixed(3)}%`;
      const chip = placement.chip;
      if (chip) {
        const widthPct = (chip.width / currentVB.w) * 100;
        node.style.setProperty("--chip-w", `${widthPct.toFixed(3)}%`);
        node.style.aspectRatio = `${chip.width} / ${chip.height}`;
      }
      node.setAttribute("tabindex", "0");
      node.style.display = "";
      visibleIds.add(placement.solution.id);
    });
    logoNodes.forEach((node, id) => {
      if (!visibleIds.has(id)) {
        node.style.display = "none";
        node.setAttribute("tabindex", "-1");
      }
    });
  }

  function updateSectorState(visibleCounts, activeLevel1, allActive) {
    sectorElements.forEach(({ sectorGroup, bannerGroup }, level1) => {
      // Un secteur reste EN COULEUR seulement s'il est dans le filtre de fonctions ET qu'il contient
      // au moins une entreprise visible (recherche/filtres). Sinon il est grise.
      const inFilter = activeLevel1.has(level1);
      const hasResults = (visibleCounts.get(level1) || 0) > 0;
      const colored = inFilter && hasResults;
      sectorGroup.setAttribute("data-selected", String(colored && !allActive));
      sectorGroup.setAttribute("data-dimmed", String(!colored));
      bannerGroup.setAttribute("data-dimmed", String(!colored));
    });
  }

  namespace.panorama = { renderPanoramaBase, fitViewBox, ensureLogos, renderLogos, updateSectorState };
})(window.CP);
