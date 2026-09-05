import os
import config


def test_ensure_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_AUDIO", str(tmp_path / "audio"))
    monkeypatch.setattr(config, "DATA_VIDEO", str(tmp_path / "video"))
    config.ensure_dirs()
    assert os.path.isdir(str(tmp_path / "audio"))
    assert os.path.isdir(str(tmp_path / "video"))


def test_check_ffmpeg_message(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    try:
        config.check_ffmpeg()
        assert False, "should raise"
    except config.FFmpegMissingError as e:
        assert "brew install ffmpeg" in str(e)
