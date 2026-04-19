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
from time import sleep
from bs4 import BeautifulSoup
from pathlib import Path
from selenium.common.exceptions import TimeoutException


FIELDNAMES = [
    "url",
    "username",
    "service_name",
    "rating",
    "reviews_count",
    "starting_price",
    "category",
    "accepts",
    "last_updated",
]

FAILED_FIELDNAMES = ["url", "reason"]


def create_driver():
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def scrape_vgen_service(driver, url: str, delay_seconds: float = 5.0) -> dict:
    time.sleep(delay_seconds)

    data = {
        "url": url,
        "username": None,
        "service_name": None,
        "rating": None,
        "reviews_count": None,
        "starting_price": None,
        "category": None,
        "accepts": None,
        "last_updated": None,
    }

    try:
        driver.get(url)

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "detailsHeading"))
            )
        except TimeoutException:
            print(f"WARNING: detailsHeading never appeared for {url}, reloading...")
            try:
                driver.get(url)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "detailsHeading"))
                )
            except TimeoutException:
                print(f"WARNING: detailsHeading still missing after reload for {url}")
        sleep(3)
        debug_path = f"debug_{url.split('/')[3]}_{url.split('/')[-1][:8]}.html"
        # with open(debug_path, "w", encoding="utf-8") as dbg:
        #     dbg.write(driver.page_source)
        print(f"DEBUG: saved page source to {debug_path}")

        soup = BeautifulSoup(driver.page_source, "html.parser")

        url_parts = url.split("/")
        if len(url_parts) >= 4:
            data["username"] = "@" + url_parts[3].strip("/")

        details_heading = soup.find(class_="detailsHeading")
        if details_heading:
            h2 = details_heading.find("h2")
            if h2:
                data["service_name"] = h2.get_text(strip=True)

        if not data["service_name"]:
            title_el = soup.find("title")
            if title_el:
                title_text = title_el.get_text(strip=True)
                title_parts = title_text.split("|")
                if len(title_parts) >= 2:
                    data["service_name"] = "|".join(title_parts[:2]).strip()
                elif title_parts:
                    data["service_name"] = title_parts[0].strip()

        if not data["service_name"]:
            h1 = soup.find("h1")
            if h1:
                data["service_name"] = h1.get_text(strip=True)

        category_el = soup.find("p", class_="parentCategory")
        if category_el:
            data["category"] = category_el.get_text(strip=True)

        price_el = soup.find("p", class_="servicePrice")
        if price_el:
            m = re.search(r"\$([\d\.]+)", price_el.get_text())
            if m:
                try:
                    data["starting_price"] = float(m.group(1))
                except ValueError:
                    data["starting_price"] = m.group(1)

        rating_el = soup.find(
            string=lambda s: isinstance(s, str) and re.search(r"[\d\.]+\s*[·•\u00b7\u2027\u22c5]\s*\d+\s+reviews", s)
        )
        if rating_el:
            m = re.search(r"([\d\.]+)\s*[·•\u00b7\u2027\u22c5]\s*(\d+)\s+reviews", rating_el)
            if m:
                try:
                    data["rating"] = float(m.group(1))
                except ValueError:
                    pass
                data["reviews_count"] = int(m.group(2))

        review_strings = [s.strip() for s in soup.strings if re.search(r'\d+\s+reviews', str(s))]
        print(f"RATING SEARCH: {review_strings}")

        ACCEPT_KEYWORDS = [
            "Open communication",
            "WIP updates",
            "Revisions available",
            "Custom proposal",
            "Personalized",
            "Made from template",
            "Commercial use",
            "NSFW",
        ]
        found_accepts = []
        for kw in ACCEPT_KEYWORDS:
            el = soup.find(string=lambda s, k=kw: isinstance(s, str) and k.lower() in s.lower())
            if el:
                found_accepts.append(kw)
        if found_accepts:
            data["accepts"] = "; ".join(found_accepts)

        updated_el = soup.find(
            string=lambda s: isinstance(s, str) and "Last updated" in s
        )
        if updated_el:
            data["last_updated"] = updated_el.strip()

        return data

    except Exception as e:
        data["service_name"] = f"ERROR: {e}"
        return data


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

    done_urls = load_already_done(output_csv)
    failed_csv = output_csv.replace(".csv", "_failed.csv")
    done_urls.update(load_already_done(failed_csv))

    file_exists = Path(output_csv).exists()
    failed_exists = Path(failed_csv).exists()

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
    processed = 0

    try:
        for url in urls:
            if url in done_urls:
                print(f"SKIP (already done): {url}")
                continue

            if processed > 0 and processed % 10 == 0:
                print("RESTARTING DRIVER TO CLEAR CACHE")
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = create_driver()

            info = scrape_vgen_service(driver, url, delay_seconds)
            processed += 1

            if not info.get("service_name") or info["service_name"].startswith("ERROR") or (int(info["reviews_count"] or 0) < 30):
                failed_writer.writerow({"url": url, "reason": info.get("service_name", "Unknown error")})
                failed_f.flush()
                print(f"FAILED: {url}")
            else:
                writer.writerow(info)
                f.flush()
                print(
                    f"OK: {url} -> {info['service_name']} "
                    f"(${info['starting_price']}, {info['reviews_count']} reviews)"
                )

    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        f.close()
        failed_f.close()
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    scrape_from_file("duh.csv", "vgen_services.csv", delay_seconds=3.0)