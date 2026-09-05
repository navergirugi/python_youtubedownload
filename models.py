"""Shared dataclass contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    channel: str = ""
    duration_str: str = ""


@dataclass(frozen=True)
class SongEntry:
    artist: str
    title: str

    def query_audio(self) -> str:
        from config import AUDIO_QUERY_TEMPLATE

        return AUDIO_QUERY_TEMPLATE.format(artist=self.artist, title=self.title)

    def query_video(self) -> str:
        from config import VIDEO_QUERY_TEMPLATE

        return VIDEO_QUERY_TEMPLATE.format(artist=self.artist, title=self.title)
