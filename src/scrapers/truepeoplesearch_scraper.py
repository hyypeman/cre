import asyncio
import nodriver as uc
import time
import json
import re
import pandas as pd
import random
import os
import capsolver
from typing import Dict, Any, List, Optional, Union
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set to always search in this location regardless of input address
SEARCH_LOCATION = 'New York, NY'

# Filters out all results for people younger than this age
MINIMUM_AGE_FILTER = 35

# Maximum search result pages to scrape (0 for unlimited)
MAX_SEARCH_PAGES = 10

# API key for solving CAPTCHAs
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY")

async def solve_cloudflare_captcha(page):
    """
    Solves Cloudflare Turnstile CAPTCHA using CapSolver API.

    Args:
        page: The nodriver page instance.
    """
    print("Attempting to solve Cloudflare Turnstile CAPTCHA...")

    # Extract the sitekey
    sitekey = await page.evaluate('''
        (() => {
            const turnstileElement = document.querySelector('div[data-sitekey]');
            return turnstileElement ? turnstileElement.getAttribute('data-sitekey') : null;
        })()
    ''')
    
    if not sitekey:
        raise Exception("Cloudflare siteKey could not be found, unable to solve captcha")
    
    # Get the current URL for the API call
    current_url = await page.evaluate("window.location.href")
    
    # Setup capsolver
    capsolver.api_key = CAPSOLVER_API_KEY
    
    # Call the API to solve the captcha
    solution = capsolver.solve({
        "type": "AntiTurnstileTaskProxyLess",
        "websiteKey": sitekey,
        "websiteURL": current_url,
    })
    
    if not solution or 'token' not in solution:
        raise Exception(f"Failed to get token from CapSolver API: {solution}")
        
    print("Successfully obtained token from CapSolver API")
    
    # Insert the token into the form
    await page.evaluate(f'''
        (() => {{
            const turnstileInput = document.querySelector('input[name="cf-turnstile-response"]');
            if (turnstileInput) {{
                turnstileInput.value = "{solution['token']}";
                return true;
            }}
            return false;
        }})()
    ''')
    
    # Submit the form - using the proper form submit rather than just clicking a button
    form_submitted = await page.evaluate('''
        (() => {
            const captchaForm = document.querySelector('form[action*="/internalcaptcha/captchasubmit"]');
            if (captchaForm) {
                captchaForm.submit();
                return true;
            }
            return false;
        })()
    ''')
    
    if form_submitted:
        print("Successfully submitted captcha form")
        # Wait for the page to load after form submission
        await asyncio.sleep(3)
    else:
        raise Exception("Could not submit captcha form - form not found")

async def parse_search_page(page):
    """
    Parse the search results page and extract basic information about each person.
    
    Args:
        page: The browser page object with loaded search results
        
    Returns:
        List of dictionaries with basic person information including:
        - name: Person's full name
        - URL: Full URL to the person's detail page
        - age: Person's age as integer (0 if unknown or deceased)
        - address: Current address
    """
    results = []
    
    # Iterate each search result
    for card in await page.query_selector_all('div.content-center > div.card-summary:not(.d-none)'):
        result = {}
        result["name"] = (await card.query_selector('div.h4')).text.strip()
        result["URL"] = 'https://www.truepeoplesearch.com' + card.attrs["data-detail-link"]
        
        # Get all result sections
        card_sections = await card.query_selector_all(':scope > div.row > div > div')
        for section in card_sections:
            
            label_element = await section.query_selector('span.content-label')
            if not label_element:
                # First row containing name does not have a label
                continue
            
            section_label = (await section.query_selector('span.content-label')).text.strip().lower()
            section_text = (await section.query_selector('span.content-value')).text.strip()
            
            if section_label == "age":
                try:
                    result["age"] = int(section_text)
                except Exception:
                    # If age cannot be converted to integer, for example age
                    # is "Unknown", then use default value 0
                    result["age"] = 0
                
            elif section_label == "lives in":
                result["address"] = section_text
                
            elif section_label == "deceased":
                result["age"] = 0
             
        results.append(result)

    return results
        
async def extract_phone_numbers(section):
    phone_numbers = {}
    
    # Iterate each phone number
    phone_number_sections = await section.query_selector_all("div.col-12.col-md-6")
    for phone_number_section in phone_number_sections:
        
        phone_number = (await phone_number_section.query_selector("span[itemprop='telephone']")).text.strip()
        phone_type = (await phone_number_section.query_selector("span.smaller")).text.strip().lower()
        last_reported = None
        phone_provider = None
        phone_status = None
        
        phone_details_rows = (await phone_number_section.query_selector_all("span.dt-sb"))
        for index, phone_details_row in enumerate(phone_details_rows):
            
            row_text = phone_details_row.text.strip()
            
            if index == 0 and not row_text.lower().startswith("last reported"):
                phone_status = row_text
                
            elif row_text.lower().startswith("last reported"):
                last_reported = row_text.lower().split("reported")[-1].strip().title()
                
            elif index == len(phone_details_rows) - 1:
                phone_provider = row_text
            
        
        if phone_type not in phone_numbers:
            phone_numbers[phone_type] = []
        
        phone_numbers[phone_type].append({
            "number": phone_number,
            "type": phone_type,
            "last_reported": last_reported,
            "provider": phone_provider,
            "status": phone_status,
        })
        
    return phone_numbers

async def extract_emails(section):
    emails = []
    
    email_rows = await section.query_selector_all("div.row.pl-sm-2")
    for email_row in email_rows:
        emails.append(email_row.text.strip())
        
    return emails

async def extract_businesses(section):
    businesses = []
    business_rows = await section.query_selector_all("div.row")
    
    for row in business_rows:
        business_name_span = await row.query_selector("span.dt-hd")
        
        if not business_name_span:
            continue
        
        business_name = business_name_span.text.strip()
        business_row_inner_html = await (await row.query_selector("div.col")).get_html()
        business_address = business_row_inner_html.split("<br>")[-1].split("<")[0].strip()
        
        businesses.append({
            "Name": business_name,
            "Address": business_address,
        })
    
    return businesses

async def extract_education_and_employment(section):
    education_and_employment = []
    segments = await section.query_selector_all("div.row.pl-sm-2.mt-2")
    
    for segment in segments:
        segment_fields = await segment.query_selector_all("div.col-6.mb-2")
        segment_dict = {}
        
        for segment_field in segment_fields:
            # We need to get html instead of just text,
            # because text returns only key without value
            segment_text_html = (await segment_field.get_html()).strip()
            segment_key = segment_text_html.split("<br>")[0].split(">")[-1].strip()
            
            # Get everything after new line "<br>" and before </div>
            # Do another split on ">" if enclosed within <b> tag
            segment_value = segment_text_html.split("<br>")[1].rsplit("</")[0].split(">")[-1].strip()
            segment_dict[segment_key] = segment_value
            
        education_and_employment.append(segment_dict)
    
    return education_and_employment

async def extract_current_address(section):
    address_link = await section.query_selector('a[href*="/find/address/"]')
    
    # Extract address elements
    street_address = await address_link.query_selector('span[itemprop="streetAddress"]')
    city = await address_link.query_selector('span[itemprop="addressLocality"]')
    state = await address_link.query_selector('span[itemprop="addressRegion"]')
    zip_code = await address_link.query_selector('span[itemprop="postalCode"]')
    
    # Combine address components
    current_address = {
        "street": street_address.text,
        "city": city.text,
        "state": state.text,
        "zip": zip_code.text,
        "full": f"{street_address.text}, {city.text}, {state.text} {zip_code.text}"
    }
    
    return current_address
        
async def extract_details(page, result):
    """
    Extract detailed information from a person's profile page
    
    Args:
        page: The browser page object
        result: The search result dictionary containing the URL to visit
        
    Returns:
        Dict[str, Any]: Updated result dictionary with additional details including:
            - phone_numbers: Dict mapping phone types to lists of phone details
            - emails: List of email addresses
            - possible_business_ownership: List of business details
            - Education and Employment: List of education/employment records
            - current_address: Dict with address components
    """
    try:
        # Navigate to the profile page
        await page.get(result["URL"])
        await asyncio.sleep(3)
        print(f'Opening page: {result["URL"]}')
        
        # Wait for the content to load
        await wait_for_page(page, query_selector="div#personDetails")
        
        # Extract details from profile sections
        sections = await page.query_selector_all("div#personDetails div.row.pl-md-1")
        for section in sections:
            section_title_element = await section.query_selector("div.h5")
            
            if not section_title_element:
                continue
            
            section_title = section_title_element.text.strip().lower()
                
            if section_title == "phone numbers":
                result["phone_numbers"] = await extract_phone_numbers(section)
            
            elif section_title == "email addresses":
                result["emails"] = await extract_emails(section)
            
            elif section_title == "possible business ownership":
                result["possible_business_ownership"] = await extract_businesses(section)
                
            elif section_title == "education and employment":
                result["education_and_employment"] = await extract_education_and_employment(section)
                
            elif section_title == "current address":
                result["current_address"] = await extract_current_address(section)
        
        return result
        
    except Exception as e:
        print(f"Error extracting details: {str(e)}")
        return result
    
async def fill_search_form(page, contact_name, contact_address):
    # We search either contact name or address
    if contact_name:
        # Check if we have Name Search tab selected
        name_tab = await page.select('span#searchTypeName-d')
        
        if not name_tab:
            raise Exception('Error finding Name Search tab')
        
        if 'selected' not in name_tab.attrs['class_']:
            # If we are on different tab, click on Name Search tab
            await (await name_tab.query_selector("span")).click()
            await page.wait_for('span#searchTypeName-d.search-type-selected')
        
        # Make sure contact form is displayed
        name_input = await page.wait_for('div#searchFormNameDesktop input[name="Name"]', timeout=10)
        location_input = await page.select("#searchFormNameDesktop input[name='CityStateZip']", timeout= 10)
        
        if not name_input:
            raise Exception("Name input field not found")
        
        if not location_input:
            raise Exception("Location input field not found")
        
        # Fill the name input field
        await name_input.send_keys(contact_name)
        await asyncio.sleep(0.5)
        inputted_name = await name_input.apply("(elem) => elem.value")
        
        if inputted_name != contact_name:
            raise Exception("Error filling name input")
        
        # Fill the location input field
        await location_input.send_keys(SEARCH_LOCATION)
        await asyncio.sleep(0.5)
        inputted_location = await location_input.apply("(elem) => elem.value")
        
        if inputted_location != SEARCH_LOCATION:
            raise Exception("Error filling location input")
        
        print(f"Searching contact name: {contact_name}")
        
    elif contact_address:
        # Check if we have Address Search tab selected
        address_tab = await page.select('span#searchTypeAddress-d')
        
        if not address_tab:
            raise Exception("Error finding Address Search tab")
        
        if 'selected' not in address_tab.attrs['class_']:
            # If we are on different tab, click on Address Search tab
            await (await address_tab.query_selector("span")).click()
            await page.wait_for('span#searchTypeAddress-d.search-type-selected')

        # Make sure contact form is displayed
        address_input = await page.wait_for('div#searchFormAddressDesktop input[name="StreetAddress"]', timeout=10)
        location_input = await page.select("#searchFormAddressDesktop input[name=\"CityStateZip\"]")
        
        if not address_input:
            raise Exception("Address input field not found")
        
        if not location_input:
            raise Exception("Location input field not found")
        
        # Fill the address input field
        await address_input.send_keys(contact_address)
        await asyncio.sleep(0.5)
        inputted_address = await address_input.apply("(elem) => elem.value")
        
        if inputted_address != contact_address:
            raise Exception("Error filling address input")
        
        # Fill the location input field
        await location_input.send_keys(SEARCH_LOCATION)
        await asyncio.sleep(0.5)
        inputted_location = await location_input.apply("(elem) => elem.value")
        
        if inputted_location != SEARCH_LOCATION:
            raise Exception("Error filling location input")
        
        print(f"Searching address: {contact_address}")
        
async def wait_for_page(page, query_selector, timeout=60):
    """
    Wait until element, identifiable by css selector query_selector,
    is displayed on the page. Handles captcha detection and solving.
    
    Args:
        page: The browser page object
        query_selector (str): CSS selector to wait for
        timeout (int): Maximum wait time in seconds
        
    Returns:
        bool: True if element found within timeout, False otherwise
        
    Note:
        Will automatically detect and solve Cloudflare captchas during wait time
    """
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        if (await page.query_selector("form[action*=\"/internalcaptcha/captchasubmit\"]")):
            await solve_cloudflare_captcha(page)

        if (await page.query_selector(query_selector)):
            return
        
    raise Exception(f"Timeout waiting for selector {query_selector}")

async def run_search(
    contact_name: Optional[str] = None, 
    contact_address: Optional[str] = None
) -> Union[List[Dict[str, Any]], Dict[str, str]]:
    """
    Main search function that launches browser and performs the search.
    
    Args:
        contact_name: Name to search for (format: "FirstName LastName")
        contact_address: Address to search for (format: "Street Address")
        
    Returns:
        Either a list of person records or an error dictionary
        
    Raises:
        Exception: If browser automation fails
    """
    try:
        # Start a browser instance
        browser = await uc.start()
        
        # Search does not work when browser is not maximized
        await browser.main_tab.maximize()
        
        # Navigate to TruePeopleSearch and wait for the page to load
        page = await browser.get('https://www.truepeoplesearch.com/')
        
        # Format search address - remove city, state and zip code
        if contact_address:
            search_contact_address = contact_address.split(",")[0].strip()
        else:
            search_contact_address = None
        
        # Fill either Name or Address, always fill City + State
        await fill_search_form(page, contact_name, search_contact_address)
        
        # Click the search button
        submit_button = await page.query_selector('button#btnSubmit-d-n')
        await submit_button.click()
        print('Submitting search input parameters')
        
        # Wait for results to load
        search_results = []
        page_count = 0
        
        # Wait for results
        await wait_for_page(page, query_selector="div.record-count > div:nth-child(1)")
        
        # Extract number of results
        num_results_element = await page.select('div.record-count > div:nth-child(1)')
        num_results = num_results_element.text
        
        if 'We could not find any records' in num_results:
            return {"error": f"No records found for {contact_name if contact_name else contact_address}"}
        
        numbers = re.findall(r'\d+', num_results)
        total_results = numbers[0]
        print("Number of results", total_results)
        
        while True:
            # Extract result details from current page
            page_results = await parse_search_page(page)
            search_results.extend(page_results)
            
            # Go to next page, if next page is available
            page_count += 1
            next_page_button = await page.query_selector('a#btnNextPage')
            if not next_page_button or (MAX_SEARCH_PAGES and page_count > MAX_SEARCH_PAGES):
                # Next page is not available, or we reached maximum search pages
                break
                
            # Go to next page and wait for results
            await next_page_button.click()
            await wait_for_page(page, query_selector=".card-summary")
            
        # Filter search results based on age requirements (must have age and must be over 35)
        age_filtered_results = [result for result in search_results if result['age'] >= MINIMUM_AGE_FILTER]
        
        # Filter search results based on location, keep NY state
        location_filtered_results = [r for r in age_filtered_results if r['address'].split(",")[-1].strip() == "NY"]
        
        # Extract details from each person page
        for result in location_filtered_results:
            await extract_details(page, result)
            
        # Add our search parameters (name or address)
        for result in location_filtered_results:
            
            if contact_name:
                result["contact_name"] = contact_name
                
            elif contact_address:
                result["contact_address"] = contact_address
        
        return location_filtered_results
        
    except Exception as e:
        raise e
    
    finally:
        # Close the browser
        browser.stop()

def search_truepeoplesearch(
    contact_name: Optional[str] = None, 
    contact_address: Optional[str] = None
) -> Union[List[Dict[str, Any]], Dict[str, str]]:
    """
    Search for a person on TruePeopleSearch
    
    Args:
        contact_name (str, optional): Name of the person to search for
        contact_address (str, optional): Address to search for
        
    Returns:
        list: List of dictionaries containing search results or error dict
    """
    try:
        if not contact_name and not contact_address:
            raise Exception('No contact name or contact address to search')
        
        data = asyncio.run(run_search(contact_name=contact_name, contact_address=contact_address))
        return data
    except Exception as e:
        return {"error": f"Error while extracting information for {contact_name if contact_name else contact_address}, {str(e)}"}

# Example usage
if __name__ == "__main__":
    # Search by name
    contact_name = 'Edward Song'
    results = search_truepeoplesearch(contact_name=contact_name)
    print(json.dumps(results, indent=4))
    
    # Search by address
    contact_address = "1185 SIXTH AVE FL 10, NEW YORK, 10036, NY, United States"
    results = search_truepeoplesearch(contact_address=contact_address)
    print(json.dumps(results, indent=4))
    