"use strict";

/**
 * Menu hamburger (mobile). Sous 760px la barre du haut n'a plus la place d'afficher le titre, la barre
 * de recherche et les boutons cote a cote : on deplace alors la recherche, le bouton Filtres et le bouton
 * Solutions dans un panneau deroulant ouvert par le bouton hamburger. Au dela de 760px les elements
 * reprennent leur place d'origine dans la barre. On DEPLACE les vrais noeuds (pas de copie) : leurs
 * ecouteurs (recherche, ouverture des tiroirs) restent donc actifs.
 */
(function attachMobileMenu(namespace) {
  function bind() {
    const menuBtn = document.getElementById("menuToggle");
    const menu = document.getElementById("mobileMenu");
    if (!menuBtn || !menu) return;

    const movable = [
      document.querySelector(".topbar-center"),
      document.getElementById("filtersToggle"),
      document.getElementById("drawerToggle"),
    ].filter(Boolean);

    // Memorise l'emplacement d'origine (parent + noeud suivant) pour restaurer la barre sur desktop.
    const homes = movable.map((el) => ({ el, parent: el.parentNode, next: el.nextSibling }));
    const mq = window.matchMedia("(max-width: 760px)");

    function setOpen(open) {
      menu.hidden = !open;
      menuBtn.setAttribute("aria-expanded", String(open));
    }

    function apply() {
      if (mq.matches) {
        homes.forEach(({ el }) => menu.appendChild(el));
      } else {
        homes.forEach(({ el, parent, next }) => parent.insertBefore(el, next));
        setOpen(false);
      }
    }

    apply();
    mq.addEventListener("change", apply);

    menuBtn.addEventListener("click", () => setOpen(menu.hidden));
    // Ouvrir un tiroir (Filtres / Solutions) referme le menu pour liberer la vue.
    menu.addEventListener("click", (event) => {
      if (event.target.closest("#filtersToggle, #drawerToggle")) setOpen(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !menu.hidden) setOpen(false);
    });
  }

  namespace.mobileMenu = { bind };
})(window.CP);
