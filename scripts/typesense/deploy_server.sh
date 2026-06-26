#!/usr/bin/env bash
#
# Deploiement Typesense, execute SUR le serveur (via SSH depuis GitHub Actions).
#
# SECURITE / NON-REGRESSION : ce script ne touche QUE le conteneur Typesense (${TS_CONTAINER}) et
# sa collection 'solutions'. Il ne touche PAS nginx-proxy ni les autres conteneurs, n'installe PAS
# Docker par defaut, ne fait AUCUN prune, et refuse de creer le conteneur si le port est deja pris
# par autre chose. Aucun autre site ne peut etre impacte.
#
# Variables d'environnement attendues :
#   TS_KEY        cle API admin Typesense (obligatoire)
#   IMPORT_FILE   chemin du JSONL d'import (obligatoire)
#   SCHEMA_FILE   chemin du schema JSON (obligatoire)
#   TS_PORT       port hote publie (defaut 40000)
#   TS_CONTAINER  nom du conteneur (defaut typesense)
#   TS_IMAGE      image (defaut typesense/typesense:27.1)
#   TS_VOLUME     volume de donnees (defaut typesense-data)
#   TS_URL        URL d'API (defaut http://localhost:${TS_PORT})
#   MANAGE_CONTAINER  1 = gerer le conteneur Docker (creer s'il manque) ; 0 = NE PAS toucher Docker,
#                     juste reindexer via l'API (DEFAUT 0, le plus sur : aucun risque pour les autres sites).
#                     Mettre a 1 seulement sur un hote dedie / serveur vierge.
#   INSTALL_DOCKER  mettre a 1 pour installer Docker s'il est ABSENT (off par defaut ; pour serveur vierge)
#
set -euo pipefail

TS_PORT="${TS_PORT:-40000}"
TS_CONTAINER="${TS_CONTAINER:-typesense}"
TS_IMAGE="${TS_IMAGE:-typesense/typesense:27.1}"
TS_VOLUME="${TS_VOLUME:-typesense-data}"
TS_URL="${TS_URL:-http://localhost:${TS_PORT}}"

: "${TS_KEY:?TS_KEY manquant}"
: "${IMPORT_FILE:?IMPORT_FILE manquant}"
: "${SCHEMA_FILE:?SCHEMA_FILE manquant}"

MANAGE_CONTAINER="${MANAGE_CONTAINER:-0}"

# Docker : on ne l'installe QUE si on gere le conteneur, et seulement si demande ET absent (serveur vierge).
if [ "${MANAGE_CONTAINER}" = "1" ] && ! command -v docker >/dev/null 2>&1; then
  if [ "${INSTALL_DOCKER:-0}" = "1" ]; then
    echo "Docker absent : installation (INSTALL_DOCKER=1)."
    curl -fsSL https://get.docker.com | sh
  else
    echo "ERREUR : Docker absent. Installez-le, ou relancez avec INSTALL_DOCKER=1." >&2
    exit 1
  fi
fi

ensure_container() {
  if docker ps --format '{{.Names}}' | grep -qx "${TS_CONTAINER}"; then
    echo "Conteneur ${TS_CONTAINER} deja en cours d'execution."
    return
  fi
  if docker ps -a --format '{{.Names}}' | grep -qx "${TS_CONTAINER}"; then
    echo "Conteneur ${TS_CONTAINER} present mais arrete : demarrage."
    docker start "${TS_CONTAINER}" >/dev/null
    return
  fi
  # Garde-fou : ne JAMAIS ecraser un service tiers qui utiliserait deja ce port.
  if docker ps --format '{{.Ports}}' | grep -q ":${TS_PORT}->"; then
    echo "ERREUR : le port ${TS_PORT} est deja publie par un AUTRE conteneur. Abandon (rien casse)." >&2
    exit 1
  fi
  echo "Creation du conteneur ${TS_CONTAINER} (port ${TS_PORT} -> 8108)."
  docker run -d --name "${TS_CONTAINER}" --restart unless-stopped \
    -p "${TS_PORT}:8108" \
    -v "${TS_VOLUME}:/data" \
    "${TS_IMAGE}" \
    --data-dir /data --api-key="${TS_KEY}" --enable-cors >/dev/null
}

wait_health() {
  for _ in $(seq 1 30); do
    if curl -fsS "${TS_URL}/health" >/dev/null 2>&1; then
      echo "Typesense repond (healthy)."
      return
    fi
    sleep 1
  done
  echo "ERREUR : Typesense ne repond pas sur ${TS_URL}/health" >&2
  exit 1
}

ensure_collection() {
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' "${TS_URL}/collections/solutions" \
    -H "X-TYPESENSE-API-KEY: ${TS_KEY}")
  if [ "${code}" = "200" ]; then
    echo "Collection 'solutions' deja presente (schema conserve, pas de coupure)."
  else
    echo "Creation de la collection 'solutions' depuis le schema."
    curl -fsS -X POST "${TS_URL}/collections" \
      -H "X-TYPESENSE-API-KEY: ${TS_KEY}" -H 'Content-Type: application/json' \
      --data-binary @"${SCHEMA_FILE}" >/dev/null
  fi
}

import_docs() {
  echo "Import (upsert) des documents."
  local resp="/tmp/ts_import_resp.txt"
  curl -fsS -X POST "${TS_URL}/collections/solutions/documents/import?action=upsert" \
    -H "X-TYPESENSE-API-KEY: ${TS_KEY}" -H 'Content-Type: text/plain' \
    --data-binary @"${IMPORT_FILE}" > "${resp}"
  local fails ok
  fails=$(grep -c '"success":false' "${resp}" || true)
  ok=$(grep -c '"success":true' "${resp}" || true)
  echo "Import : ${ok} documents OK, ${fails} echecs."
  if [ "${fails}" != "0" ]; then
    echo "Extrait des echecs :" >&2
    grep '"success":false' "${resp}" | head -3 >&2
    exit 1
  fi
}

if [ "${MANAGE_CONTAINER}" = "1" ]; then
  ensure_container
else
  echo "MANAGE_CONTAINER=0 : on ne touche PAS Docker, reindexation via l'API ${TS_URL} uniquement."
fi
wait_health
ensure_collection
import_docs
echo "OK : Typesense est a jour."
