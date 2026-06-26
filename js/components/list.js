"use strict";

/**
 * Liste des solutions filtrees (tiroir de droite) : une carte cliquable par acteur (logo + nom +
 * fonction). Le clic ouvre la fiche detaillee (modal). Affiche l'etat vide si aucun resultat.
 */
(function attachList(namespace) {
  const { assetPath, initials, tagLightLogo } = namespace.utils;

  function createLogo(solution) {
    const wrap = document.createElement("span");
    wrap.className = "sol-card-logo";
    if (solution.logo_path) {
      const image = document.createElement("img");
      image.src = assetPath(solution.logo_path);
      image.alt = "";
      image.loading = "lazy";
      image.addEventListener(
        "error",
        () => {
          image.remove();
          wrap.textContent = initials(solution.solution_name);
        },
        { once: true },
      );
      wrap.appendChild(image);
      tagLightLogo(image, wrap, solution.id); // fond foncé auto si le logo est blanc
    } else {
      wrap.textContent = initials(solution.solution_name);
    }
    return wrap;
  }

  function createCard(solution, openModal) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "sol-card";
    card.dataset.solutionId = solution.id;
    card.dataset.sector = solution.nist.level1;
    card.setAttribute("role", "listitem");

    const text = document.createElement("span");
    text.className = "sol-card-text";

    const name = document.createElement("span");
    name.className = "sol-card-name";
    name.textContent = solution.solution_name;

    const meta = document.createElement("span");
    meta.className = "sol-card-meta";
    const subLabels = solution.nist.level2.length
      ? solution.nist.level2.slice(0, 2).join(" · ")
      : solution.company_name || "";
    meta.textContent = subLabels;

    text.append(name, meta);

    const tag = document.createElement("span");
    tag.className = "sol-card-tag";
    tag.textContent = solution.nist.level1;

    card.append(createLogo(solution), text, tag);
    card.addEventListener("click", () => openModal(solution.id));
    return card;
  }

  function renderActiveChips(context, visibleCount) {
    const { elements, state } = context;
    const container = elements.activeChips;
    container.replaceChildren();

    const totalLevel1 = namespace.config.level1Order.length;
    if (state.activeLevel1.size !== totalLevel1) {
      Array.from(state.activeLevel1).forEach((level1) => {
        container.appendChild(
          makeChip(level1, () => {
            state.activeLevel1.delete(level1);
            if (state.activeLevel1.size === 0) {
              namespace.config.level1Order.forEach((value) =>
                state.activeLevel1.add(value),
              );
            }
            namespace.filters.renderFunctionFilters(context);
            context.render();
          }),
        );
      });
    }
    Array.from(state.activeLevel2).forEach((code) => {
      container.appendChild(
        makeChip(code, () => {
          state.activeLevel2.delete(code);
          namespace.filters.renderLevelFilters(context);
          context.render();
        }),
      );
    });
    Array.from(state.activeLevel3).forEach((code) => {
      container.appendChild(
        makeChip(code, () => {
          state.activeLevel3.delete(code);
          namespace.filters.renderLevelFilters(context);
          context.render();
        }),
      );
    });
    if (state.search) {
      container.appendChild(
        makeChip(`« ${state.search} »`, () => {
          elements.searchInput.value = "";
          state.search = "";
          state.searchNormalized = "";
          elements.searchClear.hidden = true;
          context.render();
        }),
      );
    }

    elements.resultsCount.textContent = String(visibleCount);
    elements.resultCount.textContent = String(visibleCount);
  }

  function makeChip(label, onRemove) {
    const chip = document.createElement("span");
    chip.className = "active-chip";
    chip.textContent = label;
    const close = document.createElement("button");
    close.type = "button";
    close.setAttribute("aria-label", `Retirer ${label}`);
    close.innerHTML =
      '<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
    close.addEventListener("click", onRemove);
    chip.appendChild(close);
    return chip;
  }

  let lastVisibleIds = null;

  function renderList(visible, context, openModal) {
    const { elements } = context;
    renderActiveChips(context, visible.length);

    if (elements.drawer.hidden) {
      lastVisibleIds = null;
      return;
    }
    const currentIds = visible.map((s) => s.id).join(",");
    if (currentIds === lastVisibleIds) return;
    lastVisibleIds = currentIds;

    const fragment = document.createDocumentFragment();
    visible.forEach((solution) =>
      fragment.appendChild(createCard(solution, openModal)),
    );
    elements.solutionList.replaceChildren(fragment);
    elements.emptyState.hidden = visible.length !== 0;
  }

  namespace.list = { renderList };
})(window.CP);
