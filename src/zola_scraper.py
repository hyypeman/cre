from playwright.sync_api import sync_playwright
import time
from dotenv import load_dotenv
import os
from playwright_recaptcha import recaptchav2

# Load environment variables
load_dotenv()


def lookup_zola_owner(address: str) -> str:
    """
    Look up property ownership information on NYC's ZoLa website using Playwright.

    Args:
        address (str): The property address to look up

    Returns:
        str: The owner information if found, or an error message if not found
    """
    # Get Capsolver API key from environment variable
    api_key = os.getenv("CAPSOLVER_API_KEY")
    if not api_key:
        return "Error: CAPSOLVER_API_KEY environment variable not set"

    # Get optional settings
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    timeout = int(os.getenv("TIMEOUT", "30000"))

    with sync_playwright() as p:
        # Launch the browser with headless mode from environment
        browser = p.chromium.launch(headless=headless)

        try:
            # Create a new context and page
            context = browser.new_context()
            page = context.new_page()

            # Set default timeout from environment
            page.set_default_timeout(timeout)

            # Navigate to ZoLa
            page.goto("https://zola.planning.nyc.gov")

            # Handle the welcome popup if it exists
            try:
                # Wait for the popup to be visible
                page.wait_for_selector('div.reveal[role="dialog"]')

                # Click the close button using its specific class and aria-label
                close_button = page.locator('button.close-button[aria-label="Close modal"]')
                if close_button:
                    close_button.click()

                # Wait for popup to disappear
                page.wait_for_selector('div.reveal[role="dialog"]', state="hidden")
            except Exception as popup_error:
                print(f"Note: Popup handling error (might not be present): {popup_error}")

            # Wait for and fill the search box using its specific ID
            search_box = page.locator("#map-search-input")
            search_box.fill(address)

            # Wait for autocomplete results to appear
            page.wait_for_selector("li.result.highlighted-result")
            time.sleep(1)  # Small additional wait to ensure all results are loaded

            # Click the first highlighted result
            first_result = page.locator("li.result.highlighted-result div[data-ember-action]").first
            first_result.click()

            # Wait for the lot-details section to appear
            page.wait_for_selector("section.lot-details")

            # Click Show Owner to trigger CAPTCHA
            show_owner_button = page.locator('button.a11y-orange[type="submit"]')
            show_owner_button.click()

            # Initialize the solver with context manager to handle reCAPTCHA
            try:
                with recaptchav2.SyncSolver(page, capsolver_api_key=api_key) as solver:
                    # Solve the reCAPTCHA
                    token = solver.solve_recaptcha(wait=True)
                    print(f"CAPTCHA token: {token}")
                    if not token:
                        return "Failed to solve CAPTCHA - no token received"
                    # Wait for owner information to appear after CAPTCHA is solved
                    try:
                        page.wait_for_selector(
                            "label.data-label:has-text('Owner') + span.datum:not(:empty)",
                            timeout=20000,  # Increased timeout for loading spinner
                        )
                    except Exception:
                        return "Owner information did not appear after solving CAPTCHA"
            except Exception as captcha_error:
                return f"Error solving CAPTCHA: {str(captcha_error)}"

            # Try to get owner information from the data grid
            owner_label = page.locator("label.data-label:has-text('Owner')")
            if owner_label.count() > 0:
                # Get the associated datum span (owner name)
                owner_info = (
                    owner_label.locator("xpath=following-sibling::span").inner_text().strip()
                )
                return f"Owner: {owner_info}"
            else:
                return "Owner information not found in the expected location"

        except Exception as e:
            return f"Error looking up address: {str(e)}"

        finally:
            browser.close()


# Example usage
if __name__ == "__main__":
    test_address = "798 LEXINGTON AVENUE, New York, NY"
    owner_info = lookup_zola_owner(test_address)
    print(f"Owner information for {test_address}:")
    print(owner_info)

# Note: Before first run:
# 1. Install browser binaries: playwright install chromium
# 2. Set CAPSOLVER_API_KEY in .env file
# 3. Install dependencies from requirements.txt
