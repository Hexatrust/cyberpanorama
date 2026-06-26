# Réindexation Typesense

La recherche du site passe par Typesense (avec un repli local si le serveur est injoignable). Quand la
donnée change, GitHub Actions réindexe tout seul ; on n'a rien à lancer à la main.

## Comment ça marche

Le workflow `.github/workflows/typesense-reindex.yml` se connecte au serveur en SSH, copie le JSONL
(`build_import.py`), le schéma et `deploy_server.sh`, puis lance `deploy_server.sh` là-bas : il recrée la
collection si besoin et réimporte les documents.

`deploy_server.sh` ne touche QUE le conteneur Typesense et sa collection : pas d'install Docker par
défaut, rien d'autre n'est modifié sur le serveur. Sur un serveur vierge, on l'appelle une fois avec
`MANAGE_CONTAINER=1 INSTALL_DOCKER=1` pour créer le conteneur ; ensuite les réindexations normales
(`MANAGE_CONTAINER=0`) ne font que mettre la donnée à jour.

## Sécurité

Le site n'embarque aucune clé : le reverse-proxy injecte une clé search-only côté serveur et n'expose que
l'endpoint de recherche. La clé admin reste un secret GitHub, utilisée seulement par le workflow.

Pour monter ce reverse-proxy (nginx : TLS sur 443, filtrage des chemins, injection de la clé), voir
[nginx.md](nginx.md) : un guide générique, indépendant d'un serveur particulier.

## Activer

Rien ne tourne tant que la variable `TYPESENSE_AUTODEPLOY` n'est pas `true`. À régler dans
Settings -> Secrets and variables -> Actions :

- Variables : `TYPESENSE_AUTODEPLOY=true`, `TS_URL` (l'API vue depuis l'hôte SSH, souvent
  `http://localhost:40000`), optionnel `TS_SSH_PORT`.
- Secrets : `TS_SSH_HOST`, `TS_SSH_USER`, `TS_SSH_KEY`, `TS_ADMIN_KEY`.

Le port SSH de l'hôte doit être joignable depuis Internet (le runner GitHub est dans le cloud), sinon
utiliser un runner self-hosted.

## À la main

```bash
python3 scripts/build_app_data.py
python3 scripts/typesense/build_import.py _ts/solutions.jsonl
TS_KEY=<admin> IMPORT_FILE=.../_ts/solutions.jsonl SCHEMA_FILE=.../scripts/typesense/schema.json \
  bash scripts/typesense/deploy_server.sh
```
