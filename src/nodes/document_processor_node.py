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

    def run(self, state: PropertyResearchState) -> dict:
        """Process any PDF documents found in ACRIS."""
        logger.info("📑 Processing property documents")
        print("📑 Processing property documents")

        if not state.get("acris_property_records"):
            logger.info("No ACRIS records found, skipping document processing")
            return {
                "current_step": "Document processing skipped (no ACRIS records)",
                "next_steps": ["analyze_owner"],
            }

        try:
            # Extract text from PDFs found in ACRIS
            ownership_records = self._process_documents(state["acris_property_records"])

            return {
                "property_ownership_records": ownership_records,
                "current_step": "Document processing completed",
                "next_steps": ["analyze_owner"],
            }
        except Exception as e:
            error_msg = f"Document processing error: {str(e)}"
            logger.error(error_msg)

            return {
                "errors": [error_msg],
                "current_step": "Document processing failed",
                "next_steps": ["analyze_owner"],
            }

    def _process_documents(self, acris_records) -> List[Dict[str, Any]]:
        """Process documents from ACRIS records."""
        ownership_records: List[Dict[str, Any]] = []

        if isinstance(acris_records, dict) and "files" in acris_records:
            logger.info(f"Processing {len(acris_records['files'])} documents from ACRIS")
            ownership_records = extract_text_from_pdf(acris_records)
            logger.info(f"Successfully processed {len(ownership_records)} documents")
        else:
            logger.warning("No files found in ACRIS records to process")
            print("No files found in ACRIS records to process")

        return ownership_records
