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
        - Contact information from SkipGenie
        - Contact information from TruePeopleSearch
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
            "Phone 2",
            "Phone 3",
            "Phone 4",
            "Phone 5",
            "Phone 6",
            "Email 1",
            "Email 2",
            "Email 3",
            "Email 4",
            "Confidence",
            "Notes",
        ]

        # Prepare data for spreadsheet
        address = state.get("address", "Unknown")
        owner_name = state.get("owner_name", "Unknown")
        owner_type = state.get("owner_type", "unknown")

        # Get contact information, prioritizing TruePeopleSearch over other sources
        contact_name = state.get("contact_name", "")
        if not contact_name:
            contact_name = owner_name if owner_type.lower() == "individual" else ""

        # Determine if owner is a company
        company = state.get("company_name", "")
        if not company and owner_type.lower() in ["llc", "corporation"]:
            company = owner_name

        # Process phone numbers from multiple sources
        phone_numbers = []

        # First add extracted phones from Analyzer (if available)
        extracted_phones = state.get("extracted_phones", [])
        if extracted_phones:
            phone_numbers.extend([p for p in extracted_phones if p])

        # Then add contact numbers from people search
        contact_numbers = state.get("contact_numbers", [])
        if contact_numbers:
            # Format and deduplicate phone numbers
            unique_numbers = set(phone_numbers)  # Track numbers we've already added
            for phone in contact_numbers:
                number = phone.get("number", "").strip()
                if number and number not in unique_numbers:
                    unique_numbers.add(number)
                    phone_numbers.append(number)

        # Ensure we have at least 6 phone slots (empty strings for missing phones)
        phones = (phone_numbers + [""] * 6)[:6]

        # Process email addresses from multiple sources
        email_addresses = []

        # First add extracted emails from Analyzer (if available)
        extracted_emails = state.get("extracted_emails", [])
        if extracted_emails:
            email_addresses.extend([e for e in extracted_emails if e])

        # Then add contact emails from people search
        contact_emails = state.get("contact_emails", [])
        if contact_emails:
            # Deduplicate emails
            unique_emails = set(email_addresses)  # Track emails we've already added
            for email in contact_emails:
                email = email.strip()
                if email and email not in unique_emails:
                    unique_emails.add(email)
                    email_addresses.append(email)

        # Ensure we have at least 4 email slots (empty strings for missing emails)
        emails = (email_addresses + [""] * 4)[:4]

        # Use contacts from both sources
        contacts = []

        # First add extracted contacts from Analyzer
        extracted_contacts = state.get("extracted_contacts", [])
        if extracted_contacts:
            contacts.extend([c for c in extracted_contacts if c])

        # Ensure we have exactly 4 contact fields
        contacts = (contacts + [""] * 4)[:4]

        # Get confidence level, defaulting to medium if not available
        confidence = state.get("confidence", "medium")

        # Build notes with information from Analyzer and data sources
        notes = state.get("extracted_notes", "")
        if not notes:
            notes = "Data compiled from multiple sources: "

            if state.get("property_shark_ownership_data"):
                notes += "PropertyShark, "

            if state.get("acris_property_records"):
                notes += "ACRIS, "

            if state.get("zola_owner_name"):
                notes += "ZoLa, "

            if state.get("company_registry_data"):
                notes += "OpenCorporates, "

            if state.get("contact_numbers") or state.get("contact_emails"):
                notes += "SkipGenie/TruePeopleSearch, "

            # Remove trailing comma and space
            notes = notes.rstrip(", ")

        # Create row data
        new_row = (
            [
                address,
                owner_name,
                owner_type,
                contact_name,
                company,
            ]
            + contacts
            + phones
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
