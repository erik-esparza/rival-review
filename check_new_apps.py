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
    
    # If any key contains 'surface', drop all UTM parameters
    if any("surface" in k for k in query_params):
        return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    
    return url

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
        time.sleep(5)  # Allow JavaScript to load

        # Stop if 'Sorry, nothing here' is found in the app header
        if driver.find_elements(By.CSS_SELECTOR, "#app-header > div > p"):
            header_text = driver.find_element(By.CSS_SELECTOR, "#app-header > div > p").text
            if header_text.startswith("Sorry, nothing here"):
                print("No more apps found. Stopping iteration.")
                break

        # Extract app elements
        app_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='https://apps.shopify.com/']")
        
        if not app_links:
            print(f"No apps found on page {page}. Stopping iteration.")
            break
        
        seen_apps = set()
        for a_tag in app_links:
            try:
                link = a_tag.get_attribute("href")
                title = a_tag.text.strip()
                clean_link = clean_url(link)
                
                # Ignore pagination links and unwanted categories
                if re.fullmatch(r"\d+", title) or "/categories/" in clean_link or "/stories/" in clean_link or "auth=" in clean_link or "/sitemap" in clean_link or title in ["Previous", "Next"]:
                    continue
                
                # Ensure valid title & link, and avoid duplicates
                if not title or not clean_link or clean_link in seen_apps:
                    continue
                
                seen_apps.add(clean_link)
                all_apps.append({"name": title, "url": clean_link})

            except Exception as e:
                print(f"🔥 Error processing app link: {e}")
        
        page += 1
    
    driver.quit()
    return {"all_apps": all_apps}

def load_past_apps():
    """Load past app data from JSON."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            data = f.read().strip()
            past_apps = json.loads(data) if data else []
            return past_apps if isinstance(past_apps, dict) else {"all_apps": [], "new_apps": []}
    except json.JSONDecodeError:
        print("Warning: past_apps.json is corrupted. Resetting data.")
        return {"all_apps": [], "new_apps": []}

def save_current_apps(data):
    """Save current apps to JSON."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def compare_apps():
    """Compare current apps with past apps and detect new ones."""
    past_data = load_past_apps()
    past_apps = past_data.get("all_apps", [])
    
    fetched_data = fetch_apps()
    current_apps = fetched_data["all_apps"]
    
    past_app_names = {app["name"] for app in past_apps if isinstance(app, dict)}
    new_apps = [app for app in current_apps if app["name"] not in past_app_names]

    output = {
        "all_apps": current_apps,
        "new_apps": new_apps
    }

    print(json.dumps(output, indent=4))
    save_current_apps(output)

if __name__ == "__main__":
    compare_apps()
