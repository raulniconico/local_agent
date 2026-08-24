#!/usr/bin/env bash
# Ships this directory to the Caddy docroot on the coffee-can.org instance.
#
# Separate from coffee_server/deploy/deploy.sh on purpose: that script owns the
# gateway (instance, container, TLS) and re-runs a Docker build every time. The
# site is static files on the same box and has no reason to wait for that.
set -euo pipefail
cd "$(dirname "$0")"

KEY="${KEY_FILE:-../coffee_server/coffee-server-key.pem}"
# The hostname, not the Elastic IP. Both resolve to the same box today, but a
# committed IP is a value that goes stale the moment the instance moves and
# that someone later trusts because it is checked in. DNS is the thing that is
# supposed to know where the server is.
HOST="${SITE_SSH_HOST:-ec2-user@coffee-can.org}"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)

[ -f "$KEY" ] || { echo "key not found: $KEY" >&2; exit 1; }

echo "Syncing site to $HOST:/srv/site ..."
# Into a staging dir the ec2-user owns, then moved: /srv/site is root-owned and
# rsync-over-ssh cannot sudo mid-transfer.
rsync -az --delete -e "ssh ${SSH_OPTS[*]}" \
  --exclude='deploy.sh' --exclude='.DS_Store' \
  ./ "$HOST:/home/ec2-user/site-staging/"

ssh "${SSH_OPTS[@]}" "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
sudo mkdir -p /srv/site
sudo rsync -a --delete /home/ec2-user/site-staging/ /srv/site/
sudo chown -R caddy:caddy /srv/site
REMOTE

echo "Deployed. https://coffee-can.org"
