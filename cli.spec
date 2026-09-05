# -*- mode: python ; coding: utf-8 -*-
"""CLI onefile 빌드용 (ffmpeg+ffprobe 내장). 빌드: pyinstaller --noconfirm cli.spec"""
block_cipher = None


def _ffmpeg_binaries():
    """ffmpeg+ffprobe를 번들에 포함 (app.spec과 동일 로직)."""
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
                return  # choco shim 제외, 진짜 바이너리만
        except OSError:
            return
        key = _os.path.normcase(_os.path.abspath(exe))
        if key in seen:
            return
        seen.add(key)
        out.append((exe, "."))
        d, base = _os.path.split(exe)
        if base.lower().startswith("ffmpeg"):
            ext = _os.path.splitext(base)[1]
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
    ['cli.py'],
    pathex=[],
    binaries=_ffmpeg_binaries(),
    datas=[],
    hiddenimports=['mutagen'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
