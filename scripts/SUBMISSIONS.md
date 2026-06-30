# Formulaires de contribution

Ajouter ou corriger un acteur sans toucher au code : on remplit un formulaire GitHub. Un mainteneur
relit, et quand c'est bon il pose le label `approved` : la donnée est alors appliquée et publiée
automatiquement.

## Les formulaires

- Ajouter   : `https://github.com/<owner>/<repo>/issues/new?template=add_company.yml`
- Modifier  : `https://github.com/<owner>/<repo>/issues/new?template=edit_company.yml`

Aussi accessibles depuis les boutons du README. Définis dans `.github/ISSUE_TEMPLATE/`.

Le logo : un seul champ qui accepte une image glissée/collée (PNG, GIF, JPG, SVG, WebP, hébergée par
GitHub) OU une URL publique directe. NIST (ajout) : la fonction (N1), les catégories (N2, menu multi-choix)
et les sous-catégories (N3, texte libre type `PR.DS-01, DE.CM-02`) sont **obligatoires** (elles s'affichent
sur la fiche). En modification, ces champs restent optionnels (on ne renseigne que ce qui change).

> Dépôt privé : ces URLs renvoient 404 pour qui n'a pas accès au dépôt. Passer en public pour des
> contributions ouvertes.

## Ce qui se passe ensuite

1. Le formulaire crée une issue avec le label `panorama:new-entry` ou `panorama:edit`. À l'ouverture,
   **rien ne se passe** automatiquement.
2. Un mainteneur relit l'issue. Si c'est bon, il pose le label **`approved`**.
3. Ce label déclenche `.github/workflows/process-submission.yml`, qui lance
   `.github/scripts/parse_submission.py` : il lit le formulaire, télécharge le logo, écrit la donnée dans
   `data/solutions.json` (ajout ou modification), puis régénère le site **et l'Excel**.
4. Le workflow commit sur `main`, déclenche le déploiement + la réindexation Typesense, puis ferme l'issue.

Garde-fou : seuls les membres avec droit d'écriture peuvent poser un label, donc seul un mainteneur peut
approuver. Le label `approved` doit exister dans le dépôt (créé une fois via Settings -> Labels ou
`gh label create approved`).
