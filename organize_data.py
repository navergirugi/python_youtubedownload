import os
import re
import shutil

DATA_DIR = 'data'
SINGER_FILE = 'singer.txt'

def organize():
    if not os.path.exists(DATA_DIR):
        print("Data directory not found.")
        return

    files = [f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f)) and f.endswith('.mp3')]
    artists = set()

    print(f"Total {len(files)} files found. Reorganizing...")

    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        
        # 파일명에서 가수 추출 시도
        # 형식 1: 0001. 가수 - 제목.mp3
        match = re.match(r'^\d{4}\.\s*(.+?)\s*[-–]\s*(.+)\.mp3$', filename)
        if match:
            artist = match.group(1).strip()
        else:
            # 형식 2: 가수 - 제목.mp3 (번호 없음)
            match2 = re.match(r'^(.+?)\s*[-–]\s*(.+)\.mp3$', filename)
            if match2:
                artist = match2.group(1).strip()
            else:
                artist = "Unknown Artist"
        
        # 특수문자 제거 (폴더명용)
        safe_artist = re.sub(r'[\\/*?:"<>|]', "", artist)
        artists.add(safe_artist)
        
        artist_dir = os.path.join(DATA_DIR, safe_artist)
        if not os.path.exists(artist_dir):
            os.makedirs(artist_dir)
            
        target_path = os.path.join(artist_dir, filename)
        
        try:
            shutil.move(filepath, target_path)
        except Exception as e:
            print(f"Error moving {filename}: {e}")

    # singer.txt 생성
    with open(SINGER_FILE, 'w', encoding='utf-8') as f:
        for artist in sorted(list(artists)):
            f.write(f"{artist}\n")
            
    print(f"Reorganization complete. Created {SINGER_FILE} with {len(artists)} artists.")

if __name__ == "__main__":
    organize()
