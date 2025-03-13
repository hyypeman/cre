from typing import Dict, List, Any, Optional, TypedDict
from typing_extensions import Required


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

    Data fields:
    - ZoLa data: Owner information from ZoLa
    - ACRIS data: Property information and documents from ACRIS
    - Document data: Extracted information from property documents
    - Property Shark data: Additional property information (not implemented)
    - Open Corporates data: Company information for LLC owners (not implemented)
    - Person search data: Information about individual owners (not implemented)

    Owner information:
    - owner_name: Extracted owner name (individual or company)
    - owner_type: Type of owner (individual, llc, corporation, etc.)

    Process tracking:
    - current_step: Current step in the research process
    - next_steps: List of steps to execute next
    - errors: List of errors encountered during research
    """

    # ZoLa data
    zola_results: Optional[str]

    # ACRIS data
    acris_results: Optional[Dict[str, Any]]

    # Document processing data
    documents: Optional[List[Dict[str, Any]]]

    # Property Shark data
    property_shark_results: Optional[Dict[str, Any]]

    # Open Corporates data
    open_corporates_results: Optional[Dict[str, Any]]

    # Person search results
    person_search_results: Optional[Dict[str, Any]]

    # Extracted owner information
    owner_name: Optional[str]
    owner_type: Optional[str]

    # Process tracking
    current_step: str
    next_steps: List[str]
    errors: List[str]
