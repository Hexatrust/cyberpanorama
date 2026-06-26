# Formulaires de contribution

Ajouter ou corriger un acteur sans toucher au code : on remplit un formulaire GitHub, ça finit en
Pull Request qu'un mainteneur valide.

## Les formulaires

- Ajouter   : `https://github.com/<owner>/<repo>/issues/new?template=add_company.yml`
- Modifier  : `https://github.com/<owner>/<repo>/issues/new?template=edit_company.yml`

Aussi accessibles depuis les boutons du README. Définis dans `.github/ISSUE_TEMPLATE/`.

Le logo : on peut glisser/coller une image (PNG, GIF, JPG, SVG) directement dans le formulaire (GitHub
l'héberge), ou coller une URL.

> Dépôt privé : ces URLs renvoient 404 pour qui n'a pas accès au dépôt. Passer en public pour des
> contributions ouvertes.

## Ce qui se passe ensuite

1. Le formulaire crée une issue avec le label `panorama:new-entry` ou `panorama:edit`.
2. Ce label déclenche `.github/workflows/process-submission.yml`.
3. Le workflow lance `.github/scripts/parse_submission.py` : il lit le formulaire, télécharge le logo,
   écrit la donnée dans `data/solutions.json` (ajout = nouvelle entrée ; modif = entrée existante), puis
   régénère le site.
4. Une Pull Request est ouverte. Rien n'est publié tant qu'un mainteneur ne l'a pas fusionnée ; la fusion
   déclenche le déploiement.

À savoir : le réglage GitHub « Allow GitHub Actions to create and approve pull requests » doit être activé
(Settings -> Actions -> General), sinon la création de la PR échoue.
