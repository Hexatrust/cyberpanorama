"use strict";

/**
 * Ouverture/fermeture des deux tiroirs lateraux : Filtres (gauche) et liste des Solutions (droite),
 * via leurs boutons, la croix, un clic exterieur ou Echap.
 */
(function attachDrawer(namespace) {
  function setOpen(node, isOpen) {
    if (isOpen) {
      node.hidden = false;
      requestAnimationFrame(() => node.classList.add("is-open"));
    } else {
      node.classList.remove("is-open");
      setTimeout(() => { node.hidden = true; }, 220);
    }
  }

  function openList(context) {
    setOpen(context.elements.drawer, true);
    context.elements.drawerToggle.setAttribute("aria-expanded", "true");
    context.render();
  }

  function closeList(context) {
    setOpen(context.elements.drawer, false);
    context.elements.drawerToggle.setAttribute("aria-expanded", "false");
  }

  function toggleList(context) {
    if (context.elements.drawer.hidden) openList(context);
    else closeList(context);
  }

  function openFilters(context) {
    setOpen(context.elements.filtersDrawer, true);
    context.elements.filtersToggle.setAttribute("aria-expanded", "true");
  }

  function closeFilters(context) {
    setOpen(context.elements.filtersDrawer, false);
    context.elements.filtersToggle.setAttribute("aria-expanded", "false");
  }

  function toggleFilters(context) {
    if (context.elements.filtersDrawer.hidden) openFilters(context);
    else closeFilters(context);
  }

  // Rend un tiroir redimensionnable au drag : poignee sur son bord interieur, largeur memorisee
  // dans localStorage. side = 'right' (tiroir gauche, on tire vers la droite) ou 'left' (tiroir droit).
  function makeResizable(drawer, side) {
    if (!drawer || drawer.querySelector(".drawer-resize")) return;
    const handle = document.createElement("div");
    handle.className = "drawer-resize";
    handle.setAttribute("aria-hidden", "true");
    drawer.appendChild(handle);
    const key = "cp-drawer-w-" + drawer.id;
    const saved = parseInt(localStorage.getItem(key) || "", 10);
    if (saved) drawer.style.setProperty("--drawer-w", saved + "px");
    let startX = 0;
    let startW = 0;
    const onMove = (event) => {
      const dx = event.clientX - startX;
      let w = side === "right" ? startW + dx : startW - dx;
      w = Math.max(280, Math.min(Math.round(window.innerWidth * 0.75), w));
      drawer.style.setProperty("--drawer-w", w + "px");
    };
    const onUp = () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.body.classList.remove("is-resizing");
      const w = parseInt(getComputedStyle(drawer).getPropertyValue("--drawer-w"), 10);
      if (w) localStorage.setItem(key, String(w));
    };
    handle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      event.stopPropagation();
      startX = event.clientX;
      startW = drawer.getBoundingClientRect().width;
      document.body.classList.add("is-resizing");
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    });
  }

  function bind(context) {
    const { elements } = context;
    makeResizable(elements.filtersDrawer, "right");
    makeResizable(elements.drawer, "left");
    elements.drawerToggle.addEventListener("click", () => toggleList(context));
    elements.drawerClose.addEventListener("click", () => closeList(context));
    elements.filtersToggle.addEventListener("click", () => toggleFilters(context));
    elements.filtersClose.addEventListener("click", () => closeFilters(context));

    // Clic en dehors : on ferme le panneau Filtres. Le tiroir Solutions, lui, RESTE ouvert (on peut
    // consulter le panorama a cote) ; il se ferme via sa croix ou Echap.
    document.addEventListener("pointerdown", (event) => {
      const target = event.target;
      if (!elements.filtersDrawer.hidden
          && !elements.filtersDrawer.contains(target)
          && !elements.filtersToggle.contains(target)) {
        closeFilters(context);
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || !elements.modal.hidden) return;
      if (!elements.drawer.hidden) closeList(context);
      else if (!elements.filtersDrawer.hidden) closeFilters(context);
    });
  }

  namespace.drawer = { bind, openList, closeList, toggleList, openFilters, closeFilters, toggleFilters };
})(window.CP);
