# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=[('Icons', 'Icons'),
           ('Fonts', 'Fonts'),
    ],  
    hiddenimports=['heater'],  # Add heater back to hiddenimports so it can be imported
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Diamond Heater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Icons/Icon.ico', 
)
