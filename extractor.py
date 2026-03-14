import os
import re
import sys
import time
import json
import socket
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

# .env 파일 로드 (__file__ 기준 절대 경로로 고정하여 실행 위치 무관)
_DOTENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
print("============================")
print("[디버깅] ENV path:", _DOTENV_PATH)
print("============================")

load_dotenv(dotenv_path=_DOTENV_PATH, override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY == "your_api_key_here":
    GEMINI_API_KEY = None

# Gemini 브라우저 설정
GEMINI_BROWSER_PROFILE = os.path.join(os.path.dirname(__file__), ".gemini_profile")
CHROME_USER_DATA = os.getenv("CHROME_USER_DATA") # 사용자 개인 크롬 데이터 경로 (선택)
CHROME_PROFILE = os.getenv("CHROME_PROFILE", "Default") # 사용자 크롬 프로필 이름
CHROME_DEBUGGING_PORT = os.getenv("CHROME_DEBUGGING_PORT") # 이미 실행 중인 크롬 포트 (예: 9222)
GEMINI_CHAT_URL = os.getenv("GEMINI_CHAT_URL", "https://gemini.google.com/app") # 고정 사용할 Gemini 채팅 URL

# 디버깅용 출력 (환경 변수 확인)
print("[디버깅] CHROME_DEBUGGING_PORT:", CHROME_DEBUGGING_PORT)
print("[디버깅] CHROME_USER_DATA:", CHROME_USER_DATA)
print("[디버깅] CHROME_PROFILE:", CHROME_PROFILE)
print("[디버깅] GEMINI_CHAT_URL:", GEMINI_CHAT_URL)

if not CHROME_USER_DATA and not os.path.exists(GEMINI_BROWSER_PROFILE):
    os.makedirs(GEMINI_BROWSER_PROFILE)

# Gemini API Key 로드 확인 (google-genai SDK는 Client 인스턴스에서 API 키를 직접 사용하므로 configure가 필요 없음)
if GEMINI_API_KEY:
    print("[알림] GEMINI_API_KEY가 설정되었습니다.")

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
_SHARED_DRIVER = None # 모든 브라우저 작업을 위한 통합 드라이버

def load_singer_list():
    """singer.txt 파일에서 가수 목록을 로드합니다."""
    singer_path = os.path.join(os.path.dirname(__file__), 'singer.txt')
    singers = set()
    if os.path.exists(singer_path):
        try:
            with open(singer_path, 'r', encoding='utf-8') as f:
                for line in f:
                    name = line.strip()
                    if name:
                        singers.add(name)
        except Exception as e:
            print(f"[경고] singer.txt 로드 실패: {e}")
    return singers

_SINGER_LIST = load_singer_list()

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
        'playlist_items': '1:100',  # 플레이리스트라도 너무 많은 관련 영상 스크랩을 막기 위해 100개까지만 스크랩
        'compat_opts': ['no-youtube-related-video'], # 플레이리스트가 아닐 때 우측 관련영상이 딸려오는 것을 방지
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # 만약 entries가 있다면, 관련 영상(related_videos)이 섞이지 않도록 필터링
        if info and 'entries' in info:
            # 실제 비디오 ID가 있고, 광고나 추천 항목이 아닌 것만 남김
            info['entries'] = [e for e in info['entries'] if e and (e.get('url') or e.get('id'))]
        return info

def find_chrome_debug_port():
    """이미 실행 중인 크롬의 원격 디버깅 포트를 자동으로 찾습니다 (9222~9229 시도)."""
    for port in range(9222, 9230):
        try:
            import urllib.request
            req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
            if req.status == 200:
                print(f"  [자동 감지] 크롬 디버깅 포트 발견: {port}")
                return str(port)
        except:
            continue
    return None

def get_shared_driver():
    """모든 브라우저 작업을 위한 통합 드라이버를 가져오거나 생성합니다."""
    global _SHARED_DRIVER
    
    # 설정 다시 확인 (절대 경로로 .env 재로드)
    load_dotenv(dotenv_path=_DOTENV_PATH, override=True)
    dbg_port = os.getenv("CHROME_DEBUGGING_PORT", "").strip().strip('"').strip("'")
    if not dbg_port: dbg_port = None
    
    # .env에 포트가 없으면 실행 중인 크롬에서 자동 탐지
    if not dbg_port:
        dbg_port = find_chrome_debug_port()
        if dbg_port:
            print(f"  [알림] .env에 CHROME_DEBUGGING_PORT가 없어 자동 감지된 포트({dbg_port})를 사용합니다.")
    
    user_data = os.getenv("CHROME_USER_DATA")
    if not user_data:
        # 사용자가 이미 띄워둔 크롬을 쓸 수 없을 때는, 충돌(Crash) 방지를 위해 격리된 임시 프로필 사용
        user_data = GEMINI_BROWSER_PROFILE
    
    profile_name = os.getenv("CHROME_PROFILE", "Default")
    
    if _SHARED_DRIVER:
        try:
            _ = _SHARED_DRIVER.current_url
            return _SHARED_DRIVER
        except:
            _SHARED_DRIVER = None
            
    print(f"\n[디버깅 정보] CHROME_DEBUGGING_PORT: {dbg_port or '미설정(None)'}")
    
    chrome_options = Options()
    
    # 원격 디버깅 접속 (사용자가 이미 띄워둔 크롬 사용)
    if dbg_port:
        print(f"  [브라우저 연동] 원격 디버깅 포트 {dbg_port}에 연결을 시도합니다...")
        chrome_options.debugger_address = f"127.0.0.1:{dbg_port}"
        # 원격 접속 시에는 신규 실행 관련 옵션들이 무시됩니다
    else:
        print(f"  [브라우저 실행] 독립된 프로필({profile_name})을 사용하여 브라우저를 실행합니다.")
        chrome_options.add_argument(f"--user-data-dir={user_data}")
        chrome_options.add_argument(f"--profile-directory={profile_name}")

    # 추가 공통 옵션
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 접속 성공 확인 및 로그
        if dbg_port:
            print(f"  [성공] 기존에 열려있던 크롬 브라우저와 연동되었습니다!")
        else:
            # 신규 실행 시에만 봇 감지 우회 스크립트 적용
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
        _SHARED_DRIVER = driver
        return _SHARED_DRIVER
    except Exception as e:
        print(f"\n[오류] 브라우저 연결 실패: {e}")
        if "DevToolsActivePort" in str(e) or "already in use" in str(e).lower() or "crashed" in str(e):
            print("-" * 60)
            print("❗ [중요] 기존에 열려있는 구글 크롬 창을 모두 닫은 후 다시 실행해주세요!")
            print("   (또는 크롬을 원격 디버깅 포트로 실행해야만 기존 창과 함께 사용할 수 있습니다.)")
            print("-" * 60)
        elif dbg_port:
            print("-" * 60)
            print(f"원격 접속(포트 {dbg_port})에 실패했습니다.")
            print("해결 방법:")
            print(f"1. 크롬을 완전히 종료(모든 창 닫기)한 후, 반드시 아래 옵션을 붙여서 다시 실행해 주세요.")
            print(f"   옵션: --remote-debugging-port={dbg_port}")
            print(f"   실행 예시: chrome.exe --remote-debugging-port={dbg_port}")
            print(f"2. 또는 .env 파일에서 CHROME_DEBUGGING_PORT 설정을 지우고 다시 실행하세요.")
            print("-" * 60)
        return None

def get_metadata_from_browser(url):
    """브라우저를 사용하여 유튜브 영상의 제목과 채널명을 추출합니다."""
    if url in _BROWSER_CACHE:
        return _BROWSER_CACHE[url]
        
    print(f"\n[브라우저 로드 중...] {url}")
    driver = get_shared_driver()
    if not driver:
        return None, None, None
        
    video_title, channel_name, description = "Unknown Title", "Unknown Artist", ""
    
    try:
        # 이미 열린 창이 있다면 새 탭에서 열기 (속도 및 맥락 유지)
        if len(driver.window_handles) > 0:
            driver.execute_script(f"window.open('{url}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
        else:
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
        # 공유 드라이버이므로 quit() 하면 안 됨!
        # 대신 이 함수에서 연 유튜브 탭만 닫고 메인 탭으로 복귀합니다.
        if driver and len(driver.window_handles) > 1:
            try:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except: pass
    
    result = (channel_name, video_title, description[:500])
    _BROWSER_CACHE[url] = result
    return result

def get_metadata_from_gemini_web(url, track_title, video_title, full_description):
    """gemini.google.com 웹 UI에 직접 질문하여 가수와 제목을 알아냅니다."""
    print(f"\n[Gemini Web AI 접속 중...] {track_title}")
    
    driver = get_shared_driver()
    if not driver:
        return None, None, False

    try:
        # 1. 지정된 Gemini 채팅 탭 선정 (해당 URL이 이미 열리면 전환, 없으면 새탭 오픈)
        target_url = GEMINI_CHAT_URL  # .env에 설정한 URL (예: 고정 채팅방)
        gemini_tab = None
        
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            if "gemini.google.com" in driver.current_url:
                gemini_tab = handle
                break
                
        if not gemini_tab:
            # Gemini 탭이 없으니 새 탭으로 여는데, target_url이 특정 채팅이면 바로 채팅으로 접속
            driver.execute_script(f"window.open('{target_url}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
        else:
            # 이미 Gemini 탭이 있는데, 지정된 URL이 다른 채팅이면 해당 채팅으로 이동
            if target_url not in driver.current_url:
                driver.get(target_url)
                time.sleep(2)
        
        wait = WebDriverWait(driver, 25)
        
        # [중요 변경] 이전 질문에 대한 답변이 아직 진행 중인지 확인 (응답 중지 버튼 유무로 판단)
        try:
            # 응답 생성 중일 때 나타나는 '응답 중지(Stop)' 버튼 등 대기
            stop_btn_selectors = [
                 "button[aria-label*='Stop generating']",
                 "button[aria-label*='응답 중지']",
                 "button[aria-label*='중지']"
            ]
            for s_sel in stop_btn_selectors:
                elems = driver.find_elements(By.CSS_SELECTOR, s_sel)
                if elems and elems[0].is_displayed():
                    print("  [알림] 이전 질문이 아직 답변 중입니다. 완료될 때까지 잠시 대기합니다...")
                    time.sleep(5)
                    break
        except: pass
        
        # 2. 로그인 여부 확인 및 대기
        try:
            login_buttons = driver.find_elements(By.XPATH, "//span[contains(text(),'로그인') or contains(text(),'Sign in')]")
            if login_buttons:
                print("\n" + "!"*60)
                print("[중요] Gemini 웹사이트에 로그인이 필요합니다.")
                print("브라우저 창에서 구글 계정으로 로그인을 시도해 주세요.")
                print("!"*60)
                wait_long = WebDriverWait(driver, 600)
                wait_long.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true']")))
                print("\n[성공] 로그인이 확인되었습니다.")
                time.sleep(2)
        except: pass

        # 3. 입력창 찾기
        input_selectors = [
            "div[contenteditable='true']",
            "rich-textarea .ql-editor",
            "textarea[aria-label*='Prompt']",
            "rich-textarea div[role='textbox']"
        ]
        prompt_input = None
        for sel in input_selectors:
            try:
                prompt_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                if prompt_input and prompt_input.is_displayed(): break
            except: continue
            
        if not prompt_input:
            print("  [오류] 입력창을 찾을 수 없습니다. (페이지 응답 없음)")
            return None, None, False
            
        raw_prompt = f"""당신은 전문 음악 분석가입니다. 아래 제공된 [데이터 정보]를 바탕으로, 지목된 '대상 트랙'의 정확한 [가수]와 [노래 제목]을 추출하세요. 답변은 가수: [가수명] / 제목: [공제목] / 일본노래여부: [네/아니오] 형식으로만 해주세요. [데이터 정보] - 유튜브 URL: {url} - 영상 제목: {video_title} - 대상 트랙 제목(원본): {track_title} - 영상 전체 설명: {full_description[:1000]}"""
        
        clean_prompt = "".join(c if ord(c) <= 0xFFFF else "" for c in raw_prompt)
        # 줄바꿈(\n) 입력 시 자동 전송(Enter)되는 것을 막기 위해 모든 텍스트를 한 줄 공백으로 처리
        clean_prompt = clean_prompt.replace('\n', ' ')
        clean_prompt = " ".join(clean_prompt.split())
        
        # 5. 텍스트 주입 (클립보드 방식이나 send_keys 방식으로 최신 버전 대응)
        prompt_input.click()
        time.sleep(0.5)
        
        from selenium.webdriver.common.keys import Keys
        try:
            # pyperclip이 설치되어 있다면 클립보드를 통한 고속 입력 시도
            import pyperclip
            pyperclip.copy(clean_prompt)
            prompt_input.send_keys(Keys.CONTROL, 'v')
        except ImportError:
            # pyperclip이 없으면 직접 SendKeys로 타이핑
            prompt_input.send_keys(clean_prompt)
        
        # 만약 입력이 누락되었을 경우를 대비해 마지막엔 공백 하나 추가
        prompt_input.send_keys(" ")
        
        time.sleep(1.5)
        
        # 6. 전송 실행
        try:
            send_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send'], button[aria-label*='전송'], button[aria-label*='보내기']")
            send_btn.click()
        except:
            prompt_input.send_keys(Keys.ENTER)
            
        print("  [AI 답변 대기 중... (최대 35초)]")
        # 답변이 완성될 때까지 충분히 대기
        time.sleep(7) 
        
        # [중요 추가] 응답이 완전히 끝날 때까지 대기
        wait_for_stop = 0
        while wait_for_stop < 15:
            is_generating = False
            for s_sel in ["button[aria-label*='Stop generating']", "button[aria-label*='응답 중지']", "button[aria-label*='중지']"]:
                try:
                    btns = driver.find_elements(By.CSS_SELECTOR, s_sel)
                    if btns and btns[0].is_displayed():
                        is_generating = True
                        break
                except: pass
                
            if not is_generating:
                break
                
            time.sleep(2)
            wait_for_stop += 1
            
        time.sleep(2) # 렌더링 안정화 기다림
        
        # 7. 답변 읽기 (최신 Gemini UI 셀렉터)
        response_selectors = [
            "model-response .markdown",
            "[data-chunk-index] p",
            ".response-content p",
            "message-content p",
            ".model-response-text p",
        ]
        last_response = ""
        for rsel in response_selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, rsel)
            if elems:
                last_response = elems[-1].text
                break
                
        if not last_response:
            print("  [오류] AI 답변을 읽어오지 못했습니다. (시간 초과 가능성)")
            return None, None, False
            
        print(f"\n[Gemini Web AI 답변]\n{last_response}\n" + "-"*30)
        
        # 8. 답변 파싱
        artist, title, is_jp = "Unknown Artist", track_title, False
        match_artist = re.search(r'가수\s*:\s*(.+?)(?:\s*/|$)', last_response, re.MULTILINE)
        match_title = re.search(r'제목\s*:\s*(.+?)(?:\s*/|$)', last_response, re.MULTILINE)
        match_jp = re.search(r'일본노래여부\s*:\s*(네|예|True|true)', last_response)
        
        if match_artist: artist = match_artist.group(1).strip()
        if match_title: title = match_title.group(1).strip()
        if match_jp: is_jp = True
        
        return artist, title, is_jp
        
    except Exception as e:
        print(f"  [Gemini Web 오류] {e}")
        global _SHARED_DRIVER
        try:
            dbg = os.getenv("CHROME_DEBUGGING_PORT", "").strip()
            if not dbg:
                driver.quit()
        except: pass
        _SHARED_DRIVER = None
        return None, None, False

def get_tracklist_from_gemini_web(thumbnail_url, video_title):
    """Gemini Web을 통해 썸네일 이미지에서 트랙 리스트를 추출합니다."""
    print(f"\n[썸네일 분석 중...] Gemini Web을 통해 트랙 리스트를 추출합니다.")
    
    driver = get_shared_driver()
    if not driver:
        return []

    try:
        # Gemini 탭 확보 (없으면 생성)
        target_url = GEMINI_CHAT_URL
        gemini_tab = None
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            if "gemini.google.com" in driver.current_url:
                gemini_tab = handle
                break
        if not gemini_tab:
            driver.execute_script(f"window.open('{target_url}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
        
        wait = WebDriverWait(driver, 25)
        
        # 입력창 찾기 (이미 답변 중이면 대기)
        try:
            for s_sel in ["button[aria-label*='Stop']", "button[aria-label*='중지']"]:
                btns = driver.find_elements(By.CSS_SELECTOR, s_sel)
                if btns and btns[0].is_displayed():
                    time.sleep(5)
                    break
        except: pass

        input_selectors = ["div[contenteditable='true']", "rich-textarea .ql-editor"]
        prompt_input = None
        for sel in input_selectors:
            try:
                prompt_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                if prompt_input and prompt_input.is_displayed(): break
            except: continue
            
        if not prompt_input:
            print("  [오류] Gemini 입력창을 찾을 수 없습니다.")
            return []
            
        # 프롬프트 구성 (썸네일 URL 포함)
        prompt = f"다음 주소의 유튜브 썸네일 [ {thumbnail_url} 이미지 속에 적힌 글자만(OCR 방식) 읽어줘] 트렉 목록을 추출해줘. (비디오 제목: {video_title}) 결과는 반드시 01. 가수 - 제목 [시작타임 ~ 종료타임] 형식으로 리스트만 알려줘."
        # ChromeDriver에서 이모지(Non-BMP)를 보내면 오류가 나므로 필터링
        prompt = "".join(c if ord(c) <= 0xFFFF else "" for c in prompt)
        
        prompt_input.click()
        time.sleep(0.5)
        
        from selenium.webdriver.common.keys import Keys
        try:
            import pyperclip
            pyperclip.copy(prompt)
            prompt_input.send_keys(Keys.CONTROL, 'v')
        except:
            prompt_input.send_keys(prompt)
        
        prompt_input.send_keys(" ")
        time.sleep(1)
        
        try:
            send_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send'], button[aria-label*='전송']")
            send_btn.click()
        except:
            prompt_input.send_keys(Keys.ENTER)
            
        print("  [AI 답변 대기 중...]")
        time.sleep(10)
        
        # 응답 완료 대기
        for _ in range(15):
            is_generating = False
            for s_sel in ["button[aria-label*='Stop']", "button[aria-label*='중지']"]:
                btns = driver.find_elements(By.CSS_SELECTOR, s_sel)
                if btns and btns[0].is_displayed():
                    is_generating = True
                    break
            if not is_generating: break
            time.sleep(2)

        # 결과 읽기
        response_selectors = ["model-response .markdown", "[data-chunk-index] p", ".response-content p"]
        last_response = ""
        for rsel in response_selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, rsel)
            if elems:
                last_response = elems[-1].text
                break
        
        if not last_response:
            return []
            
        print(f"\n[Gemini 썸네일 분석 답변]\n{last_response}\n" + "-"*30)
        
        tracks = []
        lines = last_response.split('\n')
        for line in lines:
            line = line.strip()
            if re.match(r'^\d+[\.\)\s]', line) or '-' in line:
                artist, title, is_jp = parse_track_info(line)
                if not is_jp and title != line:
                    track_data = {'artist': artist, 'title': title, 'raw_title': line}
                    # [추가] 시작타임 추출 시도 [01:23] 또는 [01:23:45] 형식
                    time_match = re.search(r'\[\s*(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})', line)
                    if time_match:
                        s_time = time_match.group(1)
                        pts = list(map(int, s_time.split(':')))
                        if len(pts) == 2: track_data['start_sec'] = pts[0]*60 + pts[1]
                        elif len(pts) == 3: track_data['start_sec'] = pts[0]*3600 + pts[1]*60 + pts[2]
                        
                    tracks.append(track_data)
        
        return tracks
        
    except Exception as e:
        print(f"  [썸네일 분석 오류] {e}")
        return []

def close_shared_driver():
    """사용이 끝난 통합 드라이버를 정리합니다."""
    global _SHARED_DRIVER
    if _SHARED_DRIVER:
        try:
            # 원격 디버깅 모드일 때는 창을 닫지 않고 연결만 끊음 (사용자 편의)
            if not os.getenv("CHROME_DEBUGGING_PORT"):
                _SHARED_DRIVER.quit()
                print("\n[알림] Gemini 브라우저를 종료했습니다.")
        except: pass
        _SHARED_DRIVER = None

def get_metadata_from_gemini(url, video_title, track_title, full_description):
    """Gemini AI(google-genai)를 사용하여 영상의 가수와 제목을 추론합니다."""
    # 1. 먼저 사용자에게 무엇을 물어보려 하는지 로그 출력
    print("\n" + "="*50)
    print("[AI에게 보낼 질문(Prompt) 요약]")
    print(f"URL: {url}")
    print(f"영상 제목: {video_title}")
    print(f"분석 대상(트랙): {track_title}")
    print("="*50)

    # 2. 우선적으로 Gemini 웹 사이트 분석 시도 (로그인된 세션 활용 목적)
    print("[알림] 로그인된 크롬 브라우저를 통하여 Gemini 웹 추론을 우선 시도합니다.")
    
    br_channel, br_video_title, br_desc = get_metadata_from_browser(url)
    
    # 웹 UI 연동 함수 호출 (추출된 브라우저 정보 사용)
    ai_artist, ai_title, is_jp = get_metadata_from_gemini_web(url, track_title, video_title or br_video_title, br_desc)
    
    if ai_artist and ai_title:
        print("\n[Gemini 웹 분석 결과 성공]")
        print(f"가수명(후보): {ai_artist} / 제목: {ai_title}")
        print("-" * 50)
        return ai_artist, ai_title, is_jp
        
    print("\n[알림] Gemini 웹 분석에 실패했습니다.")
    
    # 3. 실패 시, 설정된 GEMINI_API_KEY가 있다면 API (google-genai) 로 시도
    if not GEMINI_API_KEY:
        print("[알림] Gemini API Key가 설정되어 있지 않아 유튜브 기본 정보로 대체합니다.")
        return br_channel, br_video_title, False
        
    print("[알림] GEMINI_API_KEY가 존재하므로 백그라운드 API 분석을 시도합니다.")
        
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

def parse_track_info(title_str, url=None, video_title=None, description=None, playlist_title=None, context_artist=None):
    """
    제목 문자열(title_str)에서 가수와 곡 제목을 분리하고, 일본 노래인지 감지합니다.
    분리가 안 되거나 결과가 'Unknown Artist'일 경우 Gemini를 사용하여 분석합니다.
    """
    # 0. 가장 먼저, 인자로 받은 context_artist가 있다면 사용. 없으면 유추 시도.
    artist = "Unknown Artist"
    if context_artist and context_artist != "Unknown Artist":
        artist = context_artist
    else:
        # 가수를 유추할 수 있는 키워드들
        ctx_title = playlist_title if playlist_title else video_title
        if ctx_title:
            ctx_keywords = ["노래 모음", "노래모음", "히트곡", "메들리", "플레이리스트", "Playlist", "콘서트", "공연", "전집"]
            clean_ctx = re.sub(r'[◈\[\]\(\)\-\d]', ' ', ctx_title).strip()
            for keyword in ctx_keywords:
                if keyword.lower() in clean_ctx.lower():
                    parts = re.split(re.escape(keyword), clean_ctx, flags=re.IGNORECASE)
                    if parts and parts[0].strip():
                        potential_artist = parts[0].strip()
                        if 2 <= len(potential_artist) <= 8:
                            artist = potential_artist
                            break
    
    # 불필요한 앞부분 숫자나 기호 제거
    title_str = re.sub(r'^[\s\-\(\)\d\.]+', '', title_str).strip()
    
    # 전각 대시(–)와 일반 대시(-), 그리고 슬래시(/) 등 처리
    delimiters = [r'\s*-\s*', r'\s*–\s*', r'\s*:\s*', r'\s*~\s*', r'\s*/\s*']
    pattern = '|'.join(delimiters)
    parts = re.split(pattern, title_str, maxsplit=1)
    
    title = title_str.strip()
    is_japanese = False

    # [캐시 체크] URL과 제목 조합으로 캐시 키 생성 (모음곡 대응)
    cache_key = (url, title_str)
    if url and cache_key in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE[cache_key]

    if len(parts) == 2:
        # 기존 artist가 Unknown Artist인 경우에만 업데이트
        if artist == "Unknown Artist":
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
    # [최적화] 이미 singer.txt에 있는 가수(컬렉션)라면 AI 호출 생략
    if (artist == "Unknown Artist" or "unknown" in artist.lower()) and url and not is_japanese:
        # 이미 context로 명확한 가수를 알고 있는지 확인 (singer.txt 기반)
        if context_artist and context_artist in _SINGER_LIST:
            # AI 호출 생략하고 context_artist 사용
            artist = context_artist
            print(f"  [최적화] '{artist}'가 singer.txt에 존재하여 AI 분석을 건너뜁니다.")
        else:
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
            
    # [수정] 제목에서 모든 형태의 시간 정보(타임스탬프) 및 지저분한 기호 완벽 제거
    # 1. 시간 패턴 정의 (01:23, 01:23:45, 000000 등)
    t_pat = r'\d+(?::\d+){1,2}|\d{6,}'
    
    # 2. 괄호와 함께 묶인 시간/범위 우선 제거 (예: [ 00:00 ~ 01:23 ])
    title = re.sub(fr'[\[\(\{{]\s*{t_pat}(?:\s*[~-]\s*{t_pat})*\s*[\]\)\}}]', '', title).strip()
    
    # 3. 괄호 없는 시간/범위 제거 (예: 00:00 ~ 01:23)
    title = re.sub(fr'{t_pat}(?:\s*[~-]\s*{t_pat})*', '', title).strip()
    
    # 4. 남은 찌꺼기 기호들 제거 (대괄호, 물결, 대시, 슬래시 등)
    # 시간 제거 후 외롭게 남은 기호들을 공백으로 치환 후 strip
    title = re.sub(r'[\[\]\(\)\{{\}\~\=\|\/]', ' ', title).strip()
    
    # 5. 연속된 공백 및 앞뒤 잔여 부호 정리
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'^[-\s\.]+|[-\s\.]+$', '', title).strip()
            
    # 결과 캐싱 (URL + 원본 제목 조합)
    if url:
        _ANALYSIS_CACHE[cache_key] = (artist, title, is_japanese)
            
    return artist, title, is_japanese

def parse_timestamps(description, video_title=None, url=None, playlist_title=None):
    """영상 설명에서 타임스탬프와 정보를 추출합니다."""
    timestamps = []
    
    # 0. 본문 상단이나 제목에서 기본 가수 정보 유추 (컨텍스트 기반)
    context_artist = "Unknown Artist"
    # 본문 첫 3줄 정도 검사
    desc_sample = "\n".join(description.split('\n')[:3])
    if video_title: desc_sample = f"{video_title}\n{desc_sample}"
    
    # "가수명 노래모음", "가수명 플레이리스트" 등 패턴 찾기 (비탐욕적 매칭으로 정확도 향상)
    # 키워드 확장: 노래모음, 인기곡, 메들리, 플레이리스트, Playlist 등
    kw_re = r'(?:노래\s?모음|인기곡|연속\s?듣기|트롯|메들리|BEST|히트곡|플레이리스트|Playlist|콘서트|공연|전집)'
    m = re.search(fr'([가-힣\w\s]+?)\s*{kw_re}', desc_sample, re.I)
    if m:
        context_artist = m.group(1).strip()
        # "노래" 또는 "의" 가 가수 이름 끝에 붙는 오동작 방지
        context_artist = re.sub(r'\s*의$|\s*노래$', '', context_artist)
        print(f"  [컨텍스트] 유추된 가수: {context_artist}")

    # 시간 패턴 (01:23, 01:23:45 등)
    t_re = r'(\d{1,2}:?\d{2}:\d{2}|\d{1,2}:\d{2})'
    
    # 1. 앞에 시간 있는 경우: 00:00 제목
    re_front = re.compile(fr'^[\[\(]?{t_re}[\]\)]?[\s\-:/\.]+(.+)$')
    # 2. 뒤에 시간 있는 경우: 제목 00:00
    re_back = re.compile(fr'^(.+?)\s*[\[\(]?{t_re}[\]\)]?$', re.MULTILINE)
    
    for line in description.split('\n'):
        line = line.strip()
        if not line: continue
        
        # 번호 (01. 등) 제거 - 단, 뒤에 콜론(:)이 오면 타임스탬프이므로 제외
        line = re.sub(r'^\d+(?!\:)(?:[\.\)\s\-]+|$)', '', line).strip()
        
        # 패턴 1 (앞에 시간) 매칭 시도
        m_f = re_front.match(line)
        if m_f:
            time_str = m_f.group(1)
            raw_title = m_f.group(2).strip()
        else:
            # 패턴 2 (뒤에 시간) 매칭 시도
            m_b = re_back.search(line)
            if m_b:
                raw_title = m_b.group(1).strip()
                time_str = m_b.group(2)
            else:
                continue
            
        # 시간 변환
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 2: seconds = parts[0] * 60 + parts[1]
        elif len(parts) == 3: seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else: continue
        
        artist, title, is_jp = parse_track_info(raw_title, url=url, video_title=video_title, description=description, playlist_title=playlist_title, context_artist=context_artist)
        
        # [핵심 로직] 노래모음/플레이리스트 영상이라면 메인 가수를 강제로 적용 (우선순위 최고)
        if context_artist != "Unknown Artist":
            # 메인 가수가 있는데 트랙 가수가 다르거나 Unknown인 경우 메인 가수로 교체
            # 단, 제목(title)은 파싱된 그대로 유지하여 '송민도 - 나 하나의 사랑' 식으로 보존 가능하게 함
            if artist != context_artist:
                # 아티스트가 다르게 잡혔다면 제목 앞에 원래 아티스트 정보를 붙여줌 (정보 보존)
                if artist != "Unknown Artist":
                    title = f"{artist} - {title}"
            artist = context_artist
            
        if is_jp: continue
        
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

def parse_tracklist_without_time(description):
    """설명란에서 시간 정보 없이 번호가 매겨진 트랙 리스트를 추출합니다."""
    tracks = []
    # 매치: 줄 시작부분에 숫자 + 점/괄호/슬래시 + 공백 후 텍스트 (예: "01. 찔레꽃 - 백난아")
    pattern = re.compile(r'^\s*(?:\d{1,2}|\d{1,2}\/)[\.\)]\s+(.+)', re.MULTILINE)
    
    for match in pattern.finditer(description):
        raw_title = match.group(1).strip()
        artist, title, is_jp = parse_track_info(raw_title)
        if not is_jp:
            tracks.append({
                'artist': artist,
                'title': title,
                'raw_title': raw_title
            })
    return tracks

def detect_silences(audio_file):
    """ffmpeg를 사용하여 오디오 파일의 무음 구간(1.5초 이상, -30dB 이하)을 탐지합니다."""
    print(f"\n[무음 탐지] 오디오 파일을 스캔하여 곡 분할 지점을 찾고 있습니다... (시간이 소요될 수 있습니다)")
    ffmpeg_exe = r'C:\ProgramData\chocolatey\bin\ffmpeg.exe'
    
    # -i audio_file -af silencedetect=noise=-30dB:d=1.5 -f null -
    cmd = [
        ffmpeg_exe, '-i', audio_file, 
        '-af', 'silencedetect=noise=-30dB:d=1.5',
        '-f', 'null', '-'
    ]
    
    # 출력은 stderr로 나옵니다
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, errors='ignore')
    
    silences = []
    start_pattern = re.compile(r'silence_start:\s+([\d\.]+)')
    end_pattern = re.compile(r'silence_end:\s+([\d\.]+)')
    
    for line in result.stderr.split('\n'):
        rem_start = start_pattern.search(line)
        if rem_start:
            silences.append({'start': float(rem_start.group(1)), 'end': None})
            
        rem_end = end_pattern.search(line)
        if rem_end and silences:
            silences[-1]['end'] = float(rem_end.group(1))
            
    # 유효한(끝나는 시간이 있는) 무음 구간만 반환
    valid_silences = [s for s in silences if s['end'] is not None]
    
    def format_sec(sec):
        m, s = divmod(int(sec), 60)
        return f"{m:02d}:{s:02d}"

    print(f"  > 총 {len(valid_silences)}개의 무음 구간이 발견되었습니다.")
    for i, s in enumerate(valid_silences):
        duration = s['end'] - s['start']
        print(f"    [{i+1}] {format_sec(s['start'])} ~ {format_sec(s['end'])} (길이: {duration:.1f}초)")
    return valid_silences

def get_existing_indices():
    """현재 DATA_DIR에 존재하는 파일들의 인덱스 세트를 반환합니다 (가수별 하위 폴더 포함)."""
    if not os.path.exists(DATA_DIR):
        return set()
    
    indices = set()
    # 하위 폴더를 포함하여 모든 mp3 파일 검색
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.mp3'):
                match = re.match(r'^(\d{4})\.', f)
                if match:
                    indices.add(int(match.group(1)))
    return indices

def check_duplicate(artist, title):
    """가수와 제목이 일치하는 파일이 있는지 확인 (모든 하위 폴더 검색)."""
    if not os.path.exists(DATA_DIR):
        return False
    
    # 특수문자 및 공백 제거 후 비교
    norm = lambda s: re.sub(r'[^가-힣a-zA-Z0-9]', '', s).lower()
    search_norm = norm(f"{artist}{title}")
    
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
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
        
        # [수정] singer.txt에 있는 가수만 전용 폴더 생성, 없으면 data 폴더에 직접 저장
        safe_artist = re.sub(r'[\\/*?:"<>|]', "", artist)
        
        # 최신 singer.txt 로드 (작업 중간에 수정될 수 있으므로)
        singer_list = load_singer_list() 
        
        if safe_artist in singer_list:
            artist_dir = os.path.join(DATA_DIR, safe_artist)
            if not os.path.exists(artist_dir):
                os.makedirs(artist_dir)
            filepath = os.path.join(artist_dir, filename)
        else:
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
    print(f"[알림] 완료된 파일들은 상기 명시된 '{os.path.abspath(DATA_DIR)}' 폴더에서 확인하실 수 있습니다.")

def process_single_video(url, info, normalize=True):
    """개별 영상을 분석하여 다운로드 및 (필요시) 분할 처리를 수행합니다."""
    video_id = info.get('id', 'default')
    description = info.get('description', '')
    video_title = info.get('title', 'Unknown Title')
    duration = info.get('duration', 0)
    playlist_title = info.get('playlist_title')
    
    # 1. 트랙 분석 시도 (설명란 또는 챕터)
    tracks = parse_timestamps(description, video_title, url=url, playlist_title=playlist_title)
    if not tracks:
        tracks = parse_chapters(info)
        
    require_silence_detection = False
    
    # [특수 케이스] 분할 정보(타임스탬프)가 없는 경우
    if not tracks:
        # 시간은 없어도 번호가 매겨진 리스트(01. 제목 - 가수)가 있는지 확인
        list_tracks = parse_tracklist_without_time(description)
        if len(list_tracks) > 1:
            print(f"\n[알림] 시간 정보는 없으나 {len(list_tracks)}개의 곡 목록을 발견했습니다. 무음 구간 탐지로 분할을 시도합니다.")
            tracks = list_tracks
            require_silence_detection = True
        else:
            # [추가] 썸네일 분석 시도
            thumbnail_url = info.get('thumbnail')
            if thumbnail_url:
                print(f"\n[알림] 설명란에 정보가 없어 썸네일 이미지 분석을 시도합니다...")
                vision_tracks = get_tracklist_from_gemini_web(thumbnail_url, video_title)
                if len(vision_tracks) > 1:
                    print(f"  > 썸네일에서 {len(vision_tracks)}개의 트랙을 추출했습니다.")
                    tracks = vision_tracks
                    # 시간 정보가 하나라도 포함되어 있는지 확인
                    if any('start_sec' in t for t in tracks):
                        print(f"  [알림] 썸네일에 시간 정보가 포함되어 있어 무음 탐지를 건너뜁니다.")
                        require_silence_detection = False
                    else:
                        require_silence_detection = True
            
            if not tracks and duration > 300:
                print(f"\n[건너뜀] 5분 이상 영상이나 분할 정보 없음: {video_title} ({duration}초)")
                return

    # 2. 분석 결과가 아예 없으면 단일 트랙으로 간주하고 제목에서 메타데이터 추출
    if not tracks:
        artist, title, is_jp = parse_track_info(video_title, url=url, video_title=video_title, description=description, playlist_title=playlist_title)
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
            if t['artist'] == "Unknown Artist" and not require_silence_detection:
                a, tit, is_jp = parse_track_info(t['raw_title'], url=url, video_title=video_title, description=description, playlist_title=playlist_title)
                if is_jp:
                    continue
                t['artist'], t['title'] = a, tit
            filtered_tracks.append(t)
        tracks = filtered_tracks
        
    if not tracks:
        print(f"\n[알림] 처리할 유효한 트랙이 없습니다 (필터링됨).")
        return

    print(f"\n- 처리 대상: {video_title}")
    
    if tracks:
        print("\n" + "="*60)
        print(f" [트랙 분석 요약] 총 {len(tracks)}곡의 정보를 발견했습니다.")
        print("-" * 60)
        for i, t in enumerate(tracks):
            t_name = f"{t.get('artist', 'Unknown')} - {t.get('title', 'Unknown')}"
            t_time = t.get('time_str', '??:??')
            print(f" {i+1:02d}. {t_name:<40} [{t_time}]")
        print("-" * 60)
        abs_data_path = os.path.abspath(DATA_DIR)
        print(f" [저장 폴더] {abs_data_path}")
        print("=" * 60 + "\n")
    else:
        print(f"  (분석된 트랙 정보가 없습니다.)")

    audio_file = f"temp_{video_id}.mp3"
    try:
        download_audio(url, video_id)
        
        # 무음 구간 탐지가 필요한 경우 오디오 다운로드 후 start_sec 할당
        if require_silence_detection and len(tracks) > 1:
            silences = detect_silences(audio_file)
            
            # [개선] 가수명(Unknown Artist) 일괄 지정
            unknown_tracks = [t for t in tracks if t['artist'] == "Unknown Artist"]
            if unknown_tracks:
                print(f"\n[알림] 가수 이름이 확인되지 않은 곡이 {len(unknown_tracks)}개 있습니다.")
                batch_artist = input("일괄 적용할 가수명을 입력하세요 (건너뛰려면 Enter): ").strip()
                if batch_artist:
                    for t in tracks:
                        if t['artist'] == "Unknown Artist":
                            t['artist'] = batch_artist
                    print(f"  > {len(unknown_tracks)}곡의 가수가 '{batch_artist}'(으)로 설정되었습니다.")

            # [개선] 대화형 트랙 매핑
            print("\n" + "="*40)
            print(f"[곡 목록 정보] 총 {len(tracks)}곡이 발견되었습니다.")
            for i, t in enumerate(tracks):
                print(f"{i+1:2d}. {t['artist']} - {t['title']}")
            print("="*40)
            
            try:
                start_idx_input = input(f"\n몇 번 곡부터 매핑을 시작할까요? (1-{len(tracks)}, 기본값 1): ").strip()
                start_idx = int(start_idx_input) if start_idx_input else 1
                if not (1 <= start_idx <= len(tracks)):
                    print(f"  [알림] 범위를 벗어난 입력입니다. 1번부터 시작합니다.")
                    start_idx = 1
            except ValueError:
                print("  [알림] 올바른 숫자가 아닙니다. 1번부터 시작합니다.")
                start_idx = 1

            # 시작 인덱스에 따라 트랙 리스트 재조정
            tracks = tracks[start_idx-1:]
            
            confirm = input(f"\n발견된 {len(silences)}개의 지점을 '{tracks[0]['title']}' 곡부터 순서대로 매핑할까요? (y/n): ").strip().lower()
            
            if confirm == 'y':
                # 첫 번째 곡은 무조건 0초 (또는 영상의 시작)
                tracks[0]['start_sec'] = 0
                
                # 두 번째 곡부터는 발견된 무음 구간의 끝(소리 시작점)을 매핑
                mapped_count = 1
                for i in range(1, len(tracks)):
                    if i - 1 < len(silences):
                        tracks[i]['start_sec'] = silences[i - 1]['end']
                        mapped_count += 1
                    else:
                        print(f"  [경고] 무음 구간 부족: '{tracks[i]['title']}' 부터는 분할이 불가능합니다.")
                        tracks = tracks[:i]
                        break
                print(f"  [완료] 총 {mapped_count}곡이 매핑되었습니다.")
            else:
                print("  [알림] 사용자가 매핑을 취소했습니다. 단일 트랙으로 처리하거나 다음 영상으로 넘어갑니다.")
                # 단일 트랙으로 처리하기 위해 첫 곡만 남김 (전체 길이)
                tracks = [tracks[0]]
                tracks[0]['start_sec'] = 0
        
        split_audio_ffmpeg(audio_file, tracks, limit=None)
    except Exception as e:
        print(f"\n[오류] {video_title} 처리 중 에러 발생: {e}")
    finally:
        clean_temp_files(f"temp_{video_id}")

def process_url_flow(input_url):
    print("\n정보를 가져오는 중...")
    try:
        info = get_video_info(input_url)
    except Exception as e:
        print(f"\n[오류] 정보를 가져올 수 없습니다: {e}")
        return

    # 재생목록 여부 확인
    if '_type' in info and info['_type'] == 'playlist':
        entries = info.get('entries', [])
        
        # 실제 비디오 항목만 필터링
        filtered_entries = [
            entry for entry in entries 
            if entry and entry.get('_type') == 'url' and entry.get('id')
        ]
        
        entries = filtered_entries
        total = len(entries)
        
        is_mix = "RD" in input_url or "RD" in info.get('id', '')
        
        # [수정] 믹스(관련 영상)인 경우, 플레이리스트 메뉴를 띄우지 않고 단일 영상으로 처리
        if is_mix:
            print(f"\n[알림] YouTube Mix(관련 영상 목록)가 감지되었습니다. '{info.get('title')}'")
            print("  > 재생목록 메뉴를 건너뛰고 단일 영상 모드로 진행합니다.")
            
            video_url = input_url
            if entries:
                 video_url = entries[0].get('url') or f"https://www.youtube.com/watch?v={entries[0].get('id')}"
            
            detailed_info = get_video_info(video_url)
            if info.get('title'):
                detailed_info['playlist_title'] = info.get('title')
            process_single_video(video_url, detailed_info)
            return

        print(f"\n[재생목록 발견] 제목: {info.get('title', '알 수 없는 재생목록')}")
        print(f"총 {total}개의 영상이 포함되어 있습니다.")
        
        print("\n원하는 작업을 선택하세요:")
        print("1. 이 주소의 '단일 영상'만 추출")
        print("2. 재생목록 '전체' 추출 (대량 작업)")
        print("3. 재생목록 '상위 10곡만' 테스트 추출")
        print("Q. 종료")
        
        choice = input("\n선택 (1/2/3/Q): ").strip().lower()
        
        if choice == '1':
            first_entry = entries[0] if entries else None
            video_url = input_url
            if first_entry:
                video_url = first_entry.get('url') or f"https://www.youtube.com/watch?v={first_entry.get('id')}"
            
            print(f"\n[단일 곡 모드] 첫 번째 영상을 분석합니다...")
            detailed_info = get_video_info(video_url)
            if info.get('title'):
                detailed_info['playlist_title'] = info.get('title')
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
                    if info.get('title'):
                        detailed_info['playlist_title'] = info.get('title')
                    process_single_video(video_url, detailed_info)
                except Exception as e:
                    print(f"  [건너뜜] {e}")
        else:
            print("작업을 취소합니다.")
            return
    else:
        # 단일 영상
        process_single_video(input_url, info)

def main():
    print("="*60)
    print(" 유튜브 MP3 추출기 (재생목록 & 메타데이터 보정 지원) ")
    print("="*60)
    
    while True:
        input_url = input("\n유튜브 URL(영상 또는 재생목록)을 입력하세요 (종료하려면 'q' 입력): ").strip()
        if not input_url or input_url.lower() == 'q':
            break
            
        process_url_flow(input_url)
        print(f"\n" + "-"*60)
        print("[완료] 입력하신 URL의 처리가 끝났습니다. 추가로 다운로드할 URL을 입력하세요.")

    print(f"\n" + "="*60)
    print(f"[최종 성공] 프로그램이 종료되었습니다. '{DATA_DIR}' 폴더를 확인하세요.")
    print("="*60)
    
    close_shared_driver()

if __name__ == "__main__":
    main()
