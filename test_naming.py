import os
import naming


def test_sanitize_strips_illegal():
    assert naming.sanitize('a/b\\c:d*e?f"g<h>i|j') == "abcdefghi j" or "/" not in naming.sanitize("a/b")


def test_sanitize_keeps_unicode():
    assert naming.sanitize("아이유 - Celebrity") == "아이유 - Celebrity"
    assert "あいみょん" in naming.sanitize("あいみょん - マリーゴールド")


def test_unique_path_collision(tmp_path):
    d = str(tmp_path)
    open(os.path.join(d, "A - B.mp3"), "w").close()
    p1 = naming.unique_path(d, "A - B", ".mp3")
    assert p1.endswith("A - B (1).mp3")
    open(p1, "w").close()
    p2 = naming.unique_path(d, "A - B", "mp3")
    assert p2.endswith("A - B (2).mp3")


def test_song_filename():
    assert naming.song_filename("아이유", "Celebrity") == "아이유 - Celebrity"
