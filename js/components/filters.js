"use strict";

/**
 * Panneau Filtres : cases des fonctions NIST niveau 1 et des categories/sous-categories niveau 2/3.
 * Met a jour l'etat (state.activeLevel1/2/3) et relance le rendu ; les filtres masquent/attenuent des
 * logos sans changer la forme du camembert.
 */
(function attachFilters(namespace) {
  const { level1Order } = namespace.config;
  const { buildCounts } = namespace.utils;

  function renderFunctionFilters(context) {
    const { data, elements, render, state } = context;
    const counts = buildCounts(data.solutions, (solution) => [
      solution.nist.level1,
    ]);
    const fragment = document.createDocumentFragment();

    level1Order.forEach((level1) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "fn-chip";
      button.dataset.level1 = level1;
      button.dataset.sector = level1;
      const isActive = state.activeLevel1.has(level1);
      button.setAttribute("aria-pressed", String(isActive));
      const color = data.level1_catalog[level1]?.color || "#f5f1e8";
      button.style.setProperty("--chip-bg", color);

      const name = document.createElement("span");
      name.className = "fn-name";
      name.textContent = level1;
      button.appendChild(name);

      const count = document.createElement("span");
      count.className = "fn-count";
      count.textContent = String(counts.get(level1) || 0);
      button.appendChild(count);

      button.addEventListener("click", () => {
        if (state.activeLevel1.has(level1)) {
          state.activeLevel1.delete(level1);
        } else {
          state.activeLevel1.add(level1);
        }
        if (state.activeLevel1.size === 0) {
          level1Order.forEach((value) => state.activeLevel1.add(value));
        }
        renderFunctionFilters(context);
        render();
      });

      fragment.appendChild(button);
    });

    elements.functionFilters.replaceChildren(fragment);
  }

  function renderCheckboxFilters(container, items, activeSet, type, render) {
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "empty-filter";
      empty.textContent = "Aucune donnée disponible";
      container.replaceChildren(empty);
      return;
    }

    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const id = `${type}-${item.code.replace(/[^a-z0-9]/gi, "-")}`;
      const label = document.createElement("label");
      label.className = "check-row";
      label.setAttribute("for", id);

      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = id;
      input.checked = activeSet.has(item.code);
      input.addEventListener("change", () => {
        if (input.checked) {
          activeSet.add(item.code);
        } else {
          activeSet.delete(item.code);
        }
        render();
      });

      const text = document.createElement("span");
      // Format : "Full Name (CODE)" si on a un nom, sinon juste le code
      text.textContent = item.label
        ? `${item.label} (${item.code})`
        : item.code;
      text.title = item.label ? `${item.code} — ${item.label}` : item.code;

      const count = document.createElement("span");
      count.className = "check-count";
      count.textContent = String(item.count);

      label.append(input, text, count);
      fragment.appendChild(label);
    });

    container.replaceChildren(fragment);
  }

  function renderLevelFilters(context) {
    const { data, elements, render, state } = context;
    const level2Counts = buildCounts(
      data.solutions,
      (solution) => solution.nist.level2,
    );
    const level2Items = Object.entries(data.level2_catalog)
      .filter(([code]) => level2Counts.has(code))
      .map(([code, info]) => ({
        code,
        label: info.label,
        count: level2Counts.get(code),
      }))
      .sort((a, b) => a.code.localeCompare(b.code));

    const level3Counts = buildCounts(
      data.solutions,
      (solution) => solution.nist.level3,
    );
    const level3Catalog = data.level3_catalog || {};
    const level3Items = Array.from(level3Counts.entries())
      .map(([code, count]) => ({
        code,
        label: level3Catalog[code] || "",
        count,
      }))
      .sort((a, b) => a.code.localeCompare(b.code));

    renderCheckboxFilters(
      elements.level2Filters,
      level2Items,
      state.activeLevel2,
      "level2",
      render,
    );
    renderCheckboxFilters(
      elements.level3Filters,
      level3Items,
      state.activeLevel3,
      "level3",
      render,
    );
  }

  // Filtre par taille d'entreprise (du plus grand au plus petit). Memes libelles que la fiche.
  const SIZE_ORDER = ["very_large", "large", "medium", "small"];
  const SIZE_LABELS = {
    very_large: "Grand groupe",
    large: "ETI / Scale-up",
    medium: "PME",
    small: "Startup / TPME",
  };

  function renderSizeFilters(context) {
    const { data, elements, render, state } = context;
    const counts = buildCounts(data.solutions, (solution) => [solution.size]);
    const fragment = document.createDocumentFragment();

    SIZE_ORDER.forEach((code) => {
      const n = counts.get(code) || 0;
      if (!n) return; // on n'affiche pas une taille sans acteur
      const id = `size-${code}`;
      const label = document.createElement("label");
      label.className = "check-row";
      label.setAttribute("for", id);

      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = id;
      input.checked = state.activeSizes.has(code);
      input.addEventListener("change", () => {
        if (input.checked) {
          state.activeSizes.add(code);
        } else {
          state.activeSizes.delete(code);
        }
        render();
      });

      const text = document.createElement("span");
      text.textContent = SIZE_LABELS[code] || code;

      const count = document.createElement("span");
      count.className = "check-count";
      count.textContent = String(n);

      label.append(input, text, count);
      fragment.appendChild(label);
    });

    elements.sizeFilters.replaceChildren(fragment);
  }

  namespace.filters = {
    renderFunctionFilters,
    renderLevelFilters,
    renderSizeFilters,
  };
})(window.CP);
