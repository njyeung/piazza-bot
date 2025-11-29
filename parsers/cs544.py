#!/usr/bin/env python3
"""
CS544 Fall 2025 parser for Tyler Caraza-Harter's course schedule.

Extracts Kaltura lecture gallery links from the course schedule page.
"""

import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def main():
    """
    Parse CS544 schedule page and print lecture Kaltura gallery links to stdout.
    """
    schedule_url = "https://tyler.caraza-harter.com/cs544/f25/schedule.html"

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
        driver.get(schedule_url)

        # Wait for page to load
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )

        # Find all <a> tags and filter for lecture links
        all_links = driver.find_elements(By.TAG_NAME, "a")

        for link in all_links:
            text = link.text
            if "lecture" in text.lower():
                href = link.get_attribute("href")
                if href:
                    lecture_data = {
                        "class_name": "CS544",
                        "professor": "Tyler",
                        "semester": "FALL25",
                        "url": href,
                        "lecture_title": text.strip()
                    }
                    print(json.dumps(lecture_data))

    except Exception as e:
        print(f"Error fetching lecture links: {e}", file=__import__('sys').stderr)
        raise

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
