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

        Requires owner_name in the state.
        Returns contact information found via TruePeopleSearch.
        """
        # Check if we have the owner name for search
        owner_name = state.get("owner_name")

        if not owner_name:
            logger.warning("No owner name found, skipping TruePeopleSearch search")
            return {
                "current_step": "TruePeopleSearch search skipped (no owner name)",
                "next_steps": [],
            }

        # Log the search operation
        logger.info(f"🔍 Searching TruePeopleSearch for name: {owner_name}")
        print(f"🔍 Searching TruePeopleSearch for name: {owner_name}")

        # Perform the actual search - only by name, never by address
        try:
            results = search_truepeoplesearch(contact_name=owner_name, contact_address=None)

            # Check if we got an error
            if isinstance(results, dict) and "error" in results:
                logger.warning(f"TruePeopleSearch error: {results['error']}")
                return {
                    "current_step": f"TruePeopleSearch search error: {results['error']}",
                    "next_steps": [],
                }

            # Process results if we got any
            if results and isinstance(results, list) and len(results) > 0:
                # Extract contact information from the first result
                first_result = results[0]

                # Get phone numbers
                phone_numbers = []
                if "phone_numbers" in first_result:
                    for phone_type, phones in first_result["phone_numbers"].items():
                        for phone in phones:
                            phone_numbers.append(
                                {
                                    "number": phone["number"],
                                    "type": phone["type"],
                                    "provider": phone.get("provider", "Unknown"),
                                }
                            )

                # Get emails
                emails = first_result.get("emails", [])

                # Update state with contact information
                state["contact_name"] = first_result.get("name", owner_name)
                state["contact_numbers"] = phone_numbers
                state["contact_emails"] = emails

                if "current_address" in first_result:
                    state["contact_address"] = first_result["current_address"].get("full", "")

                return {
                    "current_step": f"TruePeopleSearch search completed - found {len(results)} results",
                    "next_steps": [],
                    "contact_info": {
                        "name": first_result.get("name", ""),
                        "phones": phone_numbers,
                        "emails": emails,
                    },
                }
            else:
                logger.info("No results found in TruePeopleSearch")
                return {
                    "current_step": "TruePeopleSearch search completed - no results found",
                    "next_steps": [],
                }

        except Exception as e:
            logger.error(f"Error searching TruePeopleSearch: {str(e)}")
            return {
                "current_step": f"TruePeopleSearch search error: {str(e)}",
                "next_steps": [],
                "errors": [f"TruePeopleSearch search error: {str(e)}"],
            }
