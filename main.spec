# main.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None
app_name = 'jarvis_chatbot'
added_files = [
    ('static', 'static'), 
    ('templates', 'templates'), 
    ('sounds', 'sounds'),
    ('static', 'static'),
    ('config.json.example', '.'), 
    ('readme.md', '.'), 
    ('jarvis_v2.onnx', '.'), 
    ('jarvis_v2.tflite', '.'), 
]
hiddenimports = ['engineio.async_drivers.threading']

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon='static/images/favicon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    #a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name
)

# Post-compile hook to copy config.json.example to config.json
import shutil
shutil.copy(f"dist/{app_name}/_internal/config.json.example", f"dist/{app_name}/_internal/config.json")