"""
Property Research Scrapers - Tools for extracting property ownership information.

This package contains scrapers for various property data sources:
- ZoLa: NYC's Zoning and Land Use Map
- ACRIS: NYC's Automated City Register Information System
- Document Processor: Tools for extracting data from property documents
"""

from .zola_scraper import lookup_zola_owner
from .acris_scraper import search_acris
from .document_processor import extract_text_from_pdf

__all__ = ["lookup_zola_owner", "search_acris", "extract_text_from_pdf"]
