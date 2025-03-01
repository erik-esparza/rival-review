from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from datetime import datetime
import json
import os
import time
import csv

# Constants
CHROMEDRIVER_PATH = "/opt/homebrew/bin/chromedriver"
CSV_FOLDER = os.path.join(os.getcwd(), "data/csv_exports")  # Ensure correct path

# Configure Selenium
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

def fetch_reviews(app_url, app_name):
    """Scrape latest reviews for a given app, including overall rating."""
    reviews = []
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(app_url)
    time.sleep(5)

    # Extract the overall score before review iteration
    try:
        overall_element = driver.find_element(By.CSS_SELECTOR, ".app-reviews-metrics div:nth-child(2) [aria-label$='out of 5 stars']")
        overall_rating = float(overall_element.get_attribute("aria-label").split(" ")[0])
    except Exception as e:
        print(f"⚠️ Could not find overall rating for {app_name}: {e}")
        overall_rating = None  # Default to None if not found

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

            reviews.append({
                "app_name": app_name,
                "app_url": app_url,
                "date": date_text,
                "star_rating": rating,
                "content": content,
                "overall_score": overall_rating  # ✅ Include overall score for each review
            })

        except Exception as e:
            print(f"🔥 Error processing review: {e}")

    driver.quit()
    return reviews


def save_new_reviews(review_data):
    """Save new review data into a separate CSV file with a timestamp."""
    os.makedirs(CSV_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(CSV_FOLDER, f"reviews_{timestamp}.csv")

    with open(filename, "w", newline="") as f:
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

    # Ensure directory exists
    os.makedirs(CSV_FOLDER, exist_ok=True)  

    # Construct correct path
    filename = os.path.join(CSV_FOLDER, "historical_reviews.csv")  

    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Timestamp when data was collected

    with open(filename, "a", newline="") as f:  # "a" mode appends new data
        writer = csv.writer(f)

        if not file_exists:  # If file doesn't exist, add headers
            writer.writerow(["date_collected", "app_name", "app_url", "review_date", "star_rating", "review_content", "overall_score"])

        for app_url, reviews in review_data.items():  # Iterate over apps
            app_name = reviews[0]["app_name"] if reviews else "Unknown App"  # Get app_name directly from reviews

            for review in reviews:  # Iterate through each review
                writer.writerow([
                    timestamp,  # Timestamp of collection
                    app_name,  # Extracted from the passed object
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

    # Load app names from the stored JSON of apps
    with open("data/past_apps.json", "r") as f:
        past_data = json.load(f)

    app_name_map = {app["url"]: app["name"] for app in past_data["top_5"]}

    all_reviews = {}

    for link in review_links:
        app_name = app_name_map.get(link.split("/reviews")[0], "Unknown App")  # Extract app name
        print(f"📥 Fetching reviews for: {app_name} ({link})")
        all_reviews[link] = fetch_reviews(link, app_name)  # Pass app_name too

    save_new_reviews(all_reviews)  # Save the newly fetched reviews
    save_historical_reviews(all_reviews)  # Append them to historical record


if __name__ == "__main__":
    main()
