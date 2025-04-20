from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys
import re
import time
from datetime import datetime
import json

# Business Data Scraping Classes
@dataclass
class Business:
    """Holds business data"""
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    error_message: str = ''

@dataclass
class BusinessList:
    """Holds list of Business objects and saves to CSV"""
    business_list: list[Business] = field(default_factory=list)
    save_at: str = 'output'
    # Added a set to track unique business names to prevent duplicates
    _unique_businesses: set = field(default_factory=set)

    def add_business(self, business):
        """Add a business to the list only if it's not a duplicate"""
        # Use name and address as a unique identifier (if both exist)
        if business.name and business.address:
            unique_id = f"{business.name}_{business.address}"
        elif business.name:  # If only name exists
            unique_id = f"{business.name}_noaddress"
        else:  # If neither exists (unlikely but possible)
            unique_id = f"unknown_{len(self.business_list)}"
            
        if unique_id not in self._unique_businesses:
            self._unique_businesses.add(unique_id)
            self.business_list.append(business)
            return True
        return False

    def dataframe(self):
        """Convert business list to pandas DataFrame"""
        # Create list of dictionaries
        data = []
        for business in self.business_list:
            data.append({
                'name': business.name,
                'address': business.address,
                'website': business.website,
                'phone_number': business.phone_number,
                'error_message': business.error_message
            })
        # Create DataFrame directly from list of dicts
        return pd.DataFrame(data)

    def save_to_csv(self, filename):
        """Save business data to CSV file"""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
            
        file_path = f"{self.save_at}/{filename}.csv"
        
        if len(self.business_list) > 0:
            df = self.dataframe()
            df.to_csv(file_path, index=False)
            print(f"Data saved successfully to {file_path} with {len(self.business_list)} records.")
        else:
            # Create empty file with headers
            pd.DataFrame(columns=['name', 'address', 'website', 'phone_number', 'error_message']).to_csv(file_path, index=False)
            print(f"Warning: No businesses found. Empty CSV created at {file_path}")

# Sanitize the filename by removing invalid characters
def sanitize_filename(filename):
    """Sanitize the filename by removing invalid characters."""
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()

def setup_persistent_context(playwright):
    """
    Create a persistent context with pre-accepted cookies
    This method bypasses cookie popups by setting cookies directly
    """
    print("Setting up a persistent browser context with pre-accepted cookies...")
    
    # Create a user data directory if it doesn't exist
    user_data_dir = os.path.join(os.getcwd(), "browser_data")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    
    # Create persistent browser context with explicit cookie acceptance
    browser = playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=True,
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
        accept_downloads=True,
        locale='en-US',
        # Set permissions to allow everything
        permissions=['geolocation', 'notifications'],
        # Skip service workers which may block UI access
        args=[
            '--disable-blink-features=AutomationControlled',  # Make automation less detectable
            '--disable-features=IsolateOrigins,site-per-process',  # Disable site isolation
            '--disable-site-isolation-trials'
        ]
    )
    
    # Create a page within this context
    page = browser.new_page()
    
    # Set cookies to bypass consent (pre-accepting common consent cookies)
    google_cookies = [
        {
            'name': 'CONSENT', 
            'value': 'YES+cb.20210720-07-p0.en+FX+410', 
            'domain': '.google.com',
            'path': '/'
        },
        {
            'name': 'SOCS',
            'value': 'CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA1X3AxGgJlbiACGgYIgJnNpAY',
            'domain': '.google.com',
            'path': '/'
        }
    ]
    
    # Add cookies directly to the context
    context_cookies = browser.cookies()
    context_cookies.extend(google_cookies)
    browser.add_cookies(google_cookies)
    
    print("Browser context set up with pre-accepted cookies")
    return browser, page

def handle_consent_actively(page):
    """
    Actively handles consent dialogs using JavaScript injection and aggressive clicking
    """
    print("Actively handling consent dialogs...")
    
    # First try: Check if we're on consent.google.com and handle it
    if "consent.google.com" in page.url:
        print("Detected consent.google.com - using aggressive approach")
        
        # Try to inject consent acceptance via JavaScript (works on many Google consent pages)
        try:
            page.evaluate("""() => {
                // Try to click any visible "Accept all" button using various approaches
                const acceptButtons = [
                    document.querySelector('button[jsname="higCR"]'),
                    document.querySelector('button[aria-label*="Accept"]'), 
                    document.querySelector('button[aria-label*="agree"]'),
                    document.querySelector('button[jsname="j6LnYe"]'),
                    document.querySelector('button:nth-child(1)'),
                    ...Array.from(document.querySelectorAll('button'))
                        .filter(el => el.textContent.includes('Accept') || 
                                el.textContent.includes('Agree') || 
                                el.textContent.includes('I agree') || 
                                el.textContent.includes('Accept all'))
                ];
                
                // Click the first valid button found
                for (let btn of acceptButtons) {
                    if (btn && btn.offsetParent !== null) {
                        btn.click();
                        return true;
                    }
                }
                
                // If no button clicked yet, try a more aggressive approach
                document.querySelectorAll('form button').forEach(btn => btn.click());
                return false;
            }""")
            
            # Wait to see if we navigate away from consent page
            page.wait_for_timeout(3000)
            
            # If still on consent page, try clicking all buttons sequentially
            if "consent.google.com" in page.url:
                print("Still on consent page. Trying to click all buttons sequentially...")
                buttons = page.locator('button').all()
                for i, button in enumerate(buttons):
                    try:
                        print(f"Trying button {i+1}/{len(buttons)}")
                        button.click(force=True)  # Force click even if not strictly visible
                        page.wait_for_timeout(1000)
                        # Check if we navigated away
                        if "consent.google.com" not in page.url:
                            print("Successfully navigated away from consent page!")
                            return True
                    except Exception:
                        continue
                        
            # If we got here, we've likely navigated away from consent.google.com
            if "consent.google.com" not in page.url:
                print("Successfully handled consent page!")
                return True
                
        except Exception as e:
            print(f"Error during JavaScript consent handling: {e}")
    
    # Second try: Handle in-page consent dialogs (after getting past the initial consent page)
    try:
        # Common consent dialog selectors
        consent_buttons = [
            "#L2AGLb",  # Google's primary consent button 
            ".tHlp8d", 
            "[aria-label='Accept all']",
            "[aria-label='I agree']",
            "button:has-text('Accept all')", 
            "button:has-text('Accept')",
            "button:has-text('Agree')",
            "button:has-text('I agree')",
            "button.VfPpkd-LgbsSe"  # Generic material button class
        ]
        
        for button in consent_buttons:
            if page.locator(button).count() > 0:
                try:
                    print(f"Clicking in-page consent button: {button}")
                    page.locator(button).click(force=True)
                    page.wait_for_timeout(1000)
                    print("In-page cookie consent handled.")
                    return True
                except Exception as e:
                    print(f"Failed to click {button}: {e}")
    
        # Try clicking any buttons with accept text using JS (more reliable than selectors)
        page.evaluate("""() => {
            const acceptButtons = Array.from(document.querySelectorAll('button'))
                .filter(el => 
                    el.textContent.toLowerCase().includes('accept') || 
                    el.textContent.toLowerCase().includes('agree') ||
                    el.textContent.toLowerCase().includes('got it')
                );
            
            for (let btn of acceptButtons) {
                if (btn && btn.offsetParent !== null) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }""")
        
    except Exception as e:
        print(f"Error handling in-page consent: {e}")
    
    # If we reached here, either no dialog was found or we handled it
    print("Consent handling complete")
    return True

def initialize_google_maps(page):
    """
    Completely initialize Google Maps with robust error handling
    Uses multiple strategies to ensure Maps is properly loaded
    """
    max_attempts = 5
    success = False
    
    for attempt in range(max_attempts):
        try:
            print(f"\nAttempt {attempt+1}/{max_attempts} to initialize Google Maps...")
            
            # First try to go to Google Maps homepage
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_timeout(5000)  # Wait longer for page to stabilize
            
            # Handle consent dialogs aggressively
            handle_consent_actively(page)
            
            # If we ended up on consent.google.com, try direct navigation to maps
            if "consent.google.com" in page.url:
                print("Still on consent page. Trying direct navigation...")
                page.goto("https://www.google.com/maps", timeout=60000)
                page.wait_for_timeout(3000)
                handle_consent_actively(page)
            
            # Check if we're on Google Maps by looking for the search box
            search_box_visible = page.locator('#searchboxinput').is_visible()
            
            if search_box_visible:
                print("Google Maps loaded successfully! Search box is visible.")
                
                # Take a screenshot to confirm (useful for debugging)
                screenshot_dir = "debug_screenshots"
                if not os.path.exists(screenshot_dir):
                    os.makedirs(screenshot_dir)
                page.screenshot(path=f"{screenshot_dir}/maps_loaded_{attempt+1}.png")
                
                # Clear any potential search history/dialogs
                try:
                    # Clear search box if it has text
                    if page.locator('#searchboxinput').input_value():
                        page.locator('#searchboxinput').fill("")
                        page.wait_for_timeout(500)
                        
                    # Press Escape to dismiss any dialogs
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                except Exception:
                    pass
                
                success = True
                break
            else:
                print("Search box not found or not visible.")
                # Take a screenshot to help debug
                screenshot_dir = "debug_screenshots"
                if not os.path.exists(screenshot_dir):
                    os.makedirs(screenshot_dir)
                page.screenshot(path=f"{screenshot_dir}/maps_failed_{attempt+1}.png")
                
                # Try a different approach: go to Google first, then to Maps
                print("Trying alternative approach: Google homepage first...")
                page.goto("https://www.google.com", timeout=30000)
                page.wait_for_timeout(3000)
                handle_consent_actively(page)
                
                # Click on Google Apps menu (9 dots)
                try:
                    page.click('a[aria-label="Google apps"]')
                    page.wait_for_timeout(1000)
                    # Try to find and click Maps in the menu
                    maps_links = page.locator('a[href*="maps.google.com"]').all()
                    if maps_links:
                        maps_links[0].click()
                        page.wait_for_timeout(5000)
                        # Check if we made it to Maps
                        if page.locator('#searchboxinput').is_visible():
                            print("Successfully reached Maps via Google apps menu!")
                            success = True
                            break
                except Exception as e:
                    print(f"Error using Google apps menu: {e}")
        
        except Exception as e:
            print(f"Error during Maps initialization attempt {attempt+1}: {e}")
            # Take error screenshot
            screenshot_dir = "debug_screenshots"
            if not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir)
            try:
                page.screenshot(path=f"{screenshot_dir}/error_{attempt+1}.png")
            except:
                pass
    
    if not success:
        print("Failed to initialize Google Maps after multiple attempts.")
        print("Please check debug screenshots for more information.")
    
    return success

def update_no_website_master_list(business_df, search_term):
    """
    Updates the master list of businesses without websites
    
    Args:
        business_df: DataFrame of businesses from current scrape
        search_term: The search term used for this scrape
    """
    master_file = os.path.join('output', 'businesses_without_websites_master.csv')
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Filter businesses without websites
    no_website_df = business_df[
        (business_df['website'].isnull()) | 
        (business_df['website'] == '')
    ].copy()
    
    # If no businesses without websites were found, return
    if len(no_website_df) == 0:
        print("No businesses without websites found in this scrape.")
        return
    
    # Add metadata columns
    no_website_df['search_term'] = search_term
    no_website_df['date_added'] = current_date
    
    # Create unique identifier for deduplication
    no_website_df['unique_id'] = no_website_df.apply(
        lambda row: f"{row['name']}_{row['address']}" if pd.notna(row['address']) else f"{row['name']}_noaddress", 
        axis=1
    )
    
    # Check if master file exists
    if os.path.exists(master_file):
        # Load existing master file
        master_df = pd.read_csv(master_file)
        
        # Add unique_id to master if it doesn't exist
        if 'unique_id' not in master_df.columns:
            master_df['unique_id'] = master_df.apply(
                lambda row: f"{row['name']}_{row['address']}" if pd.notna(row['address']) else f"{row['name']}_noaddress", 
                axis=1
            )
        
        # Identify new businesses not in master list
        existing_ids = set(master_df['unique_id'])
        new_businesses = no_website_df[~no_website_df['unique_id'].isin(existing_ids)]
        
        # Append only new businesses to master list
        if len(new_businesses) > 0:
            updated_master = pd.concat([master_df, new_businesses], ignore_index=True)
            updated_master.to_csv(master_file, index=False)
            print(f"Added {len(new_businesses)} new businesses without websites to master list.")
        else:
            print("No new businesses without websites to add to master list.")
    else:
        # Create new master file
        no_website_df.to_csv(master_file, index=False)
        print(f"Created master list with {len(no_website_df)} businesses without websites.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()

    if args.search:
        search_list = [args.search]
    else:
        search_list = []

    if args.total:
        total = args.total
    else:
        total = 1_000_000

    if not args.search:
        search_list = []
        input_file_name = 'input.txt'
        input_file_path = os.path.join(os.getcwd(), input_file_name)
        if os.path.exists(input_file_path):
            with open(input_file_path, 'r') as file:
                search_list = file.readlines()

        if len(search_list) == 0:
            print('Error: You must either pass the -s search argument or add searches to input.txt')
            sys.exit()

    # Initialize the Playwright with persistent context for cookie handling
    with sync_playwright() as p:
        # Use persistent context to maintain cookies between sessions
        browser, page = setup_persistent_context(p)
        
        # Initialize Google Maps with robust cookie consent handling
        if not initialize_google_maps(page):
            print("Failed to initialize Google Maps. Please check cookie settings manually.")
            input("Press Enter to continue after manually accepting cookies...")
            # Try one more time after manual intervention
            if not initialize_google_maps(page):
                print("Still unable to initialize Google Maps. Exiting.")
                browser.close()
                sys.exit(1)

        for search_for_index, search_for in enumerate(search_list):
            # Create a new business list for each search
            business_list = BusinessList()
            
            search_term = search_for.strip()
            print(f"-----\n{search_for_index} - {search_term}")

            # Sanitize the search term before using it in the filename
            search_for_sanitized = sanitize_filename(search_term)
            
            # Make sure the search box is available and clear it safely
            try:
                # Wait for the search box to be available
                page.wait_for_selector('#searchboxinput', timeout=5000)
                
                # Clear the search box using fill with empty string first
                page.locator('#searchboxinput').fill("")
                page.wait_for_timeout(500)
                
                # Now fill with the search term
                page.locator('#searchboxinput').fill(search_term)
                page.wait_for_timeout(1000)
                
                page.keyboard.press("Enter")
                page.wait_for_timeout(5000)  # Give more time for results to load
                
            except Exception as e:
                print(f"Error with search input: {e}")
                print("Attempting to reinitialize Google Maps...")
                
                # Try to recover by reloading Google Maps
                if not initialize_google_maps(page):
                    print("Failed to recover Google Maps page. Skipping this search term.")
                    continue  # Skip to the next search term
                continue

            # Check if search results are loading
            try:
                # Wait for search results to appear
                selector = '//a[contains(@href, "https://www.google.com/maps/place")]'
                page.wait_for_selector(selector, timeout=10000)
                
                # Take a screenshot for debugging if needed
                # page.screenshot(path=f"debug_search_{search_for_sanitized}.png")
                
                # Verify we have results
                result_count = page.locator(selector).count()
                if result_count == 0:
                    print(f"No results found for '{search_term}'")
                    continue
                    
                print(f"Found initial {result_count} results")
                page.hover(selector)
                
            except Exception as e:
                print(f"No search results found for '{search_term}': {e}")
                continue  # Skip to the next search term

            previously_counted = 0
            listings = []  # Initialize listings here
            
            # Added counter for duplicates
            duplicates_found = 0
            
            # Scroll and collect listings
            scroll_attempts = 0
            max_scroll_attempts = 20  # Limit scrolling attempts to prevent infinite loops
            
            while scroll_attempts < max_scroll_attempts:
                try:
                    page.mouse.wheel(0, 10000)
                    page.wait_for_timeout(2000)
                    scroll_attempts += 1

                    current_count = page.locator(selector).count()
                    print(f"Currently found: {current_count} listings (scroll attempt {scroll_attempts})")
                    
                    # Check if we've reached the desired total
                    if current_count >= total:
                        print(f"Reached target count of {total}")
                        break
                        
                    # Check if no new listings are being loaded
                    if current_count == previously_counted:
                        if scroll_attempts > 2:  # Only consider it finished if we've had multiple attempts with no new results
                            print(f"No new listings after multiple scrolls. Stopping at {current_count}")
                            break
                    else:
                        previously_counted = current_count
                except Exception as e:
                    print(f"Error while scrolling: {e}")
                    break

            # Collect all the listings after scrolling
            try:
                all_listings = page.locator(selector).all()
                print(f"Total listings found: {len(all_listings)}")
                
                # Limit to total if needed
                listings = all_listings[:min(len(all_listings), total)]
                listings = [listing.locator("xpath=..") for listing in listings]
                print(f"Processing {len(listings)} listings...")
            except Exception as e:
                print(f"Error collecting listings: {e}")
                continue  # Skip to next search term
            
            # Process the collected listings
            businesses_added = 0
            
            for i, listing in enumerate(listings):
                try:
                    # Create a new Business object
                    business = Business()
                    
                    # Get the name from the listing before clicking
                    try:
                        business.name = listing.get_attribute('aria-label') or ""
                        if not business.name:
                            # Try alternative selectors for name
                            if listing.locator('h3').count() > 0:
                                business.name = listing.locator('h3').inner_text()
                            elif listing.locator('.fontHeadlineSmall').count() > 0:
                                business.name = listing.locator('.fontHeadlineSmall').inner_text()
                    except Exception as e:
                        print(f"Error getting name: {e}")
                        business.name = f"Unknown Business {i+1}"
                    
                    # Click on the listing to show details
                    try:
                        listing.click()
                        page.wait_for_timeout(2000)  # Give more time for details to load
                    except Exception as e:
                        print(f"Error clicking listing {i}: {e}")
                        business.error_message = f"Couldn't click: {str(e)}"
                        if business_list.add_business(business):
                            businesses_added += 1
                        continue
                    
                    # Define XPaths for business details
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'

                    # Get business details one by one with error handling
                    try:
                        business.address = page.locator(address_xpath).inner_text() if page.locator(address_xpath).count() > 0 else ""
                    except Exception as e:
                        print(f"Error getting address: {e}")
                        business.address = ""
                        
                    try:
                        business.website = page.locator(website_xpath).inner_text() if page.locator(website_xpath).count() > 0 else ""
                        # Format website URL properly
                        if business.website and not business.website.startswith("http://") and not business.website.startswith("https://"):
                            business.website = f"https://{business.website}"
                    except Exception as e:
                        print(f"Error getting website: {e}")
                        business.website = ""
                        
                    try:
                        business.phone_number = page.locator(phone_number_xpath).inner_text() if page.locator(phone_number_xpath).count() > 0 else ""
                    except Exception as e:
                        print(f"Error getting phone: {e}")
                        business.phone_number = ""

                    # Add business to list if it's not a duplicate
                    if business_list.add_business(business):
                        businesses_added += 1
                    else:
                        duplicates_found += 1

                    # Print progress regularly
                    if i % 5 == 0 or i == len(listings) - 1:
                        print(f"Processed {i+1}/{len(listings)} listings. Added: {businesses_added}, Duplicates: {duplicates_found}")

                except Exception as e:
                    print(f"Error processing listing {i}: {str(e)}")
                    # Still try to add the business with whatever info we have
                    business = Business(error_message=f'Error processing listing: {e}')
                    business.name = f"Error Processing Business {i+1}"
                    business_list.add_business(business)

            print(f"Search complete. Added {businesses_added} businesses. Skipped {duplicates_found} duplicates.")
            
            # Get current date and time for filename
            current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M")
            
            # Save the data to CSV
            filename = f"google_maps_data_{search_for_sanitized}_{current_datetime}"
            business_list.save_to_csv(filename)
            
            # Update the master list of businesses without websites
            business_df = business_list.dataframe()
            update_no_website_master_list(business_df, search_term)

        browser.close()

if __name__ == "__main__":
    main()