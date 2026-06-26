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
    // On NE cherche PAS dans `description` : sinon une requete comme "thales" remonte toutes les fiches
    // qui citent Thales comme client/partenaire. La recherche porte sur le nom, l'entreprise et les
    // mots-cles d'indexation (faits pour ca).
    queryBy: "solution_name,company_name,indexation,nis2_objective",
    queryByWeights: "6,5,3,1",
  };

  async function search(query) {
    const q = (query || "").trim();
    if (!q) return null;
    if (!config.host) return null;          // pas d'host configure -> repli client-side
    const ids = new Set();
    let page = 1;
    let found = Infinity;
    while (ids.size < found && page <= 3) {
      const params = new URLSearchParams({
        q,
        query_by: config.queryBy,
        query_by_weights: config.queryByWeights,
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
