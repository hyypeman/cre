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

    # Individual owners - restructured to separate name from metadata
    individual_owners: List[Dict[str, str]] = Field(
        description="List of individual owners/contacts with clean name and metadata separated"
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

            # Perform final validation of individual owners to ensure clean names
            individual_owners = self._ensure_clean_individual_owners(
                analysis.get("individual_owners", [])
            )

            # Store extracted data in state
            updated_state = {
                "owner_name": analysis.get("owner_name", "Unknown"),
                "owner_type": analysis.get("owner_type", "unknown"),
                "individual_owners": individual_owners,
                "has_individual_owners": analysis.get("has_individual_owners", False)
                and len(individual_owners) > 0,
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
             * name: Their full name (do NOT include source, type, or any other annotations in the name)
             * source: Where you found this person (PropertyShark, ACRIS, ZoLa, etc.)
             * type: Their role (owner, manager, member, etc.)
           - Determine if we have any individual owners identified (true/false)
           - IMPORTANT: Keep the name field clean with ONLY the person's name
        
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
                    idx = 0
                    for ind_owner in record["individual_owners"]:
                        name = ind_owner.get("name", "")
                        if name:
                            idx += 1
                            # Store clean name and metadata separately
                            individual_owners.append(
                                {
                                    "name": name,  # Store only the name
                                    "source": "ACRIS",
                                    "type": ind_owner.get("title", "owner"),
                                    "order": idx,  # Store order as separate field
                                }
                            )
                            has_individual_owners = True

        # Extract individuals from PropertyShark if available
        if isinstance(ps_data, dict) and "real_owners" in ps_data:
            ps_idx = 0
            for owner in ps_data["real_owners"]:
                name = owner.get("name", "")
                if name:
                    ps_idx += 1
                    # Store clean name and metadata separately
                    individual_owners.append(
                        {
                            "name": name,  # Store only the name
                            "source": "PropertyShark",
                            "type": "real_owner",
                            "order": ps_idx,  # Store order as separate field
                        }
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

    def _ensure_clean_individual_owners(
        self, individual_owners: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate and clean individual owner names using LLM to ensure no annotations are present.

        Args:
            individual_owners: List of individual owner dictionaries

        Returns:
            Cleaned list of individual owners
        """
        if not individual_owners:
            return []

        cleaned_owners = []
        names_to_clean = []

        # First pass: identify names that need cleaning
        for i, owner in enumerate(individual_owners):
            if not isinstance(owner, dict) or "name" not in owner:
                continue

            name = owner["name"]

            # Check if name likely has annotations
            if "(" in name or "-" in name or ":" in name:
                names_to_clean.append({"index": i, "original_name": name, "owner_data": owner})
            else:
                cleaned_owners.append(owner)

        # If no names need cleaning, return the original list
        if not names_to_clean:
            return individual_owners

        # Use LLM to clean names and extract metadata in batch
        cleaned_data = self._clean_names_with_llm(names_to_clean)

        # Add cleaned data to the final list
        for item in cleaned_data:
            cleaned_owners.append(item)

        # Sort the cleaned owners to maintain original order
        cleaned_owners.sort(key=lambda x: x.get("order", 999))

        return cleaned_owners

    def _clean_names_with_llm(self, names_to_clean: List[Dict]) -> List[Dict[str, Any]]:
        """
        Use LLM to clean names and extract metadata from annotated names.

        Args:
            names_to_clean: List of dictionaries containing names that need cleaning

        Returns:
            List of owner dictionaries with clean names and extracted metadata
        """
        if not names_to_clean:
            return []

        # Prepare the prompt for the LLM
        prompt = """
        You are an expert in data cleaning. I have a list of names with annotations that I need cleaned.
        For each name, I need you to:
        
        1. Extract just the person's name without any annotations, numbers, or role information
        2. Extract metadata like the person's role (owner, member, manager, etc.)
        3. Extract the source of the information (ACRIS, PropertyShark, etc.)
        
        Here are the annotated names:
        
        """

        for i, item in enumerate(names_to_clean):
            prompt += f'{i + 1}. "{item["original_name"]}"\n'

        prompt += """
        Please provide a structured response in the following format:
        
        ```json
        [
          {
            "original": "Annotated name as provided",
            "clean_name": "Just the person's name",
            "role": "Their role (if found)",
            "source": "Information source (if found)",
            "notes": "Any additional information"
          },
          ...
        ]
        ```
        
        Always preserve the original list order. If any information can't be determined, use "unknown" for that field.
        """

        try:
            # Create a message for the LLM
            messages = [
                SystemMessage(
                    content="You are a data cleaning assistant that extracts clean names and metadata from annotated text."
                ),
                HumanMessage(content=prompt),
            ]

            # Get response from the LLM
            response = self.llm.invoke(messages)

            # Extract JSON from the response text
            json_text = ""
            in_json = False

            for line in response.content.split("\n"):
                if line.strip() == "```json":
                    in_json = True
                    continue
                elif line.strip() == "```" and in_json:
                    break
                elif in_json:
                    json_text += line + "\n"

            # Parse the JSON response
            if json_text:
                cleaned_data = json.loads(json_text)

                # Match the cleaned data back to the original items and create owner dictionaries
                result = []

                for i, item in enumerate(names_to_clean):
                    try:
                        original_owner = item["owner_data"]
                        cleaned_info = cleaned_data[i] if i < len(cleaned_data) else None

                        if cleaned_info:
                            # Create a new owner dictionary with the cleaned name
                            clean_owner = original_owner.copy()

                            # Update with cleaned data
                            clean_owner["name"] = cleaned_info["clean_name"].strip()

                            # Only update metadata if not already present
                            if "role" in cleaned_info and cleaned_info["role"] != "unknown":
                                if (
                                    "type" not in clean_owner
                                    or not clean_owner["type"]
                                    or clean_owner["type"] == "unknown"
                                ):
                                    clean_owner["type"] = cleaned_info["role"]

                            if "source" in cleaned_info and cleaned_info["source"] != "unknown":
                                if "source" not in clean_owner or not clean_owner["source"]:
                                    clean_owner["source"] = cleaned_info["source"]

                            # Keep track of the original order
                            clean_owner["order"] = item["index"]

                            # Add to results
                            result.append(clean_owner)

                            # Log the cleaning
                            logger.info(
                                f"LLM cleaned name: '{item['original_name']}' -> '{clean_owner['name']}'"
                            )
                        else:
                            # Fallback: add the original owner data
                            original_owner["order"] = item["index"]
                            result.append(original_owner)
                    except Exception as e:
                        logger.warning(f"Error processing cleaned data for item {i}: {str(e)}")
                        # Fallback: add the original owner data
                        original_owner = item["owner_data"].copy()
                        original_owner["order"] = item["index"]
                        result.append(original_owner)

                return result
            else:
                logger.warning("Could not extract JSON from LLM response")
        except Exception as e:
            logger.error(f"Error using LLM to clean names: {str(e)}")

        # Fallback: return the original data if LLM cleaning fails
        fallback_result = []
        for item in names_to_clean:
            owner_data = item["owner_data"].copy()
            owner_data["order"] = item["index"]

            # Apply basic regex cleaning as a last resort
            if "(" in owner_data["name"] or "-" in owner_data["name"]:
                clean_name = re.sub(r"\s*\(\d+\)\s*-\s*[^()]+\([^()]+\)", "", owner_data["name"])
                clean_name = re.sub(r"\s*\([^)]*\)", "", clean_name)
                clean_name = re.sub(r"\s*-\s*[^-]*$", "", clean_name)
                clean_name = clean_name.strip()

                if clean_name != owner_data["name"]:
                    logger.warning(f"Fallback cleaning: '{owner_data['name']}' -> '{clean_name}'")
                    owner_data["name"] = clean_name

            fallback_result.append(owner_data)

        return fallback_result
