"use strict";

/**
 * Recherche tolérante aux fautes + synonymes, côté client (sans serveur).
 *
 * Pour un index riche en acronymes (ztna, ndr, edr...), un matcher par TOKENS est bien plus precis
 * qu'une recherche floue globale. Pour chaque acteur on indexe l'ensemble de ses mots (nom, entreprise,
 * champ `indexation` = produit phare + mots-cles, libelles NIST). Une requete matche si :
 *   - exact      : le mot tape figure tel quel,
 *   - prefixe    : un mot indexe commence par le mot tape (>= 3 lettres),
 *   - faute      : distance d'edition <= 1 (mot tape >= 4 lettres) -> « ztng » trouve « ztna ».
 * Les synonymes/acronymes (ex : « zero trust » equivaut a « ztna ») viennent de `search_synonyms.json`
 * embarque dans les donnees : on ajoute des variantes de requete pour les termes du meme groupe.
 */
(function attachSearchIndex(namespace) {
  const { normalize } = namespace.utils;

  const STOP = new Set(["de", "des", "du", "la", "le", "les", "aux", "et", "en", "un", "une",
    "the", "and", "of", "to", "for", "with", "sur", "par", "ou"]);

  let docs = [];                 // [{ id, words: Set<string> }]
  let synonymLookup = new Map(); // terme normalisé -> Set des termes du même groupe
  let cacheQuery = null;
  let cacheIds = null;

  function tokenize(str) {
    return normalize(str)
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length >= 2 && !STOP.has(w));
  }

  function buildSynonymLookup(groups) {
    const lookup = new Map();
    (groups || []).forEach((group) => {
      const norm = group.map((t) => normalize(t).trim()).filter(Boolean);
      norm.forEach((term) => {
        if (!lookup.has(term)) lookup.set(term, new Set());
        norm.forEach((other) => lookup.get(term).add(other));
      });
    });
    return lookup;
  }

  function build(data) {
    const l2 = data.level2_catalog || {};
    const l3 = data.level3_catalog || {};
    docs = (data.solutions || []).map((s) => {
      // Mots du NOM (solution + entreprise) : ils sont prioritaires a la recherche.
      const nameParts = [s.solution_name || "", s.company_name || ""];
      // Mots de CONTENU : fonction, mots-cles d'indexation, libelles NIST et description detaillee.
      // Indexes mais non prioritaires (cf. idsFor) : une recherche qui matche un nom n'y descend pas.
      const contentParts = [s.nist?.level1 || ""]
        .concat(s.indexation || [])
        .concat((s.nist?.level2 || []).map((c) => l2[c]?.label || ""))
        .concat((s.nist?.level3 || []).map((c) => l3[c] || ""))
        .concat([s.detailed_description || ""]);
      const nameWords = new Set();
      nameParts.forEach((p) => tokenize(p).forEach((w) => nameWords.add(w)));
      const words = new Set(nameWords);   // le nom fait aussi partie du contenu global
      contentParts.forEach((p) => tokenize(p).forEach((w) => words.add(w)));
      return { id: s.id, nameWords, words };
    });
    synonymLookup = buildSynonymLookup(data.search_synonyms);
    cacheQuery = null;
    cacheIds = null;
  }

  // Distance d'edition <= 1 (suffisant pour les fautes de frappe simples).
  function within1(a, b) {
    if (a === b) return true;
    const la = a.length;
    const lb = b.length;
    if (Math.abs(la - lb) > 1) return false;
    let i = 0;
    let j = 0;
    let diff = 0;
    while (i < la && j < lb) {
      if (a[i] === b[j]) { i += 1; j += 1; continue; }
      diff += 1;
      if (diff > 1) return false;
      if (la > lb) i += 1;
      else if (lb > la) j += 1;
      else { i += 1; j += 1; }
    }
    if (i < la || j < lb) diff += 1;
    return diff <= 1;
  }

  function wordMatches(qw, words) {
    if (words.has(qw)) return true;
    for (const w of words) {
      if (qw.length >= 3 && w.startsWith(qw)) return true;
      if (qw.length >= 4 && Math.abs(w.length - qw.length) <= 1 && within1(w, qw)) return true;
    }
    return false;
  }

  // Variantes de requete : chaque variante = liste de mots (ET entre les mots, OU entre les variantes).
  function variantsFor(q) {
    const base = tokenize(q);
    const variants = base.length ? [base] : [];
    const seen = new Set([base.join(" ")]);
    const addVariant = (term, skip) => {
      if (term === skip) return;
      const ws = tokenize(term);
      const key = ws.join(" ");
      if (ws.length && !seen.has(key)) { seen.add(key); variants.push(ws); }
    };
    const whole = synonymLookup.get(q.trim());
    if (whole) whole.forEach((term) => addVariant(term, q.trim()));
    base.forEach((tok) => {
      const grp = synonymLookup.get(tok);
      if (grp) grp.forEach((term) => addVariant(term, tok));
    });
    return variants;
  }

  // Set d'ids correspondant a la requete (null si requete vide = pas de filtre recherche).
  function idsFor(normalizedQuery) {
    const q = (normalizedQuery || "").trim();
    if (!q || !docs.length) return null;
    if (q === cacheQuery) return cacheIds;
    const variants = variantsFor(q);
    const matches = (wordsSet) => {
      for (const v of variants) {
        if (v.every((qw) => wordMatches(qw, wordsSet))) return true;
      }
      return false;
    };
    // Priorite au nom : si la requete matche des NOMS de solutions, on ne renvoie que ceux-la.
    // Ainsi "thales" remonte la fiche Thales, pas toutes les fiches qui citent Thales en client.
    // Sans aucun match de nom, on elargit au contenu (mots-cles, NIST, description detaillee).
    const nameIds = new Set();
    docs.forEach((d) => { if (matches(d.nameWords)) nameIds.add(d.id); });
    let ids;
    if (nameIds.size) {
      ids = nameIds;
    } else {
      ids = new Set();
      docs.forEach((d) => { if (matches(d.words)) ids.add(d.id); });
    }
    cacheQuery = q;
    cacheIds = ids;
    return ids;
  }

  namespace.searchIndex = { build, idsFor };
})(window.CP);
