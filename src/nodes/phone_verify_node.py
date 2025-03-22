import logging
import asyncio
from typing import List, Dict, Any
from ..state import PropertyResearchState
from ..utils.twilio import verify_phone_number
logger = logging.getLogger(__name__)


class TwilioNode:
    """Node for analyzing phone numbers using Twilio."""

    def __init__(self):
        """Initialize the Twilio Lookup node."""
        pass

    def run(self, state: PropertyResearchState) -> dict:
        """Analyze and validate phone numbers from property research state."""
        logger.info("📱 Analyzing and validating phone numbers")
        print("📱 Analyzing and validating phone numbers")
        
        try:
            # Extract all phone numbers from state
            all_phones = self._extract_all_phones(state)
            
            if not all_phones:
                logger.info("No phone numbers found to analyze")
                return {
                    "phone_verification": None,
                    "phone_number_valid": False,
                    "phone_analysis": {
                        "valid_phones": [],
                        "invalid_phones": [],
                        "primary_phone": None
                    },
                    "current_step": "Twilio verification skipped - no phone numbers"
                }
            
            # Validate phone numbers
            validation_results = self._validate_phones(all_phones)
            
            # Determine primary phone
            primary_phone = self._determine_primary_phone(validation_results, state)
            
            # Log the primary number status
            if primary_phone:
                logger.info(f"✅ Primary phone identified: {primary_phone.get('formatted', 'unknown')}")
                print(f"✅ Primary phone identified: {primary_phone.get('formatted', 'unknown')}")
            else:
                logger.info("❌ No valid primary phone number identified")
                print("❌ No valid primary phone number identified")
            
            # Update state with validation results
            return {
                "phone_verification": primary_phone,
                "phone_number_valid": primary_phone is not None,
                "phone_number_formatted": primary_phone.get("formatted", "") if primary_phone else "",
                "contact_number": primary_phone.get("formatted", state.get("contact_number", "Not available")) if primary_phone else state.get("contact_number", "Not available"),
                "phone_analysis": {
                    "valid_phones": validation_results["valid"],
                    "invalid_phones": validation_results["invalid"],
                    "primary_phone": primary_phone
                },
                "current_step": "Twilio verification completed"
            }
            
        except Exception as e:
            error_msg = f"Twilio verification error: {str(e)}"
            logger.error(error_msg)
            logger.exception("Detailed error:")
            
            return {
                "errors": [error_msg],
                "phone_verification": {"status": "error", "valid": False},
                "phone_number_valid": False,
                "phone_analysis": {
                    "valid_phones": [],
                    "invalid_phones": [],
                    "primary_phone": None
                },
                "current_step": "Twilio verification failed"
            }
    
    def _extract_all_phones(self, state: PropertyResearchState) -> List[str]:
        """Extract all phone numbers from various data sources in the state."""
        all_phones = set()
        
        # First check the contact_number from state (already determined primary phone)
        contact_number = state.get("contact_number")
        if contact_number and contact_number != "Not available":
            all_phones.add(contact_number)
        
        # Extract from PropertyShark data
        ps_data = state.get("property_shark_ownership_data", {})
        if isinstance(ps_data, dict):
            # Extract from real owners
            real_owners = ps_data.get("real_owners", [])
            for owner in real_owners:
                if isinstance(owner, dict) and "phones" in owner:
                    all_phones.update(owner.get("phones", []))
        
        # Extract from person search results
        person_data = state.get("person_search_results", {})
        if isinstance(person_data, dict):
            for person_id, person_info in person_data.items():
                if isinstance(person_info, dict) and "phones" in person_info:
                    all_phones.update(person_info.get("phones", []))
        
        # Extract from company registry data
        company_data = state.get("company_registry_data", {})
        if isinstance(company_data, dict) and "contact_info" in company_data:
            contact_info = company_data.get("contact_info", {})
            if isinstance(contact_info, dict) and "phone" in contact_info:
                phone = contact_info.get("phone")
                if phone:
                    all_phones.add(phone)
        
        # Clean phone numbers
        cleaned_phones = [self._clean_phone_number(phone) for phone in all_phones if phone]
        return [phone for phone in cleaned_phones if phone]  # Remove empty strings
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone numbers."""
        # If it's already a string like "Not available", return empty string
        if not phone or phone == "Not available":
            return ""
            
        # Remove non-digit characters
        digits_only = ''.join(filter(str.isdigit, phone))
        
        # Format US numbers as needed
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        elif len(digits_only) > 8:  # Assume it's a valid number with country code
            return f"+{digits_only}"
        
        return ""  # Return empty string for invalid numbers
    
    def _validate_phones(self, phone_numbers: List[str]) -> Dict[str, List]:
        """Validate phone numbers using Twilio API."""
        valid_phones = []
        invalid_phones = []
        
        # Create event loop for async calls
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Create tasks for each phone number
            tasks = [verify_phone_number(phone) for phone in phone_numbers]
            results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            
            # Process results
            for phone, result in zip(phone_numbers, results):
                if isinstance(result, Exception):
                    logger.error(f"Error validating {phone}: {str(result)}")
                    invalid_phones.append(phone)
                elif result.get("valid", False):
                    valid_phones.append({
                        "number": phone,
                        "formatted": result.get("national_format", phone),
                        "country_code": result.get("country_code", "unknown")
                    })
                else:
                    invalid_phones.append(phone)
                    
            return {
                "valid": valid_phones,
                "invalid": invalid_phones
            }
        
        finally:
            loop.close()
    
    def _determine_primary_phone(self, validation_results: Dict[str, List], state: PropertyResearchState) -> Dict[str, Any]:
        """Determine the primary (most reliable) phone number."""
        valid_phones = validation_results["valid"]
        
        if not valid_phones:
            return None
        
        # If we only have one valid phone, that's our primary
        if len(valid_phones) == 1:
            return valid_phones[0]
        
        # First, check if the contact_number from analyzer is among valid phones
        contact_number = state.get("contact_number")
        if contact_number and contact_number != "Not available":
            contact_number_clean = self._clean_phone_number(contact_number)
            for phone in valid_phones:
                if phone["number"] == contact_number_clean:
                    return phone
        
        # Prioritize US phone numbers
        us_phones = [p for p in valid_phones if p.get("country_code") == "US"]
        if us_phones:
            return us_phones[0]
        
        # If no prioritization criteria met, return the first valid phone
        return valid_phones[0]
