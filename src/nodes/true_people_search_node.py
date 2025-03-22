import logging
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class TruePeopleSearchNode:
    """Node for searching TruePeopleSearch for person information (dummy implementation)."""

    def __init__(self):
        """Initialize the TruePeopleSearch node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Search TruePeopleSearch for person information (dummy implementation)."""
        # Get extracted_data BEFORE any processing
        extracted_data = state.get("extracted_data", {})
        
        if not state.get("owner_name"):
            logger.warning("No owner name found, skipping TruePeopleSearch search")
            return {
                "extracted_data": extracted_data,
                "current_step": "TruePeopleSearch search skipped (no owner name)",
                "next_steps": [],
            }

        logger.info(f"🔍 Would search TruePeopleSearch for: {state['owner_name']}")
        print(f"🔍 Would search TruePeopleSearch for: {state['owner_name']}")

        # This is a dummy implementation that doesn't actually search TruePeopleSearch
        # In a real implementation, this would call a scraper function and return person_search_results
        return {
            "extracted_data": extracted_data,
            "current_step": "TruePeopleSearch search completed (dummy)",
            "next_steps": [],
        }
