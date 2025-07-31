# Avito Opportunity Hunter Bot

A powerful Python bot that automates the search for real estate opportunities on Avito.ma. This tool constantly monitors new listings and sends instant Telegram notifications for properties that match specific, user-defined criteria.

## The Problem It Solves

Real estate agents, investors, and individuals in Morocco waste hours every day manually searching for the best rental or sale deals. The best opportunities are often gone within minutes. This bot solves that problem by providing a significant speed advantage.

## Key Features

- **Automated Scraping:** Continuously scrapes Avito.ma for new apartment listings.
- **Intelligent Filtering:** Filters listings based on price, location, and keywords.
- **Instant Notifications:** Sends formatted, easy-to-read alerts directly to your Telegram.
- **Duplicate Prevention:** Uses a local SQLite database to ensure you only get notified about each opportunity once.

## Tech Stack

- **Language:** Python
- **Libraries:** `requests`, `BeautifulSoup4`, `sqlite3`
- **Platform:** Runs 24/7 on cloud platforms like Replit.

## How to Use
1. Clone the repository.
2. Install the required libraries: `pip install requests beautifulsoup4`
3. Create a Telegram bot and get the API token and your Chat ID.
4. Fill in your credentials in the script.
5. Run the script: `python main.py`
6. 
