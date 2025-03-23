import logging
from ..state import PropertyResearchState
from ..scrapers.truepeoplesearch_scraper import search_truepeoplesearch

logger = logging.getLogger(__name__)


class TruePeopleSearchNode:
    """Node for searching TruePeopleSearch for person information."""

    def __init__(self):
        """Initialize the TruePeopleSearch node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """
        Search TruePeopleSearch for person information.

        Searches for individual owners identified in the analyzer node.
        Returns contact information found via TruePeopleSearch.
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
            logger.warning("No individual owners found, skipping TruePeopleSearch search")
            return {
                "current_step": "TruePeopleSearch search skipped (no individual owners)",
                "next_steps": ["refine_phone_numbers"],
                "truepeoplesearch_phones": [],
            }

        # Log the search operation
        logger.info(f"🔍 Searching TruePeopleSearch for {len(individual_owners)} individuals")
        print(f"🔍 Searching TruePeopleSearch for {len(individual_owners)} individuals")

        # Initialize results storage
        contact_info = []
        truepeoplesearch_phones = []
        errors = []

        # Search for each individual owner
        for owner in individual_owners:
            owner_name = owner["name"]
            logger.info(f"Searching for: {owner_name}")

            try:
                # Perform the actual search - only by name, never by address
                results = search_truepeoplesearch(contact_name=owner_name, contact_address=None)

                # Check if we got an error
                if isinstance(results, dict) and "error" in results:
                    error_msg = f"TruePeopleSearch error for {owner_name}: {results['error']}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue

                # Process results if we got any
                if results and isinstance(results, list) and len(results) > 0:
                    # Extract contact information from the first result
                    first_result = results[0]
                    contact_name = first_result.get("name", owner_name)

                    owner_contact = {
                        "name": contact_name,
                        "original_search": owner_name,
                        "phones": [],
                        "emails": first_result.get("emails", []),
                    }

                    # Get phone numbers in a consistent format for comparison
                    if "phone_numbers" in first_result:
                        for phone_type, phones in first_result["phone_numbers"].items():
                            for phone in phones:
                                phone_number = phone["number"]

                                # Add to owner's contact info
                                owner_contact["phones"].append(
                                    {
                                        "number": phone_number,
                                        "type": phone["type"],
                                        "provider": phone.get("provider", "Unknown"),
                                    }
                                )

                                # Add to truepeoplesearch_phones for later comparison
                                truepeoplesearch_phones.append(
                                    {
                                        "number": phone_number,
                                        "contact_name": contact_name,
                                        "original_search": owner_name,
                                        "type": phone["type"],
                                        "provider": phone.get("provider", "Unknown"),
                                        "source": "TruePeopleSearch",
                                        "confidence": "medium",
                                    }
                                )

                    contact_info.append(owner_contact)
                else:
                    logger.info(f"No results found in TruePeopleSearch for {owner_name}")
            except Exception as e:
                error_msg = f"Error searching TruePeopleSearch for {owner_name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

        # Return results
        return {
            "current_step": f"TruePeopleSearch search completed - found data for {len(contact_info)} individuals",
            "next_steps": ["refine_phone_numbers"],
            "truepeoplesearch_results": contact_info,
            "truepeoplesearch_phones": truepeoplesearch_phones,
            "errors": errors if errors else None,
        }
