import json

from playwright.sync_api import sync_playwright, Page
import time
import os
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Path for storing browser state
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".reonomy_browser_data")
AUTH_FILE = os.path.join(os.path.expanduser("~"), ".reonomy_auth.json")


def is_logged(page: Page) -> bool:
    """
    Checks if the user is logged into Reonomy by navigating to the profile page.

    This function attempts to verify login status by accessing the "My Account" page.
    If logged in, it stores the authentication state in a JSON file.

    Args:
        page (Page): The Playwright page instance.

    Returns:
        bool: True if logged in, False otherwise.

    Best Practices:
    - Avoid using fixed sleep times (`time.sleep(5)`) where possible. Instead, rely on Playwright’s built-in `wait_for_load_state()`.
    - Store authentication data securely if handling sensitive credentials.
    - Consider catching and handling potential exceptions during navigation.
    """

    login_url = "https://app.reonomy.com/"

    try:
        page.goto(login_url, timeout=60000)
        page.wait_for_load_state()
        time.sleep(5)

        # Verify login status by checking for "My Account" in page content
        if "Account" in page.content():
            print("Login successful")

            # Store authentication state
            storage_state = page.context.storage_state()
            with open(AUTH_FILE, "w") as f:
                json.dump(storage_state, f)

            return True

    except Exception as e:
        print(f"Error checking login status: {e}")

    print("Login check failed")
    return False


def login(page: Page):
    """
    Logs into the Reonomy website using Playwright.

    This function navigates to the login page, fills in user credentials,
    handles cookie consent and potential two-factor security code verification,
    and finally checks for a successful login by navigating to the user's profile page.

    Args:
        page (Page): A Playwright page object used to control the browser.

    Returns:
        bool: True if the login process was successful, False otherwise.
    """
    # Define the URLs for login and profile pages.

    try:
        page.context.set_default_timeout(60000)

        if is_logged(page):
            print('Logged by storage')
            return True

        # Handle cookie consent if the dialog is visible.
        cookies_xpath = '//*[@id="onetrust-accept-btn-handler"]'
        if page.is_visible(cookies_xpath):
            page.click(cookies_xpath)
            time.sleep(2)

        # Fill in the email field using the environment variable or a default value.
        email_xpath = '//*[@name="email"]'
        page.query_selector(email_xpath).fill(os.getenv("REONOMY_EMAIL", "test@mail.com"))

        # Fill in the password field similarly.
        password_xpath = '//*[@name="password"]'
        page.query_selector(password_xpath).fill(
            os.getenv("REONOMY_PASSWORD", "test@mail.com")
        )

        # Click the submit button to attempt login.
        submit_xpath = '//*[@name="submit"]'
        if page.is_visible(submit_xpath):
            page.click(submit_xpath)
            time.sleep(15)

        page.wait_for_load_state('domcontentloaded')

        if is_logged(page):
            return True

    except Exception:
        error_details = traceback.format_exc()
        print("Error in login:", error_details)

    return False


def search(address: str, page: Page):
    """
    Searches for a property address on the Reonomy website and navigates to the contact page of the first search result.

    The function performs the following steps:
      1. Opens the Reonomy homepage.
      2. Fills in the search field with the provided property address.
      3. Selects the first result from the search results.
      4. Attempts to click on the "ownership" tab to display the property's contact details.

    Args:
        address (str): The property address to search for.
        page (Page): A Playwright page object used for browser interactions.

    Returns:
        bool: True if the contact page was successfully reached; False otherwise.
    """
    search_url = "https://app.reonomy.com/!/home"

    try:
        page.context.set_default_timeout(60000)
        page.goto(search_url, timeout=60000)
        page.wait_for_load_state()
        time.sleep(5)

        # Locate the search field for the address using its XPath.
        search_xpath = '//*[@id="quick-search-box-input"]'
        # Fill the search field with the provided address.
        page.query_selector(search_xpath).fill(address)
        time.sleep(5)

        # XPath to select the first item in the search results list.
        submit_xpath = '//*[@id="focus-me-first"]'
        # Check if the first search result is visible.
        if page.is_visible(submit_xpath):
            # Click on the first search result.
            page.click(submit_xpath)
            time.sleep(5)

            owner_xpath = '//*[@id="property-details-tab-ownership"]'
            if page.is_visible(owner_xpath):
                page.click(owner_xpath)
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
    Parses owner details from a Reonomy page.

    This function extracts information about real owners and registered (current) owners
    from the given page using Playwright. For each owner, it retrieves details such as name,
    associated owner identifier, address, and phone numbers.

    Args:
        page (Page): A Playwright page object representing the loaded Reonomy details page.

    Returns:
        dict: A dictionary with two keys:
              - 'real_owners': A list of dictionaries containing details for each real owner.
              - 'registered_owners': A list of dictionaries containing details for each registered owner.
    """

    # Initialize the dictionary to store parsed owner details.
    details = {}

    try:
        # --- Parsing Real Owners ---
        print("Start search real owners")
        # XPath to locate real owner elements on the page.
        owner_xpath = '//div[@data-testid="reported-owner-items"]/div'
        reported_owner = page.query_selector_all(owner_xpath)

        # If any real owner elements are found, iterate through each element.
        if reported_owner:
            details["name"] = reported_owner[0].text_content().strip()

            if len(reported_owner) > 1:
                # Extract the owner's address if present.
                details["address"] = reported_owner[1].text_content().strip()

        return details

    except Exception:
        # In case of any exceptions, log the full traceback for debugging.
        error_details = traceback.format_exc()
        print("Error in parsing details:", error_details)

    # Return an empty dictionary if an error occurred.
    return {}


def get_browser_context(playwright, headless=False):
    """Create or reuse a browser context with stored auth state"""
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    params = {
        "headless": headless,
        "args": ["--disable-debugging-pane", "--disable-automation"]
    }

    # Launch browser with persistent context
    browser = playwright.firefox.launch(**params)

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


def search_reonomy(address: str | list) -> dict:
    """
    Searches for property information using the Reonomy system.

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
            context.set_default_timeout(timeout)
            # Create a new browser context and open a new page.
            page = context.new_page()
            # Create a new browser context and open a new page.
            page.set_default_timeout(timeout)

            # Perform login; if it fails, log the error and return an empty dictionary.
            if not login(page):
                print("Something went wrong in login process")
                return {}

            # Initialize the result dictionary
            result = {}
            # Convert single address to a list for uniform processing
            addresses = [address] if isinstance(address, str) else address

            for addr in addresses:
                # Execute the property search using the current address.
                if not search(addr, page):
                    print(f"Something went wrong in search process for address: {addr}")
                    result[addr] = {}
                    continue

                # Parse the property details from the current page.
                property_owner_data = parse_details(page)
                if not property_owner_data:
                    print(f"Something went wrong in parsing details for address: {addr}")
                    result[addr] = {}
                    continue

                # Store the successfully parsed property owner data.
                result[addr] = property_owner_data

            # Return the successfully parsed property owner data.
            return result

        except Exception as e:
            # Log any exceptions that occur during the process for debugging purposes.
            print(f"Error searching Reonomy: {str(e)}")
            return {}

        finally:
            # Ensure the browser is closed to free up resources regardless of success or failure.
            browser.close()


if __name__ == "__main__":
    test_address = ["798 LEXINGTON AVENUE, New York, NY"]
    results = search_reonomy(test_address)
    print(f"Reonomy results for {test_address}:")
    print(results)
