#!/usr/bin/env bash
# Build the Windows .exe on Linux with PyInstaller running under Wine (tobix/pywine image).
# Output: dist/release/DXClusterClient-<ver>-win64.exe
# On a real Windows machine simply run:  pip install pyside6 pyinstaller && pyinstaller dxclusterclient.spec
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import dxclient; print(dxclient.__version__)")
ENGINE=$(command -v podman || command -v docker)
"$ENGINE" run --rm -v "$PWD":/src:Z -w /src docker.io/tobix/pywine:3.12 bash -c '
  set -e
  wine python -m pip install --quiet "PySide6>=6.6" pyinstaller
  wine python -m PyInstaller --noconfirm --clean --distpath build/win-dist --workpath build/win-work dxclusterclient.spec
  chown -R '"$(id -u):$(id -g)"' build
'
mkdir -p dist/release
cp build/win-dist/DXClusterClient.exe "dist/release/DXClusterClient-${VERSION}-win64.exe"
echo "Built dist/release/DXClusterClient-${VERSION}-win64.exe"
