# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

NAME = "ToBWirelessManager"  # 应用名称
MAIN_SCRIPT = "ToBWirelessManager.py"  # 主程序入口

# 获取QGIS和Python的路径（根据实际情况调整）
QGIS_PATH = r"C:\OSGeo4W\apps\qgis-qt6"
PYTHON_PATH = r"C:\OSGeo4W\apps\Python312"
QT_PATH = r"C:\OSGeo4W\apps\Qt6"  # PyQt6对应的Qt6路径

block_cipher = None

os.environ['PATH'] = f"{QT_PATH}\\bin;{QGIS_PATH}\\bin;{os.environ['PATH']}"
os.environ['QT_API'] = 'pyqt6'  # 告诉PyInstaller使用PyQt6

binaries = [
    (os.path.join(QGIS_PATH, "python", "qgis", "_core.pyd"), "."),
    (os.path.join(QGIS_PATH, "python", "qgis", "_gui.pyd"), "."),
]

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[],
    binaries=binaries,
    datas=[(os.path.join(QGIS_PATH, "plugins"), "qgis\\plugins"),
        (os.path.join(PYTHON_PATH, "Lib", "site-packages", "PyQt6", "*.pyd"), "PyQt6"),
        (os.path.join(QT_PATH, "plugins", "styles"), "PyQt6\\Qt6\\plugins\\styles"),
        (os.path.join(QT_PATH, "plugins", "iconengines"), "PyQt6\\Qt6\\plugins\\iconengines"),
        (os.path.join(QT_PATH, "plugins", "imageformats"), "PyQt6\\Qt6\\plugins\\imageformats"),
        (os.path.join(QT_PATH, "plugins", "platforms"), "PyQt6\\Qt6\\plugins\\platforms")],
    hiddenimports=[
        'qgis._core',
        'qgis._gui'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook.py'],
    excludes=['PyQt5'],
    noarchive=False,
    optimize=0,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/logo/LOGO.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=NAME,
)
