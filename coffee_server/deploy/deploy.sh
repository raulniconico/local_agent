#!/usr/bin/env bash
# Creates (or reuses) an EC2 instance, ships coffee_server's code and .env to
# it, and (re)builds/(re)starts the Docker container there. Safe to re-run:
# it reuses the existing instance/security group by their Name tag instead of
# creating duplicates, and replaces the running container each time -- so
# this doubles as the redeploy command after a code change.
#
# Prerequisites: `aws` CLI installed and configured (`aws configure`), plus
# `ssh`, `scp`, `rsync`, and `curl` locally. See ../README.md's "Deploying
# with deploy.sh" section for the one-time AWS setup (key pair, etc.).
set -euo pipefail
cd "$(dirname "$0")"

# --- 0. Config ---------------------------------------------------------------
[ -f .env ] || {
  echo "deploy/.env not found. Copy deploy/.env.example to deploy/.env and fill it in first." >&2
  exit 1
}
# shellcheck disable=SC1091
source .env

: "${KEY_NAME:?Set KEY_NAME in deploy/.env}"
: "${KEY_FILE:?Set KEY_FILE in deploy/.env}"
KEY_FILE="${KEY_FILE/#\~/$HOME}" # expand a literal leading ~, since `source` doesn't
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
INSTANCE_NAME="${INSTANCE_NAME:-coffee-server}"
APP_PORT="${APP_PORT:-8000}"
# The public hostname Caddy terminates TLS on. Empty disables the TLS step and
# falls back to the old plain-HTTP-on-APP_PORT behaviour.
API_HOST="${API_HOST:-}"
SITE_HOST="${SITE_HOST:-}"
SG_NAME="${INSTANCE_NAME}-sg"

[ -f "$KEY_FILE" ] || { echo "KEY_FILE '$KEY_FILE' does not exist." >&2; exit 1; }
[ -f ../.env ] || {
  echo "coffee_server/.env not found. Copy .env.example to .env and fill in" >&2
  echo "SERVER_API_KEY plus at least one provider's API key before deploying." >&2
  exit 1
}

NEED_INSTALL=0
for cmd in aws ssh scp rsync curl; do
  command -v "$cmd" >/dev/null 2>&1 || NEED_INSTALL=1
done
if [ "$NEED_INSTALL" -eq 1 ]; then
  echo "Some local prerequisites are missing; installing them now (needs sudo)..."
  ./install-deps.sh
fi
for cmd in aws ssh scp rsync curl; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required command: $cmd (install-deps.sh couldn't install it -- see its output above)" >&2; exit 1; }
done

if [ -z "${AWS_REGION:-}" ]; then
  AWS_REGION="$(aws configure get region || true)"
  [ -n "$AWS_REGION" ] || { echo "AWS_REGION is not set in deploy/.env and no default region is configured." >&2; exit 1; }
fi
export AWS_DEFAULT_REGION="$AWS_REGION"

SSH_OPTS=(-i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5)

echo "== Region: $AWS_REGION | Instance: $INSTANCE_NAME ($INSTANCE_TYPE) =="

# --- 1. Default VPC -----------------------------------------------------------
VPC_ID="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)"
if [ -z "$VPC_ID" ] || [ "$VPC_ID" = "None" ]; then
  echo "No default VPC in $AWS_REGION. Create one first:" >&2
  echo "  aws ec2 create-default-vpc --region $AWS_REGION" >&2
  exit 1
fi

# --- 2. Security group (idempotent: reuse by Name tag/group-name) -----------
SG_ID="$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  echo "Creating security group $SG_NAME..."
  SG_ID="$(aws ec2 create-security-group --group-name "$SG_NAME" \
    --description "coffee_server: SSH from deploy host, app port public" \
    --vpc-id "$VPC_ID" --query 'GroupId' --output text)"
  aws ec2 create-tags --resources "$SG_ID" --tags "Key=Name,Value=$SG_NAME"
else
  echo "Reusing security group $SG_ID"
fi

MY_IP="$(curl -s https://checkip.amazonaws.com)"
# Ignore "already exists" (idempotent re-run) -- these rules are the entire
# access policy: SSH locked to whoever is running this script right now, and
# either 80+443 (TLS mode, Caddy fronts the app) or APP_PORT open to the world
# (no-TLS fallback; the app itself enforces X-API-Key).
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
  --protocol tcp --port 22 --cidr "${MY_IP}/32" >/dev/null 2>&1 || true
if [ -n "$API_HOST" ]; then
  # TLS mode: Caddy fronts the app. 80 is required for the ACME HTTP-01
  # challenge, not just for the redirect -- cert issuance fails without it.
  # APP_PORT is deliberately NOT opened: the container binds 127.0.0.1 only.
  for port in 80 443; do
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
      --protocol tcp --port "$port" --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
  done
  aws ec2 revoke-security-group-ingress --group-id "$SG_ID" \
    --protocol tcp --port "$APP_PORT" --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
else
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --protocol tcp --port "$APP_PORT" --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
fi

# --- 3. Instance (idempotent: reuse by Name tag if pending/running) ---------
INSTANCE_ID="$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=pending,running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || true)"

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = "None" ]; then
  echo "Launching a new instance..."
  AMI_ID="$(aws ssm get-parameters \
    --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query 'Parameters[0].Value' --output text)"
  INSTANCE_ID="$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --user-data file://user-data.sh \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query 'Instances[0].InstanceId' --output text)"
else
  echo "Reusing instance $INSTANCE_ID"
fi

echo "Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
PUBLIC_IP="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
echo "Instance $INSTANCE_ID is running at $PUBLIC_IP"

# --- 4. Wait for SSH + Docker (user-data runs async after boot) ------------
echo "Waiting for SSH and Docker to be ready (can take a few minutes on first boot)..."
for i in $(seq 1 40); do
  if ssh "${SSH_OPTS[@]}" "ec2-user@$PUBLIC_IP" 'command -v docker' >/dev/null 2>&1; then
    echo "Docker is ready."
    break
  fi
  [ "$i" -eq 40 ] && { echo "Timed out waiting for Docker on the instance." >&2; exit 1; }
  sleep 15
done

# --- 5. Ship code + secrets --------------------------------------------------
echo "Syncing code..."
rsync -az -e "ssh ${SSH_OPTS[*]}" \
  --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
  --exclude='.env' --exclude='*.pem' --exclude='*.ppk' \
  ../ "ec2-user@$PUBLIC_IP:/home/ec2-user/coffee_server/"
scp "${SSH_OPTS[@]}" ../.env "ec2-user@$PUBLIC_IP:/home/ec2-user/coffee_server/.env"

# --- 6. Build and (re)start the container -----------------------------------
echo "Building image and (re)starting the container..."
ssh "${SSH_OPTS[@]}" "ec2-user@$PUBLIC_IP" "APP_PORT=$APP_PORT API_HOST='$API_HOST' bash -s" <<'REMOTE'
set -euo pipefail
cd ~/coffee_server
# accounts.db lives on a bind mount, NOT inside the container: every deploy
# does `docker rm -f`, so an in-image database would take the per-user
# metering records with it each time.
mkdir -p data
docker build -t coffee-server .
docker rm -f coffee-server-app >/dev/null 2>&1 || true
if [ -n "$API_HOST" ]; then
  # Caddy reaches the app over the loopback, so the port is not published to
  # the host's public interface at all -- defence in depth behind the SG rule.
  BIND="127.0.0.1:${APP_PORT}:8000"
else
  BIND="${APP_PORT}:8000"
fi
docker run -d --name coffee-server-app --restart unless-stopped \
  -p "$BIND" \
  -v /home/ec2-user/coffee_server/data:/data \
  -e ACCOUNT_DB_PATH=/data/accounts.db \
  -e SYNC_DIR=/data/sync_blobs \
  --env-file .env coffee-server
REMOTE

# --- 6b. TLS front end (Caddy) ------------------------------------------------
if [ -n "$API_HOST" ]; then
  echo "Installing/configuring Caddy for $API_HOST..."
  ssh "${SSH_OPTS[@]}" "ec2-user@$PUBLIC_IP" "APP_PORT=$APP_PORT API_HOST='$API_HOST' SITE_HOST='$SITE_HOST' bash -s" <<'REMOTE'
set -euo pipefail

if ! command -v caddy >/dev/null 2>&1; then
  JSON=$(curl -sSL https://api.github.com/repos/caddyserver/caddy/releases/latest)
  VER=$(printf '%s' "$JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["tag_name"].lstrip("v"))')
  curl -sSL -o /tmp/caddy.tgz "https://github.com/caddyserver/caddy/releases/download/v${VER}/caddy_${VER}_linux_amd64.tar.gz"
  tar -xzf /tmp/caddy.tgz -C /tmp caddy
  sudo install -m 0755 /tmp/caddy /usr/bin/caddy
  sudo groupadd --system caddy 2>/dev/null || true
  sudo useradd --system --gid caddy --home-dir /var/lib/caddy --create-home \
    --shell /usr/sbin/nologin caddy 2>/dev/null || true
fi

sudo mkdir -p /etc/caddy /srv/site

# No global `email` on purpose: it would be sent to Let's Encrypt as the ACME
# account contact and nobody has chosen one. Certs still issue and renew; the
# only loss is expiry-warning mail.
{
  printf '%s {\n\treverse_proxy localhost:%s\n\tlog {\n\t\toutput file /var/log/caddy/api.log\n\t}\n}\n' "$API_HOST" "$APP_PORT"
  if [ -n "$SITE_HOST" ]; then
    printf '\n%s, www.%s {\n\troot * /srv/site\n\tfile_server\n\tlog {\n\t\toutput file /var/log/caddy/site.log\n\t}\n}\n' "$SITE_HOST" "$SITE_HOST"
  fi
} | sudo tee /etc/caddy/Caddyfile >/dev/null

# LogsDirectory= rather than a hand-rolled mkdir+chown: on Amazon Linux the
# manually created directory has the wrong SELinux context and Caddy dies with
# "permission denied" opening its own log despite owning the directory.
sudo tee /etc/systemd/system/caddy.service >/dev/null <<'UNIT'
[Unit]
Description=Caddy web server
After=network.target

[Service]
User=caddy
Group=caddy
ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile --force
TimeoutStopSec=5s
LimitNOFILE=1048576
AmbientCapabilities=CAP_NET_BIND_SERVICE
LogsDirectory=caddy
LogsDirectoryMode=0750
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
UNIT

sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable caddy >/dev/null 2>&1 || true
sudo systemctl restart caddy
REMOTE
fi

# --- 7. Health check ----------------------------------------------------------
echo "Waiting for the service to answer /healthz..."
if [ -n "$API_HOST" ]; then
  HEALTH_URL="https://$API_HOST/healthz"; BASE_URL="https://$API_HOST"
else
  HEALTH_URL="http://$PUBLIC_IP:$APP_PORT/healthz"; BASE_URL="http://$PUBLIC_IP:$APP_PORT"
fi
for i in $(seq 1 20); do
  if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    echo
    echo "Deployed. $BASE_URL"
    echo 'Try: curl -H "X-API-Key: <SERVER_API_KEY>" -H "Content-Type: application/json" \'
    echo "       -d '{\"provider\": \"qwen\", \"prompt\": \"hi\"}' $BASE_URL/v1/ask"
    exit 0
  fi
  [ "$i" -eq 20 ] && { echo "Container built and started, but /healthz never answered -- check logs:" >&2; \
    echo "  ssh -i $KEY_FILE ec2-user@$PUBLIC_IP docker logs coffee-server-app" >&2; exit 1; }
  sleep 3
done
