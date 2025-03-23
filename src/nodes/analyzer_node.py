import logging
import re
import json
import os
import pandas as pd
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class PropertyAnalysisResponse(BaseModel):
    """Unified schema for property data and owner analysis."""

    # Basic property information
    owner_name: str = Field(description="The full legal name of the owner (individual or entity)")
    owner_type: str = Field(description="One of: llc, corporation, individual, or unknown")
    confidence: str = Field(description="One of: high, medium, or low")

    # Contact information
    contacts: List[str] = Field(description="Contact names associated with the property (up to 4)")
    phones: List[str] = Field(
        description="Phone numbers associated with the property or contacts (up to 6)"
    )
    emails: List[str] = Field(
        description="Email addresses associated with the property or contacts (up to 4)"
    )
    primary_phone: str = Field(description="The most reliable phone number")

    # Company information
    company_name: str = Field(
        description="Company name if owner is LLC or corporation, otherwise empty string"
    )

    # Individual owners
    individual_owners: List[Dict[str, str]] = Field(
        description="List of individual owners/contacts with name, source, and type"
    )
    has_individual_owners: bool = Field(description="Whether any individual owners were identified")

    # Additional information
    notes: str = Field(
        description="Any explanations, observations, or additional context about the data"
    )


class AnalyzerNode:
    """Node for analyzing property data and extracting ownership information."""

    def __init__(self, model_name="gpt-4o", temperature=0):
        """Initialize the analyzer node."""
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def run(self, state: PropertyResearchState) -> dict:
        """Extract data from property research state and store in the state."""
        logger.info("🧠 Analyzing property data and extracting ownership information")
        print("🧠 Analyzing property data and extracting ownership information")

        try:
            # Extract all property data with LLM in a single call
            analysis = self._analyze_property_data(state)

            # Extract PropertyShark phone numbers separately if available
            property_shark_phones = self._extract_property_shark_phones(state)

            # Store extracted data in state
            updated_state = {
                "owner_name": analysis.get("owner_name", "Unknown"),
                "owner_type": analysis.get("owner_type", "unknown"),
                "individual_owners": analysis.get("individual_owners", []),
                "has_individual_owners": analysis.get("has_individual_owners", False),
                "confidence": analysis.get("confidence", "low"),
                "extracted_contacts": analysis.get("contacts", []),
                "extracted_emails": analysis.get("emails", []),
                "extracted_notes": analysis.get("notes", ""),
                "property_shark_phones": property_shark_phones,
                "current_step": "Analysis completed",
                # Next steps will be determined by conditional logic in the workflow
                "next_steps": [],
            }

            # If company name is available, add it to the state
            if analysis.get("company_name"):
                updated_state["company_name"] = analysis["company_name"]

            return updated_state

        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            logger.exception("Detailed error:")
            return {
                "errors": [f"Analysis error: {str(e)}"],
                "current_step": "Analysis failed",
                "next_steps": [],
            }

    def _analyze_property_data(self, state: PropertyResearchState) -> Dict[str, Any]:
        """Analyze all property data in a single LLM call and return structured response."""
        logger.info("Using LLM to analyze property data comprehensively")

        prompt = f"""
        You are a real estate data analyst tasked with extracting comprehensive information for a property.
        
        # PROPERTY INFORMATION
        Address: {state["address"]}
        
        # DATA SOURCES
        
        ## 1. PROPERTY SHARK DATA
        {json.dumps(state.get("property_shark_ownership_data", {}), indent=2, default=str)}
        
        ## 2. PROPERTY DOCUMENTS FROM ACRIS
        {json.dumps(state.get("property_ownership_records", []), indent=2, default=str)}
        
        ## 3. ACRIS PROPERTY RECORDS
        {json.dumps(state.get("acris_property_records", {}), indent=2, default=str)}
        
        ## 4. ZOLA OWNER INFORMATION
        Owner Name: {state.get("zola_owner_name", "Not available")}
        
        ## 5. COMPANY REGISTRY DATA (if available)
        {json.dumps(state.get("company_registry_data", {}), indent=2, default=str)}
        
        ## 6. PERSON SEARCH RESULTS (if available)
        {json.dumps(state.get("person_search_results", {}), indent=2, default=str)}
        
        # COMPREHENSIVE ANALYSIS TASK
        
        Analyze all available data sources and provide:
        
        1. PRIMARY OWNERSHIP INFORMATION
           - The most likely current legal owner of the property
           - Whether the owner is an LLC, corporation, or individual
           - Your confidence level in this determination
           - If the owner is an LLC or corporation, identify the company name
        
        2. INDIVIDUAL OWNERS/CONTACTS
           - Identify all individual owners/contacts associated with this property from all sources
           - For each individual owner/contact identified, provide:
             * name: Their full name
             * source: Where you found this person (PropertyShark, ACRIS, ZoLa, etc.)
             * type: Their role (owner, manager, member, etc.)
           - Determine if we have any individual owners identified (true/false)
        
        3. CONTACT INFORMATION
           - Contact names associated with the property (up to 4)
           - Phone numbers associated with the property or contacts (up to 6)
           - Email addresses associated with the property or contacts (up to 4)
           - The primary phone number (the most reliable one)
        
        4. NOTES AND CONTEXT
           - Provide any observations, explanations, or additional context about the data
        
        # IMPORTANT CONSIDERATIONS
        
        - PropertyShark and ACRIS are reliable sources for ownership information
        - PropertyShark's "real_owners" data is good for contact information
        - Consider all sources when identifying individual owners
        - Look for real people associated with LLCs or corporations
        - Format phone numbers as (XXX) XXX-XXXX if possible
        - HIGH confidence: When data matches across multiple sources
        - MEDIUM confidence: When data is from reliable source but not confirmed by others
        - LOW confidence: When sources conflict or limited data is available
        - The goal is to identify all possible individual contacts for this property
        """

        # Create chain with structured output
        chain = self.llm.with_structured_output(PropertyAnalysisResponse)

        try:
            # Get structured response from LLM
            result = chain.invoke(prompt)
            logger.info(f"Successfully analyzed property data for {state['address']}")

            # Convert to dictionary and return
            return result.dict()

        except Exception as e:
            logger.error(f"Error in LLM property analysis: {str(e)}")
            # Fall back to minimal extraction
            return self._fallback_extraction(state)

    def _fallback_extraction(self, state: PropertyResearchState) -> Dict[str, Any]:
        """Fallback extraction method if LLM fails."""
        logger.info("Using fallback extraction method")

        # Basic extraction from PropertyShark
        owner_name = "Unknown"
        owner_type = "unknown"
        confidence = "low"
        contacts = []
        phones = []
        emails = []
        primary_phone = ""
        individual_owners = []
        has_individual_owners = False
        company_name = ""
        notes = "Data extracted using fallback method due to LLM extraction failure."

        # Try to get owner from PropertyShark
        ps_data = state.get("property_shark_ownership_data", {})
        ps_owner = None
        if (
            isinstance(ps_data, dict)
            and "registered_owners" in ps_data
            and "data" in ps_data["registered_owners"]
        ):
            ps_owner = ps_data["registered_owners"]["data"].get("name")
            if ps_owner:
                owner_name = ps_owner
                owner_type = self._determine_owner_type(owner_name)
                confidence = "medium"  # Default to medium if only PropertyShark data is available

                # Set company name if it's an LLC or corporation
                if owner_type.lower() in ["llc", "corporation"]:
                    company_name = owner_name

        # Check ZoLa data
        zola_owner = state.get("zola_owner_name")

        # Check ACRIS data
        acris_owner = None
        if state.get("property_ownership_records"):
            for record in state["property_ownership_records"]:
                if "entity_owner" in record and record["entity_owner"]:
                    acris_owner = record["entity_owner"]
                    break

                # Try to extract individual owners from ACRIS
                if "individual_owners" in record and record["individual_owners"]:
                    for ind_owner in record["individual_owners"]:
                        name = ind_owner.get("name", "")
                        if name:
                            individual_owners.append(
                                {
                                    "name": name,
                                    "source": "ACRIS",
                                    "type": ind_owner.get("title", "unknown"),
                                }
                            )
                            has_individual_owners = True

        # Extract individuals from PropertyShark if available
        if isinstance(ps_data, dict) and "real_owners" in ps_data:
            for owner in ps_data["real_owners"]:
                name = owner.get("name", "")
                if name:
                    individual_owners.append(
                        {"name": name, "source": "PropertyShark", "type": "real_owner"}
                    )
                    has_individual_owners = True

                    # Add to contacts as well
                    if name not in contacts:
                        contacts.append(name)

        # Determine confidence based on data agreement
        if ps_owner:
            # If we have PropertyShark data, check if it matches other sources
            if (zola_owner and self._names_match(ps_owner, zola_owner)) or (
                acris_owner and self._names_match(ps_owner, acris_owner)
            ):
                confidence = "high"
            elif not zola_owner and not acris_owner:
                confidence = "medium"
            else:
                confidence = "low"
        elif acris_owner:
            # If we only have ACRIS data
            owner_name = acris_owner
            owner_type = self._determine_owner_type(owner_name)
            if zola_owner and self._names_match(acris_owner, zola_owner):
                confidence = "medium"
            else:
                confidence = "low"

            # Set company name if it's an LLC or corporation
            if owner_type.lower() in ["llc", "corporation"]:
                company_name = owner_name

        elif zola_owner:
            # If we only have ZoLa data
            owner_name = zola_owner
            owner_type = self._determine_owner_type(owner_name)
            confidence = "low"

            # Set company name if it's an LLC or corporation
            if owner_type.lower() in ["llc", "corporation"]:
                company_name = owner_name

        # Add explanation to notes
        if confidence == "high":
            notes += " Owner information confirmed across multiple sources."
        elif confidence == "medium":
            notes += " Owner information from a reliable source but not confirmed by other sources."
        else:
            notes += " Limited or conflicting owner information available."

        return {
            "owner_name": owner_name,
            "owner_type": owner_type,
            "confidence": confidence,
            "contacts": contacts,
            "phones": phones,
            "emails": emails,
            "primary_phone": primary_phone,
            "company_name": company_name,
            "individual_owners": individual_owners,
            "has_individual_owners": has_individual_owners,
            "notes": notes,
        }

    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two owner names match, accounting for common variations."""
        if not name1 or not name2:
            return False

        # Normalize names for comparison
        n1 = name1.upper().strip()
        n2 = name2.upper().strip()

        # Direct match
        if n1 == n2:
            return True

        # Check for LLC variations
        n1_normalized = (
            n1.replace(".", "").replace(",", "").replace(" LLC", "LLC").replace("L.L.C", "LLC")
        )
        n2_normalized = (
            n2.replace(".", "").replace(",", "").replace(" LLC", "LLC").replace("L.L.C", "LLC")
        )

        if n1_normalized == n2_normalized:
            return True

        # Check if one is a substring of the other (for abbreviated names)
        if len(n1) > 5 and len(n2) > 5:
            if n1 in n2 or n2 in n1:
                return True

        return False

    def _determine_owner_type(self, owner_name: str) -> str:
        """Determine owner type based on name."""
        if not owner_name:
            return "unknown"

        upper_name = owner_name.upper()
        if "LLC" in upper_name or "L.L.C" in upper_name:
            return "llc"
        elif "CORP" in upper_name or "INC" in upper_name:
            return "corporation"
        else:
            return "individual"

    def _extract_property_shark_phones(self, state: PropertyResearchState) -> List[Dict[str, Any]]:
        """Extract phone numbers from PropertyShark data as one potential source."""
        phone_data = []

        try:
            ps_data = state.get("property_shark_ownership_data", {})

            # Extract phone numbers from real_owners section
            if isinstance(ps_data, dict) and "real_owners" in ps_data:
                real_owners = ps_data["real_owners"]

                for owner in real_owners:
                    contact_name = owner.get("name", "Unknown")

                    # Extract phones for this contact
                    if "phones" in owner and owner["phones"]:
                        for phone in owner["phones"]:
                            phone_data.append(
                                {
                                    "number": phone,
                                    "contact_name": contact_name,
                                    "source": "PropertyShark",
                                    "confidence": "medium",  # PropertyShark is just one source
                                }
                            )

            logger.info(f"Extracted {len(phone_data)} phone numbers from PropertyShark")
            return phone_data

        except Exception as e:
            logger.warning(f"Error extracting PropertyShark phones: {str(e)}")
            return []
