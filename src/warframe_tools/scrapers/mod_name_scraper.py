"""Scraper for mod names and URLs from Warframe wiki."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import json
from datetime import datetime
from pathlib import Path


def scrape_mod_names(data_dir=None, headless=False):
    """
    Scrape mod names and URLs from Warframe wiki mods list page.
    
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
        # Navigate to the mods page
        url = "https://wiki.warframe.com/w/Mod/List_of_Mods#Primary"
        print(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for the page to load
        time.sleep(3)  # Give the page time to fully load
        
        # Find all tables with class "listtable" (these are the mod tables)
        print("\nFinding mod tables...")
        tables = driver.find_elements(By.CSS_SELECTOR, "table.listtable")
        print(f"Found {len(tables)} mod tables")
        
        # Store all mods with their metadata
        all_mods = []
        mod_urls_set = set()  # To avoid duplicates
        
        # Process each table
        for table_idx, table in enumerate(tables, 1):
            print(f"\nProcessing table {table_idx}/{len(tables)}...")
            
            # Try to find the section this table belongs to
            # Look for the nearest h2 or h3 heading before this table
            section_name = "Unknown"
            try:
                # Get the table's parent or find preceding heading
                table_parent = table.find_element(By.XPATH, "./..")
                # Try to find a heading in the parent or before it
                try:
                    heading = table.find_element(By.XPATH, "./preceding::h2[1] | ./preceding::h3[1]")
                    section_name = heading.text.strip()
                except:
                    # Try finding in parent
                    try:
                        heading = table_parent.find_element(By.CSS_SELECTOR, "h2, h3")
                        section_name = heading.text.strip()
                    except:
                        pass
            except:
                pass
            
            # Find all rows in the table (skip header row)
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            if not rows:
                # Try without tbody
                rows = table.find_elements(By.TAG_NAME, "tr")
                # Skip first row if it's a header
                if rows and rows[0].find_elements(By.TAG_NAME, "th"):
                    rows = rows[1:]
            
            print(f"  Found {len(rows)} mod rows in section '{section_name}'")
            
            # Process each row
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 5:  # Need at least Name, Description, Polarity, Rarity, Subcategory
                        continue
                    
                    # Extract mod name and URL from first cell
                    name_cell = cells[0]
                    mod_link = name_cell.find_element(By.CSS_SELECTOR, "a[href*='/w/']")
                    mod_name = mod_link.text.strip()
                    mod_url = mod_link.get_attribute('href')
                    
                    # Normalize URL
                    if mod_url and mod_url.startswith('/'):
                        mod_url = f"https://wiki.warframe.com{mod_url}"
                    
                    # Skip if we've already seen this mod
                    if mod_url in mod_urls_set:
                        continue
                    mod_urls_set.add(mod_url)
                    
                    # Extract description (second cell)
                    description = cells[1].text.strip() if len(cells) > 1 else ""
                    
                    # Extract polarity (third cell) - might be an image or text
                    polarity_cell = cells[2] if len(cells) > 2 else None
                    polarity = ""
                    if polarity_cell:
                        # Try to find polarity name from image alt or title
                        polarity_img = polarity_cell.find_elements(By.TAG_NAME, "img")
                        if polarity_img:
                            polarity_alt = polarity_img[0].get_attribute('alt') or ""
                            polarity_title = polarity_img[0].get_attribute('title') or ""
                            polarity = polarity_alt or polarity_title or polarity_cell.text.strip()
                        else:
                            polarity = polarity_cell.text.strip()
                    
                    # Extract rarity (fourth cell)
                    rarity = cells[3].text.strip() if len(cells) > 3 else ""
                    
                    # Extract subcategory (fifth cell) - might have multiple links
                    subcategory_cell = cells[4] if len(cells) > 4 else None
                    subcategories = []
                    if subcategory_cell:
                        subcategory_text = subcategory_cell.text.strip()
                        if subcategory_text and subcategory_text.lower() != "none":
                            # Split by comma and clean up
                            subcategories = [s.strip() for s in subcategory_text.split(',') if s.strip()]
                        
                        # Also get links for subcategories
                        subcategory_links = subcategory_cell.find_elements(By.TAG_NAME, "a")
                        subcategory_urls = []
                        for link in subcategory_links:
                            href = link.get_attribute('href')
                            if href:
                                if href.startswith('/'):
                                    href = f"https://wiki.warframe.com{href}"
                                subcategory_urls.append({
                                    'name': link.text.strip(),
                                    'url': href
                                })
                    
                    # Create mod entry
                    mod_entry = {
                        "mod_name": mod_name,
                        "mod_url": mod_url,
                        "description": description,
                        "polarity": polarity,
                        "rarity": rarity,
                        "subcategories": subcategories,
                        "section": section_name
                    }
                    
                    # Add subcategory URLs if we found any
                    if subcategory_cell and subcategory_links:
                        mod_entry["subcategory_links"] = subcategory_urls
                    
                    all_mods.append(mod_entry)
                    
                except Exception as e:
                    # Skip rows that fail to parse
                    continue
        
        print(f"\n\nExtracted {len(all_mods)} unique mods")
        
        # Display first 10 as a sample
        print("\nFirst 10 mods:")
        for i, mod in enumerate(all_mods[:10], 1):
            print(f"{i}. {mod['mod_name']} ({mod['rarity']}) - {mod['section']}")
        
        # Save to JSON file with today's date
        today = datetime.now().strftime("%Y-%m-%d")
        filename = data_dir / f"mod_links_{today}.json"
        
        mod_data = {
            "scrape_date": today,
            "total_mods": len(all_mods),
            "mods": all_mods
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(mod_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved {len(all_mods)} mod links to {filename}")
        return filename
        
    finally:
        # Close the browser when done
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    scrape_mod_names()

