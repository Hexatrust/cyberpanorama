# Données du panorama

L'**Excel `solutions_master.xlsx` est la source de vérité**. Les scripts la transforment en deux sorties :
le fichier que le site charge (`solutions.generated.js`) et le `solutions.json`. Si l'Excel et le JSON
diffèrent, **c'est l'Excel qui gagne** (le build par défaut réinjecte l'Excel dans le JSON avant tout).

## Fichiers

- `solutions_master.xlsx` — **la source de vérité** : 276 acteurs publiés, tous les champs éditables (nom,
  taille, description, NIST, site, contact, mots-clés `Indexation`, logo). Garder la colonne `ID`.
- `solutions.json` — la même donnée en JSON, **régénérée depuis l'Excel** par le build. On peut l'éditer
  ponctuellement (puis `build.py --from-json`), mais l'Excel reste le maître.
- `size_review.json` — la taille d'entreprise (c'est elle que les builds appliquent) et sa justification
  (pour la feuille « Classement » de l'Excel).
- `nist_labels_fr.json`, `search_synonyms.json`, `classification_audit.json` — libellés NIST, synonymes de
  recherche, justifications du classement (Excel).
- Générés (ne pas éditer) : `solutions.generated.js`, `solutions_master.xlsx`, `master_qa_report.json`.

## Régénérer

Un seul script, `build.py` :

```bash
python3 scripts/build.py             # défaut : j'ai édité l'Excel -> réinjecte dans le JSON, puis régénère
python3 scripts/build.py --from-json # cas rare : j'ai édité directement le JSON -> régénère sans lire l'Excel
```

Le défaut enchaîne `xlsx_to_json.py` (Excel -> JSON), `build_app_data.py` (-> site) et
`build_master_xlsx.py` (-> Excel). On peut les lancer séparément si besoin.

Côté Excel : garder la colonne `ID` (elle sert à réapparier les lignes). Tout ce qui est affiché sur le
site fait l'aller-retour Excel <-> `solutions.json` (vérifié, sans perte).

## Acteurs retirés

`DROP_IDS` et `EXCLUDE_IDS`, dans les deux scripts de build, listent les acteurs qu'on ne montre pas
(doublons éditeur/produit, hors périmètre cyber, sociétés disparues). Comme ils ne sont ni sur le site
ni dans l'Excel, on les réintègre en retirant leur id de ces ensembles.

## Reste du pipeline

- Recherche : `scripts/typesense/` (réindexation, voir son README).
- Formulaires de contribution : `scripts/SUBMISSIONS.md`.
- Déploiement : `.github/workflows/` (le site est rebâti et publié à chaque push).
