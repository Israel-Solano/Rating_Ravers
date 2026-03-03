import csv
import time
import gzip
from io import BytesIO
from urllib.parse import urlparse

import requests
import xml.etree.ElementTree as ET

# Change this per site
SITEMAP_INDEX_URL = "https://www.mycolombianrecipes.com/sitemap_index.xml"
OUTPUT_CSV ="colombian.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content

def clean_xml_bytes(xml_bytes: bytes) -> bytes:
    # Try to strip leading/trailing whitespace and null bytes
    xml_bytes = xml_bytes.strip().replace(b"\x00", b"")
    return xml_bytes

def fetch_xml_maybe_gzip(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    raw = resp.content
    if url.lower().endswith(".gz"):
        raw = gzip.decompress(raw)
    return raw  # bytes

def parse_sitemap_index(xml_bytes):
    xml_bytes = clean_xml_bytes(xml_bytes)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(xml_bytes)
    loc_elems = root.findall("sm:sitemap/sm:loc", ns)
    return [e.text.strip() for e in loc_elems if e.text]

def parse_urlset(xml_bytes):
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(xml_bytes)
    loc_elems = root.findall("sm:url/sm:loc", ns)
    return [e.text.strip() for e in loc_elems if e.text]

def main():
    print(f"Fetching sitemap index: {SITEMAP_INDEX_URL}")
    index_xml = fetch_xml_maybe_gzip(SITEMAP_INDEX_URL)
    sitemap_urls = parse_sitemap_index(index_xml)
    print(f"Found {len(sitemap_urls)} child sitemaps")

    all_urls = set()

    for i, sm_url in enumerate(sitemap_urls, start=1):
        print(f"[{i}/{len(sitemap_urls)}] Fetching sitemap: {sm_url}")
        try:
            sm_xml = fetch_xml_maybe_gzip(sm_url)
            locs = parse_urlset(sm_xml)
        except Exception as e:
            print(f"  Error parsing {sm_url}: {e}")
            continue

        print(f"  Found {len(locs)} URLs in this sitemap")
        all_urls.update(locs)

        time.sleep(5)

    print(f"Total unique URLs: {len(all_urls)}")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url"])
        for url in sorted(all_urls):
            writer.writerow([url])

    print(f"Wrote URLs to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
