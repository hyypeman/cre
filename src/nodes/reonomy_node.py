import logging
from ..state import PropertyResearchState
from ..scrapers import reonomy_scrapper

logger = logging.getLogger(__name__)


class ReonomyNode:
    """Node for searching Reonomy for property ownership information."""

    def __init__(self):
        """Initialize the Reonomy node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Search Reonomy for property information."""
        logger.info(f"🏢 Searching Reonomy for: {state['address']}")
        print(f"🏢 Searching Reonomy for: {state['address']}")

        try:
            # Call the search_reonomy function with the address
            reonomy_data = reonomy_scrapper(state["address"])

            return {
                "reonomy_address_data": reonomy_data,
                "current_step": "Reonomy search completed",
                "next_steps": ["acris_search"],
            }
        except Exception as e:
            error_msg = f"Reonomy search error: {str(e)}"
            logger.error(error_msg)

            return {
                "errors": [error_msg],  # Just return the new error, reducer will combine
                "current_step": "Reonomy search failed",
                "next_steps": ["acris_search"],  # Continue to next step even if this fails
            }
