from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import redis

# Configuration from environment variables
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_QUEUE = os.getenv('REDIS_QUEUE', 'frontier')

def fetch_transcript(url) -> bool:
    """Fetch and download transcript for a given video URL"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.binary_location = "/usr/local/bin/chrome"

    # Run headless in Docker
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')

    prefs = {
        "download.default_directory": "/volume",
        "download.prompt_for_download": False,
        "directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    service = ChromeService(executable_path="/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print(f"Processing URL: {url}")
        driver.get(url)

        # Click play button
        play_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#kplayer .playkit-pre-playback-play-button"))
        )
        play_button.click()

        # click download button
        download_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Download"]'))
        )
        download_button.click()

        # click the overlay download to get the transcript
        download_overlay_item = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '.download-item__download-icon___h9D1D'))
        )
        download_overlay_item.click()

        # wait for download to complete
        time.sleep(3)
        print(f"Successfully downloaded transcript for: {url}")
        return True

    except Exception as e:
        print(f"No transcript available {url}: {e}")
        return False
    finally:
        driver.quit()

def main():
    """Main loop to process URLs from Redis queue"""
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    print(f"Waiting for URLs on queue: {REDIS_QUEUE}")

    while True:
        try:
            # wait for a link from the redis queue
            result = r.blpop(REDIS_QUEUE)

            if result:
                _, url = result
                print(f"\nReceived URL from queue: {url}")

                # Process the URL
                success = fetch_transcript(url)

                if success:
                    print(f"Completed: {url}\n")
                else:
                    print(f"No transcript found: {url}\n")

        except redis.ConnectionError as e:
            # Wait before retrying
            print(f"Redis connection error: {e}")
            time.sleep(5)  
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()