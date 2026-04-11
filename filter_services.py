#!/usr/bin/env python3
"""
Filter service URLs to only those belonging to users in the users CSV file.
Usage: python filter_services.py <services_file> <users_csv> <output_file>
"""

import sys
import csv

def load_user_urls(users_csv):
    user_urls = set()
    with open(users_csv, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row['url'].strip().rstrip('/')
            user_urls.add(url)
    return user_urls

def filter_services(services_file, user_urls, output_file):
    kept = []
    skipped = 0

    with open(services_file, encoding='utf-8') as f:
        for line in f:
            service_url = line.strip()
            if not service_url:
                continue

            # Extract base user URL: https://vgen.co/<username>
            parts = service_url.split('/')
            # ['https:', '', 'vgen.co', '<username>', 'service', ...]
            if len(parts) >= 4:
                base_url = '/'.join(parts[:4]).rstrip('/')
            else:
                base_url = service_url

            if base_url in user_urls:
                kept.append(service_url)
            else:
                skipped += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        for url in kept:
            f.write(url + '\n')

    return len(kept), skipped

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python filter_services.py <services_file> <users_csv> <output_file>")
        sys.exit(1)

    services_file, users_csv, output_file = sys.argv[1], sys.argv[2], sys.argv[3]

    user_urls = load_user_urls(users_csv)
    print(f"Loaded {len(user_urls)} user URLs from '{users_csv}'")

    kept, skipped = filter_services(services_file, user_urls, output_file)
    print(f"Kept {kept} service URLs, skipped {skipped}")
    print(f"Output saved to '{output_file}'")