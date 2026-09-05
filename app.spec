# -*- mode: python ; coding: utf-8 -*-
"""macOS: onedir + BUNDLE(.app). CLI: pyinstaller --onefile cli.py"""
block_cipher = None


def _ffmpeg_binaries():
    """ffmpeg+ffprobe를 번들에 포함 (둘 다 있어야 yt-dlp 변환/합치기 동작).

    우선순위: PATH의 진짜 바이너리(choco shim 제외) → choco/brew 정석 경로
    → imageio-ffmpeg 폴백(ffmpeg만, ffprobe 없음).
    """
    import glob as _glob
    import os as _os
    import shutil as _shutil

    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    def _add(exe: str | None) -> None:
        if not exe or not _os.path.isfile(exe):
            return
        try:
            if _os.path.getsize(exe) < 1_000_000:
                return  # choco shim(수백KB) 제외, 진짜 바이너리(수십MB)만
        except OSError:
            return
        key = _os.path.normcase(_os.path.abspath(exe))
        if key in seen:
            return
        seen.add(key)
        out.append((exe, "."))
        # 같은 폴더의 ffprobe도 함께 (yt-dlp merge/extract에 둘 다 필요)
        d, base = _os.path.split(exe)
        if base.lower().startswith("ffmpeg"):
            ext = _os.path.splitext(base)[1]  # '.exe' or ''
            for probe in (f"ffprobe{ext}", "ffprobe.exe", "ffprobe"):
                p = _os.path.join(d, probe)
                pk = _os.path.normcase(_os.path.abspath(p))
                if p != exe and _os.path.isfile(p) and pk not in seen:
                    seen.add(pk)
                    out.append((p, "."))
                    break

    _add(_shutil.which("ffmpeg"))
    for cand in (
        r"C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ):
        _add(cand)
    for cand in _glob.glob(
        r"C:\ProgramData\chocolatey\lib\ffmpeg*\tools\ffmpeg\bin\ffmpeg.exe"
    ):
        _add(cand)
    if out:
        return out
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
        'CFBundleShortVersionString': '1.0.4',
    },
)
