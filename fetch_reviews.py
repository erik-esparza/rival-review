from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import json
import os
import time
import csv

# Constants
CHROMEDRIVER_PATH = "/opt/homebrew/bin/chromedriver"
CSV_FOLDER = "data/csv_exports"

# Configure Selenium
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

def fetch_reviews(app_url):
    """Scrape latest reviews for a given app."""
    reviews = []
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(app_url)
    time.sleep(5)

    review_cards = driver.find_elements(By.CSS_SELECTOR, "[data-merchant-review]")

    for card in review_cards:
        try:
            # Extract rating from aria-label
            rating_element = card.find_element(By.CSS_SELECTOR, "[aria-label$='out of 5 stars']")
            rating = int(rating_element.get_attribute("aria-label").split(" ")[0])

            # Extract date (next sibling div)
            date_element = rating_element.find_element(By.XPATH, "./following-sibling::div")
            date_text = date_element.text.replace("Edited ", "").strip()

            # Extract content (direct child <p>)
            content_element = card.find_element(By.CSS_SELECTOR, "[data-truncate-content-copy] > p")
            content = content_element.text.strip()

            reviews.append({"rating": rating, "date": date_text, "content": content})

        except Exception as e:
            print(f"🔥 Error processing review: {e}")

    driver.quit()
    return reviews

def save_reviews_to_csv(reviews):
    """Save reviews to a CSV file."""
    os.makedirs(CSV_FOLDER, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filepath = os.path.join(CSV_FOLDER, f"reviews_{timestamp}.csv")

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["app_url", "rating", "date", "content"])
        for app_url, review_list in reviews.items():
            for review in review_list:
                writer.writerow([app_url, review["rating"], review["date"], review["content"]])

    print(f"✅ Reviews saved: {filepath}")

def main():
    """Load Top 5 apps and fetch their reviews."""
    with open("data/top_5_links.json", "r") as f:
        review_links = json.load(f)

    all_reviews = {}
    for link in review_links:
        print(f"📥 Fetching reviews for: {link}")
        all_reviews[link] = fetch_reviews(link)

    save_reviews_to_csv(all_reviews)

if __name__ == "__main__":
    main()
