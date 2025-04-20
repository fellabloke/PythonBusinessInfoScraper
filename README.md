# PythonBusinessInfoScraper
Overview:
This Python script automates the extraction of business information from Google Maps search results. It uses Playwright for browser automation to collect business names, addresses, websites, and phone numbers, then organizes this data into CSV files for easy analysis.

Features:
Automated Data Collection: Extracts business details from Google Maps search results
Duplicate Detection: Ensures no duplicate business entries are stored
Batch Processing: Process multiple search terms from a file
Consent Dialog Management: Automatically handles cookie consent popups
Master List Tracking: Maintains a master list of businesses without websites

Prerequisites:
Python 3.8 or higher
Playwright for Python
Pandas

Installation:
Clone this repository:

git clone https://github.com/fellabloke/PythonBusinessInfoScraper.git

cd PythonBusinessInfoScraper

Set up a virtual environment:

python -m venv venv

Activate the virtual environment:

Windows: venv\Scripts\activate

macOS/Linux: source venv/bin/activate

Install the required packages:

pip install -r requirements.txt

Install Playwright browsers:

playwright install chromium

Usage:

Command Line Options:

-s, --search: Specify a single search term
-t, --total: Maximum number of results to collect (default: 1,000,000)

Examples
Search for coffee shops in New York:
python BusinessInfoScraper.py -s "coffee shops in New York"
Search for multiple terms defined in input.txt with a limit of 50 results each:
python BusinessInfoScraper.py -t 50

Input File Format
Create a file named input.txt in the same directory as the script, with each search term on a new line:
coffee shops in New York
restaurants in Chicago
dentists in Los Angeles
Output
The script creates CSV files in the output directory:

Individual files for each search query with timestamps
A master list of businesses without websites (businesses_without_websites_master.csv)

CSV columns include:

name: Business name
address: Physical address
website: Business website URL
phone_number: Contact phone number
error_message: Any errors encountered during scraping

Limitations:

Google Maps may change its UI structure, potentially breaking selectors
Excessive scraping may trigger Google's anti-bot measures
Some businesses may not have complete information available

Troubleshooting
If you encounter issues:

Check the debug_screenshots directory for visual debugging information
Ensure your internet connection is stable
Try reducing the number of results requested
Check if Google has updated its interface

License
MIT License
Disclaimer
This project is not affiliated with, authorized by, endorsed by, or in any way officially connected with Google or Google Maps. Google and Google Maps are trademarks of Google LLC.
The use of web scraping tools may violate the Terms of Service of websites. Use at your own risk and responsibility.
