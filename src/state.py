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
    # zola just returns the "owner" field
    # it can often be a company, but it can also be an individual
    zola_results: Optional[str]

    # ACRIS data
    # property info, what files we downloaded, and which one is mortgage and which one is deed
    acris_results: Optional[Dict[str, Any]]

    # Property Ownership Record after reading the mortgage and deed:
    #  - property_address: The full address of the property.
    #  - entity_owner: The business entity that legally owns the property.
    #  - individual_owners: A list of individuals associated with the ownership.
    #  - name: The individual's full name.
    #  - title: Their role within the owning entity.
    #  - ownership_evidence: A brief description of the legal document proving ownership.
    documents: Optional[List[Dict[str, Any]]]

    # Property Shark Data:
    # - real_owners: Key individuals linked to the property.
    #   - name: Full name and role.
    #   - real_owner: Affiliated entity.
    #   - address: Listed address.
    #   - phones: Associated phone numbers.
    #
    # - registered_owners: Official property owners.
    #   - data: Includes entity name, address, source, and last recorded update.
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
