#!/usr/bin/env bash
# Sets up ApexLens on a fresh Ubuntu 22.04/24.04 VM (x86-64 or arm64, e.g. an Oracle Always Free A1 instance):
# Docker, firewall, .env, images, the data pipeline (hours), the services behind HTTPS, and a daily job that
# fetches race results and scores the prediction game.
#
#   git clone https://github.com/akashsaha477/F1 && cd F1
#   bash deploy/setup.sh [--domain host] [--admin-token t] [--anthropic-key k] [--seasons 2022-2026] [--skip-pipeline]
#
# Without --domain the site is served on <public-ip>.sslip.io, which needs no DNS setup and gets a real
# certificate. Re-running the script is safe: it keeps an existing .env and data.
set -euo pipefail
cd "$(dirname "$0")/.."

DOMAIN="" ADMIN_TOKEN="" ANTHROPIC_KEY="" SEASONS="2022-2026" RUN_PIPELINE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --admin-token) ADMIN_TOKEN="$2"; shift 2 ;;
    --anthropic-key) ANTHROPIC_KEY="$2"; shift 2 ;;
    --seasons) SEASONS="$2"; shift 2 ;;
    --skip-pipeline) RUN_PIPELINE=0; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

say() { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }

say "Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
dc() { if docker info >/dev/null 2>&1; then docker compose "$@"; else sudo docker compose "$@"; fi; }
dc version >/dev/null

say "Firewall: allow HTTP and HTTPS"
# Oracle's Ubuntu images ship iptables rules that reject everything except SSH; ufw may also be active.
if sudo iptables -C INPUT -j REJECT --reject-with icmp-host-prohibited >/dev/null 2>&1 \
   || sudo iptables -S INPUT | grep -q REJECT; then
  for port in 80 443; do
    sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT >/dev/null 2>&1 \
      || sudo iptables -I INPUT 5 -p tcp --dport "$port" -j ACCEPT
  done
  if command -v netfilter-persistent >/dev/null 2>&1; then sudo netfilter-persistent save; fi
fi
if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q "Status: active"; then
  sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
fi
echo "(the cloud provider's own network rules must also allow TCP 80 and 443 — see deploy/README.md)"

say "Configuration (.env)"
if [ ! -f .env ]; then
  if [ -z "$DOMAIN" ]; then
    IP="$(curl -fsS https://api.ipify.org || curl -fsS https://ifconfig.me)"
    DOMAIN="${IP}.sslip.io"
  fi
  [ -n "$ADMIN_TOKEN" ] || ADMIN_TOKEN="$(openssl rand -hex 16)"
  cat > .env <<EOF
APEXLENS_DOMAIN=${DOMAIN}
APEXLENS_DATA_DIR=/app/data
APEXLENS_REPORTS_DIR=/app/reports
APEXLENS_DEFAULT_SEASONS=$(echo "$SEASONS" | awk -F- '{for (y=$1; y<=$2; y++) printf "%s%d", (y>$1?",":""), y}')
SEASONS=${SEASONS}
# prediction game: only the holder of this token can trigger "fetch results & score" from the dashboard
APEXLENS_GAME_ADMIN_TOKEN=${ADMIN_TOKEN}
# AI entrant (Claude); empty = model only
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
APEXLENS_GAME_AI_ENABLED=true
APEXLENS_GAME_AI_MODEL=claude-opus-5-5
EOF
  echo "wrote .env (domain ${DOMAIN})"
else
  echo ".env exists, keeping it"
fi
DOMAIN="$(grep '^APEXLENS_DOMAIN=' .env | cut -d= -f2-)"
ADMIN_TOKEN="$(grep '^APEXLENS_GAME_ADMIN_TOKEN=' .env | cut -d= -f2-)"
mkdir -p data reports

say "Images"
dc --project-directory . -f deploy/docker-compose.prod.yml build

if [ "$RUN_PIPELINE" = 1 ] && [ ! -f data/models/production.json ]; then
  say "Data pipeline (ingest ${SEASONS}, features, training, evaluation, reports) — this takes hours; safe to re-run"
  dc --project-directory . -f deploy/docker-compose.prod.yml --profile pipeline run --rm pipeline
fi

say "Services"
dc --project-directory . -f deploy/docker-compose.prod.yml up -d
dc --project-directory . -f deploy/docker-compose.prod.yml ps

say "Daily job: fetch results of finished races and score the prediction game (03:30 UTC)"
JOB="cd $PWD && docker compose --project-directory . -f deploy/docker-compose.prod.yml exec -T api python scripts/game.py settle-due --fetch >> $PWD/deploy/settle.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'scripts/game.py settle-due' ; echo "30 3 * * * $JOB" ) | crontab -

say "Done"
echo "Dashboard:    https://${DOMAIN}   (the certificate is issued on the first visit; give it a minute)"
echo "API docs:     https://${DOMAIN}/api/docs"
echo "Admin token:  ${ADMIN_TOKEN}   (paste it in the prediction game's 'After the race' box; it is in .env)"
echo "Logs:         docker compose --project-directory . -f deploy/docker-compose.prod.yml logs -f"
