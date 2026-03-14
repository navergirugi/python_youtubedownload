import re

def parse_timestamps(description):
    timestamps = []
    # (기존) time_pattern = re.compile(r'[\[({]?(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})[\])}]?\s*[-]?\s*(.+)')
    # (수정)
    time_pattern = re.compile(r'[\[({]?(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})[\])}]?[\s\-:]*(.+)')
    
    for line in description.split('\n'):
        # 라인 앞부분 (01) 등 제거
        line = re.sub(r'^\(\d+\)\s*', '', line).strip()
        
        match = time_pattern.search(line)
        if match:
            time_str = match.group(1)
            raw_title = match.group(2).strip()
            print(f"[{time_str}] {raw_title}")

text = """
00:02:00 해운대 엘레지/작사 한산도/작곡 백영호
00:02:59 꿈꾸는 백마강/작사 조명암/작곡 임근식 
00:06:15 나그네 설움/작사 고려성/작곡 이재호
00:09:23 남원애수/작사 김부해/작곡 김화영
"""
parse_timestamps(text)
