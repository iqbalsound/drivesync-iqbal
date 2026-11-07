#!/usr/bin/env bash
# Builds dist/drivesync-iqbal-<version>-1.noarch.rpm
# Needs rpmbuild:  sudo dnf install rpm-build    (or on Debian/Ubuntu: sudo apt install rpm)
set -euo pipefail
cd "$(dirname "$0")/../.."
PKG=drivesync-iqbal
VER=$(python3 tools/version.py)
TOP="$PWD/build/rpm"
rm -rf "$TOP" && mkdir -p "$TOP/SOURCES" "$TOP/SPECS" dist
tar --exclude=__pycache__ --transform "s,^,$PKG-$VER/," \
    -czf "$TOP/SOURCES/$PKG-$VER.tar.gz" drivesync_iqbal packaging LICENSE README.md
sed "s/@VERSION@/$VER/" packaging/linux/$PKG.spec.in > "$TOP/SPECS/$PKG.spec"
rpmbuild --define "_topdir $TOP" -bb "$TOP/SPECS/$PKG.spec"
cp "$TOP"/RPMS/noarch/*.rpm dist/
echo "RPM copied to dist/"
