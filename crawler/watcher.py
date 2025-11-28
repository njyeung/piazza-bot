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
REDIS_SEEN_SET = os.getenv('REDIS_SEEN_SET', 'seen')

SCHEDULE_URL = os.getenv('SCHEDULE_URL', 'https://tyler.caraza-harter.com/cs544/f25/schedule.html')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 300))  # Default 5 minutes

def get_lecture_links():
    """Fetch all lecture links from the schedule page"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.binary_location = "/usr/local/bin/chrome"

    # Run headless in Docker
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')

    service = ChromeService(executable_path="/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print(f"Fetching schedule from: {SCHEDULE_URL}")
        driver.get(SCHEDULE_URL)

        # wait for page to load
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )

        # find all <a> tags
        # append the ones that have "Lecture" in text
        all_links = driver.find_elements(By.TAG_NAME, "a")
        lecture_links = []
        for link in all_links:
            text = link.text.lower()
            if "lecture" in text:
                href = link.get_attribute("href")
                if href:
                    lecture_links.append(href)

        print(f"Found {len(lecture_links)} lecture links")
        return lecture_links

    except Exception as e:
        print(f"Error fetching lecture links: {e}")
        return []
    finally:
        driver.quit()

def main():
    """Main loop to poll schedule and add new links to frontier"""
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    print(f"Watcher started - polling every {POLL_INTERVAL} seconds")
    print(f"Queue: {REDIS_QUEUE}")
    print(f"Seen set: {REDIS_SEEN_SET}\n")

    while True:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Polling schedule page...")

            # Get all lecture links
            lecture_links = get_lecture_links()

            new_count = 0
            for url in lecture_links:

                if not r.sismember(REDIS_SEEN_SET, url):
                    r.sadd(REDIS_SEEN_SET, url)
                    r.rpush(REDIS_QUEUE, url)

                    new_count += 1

            if new_count == 0:
                print(f"  No new links found")
            else:
                print(f"  Added {new_count} new link(s) to frontier")
            
            queue_length = r.llen(REDIS_QUEUE)
            seen_count = r.scard(REDIS_SEEN_SET)
            print(f"  Stats: {queue_length} in queue, {seen_count} total seen\n")
            
            print(f"Sleeping for {POLL_INTERVAL} seconds...")
            time.sleep(POLL_INTERVAL)

        except redis.ConnectionError as e:
            print(f"Redis connection error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nShutting down watcher...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
