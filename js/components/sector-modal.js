"use strict";

/**
 * Popup d'un secteur : clic sur une part (ou son onglet) -> on ouvre une popup montrant UNIQUEMENT ce
 * secteur (son quartier du camembert, agrandi, rempli de ses logos), sur un fond assombri. Clic a cote
 * (hors du cadre), bouton Fermer ou Echap = fermeture. Les autres secteurs ne sont pas affiches.
 */
(function attachSectorModal(namespace) {
  const { assetPath, initials, svgElement, tagLightLogo } = namespace.utils;

  function pointsAttr(points) {
    return points.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  }

  function buildLogo(placement, vb, openModal) {
    const { solution, x, y, chip } = placement;
    const div = document.createElement("div");
    div.className = "logo popup-logo";
    div.dataset.solutionId = solution.id;
    div.dataset.sector = solution.nist.level1;
    div.setAttribute("role", "button");
    div.setAttribute("tabindex", "0");
    div.setAttribute("aria-label", solution.solution_name);
    div.title = solution.solution_name;
    div.style.left = `${(((x - vb.x) / vb.w) * 100).toFixed(3)}%`;
    div.style.top = `${(((y - vb.y) / vb.h) * 100).toFixed(3)}%`;
    if (chip) {
      div.style.setProperty("--chip-w", `${((chip.width / vb.w) * 100).toFixed(3)}%`);
      div.style.aspectRatio = `${chip.width} / ${chip.height}`;
    }
    if (solution.logo_path) {
      const img = document.createElement("img");
      img.src = assetPath(solution.logo_path);
      img.alt = "";
      img.loading = "lazy";
      img.decoding = "async";
      img.addEventListener("error", () => {
        img.remove();
        div.textContent = initials(solution.solution_name);
        div.classList.add("logo-missing");
      }, { once: true });
      div.appendChild(img);
      tagLightLogo(img, div, solution.id);
    } else {
      div.textContent = initials(solution.solution_name);
      div.classList.add("logo-missing");
    }
    div.addEventListener("click", (event) => { event.stopPropagation(); openModal(solution.id); });
    div.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openModal(solution.id); }
    });
    return div;
  }

  function open(level1, context) {
    const { data, elements, state } = context;
    // Memes filtres que le panorama (cf. app.filteredSolutions) : on n'affiche dans la popup QUE les
    // solutions reellement visibles. Important : si la recherche renvoie un Set d'ids (Typesense / nom
    // exact), on s'en sert plutot que matchesQuery, sinon la popup montrait plus large que le panorama.
    const q = state.searchNormalized;
    const sols = data.solutions.filter((s) => {
      if (s.nist.level1 !== level1) return false;
      if (!namespace.utils.hasIntersection(s.nist.level2, state.activeLevel2)) return false;
      if (!namespace.utils.hasIntersection(s.nist.level3, state.activeLevel3)) return false;
      if (!q) return true;
      if (state.searchIds instanceof Set) return state.searchIds.has(s.id);
      return namespace.utils.matchesQuery(s, q);
    });

    elements.sectorPopupTitle.textContent = level1;
    elements.sectorPopupCount.textContent = String(sols.length);

    const g = namespace.layout.popupSector(level1, sols);
    const vb = g.viewBox;
    const slice = elements.sectorModal.querySelector(".sector-popup-slice");
    if (slice) {
      slice.dataset.sector = level1;
      if (g.accent) { slice.style.setProperty("--sector-accent", g.accent); slice.style.setProperty("--sector-fill", g.color); }
    }

    const svg = document.getElementById("sectorPopupSvg");
    const frame = document.getElementById("sectorPopupFrame");
    svg.setAttribute("viewBox", `${vb.x.toFixed(1)} ${vb.y.toFixed(1)} ${vb.w.toFixed(1)} ${vb.h.toFixed(1)}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    // Cadre : occupe le viewport en gardant l'aspect du quartier.
    const aspect = vb.w / vb.h;
    let frameW = window.innerWidth * 0.9;
    let frameH = frameW / aspect;
    if (frameH > window.innerHeight * 0.86) { frameH = window.innerHeight * 0.86; frameW = frameH * aspect; }
    frame.style.width = `${Math.floor(frameW)}px`;
    frame.style.height = `${Math.floor(frameH)}px`;

    const sectorLayer = document.getElementById("popupSectorLayer");
    sectorLayer.replaceChildren();
    const poly = svgElement("polygon");
    poly.setAttribute("points", pointsAttr(g.polygon));
    poly.setAttribute("fill", g.color);
    poly.setAttribute("fill-opacity", String(namespace.config.sectorFillOpacity != null ? namespace.config.sectorFillOpacity : 0.32));
    poly.setAttribute("stroke", g.accent);
    poly.setAttribute("stroke-width", "3");
    poly.setAttribute("stroke-linejoin", "round");
    sectorLayer.appendChild(poly);
    const bannerLayer = document.getElementById("popupBannerLayer");
    if (bannerLayer) bannerLayer.replaceChildren();

    const overlay = document.getElementById("popupLogoLayer");
    overlay.replaceChildren();
    const frag = document.createDocumentFragment();
    g.placed.forEach((pl) => frag.appendChild(buildLogo(pl, vb, (id) => { close(context); namespace.modal.open(id, context); })));
    overlay.appendChild(frag);

    elements.sectorModal.hidden = false;
    requestAnimationFrame(() => elements.sectorModal.classList.add("is-open"));
    if (elements.sectorPopupClose) elements.sectorPopupClose.focus();
  }

  function close(context) {
    const { elements } = context;
    elements.sectorModal.classList.remove("is-open");
    setTimeout(() => { elements.sectorModal.hidden = true; }, 200);
  }

  function bind(context) {
    const { elements } = context;
    if (elements.sectorPopupClose) elements.sectorPopupClose.addEventListener("click", () => close(context));
    // Tout clic qui n'est PAS sur un logo (ni le bouton Fermer / le bandeau d'info) ferme la popup :
    // le fond assombri, le quartier lui-meme, ET les coins blancs du cadre autour du quartier.
    elements.sectorModal.addEventListener("click", (event) => {
      if (!event.target.closest(".popup-logo, .sector-popup-close-btn, .sector-popup-info")) close(context);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !elements.sectorModal.hidden) close(context);
    });
  }

  namespace.sectorModal = { bind, open, close };
})(window.CP);
