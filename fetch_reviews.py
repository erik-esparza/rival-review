from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from datetime import datetime
import json
import os
import time
import csv

# Constants
## Chromedriver global path is replaced by the expression in the "driver" var
CSV_FOLDER = os.path.join(os.getcwd(), "data/csv_exports")  # Ensure correct path

# Configure Selenium
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

# Ensure necessary folders exist
os.makedirs("data/csv_exports", exist_ok=True)
os.makedirs("data", exist_ok=True)  # Just in case other scripts rely on this

def fetch_reviews(app_url, app_name):
    """Scrape all reviews for a given app, iterating over pages until no more reviews exist."""
    reviews = []
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    page = 1  # Start from page 1
    overall_score = None  # ✅ Keep track of last known valid overall score

    while True:
        paged_url = f"{app_url}&page={page}"  # Append page number
        print(f"📄 Scraping page {page} of reviews for {app_name}: {paged_url}")

        driver.get(paged_url)
        time.sleep(5)  # Keep static delay to avoid detection

        # Check if reviews exist on this page
        review_cards = driver.find_elements(By.CSS_SELECTOR, "[data-merchant-review]")
        if not review_cards:
            print(f"🚫 No reviews found on page {page}, stopping.")
            break  # No reviews = No more pages, exit loop

        # ✅ Only extract `overall_score` ONCE per app (page 1)
        if page == 1:
            try:
                overall_element = driver.find_element(By.CSS_SELECTOR, ".app-reviews-metrics > div:nth-child(2) [aria-label$='out of 5 stars']")
                overall_score = float(overall_element.get_attribute("aria-label").split(" ")[0])
                print(f"⭐ Overall score detected: {overall_score}")
            except Exception as e:
                print(f"⚠ Could not find overall rating for {app_name}: {e}")

        for card in review_cards:
            try:
                # Extract rating from aria-label
                rating_element = card.find_element(By.CSS_SELECTOR, "[aria-label$='out of 5 stars']")
                rating = float(rating_element.get_attribute("aria-label").split(" ")[0])

                # Extract date (next sibling div)
                date_element = rating_element.find_element(By.XPATH, "./following-sibling::div")
                date_text = date_element.text.replace("Edited ", "").strip()

                # Extract content (direct child <p>)
                content_element = card.find_element(By.CSS_SELECTOR, "[data-truncate-content-copy] > p")
                content = content_element.text.strip()

                # ✅ If `overall_score` is None, inherit last valid score
                if overall_score is None:
                    print(f"🔄 Using last known valid overall score: {overall_score}")

                reviews.append({
                    "app_name": app_name,
                    "date": date_text,
                    "star_rating": rating,
                    "content": content,
                    "overall_score": overall_score  # ✅ Persist across pages
                })

            except Exception as e:
                print(f"🔥 Error processing review: {e}")

        # Check if there's a "Next" page
        next_button = driver.find_elements(By.CSS_SELECTOR, "a[rel='next']")
        if not next_button:
            print(f"✅ All pages scraped for {app_name}.")
            break  # No "Next" button → Last page reached

        page += 1  # Move to next page

    driver.quit()
    return reviews

def save_new_reviews(review_data):
    """Save new review data into a separate CSV file with a timestamp."""
    os.makedirs(CSV_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(CSV_FOLDER, f"reviews_{timestamp}.csv")

    with open(filename, "w", newline="", encoding="utf-8") as f:  # ✅ Ensures correct encoding
        writer = csv.writer(f)
        writer.writerow(["App Name", "Review Date", "Star Rating", "Review Content", "Overall Score"])

        for app_url, reviews in review_data.items():
            for review in reviews:
                writer.writerow([
                    review["app_name"],
                    review["date"],
                    review["star_rating"],
                    review["content"],
                    review["overall_score"]
                ])

    print(f"✅ New reviews saved: {filename}")

def save_historical_reviews(review_data):
    """Append new review data to a single historical CSV file that accumulates data over time."""

    os.makedirs(CSV_FOLDER, exist_ok=True)  
    filename = os.path.join(CSV_FOLDER, "historical_reviews.csv")  

    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Timestamp when data was collected

    with open(filename, "a", newline="", encoding="utf-8") as f:  # ✅ UTF-8 for special characters
        writer = csv.writer(f)

        if not file_exists:  # If file doesn't exist, add headers
            writer.writerow(["date_collected", "app_name", "app_url", "review_date", "star_rating", "review_content", "overall_score"])

        for app_url, reviews in review_data.items():  
            app_name = reviews[0]["app_name"] if reviews else "Unknown App"

            for review in reviews:
                writer.writerow([
                    timestamp,
                    app_name,
                    app_url,
                    review["date"],
                    review["star_rating"],
                    review["content"],
                    review["overall_score"]
                ])

    print(f"✅ Historical reviews saved: {filename}")

def main():
    """Load Top 5 apps, fetch reviews once, and save to both new & historical files."""
    with open("data/top_5_links.json", "r") as f:
        review_links = json.load(f)

    with open("data/past_apps.json", "r") as f:
        past_data = json.load(f)

    app_name_map = {app["url"]: app["name"] for app in past_data["top_5"]}

    all_reviews = {}

    for link in review_links:
        app_name = app_name_map.get(link.split("/reviews")[0], "Unknown App")
        print(f"📥 Fetching reviews for: {app_name} ({link})")
        all_reviews[link] = fetch_reviews(link, app_name)

    save_new_reviews(all_reviews)
    save_historical_reviews(all_reviews)

if __name__ == "__main__":
    main()
