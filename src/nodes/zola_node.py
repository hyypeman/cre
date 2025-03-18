import logging
from ..state import PropertyResearchState
from ..scrapers import lookup_zola_owner

logger = logging.getLogger(__name__)


class ZolaNode:
    """Node for searching ZoLa for property ownership information."""

    def __init__(self):
        """Initialize the ZoLa node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Search ZoLa for property information."""
        logger.info(f"🏢 Searching ZoLa for: {state['address']}")
        print(f"🏢 Searching ZoLa for: {state['address']}")

        try:
            zola_owner = lookup_zola_owner(state["address"])

            return {
                "zola_owner_name": zola_owner,
                "current_step": "ZoLa search completed",
                "next_steps": ["acris_search"],
            }
        except Exception as e:
            error_msg = f"ZoLa search error: {str(e)}"
            logger.error(error_msg)

            return {
                "errors": [error_msg],  # Just return the new error, reducer will combine
                "current_step": "ZoLa search failed",
                "next_steps": ["acris_search"],  # Continue to next step even if this fails
            }
