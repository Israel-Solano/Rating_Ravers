import csv
import time
import random
import os
import re
import json
from bs4 import BeautifulSoup


try:
    from curl_cffi import requests
except ImportError:
    print("ERROR: Please install curl-cffi first:")
    print("pip install curl-cffi")
    exit(1)


def extract_zocdoc_provider_data(soup, html_content, url):
    """
    Extract provider data from ZocDoc pages.
    ZocDoc uses a combination of meta tags, data attributes, and embedded content.
    """
    provider_data = {
        'url': url,
        'name': 'N/A',
        'credentials': 'N/A',
        'specialty': 'N/A',
        'practice_name': 'N/A',
        'rating': 'N/A',
        'review_count': 'N/A',
        'npi': 'N/A',
        'gender': 'N/A',
        'languages': 'N/A',
        'virtual_care': 'N/A',
        'accepting_new_patients': 'N/A',
        'visit_reasons': 'N/A',
        'insurance_accepted': 'N/A',
        'specialty_id': 'N/A',
        'meta_description': 'N/A',
    }

    # Extract name and credentials from title
    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.get_text()
        # Title format: "Name, CREDENTIALS, STATE | Service"
        match = re.match(r'([^,]+),\s*([^,]+)', title_text)
        if match:
            provider_data['name'] = match.group(1).strip()
            provider_data['credentials'] = match.group(2).split(',')[0].strip()

    # Extract specialty from URL
    specialty_match = re.search(r'dr_specialty=(\d+)', url)
    if specialty_match:
        provider_data['specialty_id'] = specialty_match.group(1)

    # Extract description from "Getting to know" section
    description_section = soup.find('span', {'data-test': 'AboutProfessional-details-professional-statement-section'})
    if description_section:
        # Get the full text including the collapsed part
        preview_span = description_section.find('span', {'data-test': 'preview-span'})
        collapsed_span = description_section.find('span', class_=re.compile(r'sc-9jrvto-2'))
        
        description_parts = []
        if preview_span:
            description_parts.append(preview_span.get_text(strip=True))
        if collapsed_span:
            description_parts.append(collapsed_span.get_text(strip=True))
        
        if description_parts:
            full_description = ' '.join(description_parts)
            provider_data['meta_description'] = full_description[:500]  # Limit to 500 chars

    # Fallback: Try to get from meta description tag if "Getting to know" section not found
    if provider_data['meta_description'] == 'N/A':
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            desc_content = meta_desc.get('content', '')
            provider_data['meta_description'] = desc_content[:500]

    # Extract specialty from page content
    specialty_tag = soup.find('span', {'data-test': 'provider-specialty'})
    if specialty_tag:
        provider_data['specialty'] = specialty_tag.get_text(strip=True)

    # CORRECTED RATING EXTRACTION
    # ZocDoc stores the rating in a div with dynamic class names
    # Look for the numeric rating displayed on the page
    
    # Method 1: Find div with rating number (most reliable)
    rating_div = soup.find('div', class_=re.compile(r'sc-hOynoF'))
    if rating_div:
        rating_text = rating_div.get_text(strip=True)
        try:
            rating_val = float(rating_text)
            if 0 <= rating_val <= 5:
                provider_data['rating'] = rating_val
        except ValueError:
            pass
    
    # Method 2: Look for aria-label with rating value
    if provider_data['rating'] == 'N/A':
        aria_rating = soup.find(attrs={'aria-label': re.compile(r'Rated\s+(\d+\.?\d*)\s+out\s+of', re.IGNORECASE)})
        if aria_rating:
            match = re.search(r'Rated\s+(\d+\.?\d*)\s+out\s+of', aria_rating['aria-label'])
            if match:
                try:
                    rating_val = float(match.group(1))
                    if 0 <= rating_val <= 5:
                        provider_data['rating'] = rating_val
                except ValueError:
                    pass
    
    # Method 3: Look for any div containing just a rating number near star icons
    if provider_data['rating'] == 'N/A':
        all_divs = soup.find_all('div', class_=True)
        for div in all_divs:
            text = div.get_text(strip=True)
            # Check if it's just a rating number (e.g., "4.96", "4.5", "5.0")
            if re.match(r'^\d\.\d{1,2}$', text):
                # Check if there are star elements nearby (sibling or parent)
                parent = div.find_parent()
                if parent and (parent.find('svg') or 'star' in str(parent).lower() or 'rating' in str(parent).lower()):
                    try:
                        rating_val = float(text)
                        if 0 <= rating_val <= 5:
                            provider_data['rating'] = rating_val
                            break
                    except ValueError:
                        continue

    # IMPROVED REVIEW COUNT EXTRACTION
    # Method 1: Look for "(X patient ratings)" text in spans
    rating_span = soup.find('span', class_=re.compile(r'sc-1s4x40y-9|khlsTZ'))
    if rating_span:
        rating_text = rating_span.get_text(strip=True)
        match = re.search(r'(\d+)\s+patient\s+ratings?', rating_text, re.IGNORECASE)
        if match:
            try:
                count = int(match.group(1))
                if count > 0:
                    provider_data['review_count'] = count
            except ValueError:
                pass

# Method 1: Look for meta tag with itemprop="reviewCount" (most reliable)
    review_meta = soup.find('meta', {'itemprop': 'reviewCount'})
    if review_meta and review_meta.get('content'):
        try:
            count = int(review_meta.get('content'))
            if count > 0:
                provider_data['review_count'] = count
        except (ValueError, TypeError):
            pass
    # Method 2: Look for "See all X reviews" button text
    if provider_data['review_count'] == 'N/A':
        review_button = soup.find('button', {'data-test': 'focal-review-summary-read-more-link'})
        if review_button:
            button_text = review_button.get_text(strip=True)
            match = re.search(r'(\d+)\s+reviews?', button_text, re.IGNORECASE)
            if match:
                try:
                    count = int(match.group(1))
                    if count > 0:
                        provider_data['review_count'] = count
                except ValueError:
                    pass

    # Method 3: Generic search for "(X patient ratings)" or "X reviews" patterns
    if provider_data['review_count'] == 'N/A':
        review_patterns = [
            r'\((\d+)\s+patient\s+ratings?\)',
            r'(\d+)\s+verified\s+reviews?',
            r'See\s+all\s+(\d+)\s+reviews?',
            r'reviewCount["\']?\s*:\s*["\']?(\d+)',
        ]
        for pattern in review_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                try:
                    count = int(match.group(1))
                    if count > 0 and count < 100000:
                        provider_data['review_count'] = count
                        break
                except ValueError:
                    continue

    # Extract NPI (National Provider Identifier)
    npi_pattern = r'(?:NPI|National Provider Identifier)[^\d]*(\d{10})'
    npi_match = re.search(npi_pattern, html_content, re.IGNORECASE)
    if npi_match:
        provider_data['npi'] = npi_match.group(1)

    # Extract gender
    gender_section = soup.find('section', {'data-test': 'Gender-section'})
    if gender_section:
        # Get text after the h3 header
        gender_text = gender_section.get_text(strip=True)
        gender_text = gender_text.replace('Gender', '').strip()
        if gender_text:
            provider_data['gender'] = gender_text

    # Extract languages
    lang_div = soup.find('div', {'data-test': 'provider-languages'})
    if lang_div:
        provider_data['languages'] = lang_div.get_text(strip=True)

    # Check for virtual care
    if re.search(r'virtual\s+care|telemedicine|video\s+visit', html_content, re.IGNORECASE):
        provider_data['virtual_care'] = 'Yes'
    else:
        provider_data['virtual_care'] = 'No'

    # Check if accepting new patients
    if re.search(r'accepting\s+new\s+patients', html_content, re.IGNORECASE):
        provider_data['accepting_new_patients'] = 'Yes'
    elif re.search(r'not\s+accepting', html_content, re.IGNORECASE):
        provider_data['accepting_new_patients'] = 'No'

    # Extract visit reasons (conditions treated)
    visit_reasons = []

    # Extract from select dropdown options
    select_tag = soup.find('select', {'data-test': 'procedure-select'})
    if select_tag:
        # Get options from "Popular Visit Reasons" optgroup
        popular_optgroup = select_tag.find('optgroup', {'label': 'Popular Visit Reasons'})
        if popular_optgroup:
            options = popular_optgroup.find_all('option')
            visit_reasons = [opt.get_text(strip=True) for opt in options if opt.get_text(strip=True)]
        
        # If no popular reasons, get from "All Visit Reasons"
        if not visit_reasons:
            all_optgroup = select_tag.find('optgroup', {'label': 'All Visit Reasons'})
            if all_optgroup:
                options = all_optgroup.find_all('option')
                visit_reasons = [opt.get_text(strip=True) for opt in options[:10]]  # Limit to first 10

    if visit_reasons:
        provider_data['visit_reasons'] = '; '.join(visit_reasons)

    # Extract practice/location name
    # Method 1: Look for practice link in the Education and background section
    practice_link = soup.find('a', {'data-test': 'profile-practice-link'})
    if practice_link:
        provider_data['practice_name'] = practice_link.get_text(strip=True)

    # Method 2: Fallback to regex patterns if not found
    if provider_data['practice_name'] == 'N/A':
        practice_patterns = [
            r'"practiceName"\s*:\s*"([^"]+)"',
            r'<h2[^>]*practice[^>]*>([^<]+)</h2>',
        ]
        for pattern in practice_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                provider_data['practice_name'] = match.group(1).strip()
                break

    # Extract insurance information (top insurances)
    insurance_patterns = [
        r'data-test="popular-in-network-insurance-([^"]+)"',
        r'in-network-insurance-([a-z]+)',
    ]
    insurances = []
    for pattern in insurance_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        if matches:
            insurances = list(set([ins.title() for ins in matches[:5]]))
            break
    if insurances:
        provider_data['insurance_accepted'] = '; '.join(insurances)

    return provider_data


def scrape_provider_data(url, retry_count=0):
    """
    Scrape provider data from ZocDoc and similar healthcare provider websites.
    """
    try:
        response = requests.get(
            url,
            impersonate="chrome120",
            timeout=15
        )

        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract provider data
        provider_data = extract_zocdoc_provider_data(soup, response.text, url)

        return provider_data

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        if retry_count < 1:
            print(f"Retrying in 10 seconds...")
            time.sleep(10)
            return scrape_provider_data(url, retry_count + 1)
        return None


def meets_criteria(provider_data, min_rating=4.0, min_reviews=10):
    """
    Check if provider meets quality criteria.
    """
    try:
        rating = provider_data.get('rating')
        review_count = provider_data.get('review_count')

        if rating == 'N/A' or review_count == 'N/A':
            return False

        rating = float(rating)
        review_count = int(review_count)

        return rating >= min_rating and review_count >= min_reviews
    except (ValueError, TypeError):
        return False


def main():
    import sys

    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # Configuration
    urls_file = 'resources/provider_urls.csv'
    output_file = 'resources/provider_data.csv'
    MIN_DELAY = 2
    MAX_DELAY = 4
    RESET_EVERY = 5
    MIN_RATING = 4.0
    MIN_REVIEWS = 10

    fieldnames = [
        'url', 'name', 'credentials', 'specialty', 'specialty_id', 'practice_name',
        'rating', 'review_count', 'npi', 'gender', 'languages',
        'virtual_care', 'accepting_new_patients', 'visit_reasons',
        'insurance_accepted', 'meta_description'
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
    print(f"Filter: Rating >= {MIN_RATING}, Reviews >= {MIN_REVIEWS}")
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

            provider_data = scrape_provider_data(url)

            if provider_data:
                if meets_criteria(provider_data, MIN_RATING, MIN_REVIEWS):
                    writer.writerow(provider_data)
                    csvfile.flush()
                    success_count += 1
                    print(f"[OK] Saved: {provider_data['name']} ({provider_data['credentials']}) | Rating: {provider_data['rating']} ({provider_data['review_count']} reviews)")
                else:
                    filtered_count += 1
                    print(f"[SKIP] Filtered out: {provider_data['name']} (Rating: {provider_data['rating']}, Reviews: {provider_data['review_count']})")
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
