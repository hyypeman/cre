import logging
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class SkipGenieNode:
    """Node for searching SkipGenie for person information (dummy implementation)."""

    def __init__(self):
        """Initialize the SkipGenie node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Search SkipGenie for person information (dummy implementation)."""
        if not state.get("owner_name"):
            logger.warning("No owner name found, skipping SkipGenie search")
            return {
                "current_step": "SkipGenie search skipped (no owner name)",
                "next_steps": ["search_true_people"],
            }

        logger.info(f"🔍 Would search SkipGenie for: {state['owner_name']}")
        print(f"🔍 Would search SkipGenie for: {state['owner_name']}")

        # This is a dummy implementation that doesn't actually search SkipGenie
        # In a real implementation, this would call a scraper function and return person_search_results
        return {
            "current_step": "SkipGenie search completed (dummy)",
            "next_steps": ["search_true_people"],
        }
