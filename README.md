# Scraper-TrendShift

A script to collect data about repositories and save it to an SQLite database.

## Features
- Navigate through pages by changing the ID in the URL (e.g., `site.com/page/1`, `site.com/page/2`, etc.).
- The target website is not protected by bot protection, ensuring smooth scraping.
- Check if the current record exists in the database:
  - If the record exists, update it.
  - If the record does not exist, create a new record.
- Continue working until 5 consecutive errors occur for 5 page IDs.

## Database Structure
The data is organized into three tables: **language**, **ranking**, and **repository**.

### `language` Table
| id | name |

### `ranking` Table
| id | repository_id | rank_date | rand | lang_id | created_at | updated_at |

### `repository` Table
| id | name | github | website | description | trendshift_id | lang_id | stats | forks | created_at | updated_at |


# Run

1. Navigate to the `scraper` folder.
2. Create a Docker image using the command: `docker build -t scraper:01 .`
3. Run the container with the following command: `docker run --rm -v /host/folder:/app scraper:01`

The log and database files will be saved in `/host/folder`.
