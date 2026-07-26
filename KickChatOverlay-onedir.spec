# -*- mode: python ; coding: utf-8 -*-
# Onefile derlemesi (KickChatOverlay.spec) her calistirmada kendini
# %TEMP%'e acan bir bootloader kullanir; bu ozel oz-acilim paterni
# antivirus/Defender heuristiklerinde en cok yanlis pozitif alan
# PyInstaller imzasidir. Bu spec ayni uygulamayi klasor (onedir)
# olarak paketler - hicbir oz-acilim yapmaz, AV yanlis pozitifi
# riskini onemli olcude dusurur. Dagitim icin klasoru zip'leyip
# paylasmak yeterli.

EXCLUDE_SUBSTR = [
    "opengl32sw", "avcodec", "avformat", "avutil", "swresample", "swscale",
    "qt6quick", "qt6qml", "qt6designer", "qt6pdf", "qt6multimedia",
    "qt6remoteobjects", "qt6positioning", "qt6sensors", "qt6serialport",
    "qt6bluetooth", "qt6nfc", "qt6sql", "qt6test", "qt6websockets",
    "qt6webchannel", "qt6help", "qt6xml", "qt63d", "qt6opengl",
    "qt6shadertools", "qt6quickcontrols2", "d3dcompiler", "qt6network",
    "qt6httpserver", "qt6webview", "qt6spatialaudio", "qt6texttospeech",
    "qt6location", "qt6printsupport", "qt6statemachine", "qt6labs",
    "qt6quicktemplates", "qt6quickdialogs", "qt6webenginecore",
    "qt6webenginewidgets", "qt6pdfium", "qt6httpserver",
    "/qml/", "\\qml\\", "/multimedia/", "\\multimedia\\",
    "/position/", "\\position\\", "/sensors/", "\\sensors\\",
    "/sqldrivers/", "\\sqldrivers\\", "/tls/", "\\tls\\",
    "/webview/", "\\webview\\", "/sensorgestures/", "\\sensorgestures\\",
    "/renderplugins/", "\\renderplugins\\", "/webenginewidgets/",
    # qico.dll BURADA KALMASIN: uygulama ikonu/tray icon calisma
    # zamaninda icon.ico'yu QIcon ile okuyor, bu plugin olmadan QIcon
    # sessizce null doner (tray "No Icon set" uyarisi verip kaybolur).
    "qicns", "qtiff", "qtga", "qwbmp", "qpdf.dll", "qdds",
    "qtuiotouchplugin", "qoffscreen", "qminimal",
    "qsvgicon",
]


def _keep(entry):
    name = str(entry[0]).lower() + " " + str(entry[1]).lower()
    return not any(s in name for s in EXCLUDE_SUBSTR)


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("icon.ico", "."), ("sounds", "sounds")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KickChatOverlay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="KickChatOverlay",
)
