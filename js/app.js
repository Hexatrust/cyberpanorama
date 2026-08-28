"use strict";

/**
 * Point d'entree de l'app : recupere les elements du DOM, tient l'etat (filtres NIST + recherche +
 * zoom), cable les modules (panorama, filtres, recherche, tiroirs, modales, menu mobile) et orchestre
 * le rendu. `render()` recalcule la geometrie du camembert, place les logos visibles et met a jour la
 * liste. Un garde-fou recharge la page si un module n'a pas pu se charger.
 */
(function bootstrap(namespace) {
  // Garde-fou de chargement : si un <script> de module n'a pas pu se charger (1er affichage a
  // froid, requete perdue), `window.CP` est incomplet et la page s'affichait cassee
  // ("0 solutions" + hexagone vide). On recharge alors AUTOMATIQUEMENT (au plus 2 fois) pour
  // s'auto reparer, au lieu de peindre une page incomplete.
  const ns = namespace || {};
  const REQUIRED = [
    "config",
    "utils",
    "searchIndex",
    "layout",
    "filters",
    "search",
    "panorama",
    "zoom",
    "list",
    "drawer",
    "modal",
    "sectorModal",
    "mobileMenu",
  ];
  const missing = REQUIRED.filter((m) => !ns[m]);
  if (!window.CYBERPANORAMA_DATA) missing.push("data");
  if (missing.length) {
    const tries = Number(sessionStorage.getItem("cp_boot_retry") || "0");
    if (tries < 2) {
      sessionStorage.setItem("cp_boot_retry", String(tries + 1));
      location.reload();
      return;
    }
    console.error(
      "CyberPanorama : modules non charges apres rechargement:",
      missing.join(", "),
    );
    return;
  }
  sessionStorage.removeItem("cp_boot_retry");

  // Mode de page : "hexatrust" (page /hexatrust) sinon panorama general. Un seul filtrage ici suffit :
  // tous les composants lisent data.solutions, donc le dataset filtre se propage partout.
  //   /hexatrust        -> uniquement les membres HexaTrust (is_hexatrust), y compris sieges hors France
  //   panorama general  -> tout SAUF les sieges hors France (hq_outside_france)
  const mode = window.CP_MODE === "hexatrust" ? "hexatrust" : "main";
  const rawData = window.CYBERPANORAMA_DATA;
  const data = Object.assign({}, rawData, {
    solutions: (rawData.solutions || []).filter((s) =>
      mode === "hexatrust" ? s.is_hexatrust : !s.hq_outside_france),
  });
  // Drapeau de page lu par la geometrie (logos uniformes) et le branding (HexaTrust seul, pas de CESIN).
  namespace.config.hexatrustPage = (mode === "hexatrust");
  // Gabarit des logos : par defaut la taille d'entreprise s'applique sur les DEUX pages. Sur
  // /hexatrust, le filtre "Affichage" peut la neutraliser (tous les logos a la meme taille).
  namespace.config.uniformChipSize = false;
  const { level1Order } = namespace.config;

  const elements = {
    hexPanorama: document.getElementById("hexPanorama"),
    hexWrapper: document.getElementById("hexWrapper"),
    functionFilters: document.getElementById("functionFilters"),
    level2Filters: document.getElementById("level2Filters"),
    level3Filters: document.getElementById("level3Filters"),
    resetFilters: document.getElementById("resetFilters"),
    searchInput: document.getElementById("searchInput"),
    filtersSearchInput: document.getElementById("filtersSearchInput"),
    searchClear: document.getElementById("searchClear"),
    resultCount: document.getElementById("resultCount"),
    resultsCount: document.getElementById("resultsCount"),
    activeChips: document.getElementById("activeChips"),
    solutionList: document.getElementById("solutionList"),
    emptyState: document.getElementById("emptyState"),
    zoomIn: document.getElementById("zoomIn"),
    zoomOut: document.getElementById("zoomOut"),
    zoomReset: document.getElementById("zoomReset"),
    zoomValue: document.getElementById("zoomValue"),
    panToggle: document.getElementById("panToggle"),
    drawer: document.getElementById("drawer"),
    drawerToggle: document.getElementById("drawerToggle"),
    drawerClose: document.getElementById("drawerClose"),
    filtersDrawer: document.getElementById("filtersDrawer"),
    filtersToggle: document.getElementById("filtersToggle"),
    filtersClose: document.getElementById("filtersClose"),
    filtersCountBadge: document.getElementById("filtersCountBadge"),
    sectorModal: document.getElementById("sectorModal"),
    sectorPopupTitle: document.getElementById("sectorPopupTitle"),
    sectorPopupCount: document.getElementById("sectorPopupCount"),
    sectorPopupClose: document.getElementById("sectorPopupClose"),
    modal: document.getElementById("solutionModal"),
    modalClose: document.getElementById("modalClose"),
    modalLogo: document.getElementById("modalLogo"),
    modalCompany: document.getElementById("modalCompany"),
    modalTitle: document.getElementById("modalTitle"),
    modalFunction: document.getElementById("modalFunction"),
    modalSize: document.getElementById("modalSize"),
    sizeFilters: document.getElementById("sizeFilters"),
    displayGroup: document.getElementById("displayGroup"),
    displayFilters: document.getElementById("displayFilters"),
    modalBody: document.getElementById("modalBody"),
  };

  const state = {
    activeLevel1: new Set(level1Order),
    activeLevel2: new Set(),
    activeLevel3: new Set(),
    activeSizes: new Set(), // tailles d'entreprise selectionnees (vide = toutes)
    uniformSize: false, // /hexatrust : tous les logos au meme gabarit (option d'affichage)
    search: "",
    searchNormalized: "",
    searchIds: null, // Set d'IDs renvoyes par Typesense (null = pas de recherche / repli)
    modalSolutionId: null,
    zoom: 1,
    zoomSector: null, // part sur laquelle on a zoome (clic) ; null = vue complete
  };

  const context = {
    data,
    elements,
    state,
    solutionsById: new Map(
      data.solutions.map((solution) => [solution.id, solution]),
    ),
    render,
  };

  function filteredSolutions() {
    const q = state.searchNormalized;
    return data.solutions.filter((solution) => {
      if (!state.activeLevel1.has(solution.nist.level1)) return false;
      if (
        !namespace.utils.hasIntersection(
          solution.nist.level2,
          state.activeLevel2,
        )
      )
        return false;
      if (
        !namespace.utils.hasIntersection(
          solution.nist.level3,
          state.activeLevel3,
        )
      )
        return false;
      // Type d'entreprise : si des tailles sont cochees, ne garder que celles-la.
      if (state.activeSizes.size && !state.activeSizes.has(solution.size))
        return false;
      // Recherche : Typesense (state.searchIds = Set) si dispo, sinon repli client-side.
      if (!q) return true;
      if (state.searchIds instanceof Set)
        return state.searchIds.has(solution.id);
      return namespace.utils.matchesQuery(solution, q);
    });
  }

  function openModal(solutionId) {
    namespace.modal.open(solutionId, context);
  }

  function sectorCounts(visible) {
    const counts = new Map(level1Order.map((level1) => [level1, 0]));
    visible.forEach((solution) => {
      const level1 = solution.nist.level1;
      counts.set(level1, (counts.get(level1) || 0) + 1);
    });
    return counts;
  }

  // Clic sur une part (ou son onglet) : on ouvre une POPUP montrant uniquement ce secteur (son quartier
  // agrandi, rempli de ses logos). Clic a cote ferme la popup. Le camembert de fond reste inchange.
  function toggleSector(level1) {
    namespace.sectorModal.open(level1, context);
  }

  function activeFilterCount() {
    let count = 0;
    // Nombre de fonctions SELECTIONNEES (et non exclues) : selectionner Gouverner = 1, pas 5.
    if (state.activeLevel1.size < level1Order.length) {
      count += state.activeLevel1.size;
    }
    count += state.activeLevel2.size;
    count += state.activeLevel3.size;
    count += state.activeSizes.size;
    if (state.search) count += 1;
    return count;
  }

  function render() {
    // Option d'affichage lue par la geometrie (chipSize) avant tout calcul de placement.
    namespace.config.uniformChipSize = state.uniformSize;
    const visible = filteredSolutions();
    const counts = sectorCounts(visible);
    const allActive = state.activeLevel1.size === level1Order.length;

    // Le camembert garde TOUJOURS sa forme complete. Les secteurs SANS resultat (recherche ou filtre)
    // sont grises (updateSectorState) ; seuls ceux qui contiennent des entreprises visibles restent en
    // couleur. Les logos non visibles ne sont pas dessines.
    namespace.layout.computeSectorGeometry(data.solutions);
    namespace.panorama.renderPanoramaBase(
      elements.hexPanorama,
      toggleSector,
      resetFilters,
    );
    namespace.panorama.fitViewBox(elements.hexPanorama);
    namespace.panorama.updateSectorState(counts, state.activeLevel1, allActive);

    const layout = namespace.layout.computeLayout();
    const visibleIds = new Set(visible.map((s) => s.id));
    namespace.panorama.renderLogos(elements.hexPanorama, {
      placed: layout.placed.filter((p) => visibleIds.has(p.solution.id)),
    });

    namespace.list.renderList(visible, context, openModal);

    const activeCount = activeFilterCount();
    if (activeCount > 0) {
      elements.filtersCountBadge.textContent = String(activeCount);
      elements.filtersCountBadge.hidden = false;
    } else {
      elements.filtersCountBadge.hidden = true;
    }
  }

  function resetFilters() {
    state.zoomSector = null; // clic CyberPanorama / reset = retour vue complete (dezoom)
    state.activeLevel1 = new Set(level1Order);
    state.activeLevel2.clear();
    state.activeLevel3.clear();
    state.activeSizes.clear();
    state.uniformSize = false;
    state.search = "";
    state.searchNormalized = "";
    state.searchIds = null;
    elements.searchInput.value = "";
    elements.searchClear.hidden = true;
    namespace.filters.renderFunctionFilters(context);
    namespace.filters.renderLevelFilters(context);
    namespace.filters.renderSizeFilters(context);
    namespace.filters.renderDisplayFilters(context);
    render();
    if (namespace.zoom && namespace.zoom.fitToScreen)
      namespace.zoom.fitToScreen(context);
  }

  function hideSkeleton() {
    const skeleton = document.getElementById("appSkeleton");
    if (!skeleton) return;
    skeleton.classList.add("is-hidden");
    skeleton.addEventListener("transitionend", () => skeleton.remove(), {
      once: true,
    });
    setTimeout(() => skeleton.remove(), 700);
  }

  function init() {
    // Index de recherche tolérante (tokens + synonymes), construit une fois sur les données.
    if (namespace.searchIndex) namespace.searchIndex.build(data);
    // Géométrie adaptative des secteurs (rayon variable selon le nb d'acteurs) — forme fixe.
    namespace.layout.computeSectorGeometry(data.solutions);
    // 1) Setup léger : base du panorama, filtres, écouteurs — peint rapidement sous le skeleton.
    namespace.panorama.renderPanoramaBase(elements.hexPanorama, toggleSector);
    namespace.filters.renderFunctionFilters(context);
    namespace.filters.renderLevelFilters(context);
    namespace.filters.renderSizeFilters(context);
    namespace.filters.renderDisplayFilters(context);
    namespace.search.bind(context);
    namespace.zoom.bind(context);
    namespace.drawer.bind(context);
    namespace.modal.bind(context);
    namespace.sectorModal.bind(context);
    namespace.mobileMenu.bind(context);
    elements.resetFilters.addEventListener("click", resetFilters);

    // 2) Travail lourd (création des ~280 logos + layout) après un premier paint,
    //    pour que le skeleton et la base du panorama s'affichent sans blocage.
    let heavyDone = false;
    const heavy = () => {
      if (heavyDone) return; // ne s'execute qu'une fois (rAF OU timeout, le premier)
      heavyDone = true;
      namespace.panorama.ensureLogos(
        elements.hexPanorama,
        data.solutions,
        openModal,
      );
      render();
      // Zoom auto : tout le panorama tient dans la fenetre au premier affichage.
      if (namespace.zoom.fitToScreen) namespace.zoom.fitToScreen(context);
      hideSkeleton();
    };
    // rAF pour peindre apres le skeleton, MAIS rAF est gele quand l'onglet n'est pas au premier
    // plan -> filet de securite par setTimeout pour que les logos s'affichent quand meme.
    if ("requestAnimationFrame" in window) {
      requestAnimationFrame(() => requestAnimationFrame(heavy));
    }
    setTimeout(heavy, 350);
  }

  init();
})(window.CP);
