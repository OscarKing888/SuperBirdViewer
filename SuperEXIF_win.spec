# -*- mode: python ; coding: utf-8 -*-
# Windows 打包用：仅包含 exiftools_win，不包含 exiftools_mac

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('super_viewer.cfg', '.'),
        ('image/superexif.png', 'image'),
        ('image/superexif.ico', 'image'),
        ('app_common/exif_io/exiftools_win', 'app_common/exif_io/exiftools_win'),
    ],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='SuperViewer',
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
    icon='image/superexif.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SuperViewer',
)
