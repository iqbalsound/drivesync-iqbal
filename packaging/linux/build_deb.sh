#!/usr/bin/env bash
# Builds dist/drivesync-iqbal_<version>_all.deb   (run on any Debian/Ubuntu-like system)
set -euo pipefail
cd "$(dirname "$0")/../.."
PKG=drivesync-iqbal
VER=$(python3 tools/version.py)
ROOT=build/deb/${PKG}_${VER}_all
rm -rf build/deb && mkdir -p dist
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/lib/$PKG" "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/icons/hicolor/256x256/apps" \
         "$ROOT/usr/share/doc/$PKG"
sed "s/@VERSION@/$VER/" packaging/linux/control.in > "$ROOT/DEBIAN/control"
cp -r drivesync_iqbal "$ROOT/usr/lib/$PKG/"
find "$ROOT" -name __pycache__ -type d -prune -exec rm -rf {} +
rm -f "$ROOT/usr/lib/$PKG/drivesync_iqbal/assets/"*.ico
install -m 755 packaging/linux/launcher.sh "$ROOT/usr/bin/$PKG"
install -m 644 packaging/linux/$PKG.desktop "$ROOT/usr/share/applications/$PKG.desktop"
install -m 644 drivesync_iqbal/assets/$PKG.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/$PKG.svg"
install -m 644 drivesync_iqbal/assets/$PKG.png "$ROOT/usr/share/icons/hicolor/256x256/apps/$PKG.png"
install -m 644 LICENSE "$ROOT/usr/share/doc/$PKG/copyright"
for s in postinst postrm; do
  printf '#!/bin/sh\nset -e\ncommand -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true\nexit 0\n' > "$ROOT/DEBIAN/$s"
  chmod 755 "$ROOT/DEBIAN/$s"
done
find "$ROOT" -type d -exec chmod 755 {} +
dpkg-deb --build --root-owner-group "$ROOT" "dist/${PKG}_${VER}_all.deb"
echo "Built dist/${PKG}_${VER}_all.deb"
