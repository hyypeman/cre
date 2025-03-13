import logging
from typing import Dict, Any, List
from ..state import PropertyResearchState
from ..scrapers import extract_text_from_pdf

logger = logging.getLogger(__name__)


class DocumentProcessorNode:
    """Node for processing property documents extracted from ACRIS."""

    def __init__(self):
        """Initialize the document processor node."""
        pass

    def run(self, state: PropertyResearchState) -> PropertyResearchState:
        """Process any PDF documents found in ACRIS."""
        logger.info("📑 Processing property documents")
        print("📑 Processing property documents")

        if not state.get("acris_results"):
            logger.info("No ACRIS results found, skipping document processing")
            return {
                **state,
                "current_step": "Document processing skipped (no ACRIS results)",
                "next_steps": ["analyze_owner"],
            }

        try:
            # Extract text from PDFs found in ACRIS
            documents = self._process_documents(state["acris_results"])

            return {
                **state,
                "documents": documents,
                "current_step": "Document processing completed",
                "next_steps": ["analyze_owner"],
            }
        except Exception as e:
            error_msg = f"Document processing error: {str(e)}"
            logger.error(error_msg)

            return {
                **state,
                "errors": state["errors"] + [error_msg],
                "current_step": "Document processing failed",
                "next_steps": ["analyze_owner"],
            }

    def _process_documents(self, acris_results) -> List[Dict[str, Any]]:
        """Process documents from ACRIS results."""
        documents: List[Dict[str, Any]] = []

        if isinstance(acris_results, dict) and "files" in acris_results:
            logger.info(f"Processing {len(acris_results['files'])} documents from ACRIS")
            documents = extract_text_from_pdf(acris_results)
            logger.info(f"Successfully processed {len(documents)} documents")
        else:
            logger.warning("No files found in ACRIS results to process")
            print("No files found in ACRIS results to process")

        return documents
