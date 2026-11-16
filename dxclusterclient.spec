# PyInstaller spec: `pyinstaller dxclusterclient.spec`
# Produces a single-file executable in dist/ (Windows: DXClusterClient.exe, Linux: DXClusterClient)
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["dxclient/__main__.py"],
    pathex=["."],
    datas=[("dxclient/data", "dxclient/data")],
    hiddenimports=["PySide6.QtMultimedia"],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="DXClusterClient",
    console=False,
    upx=False,
)
