from playwright.sync_api import sync_playwright
import time
import re
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import traceback

# Load environment variables
load_dotenv()

def parse_property_details(page):
    # First, wait for the table to be available
    results_table_selector = 'table:has(font:has(b:has-text("Current Search Criteria:")))'
    page.wait_for_selector(results_table_selector, state='visible', timeout=30000)
    
    # Get the HTML content of the table
    table_html = page.inner_html(results_table_selector)
    
    soup = BeautifulSoup(table_html, 'html.parser')
    
    # Extract the text from the font element containing the property info
    font_element = soup.find('font', text=re.compile('Borough:'))
    if not font_element:
        # Try another approach if the first one fails
        font_element = soup.find('b', text=re.compile('Borough:')).parent
    
    property_text = font_element.get_text() if font_element else ""
    
    # Parse each field using regex
    borough_match = re.search(r'Borough:\s*(.*?)(?=Block:|$)', property_text, re.DOTALL)
    block_match = re.search(r'Block:\s*(.*?)(?=Lot:|$)', property_text, re.DOTALL)
    lot_match = re.search(r'Lot:\s*(.*?)(?=Unit:|$)', property_text, re.DOTALL)
    unit_match = re.search(r'Unit:\s*(.*?)(?=Date Range:|$)', property_text, re.DOTALL)
    
    # Extract the values
    borough = borough_match.group(1).strip() if borough_match else "Not found"
    block = block_match.group(1).strip() if block_match else "Not found"
    lot = lot_match.group(1).strip() if lot_match else "Not found"
    unit = unit_match.group(1).strip() if unit_match else "Not found"
    
    return borough, block, lot, unit

def wait_until_table_is_loaded(page):
    page.wait_for_selector('table table', state='visible', timeout=30000)
    rows_selector = 'table table tr[style^="background-color"]'
    
    # Monitor for stabilization - wait until the row count stops changing
    previous_count = 0
    stable_count = 0
    max_checks = 10
    for _ in range(max_checks):
        current_count = page.locator(rows_selector).count()
        
        # If row count hasn't changed, increment stable counter
        if current_count == previous_count and current_count > 0:
            stable_count += 1
            if stable_count >= 3:  # Three consecutive checks with same count
                break
        else:
            stable_count = 0
            
        previous_count = current_count
        page.wait_for_timeout(1000)
    
    # Add a small additional buffer time
    page.wait_for_timeout(2000)

def parse_property_records_table(page):
    """
    Parse property records table from the webpage.
    
    Args:
        page: Playwright page object that has loaded the records page
        
    Returns:
        list: List of dictionaries with extracted record information
    """
    # Make sure the table is fully loaded
    wait_until_table_is_loaded(page)
    
    # Find all data rows (rows with background color)
    results = []
    
    # Extract all rows that have style attribute and are not header rows
    rows = page.query_selector_all('table table tr[style^="background-color"]')
    
    for row in rows:
        # Extract ID from IMG button
        img_button = row.query_selector('input[name="IMG"]')
        if not img_button:
            continue
        
        # Extract ID from onclick attribute using regex
        onclick_attr = img_button.get_attribute('onclick')
        
        if not onclick_attr:
            continue
        
        id_match = re.search(r'go_image\("([^"]+)"\)', onclick_attr)
        record_id = id_match.group(1) if id_match else ""
        
        # Extract cell contents
        cells = row.query_selector_all('td')
        
        if len(cells) < 14:  # Ensure we have enough cells
            continue
        
        # Extract text from cells, handling potential empty cells
        def extract_text(cell):
            font_tag = cell.query_selector('font')
            return font_tag.inner_text().strip() if font_tag else ""
        
        record = {
            "id": record_id,
            "reel_pg_file": extract_text(cells[1]),
            "crfn": extract_text(cells[2]),
            "lot": extract_text(cells[3]),
            "partial": extract_text(cells[4]),
            "doc_date": extract_text(cells[5]),
            "recorded_filed": extract_text(cells[6]),
            "document_type": extract_text(cells[7]),
            "pages": extract_text(cells[8]),
            "party1": extract_text(cells[9]),
            "party2": extract_text(cells[10]),
            "party3_other": extract_text(cells[11]),
            "more_party_names": True if cells[12].query_selector('img[src*="check.gif"]') else False,
            "doc_amount": extract_text(cells[14])
        }
        
        results.append(record)
    
    return results

def download_document(page, document_id):
    """
    Downloads a document from ACRIS as a PDF file by clicking the Save button.
    
    Args:
        page: Playwright page object
        document_id: ID of the document to download
        
    Returns:
        str: Path to the downloaded PDF file
    """
    # Create documents directory if it doesn't exist
    os.makedirs('documents', exist_ok=True)
    
    # Set download path
    download_path = os.path.join(os.getcwd(), 'documents')
    page.context.set_default_timeout(60000)  # 60 seconds timeout
    
    # Set up download handling
    download_file_path = None
    
    # Navigate to document view page
    url = f"https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentImageView?doc_id={document_id}"
    print(f"Navigating to {url}")
    
    try:
        # Configure download behavior to save automatically
        page.context.set_default_timeout(60000)
        
        # Start waiting for download before clicking
        with page.expect_download(timeout=300000) as download_info:
            # Navigate to the page
            page.goto(url, timeout=60000)
            
            # Wait for the iframe to load
            page.wait_for_selector('iframe[name="mainframe"]', state='visible', timeout=30000)
            
            # Switch to the iframe context
            iframe = page.frame_locator('iframe[name="mainframe"]')
            
            # Wait a moment for the iframe to fully initialize
            page.wait_for_timeout(3000)
            
            # Click the Save button inside the iframe
            print("Clicking Save button...")
            save_button = iframe.locator('td.vtm_buttonCell img[title="Save"]')
            save_button.click()
            
            # Wait for the dialog to appear
            page.wait_for_timeout(2000)
            
            # Click the OK button in the dialog
            print("Clicking OK button in the dialog...")
            ok_button = iframe.locator('span.vtmBtn').filter(has_text="OK")
            ok_button.click()
            
            # Wait for the download to start
            print("Waiting for download to start...")
            
        # Get the download info
        download = download_info.value
        print(f"Download started: {download.suggested_filename}")
        
        # Wait for the download to complete
        download_file_path = os.path.join(download_path, f"{document_id}.pdf")
        download.save_as(download_file_path)
        print(f"Downloaded PDF saved to: {download_file_path}")
        
        return download_file_path
        
    except Exception as e:
        print(f"Error downloading document {document_id}: {str(e)}")
        return None

def search_acris(address: str) -> str:
    """
    Search for property information in the NYC ACRIS database.

    Args:
        address (str): The property address to search for

    Returns:
        str: A summary of the property information found in ACRIS
    """
    # Get optional settings from environment
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    timeout = int(os.getenv("TIMEOUT", "30000"))

    # Parse address to extract components
    # Example: "798 LEXINGTON AVENUE, New York, NY"
    address_parts = address.upper().replace(",", "").split()

    # Try to extract street number and name
    street_number = None
    street_name = []

    for part in address_parts:
        if re.match('\\d+(-\\d+)?', part) and not street_number:
            street_number = part
        elif part not in ["NEW", "YORK", "NY", "MANHATTAN"]:
            street_name.append(part)

    street_name = " ".join(street_name)

    if not street_number or not street_name:
        return "Could not parse address components for ACRIS search"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-debugging-pane",
                "--disable-automation"
            ]
        )

        try:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(timeout)

            # Navigate to ACRIS search page
            # page.goto("https://a836-acris.nyc.gov/DS/DocumentSearch/BBLSearch")
            page.goto('https://a836-acris.nyc.gov/CP/LookUp/Index')
            
            # page.goto("https://a836-acris.nyc.gov/DS/DocumentSearch/BBL")
            
            # Select Manhattan (Borough 1) by default
            page.select_option('select[name="select_borough"]', "1")

            # Enter address information
            page.fill('input[name="text_street_number"]', street_number)
            page.fill('input[name="text_street_name"]', street_name)
            
            # Validate inputs were correctly filled
            actual_street_number = page.input_value('input[name="text_street_number"]')
            actual_street_name = page.input_value('input[name="text_street_name"]')
            
            if actual_street_number != street_number or actual_street_name.strip() != street_name.strip():
                return "Address input validation failed"
            
            with page.context.expect_page() as new_page_info:
                page.click('input[type="submit"]')
            
            # Wait for navigation to complete
            page.wait_for_load_state('networkidle')
            
            # Wait for the btn_docsearch button to be visible and stable
            page.wait_for_selector('input[name="btn_docsearch"]', state='visible', timeout=15000)
            
            page.click('input[name="btn_docsearch"]', timeout=30000)

            # Wait for page to respond after clicking btn_docsearch
            page.wait_for_load_state('networkidle')
            
            # Wait for the Search button to be ready
            page.wait_for_selector('input[type="submit"][value="Search"]', state='visible')
            page.click('input[type="submit"][value="Search"]', timeout=30000)

            # Wait for results
            page.wait_for_selector('table:has(font:has(b:has-text("Current Search Criteria:")))', 
                            state='visible', 
                            timeout=30000)

            # Check if we have results
            no_results = page.locator('text="No Records Found"').count()
            if no_results > 0:
                return f"No records found in ACRIS for {address}"
            
            # Parse property details
            borough, block, lot, unit = parse_property_details(page)
            property_info = {
                "address": address,
                "borough": borough,
                "block": block,
                "lot": lot,
                "unit": unit
            }
            
            # select 99 records
            page.wait_for_load_state('networkidle', timeout=60000)
            page.wait_for_load_state('domcontentloaded', timeout=60000)
            page.select_option('select[name="com_maxrows"]', value="99")
            
            page.wait_for_load_state('networkidle', timeout=60000)
            records = parse_property_records_table(page)
            
            top_mortgage_doc = None
            top_deed_doc = None
                
            # Find first mortgage document and first deed document
            for record in records:
                doc_type = record['document_type'].upper()
                doc_types = [item.strip() for item in doc_type.split(',')]
                
                # Check for mortgage
                if 'MORTGAGE' in doc_types and not top_mortgage_doc:
                    top_mortgage_doc = record
                
                # Check for deed
                if 'DEED' in doc_types and not top_deed_doc:
                    top_deed_doc = record
                
                # Break early if we've found both
                if top_mortgage_doc and top_deed_doc:
                    break
            
            # Format mortgage information
            mortgage_info = None
            mortgage_file = None
            
            if top_mortgage_doc:
                mortgage_info = {
                    "id": top_mortgage_doc.get('id', ''),
                    "lot": top_mortgage_doc.get('lot', ''),
                    "partial": top_mortgage_doc.get('partial', ''),
                    "doc_date": top_mortgage_doc.get('doc_date', ''),
                    "doc_type": top_mortgage_doc.get('document_type', ''),
                    "party1": top_mortgage_doc.get('party1', ''),
                    "party2": top_mortgage_doc.get('party2', ''),
                    "party3": top_mortgage_doc.get('party3_other', '')
                }
                
                mortgage_file = download_document(page, top_mortgage_doc['id'])
            
            # Format deed information
            deed_info = None
            deed_file = None
            
            if top_deed_doc:
                deed_info = {
                    "id": top_deed_doc.get('id', ''),
                    "lot": top_deed_doc.get('lot', ''),
                    "partial": top_deed_doc.get('partial', ''),
                    "doc_date": top_deed_doc.get('doc_date', ''),
                    "doc_type": top_deed_doc.get('document_type', ''),
                    "party1": top_deed_doc.get('party1', ''),
                    "party2": top_deed_doc.get('party2', ''),
                    "party3": top_deed_doc.get('party3_other', '')
                }
                
                deed_file = download_document(page, top_deed_doc['id'])

            # Return the formatted response
            return {
                "property_info": property_info,
                "mortgage_info": mortgage_info,
                "deed_info": deed_info,
                "mortgage_file": mortgage_file,
                "deed_file": deed_file
            }

        except Exception as e:
            
            try:
                # Safely try to access the new page that might have been created
                new_page = new_page_info.value
                
                # Add a timeout to wait_for_load_state to prevent hanging
                new_page.wait_for_load_state(timeout=10000)
                
                # Check if the tax lot not found error is visible
                tax_lot_not_found = new_page.locator('//span[@id="error_box"]/b/font[text()="TAX LOT NOT FOUND"]').is_visible(timeout=5000)
                
                if tax_lot_not_found:
                    return f"Tax lot not found for {address}"
                
            except Exception as inner_e:
                # If anything goes wrong while checking the new page, fall back to the original error
                pass
            
            
            if tax_lot_not_found:
                return f"Tax lot not found for {address}"
            
            
            return f"Error searching ACRIS: {str(e)}"

        finally:
            browser.close()


# Example usage
if __name__ == "__main__":
    
    test_address = "798 LEXINGTON AVENUE, New York, NY"
    acris_results = search_acris(test_address)
    print(f"ACRIS results for {test_address}:")
    print(acris_results)
