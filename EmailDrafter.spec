# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['email_drafter_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('dropdown_arrow.svg', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy',
        'PIL',
        'Pillow',
        'cryptography',
        'bcrypt',
        'psutil',
        'test',
        'unittest',
        'pydoc',
        'doctest',
        'tkinter',
        '_tkinter',
        'PyQt5',
        'PyQt6',
        'curses',
        'xml.dom',
        'xmlrpc',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='EmailDrafter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['email_drafter.icns'],
    exclude_binaries=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='EmailDrafter',
)
app = BUNDLE(
    coll,
    name='EmailDrafter.app',
    icon='email_drafter.icns',
    bundle_identifier='com.emaildrafter.desktop',
)
