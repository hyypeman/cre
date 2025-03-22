import logging
import os

import pandas as pd
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class SpreadsheetNode:
    """Node for saving property ownership data to a spreadsheet."""

    def __init__(self):
        """Initialize the Spreadsheet node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Save property ownership data to Excel spreadsheet."""
        logger.info(f"🏢 Saving property ownership data to spreadsheet")
        print(f"🏢 Saving property ownership data to spreadsheet")

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

        try:
            # Get extracted data from state
            extracted_data = state.get("extracted_data", {})
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
            if os.path.exists(excel_path):
                df = pd.read_excel(excel_path)
                # Skip if address already exists
                if address in df["Property Address"].values:
                    logger.info(f"Address '{address}' already exists in spreadsheet, skipping")
                    return state
            else:
                df = pd.DataFrame(columns=columns)

            # Add new row and save
            df.loc[len(df)] = new_row
            df.to_excel(excel_path, index=False)
            logger.info(f"Saved property data to {excel_path}")
            print(f"📊 Saved property data to spreadsheet: {excel_path}")
            
        except Exception as e:
            logger.error(f"Error saving spreadsheet: {e}")
            state["errors"].append(f"Failed to save to spreadsheet: {str(e)}")
            
        return state
