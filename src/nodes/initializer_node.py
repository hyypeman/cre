import logging
import os
import glob
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class InitializerNode:
    """Node for initializing the property research workflow."""

    def __init__(self):
        """Initialize the initializer node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Initialize the property research workflow."""
        logger.info(f"🔍 Starting property research for: {state['address']}")
        print(f"🔍 Starting property research for: {state['address']}")

        # Clean up documents folder
        self._cleanup_documents_folder()

        return {
            "current_step": "Initialization completed",
            "next_steps": ["zola_search", "acris_search", "property_shark_search"],
        }

    def _cleanup_documents_folder(self):
        """Clean up the documents folder by deleting all files."""
        documents_dir = os.path.join(os.getcwd(), "documents")

        # Create the documents directory if it doesn't exist
        if not os.path.exists(documents_dir):
            os.makedirs(documents_dir)
            logger.info(f"Created documents directory: {documents_dir}")
            return

        # Delete all files in the documents directory
        file_count = 0
        for file_path in glob.glob(os.path.join(documents_dir, "*")):
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    file_count += 1
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {e}")

        if file_count > 0:
            logger.info(f"🧹 Cleaned up documents folder, deleted {file_count} files")
            print(f"🧹 Cleaned up documents folder, deleted {file_count} files")
