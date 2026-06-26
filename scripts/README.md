# Données du panorama

La donnée vit dans des JSON, deux scripts la transforment en deux sorties : le fichier que le site charge
(`solutions.generated.js`) et l'Excel (`solutions_master.xlsx`). On peut éditer soit le JSON, soit l'Excel.

## Fichiers

- `solutions.json` — **le fichier unique de donnée** : exactement les 276 acteurs publiés (1 par entrée,
  clé `id`), avec tous les champs éditables (nom, description, site, contact, NIST, taille, mots-clés
  `indexation`, **et le logo** : nom de fichier, qui doit exister dans `assets/logos/`).
- `size_review.json` — la taille d'entreprise (c'est elle que les builds appliquent) et sa justification
  (pour la feuille « Classement » de l'Excel).
- `nist_labels_fr.json`, `search_synonyms.json`, `classification_audit.json` — libellés NIST, synonymes de
  recherche, justifications du classement (Excel).
- Générés (ne pas éditer) : `solutions.generated.js`, `solutions_master.xlsx`, `master_qa_report.json`.

## Régénérer

Un seul script, `build.py` :

```bash
python3 scripts/build.py              # j'ai édité un JSON  -> regénère site + Excel
python3 scripts/build.py --from-excel # j'ai édité l'Excel  -> réinjecte dans les JSON, puis regénère
```

Il enchaîne `xlsx_to_json.py` (Excel -> JSON), `build_app_data.py` (-> site) et `build_master_xlsx.py`
(-> Excel). On peut les lancer séparément si besoin.

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
