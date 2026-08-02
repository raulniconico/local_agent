#!/usr/bin/env bash
# Installs deploy.sh's *local* prerequisites: the aws CLI, rsync, and
# ssh/scp (openssh client) -- curl is assumed already present, since this
# script itself needs it to fetch the AWS CLI installer. Supports apt/dnf/yum
# (Linux) and Homebrew (macOS); prints manual install instructions and exits
# non-zero on anything else rather than guessing.
#
# Run directly (`./install-deps.sh`) or let deploy.sh call it automatically
# when it finds something missing. Uses sudo for system package installs --
# expect a password prompt.
set -euo pipefail

detect_manager() {
  if command -v apt-get >/dev/null 2>&1; then echo apt
  elif command -v dnf >/dev/null 2>&1; then echo dnf
  elif command -v yum >/dev/null 2>&1; then echo yum
  elif command -v brew >/dev/null 2>&1; then echo brew
  else echo none
  fi
}
MANAGER="$(detect_manager)"

pkg_install() {
  case "$MANAGER" in
    apt)  sudo apt-get update -y && sudo apt-get install -y "$@" ;;
    dnf)  sudo dnf install -y "$@" ;;
    yum)  sudo yum install -y "$@" ;;
    brew) brew install "$@" ;;
    *)    echo "No supported package manager found (apt-get/dnf/yum/brew)." >&2
          echo "Install manually: $*" >&2
          return 1 ;;
  esac
}

# Package name for ssh/scp differs by distro; macOS ships them built in.
ssh_pkg_name() {
  case "$MANAGER" in
    apt) echo openssh-client ;;
    dnf|yum) echo openssh-clients ;;
    *) echo "" ;;
  esac
}

install_aws_cli() {
  command -v aws >/dev/null 2>&1 && return 0
  echo "Installing AWS CLI v2..."

  if [ "$MANAGER" = "brew" ]; then
    brew install awscli
    return
  fi

  local arch url tmpdir
  arch="$(uname -m)"
  case "$arch" in
    x86_64) url="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" ;;
    aarch64|arm64) url="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" ;;
    *)
      echo "Unsupported architecture '$arch' for the AWS CLI auto-installer." >&2
      echo "Install manually: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" >&2
      return 1
      ;;
  esac

  command -v unzip >/dev/null 2>&1 || pkg_install unzip
  tmpdir="$(mktemp -d)"
  curl -sSL "$url" -o "$tmpdir/awscliv2.zip"
  unzip -q "$tmpdir/awscliv2.zip" -d "$tmpdir"
  sudo "$tmpdir/aws/install"
  rm -rf "$tmpdir"
}

install_aws_cli

MISSING_PKGS=()
command -v rsync >/dev/null 2>&1 || MISSING_PKGS+=(rsync)
if ! command -v ssh >/dev/null 2>&1; then
  pkg="$(ssh_pkg_name)"
  [ -n "$pkg" ] && MISSING_PKGS+=("$pkg")
fi

if [ "${#MISSING_PKGS[@]}" -gt 0 ]; then
  echo "Installing: ${MISSING_PKGS[*]}"
  pkg_install "${MISSING_PKGS[@]}"
fi

for cmd in aws ssh scp rsync curl; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Still missing after install: $cmd -- install it manually." >&2; exit 1; }
done

echo "All deploy.sh prerequisites are installed."
