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


class PropertyData(BaseModel):
    """Schema for property data extraction."""

    owner_name: str = Field(description="The full legal name of the owner (individual or entity)")
    owner_type: str = Field(description="One of: llc, corporation, individual, or unknown")
    confidence: str = Field(description="One of: high, medium, or low")
    contacts: List[str] = Field(description="Up to 4 contact names associated with the property")
    phones: List[str] = Field(
        description="Up to 6 phone numbers associated with the property or contacts"
    )
    emails: List[str] = Field(
        description="Up to 4 email addresses associated with the property or contacts"
    )
    primary_phone: str = Field(description="The most reliable phone number")
    company: str = Field(
        description="Company name if owner is LLC or corporation, otherwise empty string"
    )
    notes: str = Field(
        description="Any explanations, observations, or additional context about the data"
    )


class AnalyzerNode:
    """Node for analyzing property data and saving results to spreadsheet."""

    def __init__(self, model_name="gpt-4o", temperature=0):
        """Initialize the analyzer node."""
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.parser = JsonOutputParser(pydantic_object=PropertyData)

    def run(self, state: PropertyResearchState) -> dict:
        """Extract data from property research state and save to spreadsheet."""
        logger.info("🧠 Analyzing property data and saving to spreadsheet")
        print("🧠 Analyzing property data and saving to spreadsheet")

        try:
            # Extract all needed data using LLM
            extracted_data = self._extract_data_with_llm(state)

            # Save to spreadsheet
            self._save_to_spreadsheet(state, extracted_data)

            # Get primary phone for verification
            primary_phone = extracted_data.get("primary_phone", "")

            # Return state update with phone number for verification
            return {
                "owner_name": extracted_data["owner_name"],
                "owner_type": extracted_data["owner_type"],
                "contact_number": extracted_data["primary_phone"] or "Not available",
                "current_step": "Analysis completed",
                "next_steps": ["complete"],
            }

        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            logger.exception("Detailed error:")
            return {
                "errors": [f"Analysis error: {str(e)}"],
                "current_step": "Analysis failed",
                "next_steps": ["complete"],
            }

    def _extract_data_with_llm(self, state: PropertyResearchState) -> Dict[str, Any]:
        """Extract all needed data from available sources using LLM with structured output."""
        logger.info("Using LLM to extract property data for spreadsheet")

        prompt = f"""
        You are a real estate data analyst tasked with extracting information for a property spreadsheet.
        
        # PROPERTY INFORMATION
        Address: {state["address"]}
        
        # DATA SOURCES (in order of reliability)
        
        ## 1. PROPERTY SHARK DATA (Most Reliable)
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
        
        # TASK
        Analyze all available data sources and extract the following information:
        
        1. The most likely current legal owner of the property
        2. Whether the owner is an LLC, corporation, or individual
        3. Your confidence level in this determination
        4. Up to 4 contact names associated with the property
        5. Up to 6 phone numbers associated with the property or contacts
        6. Up to 4 email addresses associated with the property or contacts
        7. The primary phone number (the most reliable one)
        8. Any observations or explanations about the data in the notes field
        
        # PRIORITY RULES
        - PropertyShark's "registered_owners" data is the most reliable source for ownership
        - Recent deed documents from ACRIS are the next most reliable for ownership
        - PropertyShark's "real_owners" data is good for contact information
        - Phone numbers should be formatted as (XXX) XXX-XXXX if possible
        - If the owner is an LLC or corporation, list it as the company
        - If the owner is an individual, leave the company field empty
        
        # CONFIDENCE DETERMINATION
        - HIGH confidence: When PropertyShark data matches with ACRIS and/or ZoLa data
        - MEDIUM confidence: When only PropertyShark data is available, or when there are minor discrepancies between sources
        - LOW confidence: When sources conflict significantly or when limited data is available
        
        # IMPORTANT
        Include any explanations, observations, or additional context in the notes field.
        """

        # Create chain with structured output
        chain = self.llm.with_structured_output(PropertyData)

        try:
            # Get structured response from LLM
            result = chain.invoke(prompt)
            logger.info(f"Successfully extracted data for {state['address']}")

            # Convert to dictionary
            extracted_data = result.dict()

            # Ensure lists are properly initialized
            extracted_data["contacts"] = extracted_data.get("contacts", [])
            extracted_data["phones"] = extracted_data.get("phones", [])
            extracted_data["emails"] = extracted_data.get("emails", [])

            return extracted_data

        except Exception as e:
            logger.error(f"Error in LLM extraction: {str(e)}")
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

        # Check ZoLa data
        zola_owner = state.get("zola_owner_name")

        # Check ACRIS data
        acris_owner = None
        if state.get("property_ownership_records"):
            for record in state["property_ownership_records"]:
                if "entity_owner" in record and record["entity_owner"]:
                    acris_owner = record["entity_owner"]
                    break

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
        elif zola_owner:
            # If we only have ZoLa data
            owner_name = zola_owner
            owner_type = self._determine_owner_type(owner_name)
            confidence = "low"

        # Add explanation to notes
        if confidence == "high":
            notes += " Owner information confirmed across multiple sources."
        elif confidence == "medium":
            notes += " Owner information from a reliable source but not confirmed by other sources."
        else:
            notes += " Limited or conflicting owner information available."

        # Set company based on owner type
        company = owner_name if owner_type.lower() in ["llc", "corporation"] else ""

        return {
            "owner_name": owner_name,
            "owner_type": owner_type,
            "confidence": confidence,
            "contacts": contacts,
            "phones": phones,
            "emails": emails,
            "primary_phone": primary_phone,
            "company": company,
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

    def _save_to_spreadsheet(self, state: Dict[str, Any], extracted_data: Dict[str, Any]) -> None:
        """Save property ownership data to Excel spreadsheet."""
        # Create results directory if needed
        results_dir = os.path.join(os.getcwd(), "results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            logger.info(f"Created results directory: {results_dir}")

        excel_path = os.path.join(results_dir, "property_owners.xlsx")

        # Define columns
        columns = [
            "Property Address",
            "Contact 1",
            "Contact 2",
            "Contact 3",
            "Contact 4",
            "Company",
            "Phone 1",
            "Phone 2",
            "Phone 3",
            "Phone 4",
            "Phone 5",
            "Phone 6",
            "Email 1",
            "Email 2",
            "Email 3",
            "Email 4",
            "Owner Type",
            "Confidence",
            "Notes",
        ]

        # Prepare data for spreadsheet
        address = state["address"]
        company = extracted_data.get("company", "")
        if not company and extracted_data["owner_type"].lower() in ["llc", "corporation"]:
            company = extracted_data["owner_name"]

        contacts = (extracted_data["contacts"] + [""] * 4)[:4]
        phones = (extracted_data["phones"] + [""] * 6)[:6]
        emails = (extracted_data["emails"] + [""] * 4)[:4]
        owner_type = extracted_data["owner_type"]
        confidence = extracted_data["confidence"]
        notes = extracted_data.get("notes", "")

        # Create row data
        new_row = (
            [address] + contacts + [company] + phones + emails + [owner_type, confidence, notes]
        )

        # Load existing spreadsheet or create new one
        try:
            if os.path.exists(excel_path):
                df = pd.read_excel(excel_path)
                # Skip if address already exists
                if address in df["Property Address"].values:
                    logger.info(f"Address '{address}' already exists in spreadsheet, skipping")
                    return
            else:
                df = pd.DataFrame(columns=columns)

            # Add new row and save
            df.loc[len(df)] = new_row
            df.to_excel(excel_path, index=False)
            logger.info(f"Saved property data to {excel_path}")
            print(f"📊 Saved property data to spreadsheet: {excel_path}")

        except Exception as e:
            logger.error(f"Error saving spreadsheet: {e}")
