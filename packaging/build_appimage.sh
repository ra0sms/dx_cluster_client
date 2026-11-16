#!/usr/bin/env bash
# Build the Linux AppImage on any glibc-based Linux with Python 3.10+ (CI: ubuntu-22.04).
# PYTHON=/path/to/python selects the interpreter; SKIP_PIP=1 skips installing dependencies.
# Output: dist/release/DXClusterClient-<ver>-x86_64.AppImage
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
VERSION=$($PY -c "import dxclient; print(dxclient.__version__)")
APPDIR=build/AppDir

if [ -z "${SKIP_PIP:-}" ]; then
  $PY -m pip install --quiet --upgrade pip
  $PY -m pip install --quiet "PySide6>=6.6" pyinstaller pytest
fi
QT_QPA_PLATFORM=offscreen $PY -m pytest -q -p no:cacheprovider tests
QT_QPA_PLATFORM=offscreen $PY packaging/make_icons.py
$PY -m PyInstaller --noconfirm --clean dxclusterclient.spec

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a dist/DXClusterClient/. "$APPDIR/usr/bin/"
cp packaging/dxclusterclient.desktop "$APPDIR/" 
cp packaging/dxclusterclient.desktop "$APPDIR/usr/share/applications/"
cp packaging/icon.png "$APPDIR/dxclusterclient.png"
cp packaging/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/dxclusterclient.png"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/DXClusterClient" "$@"
RUN
chmod +x "$APPDIR/AppRun"

TOOL=build/appimagetool-x86_64.AppImage
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
mkdir -p dist/release
OUT="dist/release/DXClusterClient-${VERSION}-x86_64.AppImage"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
echo "Built $OUT"
