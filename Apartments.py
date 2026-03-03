import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def get_all_urls(base_url):
    visited = set()
    urls_to_visit = [base_url]
    scraped_urls = set()

    while urls_to_visit:
        current_url = urls_to_visit.pop()
        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            response = requests.get(current_url, timeout=5)
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            continue

        for link in soup.find_all("a", href=True):
            abs_url = urljoin(current_url, link["href"])
            parsed = urlparse(abs_url)
            # Ensure it's an http/https URL in the same domain
            if parsed.scheme in ("http", "https") and parsed.netloc == urlparse(base_url).netloc:
                if abs_url not in scraped_urls:
                    scraped_urls.add(abs_url)
                    urls_to_visit.append(abs_url)

    return list(scraped_urls)

# Usage
if __name__ == "__main__":
    base_url = "https://www.apartments.com/min-2-bedrooms-under-2500-pet-friendly-cat/washer-dryer-dishwasher/?sk=a43cea0fc4e86a789b647f2fdecbe6ea&bb=j752pmgkpI0--g8v17D&sfmin=1000&rt=4,5"  # Replace with your target website
    urls = get_all_urls(base_url)
    print(f"Found {len(urls)} unique URLs:")
    for url in urls:
        print(url)
