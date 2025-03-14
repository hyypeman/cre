from playwright.sync_api import sync_playwright, Page
from typing import Dict, Any, List, Optional
from difflib import SequenceMatcher
import os
import re
import json
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

PREFERRED_STATE = "New York"
PREFERRED_COUNTRY = "US"
MAX_RESULT_PAGES = 10  # 300 results

OPENCORPORATES_USERNAME = os.environ.get("OPENCORPORATES_USERNAME")
OPENCORPORATES_PASSWORD = os.environ.get("OPENCORPORATES_PASSWORD")

# Path for storing browser state
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".opencorporates_browser_data")
AUTH_FILE = os.path.join(os.path.expanduser("~"), ".opencorporates_auth.json")


def parse_result(result_row):
    """
    Parse one result row from search.
    Return formatted dict with information about the company.
    """

    # extract company name
    company_name_element = result_row.locator("a.company_search_result")
    company_name = company_name_element.inner_text()

    # extract company page URL
    company_url = "https://opencorporates.com" + company_name_element.get_attribute("href")

    # extract jurisdiction - country, state, address
    full_result_text = result_row.inner_text()

    # looking for patterns like "(New York (US), ATTN: NICOLE CHRZAN, 798 LEXINGTON AVE, NEW YORK, NY, 10065)"
    jurisdiction_match = re.search(r"\(([^(]+?)\s*\(([^)]+?)\)", full_result_text)

    state = ""
    country = ""
    address = ""

    if jurisdiction_match:
        state = jurisdiction_match.group(1).strip()
        country = jurisdiction_match.group(2).strip()

        # Try to extract the full address if available
        address_match = re.search(r"\([^(]+?\([^)]+?\)(.*?)\)", full_result_text)
        if address_match and address_match.group(1):
            address = address_match.group(1).strip()
            if address.startswith(","):
                address = address[1:].strip()

    alt_name = None

    if (
        "previously" in full_result_text.lower()
        or "alternatively known as" in full_result_text.lower()
    ):
        # Check if our search term is mentioned in the alternative names
        alt_name_match = re.search(
            r"(?:previously|alternatively)\s+known\s+as\s+(.*?)(?:\)|$)",
            full_result_text,
            re.IGNORECASE,
        )
        if alt_name_match:
            alt_name = alt_name_match.group(1).strip()

    # extract company start date
    start_date_element = result_row.locator("span.start_date")

    # Check if the element exists
    if start_date_element.count() > 0:
        # Element exists, extract its text
        company_start_date = start_date_element.inner_text()
    else:
        # Element doesn't exist, set to None or a default value
        company_start_date = None

    company_info = {
        "company_name": company_name,
        "country": country,
        "state": state,
        "address": address,
        "alternative_name": alt_name,
        "start_date": company_start_date,
        "URL": company_url,
    }

    return company_info


def is_matching_company_name(name1, name2, threshold=0.95):
    """
    Determines if two company names refer to the same company, accounting for
    variations in capitalization, punctuation, legal suffixes, and abbreviations.

    Args:
        name1 (str): The first company name to compare
        name2 (str): The second company name to compare
        threshold (float, optional): Minimum similarity threshold for sequence matching.
                                     Default is 0.95.

    Returns:
        bool: True if the names likely refer to the same company, False otherwise
    """
    if not name1 or not name2:
        return False

    # Normalize both strings
    norm1 = normalize_company_name(name1)
    norm2 = normalize_company_name(name2)

    # Direct match after normalization
    if norm1 == norm2:
        return True

    # Use sequence matcher for handling slight variations
    # This is especially useful for typos or slight word differences
    similarity_ratio = SequenceMatcher(None, norm1, norm2).ratio()
    if similarity_ratio >= threshold:
        return True

    return False


def normalize_company_name(name):
    """
    Normalizes a company name for comparison by:
    - Converting to lowercase
    - Removing common legal suffixes (LLC, Inc, Ltd, etc.)
    - Replacing common abbreviations
    - Removing punctuation and extra whitespace
    - Preserving numbers and distinctive identifiers

    Args:
        name (str): The company name to normalize

    Returns:
        str: The normalized company name
    """
    if not name:
        return ""

    # Convert to lowercase
    result = name.lower()

    # Define common legal suffixes to remove
    legal_suffixes = [
        r"\bllc\b",
        r"\binc\b",
        r"\binc\.$",
        r"\bltd\b",
        r"\bltd\.$",
        r"\bcorp\b",
        r"\bcorp\.$",
        r"\bcorporation\b",
        r"\bco\b",
        r"\bco\.$",
        r"\bcompany\b",
        r"\blimited\b",
        r"\blp\b",
        r"\bl\.p\.$",
        r"\bplc\b",
        r"\bp\.l\.c\.$",
        r"\bllp\b",
        r"\bl\.l\.p\.$",
    ]

    # Remove legal suffixes
    for suffix in legal_suffixes:
        result = re.sub(suffix, "", result)

    # Replace common abbreviations
    abbreviations = {
        "intl": "international",
        "int": "international",
        "assn": "association",
        "assoc": "associates",
        "mgmt": "management",
        "svcs": "services",
        "svc": "service",
        "grp": "group",
        "tech": "technology",
        "techs": "technologies",
        "sys": "systems",
        "bro": "brothers",
        "bros": "brothers",
        "mfg": "manufacturing",
    }

    for abbr, full in abbreviations.items():
        result = re.sub(rf"\b{abbr}\b", full, result)

    # Remove punctuation and special characters
    result = re.sub(r"[^\w\s-]", "", result)

    # Replace ampersand with 'and'
    result = result.replace("&", "and")

    # Remove extra whitespace and trim
    result = re.sub(r"\s+", " ", result).strip()

    return result


def get_search_results(page):
    # Wait for results to be displayed
    results_counter_selector = '//h2[contains(text(), "Found") and contains(text(), "companies")]'
    page.wait_for_selector(results_counter_selector, state="visible", timeout=30000)

    # Get number of results
    results_count = page.locator(results_counter_selector).inner_text().strip()
    counter_match = re.search(r"Found\s+(\d+[\,\d]*)\s+companies", results_count)
    # Remove commas from number if present (e.g., "1,234" -> "1234")
    number_str = counter_match.group(1).replace(",", "")
    total_results = int(number_str)

    # If more than 300 results (10 result pages), then restrict
    # it to New York US location if possible
    if total_results > 300 and page.locator('a[title="restrict to New York (US)"]').count() > 0:
        page.click('a[title="restrict to New York (US)"]')

        # Wait for results to be displayed
        page.wait_for_selector(results_counter_selector, state="visible", timeout=30000)

    page_counter = 0
    results = []

    while True:
        # Get all company results
        company_results = page.locator("ul.companies > li")
        count = company_results.count()

        # Iterate through all the results
        for i in range(count):
            result_row = company_results.nth(i)

            # Get the company name element
            company_name_element = result_row.locator("a.company_search_result")
            is_inactive = company_name_element.evaluate("el => el.classList.contains('inactive')")

            # company is inactive, skip this record
            if is_inactive:
                continue

            company_info = parse_result(result_row)
            results.append(company_info)

        page_counter += 1

        if page_counter > MAX_RESULT_PAGES:
            break

        if page.locator("li.next.next_page:not(.disabled) a").count() > 0:
            page.click("li.next.next_page:not(.disabled) a")

            # Wait for results to be displayed
            page.wait_for_selector(results_counter_selector, state="visible", timeout=30000)
        else:
            break

    return results


def extract_company_info(page: Page) -> Dict[str, Any]:
    """
    Extract company information from an OpenCorporates company page.

    Args:
        page: A Playwright page object that has navigated to an OpenCorporates company page

    Returns:
        A dictionary containing all extracted company information
    """
    company_info = {}

    # Basic company information
    company_info["name"] = _get_text_if_exists(page, "h1.wrapping_heading")

    # Extract all attributes from the DL list
    attributes = {
        "company_number": _get_text_if_exists(page, "dd.company_number"),
        "status": _get_text_if_exists(page, "dd.status"),
        "company_type": _get_text_if_exists(page, "dd.company_type"),
        "jurisdiction": _get_text_if_exists(page, "dd.jurisdiction a"),
    }

    # Add agent information only if present
    agent_name = _get_text_if_exists(page, "dd.agent_name")
    if agent_name:
        attributes["agent_name"] = agent_name

    agent_address = _get_text_if_exists(page, "dd.agent_address")
    if agent_address:
        attributes["agent_address"] = agent_address

    # Incorporation date needs special handling to extract the date
    incorporation_date_elem = page.locator("dd.incorporation_date span")
    if incorporation_date_elem.count() > 0:
        incorporation_date_text = incorporation_date_elem.inner_text()
        # Try to extract just the date part (e.g., "26 May 1995")
        date_match = re.search(r"(\d+\s+\w+\s+\d{4})", incorporation_date_text)
        if date_match:
            attributes["incorporation_date"] = date_match.group(1)

    # Extract branch information if available
    branch_elem = page.locator("dd.branch")
    if branch_elem.count() > 0:
        branch_company_link = branch_elem.locator("a.company")
        if branch_company_link.count() > 0:
            branch_company_name = branch_company_link.inner_text().strip()
            branch_company_url = "https://opencorporates.com" + branch_company_link.get_attribute(
                "href"
            )

            # Get jurisdiction from the text, which typically has format "Branch of COMPANY_NAME (Jurisdiction)"
            branch_text = branch_elem.inner_text().strip()
            jurisdiction_match = re.search(r"\(([^)]+)\)$", branch_text)
            branch_jurisdiction = (
                jurisdiction_match.group(1).strip() if jurisdiction_match else None
            )

            # Extract company number from the URL
            company_number = None
            if branch_company_url:
                company_number = branch_company_url.split("/")[-1]

            attributes["branch"] = {
                "name": branch_company_name,
                "url": branch_company_url,
                "jurisdiction": branch_jurisdiction,
                "company_number": company_number,
            }

    # Extract registered address
    contact_person = None
    registered_address_lines = page.locator(
        "dd.registered_address ul.address_lines li.address_line"
    )
    if registered_address_lines.count() > 0:
        address_lines = []
        for i in range(registered_address_lines.count()):
            line = registered_address_lines.nth(i).inner_text().strip()

            if "ATTN:" in line:
                # If ATTN in the address line, extract it as contact person
                contact_person = line.split("ATTN:")[1].split(",")[0].strip()
                line = line.split(",")[1].strip()

            if line:
                address_lines.append(line)
        attributes["registered_address"] = ", ".join(address_lines)

    if contact_person:
        attributes["contact_person"] = contact_person

    # Extract previous names
    previous_names_lines = page.locator("dd.previous_names ul.name_lines li.name_line")
    if previous_names_lines.count() > 0:
        previous_names = []
        for i in range(previous_names_lines.count()):
            name = previous_names_lines.nth(i).inner_text().strip()
            if name:
                previous_names.append(name)
        attributes["previous_names"] = previous_names

    # Extract active officers/directors
    attributes["officers"] = _extract_officers(
        page, "dd.officers ul.attribute_list li.attribute_item"
    )

    # Extract inactive officers/directors
    attributes["inactive_officers"] = _extract_officers(
        page, "dd.inactive_officers ul.attribute_list li.attribute_item", inactive=True
    )

    # Add extracted attributes to company_info
    company_info.update(attributes)

    # Extract data freshness information
    freshness_info = {
        "last_update_from_source": _get_text_if_exists(page, "dd.last_update_from_source"),
        "last_change_recorded": _get_text_if_exists(page, "dd.last_change_recorded"),
        "next_update_from_source": _get_text_if_exists(page, "dd.next_update_from_source"),
    }

    # Extract source information
    source_elem = page.locator("dd.source a")
    if source_elem.count() > 0:
        freshness_info["source_name"] = source_elem.inner_text().strip()
        freshness_info["source_url"] = source_elem.get_attribute("href")

    company_info["data_freshness"] = freshness_info

    # Extract home company information if available
    home_company_row = page.locator(
        "#data-table-branch_relationship_object table.company-data-object tbody tr"
    )
    if home_company_row.count() > 0:
        home_company_link = home_company_row.locator("a.company")
        if home_company_link.count() > 0:
            home_company_name = home_company_link.inner_text().strip()
            home_company_url = "https://opencorporates.com" + home_company_link.get_attribute(
                "href"
            )

            # Extract jurisdiction
            jurisdiction_link = home_company_row.locator("a.jurisdiction_filter")
            jurisdiction = (
                jurisdiction_link.inner_text().strip() if jurisdiction_link.count() > 0 else None
            )

            # Extract company number from URL - appears after last slash in URL
            company_number = None
            if home_company_url:
                company_number = home_company_url.split("/")[-1]

            # Extract dates if available
            company_text = home_company_row.inner_text()
            start_date = None
            date_match = re.search(r"(\d+\s+[A-Za-z]+\s+\d{4})\s*-", company_text)
            if date_match:
                start_date = date_match.group(1).strip()

            # Get details URL if available
            details_link = home_company_row.locator('a:has-text("details")')
            details_url = (
                "https://opencorporates.com" + details_link.get_attribute("href")
                if details_link.count() > 0
                else None
            )

            company_info["home_company"] = {
                "name": home_company_name,
                "url": home_company_url,
                "jurisdiction": jurisdiction,
                "company_number": company_number,
                "start_date": start_date,
                "details_url": details_url,
            }

    # Extract additional company addresses from assertions
    company_addresses = page.locator("div.assertion.company_address")
    if company_addresses.count() > 0:
        additional_addresses = []
        for i in range(company_addresses.count()):
            address_item = company_addresses.nth(i)

            address_type = address_item.locator("div.subhead a").inner_text().strip()
            address_text = address_item.locator("p.description").inner_text().strip()

            additional_addresses.append({"type": address_type, "address": address_text})

        company_info["additional_addresses"] = additional_addresses

    company_info["URL"] = page.url

    return company_info


def _extract_officers(page, selector, inactive=False):
    """
    Extract officer information from a given selector.

    Args:
        page: A Playwright page object
        selector: CSS selector for officer items
        inactive: Boolean indicating if these are inactive officers

    Returns:
        List of officer dictionaries with name, role, and URL
    """
    officers = []
    officer_items = page.locator(selector)

    if officer_items.count() > 0:
        for i in range(officer_items.count()):
            officer_item = officer_items.nth(i)
            officer_link = officer_item.locator("a.officer" + (".inactive" if inactive else ""))

            if officer_link.count() > 0:
                officer_name = officer_link.inner_text().strip()
                officer_url = officer_link.get_attribute("href")

                # Extract role from text after the link
                full_text = officer_item.inner_text().strip()
                role = full_text.replace(officer_name, "").strip().strip(",").strip()

                officers.append(
                    {
                        "name": officer_name,
                        "role": role,
                        "url": "https://opencorporates.com" + officer_url,
                        "inactive": inactive,
                    }
                )

    return officers


def _get_text_if_exists(page: Page, selector: str) -> Optional[str]:
    """Helper function to safely get text from an element if it exists"""
    element = page.locator(selector)
    if element.count() > 0:
        return element.inner_text().strip()
    return None


def get_browser_context(playwright, headless=False):
    """Create or reuse a browser context with stored auth state"""
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    # Launch browser with persistent context
    browser = playwright.chromium.launch(
        headless=headless, args=["--disable-debugging-pane", "--disable-automation"]
    )

    # Create a context - either new or with stored auth state
    if os.path.exists(AUTH_FILE):
        # Load stored auth state
        try:
            with open(AUTH_FILE, "r") as f:
                storage_state = json.load(f)

            context = browser.new_context(storage_state=storage_state)
            print("Using stored authentication state")
        except Exception as e:
            print(f"Error loading auth state: {e}")
            context = browser.new_context()
    else:
        # No stored auth state
        context = browser.new_context()

    return browser, context


def is_logged_in(page):
    """Check if the user is logged in by looking for login/signup button"""
    # login_selector = '//div[contains(@class, "header_menu_box")] //li //span[@itemprop="name" and text()="Login"]'
    # return page.locator(login_selector).count() == 0
    return page.url.endswith("?logged_in")


def login_to_opencorporates(page):
    """Log in to OpenCorporates website"""
    # Navigate to login page
    page.goto("https://opencorporates.com/users/sign_in")
    page.wait_for_selector("#user_password", state="visible", timeout=30000)

    # Fill in login form
    page.fill("#user_email", OPENCORPORATES_USERNAME)
    page.fill("#user_password", OPENCORPORATES_PASSWORD)

    # Check the "Remember me" checkbox
    page.check("#user_remember_me")

    # Click the submit button with the correct selector
    page.click('button[name="submit"]')

    # Wait for navigation after login
    page.wait_for_load_state("networkidle")

    # Verify login success
    if is_logged_in(page):
        print("Successfully logged in!")

        # Store authentication state
        storage_state = page.context.storage_state()
        with open(AUTH_FILE, "w") as f:
            json.dump(storage_state, f)

        return True
    else:
        raise Exception("Login failed!")


def filter_search_results(results, owner_name):
    # Filter based on company name
    matching_names = []

    for result in results:
        # Compare company current name to the owner name
        if is_matching_company_name(result["company_name"], owner_name):
            matching_names.append(result)
            continue

        # If company has a previous name, compare that too
        if "alternative_name" not in result or not result["alternative_name"]:
            continue

        if is_matching_company_name(result["alternative_name"], owner_name):
            matching_names.append(result)

    # Keep only companies based in the US
    matching_country = [r for r in matching_names if r["country"] == PREFERRED_COUNTRY]

    if not matching_country:
        raise Exception(f"No results for {owner_name}")

    # Return if there is exactly one match
    if len(matching_country) == 1:
        return matching_country

    # If still multiple results, filter based on state,
    # where preferred state is New York
    matching_state = [r for r in matching_country if r["state"] == PREFERRED_STATE]

    # If no companies from New York, return all companies matched in previous step
    if not matching_state:
        return matching_country

    # If one or more companies are from New York, return them all
    return matching_state


def search_opencorporate(owner_name):
    # Get optional settings from environment
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    timeout = int(os.getenv("TIMEOUT", "30000"))

    if not OPENCORPORATES_USERNAME:
        return {"error": "Error: OPENCORPORATES_USERNAME environment variable not set"}

    if not OPENCORPORATES_PASSWORD:
        return {"error": "Error: OPENCORPORATES_PASSWORD environment variable not set"}

    with sync_playwright() as p:
        browser, context = get_browser_context(p, headless=headless)

        try:
            context.set_default_timeout(timeout)
            page = context.new_page()
            page.set_default_timeout(timeout)

            # Navigate to OpenCorporates search page
            page.goto("https://opencorporates.com/")

            # Wait for the page to load
            page.wait_for_selector("input.oc-home-search_input", state="visible", timeout=15000)

            # Input owner name and submit search
            page.fill("input.oc-home-search_input", normalize_company_name(owner_name))
            page.click("button.oc-home-search_button")

            # Get results from all search result pages
            page_results = get_search_results(page)

            # Keep the most likely correct match
            # - if more than one company match the owner name and we cannot
            #   filter based on NY state, return all results
            matching_records = filter_search_results(page_results, owner_name)

            companies_data = []

            for matching_record in matching_records:
                page.goto(matching_record["URL"])

                # Wait for company data to be displayed
                page.wait_for_selector("dd.company_number", state="visible", timeout=30000)

                # If we are not logged in, perform login to display officers
                # - store browser profile and load it next time, so we do not
                #   have to login again in the next search
                if (
                    page.locator(
                        '//dd[contains(@class, "officers")] /a[contains(text(), "please log in")]'
                    ).count()
                    > 0
                ):
                    current_page_url = page.url
                    login_to_opencorporates(page)
                    page.goto(current_page_url)

                company_details = extract_company_info(page)
                companies_data.append(company_details)

            search_data = {"owner_name": owner_name, "companies": companies_data}

            return search_data

        except Exception as e:
            return {"error": f"Error searching company owner: {str(e)}"}

        finally:
            # Close browser when done
            browser.close()


if __name__ == "__main__":
    print(search_opencorporate("44 West 34th Street"))
