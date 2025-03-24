import logging
import asyncio
from typing import List, Dict, Optional, Any
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
        logger.info("📱 Analyzing phone numbers")
        
        try:
            all_phones = self._extract_phones(state)
            
            if not all_phones:
                return {
                    "phone_analysis": {"valid_phones": [], "invalid_phones": []}
                }
            
            validation_results = self._validate_phones(all_phones)
            
            return {
                "phone_analysis": validation_results
            }
            
        except Exception as e:
            logger.error(f"Twilio error: {str(e)}")
            return {
                "errors": [f"Twilio error: {str(e)}"],
                "phone_analysis": {"valid_phones": [], "invalid_phones": []}
            }
    
    def _extract_phones(self, state: PropertyResearchState) -> List[str]:
        """Extract all phone numbers from various data sources in the state."""
        all_phones = set()
        
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
        
        # Filter out empty or None values
        return [phone for phone in all_phones if phone]
    
    def _validate_phones(self, phone_numbers: List[str]) -> Dict[str, List]:
        """Validate phone numbers using Twilio API."""
        valid_phones = []
        invalid_phones = []
        
        for phone in phone_numbers:
            try:
                async def run_verification():
                    return await verify_phone_number(phone)
                
                try:
                    result = asyncio.run(run_verification())
                except RuntimeError:
                    current_loop = asyncio.get_event_loop()
                    result = current_loop.run_until_complete(run_verification())
                
                if result.get("valid", False):
                    valid_phones.append({
                        "number": phone,
                        "formatted": result.get("national_format", phone),
                        "country_code": result.get("country_code", "unknown")
                    })
                else:
                    invalid_phones.append(phone)
            except Exception as e:
                logger.error(f"Error validating {phone}: {str(e)}")
                invalid_phones.append(phone)
                
        return {"valid": valid_phones, "invalid": invalid_phones}
