"""Scraper for weapon manufacturing data from Warframe wiki."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import json
from datetime import datetime
import re
from tqdm import tqdm
from pathlib import Path


def scrape_weapon_data(weapon_links_file=None, data_dir=None, headless=False):
    """
    Scrape weapon manufacturing data from Warframe wiki.
    
    Args:
        weapon_links_file: Path to JSON file containing weapon URLs. 
                          If None, looks for latest weapon_links_*.json in data_dir.
        data_dir: Directory to read from and save to. Defaults to 'data' folder in project root.
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
    
    # Find weapon links file if not provided
    if weapon_links_file is None:
        # Find the latest weapon_links_*.json file
        weapon_links_files = sorted(data_dir.glob("weapon_links_*.json"))
        if not weapon_links_files:
            raise FileNotFoundError(f"No weapon_links_*.json file found in {data_dir}")
        weapon_links_file = weapon_links_files[-1]
        print(f"Using latest weapon links file: {weapon_links_file}")
    else:
        weapon_links_file = Path(weapon_links_file)
    
    # Load weapon links from JSON
    print(f"Loading weapon links from {weapon_links_file}...")
    with open(weapon_links_file, 'r', encoding='utf-8') as f:
        weapon_data = json.load(f)
    
    weapon_urls = weapon_data['weapon_urls']
    print(f"Loaded {len(weapon_urls)} weapon URLs")
    print(f"Processing all {len(weapon_urls)} weapons...\n")
    
    # Set up Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    
    # Base URL for normalizing relative URLs
    base_url = "https://wiki.warframe.com"
    
    # Store all weapon manufacturing data
    weapons_manufacturing_data = []
    
    try:
        for weapon_url in tqdm(weapon_urls, desc="Scraping weapons", unit="weapon"):
            try:
                # Navigate to weapon page
                driver.get(weapon_url)
                time.sleep(1)  # Wait 1 second to not overwhelm the server
                
                # Wait for page to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Extract weapon name from URL
                weapon_name = weapon_url.split('/')[-1].replace('_', ' ')
                
                # Initialize data structure for this weapon
                weapon_info = {
                    "weapon_name": weapon_name,
                    "weapon_url": weapon_url,
                    "infobox": {
                        "general_info": {},
                        "utility": {},
                        "normal_attack": {},
                        "miscellaneous": {}
                    },
                    "resources": [],
                    "time": None,
                    "rush_cost": None,
                    "market_price": None,
                    "blueprint_price": None
                }
                
                # Extract infobox data
                infobox_selector = "#mw-content-text > div.mw-content-ltr.mw-parser-output > div.infobox"
                try:
                    infobox = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, infobox_selector))
                    )
                    
                    # Find all groups/sections in the infobox
                    groups = infobox.find_elements(By.CSS_SELECTOR, "div.group")
                    
                    for group in groups:
                        # Get the header to identify the section
                        try:
                            header = group.find_element(By.CSS_SELECTOR, "div.header")
                            section_name = header.text.strip()
                        except Exception:
                            continue
                        
                        # Find all rows in this group
                        rows = group.find_elements(By.CSS_SELECTOR, "div.row")
                        
                        for row in rows:
                            try:
                                label_elem = row.find_element(By.CSS_SELECTOR, "div.label")
                                value_elem = row.find_element(By.CSS_SELECTOR, "div.value")
                                
                                label = label_elem.text.strip()
                                value = value_elem.text.strip()
                                
                                # Store based on section
                                if "General Information" in section_name:
                                    weapon_info["infobox"]["general_info"][label] = value
                                elif "Utility" in section_name:
                                    weapon_info["infobox"]["utility"][label] = value
                                elif "Normal Attack" in section_name:
                                    weapon_info["infobox"]["normal_attack"][label] = value
                                elif "Miscellaneous" in section_name:
                                    weapon_info["infobox"]["miscellaneous"][label] = value
                            except Exception:
                                continue
                    
                    # Also extract damage types from Normal Attack section if present
                    try:
                        normal_attack_group = None
                        for group in groups:
                            try:
                                header = group.find_element(By.CSS_SELECTOR, "div.header")
                                if "Normal Attack" in header.text:
                                    normal_attack_group = group
                                    break
                            except Exception:
                                continue
                        
                        if normal_attack_group:
                            # Look for damage type rows (they have hgroup)
                            hgroups = normal_attack_group.find_elements(By.CSS_SELECTOR, "div.hgroup")
                            if hgroups:
                                damage_types = {}
                                for hgroup in hgroups:
                                    damage_rows = hgroup.find_elements(By.CSS_SELECTOR, "div.row")
                                    for row in damage_rows:
                                        try:
                                            label_elem = row.find_element(By.CSS_SELECTOR, "div.label")
                                            value_elem = row.find_element(By.CSS_SELECTOR, "div.value")
                                            
                                            label = label_elem.text.strip()
                                            value = value_elem.text.strip()
                                            
                                            # Extract damage value and percentage
                                            # Format is usually: "14.19\n(43%)"
                                            damage_match = re.search(r'([\d.]+)', value.split('\n')[0])
                                            percent_match = re.search(r'\(([\d.]+)%\)', value)
                                            
                                            damage_types[label] = {
                                                "value": float(damage_match.group(1)) if damage_match else None,
                                                "percentage": float(percent_match.group(1)) if percent_match else None,
                                                "raw": value
                                            }
                                        except Exception:
                                            continue
                                
                                if damage_types:
                                    weapon_info["infobox"]["normal_attack"]["damage_types"] = damage_types
                    except Exception:
                        pass
                        
                except Exception as e:
                    tqdm.write(f"  ⚠ Could not find infobox: {e}")
                
                # Find the foundry table
                table_selector = "#mw-content-text > div.mw-content-ltr.mw-parser-output > table.foundrytable"
                
                try:
                    table = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, table_selector))
                    )
                    
                    # Find all rows in the table
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    
                    # Process each row
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        # Look for resource cells (they have images and links)
                        for cell in cells:
                            try:
                                # Check if this cell contains a resource (has an image and a link)
                                links = cell.find_elements(By.TAG_NAME, "a")
                                if links:
                                    # Get the resource name from the link
                                    resource_link = None
                                    for link in links:
                                        href = link.get_attribute('href')
                                        if href and '/w/' in href and 'Resources' not in href:
                                            resource_link = link
                                            break
                                    
                                    if resource_link:
                                        # Get the resource URL
                                        href = resource_link.get_attribute('href')
                                        
                                        # Normalize the URL
                                        if href:
                                            if href.startswith('/'):
                                                resource_url = base_url + href
                                            elif href.startswith('http'):
                                                resource_url = href
                                            else:
                                                resource_url = None
                                        else:
                                            resource_url = None
                                        
                                        # Get resource name from the link text or href
                                        resource_name = resource_link.get_attribute('title') or resource_link.get_attribute('text').strip()
                                        if not resource_name:
                                            # Extract from href
                                            if href:
                                                resource_name = href.split('/')[-1].replace('_', ' ')
                                        
                                        # Get the quantity (the number after the image, usually after a <br> tag)
                                        cell_text = cell.text.strip()
                                        
                                        # The cell structure is usually: [image/icon] resource_name quantity
                                        # Try to extract the quantity - it's usually the last number in the cell
                                        # Split by newlines and get the last line which usually contains the quantity
                                        lines = cell_text.split('\n')
                                        quantity = None
                                        
                                        # Look for quantity in the last line or parse all numbers
                                        if lines:
                                            last_line = lines[-1].strip()
                                            # Try to get a number from the last line
                                            numbers = re.findall(r'[\d,]+', last_line)
                                            if numbers:
                                                quantity_str = numbers[-1].replace(',', '')
                                                try:
                                                    quantity = int(quantity_str)
                                                except ValueError:
                                                    pass
                                        
                                        # If we didn't find it in the last line, try all numbers
                                        if quantity is None:
                                            numbers = re.findall(r'[\d,]+', cell_text)
                                            if numbers:
                                                quantity_str = numbers[-1].replace(',', '')
                                                try:
                                                    quantity = int(quantity_str)
                                                except ValueError:
                                                    pass
                                        
                                        # Only add if we found a valid quantity and it's not a duplicate
                                        if quantity is not None:
                                            if not any(r['name'] == resource_name for r in weapon_info['resources']):
                                                resource_data = {
                                                    "name": resource_name,
                                                    "quantity": quantity
                                                }
                                                # Add URL if we have it
                                                if resource_url:
                                                    resource_data["url"] = resource_url
                                                
                                                weapon_info['resources'].append(resource_data)
                            except Exception:
                                continue
                        
                        # Look for time information
                        row_text = row.text
                        if 'Time:' in row_text:
                            time_match = re.search(r'Time:\s*(\d+)\s*Day\(s\)', row_text)
                            if time_match:
                                weapon_info['time'] = f"{time_match.group(1)} Day(s)"
                        
                        # Look for rush cost
                        if 'Rush:' in row_text:
                            rush_match = re.search(r'Rush:.*?(\d+)', row_text)
                            if rush_match:
                                weapon_info['rush_cost'] = int(rush_match.group(1))
                        
                        # Look for market price
                        if 'Market' in row_text and 'Price:' in row_text:
                            market_match = re.search(r'Market.*?Price:.*?(\d+)', row_text)
                            if market_match:
                                weapon_info['market_price'] = int(market_match.group(1))
                        
                        # Look for blueprint price
                        if 'Blueprints' in row_text and 'Price:' in row_text:
                            blueprint_match = re.search(r'Blueprints.*?Price:.*?([N/A\d]+)', row_text)
                            if blueprint_match:
                                price_str = blueprint_match.group(1).strip()
                                if price_str.upper() == 'N/A':
                                    weapon_info['blueprint_price'] = None
                                else:
                                    try:
                                        weapon_info['blueprint_price'] = int(price_str)
                                    except ValueError:
                                        weapon_info['blueprint_price'] = price_str
                    
                    weapons_manufacturing_data.append(weapon_info)
                    infobox_sections = sum(1 for section in weapon_info['infobox'].values() if section)
                    tqdm.write(f"  ✓ Extracted {len(weapon_info['resources'])} resources, {infobox_sections} infobox sections")
                    
                except Exception as e:
                    tqdm.write(f"  ✗ Could not find foundry table: {e}")
                    # Still add the weapon with infobox data (if we got it) but no foundry data
                    weapon_info['foundry_error'] = str(e)
                    weapons_manufacturing_data.append(weapon_info)
            
            except Exception as e:
                tqdm.write(f"  ✗ Error processing {weapon_url}: {e}")
                weapon_name = weapon_url.split('/')[-1].replace('_', ' ')
                weapons_manufacturing_data.append({
                    "weapon_name": weapon_name,
                    "weapon_url": weapon_url,
                    "infobox": {
                        "general_info": {},
                        "utility": {},
                        "normal_attack": {},
                        "miscellaneous": {}
                    },
                    "resources": [],
                    "time": None,
                    "rush_cost": None,
                    "market_price": None,
                    "blueprint_price": None,
                    "error": str(e)
                })
            
            # Wait 1 second before next request to not overwhelm the server
            time.sleep(1)
    
    finally:
        # Close the browser
        driver.quit()
        tqdm.write("\nBrowser closed.")
    
    # Save the manufacturing data to JSON
    today = datetime.now().strftime("%Y-%m-%d")
    output_filename = data_dir / f"weapon_manufacturing_{today}.json"
    
    output_data = {
        "scrape_date": today,
        "total_weapons_scraped": len(weapons_manufacturing_data),
        "weapons": weapons_manufacturing_data
    }
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    tqdm.write(f"\nSaved manufacturing data for {len(weapons_manufacturing_data)} weapons to {output_filename}")
    
    # Display summary
    tqdm.write("\nSummary:")
    for weapon in weapons_manufacturing_data:
        tqdm.write(f"  {weapon['weapon_name']}: {len(weapon['resources'])} resources, Time: {weapon['time'] or 'N/A'}")
    
    return output_filename


if __name__ == "__main__":
    scrape_weapon_data()

