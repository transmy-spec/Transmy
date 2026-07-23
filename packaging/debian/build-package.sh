#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
VERSION=${1:-0.24.0}
ARCHITECTURE=${2:-all}
OUTPUT_DIR=${3:-"$REPOSITORY_ROOT/dist"}
BUILD_ROOT=$(mktemp -d)
PACKAGE_ROOT=$BUILD_ROOT/transmy

dpkg --validate-version "$VERSION" ||
  { printf '%s\n' "Invalid Debian package version: $VERSION" >&2; exit 1; }

cleanup() { rm -rf "$BUILD_ROOT"; }
trap cleanup EXIT INT TERM

mkdir -p \
  "$PACKAGE_ROOT/DEBIAN" \
  "$PACKAGE_ROOT/usr/bin" \
  "$PACKAGE_ROOT/usr/lib/transmy" \
  "$PACKAGE_ROOT/usr/lib/systemd/system" \
  "$PACKAGE_ROOT/usr/share/doc/transmy"

cat >"$PACKAGE_ROOT/DEBIAN/control" <<EOF
Package: transmy
Version: $VERSION
Section: admin
Priority: optional
Architecture: $ARCHITECTURE
Maintainer: Transmy contributors
Depends: ca-certificates, curl, docker.io, docker-compose, openssl, python3
Homepage: https://github.com/transmy-spec/transmy
Description: Self-hosted coordination platform for social care teams
 Transmy deploys the Transmissions application with Docker Compose and provides
 setup, diagnostics, encrypted backups and controlled upgrades on Debian 13.
EOF

install -m 0755 "$SCRIPT_DIR/transmy" "$PACKAGE_ROOT/usr/bin/transmy"
install -m 0755 "$SCRIPT_DIR/configure-realm.py" \
  "$PACKAGE_ROOT/usr/lib/transmy/packaging/debian/configure-realm.py"
install -m 0755 "$SCRIPT_DIR/postinst" "$PACKAGE_ROOT/DEBIAN/postinst"
install -m 0755 "$SCRIPT_DIR/prerm" "$PACKAGE_ROOT/DEBIAN/prerm"
install -m 0755 "$SCRIPT_DIR/postrm" "$PACKAGE_ROOT/DEBIAN/postrm"
install -m 0644 "$SCRIPT_DIR/transmy.service" \
  "$PACKAGE_ROOT/usr/lib/systemd/system/transmy.service"
install -m 0644 "$SCRIPT_DIR/transmy-backup.service" \
  "$PACKAGE_ROOT/usr/lib/systemd/system/transmy-backup.service"
install -m 0644 "$SCRIPT_DIR/transmy-backup.timer" \
  "$PACKAGE_ROOT/usr/lib/systemd/system/transmy-backup.timer"

cp -a "$REPOSITORY_ROOT/backend" "$PACKAGE_ROOT/usr/lib/transmy/backend"
cp -a "$REPOSITORY_ROOT/frontend" "$PACKAGE_ROOT/usr/lib/transmy/frontend"
cp -a "$REPOSITORY_ROOT/infrastructure" "$PACKAGE_ROOT/usr/lib/transmy/infrastructure"
install -m 0644 "$REPOSITORY_ROOT/compose.yaml" "$PACKAGE_ROOT/usr/lib/transmy/compose.yaml"
install -m 0644 "$REPOSITORY_ROOT/compose.production.yaml" \
  "$PACKAGE_ROOT/usr/lib/transmy/compose.production.yaml"
install -m 0644 "$REPOSITORY_ROOT/LICENSE" "$PACKAGE_ROOT/usr/share/doc/transmy/copyright"
install -m 0644 "$REPOSITORY_ROOT/docs/10-exploitation-production.md" \
  "$PACKAGE_ROOT/usr/share/doc/transmy/operations.md"

find "$PACKAGE_ROOT" -type d \( \
  -name node_modules -o -name dist -o -name .pytest_cache -o -name .mypy_cache \
  -o -name .ruff_cache -o -name __pycache__ \
\) -prune -exec rm -rf {} +

mkdir -p "$OUTPUT_DIR"
dpkg-deb --root-owner-group --build "$PACKAGE_ROOT" \
  "$OUTPUT_DIR/transmy_${VERSION}_${ARCHITECTURE}.deb"
