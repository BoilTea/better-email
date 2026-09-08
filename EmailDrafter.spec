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

# PyInstaller's PySide6 hook discovers every plugin that ships with Qt. Some of
# those plugins pull in large optional frameworks (PDF, QML/Quick, virtual
# keyboard, and OpenGL) that this widgets-only application never uses.
_unused_qt_frameworks = (
    'QtOpenGL.framework',
    'QtPdf.framework',
    'QtQml.framework',
    'QtQmlMeta.framework',
    'QtQmlModels.framework',
    'QtQmlWorkerScript.framework',
    'QtQuick.framework',
    'QtVirtualKeyboard.framework',
    'QtVirtualKeyboardQml.framework',
)


def _keep_qt_binary(entry):
    destination = entry[0].replace('\\', '/')

    if any(framework in destination for framework in _unused_qt_frameworks):
        return False
    if '/plugins/platforminputcontexts/' in destination:
        return False
    if '/plugins/generic/' in destination:
        return False
    if '/plugins/imageformats/' in destination:
        return destination.endswith(('libqicns.dylib', 'libqico.dylib', 'libqsvg.dylib'))
    if '/plugins/tls/' in destination:
        return destination.endswith('libqsecuretransportbackend.dylib')
    return True


a.binaries = [entry for entry in a.binaries if _keep_qt_binary(entry)]
a.datas = [
    entry
    for entry in a.datas
    if not entry[0].replace('\\', '/').startswith('PySide6/Qt/translations/')
    and not any(
        framework in entry[0].replace('\\', '/')
        for framework in _unused_qt_frameworks
    )
]
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
