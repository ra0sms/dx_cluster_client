# PyInstaller spec: `pyinstaller dxclusterclient.spec`
#   Windows: dist/DXClusterClient.exe            (single file, no console)
#   Linux:   dist/DXClusterClient/DXClusterClient (folder; packed into an AppImage by
#            packaging/build_appimage.sh)
# -*- mode: python ; coding: utf-8 -*-
import sys

WINDOWS = sys.platform == "win32"

a = Analysis(
    ["dxclient/__main__.py"],
    pathex=["."],
    datas=[("dxclient/data", "dxclient/data")],
    hiddenimports=["PySide6.QtMultimedia", "PySide6.QtSvg"],
    excludes=[
        "tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
        "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.QtPdf",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    ],
)
pyz = PYZ(a.pure)

if WINDOWS:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas,
        name="DXClusterClient",
        icon="packaging/icon.ico",
        console=False,
        upx=False,
    )
else:
    exe = EXE(
        pyz, a.scripts,
        exclude_binaries=True,
        name="DXClusterClient",
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="DXClusterClient", upx=False)
