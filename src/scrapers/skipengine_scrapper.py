import os
import traceback

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from services.client import Client

# Load environment variables
load_dotenv()


def parser_form(html: str) -> dict:
    """
    Parse an HTML form to extract its action endpoint and input fields.

    Args:
        html (str): HTML content as a string.

    Returns:
        dict: A dictionary with keys:
            - "endpoint": The form's action URL (str or None).
            - "data": A dict containing form input names as keys and their values.
                  Returns an empty dictionary if no form is found.
    """
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form:
        endpoint = form.get("action")
        inputs = form.find_all("input")
        data = {}

        # Extract the "name" and "value" for each input element.
        for input_field in inputs:
            input_name = input_field.get("name")
            if input_name:
                data[input_name] = input_field.get("value")

        return {"endpoint": endpoint, "data": data}

    return {}


def parser_html(html: str) -> list:
    """
    Parse HTML content to extract property owner details and phone numbers.

    The function searches for a div with id 'page-wrapper' and extracts panels
    that hold owner names and phone numbers. It assumes the owner's name is found
    in a panel heading and that phone numbers with their descriptions are in paired span elements.

    Args:
        html (str): HTML content as a string.

    Returns:
        list: A list of dictionaries, each containing:
            - "name": Owner's name (str).
            - "phones": A list of dictionaries with keys "phone" and "description".
              Returns an empty list if no relevant content is found.
    """
    soup = BeautifulSoup(html, "html.parser")
    panel_div = soup.find("div", {"id": "page-wrapper"})
    results = []

    if panel_div:
        panels = panel_div.find_all("div", {"class": "panel panel-success"})
        for panel in panels:
            heading = panel.find("div", {"class": "panel-heading"})
            if heading and heading.text:
                try:
                    # Expecting format "Label: Name", split to get the name.
                    name = heading.text.strip().split(": ", 1)[1]
                except IndexError:
                    name = heading.text.strip()
            else:
                name = "Unknown"

            phones = []
            phone_div = panel.find("div", {"id": "phoneSearch"})
            if phone_div:
                # Find all span elements that should contain phone data.
                spans = phone_div.find_all("span")
                # Process spans in pairs: first element is the phone number, second is the description.
                for i in range(0, len(spans) - 1, 2):
                    phone_text = spans[i].get_text(strip=True)
                    desc_text = spans[i + 1].get_text(strip=True)
                    phones.append({
                        "phone": phone_text,
                        "description": desc_text
                    })

            results.append({
                "name": name.strip(),
                "phones": phones
            })

    return results


def login(client: Client) -> bool:
    """
    Log into the SKIPENGINE system using the provided client.

    This function:
        - Fetches the login page.
        - Parses the login form.
        - Inserts user credentials from environment variables.
        - Submits the form.
        - Checks for a successful login based on the response content.

    Args:
        client (Client): An instance of Client used for HTTP requests.

    Returns:
        bool: True if the login was successful, False otherwise.
    """
    login_url = "https://app.skipgenie.com/Account/Login"

    try:
        # Fetch the login page.
        response = client.get(login_url)
        if not response or response.status_code != 200:
            print("First call failed")
            return False

        # Parse the login form to retrieve default form data.
        form = parser_form(response.content)
        # Update form data with credentials from environment variables.
        form["data"]["Email"] = os.getenv("SKIP_EMAIL", "")
        form["data"]["Password"] = os.getenv("SKIP_PASSWORD", "")

        # Submit the login form.
        response = client.post(login_url, data=form["data"])
        if not response or response.status_code != 200:
            print("Login call failed")
            return False

        # Verify login by checking for "My Account" in the response.
        if "My Account" in response.text:
            print("Login success")
            return True

    except Exception:
        error_details = traceback.format_exc()
        print("Error in login:", error_details)

    return False


def search(client: Client, data: dict) -> list:
    """
    Perform a property search on the SKIPENGINE system.

    This function:
        - Fetches the search page.
        - Parses the search form.
        - Merges the default form data with user-provided search parameters.
        - Submits the search form.
        - Parses the resulting HTML for property details.

    Args:
        client (Client): An instance of Client used for HTTP requests.
        data (dict): Dictionary containing search parameters (e.g., property address details).

    Returns:
        list: A list of search results where each result is a dictionary containing owner details.
              Returns an empty list if the search fails or no results are found.
    """
    search_url = "https://app.skipgenie.com/Search/Search"

    try:
        # Retrieve the search page.
        response = client.get(search_url)
        if not response or response.status_code != 200:
            print("First call search failed")
            return []

        # Parse the search form to get necessary hidden fields.
        form = parser_form(response.content)
        # Merge the default form data with provided search parameters.
        payload = {**form.get("data", {}), **data}
        # Submit the search form.
        response = client.post(search_url, data=payload)
        if not response or response.status_code != 200:
            print("Search call failed")
            return []

        print("Search success")

        # Check for a message indicating no search results.
        if "No results. Please refine your search." in response.text:
            print("No results. Please refine your search.")
            return []

        print("Trying to find details in HTML")
        results = parser_html(response.content)
        if results:
            return results

    except Exception:
        error_details = traceback.format_exc()
        print("Error in search:", error_details)

    return []


def search_skipengine(client: Client, form: dict) -> list:
    """
    Search for property owner information using the SKIPENGINE system.

    This function coordinates the overall process:
        - Launches a Playwright browser session.
        - Logs into the system.
        - Executes a property search based on provided address details.
        - Parses and returns the property owner information.

    Args:
        client (Client): An instance of Client used for HTTP requests.
        form (dict): Dictionary containing property address details for the search.

    Returns:
        list: A list of dictionaries with property owner data, or an empty list if any step fails.
    """

    try:
        # Attempt to log into the system.
        if not login(client):
            print("Something went wrong in the login process")
            return []

        # Perform the property search.
        property_owners_data = search(client, form)
        if not property_owners_data:
            print("Something went wrong in the search process")
            return []

        # Return the retrieved property owner information.
        return property_owners_data

    except Exception as e:
        print(f"Error searching SKIPENGINE: {str(e)}")
        error_details = traceback.format_exc()
        print("Error in main search method:", error_details)
        return []


# Example usage
if __name__ == "__main__":
    data = {
        "lastName": "Chrzan",
        "firstName": "Nicole",
        "middleName": "",
        "street": "112 Long Drive Ct Dix Hills",
        "city": "New york",
        "zip": "11746",
        "state": "NY",
    }
    owner_info = search_skipengine(Client(), data)
    print(f"Owner information for -> {data}")
    print(owner_info)
