import logging
import os
import pandas as pd
from typing import Dict, Any, List, Optional
from io import BytesIO

from ..state import PropertyResearchState
from ..utils.s3 import upload_fileobj, file_exists, download_fileobj

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
        
        If ENVIRONMENT=production, the data will be uploaded to S3.
        Otherwise, it will be saved to the local filesystem.
        """
        logger.info("🏁 Finalizing property research and saving complete results")
        print("🏁 Finalizing property research and saving complete results")

        try:
            # Save complete data to spreadsheet
            self._save_to_spreadsheet(state)

            # Determine storage location from result
            if "excel_s3_path" in state:
                storage_location = f"S3: {state['excel_s3_path']}"
            else:
                results_dir = os.path.join(os.getcwd(), "results")
                excel_path = os.path.join(results_dir, "property_owners.xlsx")
                storage_location = f"Local: {excel_path}"

            # Return state update with storage information
            return {
                "current_step": "Finalization completed",
                "storage_location": storage_location,
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

        If running in production (ENVIRONMENT=production), data is uploaded to S3.
        Otherwise, data is saved to the local filesystem.
        """
        # Determine environment and storage method
        environment = os.environ.get("ENVIRONMENT", "development").lower()
        is_production = environment == "production"
        
        # Set the filename and path
        filename = "property_owners.xlsx"
        
        if not is_production:
            # Save to local filesystem
            # Create results directory if needed
            results_dir = os.path.join(os.getcwd(), "results")
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
                logger.info(f"Created results directory: {results_dir}")

            excel_path = os.path.join(results_dir, filename)
        else:
            # For S3, we'll just need the filename initially
            excel_path = filename
            
        # Get S3 configuration for production environment
        s3_bucket = os.environ.get("S3_BUCKET_NAME")
        s3_key_prefix = os.environ.get("S3_KEY_PREFIX", "property_research")

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
            elif is_production and s3_bucket:
                # Try to load from S3 if the file exists
                s3_key = f"{s3_key_prefix.rstrip('/')}/{filename}"
                
                if file_exists(s3_bucket, s3_key):
                    # File exists, download it
                    excel_buffer = BytesIO()
                    if download_fileobj(s3_bucket, s3_key, excel_buffer):
                        excel_buffer.seek(0)
                        
                        # Load DataFrame from the downloaded file
                        df = pd.read_excel(excel_buffer)
                        
                        # Check if columns match
                        if list(df.columns) != columns:
                            logger.warning("S3 spreadsheet columns don't match expected format, recreating")
                            df = pd.DataFrame(columns=columns)
                        
                        # Update or add row based on address
                        if address in df["Property Address"].values:
                            logger.info(f"Address '{address}' already exists in S3 spreadsheet, updating entry")
                            df.loc[df["Property Address"] == address] = new_row
                        else:
                            df.loc[len(df)] = new_row
                    else:
                        # Download failed, create new DataFrame
                        logger.warning(f"Failed to download existing spreadsheet from S3, creating new one")
                        df = pd.DataFrame(columns=columns)
                        df.loc[0] = new_row
                else:
                    # File doesn't exist, create new DataFrame
                    logger.info(f"No existing spreadsheet found in S3, creating new one")
                    df = pd.DataFrame(columns=columns)
                    df.loc[0] = new_row
            else:
                # Create new spreadsheet
                df = pd.DataFrame(columns=columns)
                df.loc[0] = new_row
                
            # Save spreadsheet
            if not is_production:
                # Save to local filesystem
                df.to_excel(excel_path, index=False)
                logger.info(f"Saved property data to {excel_path}")
                print(f"📊 Saved complete property data to spreadsheet: {excel_path}")
            else:
                # Upload to S3
                if not s3_bucket:
                    raise ValueError("S3_BUCKET_NAME environment variable is required in production environment")
                
                try:
                    # Save to BytesIO object first
                    excel_buffer = BytesIO()
                    df.to_excel(excel_buffer, index=False)
                    excel_buffer.seek(0)
                    
                    # Create full S3 key (path + filename)
                    s3_key = f"{s3_key_prefix.rstrip('/')}/{filename}"
                    
                    # Upload file to S3
                    if upload_fileobj(excel_buffer, s3_bucket, s3_key):
                        s3_path = f"s3://{s3_bucket}/{s3_key}"
                        logger.info(f"Uploaded property data to {s3_path}")
                        print(f"📊 Uploaded complete property data to S3: {s3_path}")
                        
                        # Add S3 path to state
                        state["excel_s3_path"] = s3_path
                    else:
                        error_message = "Failed to upload spreadsheet to S3"
                        logger.error(error_message)
                        raise Exception(error_message)
                except Exception as e:
                    error_message = f"S3 upload error: {str(e)}"
                    logger.error(error_message)
                    raise Exception(error_message)

        except Exception as e:
            logger.error(f"Error saving spreadsheet: {e}")
            raise
