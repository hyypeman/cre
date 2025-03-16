"""
Property Research Scrapers - Tools for extracting property ownership information.

This package contains scrapers for various property data sources:
- ZoLa: NYC's Zoning and Land Use Map
- ACRIS: NYC's Automated City Register Information System
- Document Processor: Tools for extracting data from property documents
- PropertyShark: Property ownership information
- OpenCorporates: Company information for LLC owners
"""

from .zola_scraper import lookup_zola_owner
from .acris_scraper import search_acris
from .document_processor import extract_text_from_pdf
from .property_shark_scraper import search_shark
from .opencorporates_scraper import search_opencorporate

__all__ = [
    "lookup_zola_owner",
    "search_acris",
    "extract_text_from_pdf",
    "search_shark",
    "search_opencorporate",
]
