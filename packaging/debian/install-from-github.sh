#!/bin/sh
set -eu

GIT_REPOSITORY=${TRANSMY_GIT_REPOSITORY:-https://github.com/transmy-spec/Transmy.git}
GIT_REF=${TRANSMY_GIT_REF:-newest}
PACKAGE_VERSION=${TRANSMY_VERSION:-0.27.0~rc1}
WORK_DIR=

say() { printf '%s\n' "transmy: $*"; }
die() { printf '%s\n' "transmy: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run this installer as root (sudo sh install-from-github.sh)"
[ -r /etc/os-release ] || die "cannot identify the operating system"

. /etc/os-release
[ "${ID:-}" = debian ] && [ "${VERSION_ID:-}" = 13 ] ||
  die "this installer supports Debian 13 only"

cleanup() {
  [ -z "$WORK_DIR" ] || rm -rf "$WORK_DIR"
}
trap cleanup EXIT INT TERM

say "Installing the required system tools..."
apt-get update
apt-get install --yes ca-certificates git python3

WORK_DIR=$(mktemp -d)
chmod 0755 "$WORK_DIR"
say "Downloading Transmy ($GIT_REF)..."
git clone --quiet --depth 1 --branch "$GIT_REF" "$GIT_REPOSITORY" "$WORK_DIR/transmy"

say "Building the Debian package locally..."
sh "$WORK_DIR/transmy/packaging/debian/build-package.sh" "$PACKAGE_VERSION"

say "Installing Transmy and its Docker dependencies..."
apt-get install --yes "$WORK_DIR/transmy/dist/transmy_${PACKAGE_VERSION}_all.deb"

if [ -f /etc/transmy/transmy.env ]; then
  say "Existing installation detected; starting the controlled upgrade..."
  transmy upgrade
else
  say "Starting the guided configuration..."
  transmy setup
fi
