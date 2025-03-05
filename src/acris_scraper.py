from playwright.sync_api import sync_playwright
import time
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


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
        if part.isdigit() and not street_number:
            street_number = part
        elif part not in ["NEW", "YORK", "NY", "MANHATTAN"]:
            street_name.append(part)

    street_name = " ".join(street_name)

    if not street_number or not street_name:
        return "Could not parse address components for ACRIS search"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        try:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(timeout)

            # Navigate to ACRIS search page
            page.goto("https://a836-acris.nyc.gov/DS/DocumentSearch/BBLSearch")

            # Select Manhattan (Borough 1) by default
            page.select_option('select[name="borough"]', "1")

            # Enter address information
            page.fill('input[name="houseNumber"]', street_number)
            page.fill('input[name="streetName"]', street_name)

            # Click search button
            page.click('input[type="submit"][value="Search"]')

            # Wait for results
            page.wait_for_selector("table.display")

            # Check if we have results
            no_results = page.locator('text="No Records Found"').count()
            if no_results > 0:
                return f"No records found in ACRIS for {address}"

            # Extract BBL (Borough-Block-Lot) information
            bbl_info = page.locator("table.display tr").all()

            if len(bbl_info) <= 1:  # Just header row
                return f"No property details found in ACRIS for {address}"

            # Get the BBL from the first result
            bbl_row = bbl_info[1]  # Skip header row
            bbl_text = bbl_row.inner_text()

            # Extract Borough, Block, and Lot
            bbl_parts = re.findall(r"\d+", bbl_text)
            if len(bbl_parts) < 3:
                return f"Could not extract BBL information from ACRIS for {address}"

            borough, block, lot = bbl_parts[:3]

            # Click on the first result to view property details
            bbl_row.locator("a").first.click()

            # Wait for document list page
            page.wait_for_selector("table.display")

            # Extract document information
            documents = []
            doc_rows = page.locator("table.display tr").all()

            # Skip header row
            for i in range(1, min(6, len(doc_rows))):  # Get up to 5 documents
                doc_text = doc_rows[i].inner_text()
                documents.append(doc_text.replace("\t", " ").replace("\n", " - "))

            # Construct result
            result = f"""
            Property Information from ACRIS:
            Address: {address}
            Borough: {borough}
            Block: {block}
            Lot: {lot}
            
            Recent Documents:
            """

            for doc in documents:
                result += f"- {doc}\n"

            # Try to extract owner information from the most recent deed
            owner_info = "Owner information not found in documents"

            # Look for deed documents
            deed_links = page.locator('table.display tr:has-text("DEED")').all()
            if deed_links:
                # Click on the first deed to view details
                deed_links[0].locator("a").first.click()

                # Wait for document details
                page.wait_for_selector("table.display")

                # Look for party information
                party_rows = page.locator('table.display:has-text("Party") tr').all()

                for row in party_rows:
                    row_text = row.inner_text()
                    if "PARTY1" in row_text or "GRANTOR" in row_text:
                        owner_info = row_text.replace("\t", " ").replace("\n", " - ")
                        break

            result += f"\nOwnership Information:\n{owner_info}"

            return result

        except Exception as e:
            return f"Error searching ACRIS: {str(e)}"

        finally:
            browser.close()


# Example usage
if __name__ == "__main__":
    test_address = "798 LEXINGTON AVENUE, New York, NY"
    acris_results = search_acris(test_address)
    print(f"ACRIS results for {test_address}:")
    print(acris_results)
