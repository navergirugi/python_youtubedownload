import re
import subprocess
import os

def parse_tracklist_without_time(description):
    tracks = []
    # 매치: 줄 시작부분에 숫자 + 점/괄호 + 공백 후 텍스트 (예: "01. 찔레꽃 - 백난아")
    pattern = re.compile(r'^\s*(?:\d{1,2}|\d{1,2}\/)[\.\)]\s+(.+)', re.MULTILINE)
    
    for match in pattern.finditer(description):
        raw_title = match.group(1).strip()
        tracks.append({
            'raw_title': raw_title
        })
    return tracks

def detect_silences(audio_file):
    # -i audio_file -af silencedetect=noise=-30dB:d=1.5 -f null -
    ffmpeg_exe = r'C:\ProgramData\chocolatey\bin\ffmpeg.exe'
    
    # 더미 파일을 만들어 테스트 (이 부분 주석 처리하고 가짜 출력으로 대체)
    # 실제로는 subprocess.run(..., stderr=subprocess.PIPE, text=True) 로 읽음
    
    dummy_output = """
[silencedetect @ 0000000000] silence_start: 180.5
[silencedetect @ 0000000000] silence_end: 182.2 | silence_duration: 1.7
[silencedetect @ 0000000000] silence_start: 360.2
[silencedetect @ 0000000000] silence_end: 362.5 | silence_duration: 2.3
    """
    
    silences = []
    start_pattern = re.compile(r'silence_start:\s+([\d\.]+)')
    end_pattern = re.compile(r'silence_end:\s+([\d\.]+)')
    
    for line in dummy_output.split('\n'):
        rem = start_pattern.search(line)
        if rem:
            silences.append({'start': float(rem.group(1)), 'end': None})
        
        rem_end = end_pattern.search(line)
        if rem_end and silences:
            silences[-1]['end'] = float(rem_end.group(1))
            
    return silences


text = """
◈ ◈ 흘러간 옛노래 노래 모음 [전곡가사첨부] 03 ◈ ◈
   • ◈ ◈ 흘러간 옛노래 노래 모음 [전곡가사첨부] -03- ◈ ◈  
01. 찔레꽃 - 백난아
02. 비내리는 고모령 - 현인
03. 물새우는 강언덕- 나애심
04. 이별의 부산정거장 - 남인수
05. 단장의 미아리고개 - 최정자
"""

print(parse_tracklist_without_time(text))
print(detect_silences("dummy.mp3"))

