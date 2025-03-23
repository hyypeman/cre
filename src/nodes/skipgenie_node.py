import logging
import os
from ..state import PropertyResearchState
from ..scrapers.services.client import Client
from ..scrapers.skipengine_scrapper import search_skipengine

logger = logging.getLogger(__name__)


class SkipGenieNode:
    """Node for searching SkipGenie for person information."""

    def __init__(self):
        """Initialize the SkipGenie node."""
        self.client = Client()

    def run(self, state: PropertyResearchState) -> dict:
        """
        Search SkipGenie for person information.

        Requires owner_name in the state.
        Returns contact information found via SkipGenie.
        """
        # Check if we have necessary information to search
        owner_name = state.get("owner_name")

        if not owner_name:
            logger.warning("No owner name found, skipping SkipGenie search")
            return {
                "current_step": "SkipGenie search skipped (no owner name)",
                "next_steps": ["search_true_people"],
            }

        # Log the search operation
        logger.info(f"🔍 Searching SkipGenie for: {owner_name}")
        print(f"🔍 Searching SkipGenie for: {owner_name}")

        # Check if SkipGenie credentials are set
        if not os.getenv("SKIP_EMAIL") or not os.getenv("SKIP_PASSWORD"):
            logger.warning("SkipGenie credentials not set in environment variables")
            return {
                "current_step": "SkipGenie search skipped (credentials not set)",
                "next_steps": ["search_true_people"],
            }

        # Prepare search data
        try:
            # Try to parse the name into first and last components
            name_parts = owner_name.split()

            search_data = {}

            # Handle different name formats
            if len(name_parts) >= 2:
                search_data["firstName"] = name_parts[0]
                search_data["lastName"] = name_parts[-1]

                # If there are middle names, include them
                if len(name_parts) > 2:
                    search_data["middleName"] = " ".join(name_parts[1:-1])
            else:
                # If only one name component, use it as last name
                search_data["lastName"] = owner_name

            # Add address information if available
            if state.get("address"):
                address = state.get("address")
                search_data["street"] = address

                # Try to extract city, state, zip from address
                address_parts = address.split(",")
                if len(address_parts) >= 2:
                    location_parts = address_parts[-1].strip().split()

                    # Check if we have both state and zip
                    if len(location_parts) >= 2:
                        search_data["state"] = location_parts[-2]
                        search_data["zip"] = location_parts[-1]

                    # Try to get city from second to last address part
                    if len(address_parts) >= 3:
                        search_data["city"] = address_parts[-2].strip()

            # Default to NY if no state information available
            if "state" not in search_data:
                search_data["state"] = "NY"

            # Set default city if not available
            if "city" not in search_data:
                search_data["city"] = "New York"

            # Perform the actual search
            results = search_skipengine(self.client, search_data)

            # Process results if we got any
            if results and isinstance(results, list) and len(results) > 0:
                # Extract contact information from the results
                contact_info = []

                for result in results:
                    # Process name and phones
                    contact = {"name": result.get("name", "Unknown"), "phones": []}

                    # Get phones if available
                    if "phones" in result and result["phones"]:
                        for phone in result["phones"]:
                            contact["phones"].append(
                                {
                                    "number": phone.get("phone", ""),
                                    "description": phone.get("description", ""),
                                }
                            )

                    contact_info.append(contact)

                # Update state with contact information
                if contact_info:
                    # Collect all phone numbers
                    all_phones = []
                    for contact in contact_info:
                        for phone in contact["phones"]:
                            all_phones.append(
                                {
                                    "number": phone["number"],
                                    "type": phone.get("description", "Unknown"),
                                    "source": "SkipGenie",
                                }
                            )

                    # Merge with existing phone numbers if any
                    existing_phones = state.get("contact_numbers", [])
                    state["contact_numbers"] = existing_phones + all_phones

                    # Set contact name if not already set
                    if not state.get("contact_name") and contact_info[0]["name"] != "Unknown":
                        state["contact_name"] = contact_info[0]["name"]

                return {
                    "current_step": f"SkipGenie search completed - found {len(results)} results",
                    "next_steps": ["search_true_people"],
                    "skip_results": contact_info,
                }
            else:
                logger.info("No results found in SkipGenie")
                return {
                    "current_step": "SkipGenie search completed - no results found",
                    "next_steps": ["search_true_people"],
                }

        except Exception as e:
            logger.error(f"Error searching SkipGenie: {str(e)}")
            return {
                "current_step": f"SkipGenie search error: {str(e)}",
                "next_steps": ["search_true_people"],
                "errors": [f"SkipGenie search error: {str(e)}"],
            }
