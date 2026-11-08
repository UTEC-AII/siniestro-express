#!/usr/bin/env bash
# Despliegue guiado. Uso:
#   ./scripts/deploy.sh ml | core | agente | web
# Lee las variables de un archivo .env en la raíz (no versionado) y avisa
# cuál falta antes de llamar a serverless.

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICIO="${1:-}"

if [ -f "$RAIZ/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$RAIZ/.env"
  set +a
fi

faltan=0
requiere() {
  for nombre in "$@"; do
    if [ -z "${!nombre:-}" ]; then
      echo "  falta $nombre"
      faltan=1
    fi
  done
}

case "$SERVICIO" in
  ml)
    cd "$RAIZ/services/ml" || exit 1
    ;;
  core)
    echo "Revisando variables de core:"
    requiere ML_API_URL
    cd "$RAIZ/services/core" || exit 1
    ;;
  agente)
    echo "Revisando variables de agente:"
    requiere GROQ_API_KEY CORE_API_URL
    cd "$RAIZ/services/agente" || exit 1
    ;;
  web)
    echo "Revisando variables del frontend:"
    requiere VITE_AGENTE_API VITE_CORE_API
    cd "$RAIZ/frontend" || exit 1
    ;;
  *)
    echo "Uso: ./scripts/deploy.sh [ml|core|agente|web]"
    exit 1
    ;;
esac

if [ "$faltan" -ne 0 ]; then
  echo
  echo "Completa las variables en $RAIZ/.env y vuelve a intentar."
  echo "Puedes copiar .env.example como punto de partida."
  exit 1
fi

echo "Desplegando $SERVICIO desde $(pwd)"
npx serverless deploy
