import os
import re
import sys
import time
import json
import subprocess
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
from google import genai
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# .env 파일 로드
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY == "your_api_key_here":
    GEMINI_API_KEY = None

# Gemini 전용 브라우저 프로필 경로 (메인 크롬과 충돌 방지용)
GEMINI_BROWSER_PROFILE = os.path.join(os.path.dirname(__file__), ".gemini_profile")
if not os.path.exists(GEMINI_BROWSER_PROFILE):
    os.makedirs(GEMINI_BROWSER_PROFILE)

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini 설정 실패: {e}")
        GEMINI_API_KEY = None

# 데이터 저장 디렉토리 설정
DATA_DIR = 'data'

# 전역 메타데이터 로드
METADATA = {}
try:
    meta_path = os.path.join(os.path.dirname(__file__), 'metadata.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            METADATA = json.load(f)
except Exception as e:
    print(f"메타데이터 로드 실패: {e}")
# 분석 결과 캐시 (동일 URL 반복 분석 방지)
_ANALYSIS_CACHE = {}
_BROWSER_CACHE = {} # URL별 브라우저 추출 정보 캐시

def progress_hook(d):
    """다운로드 진행 상태를 표시합니다."""
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%')
        s = d.get('_speed_str', 'unknown speed')
        t = d.get('_eta_str', 'unknown time')
        sys.stdout.write(f"\r다운로드 중... {p} (속도: {s}, 남은 시간: {t})          ")
        sys.stdout.flush()
    elif d['status'] == 'finished':
        print("\n다운로드 완료! 변환 중...")

def get_video_info(url):
    """영상 정보를 가져옵니다. 재생목록 여부를 확인하기 위해 extract_flat="in_playlist" 사용."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'ignoreerrors': True,
        'no_playlist': False, # 플레이리스트 정보를 가져오기 위해 False 유지
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # 만약 entries가 있다면, 관련 영상(related_videos)이 섞이지 않도록 필터링
        if info and 'entries' in info:
            # 실제 비디오 ID가 있고, 광고나 추천 항목이 아닌 것만 남김
            info['entries'] = [e for e in info['entries'] if e and (e.get('url') or e.get('id'))]
        return info

def get_metadata_from_browser(url):
    """브라우저(Selenium)를 띄워 유튜브 영상 제목과 채널 정보를 통해 가수/제목을 추론합니다."""
    if url in _BROWSER_CACHE:
        return _BROWSER_CACHE[url]

    print(f"\n[브라우저 로드 중...] {url}")
    driver = None
    video_title, channel_name, description = "", "", ""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 헤드리스 모드
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # ChromeDriverManager 지연 방지를 위한 옵션
        os.environ['WDM_LOG_LEVEL'] = '0'
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        
        # 정보 로드 대기
        wait = WebDriverWait(driver, 15)
        
        # 제목 추출 (여러 셀렉터 시도)
        selectors = [
            "h1.ytd-video-primary-info-renderer", 
            "h1.ytd-watch-metadata",
            "yt-formatted-string.ytd-video-primary-info-renderer",
            "meta[name='title']"
        ]
        
        for sel in selectors:
            try:
                if sel.startswith("meta"):
                    video_title = driver.find_element(By.CSS_SELECTOR, sel).get_attribute("content")
                else:
                    elem = driver.find_element(By.CSS_SELECTOR, sel)
                    if elem.text:
                        video_title = elem.text
                        break
            except: continue

        # 채널명 추출
        channel_selectors = ["#upload-info #channel-name a", "#owner-sub-count", "ytd-video-owner-renderer #channel-name"]
        for sel in channel_selectors:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, sel)
                if elem.text:
                    channel_name = elem.text.strip()
                    break
            except: continue
        
        # 설명 추출
        try:
            desc_elem = driver.find_element(By.CSS_SELECTOR, "#description-inline_expander, #description")
            description = desc_elem.text
        except:
            pass
            
        if video_title or channel_name:
            print(f"  [브라우저 추출 성공]")
            print(f"  > 제목: {video_title}")
            print(f"  > 가수명(후보): {channel_name}")
        
    except Exception as e:
        print(f"[브라우저 오류] 정보 추출 실패: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass
    
    result = (channel_name, video_title, description[:500])
    _BROWSER_CACHE[url] = result
    return result

def get_metadata_from_gemini_web(track_title, video_title, full_description):
    """gemini.google.com 웹 UI에 직접 질문하여 가수와 제목을 알아냅니다."""
    print(f"\n[Gemini Web AI 접속 중...] {track_title}")
    
    # 전용 프로필 경로 절대 경로화 및 락 파일 제거
    profile_path = os.path.abspath(GEMINI_BROWSER_PROFILE)
    # 윈도우에서 브라우저 충돌을 일으키는 대표적인 락 파일들
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie", "lock"]
    for lf in lock_files:
        path = os.path.join(profile_path, lf)
        if os.path.exists(path):
            try: os.remove(path)
            except: pass

    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--profile-directory=Default")

        # 구글 봇 감지 우회 및 자동화 흔적 지우기
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 포트 충돌 방지 및 안전 실행 옵션
        chrome_options.add_argument("--remote-debugging-port=0") # 랜덤 포트 사용
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1280,1024")
        
        service = Service(ChromeDriverManager().install())
        
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            # 봇 감지 우회 스크립트
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
        except Exception as e:
            print(f"\n[오류] 브라우저 실행 실패: {e}")
            print("-" * 50)
            print("대응 방법:")
            print("1. 작업 관리자(Ctrl+Shift+Esc)에서 'chrome.exe'를 모두 강제로 종료하세요.")
            print("2. 'chromedriver.exe'가 있다면 그것도 종료하세요.")
            print(f"3. {GEMINI_BROWSER_PROFILE} 폴더를 수동으로 한 번 삭제해 보세요.")
            print("-" * 50)
            return None, None, False

        driver.get("https://gemini.google.com/app")
        wait = WebDriverWait(driver, 20)
        
        # 1. 로그인 여부 확인 및 대기
        try:
            login_buttons = driver.find_elements(By.XPATH, "//span[contains(text(),'로그인') or contains(text(),'Sign in')]")
            if login_buttons:
                print("\n" + "!"*60)
                print("[중요] Gemini 웹사이트에 로그인이 필요합니다 (처음 1회).")
                print("방금 뜬 브라우저 창에서 구글 계정으로 로그인을 시도해 주세요.")
                print("로그인에 성공하여 Gemini 메인 화면이 나올 때까지 이 창을 닫지 마세요.")
                print("!"*60)
                
                # 입력창이 나타날 때까지 대기
                wait_long = WebDriverWait(driver, 600)
                wait_long.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true']")))
                print("\n[성공] 로그인이 확인되었습니다.")
                time.sleep(2)
        except: pass

        # 2. 입력창 찾기
        input_selectors = ["div[contenteditable='true']", "textarea[aria-label*='Prompt']", "rich-textarea div"]
        prompt_input = None
        for sel in input_selectors:
            try:
                prompt_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                if prompt_input: break
            except: continue
            
        if not prompt_input:
            print("  [오류] 입력창을 찾을 수 없습니다. (페이지 응답 없음)")
            return None, None, False
            
        # 3. 질문 구성 (이모지 등 비-BMP 문자 제거하여 ChromeDriver 오류 방지)
        # 이모지를 남기면 ChromeDriver가 뻗으므로 안전한 문자 위주로 정제
        raw_prompt = f"""
        유튜브 영상 정보를 분석해서 아래 트랙의 정확한 '가수 이름'과 '노래 제목'을 추출해줘.
        타임스탬프와 전체 설명을 참고해서 이 곡의 실제 정보를 찾아줘.
        
        - 대상 곡: {track_title}
        - 영상 제목: {video_title}
        - 전체 설명: {full_description[:800]}
        
        **반드시 아래 형식으로만 답변해줘:**
        가수: [가수명] / 제목: [곡제목] / 일본노래여부: [네/아니오]
        """
        # BMP(0~FFFF) 범위 밖의 문자(이모지 등)를 수동으로 걸러냄
        clean_prompt = "".join(c if ord(c) <= 0xFFFF else "" for c in raw_prompt)
        
        prompt_input.click()
        time.sleep(1)
        # 천천히 전송
        prompt_input.send_keys(clean_prompt)
        
        time.sleep(1)
        send_btn = None
        try:
            send_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send'], button[aria-label*='보내기']")
            send_btn.click()
        except:
            from selenium.webdriver.common.keys import Keys
            prompt_input.send_keys(Keys.ENTER)
            
        print("  [AI 답변 대기 중... (15초)]")
        time.sleep(15) 
        
        responses = driver.find_elements(By.CSS_SELECTOR, ".model-response-text, .message-content, .markdown")
        if not responses:
            print("  [오류] AI 답변을 읽어오지 못했습니다. (응답 지연)")
            return None, None, False
            
        last_response = responses[-1].text
        print(f"\n[Gemini Web AI 답변]\n{last_response}\n" + "-"*30)
        
        # 답변 파싱
        artist, title, is_jp = "Unknown Artist", track_title, False
        match_artist = re.search(r'가수[:\s]+(.+?)(?=/|제목|$)', last_response)
        match_title = re.search(r'제목[:\s]+(.+?)(?=/|일본|$)', last_response)
        match_jp = re.search(r'일본노래여부[:\s]+(네|예|True|true)', last_response)
        
        if match_artist: artist = match_artist.group(1).strip()
        if match_title: title = match_title.group(1).strip()
        if match_jp: is_jp = True
        
        return artist, title, is_jp
        
    except Exception as e:
        print(f"  [Gemini Web 오류] {e}")
        return None, None, False
    finally:
        if driver:
            try: driver.quit()
            except: pass

def get_metadata_from_gemini(url, video_title, track_title, full_description):
    """Gemini AI(google-genai)를 사용하여 영상의 가수와 제목을 추론합니다."""
    # 1. 먼저 사용자에게 무엇을 물어보려 하는지 로그 출력 (필수 요청사항)
    print("\n" + "="*50)
    print("[AI에게 보낼 질문(Prompt) 요약]")
    print(f"URL: {url}")
    print(f"영상 제목: {video_title}")
    print(f"분석 대상(트랙): {track_title}")
    print("="*50)

    # 2. API 키가 없으면 Gemini 웹 UI로 진행 시도
    if not GEMINI_API_KEY:
        print("[알림] Gemini API Key가 없어 Gemini 웹 사이트 분석을 시도합니다.")
        # 유튜브 기본 정보를 먼저 가져와서 Gemini에게 전달
        br_channel, br_video_title, br_desc = get_metadata_from_browser(url)
        
        # 웹 UI 연동 함수 호출
        ai_artist, ai_title, is_jp = get_metadata_from_gemini_web(track_title, video_title or br_video_title, br_desc)
        
        if ai_artist and ai_title:
            print("\n[Gemini 웹 분석 결과 성공]")
            print(f"가수명(후보): {ai_artist} / 제목: {ai_title}")
            print("-" * 50)
            return ai_artist, ai_title, is_jp
            
        print("\n[알림] Gemini 웹 분석 실패. 유튜브 기본 정보로 대체합니다.")
        return br_channel, br_video_title, False
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        유튜브 영상 정보를 분석해서 해당 트랙의 정확한 가수 이름과 노래 제목을 추출해줘.
        
        [중요 지침]
        1. 영상 설명란(Description)에 포함된 타임스탬프(01:23 등)와 트랙 리스트를 꼼꼼히 대조해봐.
        2. 영상 제목과 전체 설명의 맥락을 보고, 노래가 하나라면 그 곡의 정보를, 여러 곡이 섞인 모음곡(Medley)이라면 아래 '분석 대상 트랙'에 맞는 정보를 찾아줘.
        
        [분석 데이터]
        - 분석 대상 트랙 제목: {track_title}
        - 영상 전체 제목: {video_title}
        - 영상 URL: {url}
        - 영상 전체 설명(챕터 정보 포함): 
        ---
        {full_description}
        ---
        
        결과는 반드시 JSON 형식으로만 답해줘. 예: {{"artist": "가수명", "title": "곡제목", "is_japanese": false}}
        * 주의: 일본 노래(엔카 등)이거나 제목/가수에 일본어가 포함되어 있다면 "is_japanese"를 true로 설정해줘.
        만약 절대 알 수 없다면 {{"artist": "Unknown Artist", "title": "Unknown Title", "is_japanese": false}} 로 답해줘.
        """
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        data = response.parsed
        if not data:
             import json
             match = re.search(r'\{.*\}', response.text, re.DOTALL)
             if match:
                 data = json.loads(match.group())
        
        if data:
            print("\n[AI로부터 받은 답변]")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            print("-"*50)
            return data.get('artist'), data.get('title'), data.get('is_japanese', False)
            
    except Exception as e:
        print(f"\n[AI 오류] Gemini 추론 실패: {e}")
        br_chan, br_vtit, br_d = get_metadata_from_browser(url)
        return br_chan, br_vtit, False
    
    return None, None, False

def parse_track_info(title_str, url=None, video_title=None, description=None):
    """'가수 - 곡제목' 형식에서 가수와 제목을 분리하고 메타데이터 및 AI로 보정합니다."""
    # 불필요한 앞부분 숫자나 기호 제거
    title_str = re.sub(r'^[\s\-\(\)\d\.]+', '', title_str).strip()
    
    # 전각 대시(–)와 일반 대시(-) 처리
    delimiters = [r'\s*-\s*', r'\s*–\s*', r'\s*:\s*', r'\s*~\s*']
    pattern = '|'.join(delimiters)
    parts = re.split(pattern, title_str, maxsplit=1)
    
    artist = "Unknown Artist"
    title = title_str.strip()
    is_japanese = False

    # [캐시 체크] URL과 제목 조합으로 캐시 키 생성 (모음곡 대응)
    cache_key = (url, title_str)
    if url and cache_key in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE[cache_key]

    if len(parts) == 2:
        artist = parts[0].strip()
        title = parts[1].strip()
    
    # 0. 물리적 일본어 필터링 (히라가나/가타카나)
    if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', title_str):
        is_japanese = True
        print(f"  [필터링] 일본어 감지: {title_str}")

    # 1. metadata.json에서 검색 (제목으로 아티스트 찾기)
    if (artist == "Unknown Artist" or artist.lower() in ["가수", "임시", "가요"]) and not is_japanese:
        clean_title = re.sub(r'[\s\(\)]', '', title)
        for key, val in METADATA.items():
            if clean_title == re.sub(r'[\s\(\)]', '', key):
                artist = val
                break
    
    # 2. AI(Gemini)/브라우저 폴백: 여전히 Unknown Artist인 경우
    if (artist == "Unknown Artist" or "unknown" in artist.lower()) and url and not is_japanese:
        ai_artist, ai_title, is_jp = get_metadata_from_gemini(url, video_title, title_str, description)
        
        # [채널명 필터링] 가수가 채널명 스타일(모음, 트롯, 채널 등)이면 무시
        channel_keywords = ["K트롯", "트롯", "모음", "메들리", "TV", "티비", "뮤직", "Music", "Official", "채널"]
        if ai_artist and any(k in ai_artist for k in channel_keywords):
            print(f"  [주의] 채널성 이름 감지되어 가수 정보 제외: {ai_artist}")
            ai_artist = "Unknown Artist"

        if ai_artist and ai_artist != "Unknown Artist":
            artist = ai_artist
            # ai_title이 영상 설명일 수 있으므로, Unknown Title이 아닐 때만 업데이트
            if ai_title and "Unknown" not in ai_title and len(ai_title) < 50:
                title = ai_title
            is_japanese = is_jp
            if is_japanese:
                print(f"  [필터링] AI 판단 - 일본 노래: {artist} - {title}")
            
    # 결과 캐싱 (URL + 원본 제목 조합)
    if url:
        _ANALYSIS_CACHE[cache_key] = (artist, title, is_japanese)
            
    return artist, title, is_japanese

def parse_timestamps(description):
    """영상 설명에서 타임스탬프와 정보를 추출합니다."""
    timestamps = []
    # FutureWarning 방지를 위해 대괄호 이스케이프 수정
    time_pattern = re.compile(r'[\[({]?(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})[\])}]?\s*[-]?\s*(.+)')
    
    for line in description.split('\n'):
        # 라인 앞부분 (01) 등 제거
        line = re.sub(r'^\(\d+\)\s*', '', line).strip()
        
        match = time_pattern.search(line)
        if match:
            time_str = match.group(1)
            raw_title = match.group(2).strip()
            
            # 시간 변환
            parts = list(map(int, time_str.split(':')))
            if len(parts) == 2: seconds = parts[0] * 60 + parts[1]
            elif len(parts) == 3: seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            else: continue
            
            artist, title, is_jp = parse_track_info(raw_title)
            if is_jp:
                continue
            
            timestamps.append({
                'start_sec': seconds, 
                'time_str': time_str, 
                'artist': artist,
                'title': title,
                'raw_title': raw_title
            })
    
    return sorted(timestamps, key=lambda x: x['start_sec'])

def parse_chapters(info):
    """유튜브 챕터 정보를 트랙 정보로 변환합니다."""
    chapters = info.get('chapters')
    if not chapters:
        return []
    
    tracks = []
    for chap in chapters:
        start_time = chap.get('start_time', 0)
        raw_title = chap.get('title', 'Unknown Track')
        
        artist, title, is_jp = parse_track_info(raw_title)
        if is_jp:
            continue
            
        # 초 단위를 MM:SS 형식으로 변환
        mins, secs = divmod(int(start_time), 60)
        time_str = f"{mins:02d}:{secs:02d}"
        
        tracks.append({
            'start_sec': int(start_time),
            'time_str': time_str,
            'artist': artist,
            'title': title,
            'raw_title': raw_title
        })
    return tracks

def get_existing_indices():
    """현재 DATA_DIR에 존재하는 파일들의 인덱스 세트를 반환합니다."""
    if not os.path.exists(DATA_DIR):
        return set()
    
    indices = set()
    for f in os.listdir(DATA_DIR):
        if f.endswith('.mp3'):
            match = re.match(r'^(\d{4})\.', f)
            if match:
                indices.add(int(match.group(1)))
    return indices

def check_duplicate(artist, title):
    """가수와 제목이 일치하는 파일이 있는지 확인 (정밀화)."""
    if not os.path.exists(DATA_DIR):
        return False
    
    # 특수문자 및 공백 제거 후 비교
    norm = lambda s: re.sub(r'[^가-힣a-zA-Z0-9]', '', s).lower()
    search_norm = norm(f"{artist}{title}")
    
    for f in os.listdir(DATA_DIR):
        if f.endswith('.mp3'):
            # 파일명에서 인덱스 제거 후 비교
            clean_f = re.sub(r'^\d{4}\.\s*', '', f).replace('.mp3', '')
            if search_norm == norm(clean_f):
                return True
    return False

def clean_temp_files(pattern):
    """임시 파일 정리."""
    import shutil
    for f in os.listdir('.'):
        if f.startswith(pattern):
            try:
                if os.path.isfile(f):
                    os.remove(f)
                elif os.path.isdir(f):
                    shutil.rmtree(f)
            except:
                pass

def download_audio(url, video_id):
    """WinError 32 방지를 위해 nopart 옵션을 사용하여 다운로드."""
    temp_name = f"temp_{video_id}"
    output_path = f"{temp_name}.mp3"
    
    clean_temp_files(temp_name)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'progress_hooks': [progress_hook],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': temp_name,
        'nopart': True,  # .part 파일 생성 방지
        # FFmpeg 관련 설정 강화 (최초 설치된 초콜레티 경로 고정)
        'ffmpeg_location': r'C:\ProgramData\chocolatey\bin', 
        'prefer_ffmpeg': True,
        'quiet': False, # 에러 상세 확인
        'no_warnings': False,
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        if "Errno 28" in str(e) or "No space left" in str(e):
            print("\n" + "!"*60)
            print("[치명적 오류] 디스크 용량이 부족합니다 (Errno 28).")
            print("현재 C 드라이브 공간이 거의 없습니다 (약 100MB 미만).")
            print("불필요한 파일을 삭제하거나 다른 드라이브로 프로젝트를 옮겨주세요.")
            print("!"*60)
            sys.exit(1)
        raise e
    
    return output_path

def split_audio_ffmpeg(audio_file, tracks, limit=None, normalize=False):
    """트랙 분할 및 볼륨 평준화."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    existing_indices = get_existing_indices()
    if limit: tracks = tracks[:limit]
        
    total_to_process = len(tracks)
    processed_count = 0
    skipped_count = 0
    
    for i, track in enumerate(tracks):
        artist = track['artist']
        title = track['title']
        # start_sec가 없는 경우(단일곡) 0으로 처리
        start_sec = track.get('start_sec', 0)
        
        if check_duplicate(artist, title):
            print(f"\n[건너뜀] 이미 존재함: {artist} - {title}")
            skipped_count += 1
            continue
            
        # 가장 작은 빈 번호 찾기
        idx = 1
        while idx in existing_indices:
            idx += 1
            
        duration = None
        # 다음 트랙이 있고 start_sec 정보가 있는 경우에만 duration 계산
        if i + 1 < len(tracks) and 'start_sec' in tracks[i+1]:
            duration = tracks[i+1]['start_sec'] - start_sec
        
        clean_name = re.sub(r'[\\/*?:"<>|]', "", f"{artist} - {title}")
        filename = f"{idx:04d}. {clean_name}.mp3"
        filepath = os.path.join(DATA_DIR, filename)
        
        # ffmpeg 명령어 구성 (절대 경로 사용)
        ffmpeg_exe = r'C:\ProgramData\chocolatey\bin\ffmpeg.exe'
        cmd = [ffmpeg_exe, '-y']
        # 단일 곡이 아니고 분할이 필요한 경우에만 -ss 적용
        if len(tracks) > 1 or start_sec > 0:
            cmd += ['-ss', str(start_sec)]
        
        cmd += ['-i', audio_file]
        
        if duration: 
            cmd += ['-t', str(duration)]
            
        if normalize:
            cmd += [
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', 
                '-c:a', 'libmp3lame', 
                '-b:a', '192k'
            ]
        else:
            cmd += ['-acodec', 'copy']
            
        cmd += [
            '-metadata', f"title={title}",
            '-metadata', f"artist={artist}",
            '-metadata', f"track={idx}",
            filepath
        ]
        
        norm_status = "(볼륨 평준화 중...)" if normalize else ""
        sys.stdout.write(f"\r진행 중... [{i+1}/{total_to_process}] {filename} {norm_status}          ")
        sys.stdout.flush()
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        existing_indices.add(idx)
        processed_count += 1
        
    print(f"\n작업 완료: {processed_count}곡 저장, {skipped_count}곡 중복 제외.")

def process_single_video(url, info, normalize=True):
    """개별 영상을 분석하여 다운로드 및 (필요시) 분할 처리를 수행합니다."""
    video_id = info.get('id', 'default')
    description = info.get('description', '')
    video_title = info.get('title', 'Unknown Title')
    duration = info.get('duration', 0)
    
    # 1. 트랙 분석 시도 (설명란 또는 챕터)
    tracks = parse_timestamps(description)
    if not tracks:
        tracks = parse_chapters(info)
    
    # [특수 케이스] 영상이 5분 이상인데 분할 정보가 없는 경우 스킵
    if not tracks and duration > 300:
        print(f"\n[건너뜀] 5분 이상 영상이나 분할 정보 없음: {video_title} ({duration}초)")
        return

    # 2. 분석 결과가 없으면 단일 트랙으로 간주하고 제목에서 메타데이터 추출
    if not tracks:
        artist, title, is_jp = parse_track_info(video_title, url=url, video_title=video_title, description=description)
        if is_jp:
            print(f"\n[건너뜀] 일본 노래로 판명됨: {artist} - {title}")
            return
            
        tracks = [{
            'artist': artist,
            'title': title,
            'raw_title': video_title
        }]
    else:
        # 발견된 트랙들에 대해서도 Unknown Artist 보정 시도 및 일본어 필터링
        filtered_tracks = []
        for t in tracks:
            if t['artist'] == "Unknown Artist":
                a, tit, is_jp = parse_track_info(t['raw_title'], url=url, video_title=video_title, description=description)
                if is_jp:
                    continue
                t['artist'], t['title'] = a, tit
            filtered_tracks.append(t)
        tracks = filtered_tracks
        
    if not tracks:
        print(f"\n[알림] 처리할 유효한 트랙이 없습니다 (필터링됨).")
        return

    print(f"\n- 처리 대상: {video_title}")
    if len(tracks) > 1:
        print(f"  ({len(tracks)}개의 트랙이 발견되었습니다.)")
    else:
        print(f"  (단일 곡으로 처리: {tracks[0]['artist']} - {tracks[0]['title']})")

    audio_file = f"temp_{video_id}.mp3"
    try:
        download_audio(url, video_id)
        split_audio_ffmpeg(audio_file, tracks, normalize=normalize)
    except Exception as e:
        print(f"\n[오류] {video_title} 처리 중 에러 발생: {e}")
    finally:
        clean_temp_files(f"temp_{video_id}")

def main():
    print("="*60)
    print(" 유튜브 MP3 추출기 (재생목록 & 메타데이터 보정 지원) ")
    print("="*60)
    
    input_url = input("유튜브 URL(영상 또는 재생목록)을 입력하세요: ").strip()
    if not input_url: return

    print("\n정보를 가져오는 중...")
    try:
        # 단일 영상 정보와 재생목록 정보를 모두 확인하기 위해 
        # 처음에는 일반 정보로 시도 (재생목록이라면 _type='playlist' 반환됨)
        info = get_video_info(input_url)
    except Exception as e:
        print(f"\n[오류] 정보를 가져올 수 없습니다: {e}")
        return

    # 재생목록 여부 확인
    if '_type' in info and info['_type'] == 'playlist':
        title = info.get('title', '알 수 없는 재생목록')
        entries = info.get('entries', [])
        
        # 실제 비디오 항목만 필터링 (None이거나 _type이 'url'이 아닌 경우 제외)
        # 'url' 타입은 실제 비디오를 가리키는 경우가 많음.
        # 'youtube#video' 같은 타입도 있을 수 있으나, yt-dlp는 보통 'url'로 통일
        filtered_entries = [
            entry for entry in entries 
            if entry and entry.get('_type') == 'url' and entry.get('id')
        ]
        
        # 필터링된 entries로 업데이트
        entries = filtered_entries
        total = len(entries)
        
        is_mix = "RD" in input_url or "RD" in info.get('id', '')
        
        if is_mix:
            print("\n[주의] 입력하신 주소는 '유튜브 믹스(RD)'입니다.")
            print("이 목록은 유튜브 알고리즘이 생성한 '관련 영상'들의 모음으로,")
            print("원래 플레이리스트가 아니므로 예상치 못한 곡들이 많이 포함될 수 있습니다.")
        
        mix_warning = " (유튜브 믹스는 관련 영상이 수천 개 포함될 수 있습니다.)" if is_mix else ""
        
        print(f"\n[재생목록 발견] 제목: {title}")
        print(f"총 {total}개의 영상이 포함되어 있습니다.{mix_warning}")
        
        print("\n원하는 작업을 선택하세요:")
        print("1. 이 주소의 '단일 영상'만 추출 (첫 번째 곡)")
        print("2. 재생목록 '전체' 추출 (대량 작업)")
        print("3. 재생목록 '상위 10곡만' 테스트 추출")
        print("Q. 종료")
        
        choice = input("\n선택 (1/2/3/Q): ").strip().lower()
        
        if choice == '1':
            first_entry = entries[0] if entries else None
            video_url = input_url # 원본 URL 사용
            if first_entry:
                video_url = first_entry.get('url') or f"https://www.youtube.com/watch?v={first_entry.get('id')}"
            
            print(f"\n[단일 곡 모드] 첫 번째 영상을 분석합니다...")
            detailed_info = get_video_info(video_url)
            process_single_video(video_url, detailed_info)
            
        elif choice in ['2', '3']:
            limit = 10 if choice == '3' else None
            msg = f"상위 {limit}개" if limit else f"전체 {total}개"
            confirm = input(f"정말로 {msg} 영상을 다운로드하시겠습니까? (y/n): ").strip().lower()
            if confirm != 'y': return
            
            target_entries = entries[:limit] if limit else entries
            for i, entry in enumerate(target_entries):
                if not entry: continue
                
                video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                print(f"\n" + "-"*40)
                print(f"[{i+1}/{len(target_entries)}] 작업 진행 중...")
                
                try:
                    detailed_info = get_video_info(video_url)
                    process_single_video(video_url, detailed_info)
                except Exception as e:
                    print(f"  [건너뜜] {e}")
        else:
            print("작업을 취소합니다.")
            return
    else:
        # 단일 영상
        process_single_video(input_url, info)

    print(f"\n" + "="*60)
    print(f"[최종 성공] 모든 작업이 종료되었습니다. '{DATA_DIR}' 폴더를 확인하세요.")
    print("="*60)

if __name__ == "__main__":
    main()

