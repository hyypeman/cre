import logging
from ..state import PropertyResearchState
from ..scrapers import search_opencorporate

logger = logging.getLogger(__name__)


class OpenCorporatesNode:
    """Node for searching OpenCorporates for LLC ownership information."""

    def __init__(self):
        """Initialize the OpenCorporates node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Search OpenCorporates for LLC ownership information."""
        logger.info(f"🏢 Searching OpenCorporates for: {state.get('owner_name', 'Unknown LLC')}")
        print(f"🏢 Searching OpenCorporates for: {state.get('owner_name', 'Unknown LLC')}")

        # Get extracted_data BEFORE any processing
        extracted_data = state.get("extracted_data", {})

        if not state.get("owner_name"):
            logger.warning("No owner name found, skipping OpenCorporates search")
            return {
                "extracted_data": extracted_data,  # Already captured above
                "current_step": "OpenCorporates search skipped (no owner name)",
                "next_steps": ["search_skipgenie"],
            }

        try:
            company_registry_data = search_opencorporate(state["owner_name"])
            # Use the extracted_data we already retrieved
            return {
                "extracted_data": extracted_data,
                "company_registry_data": company_registry_data,
                "current_step": "OpenCorporates search completed",
                "next_steps": ["search_skipgenie"],
            }
        except Exception as e:
            error_msg = f"OpenCorporates search error: {str(e)}"
            logger.error(error_msg)
            # Use the extracted_data we already retrieved
            return {
                "extracted_data": extracted_data,  # Use the already captured data
                "errors": [error_msg],
                "current_step": "OpenCorporates search failed",
                "next_steps": ["search_skipgenie"],
            }
