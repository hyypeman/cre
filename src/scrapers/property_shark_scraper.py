import re
import json

from playwright.sync_api import sync_playwright, Page
import time
import os
from dotenv import load_dotenv
import traceback
from imapclient import IMAPClient
import email
from email.policy import default

# Load environment variables
load_dotenv()

IMAP_SERVER = "imap.gmail.com"
SUBJECT_FILTER = "Your security code"
WAIT_TIME = 120  # 2 minutes (in seconds)

# Path for storing browser state
AUTH_FILE = os.path.join(os.path.expanduser("~"), ".opencorporates_firefox_auth.json")

def get_browser_context(playwright, headless=False):
    """Create or reuse a browser context with stored auth state using Firefox"""
    # Launch Firefox browser instead of Chromium
    browser = playwright.firefox.launch(
        headless=headless,
        args=[
            "--disable-debugging-pane",  # Disable the debugging pane for a cleaner UI.
            "--disable-automation",  # Disable automation flags to reduce detection.
        ],
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


def get_security_code():
    with IMAPClient(IMAP_SERVER) as client:
        client.login(
            os.getenv("PROPERTY_SHARK_EMAIL", ""), os.getenv("PROPERTY_SHARK_IMAP_PASSWORD", "")
        )
        client.select_folder("INBOX")

        start_time = time.time()
        while time.time() - start_time < WAIT_TIME:
            messages = client.search(["UNSEEN", "SUBJECT", SUBJECT_FILTER])
            if messages:
                for msg_id in messages:
                    raw_message = client.fetch([msg_id], ["RFC822"])
                    msg = email.message_from_bytes(raw_message[msg_id][b"RFC822"], policy=default)

                    # Extract text content from email
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                    else:
                        body = msg.get_payload(decode=True).decode()

                    # Extract security code (assumes it's a 5-digit number)
                    match = re.search(r"\b\d{5}\b", body)
                    if match:
                        return match.group()  # Return the security code
            time.sleep(10)  # Wait 10 seconds before checking again

        return None


def login(page: Page):
    """
    Logs into the PropertyShark website using Playwright.

    This function navigates to the login page, fills in user credentials,
    handles cookie consent and potential two-factor security code verification,
    and finally checks for a successful login by navigating to the user's profile page.

    Args:
        page (Page): A Playwright page object used to control the browser.

    Returns:
        bool: True if the login process was successful, False otherwise.
    """
    # Define the URLs for login and profile pages.
    login_url = "https://www.propertyshark.com/mason/Accounts/logon.html"
    profile_url = "https://www.propertyshark.com/mason/Accounts/My/"
    search_url = "https://www.propertyshark.com/"

    try:
        # First, go to search page and check if we are logged in
        page.context.set_default_timeout(60000)
        page.goto(search_url, timeout=60000)
        page.wait_for_load_state()
        time.sleep(5)
        
        if is_logged_in(page):
            # We are logged in already, we can skip login process
            return True

        # We are not logged in => log in process required
        page.goto(login_url, timeout=60000)
        page.wait_for_load_state()
        time.sleep(5)

        # Handle cookie consent if the dialog is visible.
        cookies_xpath = '//*[@id="onetrust-accept-btn-handler"]'
        if page.is_visible(cookies_xpath):
            page.click(cookies_xpath)
            time.sleep(2)

        # Fill in the email field using the environment variable or a default value.
        email_xpath = '//*[@id="email"]'
        page.query_selector(email_xpath).fill(os.getenv("PROPERTY_SHARK_EMAIL", "test@mail.com"))

        # Fill in the password field similarly.
        password_xpath = '//*[@id="password"]'
        page.query_selector(password_xpath).fill(
            os.getenv("PROPERTY_SHARK_PASSWORD", "test@mail.com")
        )

        # Click the submit button to attempt login.
        submit_xpath = '//*[@id="sbo"]'
        if page.is_visible(submit_xpath):
            page.click(submit_xpath)
            time.sleep(5)

        # Check if a security code is required (i.e., two-factor authentication).
        if "PropertyShark Account Security" in page.content():
            print("Need get code from email")
            code = get_security_code()
            if not code:
                print("Not find code in email")
                return False

            print("Find code -> %s" % code)
            code_xpath = "//input[@name='security_code']"
            page.query_selector(code_xpath).fill(code)

            # Re-submit the form after entering the security code.
            submit_xpath = '//*[@id="sbo"]'
            if page.is_visible(submit_xpath):
                page.click(submit_xpath)
                time.sleep(5)

                # Verify if the entered security code is invalid.
                if "Invalid security code" in page.content():
                    print("Invalid security code")
                    return False

        # Dismiss any pop-up that might appear (e.g., a "No Thanks" offer).
        pop_xpath = '//a[text()="No Thanks"]'
        if page.is_visible(pop_xpath):
            page.click(pop_xpath)
            time.sleep(1)

        # Navigate to the profile page to verify that the login was successful.
        page.goto(profile_url, timeout=60000)
        page.wait_for_load_state()
        time.sleep(5)

        # Confirm login success by checking for the presence of "My Account" text.
        if is_logged_in(page):
            print("Login success")
            
            # Store authentication state
            storage_state = page.context.storage_state()
            with open(AUTH_FILE, "w") as f:
                json.dump(storage_state, f)
            
            return True

    except Exception:
        error_details = traceback.format_exc()
        print("Error in login:", error_details)

    return False


def search(address: str, page: Page):
    """
    Searches for a property address on the PropertyShark website and navigates to the contact page of the first search result.

    The function performs the following steps:
      1. Opens the PropertyShark homepage.
      2. Fills in the search field with the provided property address.
      3. Selects the first result from the search results.
      4. Attempts to click on the "contacts" tab to display the property's contact details.

    Args:
        address (str): The property address to search for.
        page (Page): A Playwright page object used for browser interactions.

    Returns:
        bool: True if the contact page was successfully reached; False otherwise.
    """
    search_url = "https://www.propertyshark.com/"

    try:
        # Open search page if it's not opened (if we just logged in)
        if page.url != search_url:
            page.context.set_default_timeout(60000)
            page.goto(search_url, timeout=60000)
            page.wait_for_load_state()
            time.sleep(5)

        # Locate the search field for the address using its XPath.
        search_xpath = '//*[@id="search_token_address"]'
        # Fill the search field with the provided address.
        page.query_selector(search_xpath).fill(address)
        time.sleep(5)

        # XPath to select the first item in the search results list.
        submit_xpath = '//div[@class="properties-list"]/li[1]'
        # Check if the first search result is visible.
        if page.is_visible(submit_xpath):
            # Click on the first search result.
            page.click(submit_xpath)
            time.sleep(5)

            # Get the current URL and append the hash fragment
            new_url = f"{page.url}#section_contacts"

            # Navigate to the new URL
            page.goto(new_url)
            time.sleep(5)

            page.reload()
            time.sleep(5)
            return True
        else:
            # Log if no search results are found for the provided address.
            print("Not found search results")
    except Exception:
        # Capture and print the complete traceback for debugging in case of errors.
        error_details = traceback.format_exc()
        print("Error in search:", error_details)

    # Return False if the process did not complete successfully.
    return False


def parse_details(page: Page) -> dict:
    """
    Parses owner details from a PropertyShark page.

    This function extracts information about real owners and registered (current) owners
    from the given page using Playwright. For each owner, it retrieves details such as name,
    associated owner identifier, address, and phone numbers.

    Args:
        page (Page): A Playwright page object representing the loaded PropertyShark details page.

    Returns:
        dict: A dictionary with two keys:
              - 'real_owners': A list of dictionaries containing details for each real owner.
              - 'registered_owners': A list of dictionaries containing details for each registered owner.
    """

    # Initialize the dictionary to store parsed owner details.
    details = {"real_owners": [], "registered_owners": []}

    try:
        # --- Parsing Real Owners ---
        print("Start search real owners")
        # XPath to locate real owner elements on the page.
        real_owners_xpath = '//*[@id="real_owners_list"]/div'
        real_owners = page.query_selector_all(real_owners_xpath)

        # If any real owner elements are found, iterate through each element.
        if real_owners:
            for real_owner in real_owners:
                detail = {}

                # Extract the owner's name if available.
                name_element = real_owner.query_selector('//div[@class="name"]')
                if name_element:
                    detail["name"] = name_element.text_content().strip()

                # Extract the real owner identifier or description.
                owner_id_element = real_owner.query_selector(
                    "//div/span[contains(@id, 'real_owner')]"
                )
                if owner_id_element:
                    detail["real_owner"] = owner_id_element.text_content().strip()

                # Extract the owner's address if present.
                address_element = real_owner.query_selector('//div[@class="address_pin"]')
                if address_element:
                    detail["address"] = address_element.text_content().strip()

                # Extract phone numbers if available.
                phone_container = real_owner.query_selector('//div[contains(@class, "reo-phones")]')
                if phone_container:
                    phones = []
                    # XPath to locate individual phone elements.
                    phones_selectors = real_owner.query_selector_all(
                        '//div[contains(@id, "invalid_phone_")]'
                    )
                    for phone in phones_selectors:
                        phone_link = phone.query_selector("//a")
                        if phone_link:
                            phones.append(phone_link.text_content().strip())
                    if phones:
                        detail["phones"] = phones

                # Append the details if any information was extracted.
                if detail:
                    details["real_owners"].append(detail)

        # --- Parsing Registered (Current) Owners ---
        print("Start search current owners")
        # XPath to locate rows in the current owners table.
        current_owners_xpath = '//*[@id="current_owners_my_table_table_ajax"]/tbody/tr'
        current_owners = page.query_selector_all(current_owners_xpath)

        # If any registered owner rows are found, process each row.
        if current_owners:
            for current_owner in current_owners:
                # Initialize a detail dictionary with a 'data' key to store owner info.
                detail = {"data": []}

                # Locate all elements containing detailed lines about the owner.
                details_lines = current_owner.query_selector_all(
                    "//div[contains(@class, 'details-line')]"
                )
                if details_lines:
                    for line in details_lines:
                        detail["data"].append(line.text_content().strip())

                # Add the detail to the list if any data was extracted.
                if detail["data"]:
                    details["registered_owners"].append(detail)

        return details

    except Exception:
        # In case of any exceptions, log the full traceback for debugging.
        error_details = traceback.format_exc()
        print("Error in parsing details:", error_details)

    # Return an empty dictionary if an error occurred.
    return {}


def is_logged_in(page):
    # Confirm login success by checking for the presence of "My Account" text.
    if "My Account" in page.content():
        return True
    return False


def search_shark(address: str) -> dict:
    """
    Searches the NYC ACRIS database for property information using the SHARK system.

    This function uses Playwright to launch a Firefox browser, perform a login,
    execute a property search based on the provided address, and then parse the resulting details.
    It returns a dictionary containing property owner data if successful, or an empty dictionary if any step fails.

    Args:
        address (str): The property address to search for.

    Returns:
        dict: A dictionary summarizing the property information from ACRIS,
              or an empty dictionary if an error occurs during the process.
    """
    # Retrieve optional configuration settings from environment variables.
    # HEADLESS determines if the browser runs in headless mode.
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    # TIMEOUT sets the maximum wait time for page operations (default is 30000 ms).
    timeout = int(os.getenv("TIMEOUT", "30000"))

    # Initialize Playwright and launch a Firefox browser instance.
    with sync_playwright() as p:
        browser, context = get_browser_context(p, headless=headless)

        try:
            # Create a new browser context and open a new page.
            context = browser.new_context()
            page = context.new_page()
            # Set the default timeout for all actions on this page.
            page.set_default_timeout(timeout)

            # Perform login; if it fails, log the error and return an empty dictionary.
            if not login(page):
                print("Something went wrong in login process")
                return {}

            # Execute the property search using the provided address.
            if not search(address, page):
                print("Something went wrong in search process")
                return {}

            # Parse the property details from the current page.
            property_owner_data = parse_details(page)
            if not property_owner_data:
                print("Something went wrong in parsing details")
                return {}

            # Return the successfully parsed property owner data.
            return property_owner_data

        except Exception as e:
            # Log any exceptions that occur during the process for debugging purposes.
            print(f"Error searching SHARK: {str(e)}")
            return {}

        finally:
            # Ensure the browser is closed to free up resources regardless of success or failure.
            browser.close()


if __name__ == "__main__":
    test_address = "19 W 34th Street, New York, NY"
    results = search_shark(test_address)
    print(f"SHARK results for {test_address}:")
    print(results)
