import logging
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class InitializerNode:
    """Node for initializing the property research process."""

    def __init__(self):
        """Initialize the initializer node."""
        pass

    def run(self, state: PropertyResearchState) -> PropertyResearchState:
        """Initialize the research process with the given address."""
        logger.info(f"🔍 Starting property research for: {state['address']}")
        print(f"🔍 Starting property research for: {state['address']}")

        return {
            **state,
            "current_step": "Initializing research",
            "next_steps": ["zola_search"],
            "errors": [],
        }
