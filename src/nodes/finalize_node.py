import logging
import os
import pandas as pd
from typing import Dict, Any, List, Optional

from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class FinalizeNode:
    """Node for finalizing the property research workflow and saving complete results to spreadsheet."""

    def __init__(self):
        """Initialize the finalize node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """
        Finalize the property research process and save all data to spreadsheet.

        This node runs after all data collection (including SkipGenie and TruePeopleSearch)
        is complete, ensuring that the spreadsheet contains the most comprehensive
        contact information available.
        """
        logger.info("🏁 Finalizing property research and saving complete results")
        print("🏁 Finalizing property research and saving complete results")

        try:
            # Save complete data to spreadsheet
            self._save_to_spreadsheet(state)

            # Return minimal state update
            return {
                "current_step": "Finalization completed",
                "next_steps": [],
            }

        except Exception as e:
            logger.error(f"Finalization error: {str(e)}")
            logger.exception("Detailed error:")
            return {
                "errors": [f"Finalization error: {str(e)}"],
                "current_step": "Finalization failed",
                "next_steps": [],
            }

    def _save_to_spreadsheet(self, state: PropertyResearchState) -> None:
        """
        Save property ownership and contact data to Excel spreadsheet.

        Incorporates all data from the property research workflow, including:
        - Basic property and owner information from Analyzer
        - Refined contact information from PhoneNumberRefiner
        """
        # Create results directory if needed
        results_dir = os.path.join(os.getcwd(), "results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            logger.info(f"Created results directory: {results_dir}")

        excel_path = os.path.join(results_dir, "property_owners.xlsx")

        # Define columns
        columns = [
            "Property Address",
            "Owner Name",
            "Owner Type",
            "Contact Name",
            "Company",
            "Phone 1",
            "Phone 1 Contact",
            "Phone 1 Confidence",
            "Phone 1 Sources",
            "Phone 2",
            "Phone 2 Contact",
            "Phone 2 Confidence",
            "Phone 2 Sources",
            "Phone 3",
            "Phone 3 Contact",
            "Phone 3 Confidence",
            "Phone 3 Sources",
            "Email 1",
            "Email 2",
            "Confidence",
            "Notes",
        ]

        # Prepare data for spreadsheet
        address = state.get("address", "Unknown")
        owner_name = state.get("owner_name", "Unknown")
        owner_type = state.get("owner_type", "unknown")

        # Determine if owner is a company
        company = state.get("company_name", "")
        if not company and owner_type.lower() in ["llc", "corporation"]:
            company = owner_name

        # Get individual owners as potential contacts
        individual_owners = state.get("individual_owners", [])
        primary_contact = ""
        if individual_owners:
            # Use the first individual owner as the primary contact
            primary_contact = individual_owners[0]["name"]
        elif owner_type.lower() == "individual":
            primary_contact = owner_name

        # Process phone numbers from refined phone data
        refined_phones = state.get("refined_phone_numbers", [])
        phone_data = []

        # Use refined phones (already sorted by confidence)
        for phone_info in refined_phones[:3]:  # Get top 3 phone numbers
            sources = ", ".join(phone_info.get("sources", []))
            confidence = phone_info.get("confidence", "unknown")
            contact_name = phone_info.get("contact_name", "")
            phone_data.append(
                {
                    "number": phone_info["number"],
                    "contact": contact_name,
                    "confidence": confidence,
                    "sources": sources,
                }
            )

        # Ensure we have exactly 3 phone entries (including empty ones)
        phones_flat = []
        for i in range(3):
            if i < len(phone_data):
                phones_flat.extend(
                    [
                        phone_data[i]["number"],
                        phone_data[i]["contact"],
                        phone_data[i]["confidence"],
                        phone_data[i]["sources"],
                    ]
                )
            else:
                phones_flat.extend(["", "", "", ""])

        # Process email addresses from multiple sources
        email_addresses = []

        # Add extracted emails from Analyzer
        extracted_emails = state.get("extracted_emails", [])
        if extracted_emails:
            email_addresses.extend([e for e in extracted_emails if e])

        # Ensure we have at least 2 email slots (empty strings for missing emails)
        emails = (email_addresses + [""] * 2)[:2]

        # Get confidence level, defaulting to medium if not available
        confidence = state.get("confidence", "medium")

        # Build notes with information about phone number sources
        notes = state.get("extracted_notes", "")

        # Add information about phone number confidence if available
        if refined_phones and not notes:
            phone_sources = set()
            for phone in refined_phones[:1]:  # Just look at the first (primary) phone
                if "sources" in phone:
                    phone_sources.update(phone["sources"])

            if phone_sources:
                sources_str = ", ".join(sorted(phone_sources))
                notes = f"Primary phone confirmed by sources: {sources_str}. "

        if not notes:
            # Include information about all data sources used
            notes = "Data compiled from multiple sources: "

            if state.get("property_shark_ownership_data"):
                notes += "PropertyShark, "

            if state.get("acris_property_records"):
                notes += "ACRIS, "

            if state.get("zola_owner_name"):
                notes += "ZoLa, "

            if state.get("company_registry_data"):
                notes += "OpenCorporates, "

            if state.get("skipgenie_phones") or state.get("truepeoplesearch_phones"):
                notes += "SkipGenie/TruePeopleSearch, "

            # Remove trailing comma and space
            notes = notes.rstrip(", ")

        # Create row data
        new_row = (
            [
                address,
                owner_name,
                owner_type,
                primary_contact,
                company,
            ]
            + phones_flat
            + emails
            + [confidence, notes]
        )

        # Load existing spreadsheet or create new one
        try:
            if os.path.exists(excel_path):
                df = pd.read_excel(excel_path)

                # Check if columns match, if not, recreate the spreadsheet
                if list(df.columns) != columns:
                    logger.warning("Spreadsheet columns don't match expected format, recreating")
                    df = pd.DataFrame(columns=columns)

                # Skip if address already exists
                if address in df["Property Address"].values:
                    logger.info(
                        f"Address '{address}' already exists in spreadsheet, updating entry"
                    )
                    # Update existing entry
                    df.loc[df["Property Address"] == address] = new_row
                else:
                    # Add new row
                    df.loc[len(df)] = new_row
            else:
                # Create new spreadsheet
                df = pd.DataFrame(columns=columns)
                df.loc[0] = new_row

            # Save spreadsheet
            df.to_excel(excel_path, index=False)
            logger.info(f"Saved property data to {excel_path}")
            print(f"📊 Saved complete property data to spreadsheet: {excel_path}")

        except Exception as e:
            logger.error(f"Error saving spreadsheet: {e}")
            raise
