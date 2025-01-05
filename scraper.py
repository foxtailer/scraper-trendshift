import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import lxml
import re
from datetime import datetime, timedelta
import json
import os


# Create a new log file
script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
log_id = 1
while os.path.exists(os.path.join(script_dir, f"log_{log_id}.txt")):
    log_id += 1

log_file_path = os.path.join(script_dir, f"log_{log_id}.txt")
log_file = open(log_file_path, "w")


# Create SQLite database and tables
conn = sqlite3.connect(script_dir + 'github_repos.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS language (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS repository (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    github TEXT,
    website TEXT,
    description TEXT,
    trendshift_id INTEGER,
    lang_id INTEGER,
    stars INTEGER,
    forks INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lang_id) REFERENCES language(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ranking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER,
    rank_date DATE,
    rank INTEGER,
    lang_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repository_id) REFERENCES repository(id),
    FOREIGN KEY (lang_id) REFERENCES language(id)
)
''')

conn.commit()

# Function to get data from the page
def get_data_from_page(page_id):
    url = f"https://trendshift.io/repositories/{page_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0'}
    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'

    if response:
        soup = BeautifulSoup(response.text, 'lxml')

        data = {
            'name': '',
            'github': '',
            'website': '',
            'description': '',
            'trendshift_id': 0,
            'lang': '',
            'stars': 0,
            'forks': 0,
            'ranks': None
        }

        # Find trendshift_id
        data['trendshift_id'] = page_id

        # Find stars and forks
        stars_forks_div = soup.find('div', class_='flex items-center space-x-3 text-xs text-gray-500')

        if stars_forks_div:
            stars_forks = stars_forks_div.find_all('div')
            data['stars'] = convert_to_number(stars_forks[0].text)
            data['forks'] = convert_to_number(stars_forks[1].text)

        # Find description
        description_div = soup.find('div', class_='text-sm text-gray-500')
        if description_div.text:
            data['description'] = description_div.text
        else:
            data['description'] = None

        # Find links
        link_div = soup.find('div', class_='text-xs mb-2 flex items-center font-medium text-yellow-700 space-x-3')
        data['github'], data['website'] = None, None

        if link_div:
            links = link_div.find_all('a')
            for link in links:
                if link.text == "Visit GitHub":
                    data['github'] = link['href']
                elif link.text == "Website":
                    data['website'] = link['href']
        
        # Find name and language
        name_lang_div = soup.find('div', class_='flex items-center text-indigo-400 text-lg justify-between mb-1')

        if name_lang_div:
            name_lang = name_lang_div.find_all('div')
            data['name'] = name_lang[0].text
            
            if len(name_lang) > 1:
                data['lang'] = name_lang[1].text

        # Find ranking
        regex = r'\\"trendings\\"\s*:\s*\[(.*?)\]'
        match = re.search(regex, response.text, re.DOTALL)

        if match:
            ranks_str = '[' + match.group(1).replace("\\", "") + ']'
            ranks_list = json.loads(ranks_str)
        else:
            print('No match found.')

        data['ranks'] = ranks_list

        return data
    else:
        return None


def save_to_db(data):
    # language Table
    if data['lang']:
        cursor.execute("INSERT OR IGNORE INTO language (name) VALUES (?)", (data['lang'],))
        cursor.execute("SELECT id FROM language WHERE name = ?", (data['lang'],))
        lang_id = cursor.fetchone()[0]
    else:
        lang_id = 0

    # repository Table
    current_time = datetime.now()
    twenty_four_hours_ago = current_time - timedelta(hours=24)
    # Convert datetime to string format compatible with SQL
    current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    twenty_four_hours_ago_str = twenty_four_hours_ago.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
                SELECT id, updated_at FROM repository
                WHERE trendshift_id = ?
    ''', (data['trendshift_id'],))
    result = cursor.fetchone()

    if result:
        repo_id, updated_at = result
        if updated_at < twenty_four_hours_ago_str:
            cursor.execute('''
            UPDATE repository
            SET name = ?, github = ?, website = ?, description = ?, lang_id = ?, stars = ?, forks = ?, updated_at = ?
            WHERE id = ?
            ''', (data['name'], data['github'], data['website'], data['description'], lang_id, data['stars'], data['forks'], current_time_str, repo_id))
    else:
        cursor.execute('''
        INSERT INTO repository (name, github, website, description, trendshift_id, lang_id, stars, forks, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['github'], data['website'], data['description'], data['trendshift_id'], lang_id, data['stars'], data['forks'], current_time_str, current_time_str))

    repo_id = cursor.lastrowid

    # rancing Table
    for chart_point in data['ranks']:
        rank_date = chart_point['trend_date'][:10]  # Strip time

        if not chart_point['trending_language']:
            lang_id = 0

        cursor.execute("INSERT INTO ranking (repository_id, rank_date, rank, lang_id) VALUES (?, ?, ?, ?)",
                   (repo_id, rank_date, chart_point['rank'], lang_id))

    conn.commit()


def convert_to_number(value):
    value = value.strip()

    if 'k' in value:
        return int(float(value.replace('k', '')) * 1000)
    elif 'M' in value:
        return int(float(value.replace('M', '')) * 1000000)
    else:
        return int(value)


# Main loop
error_count = 0
page_id = 1

#while error_count < 5 and page_id == 5:
while error_count < 5:
    try:
        data = get_data_from_page(page_id)

        if data:
            save_to_db(data)
            log_message = f"Page {page_id} processed successfully."
            log_file.write(log_message + "\n")
            log_file.flush()
            print(log_message)
            error_count = 0  # reset error count on success
        else:
            log_message = f"Error fetching page {page_id}"
            log_file.write(log_message + "\n")
            log_file.flush()
            print(log_message)
            error_count += 1
    except Exception as e:
        log_message = f"Page {page_id} Error: {str(e)}"
        log_file.write(log_message + "\n")

    
    page_id += 1
    time.sleep(1)  # delay to handle server request limits

# Close the log file and database connection
log_file.close()
conn.close()
