import logging
from ..state import PropertyResearchState
from ..scrapers import search_opencorporate

logger = logging.getLogger(__name__)


class OpenCorporatesNode:
    """Node for searching OpenCorporates for company information."""

    def __init__(self):
        """Initialize the OpenCorporates node."""
        pass

    def run(self, state: PropertyResearchState) -> PropertyResearchState:
        """Search OpenCorporates for company information."""
        if not state.get("owner_name"):
            logger.warning("No owner name found, skipping OpenCorporates search")
            return {
                **state,
                "current_step": "OpenCorporates search skipped (no owner name)",
                "next_steps": ["analyze_owner"],
            }

        logger.info(f"🏢 Searching OpenCorporates for: {state['owner_name']}")
        print(f"🏢 Searching OpenCorporates for: {state['owner_name']}")

        try:
            open_corporates_results = search_opencorporate(state["owner_name"])

            return {
                **state,
                "open_corporates_results": open_corporates_results,
                "current_step": "OpenCorporates search completed",
                "next_steps": ["analyze_owner"],
            }
        except Exception as e:
            error_msg = f"OpenCorporates search error: {str(e)}"
            logger.error(error_msg)

            return {
                **state,
                "errors": state["errors"] + [error_msg],
                "current_step": "OpenCorporates search failed",
                "next_steps": ["analyze_owner"],
            }
