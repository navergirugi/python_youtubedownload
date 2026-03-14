import os
import re
import subprocess
import sys

# 기본 설정
DATA_DIR = 'data'
FFMPEG_EXE = r'C:\ProgramData\chocolatey\bin\ffmpeg.exe'

def get_valid_input(prompt, default=None):
    val = input(prompt).strip()
    return val if val else default

def fix_folder_metadata():
    print("\n" + "="*50)
    print(" [범용 폴더 메타데이터 수정 도구]")
    print("="*50)

    # 1. 대상 폴더 입력
    print(f"\n현재 데이터 폴더: {os.path.abspath(DATA_DIR)}")
    target_folder_name = get_valid_input("작업할 폴더명을 입력하세요 (data/ 하위 폴더명): ")
    if not target_folder_name:
        print("[오류] 폴더명을 입력해야 합니다.")
        return

    source_dir = os.path.join(DATA_DIR, target_folder_name)
    if not os.path.exists(source_dir):
        # 만약 입력한 게 절대 경로라면 그대로 사용 시도
        if os.path.exists(target_folder_name):
            source_dir = target_folder_name
        else:
            print(f"[오류] 폴더를 찾을 수 없습니다: {source_dir}")
            return

    # 2. 새로운 가수명 입력
    new_artist = get_valid_input("변경할 가수명을 입력하세요: ")
    if not new_artist:
        print("[오류] 가수명을 입력해야 합니다.")
        return

    # 3. 제목 정제 규칙 (선택 사항)
    print("\n제목에서 제거하고 싶은 문구가 있나요? (예: '옛노래', '가요무대' 등)")
    print("입력하지 않으면 파일명에서 가수명과 번호를 제외한 부분이 제목이 됩니다.")
    remove_pattern = get_valid_input("제거할 문구 (정규표현식 가능, 없으면 Enter): ")

    # 4. 대상 가수의 목적지 폴더 준비
    target_dir = os.path.join(DATA_DIR, new_artist)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # 파일 목록 가져오기
    files = [f for f in os.listdir(source_dir) if f.lower().endswith('.mp3')]
    if not files:
        print(f"[알림] '{source_dir}' 폴더에 MP3 파일이 없습니다.")
        return

    print(f"\n[분석] 총 {len(files)}개의 파일을 처리합니다.")
    confirm = input("실행하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        print("[중단] 사용자가 작업을 취소했습니다.")
        return

    processed_count = 0
    for f in files:
        old_path = os.path.join(source_dir, f)
        
        # 파일명 분석 (형식: 번호. 가수 - 제목.mp3)
        # 다양한 형식을 지원하기 위해 유연한 매칭
        match = re.match(r'^(\d{4}\.\s*)?(.+?)\s*-\s*(.+)\.mp3$', f)
        
        prefix = ""
        raw_content = ""
        
        if match:
            prefix = match.group(1) if match.group(1) else ""
            # 기존 형식이면 match.group(3)이 제목 후보
            raw_content = match.group(3)
        else:
            # 형식이 다르면 확장자 제외 전체를 제목 후보로
            name_without_ext = os.path.splitext(f)[0]
            # 앞의 번호는 유지 시도
            num_match = re.match(r'^(\d{4}\.\s*)(.+)', name_without_ext)
            if num_match:
                prefix = num_match.group(1)
                raw_content = num_match.group(2)
            else:
                raw_content = name_without_ext

        # 제목 정제
        clean_title = raw_content
        if remove_pattern:
            clean_title = re.sub(remove_pattern, '', clean_title).strip()
        
        # 번호가 없으면 생성 (또는 기존 것 활용)
        if not prefix:
            # 이 경우에는 번호 없이 진행하거나 별도의 인덱스 부여가 필요할 수 있음
            pass

        new_filename = f"{prefix}{new_artist} - {clean_title}.mp3" if prefix else f"{new_artist} - {clean_title}.mp3"
        # 파일명에서 금지된 문자 제거
        new_filename = re.sub(r'[\\/*?:"<>|]', "", new_filename)
        
        new_path = os.path.join(target_dir, new_filename)

        sys.stdout.write(f"\r  [처리중] {f[:30]}... -> {new_filename[:30]}... ")
        sys.stdout.flush()

        # ffmpeg를 이용한 태그 수정 및 이동
        temp_path = os.path.join(source_dir, "temp_fix_meta.mp3")
        cmd = [
            FFMPEG_EXE, '-i', old_path,
            '-metadata', f'artist={new_artist}',
            '-metadata', f'title={clean_title}',
            '-c', 'copy',
            '-y', temp_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_path):
                if os.path.exists(new_path):
                    # 중복 이름 방지 (번호_1 식)
                    base, ext = os.path.splitext(new_path)
                    new_path = f"{base}_dup{ext}"
                
                os.rename(temp_path, new_path)
                os.remove(old_path)
                processed_count += 1
        except Exception as e:
            print(f"\n    [오류] {f}: {e}")

    print(f"\n\n[완료] 총 {processed_count}곡의 메타데이터 수정 및 이동을 마쳤습니다.")
    
    # 소스 폴더 정리
    try:
        if not os.listdir(source_dir):
            os.rmdir(source_dir)
            print(f"[알림] 빈 폴더를 삭제했습니다: {source_dir}")
    except:
        pass

if __name__ == "__main__":
    try:
        fix_folder_metadata()
    except KeyboardInterrupt:
        print("\n[중단] 사용자에 의해 중지되었습니다.")
