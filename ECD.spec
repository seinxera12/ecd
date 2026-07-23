# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

datas = [
    ('ECD/assets', 'ECD/assets'),
]

hiddenimports = [
    'ezdxf',
    'ezdxf.addons.drawing',
    'ezdxf.addons.drawing.backend',
    'ezdxf.addons.drawing.frontend',
    'ezdxf.addons.drawing.layout',
    'ezdxf.addons.drawing.matplotlib',
    'ezdxf.addons.drawing.properties',
    'ezdxf.addons.drawing.svg',
    'ezdxf.fonts',
    'ezdxf.fonts.font_manager',
    'ezdxf.fonts.fonts',
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_agg',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'groq',
    'google.genai',
    'dotenv',
    'PIL',
    'PIL.Image',
    'requests',
]

a = Analysis(
    ['ECD/main_app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ECD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for console debug variant
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ECD',
)
