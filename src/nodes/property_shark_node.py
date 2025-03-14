import logging
from ..state import PropertyResearchState
from ..scrapers import search_shark

logger = logging.getLogger(__name__)


class PropertySharkNode:
    """Node for searching PropertyShark for property ownership information."""

    def __init__(self):
        """Initialize the PropertyShark node."""
        pass

    def run(self, state: PropertyResearchState) -> PropertyResearchState:
        """Search PropertyShark for property ownership information."""
        logger.info(f"🦈 Searching PropertyShark for: {state['address']}")
        print(f"🦈 Searching PropertyShark for: {state['address']}")

        try:
            property_shark_results = search_shark(state["address"])

            return {
                **state,
                "property_shark_results": property_shark_results,
                "current_step": "PropertyShark search completed",
                "next_steps": ["search_opencorporates"]
                if state.get("owner_name")
                else ["analyze_owner"],
            }
        except Exception as e:
            error_msg = f"PropertyShark search error: {str(e)}"
            logger.error(error_msg)

            return {
                **state,
                "errors": state["errors"] + [error_msg],
                "current_step": "PropertyShark search failed",
                "next_steps": ["search_opencorporates"]
                if state.get("owner_name")
                else ["analyze_owner"],
            }
