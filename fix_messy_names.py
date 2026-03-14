import os
import re

DATA_DIR = 'data'

def clean_title_logic(title):
    # 정규표현식 로직 (extractor.py와 동일)
    t_pat = r'\d+(?::\d+){1,2}|\d{6,}'
    title = re.sub(fr'[\[\(\{{]\s*{t_pat}(?:\s*[~-]\s*{t_pat})*\s*[\]\)\}}]', '', title).strip()
    title = re.sub(fr'{t_pat}(?:\s*[~-]\s*{t_pat})*', '', title).strip()
    title = re.sub(r'[\[\]\(\)\{{\}\~\=\|\/]', ' ', title).strip()
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'^[-\s\.]+|[-\s\.]+$', '', title).strip()
    return title

def fix_all_filenames():
    print("Checking for messy filenames...")
    fixed_count = 0
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.mp3'):
                # 형식: 0001. 주현미 - 곡제목 [00:00].mp3
                match = re.match(r'^(\d{4}\.\s*)(.+)\.mp3$', f)
                if match:
                    prefix = match.group(1)
                    content = match.group(2)
                    
                    new_content = clean_title_logic(content)
                    if new_content != content:
                        new_name = f"{prefix}{new_content}.mp3"
                        old_path = os.path.join(root, f)
                        new_path = os.path.join(root, new_name)
                        print(f"  [수정] {f} -> {new_name}")
                        try:
                            # 겹치는 파일명이 있으면 넘김
                            if os.path.exists(new_path):
                                os.remove(old_path) # 사실상 동일 파일이므로 옛날 것 삭제
                                print(f"  [삭제] 중복된 파일 정리: {f}")
                            else:
                                os.rename(old_path, new_path)
                            fixed_count += 1
                        except Exception as e:
                            print(f"  [오류] {e}")
    print(f"Cleanup complete. Total {fixed_count} files cleaned.")

if __name__ == "__main__":
    fix_all_filenames()
