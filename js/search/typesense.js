"use strict";

/**
 * Client Typesense pour la recherche de l'app.
 * search(query) renvoie un Set d'IDs de solutions correspondantes (tolerant aux fautes + synonymes),
 * ou null si la requete est vide. Leve une erreur si Typesense est injoignable (l'app retombe alors
 * sur la recherche client-side).
 *
 * SECURITE : aucune cle API n'est embarquee ici. Le reverse-proxy HTTPS injecte cote serveur une cle
 * SEARCH-ONLY et n'expose publiquement QUE l'endpoint de recherche (le reste -> 403). Le navigateur
 * n'envoie donc aucune cle : rien d'exploitable n'est visible dans le code public.
 */
(function attachTypesense(namespace) {
  const config = {
    // Host de l'endpoint de recherche : AUCUNE URL en dur ici. Elle vient de window.CP_RUNTIME,
    // genere au deploiement depuis la variable GitHub TYPESENSE_HOST (cf. js/runtime-config.js et
    // .github/workflows/deploy-pages.yml). Vide -> on retombe sur la recherche client-side.
    host: (window.CP_RUNTIME && window.CP_RUNTIME.typesenseHost) || "",
    collection: "solutions",
    // Recherche a deux niveaux (comme l'index client). Niveau 1 : le NOM seul. S'il matche, on ne
    // renvoie que ces fiches (une recherche "thales" remonte Thales, pas toutes les fiches qui la
    // citent en client). Niveau 2, seulement si aucun nom ne matche : on elargit au contenu, y compris
    // la description detaillee, avec un poids faible pour limiter le bruit.
    nameQueryBy: "solution_name,company_name",
    nameQueryByWeights: "6,5",
    contentQueryBy: "solution_name,company_name,indexation,nis2_objective,detailed_description",
    contentQueryByWeights: "6,5,3,2,1",
  };

  // Une passe de recherche (paginee) sur un jeu de champs donne. Renvoie un Set d'ids.
  async function runQuery(q, queryBy, weights) {
    const ids = new Set();
    let page = 1;
    let found = Infinity;
    while (ids.size < found && page <= 3) {
      const params = new URLSearchParams({
        q,
        query_by: queryBy,
        query_by_weights: weights,
        num_typos: "1",
        prefix: "true",
        per_page: "250",
        page: String(page),
      });
      const url = `${config.host}/collections/${config.collection}/documents/search?${params}`;
      // Pas d'en-tete de cle : le reverse-proxy injecte la cle search-only cote serveur.
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Typesense HTTP ${res.status}`);
      const data = await res.json();
      found = data.found || 0;
      (data.hits || []).forEach((h) => ids.add(h.document.id));
      if (!data.hits || data.hits.length < 250) break;
      page += 1;
    }
    return ids;
  }

  async function search(query) {
    const q = (query || "").trim();
    if (!q) return null;
    if (!config.host) return null;          // pas d'host configure -> repli client-side
    // Niveau 1 : le nom. S'il matche, on ne renvoie que ces fiches.
    const nameIds = await runQuery(q, config.nameQueryBy, config.nameQueryByWeights);
    if (nameIds.size) return nameIds;
    // Niveau 2 : elargissement au contenu (mots-cles, NIS2, description detaillee).
    return runQuery(q, config.contentQueryBy, config.contentQueryByWeights);
  }

  async function health() {
    try {
      const res = await fetch(`${config.host}/health`);
      return res.ok;
    } catch (e) {
      return false;
    }
  }

  namespace.typesense = { search, health, config };
})(window.CP);
