"use strict";

/**
 * Config d'execution injectee au deploiement. La valeur ci-dessous est volontairement VIDE (aucune URL
 * en dur dans le depot) : le workflow .github/workflows/deploy-pages.yml regenere ce fichier a partir de
 * la variable GitHub TYPESENSE_HOST. En local (host vide), la recherche retombe sur le repli client-side.
 */
window.CP_RUNTIME = { typesenseHost: "" };
