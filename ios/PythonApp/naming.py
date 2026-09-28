"""Filename sanitizing + collision-free unique paths."""
from __future__ import annotations

import os
import re

_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize(name: str) -> str:
    cleaned = _ILLEGAL_CHARS.sub("", name)
    cleaned = cleaned.strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def unique_path(directory: str, base: str, ext: str) -> str:
    if not ext.startswith("."):
        ext = "." + ext
    safe_base = sanitize(base)
    candidate = os.path.join(directory, f"{safe_base}{ext}")
    if not os.path.exists(candidate):
        return candidate
    i = 1
    while True:
        candidate = os.path.join(directory, f"{safe_base} ({i}){ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def song_filename(artist: str, title: str) -> str:
    return sanitize(f"{artist} - {title}")
