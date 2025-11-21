"""Scraper for weapon names and URLs from Warframe wiki."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import json
from datetime import datetime
from pathlib import Path


def scrape_weapon_names(data_dir=None, headless=False):
    """
    Scrape weapon names and URLs from Warframe wiki.
    
    Args:
        data_dir: Directory to save the output JSON file. Defaults to 'data' folder in project root.
        headless: Whether to run browser in headless mode.
    
    Returns:
        Path to the saved JSON file.
    """
    # Determine data directory
    if data_dir is None:
        # Get project root (assuming this is in src/warframe_tools/scrapers/)
        project_root = Path(__file__).parent.parent.parent.parent
        data_dir = project_root / "data"
    else:
        data_dir = Path(data_dir)
    
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Navigate to the weapons page
        url = "https://wiki.warframe.com/w/Weapons#By_Version_"
        print(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for the page to load
        time.sleep(3)  # Give the page time to fully load
        
        # Find the specific weapons table
        table_selector = "#tabber-ebb779b29c5ddd57a31953ee39ef28e0 > div:nth-child(3) > table"
        
        # Wait for the table to be present
        try:
            table = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, table_selector))
            )
            print("Table found!")
        except Exception as e:
            print(f"Could not find table: {e}")
            # Try scrolling to the table area
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            table = driver.find_element(By.CSS_SELECTOR, table_selector)
        
        # Find all rows in the tbody (skip the header row)
        rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
        
        # Extract unique weapon URLs from the "Weapon" column (second column, index 1)
        weapon_urls = set()
        base_url = "https://wiki.warframe.com"
        
        for row in rows:
            # Get all cells in the row
            cells = row.find_elements(By.TAG_NAME, "td")
            
            # The Weapon column is the second column (index 1)
            if len(cells) >= 2:
                weapon_cell = cells[1]
                try:
                    # Find the link in the weapon cell
                    link = weapon_cell.find_element(By.TAG_NAME, "a")
                    href = link.get_attribute('href')
                    
                    if href:
                        # Normalize the URL
                        if href.startswith('/'):
                            full_url = base_url + href
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        
                        # Filter out non-weapon pages
                        if not any(exclude in full_url.lower() for exclude in ['/category:', '/file:', '/special:', '/user:', '/talk:', '/help:', '/template:']):
                            weapon_urls.add(full_url)
                except Exception as e:
                    # Skip rows where the weapon cell doesn't have a link
                    continue
        
        print(f"Found {len(weapon_urls)} unique weapon links from the Weapon column")
        
        # Display first 10 as a sample
        print("\nFirst 10 weapon links:")
        for i, url in enumerate(sorted(weapon_urls)[:10], 1):
            print(f"{i}. {url}")
        
        # Save all weapon links to a list for easy access
        all_weapon_links = sorted(weapon_urls)
        
        # Display total count
        print(f"\nTotal unique weapon links found: {len(all_weapon_links)}")
        
        # Save to JSON file with today's date
        today = datetime.now().strftime("%Y-%m-%d")
        filename = data_dir / f"weapon_links_{today}.json"
        
        weapon_data = {
            "scrape_date": today,
            "total_weapons": len(all_weapon_links),
            "weapon_urls": all_weapon_links
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(weapon_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved {len(all_weapon_links)} weapon links to {filename}")
        return filename
        
    finally:
        # Close the browser when done
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    scrape_weapon_names()

