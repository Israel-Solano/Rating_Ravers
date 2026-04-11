from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import csv
import re
import time
from bs4 import BeautifulSoup
from pathlib import Path
from selenium.common.exceptions import TimeoutException, WebDriverException

FIELDNAMES = [
    "url",
    "username",
    "display_name",
    "reviews_count",
    "starting_price",
    "status",
    "last_updated",
]

FAILED_FIELDNAMES = ["url", "reason"]

def create_driver():
    options = Options()
    options.add_argument("--headless")  # Run without opening browser window
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def scrape_vgen_user(driver, url: str, delay_seconds: float = 5.0) -> dict:
    time.sleep(delay_seconds)

    try:
        driver.get(url)

        time.sleep(5)
        
        # Wait up to 10s for content to load
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Wait specifically for profile elements (adjust selectors as needed)
        try:
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '@')]")),
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'reviews')]"))
                )
            )
        except TimeoutException:
            print("Warning: No profile content found after waiting")

        # NO HTML SAVING - parse directly
        soup = BeautifulSoup(driver.page_source, "html.parser")

        data = {
            "url": url,
            "username": None,
            "display_name": None,
            "reviews_count": None,
            "starting_price": None,
            "status": None,
            "last_updated": None,
        }

        # Username: stricter pattern @ followed by non-space
        username_el = soup.find(
            string=lambda s: isinstance(s, str) and re.search(r"@\S+", s)
        )
        if username_el:
            m = re.search(r"(@\S+)", username_el)
            if m:
                data["username"] = m.group(1).strip()

        # Status
        status_el = soup.find(
            string=lambda s: isinstance(s, str) and "Available for new projects" in s
        )
        if status_el:
            data["status"] = status_el.strip()

        # Reviews
        reviews_el = soup.find(
            string=lambda s: isinstance(s, str) and "reviews" in s.lower()
        )
        if reviews_el:
            m = re.search(r"\((\d+)\s+reviews\)", reviews_el)
            if m:
                data["reviews_count"] = int(m.group(1))

        # Price
        price_el = soup.find(
            string=lambda s: isinstance(s, str) and "From $" in s
        )
        if price_el:
            m = re.search(r"From \$([\d\.]+)", price_el)
            if m:
                try:
                    data["starting_price"] = float(m.group(1))
                except ValueError:
                    data["starting_price"] = m.group(1)

        # Last updated
        updated_el = soup.find(
            string=lambda s: isinstance(s, str) and "Last updated" in s
        )
        if updated_el:
            data["last_updated"] = updated_el.strip()

        # Display name
        title_el = soup.find("h1") or soup.find("title")
        if title_el and title_el.text.strip():
            data["display_name"] = title_el.text.strip()

        return data

    except Exception as e:
        return {
            "url": url,
            "username": None,
            "display_name": None,
            "reviews_count": None,
            "starting_price": None,
            "status": f"ERROR: {e}",
            "last_updated": None,
        }

def read_urls(input_path: str) -> list:
    urls = []
    for line in Path(input_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls

def load_already_done(output_csv: str) -> set:
    done = set()
    if not Path(output_csv).exists():
        return done
    with open(output_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("url"):
                done.add(row["url"])
    return done

def scrape_from_file(input_path: str, output_csv: str, delay_seconds: float = 5.0):
    urls = read_urls(input_path)
    
    # Track done URLs from BOTH main and failed CSVs
    done_urls = load_already_done(output_csv)
    failed_csv = output_csv.replace(".csv", "_failed.csv")
    done_urls.update(load_already_done(failed_csv))

    file_exists = Path(output_csv).exists()
    failed_exists = Path(failed_csv).exists()
    
    # Open both files
    f = open(output_csv, "a", newline="", encoding="utf-8")
    failed_f = open(failed_csv, "a", newline="", encoding="utf-8")
    
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    failed_writer = csv.DictWriter(failed_f, fieldnames=FAILED_FIELDNAMES)
    
    if not file_exists:
        writer.writeheader()
        f.flush()
    if not failed_exists:
        failed_writer.writeheader()
        failed_f.flush()

    driver = create_driver()
    try:
        for url in urls:
            if url in done_urls:
                print(f"SKIP (already done): {url}")
                continue

            info = scrape_vgen_user(driver, url, delay_seconds)
            
            # FAILSAFE: No username = failed to load
            if not info.get('reviews_count'):
                failed_info = {"url": url, "reason": "No username found - likely failed to load"}
                failed_writer.writerow(failed_info)
                failed_f.flush()
                print(f"FAILED (no username): {url}")
            else:
                reviews = info.get('reviews_count')
                if reviews is None or reviews <= 30:
                    print(f"SKIP (no reviews): {url} -> {info['username']}")
                else:
                    print(f"OK: {url} -> {info['username']} ({reviews} reviews)")
                    writer.writerow(info)
                    f.flush()

    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        f.close()
        failed_f.close()
        driver.quit()

if __name__ == "__main__":
    scrape_from_file("resources/users_with_services.txt", "vgen_profiles.csv", delay_seconds=5.0)