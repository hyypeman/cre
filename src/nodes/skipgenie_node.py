import logging
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class SkipGenieNode:
    """Node for searching SkipGenie for owner contact information."""

    def __init__(self):
        """Initialize the SkipGenie node."""
        pass

    def run(self, state: PropertyResearchState) -> PropertyResearchState:
        """Search SkipGenie for owner contact information (dummy implementation)."""
        if not state.get("owner_name"):
            logger.warning("No owner name found, skipping SkipGenie search")
            return {
                **state,
                "current_step": "SkipGenie search skipped (no owner name)",
                "next_steps": ["search_true_people"],
            }

        logger.info(f"🔍 Would search SkipGenie for: {state['owner_name']}")
        print(f"🔍 Would search SkipGenie for: {state['owner_name']}")

        # This is a dummy implementation that doesn't actually search SkipGenie
        # In a real implementation, this would call a scraper function

        return {
            **state,
            "current_step": "SkipGenie search completed (dummy)",
            "next_steps": ["search_true_people"],
        }
