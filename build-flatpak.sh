#!/bin/bash
# Build and install the Tokenificator Flatpak locally.
#
# Requirements:
#   flatpak, flatpak-builder, pip3
#   org.gnome.Platform//46 and org.gnome.Sdk//46 installed
#
# One-time setup:
#   flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
#   flatpak install --user flathub org.gnome.Platform//46 org.gnome.Sdk//46

set -euo pipefail

MANIFEST="io.github.mordachai.Tokenificator.yml"
BUILD_DIR=".flatpak-build"
REPO_DIR=".flatpak-repo"
APP_ID="io.github.mordachai.Tokenificator"

cd "$(dirname "$0")"

echo "=== Downloading pip wheels ==="
pip3 download --prefer-binary -d pip-wheels/ -r requirements-flatpak.txt

echo ""
echo "=== Building Flatpak ==="
flatpak-builder \
    --user \
    --force-clean \
    --repo="$REPO_DIR" \
    "$BUILD_DIR" \
    "$MANIFEST"

echo ""
echo "=== Installing locally ==="
flatpak --user remote-add --no-gpg-verify --if-not-exists local-tokenificator "$REPO_DIR"
flatpak --user install --reinstall -y local-tokenificator "$APP_ID"

echo ""
echo "=== Done! ==="
echo "Run:  flatpak run $APP_ID"
echo "Then open http://localhost:5000 in your browser."
