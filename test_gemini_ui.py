import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

def test_gemini():
    chrome_options = Options()
    user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    chrome_options.add_argument(f"--user-data-dir={user_data}")
    chrome_options.add_argument("--profile-directory=Default")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print("Chrome might be open. Close it first.", e)
        return

    driver.get("https://gemini.google.com/app")
    wait = WebDriverWait(driver, 15)
    
    try:
        # Wait for input box
        input_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[contenteditable='true']")))
        print("Input box found.")
        
        prompt = "Hello, what is 1+1? Answer only with a number."
        
        # Method 1
        input_box.click()
        input_box.send_keys(prompt)
        time.sleep(1)
        
        # Find send button
        send_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send message'], button[aria-label*='전송'], button[aria-label*='보내기']")
        send_btn.click()
        
        print("Message sent.")
        
        # Wait for response
        time.sleep(10)
        
        response_selectors = [
            "model-response .markdown",
            "message-content p",
            ".model-response-text p",
        ]
        for sel in response_selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                print(f"Response using selector {sel}:", elems[-1].text)
                break
                
    except Exception as e:
        print("Error during test:", e)
        
    time.sleep(5)
    driver.quit()

if __name__ == "__main__":
    test_gemini()
