from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import redis
import json
import tempfile
import glob
from cassandra.cluster import Cluster

# Configuration from environment variables
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_QUEUE = os.getenv('REDIS_QUEUE', 'frontier')

CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOSTS', 'localhost').split(',')
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'transcript_db')

def fetch_transcript(url):
    """Fetch and download transcript for a given Laltura Gallery URL"""

    # temp dir for storing transcripts
    temp_dir = tempfile.mkdtemp(prefix="transcript_")

    chrome_options = webdriver.ChromeOptions()
    chrome_options.binary_location = "/usr/local/bin/chrome"

    # Run headless in Docker
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')

    prefs = {
        "download.default_directory": temp_dir,
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

        # Wait for newly downloaded file to appear
        downloaded_file = None
        for _ in range(5): # poll for 15 secs
            time.sleep(3)
            files = glob.glob(os.path.join(temp_dir, "*"))
            if files:
                downloaded_file = files[0]
                if not downloaded_file.endswith(".crdownload"):
                    break
        
        if not downloaded_file or downloaded_file.endswith(".crdownload"):
            print("Download did not finish.")
            return None
        
        with open(downloaded_file, "r", encoding="utf-8", errors="ignore") as f:
            transcript_text = f.read()
        
        print("Successfully fetched transcript text.")
        return transcript_text
    
    except Exception as e:
        print(f"No transcript available {url}: {e}")
        return None
    finally:
        driver.quit()

        try:
            for f in glob.glob(os.path.join(temp_dir, "*")):
                os.remove(f)
            os.rmdir(temp_dir)
        except:
            pass


def main():
    """Main loop to process lecture data from Redis queue"""

    print(f"Connecting to Cassandra at hosts: {CASSANDRA_HOSTS}, keyspace: {CASSANDRA_KEYSPACE}")
    cluster = Cluster(CASSANDRA_HOSTS)
    session = cluster.connect(CASSANDRA_KEYSPACE)

    insert_transcript_stmt = session.prepare("""
        INSERT INTO transcripts (
            class_name,
            professor,
            semester,
            url,
            lecture_number,
            lecture_title,
            transcript_text,
            downloaded_at,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, toTimestamp(now()), ?)
    """)

    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    print(f"Waiting for lectures on queue: {REDIS_QUEUE}")

    while True:
        try:
            # wait for a lecture JSON from the redis queue
            result = r.blpop(REDIS_QUEUE)

            if result:
                _, json_str = result

                lecture = json.loads(json_str)
                
                url = lecture.get('url')
                transcript = fetch_transcript(url)

                if transcript:
                    status = "success"
                else:
                    status = "missing"

                session.execute(
                    insert_transcript_stmt,
                    (
                        lecture.get("class_name"),
                        lecture.get("professor"),
                        lecture.get("semester"),
                        url,
                        lecture.get("lecture_number"),
                        lecture.get("lecture_title"),
                        transcript,
                        status,
                    ),
                )

        except redis.ConnectionError as e:
            # Wait before retrying
            print(f"Redis connection error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Shutting down...")
            cluster.shutdown()
            break
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()