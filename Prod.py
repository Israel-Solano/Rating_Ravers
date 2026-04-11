import csv
import time
import random
import os
import math
import re
import json
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests
except ImportError:
    print("ERROR: Please install curl-cffi first:")
    print("pip install curl-cffi")
    exit(1)

def extract_ikea_data(soup, html_content):
    """
    Extract product data from IKEA pages.
    IKEA uses embedded JavaScript objects rather than JSON-LD.
    """
    product_data = {}

    # Extract from meta tags
    meta_title = soup.find('meta', property='og:title')
    if meta_title:
        product_data['name'] = meta_title.get('content', 'N/A')

    # Extract price - IKEA uses various patterns
    price_patterns = [
        r'"price":\s*"\$([0-9.]+)"',
        r'"typicalPrice":\s*"\$([0-9.]+)"',
        r'\$\s*([0-9]+\.?[0-9]*)',
    ]

    for pattern in price_patterns:
        match = re.search(pattern, html_content)
        if match:
            product_data['price'] = match.group(1)
            product_data['currency'] = 'USD'
            break

    # Extract item number/SKU
    sku_match = re.search(r'"itemNo":\s*"([^"]+)"', html_content)
    if not sku_match:
        # Try from URL or page
        sku_match = re.search(r'/(\d{8})/', html_content)
    if sku_match:
        product_data['sku'] = sku_match.group(1)

    # Extract rating
    rating_patterns = [
        r'"ratingValue":\s*([0-9.]+)',
        r'"averageRating":\s*([0-9.]+)',
        r'rating:\s*{\s*value:\s*([0-9.]+)',
    ]

    for pattern in rating_patterns:
        match = re.search(pattern, html_content)
        if match:
            product_data['rating_value'] = float(match.group(1))
            break

    # Extract review count
    review_patterns = [
        r'"ratingCount":\s*([0-9]+)',
        r'"reviewCount":\s*([0-9]+)',
        r'count:\s*([0-9]+)',
    ]

    for pattern in review_patterns:
        match = re.search(pattern, html_content)
        if match:
            product_data['review_count'] = int(match.group(1))
            break

    # Extract availability
    if 'InStock' in html_content or 'in stock' in html_content.lower():
        product_data['availability'] = 'InStock'
    elif 'OutOfStock' in html_content or 'out of stock' in html_content.lower():
        product_data['availability'] = 'OutOfStock'

    # Extract brand - for IKEA it's always IKEA
    if 'ikea.com' in html_content.lower():
        product_data['brand'] = 'IKEA'

    return product_data

def scrape_product_data(url, retry_count=0):
    """
    Scrape product data from e-commerce websites.
    Works with sites using schema.org Product format or IKEA's custom format.
    """
    try:
        response = requests.get(
            url,
            impersonate="chrome120",
            timeout=15
        )

        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Try JSON-LD first (original method)
        script_tags = soup.find_all('script', type='application/ld+json')
        product_data = None

        for script_tag in script_tags:
            if not script_tag.string:
                continue
            try:
                data = json.loads(script_tag.string)

                # Handle if data is a list
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            product_data = item
                            break

                # Handle if data is a single object
                elif isinstance(data, dict):
                    if data.get('@type') == 'Product':
                        product_data = data
                    # Sometimes nested in @graph
                    elif '@graph' in data:
                        for item in data['@graph']:
                            if isinstance(item, dict) and item.get('@type') == 'Product':
                                product_data = item
                                break

                if product_data:
                    break
            except (json.JSONDecodeError, KeyError):
                continue

        # If JSON-LD found, extract from it
        if product_data:
            # Extract product name
            product_name = product_data.get('name', 'N/A')

            # Extract brand
            brand_info = product_data.get('brand', {})
            if isinstance(brand_info, dict):
                brand = brand_info.get('name', 'N/A')
            elif isinstance(brand_info, str):
                brand = brand_info
            else:
                brand = 'N/A'

            # Extract price from offers
            offers = product_data.get('offers', [])
            if isinstance(offers, dict):
                offers = [offers]

            price = 'N/A'
            currency = 'N/A'
            availability = 'N/A'
            sku = 'N/A'

            if offers and len(offers) > 0:
                offer = offers[0]
                price = offer.get('price', 'N/A')
                currency = offer.get('priceCurrency', 'N/A')
                availability = offer.get('availability', 'N/A')

                # Clean up availability URL
                if isinstance(availability, str) and 'schema.org/' in availability:
                    availability = availability.split('schema.org/')[-1]

                sku = offer.get('sku', 'N/A')

            # Extract rating and review count from aggregateRating
            aggregate_rating = product_data.get('aggregateRating', {})
            if not isinstance(aggregate_rating, dict):
                aggregate_rating = {}

            rating = (aggregate_rating.get('ratingValue') or
                     aggregate_rating.get('averageRating') or
                     'N/A')
            review_count = (aggregate_rating.get('reviewCount') or
                           aggregate_rating.get('ratingCount') or
                           aggregate_rating.get('count') or
                           'N/A')

            # Fallback: Check page source for alternative rating formats
            js_ratings = extract_js_ratings(response.text)
            if js_ratings:
                if rating == 'N/A':
                    rating = js_ratings.get('value', rating)
                if review_count == 'N/A':
                    review_count = js_ratings.get('count', review_count)

            result = {
                'url': url,
                'name': product_name,
                'brand': brand,
                'price': price,
                'currency': currency,
                'availability': availability,
                'sku': sku,
                'rating_value': rating,
                'review_count': review_count,
            }

            return result

        # Fallback: Try IKEA-specific extraction
        print("No Product schema found, trying IKEA extraction...")
        ikea_data = extract_ikea_data(soup, response.text)

        # Build result with IKEA data
        result = {
            'url': url,
            'name': ikea_data.get('name', soup.find('h1').get_text(strip=True) if soup.find('h1') else 'N/A'),
            'brand': ikea_data.get('brand', 'N/A'),
            'price': ikea_data.get('price', 'N/A'),
            'currency': ikea_data.get('currency', 'USD'),
            'availability': ikea_data.get('availability', 'N/A'),
            'sku': ikea_data.get('sku', 'N/A'),
            'rating_value': ikea_data.get('rating_value', 'N/A'),
            'review_count': ikea_data.get('review_count', 'N/A'),
        }

        return result

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        if retry_count < 1:
            print(f"Retrying in 10 seconds...")
            time.sleep(10)
            return scrape_product_data(url, retry_count + 1)
        return None

def extract_js_ratings(html_content):
    """
    Extract ratings from JavaScript object format.
    Looks for: rating:{value:4.54,count:316}
    """
    try:
        pattern = r'rating:\s*\{\s*value:\s*([0-9.]+)\s*,\s*count:\s*([0-9]+)\s*\}'
        match = re.search(pattern, html_content)
        if match:
            return {
                'value': float(match.group(1)),
                'count': int(match.group(2))
            }
    except Exception as e:
        pass
    return None

def meets_criteria(product_data):
    """
    Check if product meets quality criteria using custom formula.
    Formula: (rating - 4.5)*10 + log(review_count/1000, 2) > 0
    """
    try:
        rating = product_data.get('rating_value')
        review_count = product_data.get('review_count')

        if rating == 'N/A' or review_count == 'N/A':
            return False

        rating = float(rating)
        review_count = int(review_count)

        if review_count <= 0:
            return False

        score = (rating - 4.5) * 10 + math.log(review_count / 1000, 2)
        return score > -5
    except (ValueError, TypeError, ZeroDivisionError):
        return False

def main():
    import sys

    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # Configuration
    urls_file = 'resources/cyclegear.csv'
    output_file = 'resources/cyclegear_data.csv'
    MIN_DELAY = 1
    MAX_DELAY = 2
    RESET_EVERY = 5

    fieldnames = [
        'url', 'name', 'brand', 'price', 'currency', 'availability',
        'sku', 'rating_value', 'review_count'
    ]

    os.makedirs('resources', exist_ok=True)

    try:
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: {urls_file} not found!")
        print(f"Create the file with one URL per line.")
        return

    if not urls:
        print(f"Error: No URLs found in {urls_file}")
        return

    print(f"Found {len(urls)} URLs to scrape")
    print(f"Filter: Custom formula (rating - 4.5)*10 + log(reviews/1000, 2) > 0")
    print(f"Output will be saved to: {output_file}\n")

    with open(output_file, 'w', newline='', encoding='utf-8', buffering=1) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        csvfile.flush()

        success_count = 0
        fail_count = 0
        filtered_count = 0

        for i, url in enumerate(urls, 1):
            if i > 1 and (i - 1) % RESET_EVERY == 0:
                long_delay = random.uniform(15, 25)/10
                print(f"\n[*] Taking a longer break: {long_delay:.1f}s...\n")
                time.sleep(long_delay)

            print(f"Processing {i}/{len(urls)}: {url}")

            product_data = scrape_product_data(url)

            if product_data:
                if meets_criteria(product_data):
                    writer.writerow(product_data)
                    csvfile.flush()
                    success_count += 1
                    print(f"[OK] Saved: {product_data['name']} | Price: {product_data['currency']} {product_data['price']} | Rating: {product_data['rating_value']} ({product_data['review_count']} reviews)")
                else:
                    filtered_count += 1
                    print(f"[SKIP] Filtered out: {product_data['name']} (Rating: {product_data['rating_value']}, Reviews: {product_data['review_count']})")
            else:
                fail_count += 1
                print(f"[FAIL] Could not scrape {url}")

            if i < len(urls):
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                print(f"[WAIT] Waiting {delay:.1f}s before next request...\n")
                time.sleep(delay)

        print(f"\n{'='*50}")
        print(f"Complete! Data saved to {output_file}")
        print(f"Saved: {success_count} | Filtered: {filtered_count} | Failed: {fail_count}")
        print(f"{'='*50}")

if __name__ == "__main__":
    main()