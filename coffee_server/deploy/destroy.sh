#!/usr/bin/env bash
# Terminates the instance deploy.sh created and deletes its security group.
# Not requested as part of the deploy flow, but paired with it deliberately:
# a create-only script makes it easy to forget a running (billing) instance.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "deploy/.env not found." >&2; exit 1; }
# shellcheck disable=SC1091
source .env

INSTANCE_NAME="${INSTANCE_NAME:-coffee-server}"
SG_NAME="${INSTANCE_NAME}-sg"

if [ -z "${AWS_REGION:-}" ]; then
  AWS_REGION="$(aws configure get region || true)"
fi
export AWS_DEFAULT_REGION="$AWS_REGION"

INSTANCE_ID="$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || true)"

if [ -n "$INSTANCE_ID" ] && [ "$INSTANCE_ID" != "None" ]; then
  read -r -p "Terminate instance $INSTANCE_ID ($INSTANCE_NAME)? [y/N] " confirm
  if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null
    echo "Waiting for termination..."
    aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
    echo "Terminated."
  else
    echo "Skipped instance termination."
    exit 0
  fi
else
  echo "No pending/running/stopped instance tagged Name=$INSTANCE_NAME found."
fi

SG_ID="$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [ -n "$SG_ID" ] && [ "$SG_ID" != "None" ]; then
  aws ec2 delete-security-group --group-id "$SG_ID" && echo "Deleted security group $SG_ID."
fi
