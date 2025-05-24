# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['videofm.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.'), ('assets', 'assets')],
    hiddenimports=['requests', 'yt_dlp', 'ffmpeg', 'dotenv', 'python_dotenv.main', 'googleapiclient', 'googleapiclient.discovery', 'tqdm', 'ffmpeg_downloader'],
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
    name='videofm',
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
    icon="assets/icons/icon.ico" # for windows
)
app = BUNDLE(
    exe,
    name='videofm.app',
    icon='assets/icons/icon.icns',  # For macOS
    bundle_identifier='com.fromis9.videofm',
)
