import os
from dotenv import load_dotenv

load_dotenv()

# Apify API Configuration
# Token ini digunakan oleh apify_scraper.py untuk mengakses Instagram Scraper
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
