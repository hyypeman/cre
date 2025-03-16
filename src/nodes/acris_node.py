import logging
from ..state import PropertyResearchState
from ..scrapers import search_acris

logger = logging.getLogger(__name__)


class AcrisNode:
    """Node for searching ACRIS for property documents and ownership information."""

    def __init__(self):
        """Initialize the ACRIS node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Search ACRIS for property documents and ownership information."""
        logger.info(f"📄 Searching ACRIS for: {state['address']}")
        print(f"📄 Searching ACRIS for: {state['address']}")

        try:
            acris_property_records = search_acris(state["address"])

            return {
                "acris_property_records": acris_property_records,
                "current_step": "ACRIS search completed",
                "next_steps": ["process_documents"],
            }
        except Exception as e:
            error_msg = f"ACRIS search error: {str(e)}"
            logger.error(error_msg)

            return {
                "errors": [error_msg],  # Just return the new error, reducer will combine
                "current_step": "ACRIS search failed",
                "next_steps": ["analyze_owner"],  # Skip document processing if ACRIS fails
            }
