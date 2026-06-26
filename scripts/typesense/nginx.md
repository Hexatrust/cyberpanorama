# Reverse proxy nginx devant Typesense

Ce document explique comment poser un reverse proxy nginx qui expose la recherche Typesense au
navigateur **sans jamais livrer de clé au client**. Il est générique (à adapter à n'importe quel
serveur) et ne décrit pas une installation particulière.

## Ce que le proxy fait

Le navigateur (le site statique, par exemple sur GitHub Pages) interroge la recherche en HTTPS. Le
proxy se place devant le conteneur Typesense et :

1. termine le TLS sur le port 443 (le port 80 ne sert qu'à rediriger vers 443) ;
2. n'autorise que deux chemins, la recherche et le `health`, et répond 403 pour tout le reste
   (création de documents, suppression, administration) ;
3. injecte l'en-tête `X-TYPESENSE-API-KEY` côté serveur, avec une clé **search only**, de sorte que
   le client n'a aucune clé ;
4. relaie la requête vers le conteneur (`proxy_pass`), en HTTP simple sur le réseau local.

C'est un relais transparent, pas une redirection HTTP : le navigateur croit parler à un seul serveur
et ne voit jamais l'adresse du backend.

```
Navigateur ──HTTPS 443──> nginx (TLS, filtrage, ajout de la clé) ──HTTP──> Typesense (127.0.0.1:40000)
```

## Prérequis

- Un nom de domaine pointant sur le serveur (exemple `search.exemple.fr`).
- Un certificat TLS (Let's Encrypt via certbot, voir plus bas).
- Le conteneur Typesense lancé et **écoutant seulement en local**, pour qu'il ne soit pas joignable
  directement depuis Internet. Publier le port sur la loopback uniquement :

  ```bash
  docker run -d --name typesense --restart unless-stopped \
    -p 127.0.0.1:40000:8108 \
    -v /chemin/vers/typesense-data:/data \
    typesense/typesense:<version> \
    --data-dir /data --api-key "<CLE_ADMIN>" --enable-cors
  ```

  Le port interne de Typesense est 8108 ; ici il est publié sur `127.0.0.1:40000`. Comme l'écoute est
  liée à la loopback, seul nginx (sur la même machine) peut l'atteindre.

## Deux clés différentes

Typesense distingue la clé d'administration et les clés à portée réduite. On ne met jamais la clé
admin devant le navigateur.

- La **clé admin** sert uniquement à l'administration et à la réindexation (en SSH, jamais exposée).
- On crée une **clé search only**, limitée à l'action `documents:search` sur la collection
  `solutions`. C'est elle que nginx injecte.

```bash
curl -s "http://127.0.0.1:40000/keys" \
  -H "X-TYPESENSE-API-KEY: <CLE_ADMIN>" \
  -H 'Content-Type: application/json' \
  -d '{"description":"recherche site","actions":["documents:search"],"collections":["solutions"]}'
```

La réponse contient la valeur de la clé (affichée une seule fois) : c'est elle qu'on place dans la
config nginx.

## La clé hors du dépôt

On ne met pas la clé dans le fichier de site versionné. On la pose dans un fichier à part, lisible
par le seul utilisateur de nginx, et on l'inclut :

```bash
# /etc/nginx/typesense_key.conf  (chmod 600, proprietaire root)
# Contenu :
#   set $ts_search_key "<CLE_SEARCH_ONLY>";
```

## La configuration nginx

```nginx
# Redirection 80 vers 443
server {
    listen 80;
    listen [::]:80;
    server_name search.exemple.fr;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name search.exemple.fr;

    # Certificat (voir certbot plus bas)
    ssl_certificate     /etc/letsencrypt/live/search.exemple.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/search.exemple.fr/privkey.pem;

    # La cle search only, definie dans un fichier separe non versionne
    include /etc/nginx/typesense_key.conf;

    # Le backend : le conteneur Typesense, joignable seulement en local
    set $ts_backend http://127.0.0.1:40000;

    # Origine autorisee a lire la reponse (le site statique). Mettre l'origine exacte.
    set $cors_origin "https://utilisateur.github.io";

    # On ne logge jamais l'en-tete de cle
    proxy_set_header X-TYPESENSE-API-KEY $ts_search_key;

    # Seul l'endpoint de recherche est autorise
    location = /collections/solutions/documents/search {
        add_header Access-Control-Allow-Origin $cors_origin always;
        proxy_pass $ts_backend;
        proxy_set_header Host $host;
    }

    # Sonde de sante (pratique pour un check externe)
    location = /health {
        add_header Access-Control-Allow-Origin $cors_origin always;
        proxy_pass $ts_backend;
    }

    # Tout le reste est refuse (admin, ecriture, autres collections)
    location / {
        return 403;
    }
}
```

Points à comprendre :

- `location = ...` est une correspondance **exacte** sur le chemin (la chaîne de requête `?q=...`
  n'entre pas dans la correspondance), donc seule cette route précise passe.
- `proxy_set_header X-TYPESENSE-API-KEY` ajoute la clé sur le trajet nginx vers backend : le client
  n'envoie rien. Comme le client n'envoie aucun en-tête personnalisé, sa requête reste une requête
  simple et il n'y a pas de pré-vol CORS à gérer ; un simple `Access-Control-Allow-Origin` en réponse
  suffit pour que le JavaScript puisse lire le résultat.
- Le `return 403` du `location /` est la barrière : sans route exacte correspondante, l'API
  d'administration et l'écriture sont injoignables depuis l'extérieur.

## Le certificat TLS

```bash
sudo certbot --nginx -d search.exemple.fr
```

certbot installe le certificat et configure le renouvellement automatique. Tester ensuite la config
et recharger :

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## Vérifier

```bash
# La recherche passe (200) avec la cle injectee, sans cle cote client
curl -s "https://search.exemple.fr/collections/solutions/documents/search?q=test&query_by=solution_name" | head

# Le health passe
curl -s "https://search.exemple.fr/health"

# Tout autre chemin est refuse (403)
curl -s -o /dev/null -w '%{http_code}\n' "https://search.exemple.fr/collections/solutions/documents"
curl -s -o /dev/null -w '%{http_code}\n' "https://search.exemple.fr/keys"
```

On doit obtenir un résultat de recherche, un `{"ok":true}` sur `health`, et `403` sur les deux
derniers.

## Durcissements optionnels

- Limiter le débit par IP avec `limit_req_zone` / `limit_req` pour amortir un abus de l'endpoint de
  recherche.
- Restreindre les méthodes : la recherche est en `GET`, on peut refuser le reste avec
  `limit_except GET { deny all; }` dans le `location` de recherche.
- Vérifier que les logs d'accès n'enregistrent pas la chaîne de requête si elle peut contenir des
  données sensibles (ici une simple recherche, donc peu critique).
</content>
</invoke>
