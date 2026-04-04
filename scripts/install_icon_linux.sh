#!/usr/bin/env bash
# install_icon_linux.sh
# Installs the OpenSAK icon into the correct XDG locations so it appears
# in Linux Mint (and other GNOME/Cinnamon/KDE desktops) taskbars and app menus.
#
# Run from the repo root:
#   bash scripts/install_icon_linux.sh
#
# No sudo required — installs to ~/.local

set -e

ICONS_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets/icons"
HICOLOR="$HOME/.local/share/icons/hicolor"
PIXMAPS="$HOME/.local/share/pixmaps"

if [ ! -d "$ICONS_SRC" ]; then
    echo "ERROR: icons not found at $ICONS_SRC"
    echo "Run from the repository root directory."
    exit 1
fi

echo "Installing OpenSAK icons..."

# Install into hicolor theme (standard XDG)
declare -A SIZE_MAP=(
    ["16x16"]="opensak_16.png"
    ["32x32"]="opensak_32.png"
    ["48x48"]="opensak_48.png"
    ["64x64"]="opensak_64.png"
    ["128x128"]="opensak_128.png"
    ["256x256"]="opensak.png"
    ["512x512"]="opensak_512.png"
)

for SIZE in "${!SIZE_MAP[@]}"; do
    SRC_FILE="$ICONS_SRC/${SIZE_MAP[$SIZE]}"
    DEST_DIR="$HICOLOR/$SIZE/apps"
    if [ -f "$SRC_FILE" ]; then
        mkdir -p "$DEST_DIR"
        cp "$SRC_FILE" "$DEST_DIR/opensak.png"
        echo "  ✓ $DEST_DIR/opensak.png"
    fi
done

# Also install to pixmaps for apps that look there
mkdir -p "$PIXMAPS"
cp "$ICONS_SRC/opensak.png" "$PIXMAPS/opensak.png"
echo "  ✓ $PIXMAPS/opensak.png"

# Update icon cache
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HICOLOR" 2>/dev/null && echo "  ✓ Icon cache updated"
fi
if command -v xdg-icon-resource &>/dev/null; then
    xdg-icon-resource forceupdate 2>/dev/null || true
fi

echo ""
echo "Done! The OpenSAK icon is now installed."
echo "If it doesn't show immediately, log out and back in, or run:"
echo "  gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor/"
