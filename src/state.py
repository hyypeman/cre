from typing import Dict, List, Any, Optional, TypedDict, Union, Annotated
from typing_extensions import Required
import operator


class InputState(TypedDict, total=False):
    """
    Input state for property research containing the address to research.

    Attributes:
        address: Required property address to research
    """

    address: Required[str]


class PropertyResearchState(InputState):
    """
    Complete state for property research containing all data collected during research.

    This state tracks information from multiple data sources and the overall research process.
    """

    # Use Annotated with a reducer to handle concurrent updates
    # The lambda function returns the first non-None value
    address: Annotated[str, lambda x, y: x or y]
    """Property address being researched"""

    # ZoLa data - basic property ownership information
    # Use Annotated with a reducer to handle concurrent updates
    zola_owner_name: Annotated[Optional[str], lambda x, y: x or y]
    """Owner name from NYC's Zoning & Land Use database (can be individual or company)"""

    # ACRIS data - property documents and information
    acris_property_records: Optional[Dict[str, Any]]
    """
    Property records from NYC's ACRIS system, including:
    - property_info: Basic property information
    - files: Downloaded document files (deeds, mortgages)
    - document_types: Classification of documents (which is deed, which is mortgage)
    """

    # Processed document data - extracted from property documents
    property_ownership_records: Optional[List[Dict[str, Any]]]
    """
    Structured ownership information extracted from property documents:
    - property_address: The full address of the property
    - entity_owner: The business entity that legally owns the property
    - individual_owners: List of individuals associated with ownership
      - name: Individual's full name
      - title: Their role within the owning entity
    - ownership_evidence: Description of legal document proving ownership
    """

    # PropertyShark data - detailed ownership information
    property_shark_ownership_data: Optional[Dict[str, Any]]
    """
    Detailed ownership information from PropertyShark:
    - real_owners: Key individuals linked to the property
      - name: Full name and role
      - real_owner: Affiliated entity
      - address: Listed address
      - phones: Associated phone numbers
    - registered_owners: Official property owners
      - data: Entity name, address, source, and last recorded update
    """

    # OpenCorporates data - company information for LLC owners
    company_registry_data: Optional[Dict[str, Any]]
    """
    Company information from OpenCorporates for LLC owners:
    - company_details: Basic company information
    - officers: Company officers and directors
    - addresses: Registered addresses
    - incorporation_date: When the company was formed
    """

    # Person search results - information about individual owners
    person_search_results: Optional[Dict[str, Any]]
    """
    Information about individual owners from people search services:
    - contact_info: Phone numbers, email addresses
    - addresses: Current and previous addresses
    - relatives: Family members
    - associates: Business associates
    """
    
    # Phone verification results
    phone_analysis: Optional[Dict[str, List[Any]]]
    """
    Results of phone number validation:
    - valid_phones: List of dictionaries containing validated phone information:
      - number: The original phone number
      - formatted: The formatted version (national format)
      - country_code: The country code for the phone number
    - invalid_phones: List of phone numbers that failed validation
    """

    # Extracted owner information - consolidated from all sources
    owner_name: Optional[str]
    """Primary owner name (individual or company) extracted from all sources"""

    owner_type: Optional[str]
    """Type of owner (individual, llc, corporation, trust, etc.)"""

    # Contact information
    contact_number: Optional[str]
    """Primary contact phone number for the owner, extracted from PropertyShark or people search services"""

    # Process tracking - use Annotated with reducers to handle concurrent updates
    current_step: Annotated[str, lambda x, y: y]  # Take the latest step
    """Current step in the research process"""

    next_steps: Annotated[List[str], operator.add]  # Combine lists
    """List of steps to execute next"""

    errors: Annotated[List[str], operator.add]  # Combine error lists
    """List of errors encountered during research"""
