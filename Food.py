import csv
import time
import random
import os
import math
import re
from bs4 import BeautifulSoup


# Install this first: pip install curl-cffi
try:
    from curl_cffi import requests
except ImportError:
    print("ERROR: Please install curl-cffi first:")
    print("pip install curl-cffi")
    exit(1)


def scrape_nutrition_facts(url, retry_count=0):
    """
    Scrape nutrition facts from recipe websites.
    Works with AllRecipes, BBC Good Food, and other sites using schema.org Recipe format.
    """
    try:
        # Use curl_cffi with Chrome impersonation
        response = requests.get(
            url,
            impersonate="chrome120",  # Mimics real Chrome browser
            timeout=15
        )

        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all JSON-LD script tags
        script_tags = soup.find_all('script', type='application/ld+json')

        recipe_data = None

        # Look through all JSON-LD blocks to find the Recipe
        for script_tag in script_tags:
            if not script_tag.string:
                continue

            try:
                import json
                data = json.loads(script_tag.string)

                # Handle if data is a list
                if isinstance(data, list):
                    # Look for Recipe type in the list
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe':
                            recipe_data = item
                            break
                # Handle if data is a single object
                elif isinstance(data, dict):
                    if data.get('@type') == 'Recipe':
                        recipe_data = data
                    # Sometimes nested in @graph
                    elif '@graph' in data:
                        for item in data['@graph']:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                recipe_data = item
                                break

                if recipe_data:
                    break
    
            except (json.JSONDecodeError, KeyError):
                continue

        if recipe_data:
            # Extract recipe name
            recipe_name = recipe_data.get('name', 'N/A')
    
            # Extract total time (multiple possible fields)
            total_time = recipe_data.get('totalTime') or recipe_data.get('cookTime') or recipe_data.get('prepTime', 'N/A')
            if total_time != 'N/A':
                total_time = convert_iso_duration(total_time)
    
            # Extract ingredients (handle both list and string formats)
            ingredients = recipe_data.get('recipeIngredient', [])
            if not ingredients:
                ingredients = recipe_data.get('ingredients', [])
    
            if isinstance(ingredients, list) and ingredients:
                ingredients_str = '; '.join(str(i) for i in ingredients)
            elif isinstance(ingredients, str):
                ingredients_str = ingredients
            else:
                ingredients_str = 'N/A'
    
            # Extract nutrition info (can be nested differently)
            nutrition = recipe_data.get('nutrition', {})
            if not isinstance(nutrition, dict):
                nutrition = {}
    
            # Extract rating and review count from JSON-LD
            aggregate_rating = recipe_data.get('aggregateRating', {})
            if not isinstance(aggregate_rating, dict):
                aggregate_rating = {}
    
            # Try multiple field names for rating value
            rating = (aggregate_rating.get('ratingValue') or 
                     aggregate_rating.get('averageRating') or 
                     'N/A')
    
            # Try ratingCount FIRST (total ratings), then reviewCount (written reviews)
            review_count = (aggregate_rating.get('ratingCount') or 
                           aggregate_rating.get('reviewCount') or 
                           aggregate_rating.get('count') or
                           'N/A')
    
            # ALWAYS check page source for alternative rating formats
            # Many sites have the real rating in JavaScript, not JSON-LD
    
            # Check JavaScript object format - rating:{value:4.54,count:316}
            js_ratings = extract_js_ratings(response.text)
            if js_ratings:
                # Prefer JS ratings if JSON-LD has placeholder (5 or 5.0)
                if rating in ('N/A', 5, '5', 5.0, '5.0'):
                    rating = js_ratings.get('value', rating)
                if review_count == 'N/A':
                    review_count = js_ratings.get('count', review_count)
    
            # Check food.com format - ratingvalue4.54,count316  
            foodcom_ratings = extract_foodcom_ratings(response.text)
            if foodcom_ratings:
                if rating in ('N/A', 5, '5', 5.0, '5.0'):
                    rating = foodcom_ratings.get('value', rating)
                if review_count == 'N/A':
                    review_count = foodcom_ratings.get('count', review_count)
    
            # Check BBC Good Food format - "userRatings":{"avg":4.7,"total":250}
            bbc_ratings = extract_bbc_ratings(response.text)
            if bbc_ratings:
                if rating in ('N/A', 5, '5', 5.0, '5.0'):
                    rating = bbc_ratings.get('avg', rating)
                if review_count == 'N/A':
                    review_count = bbc_ratings.get('total', review_count)
    
            # Helper function to extract numeric value
            def extract_number(value):
                if value == 'N/A' or not value:
                    return 'N/A'
                try:
                    # Handle if already a number
                    if isinstance(value, (int, float)):
                        return str(value)
                    # Extract just the number part from strings
                    return ''.join(filter(lambda x: x.isdigit() or x == '.', str(value)))
                except:
                    return value
    
            nutrition_data = {
                'url': url,
                'name': recipe_name,
                'total_time': total_time,
                'rating_value': rating,
                'rating_count': review_count,
                'calories': extract_number(nutrition.get('calories', 'N/A')),
                'fat_g': extract_number(nutrition.get('fatContent', 'N/A')),
                'sat_fat_g': extract_number(nutrition.get('saturatedFatContent', 'N/A')),
                'sugar_g': extract_number(nutrition.get('sugarContent', 'N/A')),
                'fiber_g': extract_number(nutrition.get('fiberContent', 'N/A')),
                'cholesterol_mg': extract_number(nutrition.get('cholesterolContent', 'N/A')),
                'sodium_mg': extract_number(nutrition.get('sodiumContent', 'N/A')),
                'carbs_g': extract_number(nutrition.get('carbohydrateContent', 'N/A')),
                'protein_g': extract_number(nutrition.get('proteinContent', 'N/A')),
                'ingredients': ingredients_str,
            }
    
            return nutrition_data

        # Fallback: No Recipe schema found
        print("Warning: No Recipe schema found on page")
        nutrition_data = {
            'url': url,
            'name': soup.find('h1').get_text(strip=True) if soup.find('h1') else 'N/A',
            'total_time': 'N/A',
            'rating_value': 'N/A',
            'rating_count': 'N/A',
            'calories': 'N/A',
            'fat_g': 'N/A',
            'sat_fat_g': 'N/A',
            'sugar_g': 'N/A',
            'fiber_g': 'N/A',
            'cholesterol_mg': 'N/A',
            'sodium_mg': 'N/A',
            'carbs_g': 'N/A',
            'protein_g': 'N/A',
            'ingredients': 'N/A',
        }

        return nutrition_data

    except Exception as e:
        print(f"Error scraping {url}: {e}")

        # Retry once with longer delay
        if retry_count < 1:
            print(f"Retrying in 10 seconds...")
            time.sleep(10)
            return scrape_nutrition_facts(url, retry_count + 1)

        return None


def extract_bbc_ratings(html_content):
    """
    Extract ratings from BBC Good Food's userRatings format.
    Looks for: "userRatings":{"avg":4.7,"total":250,...}
    """
    try:
        import json
        # Search for the userRatings pattern in the HTML
        pattern = r'"userRatings":\s*(\{[^}]+\})'
        match = re.search(pattern, html_content)

        if match:
            ratings_json = match.group(1)
            ratings_data = json.loads(ratings_json)
            return {
                'avg': ratings_data.get('avg'),
                'total': ratings_data.get('total')
            }
    except Exception as e:
        pass
    
    return None


def extract_js_ratings(html_content):
    """
    Extract ratings from JavaScript object format.
    Looks for: rating:{value:4.54,count:316}
    """
    try:
        # Search for the rating pattern (with or without quotes)
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


def extract_foodcom_ratings(html_content):
    """
    Extract ratings from food.com format.
    Looks for: ratingvalue4.54,count316
    or: rating{value:4.54,count:316}
    """
    try:
        # Pattern 1: ratingvalue4.54,count316 (no separators)
        pattern1 = r'rating[:\s]*value[:\s]*([0-9.]+)\s*,\s*count[:\s]*([0-9]+)'
        match = re.search(pattern1, html_content, re.IGNORECASE)

        if match:
            return {
                'value': float(match.group(1)),
                'count': int(match.group(2))
            }
    except Exception as e:
        pass
    
    return None


def convert_iso_duration(duration):
    """
    Convert ISO 8601 duration (e.g., "PT1H30M") to readable format (e.g., "1h 30m")
    """
    if not duration or duration == 'N/A':
        return 'N/A'
    
    try:
        # Remove PT prefix
        duration = str(duration).replace('PT', '')

        hours = 0
        minutes = 0

        # Extract hours
        if 'H' in duration:
            hours = int(duration.split('H')[0])
            duration = duration.split('H')[1]

        # Extract minutes
        if 'M' in duration:
            minutes = int(duration.split('M')[0])

        # Format output
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return 'N/A'
    except:
        return duration  # Return as-is if parsing fails


def meets_criteria(nutrition_data):
    """
    Check if recipe meets quality criteria using custom formula.
    Formula: (rating - 4.5)*10 + log(review_count/1000) > 0
    """
    try:
        rating = nutrition_data.get('rating_value')
        review_count = nutrition_data.get('rating_count')

        # Convert to numbers, handle N/A
        if rating == 'N/A' or review_count == 'N/A':
            return False

        rating = float(rating)
        review_count = int(review_count)

        # Avoid log domain error (review_count must be > 0)
        if review_count <= 0:
            return False

        # Apply your formula
        score = (rating - 4.5) * 10 + math.log(review_count / 1000,2)
        return score > 0

    except (ValueError, TypeError, ZeroDivisionError):
        return False


def main():
    # Force UTF-8 on Windows
    import sys
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    
    # ========== CONFIGURATION ==========
    urls_file = 'resources/colombian.csv'
    output_file = 'resources/nutrition_data.csv'
    
    # Anti-blocking settings (more conservative)
    MIN_DELAY = 1   # Minimum seconds between requests
    MAX_DELAY = 2  # Maximum seconds between requests
    RESET_EVERY = 5  # Take a longer break every N requests


    # Define CSV columns in your specified order
    fieldnames = [
        'url', 'name', 'total_time', 'rating_value', 'rating_count', 
        'calories', 'fat_g', 'sat_fat_g', 'sugar_g', 'fiber_g', 
        'cholesterol_mg', 'sodium_mg', 'carbs_g', 'protein_g', 'ingredients'
    ]


    # Create resources directory if it doesn't exist
    os.makedirs('resources', exist_ok=True)


    # Read URLs from file
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
    print(f"Filter: Custom formula (rating - 4.5)*10 + log(reviews/1000) > 0")
    print(f"Output will be saved to: {output_file}\n")


    # Open CSV file for writing
    with open(output_file, 'w', newline='', encoding='utf-8', buffering=1) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        csvfile.flush()


        success_count = 0
        fail_count = 0
        filtered_count = 0


        for i, url in enumerate(urls, 1):
            # Take longer break every N requests
            if i > 1 and (i - 1) % RESET_EVERY == 0:
                long_delay = random.uniform(15, 25)/10
                print(f"\n[*] Taking a longer break: {long_delay:.1f}s...\n")
                time.sleep(long_delay)


            print(f"Processing {i}/{len(urls)}: {url}")


            nutrition_data = scrape_nutrition_facts(url)


            if nutrition_data:
                # Check if recipe meets criteria
                if meets_criteria(nutrition_data):
                    writer.writerow(nutrition_data)
                    csvfile.flush()
                    success_count += 1
                    print(f"[OK] Saved: {nutrition_data['name']} | Time: {nutrition_data['total_time']} | Rating: {nutrition_data['rating_value']} ({nutrition_data['rating_count']} reviews)")
                else:
                    filtered_count += 1
                    print(f"[SKIP] Filtered out: {nutrition_data['name']} (Rating: {nutrition_data['rating_value']}, Reviews: {nutrition_data['rating_count']})")
            else:
                fail_row = {field: '' for field in fieldnames}
                fail_row['url'] = url  # Assuming 'url' is one of your fieldnames
                writer.writerow(fail_row)
                csvfile.flush()
                fail_count += 1
                print(f"[FAIL] Could not scrape {url}")

            # Random delay between requests
            if i < len(urls):
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)


    print(f"\n{'='*50}")
    print(f"Complete! Data saved to {output_file}")
    print(f"Saved: {success_count} | Filtered: {filtered_count} | Failed: {fail_count}")
    print(f"{'='*50}")



if __name__ == "__main__":
    main()
