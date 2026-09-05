# -*- mode: python ; coding: utf-8 -*-
"""macOS: onedir + BUNDLE(.app). CLI: pyinstaller --onefile cli.py"""
block_cipher = None


def _ffmpeg_binaries():
    """imageio-ffmpeg 정적 바이너리를 번들에 포함 (없으면 스킵)."""
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        return [(exe, ".")]
    except Exception:
        return []


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=_ffmpeg_binaries(),
    datas=[],
    hiddenimports=['PySide6', 'mutagen'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MusicDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='MusicDownloader',
)
app = BUNDLE(
    coll,
    name='MusicDownloader.app',
    icon='icon.icns',
    bundle_identifier='com.local.musicdownloader',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.0.0',
    },
)
