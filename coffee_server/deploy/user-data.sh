#!/bin/bash
# EC2 user-data: runs once, automatically, on first boot (via cloud-init) --
# not run by deploy.sh directly. Installs Docker and rsync (Amazon Linux 2023
# ships with neither) so the instance is ready by the time deploy.sh starts
# syncing code to it.
set -euo pipefail

dnf update -y
dnf install -y docker rsync
systemctl enable --now docker
usermod -aG docker ec2-user
