"use strict";

/**
 * Pilotage de la recherche (deux champs synchronises : barre du haut + panneau Filtres).
 *
 * Flux d'une saisie :
 *   1. debounce 120 ms (on n'interroge pas a chaque frappe) ;
 *   2. RACCOURCI nom exact : si la requete est exactement le nom (ou l'entreprise) d'une ou plusieurs
 *      solutions, insensible a la casse et aux accents, on n'affiche QUE celle(s)-la ;
 *   3. sinon Typesense si joignable (recherche tolerante cote serveur) ;
 *   4. sinon repli client-side (namespace.searchIndex, via app.filteredSolutions -> utils.matchesQuery).
 *
 * `state.searchIds` vaut un Set d'ids (resultat Typesense ou nom exact) ou null (= pas de filtre serveur,
 * le repli client s'applique). Le compteur `runId` ignore une reponse Typesense tardive quand une frappe
 * plus recente a deja pris le relais.
 */
(function attachSearch(namespace) {
  const { normalize } = namespace.utils;

  function bind(context) {
    const { data, elements, state, render } = context;
    const inputs = [elements.searchInput, elements.filtersSearchInput].filter(Boolean);
    const clear = elements.searchClear;
    let timer = null;
    let runId = 0;

    // Ids des solutions dont le nom (ou l'entreprise) EST exactement la requete normalisee.
    // null s'il n'y a aucune correspondance exacte.
    function exactNameIds(normalizedQuery) {
      if (!normalizedQuery) return null;
      const ids = [];
      for (const s of data.solutions) {
        const name = normalize(s.solution_name).trim();
        const company = normalize(s.company_name || "").trim();
        if (name === normalizedQuery || company === normalizedQuery) ids.push(s.id);
      }
      return ids.length ? new Set(ids) : null;
    }

    async function runSearch(value) {
      const myRun = ++runId;
      const q = (value || "").trim();
      if (!q) { state.searchIds = null; render(); return; }

      // Nom exact -> on n'affiche que cette/ces solution(s).
      const exact = exactNameIds(normalize(q).trim());
      if (exact) { state.searchIds = exact; render(); return; }

      // Typesense (recherche tolerante cote serveur) si disponible.
      if (namespace.typesense) {
        try {
          const ids = await namespace.typesense.search(q);
          if (myRun !== runId) return;                 // une frappe plus recente a pris le relais
          state.searchIds = ids;
          render();
          return;
        } catch (e) {
          if (window.console) console.warn("Typesense indisponible, recherche client-side:", e.message);
        }
      }
      // Repli client-side : searchIds = null -> app.filteredSolutions utilise matchesQuery.
      if (myRun !== runId) return;
      state.searchIds = null;
      render();
    }

    function applyValue(value, immediate) {
      state.search = value;
      state.searchNormalized = normalize(value).trim();
      if (clear) clear.hidden = !value;
      // Garde les deux barres de recherche synchronisees.
      inputs.forEach((field) => { if (field.value !== value) field.value = value; });
      if (timer) clearTimeout(timer);
      if (immediate) runSearch(value);
      else timer = setTimeout(() => runSearch(value), 120);
    }

    inputs.forEach((field) => field.addEventListener("input", () => applyValue(field.value, false)));
    if (clear) {
      clear.addEventListener("click", () => {
        applyValue("", true);
        if (elements.searchInput) elements.searchInput.focus();
      });
    }
  }

  namespace.search = { bind };
})(window.CP);
