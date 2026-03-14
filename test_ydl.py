import sys
from yt_dlp import YoutubeDL

url = "https://www.youtube.com/watch?v=QbyWhyFqnnQ&list=RDQbyWhyFqnnQ&start_radio=1"
ydl_opts = {
    'quiet': True,
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'ignoreerrors': True,
    'no_playlist': False,
}
print("Starting extraction...")
with YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    print("ID:", info.get('id'))
    print("_type:", info.get('_type'))
    print("title (playlist name):", info.get('title'))
    if 'entries' in info:
        entries = list(info['entries'])
        print("entries length:", len(entries))
        for i, e in enumerate(entries[:10]):
            print(f"entry {i}: {e.get('title')} (by {e.get('uploader')})")
    else:
        print("No entries.")
