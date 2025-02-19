from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import json
import os
import re
import time
from urllib.parse import urlparse, parse_qs, urlencode

# Constants
SHOPIFY_SEARCH_URL = "https://apps.shopify.com/search?q=Quiz"
DATA_FILE = "data/past_apps.json"
CHROMEDRIVER_PATH = "/opt/homebrew/bin/chromedriver"  # Updated path

# Configure Selenium
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass detection
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-dev-shm-usage")

def clean_url(url):
    """Remove entire UTM parameters if 'surface' is found anywhere in the string."""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    if any("surface" in k.lower() for k in query_params.keys()):
        return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    
    return url

BAD_URL_PATTERNS = re.compile(r"(categories|stories|sitemap|login|help|about|support)")

def fetch_apps():
    """Fetch app names and links using <a> href extraction."""
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    all_apps = []
    page = 1

    while True:
        search_url = f"{SHOPIFY_SEARCH_URL}&page={page}" if page > 1 else SHOPIFY_SEARCH_URL
        print(f"Scraping: {search_url}")
        driver.get(search_url)
        time.sleep(5)  # Static delay to prevent detection by Shopify

        if driver.find_elements(By.CSS_SELECTOR, "#app-header > div > p"):
            header_text = driver.find_element(By.CSS_SELECTOR, "#app-header > div > p").text
            if header_text.startswith("Sorry, nothing here"):
                print("No more apps found. Stopping iteration.")
                break

        app_cards = driver.find_elements(By.CSS_SELECTOR, "[data-controller='app-card']")
        
        if not app_cards:
            print(f"No apps found on page {page}. Stopping iteration.")
            break
        
        seen_ads = set()
        seen_organic = set()
        valid_apps = []
        rank = len([app for app in all_apps if not app["ad"]])  # Maintain correct ranking

        for card in app_cards:
            try:
                link_element = card.find_element(By.CSS_SELECTOR, "a[href^='https://apps.shopify.com/']")
                link = link_element.get_attribute("href")
                title = link_element.text.strip()
                clean_link = clean_url(link)
                is_ad = bool(card.find_elements(By.CSS_SELECTOR, "[data-controller='popover-modal']"))
                
                if not title or not clean_link:
                    continue
                
                if BAD_URL_PATTERNS.search(clean_link) or re.fullmatch(r"\d+", title) or title in ["Previous", "Next"]:
                    continue
                
                # Allow the same app to appear twice if once as an ad and once organically
                if is_ad:
                    if clean_link in seen_ads:
                        continue  # Skip duplicate ads
                    seen_ads.add(clean_link)
                else:
                    if clean_link in seen_organic:
                        continue  # Skip duplicate organic results
                    seen_organic.add(clean_link)
                    rank += 1  # Only increment rank for organic apps
                
                app_entry = {"name": title, "url": clean_link, "ad": is_ad, "rank": None if is_ad else rank}
                valid_apps.append(app_entry)
            
            except Exception as e:
                print(f"🔥 Error processing app link: {e}")
        
        all_apps.extend(valid_apps)
        page += 1
    
    driver.quit()
    return {"all_apps": all_apps}

def load_past_apps():
    """Load past app data from JSON safely, ensuring a valid dictionary structure."""
    if not os.path.exists(DATA_FILE):
        print("INFO: past_apps.json does not exist. Creating a new one.")
        return {"all_apps": [], "new_apps": [], "top_5": []}  # Default structure

    try:
        with open(DATA_FILE, "r") as f:
            data = f.read().strip()
            if not data:
                print("WARNING: past_apps.json was empty. Resetting data.")
                return {"all_apps": [], "new_apps": [], "top_5": []}

            past_apps = json.loads(data)
            if isinstance(past_apps, dict):
                return past_apps
            elif isinstance(past_apps, list):  
                print("WARNING: past_apps.json contained a list. Converting to expected format.")
                return {"all_apps": past_apps, "new_apps": [], "top_5": []}  
            else:
                print("ERROR: Unexpected data format in past_apps.json. Resetting data.")
                return {"all_apps": [], "new_apps": [], "top_5": []}  
    except json.JSONDecodeError:
        print("ERROR: past_apps.json is corrupted. Resetting data.")
        return {"all_apps": [], "new_apps": [], "top_5": []}  

def save_current_apps(data):
    """Save current apps to JSON."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def compare_apps():
    """Compare current apps with past apps and detect ranking changes."""
    past_data = load_past_apps()
    past_apps = {app["name"]: app.get("rank", None) for app in past_data.get("all_apps", [])}
    
    fetched_data = fetch_apps()
    current_apps = fetched_data["all_apps"]
    
    ranking_changes = []
    for app in current_apps:
        prev_rank = past_apps.get(app["name"], None)
        if prev_rank is not None and prev_rank != app["rank"]:
            ranking_changes.append({"name": app["name"], "old_rank": prev_rank, "new_rank": app["rank"]})
    
    print(json.dumps({"all_apps": current_apps, "ranking_changes": ranking_changes}, indent=4))
    save_current_apps({"all_apps": current_apps, "ranking_changes": ranking_changes})

if __name__ == "__main__":
    compare_apps()
