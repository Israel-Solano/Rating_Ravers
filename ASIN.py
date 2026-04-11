import time
import csv
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ASIN_FILE = "asins.txt"
OUTPUT_FILE = "ratings.csv"
BASE_URL = "https://www.amazon.com/dp/{asin}"

# Set this if chromedriver is not on PATH, e.g. r"C:\path\to\chromedriver.exe"
CHROMEDRIVER_PATH = None  # or "chromedriver"

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    if CHROMEDRIVER_PATH:
        service = Service(CHROMEDRIVER_PATH)
    else:
        service = Service()

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_title_rating_reviews(driver, asin, timeout=15):
    url = BASE_URL.format(asin=asin)
    driver.get(url)

    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "productTitle"))
        )
    except TimeoutException:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.ID, "averageCustomerReviews"))
            )
        except TimeoutException:
            print(f"  ⚠️  Timed out loading page for {asin}")
            return "", "", ""

    # title
    title_text = ""
    try:
        title_el = driver.find_element(By.ID, "productTitle")
        title_text = title_el.text.strip()
    except NoSuchElementException:
        pass

    # rating
    rating_text = ""
    try:
        rating_span = driver.find_element(
            By.CSS_SELECTOR,
            "#averageCustomerReviews span.a-size-small.a-color-base"
        )
        rating_text = rating_span.text.strip()
    except NoSuchElementException:
        try:
            pop = driver.find_element(By.ID, "acrPopover")
            title_attr = pop.get_attribute("title") or ""
            if title_attr:
                rating_text = title_attr.split()[0]
        except NoSuchElementException:
            pass

    # review count
    reviews_text = ""
    try:
        rev_span = driver.find_element(By.ID, "acrCustomerReviewText")
        txt = rev_span.get_attribute("innerText") or rev_span.text
        txt = txt.strip()
        txt = txt.strip("()")
        txt = txt.replace("ratings", "").replace("Reviews", "").strip()
        txt = txt.replace(",", "")
        reviews_text = txt
    except NoSuchElementException:
        pass

    return title_text, rating_text, reviews_text

def main():
    asin_path = Path(ASIN_FILE)
    if not asin_path.exists():
        print(f"{ASIN_FILE} not found")
        return

    # load all ASINs
    with asin_path.open("r", encoding="utf-8") as f:
        all_asins = [line.strip() for line in f if line.strip()]

    # check existing CSV for completed ASINs
    completed_asins = set()
    file_exists = Path(OUTPUT_FILE).exists()
    if file_exists:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            completed_asins = {row["asin"] for row in reader if row.get("asin")}

    # filter to new ASINs only
    new_asins = [asin for asin in all_asins if asin not in completed_asins]
    total_new = len(new_asins)
    print(f"Found {len(all_asins)} total ASINs, {len(completed_asins)} already done")
    print(f"Will process {total_new} new ASINs")

    if total_new == 0:
        print("All ASINs already processed!")
        return

    driver = create_driver()

    # open CSV in append mode
    csv_file = open(OUTPUT_FILE, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=["asin", "title", "rating", "reviews"])

    # write header if file is new/empty
    if not file_exists or Path(OUTPUT_FILE).stat().st_size == 0:
        writer.writeheader()
        csv_file.flush()

    try:
        for i, asin in enumerate(new_asins, start=1):
            print(f"[{i}/{total_new}] {asin}")
            title, rating, reviews = get_title_rating_reviews(driver, asin)
            print(f"  📖 {title[:60]}{'...' if len(title) > 60 else ''}")
            print(f"  ⭐ {rating} ({reviews})")

            row = {
                "asin": asin,
                "title": title,
                "rating": rating,
                "reviews": reviews
            }
            writer.writerow(row)
            csv_file.flush()  # save immediately

            time.sleep(2)  # be gentle

    finally:
        csv_file.close()
        driver.quit()

    print(f"✅ Finished {total_new} new ASINs. Total output: {len(completed_asins) + total_new} rows in {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
