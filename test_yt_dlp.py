import json
from yt_dlp import YoutubeDL

def test_url(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'ignoreerrors': True,
        'no_playlist': False,
        'playlist_items': '1:5',
        'compat_opts': ['no-youtube-related-video'],
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print(f"URL: {url}")
        print(f"Type: {info.get('_type')}")
        print(f"Entries count: {len(info.get('entries', []))}")
        if 'entries' in info and len(info['entries']) > 0:
            print(f"First entry title: {info['entries'][0].get('title')}")
        print("-" * 20)

# Single video (not a playlist)
test_url("https://www.youtube.com/watch?v=AqI97zHMoQw")
# Video in a mix
test_url("https://www.youtube.com/watch?v=AqI97zHMoQw&list=RDMM")
# Real playlist
test_url("https://www.youtube.com/playlist?list=PL4fGSI1pDJn6jWqsMTz976UX6GAn5e8MA")
