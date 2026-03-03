import csv
import time
import random
import os
import re
import sys
from urllib.parse import urlparse

try:
    from curl_cffi import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Please install required packages first:")
    print("pip install curl-cffi beautifulsoup4")
    print("Run: pip install curl-cffi beautifulsoup4")
    exit(1)

def extract_manga_id_from_url(url):
    """
    Extract manga ID from MyAnimeList URL.
    Example: https://myanimelist.net/manga/2/Berserk -> 2
    """
    match = re.search(r'/manga/(\d+)', url)
    if match:
        return match.group(1)
    return None

def scrape_mal_manga(url, retry_count=0):
    """
    Scrape manga data from MyAnimeList.
    Extracts comprehensive information including scores, rankings, statistics, and more.
    """
    try:
        # Make request to MyAnimeList
        response = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            impersonate="chrome120",
            timeout=15
        )

        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title - try multiple methods
        title = 'N/A'

        # Method 1: h1 with class title-name
        title_elem = soup.find('h1', class_='title-name')
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Method 2: itemprop="name" (fallback)
        if title == 'N/A':
            name_elem = soup.find('span', {'itemprop': 'name'})
            if name_elem:
                title = name_elem.get_text(strip=True)

        # Extract English title and Synonyms from Alternative Titles
        english_title = 'N/A'
        synonyms = 'N/A'

        for spaceit in soup.find_all('div', class_='spaceit_pad'):
            text = spaceit.get_text()

            # Check for English title
            if 'English:' in text and english_title == 'N/A':
                english_match = re.search(r'English:\s*([^\n]+)', text)
                if english_match:
                    english_title = english_match.group(1).strip()

            # Check for Synonyms
            if 'Synonyms:' in text and synonyms == 'N/A':
                synonyms_match = re.search(r'Synonyms:\s*([^\n]+)', text)
                if synonyms_match:
                    synonyms = synonyms_match.group(1).strip()

        # If no English title found, use the main title as English title
        if english_title == 'N/A' and title != 'N/A':
            english_title = title

        # Extract Japanese title
        japanese_title = 'N/A'
        for spaceit in soup.find_all('div', class_='spaceit_pad'):
            text = spaceit.get_text()
            if 'Japanese:' in text:
                japanese_match = re.search(r'Japanese:\s*([^\n]+)', text)
                if japanese_match:
                    japanese_title = japanese_match.group(1).strip()
                    break

        # Extract score
        score = 'N/A'
        score_elem = soup.find('div', {'data-title': 'score'})
        if score_elem:
            score_text = score_elem.get_text(strip=True)
            score_match = re.search(r'([\d\.]+)', score_text)
            if score_match:
                score = score_match.group(1)

        # Extract scored by (number of users who scored)
        scored_by = 'N/A'
        scored_elem = soup.find('span', {'itemprop': 'ratingCount'})
        if scored_elem:
            scored_by = scored_elem.get_text(strip=True).replace(',', '')

        # Extract ranked
        ranked = 'N/A'
        ranked_elem = soup.find('span', string=re.compile('Ranked:', re.I))
        if ranked_elem:
            ranked_parent = ranked_elem.find_parent()
            if ranked_parent:
                ranked_text = ranked_parent.get_text(strip=True)
                ranked_match = re.search(r'#(\d+)', ranked_text)
                if ranked_match:
                    ranked = ranked_match.group(1)

        # Extract popularity
        popularity = 'N/A'
        popularity_elem = soup.find('span', string=re.compile('Popularity:', re.I))
        if popularity_elem:
            popularity_parent = popularity_elem.find_parent()
            if popularity_parent:
                popularity_text = popularity_parent.get_text(strip=True)
                popularity_match = re.search(r'#(\d+)', popularity_text)
                if popularity_match:
                    popularity = popularity_match.group(1)

        # Extract members
        members = 'N/A'
        members_elem = soup.find('span', string=re.compile('Members:', re.I))
        if members_elem:
            members_parent = members_elem.find_parent()
            if members_parent:
                members_text = members_parent.get_text(strip=True)
                members_match = re.search(r'Members:\s*([\d,]+)', members_text)
                if members_match:
                    members = members_match.group(1).replace(',', '')

        # Extract favorites
        favorites = 'N/A'
        favorites_elem = soup.find('span', string=re.compile('Favorites:', re.I))
        if favorites_elem:
            favorites_parent = favorites_elem.find_parent()
            if favorites_parent:
                favorites_text = favorites_parent.get_text(strip=True)
                favorites_match = re.search(r'Favorites:\s*([\d,]+)', favorites_text)
                if favorites_match:
                    favorites = favorites_match.group(1).replace(',', '')

        # Extract type, volumes, chapters
        manga_type = 'N/A'
        volumes = 'N/A'
        chapters = 'N/A'
        status = 'N/A'
        published = 'N/A'

        for spaceit in soup.find_all('div', class_='spaceit_pad'):
            text = spaceit.get_text()

            if 'Type:' in text and manga_type == 'N/A':
                type_match = re.search(r'Type:\s*([^\n]+)', text)
                if type_match:
                    manga_type = type_match.group(1).strip()

            if 'Volumes:' in text and volumes == 'N/A':
                vol_match = re.search(r'Volumes:\s*([^\n]+)', text)
                if vol_match:
                    volumes = vol_match.group(1).strip()

            if 'Chapters:' in text and chapters == 'N/A':
                chap_match = re.search(r'Chapters:\s*([^\n]+)', text)
                if chap_match:
                    chapters = chap_match.group(1).strip()

            if 'Status:' in text and status == 'N/A':
                status_match = re.search(r'Status:\s*([^\n]+)', text)
                if status_match:
                    status = status_match.group(1).strip()

            if 'Published:' in text and published == 'N/A':
                pub_match = re.search(r'Published:\s*([^\n]+)', text)
                if pub_match:
                    published = pub_match.group(1).strip()

        # Extract genres
        genres = []
        genre_spans = soup.find_all('span', {'itemprop': 'genre'})
        for genre_span in genre_spans:
            genres.append(genre_span.get_text(strip=True))
        genres_str = ', '.join(genres) if genres else 'N/A'

        # Extract themes (newer MAL structure)
        themes = []
        theme_section = soup.find('div', string=re.compile('Themes?:', re.I))
        if theme_section:
            theme_parent = theme_section.find_parent()
            if theme_parent:
                theme_links = theme_parent.find_all('a')
                for link in theme_links:
                    if '/manga/genre/' in link.get('href', ''):
                        themes.append(link.get_text(strip=True))
        themes_str = ', '.join(themes) if themes else 'N/A'

        # Extract demographic
        demographic = 'N/A'
        demo_section = soup.find('span', string=re.compile('Demographic:', re.I))
        if demo_section:
            demo_parent = demo_section.find_parent()
            if demo_parent:
                demo_link = demo_parent.find('a')
                if demo_link:
                    demographic = demo_link.get_text(strip=True)

        # Extract serialization
        serialization = 'N/A'
        serial_section = soup.find('span', string=re.compile('Serialization:', re.I))
        if serial_section:
            serial_parent = serial_section.find_parent()
            if serial_parent:
                serial_link = serial_parent.find('a')
                if serial_link:
                    serialization = serial_link.get_text(strip=True)

        # Extract authors
        authors = []
        for spaceit in soup.find_all('div', class_='spaceit_pad'):
            text = spaceit.get_text()
            if 'Authors:' in text or 'Author:' in text:
                author_links = spaceit.find_all('a')
                for link in author_links:
                    if '/people/' in link.get('href', ''):
                        author_text = link.get_text(strip=True)
                        # Remove role in parentheses
                        author_name = re.sub(r'\s*\([^)]*\)', '', author_text)
                        authors.append(author_name)
        authors_str = ', '.join(authors) if authors else 'N/A'

        # Extract synopsis
        synopsis = 'N/A'
        synopsis_elem = soup.find('span', {'itemprop': 'description'})
        if synopsis_elem:
            synopsis = synopsis_elem.get_text(strip=True)
            # Limit length
            synopsis = synopsis[:500]

        # Extract image URL
        image_url = 'N/A'
        image_elem = soup.find('img', {'itemprop': 'image'})
        if image_elem:
            image_url = image_elem.get('data-src', image_elem.get('src', 'N/A'))

        result = {
            'url': url,
            'title': title,
            'english_title': english_title,
            'synonyms': synonyms,
            'japanese_title': japanese_title,
            'type': manga_type,
            'volumes': volumes,
            'chapters': chapters,
            'status': status,
            'published': published,
            'score': score,
            'scored_by': scored_by,
            'ranked': ranked,
            'popularity': popularity,
            'members': members,
            'favorites': favorites,
            'genres': genres_str,
            'themes': themes_str,
            'demographic': demographic,
            'serialization': serialization,
            'authors': authors_str,
            'synopsis': synopsis,
            'image_url': image_url
        }

        return result

    except requests.exceptions.RequestException as e:
        print(f"  Network error: {e}")
        if retry_count < 2:
            print(f"  Retrying in 10 seconds...")
            time.sleep(10)
            return scrape_mal_manga(url, retry_count + 1)
        return None

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        if retry_count < 2:
            print(f"  Retrying in 10 seconds...")
            time.sleep(10)
            return scrape_mal_manga(url, retry_count + 1)
        return None

def meets_criteria(manga_data):
    """
    Check if manga meets criteria.
    Criteria: Members > 1000
    """
    try:
        members = manga_data.get('members', 'N/A')

        # Check members - must be over 1000
        if members != 'N/A':
            try:
                if int(members) > 1000:
                    return True
            except (ValueError, TypeError):
                pass

        # Don't include if members is N/A or <= 1000
        return False

    except Exception:
        return False

def main():
    # Better UTF-8 handling
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # Configuration - try multiple possible paths
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Try different possible locations for the input file
    possible_paths = [
        'resources/myanimelist_urls_manga.csv',  # Default
        os.path.join(script_dir, 'resources/myanimelist_urls_manga.csv'),  # Relative to script
        os.path.join(script_dir, '..', 'resources/myanimelist_urls_manga.csv'),  # Parent dir
        'myanimelist_urls_manga.csv',  # Same directory
        os.path.join(script_dir, 'myanimelist_urls_manga.csv'),  # Same as script
    ]

    urls_file = None
    for path in possible_paths:
        if os.path.exists(path):
            urls_file = path
            break

    if not urls_file:
        print("="*70)
        print("ERROR: Input file not found!")
        print("="*70)
        print("\nSearched in these locations:")
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            print(f"  - {abs_path}")
        print("\nPlease create the file 'myanimelist_urls_manga.csv' with one URL per line.")
        print("Example content:")
        print("  https://myanimelist.net/manga/2/Berserk")
        print("  https://myanimelist.net/manga/13/One_Piece")
        print("\nYou can place the file in any of the locations listed above.")
        print("="*70)
        return

    output_file = os.path.join(os.path.dirname(urls_file), 'mal_manga_data.csv')

    MIN_DELAY = 1.5
    MAX_DELAY = 3.0
    RESET_EVERY = 10

    fieldnames = [
        'url', 'title', 'english_title', 'synonyms', 'japanese_title',
        'type', 'volumes', 'chapters', 'status', 'published',
        'score', 'scored_by', 'ranked', 'popularity', 'members', 'favorites',
        'genres', 'themes', 'demographic', 'serialization',
        'authors', 'synopsis', 'image_url'
    ]

    # Read URLs
    try:
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading {urls_file}: {e}")
        return

    if not urls:
        print(f"Error: No URLs found in {urls_file}")
        print(f"Add manga URLs, one per line. Example:")
        print(f"  https://myanimelist.net/manga/2/Berserk")
        return

    print("="*70)
    print(f"Found {len(urls)} URLs to scrape")
    print(f"Input file: {os.path.abspath(urls_file)}")
    print(f"Output file: {os.path.abspath(output_file)}")
    print(f"Using MyAnimeList (MANGA)")
    print(f"Filter: Members > 1000 (STRICT)")
    print("="*70)
    print()

    with open(output_file, 'w', newline='', encoding='utf-8', buffering=1) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        csvfile.flush()

        success_count = 0
        fail_count = 0
        filtered_count = 0

        for i, url in enumerate(urls, 1):
            if i > 1 and (i - 1) % RESET_EVERY == 0:
                long_delay = random.uniform(3, 6)
                print(f"\n[*] Taking a break: {long_delay:.1f}s...\n")
                time.sleep(long_delay)

            print(f"Processing {i}/{len(urls)}: {url}")

            manga_data = scrape_mal_manga(url)

            if manga_data:
                if meets_criteria(manga_data):
                    writer.writerow(manga_data)
                    csvfile.flush()
                    success_count += 1

                    # Status emoji
                    status = manga_data['status']
                    if 'Publishing' in status:
                        status_emoji = "▶"
                    elif 'Finished' in status:
                        status_emoji = "✓"
                    elif 'On Hiatus' in status:
                        status_emoji = "⏸"
                    elif 'Discontinued' in status:
                        status_emoji = "✗"
                    else:
                        status_emoji = "?"

                    # Display title (prefer English, fallback to main title)
                    display_title = manga_data['english_title'] if manga_data['english_title'] != 'N/A' else manga_data['title']

                    print(f"  [OK] {status_emoji} {display_title}")

                    # Show synonyms if available
                    if manga_data['synonyms'] != 'N/A':
                        print(f"       Synonyms: {manga_data['synonyms']}")

                    print(f"       Score: {manga_data['score']} (by {manga_data['scored_by']} users) | Chapters: {manga_data['chapters']} | Volumes: {manga_data['volumes']}")
                    print(f"       Members: {manga_data['members']} | Ranked: #{manga_data['ranked']} | Popularity: #{manga_data['popularity']}")
                else:
                    filtered_count += 1
                    display_title = manga_data['english_title'] if manga_data['english_title'] != 'N/A' else manga_data['title']
                    mem = manga_data.get('members', 'N/A')
                    print(f"  [SKIP] {display_title} (Members: {mem} ≤ 1000)")
            else:
                fail_count += 1
                print(f"  [FAIL] Could not scrape")

            if i < len(urls):
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)

        print(f"\n{'='*50}")
        print(f"Complete! Data saved to {output_file}")
        print(f"Saved: {success_count} | Filtered: {filtered_count} | Failed: {fail_count}")
        print(f"{'='*50}")

if __name__ == "__main__":
    main()