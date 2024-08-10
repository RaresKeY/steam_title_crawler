"""
MIT License

Copyright (c) 2024 RaresKey

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import requests
from bs4 import BeautifulSoup
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime


# Database setup
def get_db_connection():
    conn = sqlite3.connect('steam_games.db')
    return conn


def create_table_for_current_datetime():
    """Create a table for the current datetime."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get current date and hour
    now = datetime.datetime.now(datetime.UTC)
    table_name = now.strftime('%Y%m%d_%H%M%S')

    # Create table with current date and hour as name
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price TEXT,
            currency TEXT,
            url TEXT
        )
    ''')
    conn.commit()
    conn.close()

    return table_name


def insert_data_into_table(table_name, games_details):
    """Insert data into the specified table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for game in games_details:
        cursor.execute(f'''
            INSERT INTO "{table_name}" (name, price, currency, url) VALUES (?, ?, ?, ?)
        ''', (game['name'], game['price'], game['currency'], game['url']))

    conn.commit()
    conn.close()


def fetch_page(url):
    """Fetch a single page and return its content."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def parse_page(content):
    """Parse a page's content and extract game details."""
    if not content:
        return []

    soup = BeautifulSoup(content, 'html.parser')
    games_details = []

    search_results = soup.find_all('a', {'class': 'search_result_row'})

    for result in search_results:
        # Extract game name
        game_name_div = result.find('span', {'class': 'title'})
        if game_name_div:
            game_name = game_name_div.get_text(strip=True)
        else:
            continue

        # Extract game URL
        game_url = result['href']

        # Extract price and currency
        price_div = result.find('div', {'class': 'discount_final_price'})
        if price_div:
            price_text = price_div.get_text(strip=True)

            # Extract price and currency using regex
            match = re.match(r'([\d.,]+)([^\d.,]+)', price_text)
            if match:
                price = match.group(1)
                currency = match.group(2).strip()
            else:
                price = "0,--"
                currency = "€"
        else:
            price = "0,--"
            currency = "€"

        # Append the details to the list
        games_details.append({
            'name': game_name,
            'price': price,
            'currency': currency,
            'url': game_url,
        })

    return games_details


def get_steam_games_parallel(base_url, count_per_page=100, max_pages=5):
    """Fetch and parse multiple pages in parallel."""
    all_games_details = []
    urls = [f"{base_url}&count={count_per_page}&page={page}" for page in range(1, max_pages + 1)]

    with ThreadPoolExecutor(max_workers=50) as executor:
        future_to_url = {executor.submit(fetch_page, url): url for url in urls}

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                content = future.result()
                games_details = parse_page(content)
                all_games_details.extend(games_details)
            except Exception as e:
                print(f"Error processing {url}: {e}")

    return all_games_details


# Base URL for the search results page
search_url = "https://store.steampowered.com/search/?sort_by=Name_ASC"

# Fetch and print items
games = get_steam_games_parallel(search_url, count_per_page=100, max_pages=50)

# Create table with current date and hour
table_name_o = create_table_for_current_datetime()

# Insert data into the table
insert_data_into_table(table_name_o, games)

print(f"Data successfully stored in table '{table_name_o}'")
