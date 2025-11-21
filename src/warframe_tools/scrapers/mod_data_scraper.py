"""Scraper for mod detailed data from Warframe wiki."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import json
from datetime import datetime
from pathlib import Path
from tqdm import tqdm


def scrape_mod_data(mod_links_file=None, data_dir=None, headless=False, limit=None):
    """
    Scrape detailed mod data from Warframe wiki mod pages.
    
    Args:
        mod_links_file: Path to JSON file containing mod URLs. 
                       If None, looks for latest mod_links_*.json in data_dir.
        data_dir: Directory to read from and save to. Defaults to 'data' folder in project root.
        headless: Whether to run browser in headless mode.
        limit: Optional limit on number of mods to scrape (useful for testing).
    
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
    
    # Find mod links file if not provided
    if mod_links_file is None:
        # Find the latest mod_links_*.json file
        mod_links_files = sorted(data_dir.glob("mod_links_*.json"))
        if not mod_links_files:
            raise FileNotFoundError(f"No mod_links_*.json file found in {data_dir}")
        mod_links_file = mod_links_files[-1]
        print(f"Using latest mod links file: {mod_links_file}")
    else:
        mod_links_file = Path(mod_links_file)
    
    # Load mod links from JSON
    print(f"Loading mod links from {mod_links_file}...")
    with open(mod_links_file, 'r', encoding='utf-8') as f:
        mod_data = json.load(f)
    
    mods = mod_data['mods']
    
    # Apply limit if specified (for testing)
    if limit is not None:
        mods = mods[:limit]
        print(f"Loaded {len(mod_data['mods'])} mods, limiting to first {len(mods)} for testing")
    else:
        print(f"Loaded {len(mods)} mods")
    
    print(f"Processing {len(mods)} mods...\n")
    
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
    
    # Store all mod data
    mods_detailed_data = []
    
    try:
        for mod_entry in tqdm(mods, desc="Scraping mods", unit="mod"):
            mod_url = mod_entry.get('mod_url', '')
            mod_name = mod_entry.get('mod_name', '') or mod_url.split('/')[-1].replace('_', ' ')
            
            if not mod_url:
                continue
            
            try:
                # Navigate to mod page
                driver.get(mod_url)
                time.sleep(1)  # Wait 1 second to not overwhelm the server
                
                # Wait for page to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Initialize data structure for this mod
                mod_info = {
                    "mod_name": mod_name,
                    "mod_url": mod_url,
                    "infobox": {},
                    "infobox_missing": False,
                    "stats_table": None,
                    "stats_table_missing": False,
                    "error": None
                }
                
                # Extract infobox data
                infobox_selector = "#mw-content-text > div.mw-content-ltr.mw-parser-output > div.infobox"
                try:
                    infobox = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, infobox_selector))
                    )
                    
                    # Get infobox title if present
                    try:
                        title_elem = infobox.find_element(By.CSS_SELECTOR, ".title")
                        mod_info["infobox"]["title"] = title_elem.text.strip()
                    except Exception:
                        pass
                    
                    # Find all groups/sections in the infobox
                    groups = infobox.find_elements(By.CSS_SELECTOR, "div.group")
                    
                    for group in groups:
                        # Get the header to identify the section
                        try:
                            header = group.find_element(By.CSS_SELECTOR, "div.header")
                            section_name = header.text.strip()
                        except Exception:
                            continue
                        
                        # Initialize section in infobox
                        if section_name not in mod_info["infobox"]:
                            mod_info["infobox"][section_name] = {}
                        
                        # Find all rows in this group
                        rows = group.find_elements(By.CSS_SELECTOR, "div.row")
                        
                        for row in rows:
                            try:
                                label_elem = row.find_element(By.CSS_SELECTOR, "div.label")
                                value_elem = row.find_element(By.CSS_SELECTOR, "div.value")
                                
                                label = label_elem.text.strip()
                                value = value_elem.text.strip()
                                
                                mod_info["infobox"][section_name][label] = value
                            except Exception:
                                continue
                    
                    # Also check for tabber structure (some mods have tabs in infobox)
                    try:
                        tabber = infobox.find_element(By.CSS_SELECTOR, ".tabber")
                        tabs = tabber.find_elements(By.CSS_SELECTOR, ".tabbertab")
                        if tabs:
                            mod_info["infobox"]["has_tabs"] = True
                            mod_info["infobox"]["tab_count"] = len(tabs)
                    except Exception:
                        pass
                    
                    tqdm.write(f"  ✓ Extracted infobox with {len(mod_info['infobox'])} sections")
                    
                except Exception as e:
                    tqdm.write(f"  ⚠ WARNING: Could not find infobox (all mods should have one): {e}")
                    mod_info["infobox"] = {}
                    mod_info["infobox_missing"] = True
                    mod_info["infobox_error"] = str(e)
                
                # Extract stats table (emodtable under h2 "Stats")
                stats_table = None
                try:
                    # First, try to find emodtable directly (simpler approach)
                    emodtables = driver.find_elements(By.CSS_SELECTOR, "table.emodtable")
                    if emodtables:
                        stats_table = emodtables[0]
                        tqdm.write(f"  ✓ Found stats table (emodtable)")
                    else:
                        # Try to find h2 with text "Stats" and then the table
                        try:
                            # Try different variations of the heading
                            stats_heading = None
                            for xpath in [
                                "//h2[contains(., 'Stats')]",
                                "//h2[contains(., 'Statistics')]",
                                "//h2/span[contains(., 'Stats')]/..",
                                "//h2//*[contains(text(), 'Stats')]/ancestor::h2"
                            ]:
                                try:
                                    stats_heading = driver.find_element(By.XPATH, xpath)
                                    break
                                except Exception:
                                    continue
                            
                            if stats_heading:
                                # Find the emodtable after this heading
                                try:
                                    stats_table = driver.find_element(By.XPATH, "//h2[contains(., 'Stats')]/following::table[@class='emodtable'][1]")
                                    tqdm.write(f"  ✓ Found stats table (emodtable) via h2")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    
                    if not stats_table:
                        raise Exception("emodtable not found")
                        
                except Exception as e:
                    tqdm.write(f"  ⚠ Could not find stats table (emodtable): {str(e)[:100]}")
                    stats_table = None
                
                # Also extract drop table (wikitable) if it exists (for reference)
                drop_table = None
                drop_tables = driver.find_elements(By.CSS_SELECTOR, "table.wikitable")
                
                if stats_table:
                    try:
                        # Get table headers - emodtable has th in first tr, not thead
                        headers = []
                        all_rows = stats_table.find_elements(By.TAG_NAME, "tr")
                        if all_rows:
                            first_row = all_rows[0]
                            header_cells = first_row.find_elements(By.TAG_NAME, "th")
                            if header_cells:
                                headers = [cell.text.strip() for cell in header_cells]
                        
                        # Get table rows (skip header row)
                        rows_data = []
                        tbody = stats_table.find_element(By.TAG_NAME, "tbody")
                        if tbody:
                            rows = tbody.find_elements(By.TAG_NAME, "tr")
                            # Skip first row if it has th (header row)
                            if rows and rows[0].find_elements(By.TAG_NAME, "th"):
                                rows = rows[1:]
                        else:
                            rows = stats_table.find_elements(By.CSS_SELECTOR, "tr")
                            # Skip header row if it has th
                            if rows and rows[0].find_elements(By.TAG_NAME, "th"):
                                rows = rows[1:]
                        
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if not cells:
                                continue
                            
                            row_data = {}
                            for i, cell in enumerate(cells):
                                header = headers[i] if i < len(headers) else f"Column_{i + 1}"
                                cell_text = cell.text.strip()
                                
                                # Check for links in cell
                                links = cell.find_elements(By.TAG_NAME, "a")
                                if links:
                                    cell_links = []
                                    for link in links:
                                        href = link.get_attribute('href')
                                        if href:
                                            if href.startswith('/'):
                                                href = base_url + href
                                            cell_links.append({
                                                'text': link.text.strip(),
                                                'url': href
                                            })
                                    if cell_links:
                                        row_data[header] = {
                                            'text': cell_text,
                                            'links': cell_links
                                        }
                                    else:
                                        row_data[header] = cell_text
                                else:
                                    row_data[header] = cell_text
                            
                            if row_data:
                                rows_data.append(row_data)
                        
                        mod_info["stats_table"] = {
                            "headers": headers,
                            "rows": rows_data
                        }
                        
                        tqdm.write(f"  ✓ Extracted stats table with {len(rows_data)} rows")
                        
                    except Exception as e:
                        tqdm.write(f"  ⚠ Could not parse stats table: {e}")
                        mod_info["stats_table"] = None
                        mod_info["stats_table_missing"] = True
                else:
                    # Stats table is optional, so this is just informational
                    mod_info["stats_table"] = None
                    mod_info["stats_table_missing"] = True
                
                # Extract drop table (wikitable) if it exists (for reference)
                if drop_tables:
                    try:
                        # Usually the first wikitable is the drop table
                        drop_table = drop_tables[0]
                        
                        # Get table headers
                        drop_headers = []
                        try:
                            drop_header_row = drop_table.find_element(By.TAG_NAME, "thead")
                            if drop_header_row:
                                drop_header_cells = drop_header_row.find_elements(By.TAG_NAME, "th")
                                drop_headers = [cell.text.strip() for cell in drop_header_cells]
                        except Exception:
                            pass
                        
                        # Get table rows
                        drop_rows_data = []
                        try:
                            drop_tbody = drop_table.find_element(By.TAG_NAME, "tbody")
                            if drop_tbody:
                                drop_rows = drop_tbody.find_elements(By.TAG_NAME, "tr")
                            else:
                                drop_rows = drop_table.find_elements(By.CSS_SELECTOR, "tr:not(:first-child)")
                            
                            for row in drop_rows:
                                cells = row.find_elements(By.TAG_NAME, "td")
                                if not cells:
                                    continue
                                
                                row_data = {}
                                for i, cell in enumerate(cells):
                                    header = drop_headers[i] if i < len(drop_headers) else f"Column_{i+1}"
                                    cell_text = cell.text.strip()
                                    
                                    # Check for links in cell
                                    links = cell.find_elements(By.TAG_NAME, "a")
                                    if links:
                                        cell_links = []
                                        for link in links:
                                            href = link.get_attribute('href')
                                            if href:
                                                if href.startswith('/'):
                                                    href = base_url + href
                                                cell_links.append({
                                                    'text': link.text.strip(),
                                                    'url': href
                                                })
                                        if cell_links:
                                            row_data[header] = {
                                                'text': cell_text,
                                                'links': cell_links
                                            }
                                        else:
                                            row_data[header] = cell_text
                                    else:
                                        row_data[header] = cell_text
                                
                                if row_data:
                                    drop_rows_data.append(row_data)
                            
                            if drop_rows_data:
                                mod_info["drop_table"] = {
                                    "headers": drop_headers,
                                    "rows": drop_rows_data
                                }
                        except Exception:
                            pass
                    except Exception:
                        pass
                
                mods_detailed_data.append(mod_info)
                
            except Exception as e:
                tqdm.write(f"  ✗ Error processing {mod_url}: {e}")
                mods_detailed_data.append({
                    "mod_name": mod_name,
                    "mod_url": mod_url,
                    "infobox": {},
                    "infobox_missing": True,
                    "stats_table": None,
                    "stats_table_missing": True,
                    "error": str(e)
                })
            
            # Wait 1 second before next request to not overwhelm the server
            time.sleep(1)
    
    finally:
        # Close the browser
        driver.quit()
        tqdm.write("\nBrowser closed.")
    
    # Save the mod data to JSON
    today = datetime.now().strftime("%Y-%m-%d")
    if limit is not None:
        output_filename = data_dir / f"mod_data_test_{limit}_{today}.json"
    else:
        output_filename = data_dir / f"mod_data_{today}.json"
    
    output_data = {
        "scrape_date": today,
        "total_mods_scraped": len(mods_detailed_data),
        "mods": mods_detailed_data
    }
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    tqdm.write(f"\nSaved detailed data for {len(mods_detailed_data)} mods to {output_filename}")
    
    # Display summary
    tqdm.write("\nSummary:")
    mods_with_infobox = sum(1 for m in mods_detailed_data if m.get('infobox') and len(m.get('infobox', {})) > 0)
    mods_missing_infobox = sum(1 for m in mods_detailed_data if m.get('infobox_missing', False))
    mods_with_stats = sum(1 for m in mods_detailed_data if m.get('stats_table'))
    mods_missing_stats = sum(1 for m in mods_detailed_data if m.get('stats_table_missing', False))
    mods_with_errors = sum(1 for m in mods_detailed_data if m.get('error'))
    mods_successful = len(mods_detailed_data) - mods_with_errors
    
    tqdm.write(f"  - Total mods processed: {len(mods_detailed_data)}")
    tqdm.write(f"  - Successfully scraped: {mods_successful}")
    tqdm.write(f"  - Mods with errors: {mods_with_errors}")
    tqdm.write(f"  - Mods with infobox: {mods_with_infobox} ✓")
    tqdm.write(f"  - Mods MISSING infobox: {mods_missing_infobox} ⚠ (should be 0)")
    tqdm.write(f"  - Mods with stats table: {mods_with_stats}")
    tqdm.write(f"  - Mods without stats table: {mods_missing_stats} (optional)")
    
    return output_filename


if __name__ == "__main__":
    scrape_mod_data()

