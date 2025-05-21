# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules

all_libraries = [
    'app',
    'find',
    'parse',
    'addDeviceData',  # Missing comma in original
    'SynBlue',
    'SynProtocol',
    'webserver',
    'sessionData',
    'bottle_websocket',
    'asyncio',
    'bleak',
    'openpyxl',
    'pexpect',
    'Gateway',
    'coloredlogs',
    'eel',
    'winrt',
    'winrt.windows.devices.bluetooth',
    'winrt.windows.devices.bluetooth.advertisement',
    'winrt.windows.devices.bluetooth.genericattributeprofile',
    'winrt.windows.devices.enumeration',
    'winrt.windows.foundation',
    'winrt.windows.foundation.collections',
    'winrt.windows.storage.streams',
    'winrt.runtime',
    'requests'
]

hidden_imports = []
for l in all_libraries:
    hidden_imports += collect_submodules(l)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('gui', 'gui'),
        ('Gateway', 'Gateway'),
        ('tools', 'tools'),
        ('SynBlue.py', '.'),
        ('SynProtocol.py', '.'),
        ('SessionData.py', '.'),
        ('webserver.py', '.'),
        ('bluetoothctl_wrapper.py', '.'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['bleak.backends.corebluetooth', 'objc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SBLETS',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui/hqv_logo.ico',
    onefile=True
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SBLETS'
)

import shutil

shutil.copyfile('config.ini', '{0}/config.ini'.format(DISTPATH))
shutil.copyfile('deviceLookup.json', '{0}/deviceLookup.json'.format(DISTPATH))
shutil.copyfile('deviceSecrets.json', '{0}/deviceSecrets.json'.format(DISTPATH))