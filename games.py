import csv
import time
import random
import os
import re
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests
except ImportError:
    print("ERROR: Please install curl-cffi first:")
    print("pip install curl-cffi")
    exit(1)

def scrape_game_reviews(url, retry_count=0):
    """
    Scrape video game review data from Metacritic pages.
    Extracts critic and user review counts and ratings.
    """
    try:
        response = requests.get(
            url,
            impersonate="chrome120",
            timeout=15
        )

        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract game name from h1 tag
        game_name = 'N/A'
        h1_tag = soup.find('h1')
        if h1_tag:
            game_name = h1_tag.get_text(strip=True)

        # Initialize variables
        critic_score = 'N/A'
        critic_reviews = 0
        user_score = 'N/A'
        user_ratings = 0
        platform_names = []
        platform_slugs = []

        # Extract Critic Score and Review Count
        # Looking for: "Based on X Critic Reviews"
        critic_review_text = soup.find('span', text=re.compile(r'Based on [\d,]+ Critic Reviews?'))
        if critic_review_text:
            match = re.search(r'Based on ([\d,]+) Critic Reviews?', critic_review_text.get_text())
            if match:
                critic_reviews = int(match.group(1).replace(',', ''))

        # Extract critic metascore
        critic_score_div = soup.find('div', {'class': re.compile(r'c-siteReviewScore.*c-siteReviewScore_medium'), 'title': re.compile(r'Metascore \d+')})
        if critic_score_div:
            score_span = critic_score_div.find('span')
            if score_span:
                critic_score = score_span.get_text(strip=True)

        # Fallback: search for metascore in title attribute
        if critic_score == 'N/A':
            metascore_elem = soup.find(attrs={'title': re.compile(r'Metascore \d+')})
            if metascore_elem:
                match = re.search(r'Metascore (\d+)', metascore_elem.get('title', ''))
                if match:
                    critic_score = match.group(1)

        # Extract User Score and Rating Count
        # Looking for: "Based on X User Ratings" (handles comma-formatted numbers like 5,595)
        user_rating_text = soup.find('span', text=re.compile(r'Based on [\d,]+ User Ratings?'))
        if user_rating_text:
            match = re.search(r'Based on ([\d,]+) User Ratings?', user_rating_text.get_text())
            if match:
                # Remove commas before converting to int
                user_ratings = int(match.group(1).replace(',', ''))

        # Extract user score
        user_score_div = soup.find('div', {'class': re.compile(r'c-siteReviewScore_user'), 'title': re.compile(r'User score')})
        if user_score_div:
            score_span = user_score_div.find('span')
            if score_span:
                user_score = score_span.get_text(strip=True)

        # Fallback: search for user score in title attribute
        if user_score == 'N/A':
            user_score_elem = soup.find(attrs={'title': re.compile(r'User score [0-9.]+')})
            if user_score_elem:
                match = re.search(r'User score ([0-9.]+)', user_score_elem.get('title', ''))
                if match:
                    user_score = match.group(1)

        # Extract platform information from "All Platforms" section
        platforms_section = soup.find('div', {'data-testid': 'all-platforms'})
        if platforms_section:
            # Find all platform tiles
            platform_tiles = platforms_section.find_all('a', class_='c-gamePlatformTile')

            for tile in platform_tiles:
                # Extract platform slug from href
                href = tile.get('href', '')
                slug_match = re.search(r'platform=([^&]+)', href)
                if slug_match:
                    slug = slug_match.group(1)
                    platform_slugs.append(slug)

                    # Extract platform display name
                    # First try to find it in the SVG title
                    svg_title = tile.find('title')
                    if svg_title:
                        platform_names.append(svg_title.get_text(strip=True))
                    else:
                        # Otherwise look for text-based platform name
                        platform_text = tile.find('div', class_='g-text-medium')
                        if platform_text:
                            platform_names.append(platform_text.get_text(strip=True))
                        else:
                            # Fallback: use the slug
                            platform_names.append(slug)

        # Convert platform lists to comma-separated strings
        platforms_display = ', '.join(platform_names) if platform_names else 'N/A'
        platforms_tags = ', '.join(platform_slugs) if platform_slugs else 'N/A'

        result = {
            'url': url,
            'game_name': game_name,
            'critic_score': critic_score,
            'critic_reviews': critic_reviews,
            'user_score': user_score,
            'user_ratings': user_ratings,
            'platforms': platforms_display,
            'platform_tags': platforms_tags
        }

        return result

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        if retry_count < 1:
            print(f"Retrying in 10 seconds...")
            time.sleep(10)
            return scrape_game_reviews(url, retry_count + 1)
        return None

def meets_criteria(game_data):
    """
    Check if game meets criteria: more than 5 critic reviews AND more than 5 user ratings
    """
    try:
        critic_reviews = game_data.get('critic_reviews', 0)
        user_ratings = game_data.get('user_ratings', 0)

        # Convert to int if they're strings
        if isinstance(critic_reviews, str):
            critic_reviews = int(critic_reviews) if critic_reviews.isdigit() else 0
        if isinstance(user_ratings, str):
            user_ratings = int(user_ratings) if user_ratings.isdigit() else 0

        return (critic_reviews > 0 and user_ratings > 5) or user_ratings > 50
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
    urls_file = 'resources/metacritic_urls.csv'
    output_file = 'resources/game_reviews.csv'
    MIN_DELAY = 1
    MAX_DELAY = 2
    RESET_EVERY = 5

    fieldnames = [
        'url', 'game_name', 'critic_score', 'critic_reviews',
        'user_score', 'user_ratings', 'platforms', 'platform_tags'
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
    print(f"Filter: More than 5 critic reviews AND more than 5 user ratings")
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

            game_data = scrape_game_reviews(url)

            if game_data:
                if meets_criteria(game_data):
                    writer.writerow(game_data)
                    csvfile.flush()
                    success_count += 1
                    print(f"[OK] Saved: {game_data['game_name']} | Critic: {game_data['critic_score']} ({game_data['critic_reviews']} reviews) | User: {game_data['user_score']} ({game_data['user_ratings']} ratings) | Platforms: {game_data['platforms']}")
                else:
                    filtered_count += 1
                    print(f"[SKIP] Filtered out: {game_data['game_name']} (Critic Reviews: {game_data['critic_reviews']}, User Ratings: {game_data['user_ratings']})")
            else:
                fail_count += 1
                print(f"[FAIL] Could not scrape {url}")

            if i < len(urls):
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)

        print(f"\n{'='*50}")
        print(f"Complete! Data saved to {output_file}")
        print(f"Saved: {success_count} | Filtered: {filtered_count} | Failed: {fail_count}")
        print(f"{'='*50}")

if __name__ == "__main__":
    main()