import os
import re
import subprocess

DATA_DIR = 'data'
UNKNOWN_DIR = os.path.join(DATA_DIR, 'Unknown Artist')
TARGET_DIR = os.path.join(DATA_DIR, '하춘화')
FFMPEG_EXE = r'C:\ProgramData\chocolatey\bin\ffmpeg.exe'

def fix_metadata():
    if not os.path.exists(UNKNOWN_DIR):
        print(f"[오류] 폴더를 찾을 수 없습니다: {UNKNOWN_DIR}")
        return

    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

    files = [f for f in os.listdir(UNKNOWN_DIR) if f.endswith('.mp3')]
    print(f"[분석] {len(files)}개의 파일을 처리합니다.")

    for f in files:
        # 패턴: 0548. Unknown Artist - 하춘화 옛노래 30 타향살이.mp3
        # 또는: 0548. Unknown Artist - 제목.mp3
        match = re.match(r'^(\d{4}\.\s*)Unknown Artist\s*-\s*(.+)\.mp3$', f)
        if not match:
            print(f"  [건너뜀] 패턴 불일치: {f}")
            continue

        prefix = match.group(1) # 0548. 
        raw_content = match.group(2) # 하춘화 옛노래 30 타향살이
        
        # 제목 정제: "하춘화 옛노래 30 타향살이" -> "타향살이"
        clean_title = re.sub(r'^하춘화\s*옛노래\s*\d+\s*', '', raw_content).strip()
        
        new_filename = f"{prefix}하춘화 - {clean_title}.mp3"
        old_path = os.path.join(UNKNOWN_DIR, f)
        new_path = os.path.join(TARGET_DIR, new_filename)

        print(f"  [처리중] {f} -> {new_filename}")

        # ffmpeg를 이용한 태그 수정 및 이동 (임시 파일 생성 후 이동)
        temp_path = os.path.join(UNKNOWN_DIR, "temp_fix.mp3")
        cmd = [
            FFMPEG_EXE, '-i', old_path,
            '-metadata', f'artist=하춘화',
            '-metadata', f'title={clean_title}',
            '-c', 'copy',
            '-y', temp_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_path):
                if os.path.exists(new_path):
                    os.remove(new_path)
                os.rename(temp_path, new_path)
                os.remove(old_path)
                # print(f"    [완료] {new_filename}")
        except Exception as e:
            print(f"    [오류] {e}")

    # 폴더가 비었으면 삭제
    if not os.listdir(UNKNOWN_DIR):
        os.rmdir(UNKNOWN_DIR)
        print(f"[완료] 빈 폴더 삭제: {UNKNOWN_DIR}")

if __name__ == "__main__":
    fix_metadata()
