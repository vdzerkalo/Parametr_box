# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Autonomous Box Generator (Windows portable build).
# Consumed by .github/workflows/build_windows.yml -> `pyinstaller box_generator.spec`.
# Produces a one-folder portable build at dist/BoxGenerator_Portable/.

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pyqtgraph.opengl',
        'OpenGL', 'OpenGL.platform.win32', 'OpenGL.arrays',
        'OpenGL.GL', 'OpenGL.GLU',
        'shapely', 'shapely.geometry', 'shapely.ops',
        'mapbox_earcut',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # cadquery/OCP were removed from the project; exclude leftovers to keep the build lean.
    excludes=['cadquery', 'OCP', 'cadquery_ocp', 'casadi', 'nlopt', 'ezdxf',
              'tkinter', 'matplotlib', 'PySide6.QtWebEngineCore'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BoxGenerator_Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # GUI app: no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BoxGenerator_Portable',
)
