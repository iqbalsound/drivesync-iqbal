#!/usr/bin/env bash
# Usage: ./build_deb.sh   ->  produces drivesync-iqbal_1.0.0_all.deb
set -euo pipefail
cd "$(dirname "$0")"
PKG=drivesync-iqbal; VER=1.0.0; ROOT=build/${PKG}_${VER}_all
rm -rf build
mkdir -p $ROOT/DEBIAN $ROOT/usr/bin $ROOT/usr/lib/$PKG $ROOT/usr/share/applications \
         $ROOT/usr/share/icons/hicolor/scalable/apps
cp packaging/control $ROOT/DEBIAN/control
cp src/drivesync.py $ROOT/usr/lib/$PKG/drivesync.py
cp assets/$PKG.svg $ROOT/usr/share/icons/hicolor/scalable/apps/$PKG.svg
cp packaging/$PKG.desktop $ROOT/usr/share/applications/
printf '#!/bin/sh\nexec python3 /usr/lib/%s/drivesync.py "$@"\n' $PKG > $ROOT/usr/bin/$PKG
cat > $ROOT/DEBIAN/postinst <<'EOS'
#!/bin/sh
set -e
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
command -v update-desktop-database >/dev/null && update-desktop-database -q || true
EOS
chmod 755 $ROOT/usr/bin/$PKG $ROOT/DEBIAN/postinst
find $ROOT -type d -exec chmod 755 {} +
dpkg-deb --build --root-owner-group $ROOT ${PKG}_${VER}_all.deb
echo "Built ${PKG}_${VER}_all.deb"
