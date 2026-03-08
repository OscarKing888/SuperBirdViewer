# -*- mode: python ; coding: utf-8 -*-
# macOS 打包用：仅包含 exiftools_mac，不包含 exiftools_win

import os


def _build_datas():
    datas = [
        ('super_viewer.cfg', '.'),
        ('icons/app_icon.png', 'icons'),
        ('icons/app_icon.ico', 'icons'),
        ('icons/app_icon.icns', 'icons'),
        ('app_common/exif_io/exiftools_mac', 'app_common/exif_io/exiftools_mac'),
        ('app_common/about_dialog/about.cfg', 'app_common/about_dialog'),
    ]
    about_images_dir = os.path.join('app_common', 'about_dialog', 'images')
    if os.path.isdir(about_images_dir):
        datas.append((about_images_dir, 'app_common/about_dialog/images'))
    return datas


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=_build_datas(),
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icons/app_icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SuperViewer',
)
app = BUNDLE(
    coll,
    name='SuperViewer.app',
    icon='icons/app_icon.icns',
    bundle_identifier=None,
)
