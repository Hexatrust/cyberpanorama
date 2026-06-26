# CyberPanorama

Panorama interactif des solutions de cybersecurite francaises et europeennes, classees selon le
NIST CSF 2.0. Projet mene avec [Hexatrust](https://www.hexatrust.com) et le [CESIN](https://www.cesin.fr).
Site statique (HTML, CSS, JavaScript), sans framework, deploye sur GitHub Pages.

Voir le panorama en ligne : https://cyberpanorama.fr

## Gerer les entreprises du panorama

[![Ajouter une entreprise](https://img.shields.io/badge/Ajouter_une_entreprise-Formulaire_GitHub-2ea44f?style=for-the-badge&logo=github)](../../issues/new?template=add_company.yml)
[![Modifier une entreprise](https://img.shields.io/badge/Modifier_une_entreprise-Formulaire_GitHub-1f6feb?style=for-the-badge&logo=github)](../../issues/new?template=edit_company.yml)

Aucune connaissance technique requise : on remplit un formulaire, le reste est automatise.

## Contexte et objectifs

- Cartographier les solutions de cybersecurite francaises et europeennes pour reduire la dependance
  aux acteurs extra-territoriaux.
- Faciliter le choix des entreprises et administrations en quete de solutions fiables et souveraines.
- Promouvoir la visibilite de l'ecosysteme local.

La classification suit le cadre de reference [NIST CSF 2.0](https://www.nist.gov/cyberframework),
structure en 6 fonctions.

| Fonction   | Description                                                            |
|------------|-----------------------------------------------------------------------|
| Gouverner  | Integrer la cybersecurite dans la gouvernance globale.                |
| Identifier | Comprendre et gerer les risques sur les systemes, actifs et donnees.  |
| Proteger   | Mettre en place des protections pour limiter l'impact des incidents.  |
| Detecter   | Identifier les evenements de securite.                                |
| Repondre   | Reagir efficacement aux incidents detectes.                           |
| Recuperer  | Restaurer les capacites et services apres un incident.                |

### Grille de taille (INSEE et Scale Up)

| Categorie       | Criteres                                                                       |
|-----------------|--------------------------------------------------------------------------------|
| Startup / TPME  | Moins de 15 salaries et CA inferieur a 2 M EUR.                                |
| PME             | 15 a 250 salaries ou CA de 2 a 50 M EUR.                                       |
| ETI / Scale Up  | Categorie INSEE ETI, ou levee de fonds superieure a environ 12 M EUR.          |
| Grand groupe    | 5000 salaries ou plus, CA superieur a 1,5 Md EUR, ou filiale d'un grand groupe.|

## Proposer un ajout ou une modification

1. Cliquer sur un des deux boutons ci-dessus pour ouvrir le formulaire.
2. Renseigner les champs (nom, fonction NIST, taille, description, site, URL du logo, etc.).
3. A la soumission, un workflow parse le formulaire, telecharge le logo, prepare les donnees et ouvre
   une Pull Request.
4. Un mainteneur verifie la PR (logo, classification, taille, description) puis la fusionne.
5. La fusion sur `main` regenere les donnees et redeploie le panorama.

Rien n'est publie sans la validation manuelle de la Pull Request.

## Structure

```
index.html                   page de l'app (racine du site)
css/  js/                    interface et rendu du panorama
assets/                      logos (assets/logos/) et branding (Hexatrust, CESIN)
data/
  solutions.generated.js     donnees consommees par l'app (generees)
  solutions.json             le fichier unique de donnee (276 acteurs publies)
  size_review.json           tailles re-verifiees (registre INSEE et web) et leur justification
  nist_labels_fr.json        referentiel NIST en francais
  search_synonyms.json       synonymes pour la recherche
scripts/build_app_data.py    regenere data/solutions.generated.js
.github/
  ISSUE_TEMPLATE/            formulaires d'ajout et de modification
  scripts/parse_submission.py parsing des soumissions
  workflows/                 deploiement Pages et traitement des soumissions
```

## Developpement local

```bash
python3 scripts/build_app_data.py
# puis ouvrir index.html, ou servir le dossier en HTTP
```

La recherche utilise Typesense quand il est joignable, avec un repli local tolerant (tokens et synonymes)
embarque dans le site.

## Deploiement

Tout push sur `main` regenere les donnees et redeploie le site via GitHub Actions
(`.github/workflows/deploy-pages.yml`).
