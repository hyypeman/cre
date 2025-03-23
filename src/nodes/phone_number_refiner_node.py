import logging
import re
import json
from typing import Dict, Any, List, Set, Optional
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class PhoneNumberAnalysisResponse(BaseModel):
    """Schema for phone number analysis response."""

    refined_phone_numbers: List[Dict[str, Any]] = Field(
        description="List of refined phone numbers with confidence levels, sources, and contact information"
    )

    primary_phone: str = Field(description="The primary phone number with highest confidence")

    phone_data_by_contact: Dict[str, List[Dict[str, Any]]] = Field(
        description="Dictionary of phone numbers organized by contact name"
    )

    notes: str = Field(description="Notes about the phone number analysis process and results")


class PhoneNumberRefinerNode:
    """Node for refining phone numbers by comparing data from multiple sources using LLM."""

    def __init__(self, model_name="gpt-4o", temperature=0):
        """Initialize the phone number refiner node."""
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

    def run(self, state: PropertyResearchState) -> dict:
        """
        Refine phone numbers by comparing data from multiple sources using LLM.

        This node takes phone numbers from PropertyShark, SkipGenie, and TruePeopleSearch
        and uses an LLM to compare them and determine the most reliable numbers.
        """
        logger.info("📞 Refining phone numbers from multiple sources")
        print("📞 Refining phone numbers from multiple sources")

        try:
            # Get all phone-related data from state
            property_shark_phones = state.get("property_shark_phones", [])
            skipgenie_phones = state.get("skipgenie_phones", [])
            truepeoplesearch_phones = state.get("truepeoplesearch_phones", [])
            individual_owners = state.get("individual_owners", [])

            # If we don't have any phone numbers, return early
            total_numbers = (
                len(property_shark_phones) + len(skipgenie_phones) + len(truepeoplesearch_phones)
            )
            if total_numbers == 0:
                logger.info("No phone numbers found, skipping refinement")
                return {
                    "refined_phone_data": {},
                    "refined_phone_numbers": [],
                    "contact_number": None,
                    "current_step": "Phone number refinement skipped (no numbers found)",
                    "next_steps": ["finalize"],
                }

            # Use LLM to analyze and refine phone numbers
            analysis_result = self._analyze_phone_numbers(
                state,
                property_shark_phones,
                skipgenie_phones,
                truepeoplesearch_phones,
                individual_owners,
            )

            # Return the analyzed results
            return {
                "refined_phone_data": analysis_result.get("phone_data_by_contact", {}),
                "refined_phone_numbers": analysis_result.get("refined_phone_numbers", []),
                "contact_number": analysis_result.get("primary_phone", ""),
                "refinement_notes": analysis_result.get("notes", ""),
                "current_step": "Phone number refinement completed",
                "next_steps": ["finalize"],
            }

        except Exception as e:
            logger.error(f"Phone number refinement error: {str(e)}")
            logger.exception("Detailed error:")

            # Return error state
            return {
                "refined_phone_data": {},
                "refined_phone_numbers": [],
                "contact_number": None,
                "current_step": f"Phone number refinement error: {str(e)}",
                "next_steps": ["finalize"],
                "errors": [f"Phone number refinement error: {str(e)}"],
            }

    def _analyze_phone_numbers(
        self,
        state: PropertyResearchState,
        property_shark_phones: List[Dict[str, Any]],
        skipgenie_phones: List[Dict[str, Any]],
        truepeoplesearch_phones: List[Dict[str, Any]],
        individual_owners: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze and refine phone numbers from multiple sources."""
        # Normalize all phone numbers for comparison
        normalized_numbers = self._normalize_phone_data(
            property_shark_phones, skipgenie_phones, truepeoplesearch_phones
        )

        # If we have very few phone numbers, use simple analysis
        if len(normalized_numbers) <= 3:
            return self._simple_phone_analysis(normalized_numbers, individual_owners)

        # For more complex cases, use LLM analysis
        return self._llm_phone_analysis(
            state,
            property_shark_phones,
            skipgenie_phones,
            truepeoplesearch_phones,
            individual_owners,
        )

    def _normalize_phone_data(
        self,
        property_shark_phones: List[Dict[str, Any]],
        skipgenie_phones: List[Dict[str, Any]],
        truepeoplesearch_phones: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Normalize phone numbers from all sources and create a unified dictionary."""
        normalized_data = {}

        # Process all phone sources
        for source_name, phone_list in [
            ("PropertyShark", property_shark_phones),
            ("SkipGenie", skipgenie_phones),
            ("TruePeopleSearch", truepeoplesearch_phones),
        ]:
            for phone_data in phone_list:
                phone_number = phone_data.get("number", "")
                normalized_number = self._normalize_phone(phone_number)

                if not normalized_number:
                    continue

                # Format number consistently if possible
                formatted_number = self._format_phone_number(normalized_number) or phone_number
                contact_name = phone_data.get("contact_name", "Unknown")

                # If this number is already tracked, update sources
                if normalized_number in normalized_data:
                    normalized_data[normalized_number]["sources"].append(source_name)

                    # Keep track of all contacts associated with this number
                    if (
                        contact_name
                        and contact_name not in normalized_data[normalized_number]["contacts"]
                    ):
                        normalized_data[normalized_number]["contacts"].append(contact_name)
                else:
                    # Add a new phone number entry
                    normalized_data[normalized_number] = {
                        "number": formatted_number,
                        "sources": [source_name],
                        "contacts": [contact_name] if contact_name else [],
                        "type": phone_data.get("type", "Unknown"),
                    }

        return normalized_data

    def _simple_phone_analysis(
        self, normalized_numbers: Dict[str, Dict[str, Any]], individual_owners: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Simple analysis for cases with few phone numbers."""
        refined_phones = []
        phone_data_by_contact = {}

        # Match phone numbers to contacts where possible
        for norm_number, phone_data in normalized_numbers.items():
            # Determine confidence based on sources
            sources = phone_data["sources"]
            confidence = "low"
            if len(sources) > 1:
                if "PropertyShark" in sources:
                    confidence = "medium-high"
                else:
                    confidence = "medium"
            elif "PropertyShark" in sources:
                confidence = "medium"

            # Find most likely contact for this phone
            contacts = phone_data["contacts"]
            best_contact = None

            # First check if it matches any known individual owner
            if individual_owners and contacts:
                owner_names = {owner["name"].lower() for owner in individual_owners}
                for contact in contacts:
                    if contact.lower() in owner_names:
                        best_contact = contact
                        break

            # If no match, use the first contact or "Unknown"
            if not best_contact:
                best_contact = contacts[0] if contacts else "Unknown"

            # Create refined phone entry
            refined_phone = {
                "number": phone_data["number"],
                "contact_name": best_contact,
                "confidence": confidence,
                "sources": sources,
                "type": phone_data.get("type", "Unknown"),
            }

            refined_phones.append(refined_phone)

            # Add to phone_data_by_contact
            if best_contact not in phone_data_by_contact:
                phone_data_by_contact[best_contact] = []
            phone_data_by_contact[best_contact].append(refined_phone)

        # Sort by confidence
        confidence_order = {"high": 0, "medium-high": 1, "medium": 2, "low": 3}
        refined_phones.sort(key=lambda x: confidence_order.get(x["confidence"], 4))

        # Get primary phone (highest confidence)
        primary_phone = refined_phones[0]["number"] if refined_phones else ""

        return {
            "refined_phone_numbers": refined_phones,
            "primary_phone": primary_phone,
            "phone_data_by_contact": phone_data_by_contact,
            "notes": f"Simple analysis performed on {len(refined_phones)} phone numbers.",
        }

    def _llm_phone_analysis(
        self,
        state: PropertyResearchState,
        property_shark_phones: List[Dict[str, Any]],
        skipgenie_phones: List[Dict[str, Any]],
        truepeoplesearch_phones: List[Dict[str, Any]],
        individual_owners: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Use LLM to analyze more complex phone number scenarios."""
        # Prepare data for the LLM
        prompt = f"""
        You are an expert data analyst tasked with refining phone number data from multiple sources.
        
        # PROPERTY INFORMATION
        Address: {state["address"]}
        Owner Name: {state.get("owner_name", "Unknown")}
        Owner Type: {state.get("owner_type", "unknown")}
        
        # INDIVIDUAL OWNERS/CONTACTS
        {json.dumps(individual_owners, indent=2, default=str)}
        
        # PHONE NUMBER SOURCES
        
        ## 1. PROPERTY SHARK PHONES
        {json.dumps(property_shark_phones, indent=2, default=str)}
        
        ## 2. SKIPGENIE PHONES
        {json.dumps(skipgenie_phones, indent=2, default=str)}
        
        ## 3. TRUE PEOPLE SEARCH PHONES
        {json.dumps(truepeoplesearch_phones, indent=2, default=str)}
        
        # TASK
        Analyze all phone numbers from the different sources and:
        
        1. Match phone numbers to individual owners/contacts where possible
        2. Determine confidence levels for each phone number based on multiple factors:
           - HIGH confidence: Numbers that appear in multiple sources for the same contact
           - MEDIUM-HIGH confidence: PropertyShark numbers that match with another source
           - MEDIUM confidence: Numbers from PropertyShark or numbers that have supporting evidence
           - LOW confidence: Numbers that appear in only one source with limited context
        
        3. For each phone number, include:
           - number: The formatted phone number (format as (XXX) XXX-XXXX if possible)
           - contact_name: The person associated with this number
           - confidence: high, medium-high, medium, or low
           - sources: List of sources that provided this number
           - type: Type of phone (mobile, work, etc.) if available
        
        4. Organize phone numbers by contact and confidence
        
        5. Identify the primary phone number (highest confidence)
        
        # CONSIDERATIONS
        - Phone numbers may appear in slightly different formats across sources
        - The same phone number might be associated with different contacts
        - Some contacts may have multiple phone numbers
        - Names may vary slightly between sources (e.g., "John Smith" vs "J. Smith")
        """

        # Create chain with structured output
        chain = self.llm.with_structured_output(PhoneNumberAnalysisResponse)

        try:
            # Get structured response from LLM
            result = chain.invoke(prompt)
            logger.info(f"Successfully analyzed phone numbers for {state['address']}")

            # Convert to dictionary and return
            return result.dict()

        except Exception as e:
            logger.error(f"Error in LLM phone number analysis: {str(e)}")
            # Fall back to simple analysis
            normalized_numbers = self._normalize_phone_data(
                property_shark_phones, skipgenie_phones, truepeoplesearch_phones
            )
            return self._simple_phone_analysis(normalized_numbers, individual_owners)

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison by removing all non-digits."""
        if not phone:
            return ""
        return re.sub(r"\D", "", phone)

    def _format_phone_number(self, normalized_number: str) -> Optional[str]:
        """Format phone number as (XXX) XXX-XXXX if possible."""
        if len(normalized_number) == 10:
            return f"({normalized_number[:3]}) {normalized_number[3:6]}-{normalized_number[6:]}"
        elif len(normalized_number) == 11 and normalized_number[0] == "1":
            return f"({normalized_number[1:4]}) {normalized_number[4:7]}-{normalized_number[7:]}"
        return None
