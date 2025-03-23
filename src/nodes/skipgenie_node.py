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

        Searches for individual owners identified in the analyzer node.
        Returns contact information found via SkipGenie.
        """
        # Get individual owners to search for
        individual_owners = state.get("individual_owners", [])

        # If no individual owners, check if we have an owner name that's an individual
        if not individual_owners:
            owner_name = state.get("owner_name")
            owner_type = state.get("owner_type", "").lower()

            if owner_name and owner_type == "individual":
                individual_owners = [{"name": owner_name, "source": "owner_name", "type": "owner"}]

        if not individual_owners:
            logger.warning("No individual owners found, skipping SkipGenie search")
            return {
                "current_step": "SkipGenie search skipped (no individual owners)",
                "next_steps": ["search_true_people"],
                "skipgenie_phones": [],
            }

        # Log the search operation
        logger.info(f"🔍 Searching SkipGenie for {len(individual_owners)} individuals")
        print(f"🔍 Searching SkipGenie for {len(individual_owners)} individuals")

        # Check if SkipGenie credentials are set
        if not os.getenv("SKIP_EMAIL") or not os.getenv("SKIP_PASSWORD"):
            logger.warning("SkipGenie credentials not set in environment variables")
            return {
                "current_step": "SkipGenie search skipped (credentials not set)",
                "next_steps": ["search_true_people"],
                "skipgenie_phones": [],
            }

        # Initialize results storage
        contact_info = []
        skipgenie_phones = []

        # Search for each individual owner
        for owner in individual_owners:
            owner_name = owner["name"]
            logger.info(f"Searching for: {owner_name}")

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
                    for result in results:
                        # Process name and phones
                        contact_name = result.get("name", "Unknown")
                        contact = {
                            "name": contact_name,
                            "phones": [],
                            "original_search": owner_name,
                        }

                        # Get phones if available
                        if "phones" in result and result["phones"]:
                            for phone in result["phones"]:
                                phone_number = phone.get("phone", "")
                                phone_type = phone.get("description", "Unknown")

                                # Add to contact's phones
                                contact["phones"].append(
                                    {
                                        "number": phone_number,
                                        "description": phone_type,
                                    }
                                )

                                # Add to skipgenie_phones for later comparison
                                skipgenie_phones.append(
                                    {
                                        "number": phone_number,
                                        "contact_name": contact_name,
                                        "original_search": owner_name,
                                        "type": phone_type,
                                        "source": "SkipGenie",
                                        "confidence": "medium",
                                    }
                                )

                        contact_info.append(contact)
                else:
                    logger.info(f"No results found in SkipGenie for {owner_name}")

            except Exception as e:
                logger.error(f"Error searching SkipGenie for {owner_name}: {str(e)}")
                continue

        # Return results
        if contact_info:
            return {
                "current_step": f"SkipGenie search completed - found data for {len(contact_info)} individuals",
                "next_steps": ["search_true_people"],
                "skipgenie_results": contact_info,
                "skipgenie_phones": skipgenie_phones,
            }
        else:
            return {
                "current_step": "SkipGenie search completed - no results found",
                "next_steps": ["search_true_people"],
                "skipgenie_phones": [],
            }
