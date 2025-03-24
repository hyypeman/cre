import os
from twilio.rest import Client

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]


async def verify_phone_number(phone_number: str):
    """Verify a phone number."""
    try:
        client = Client(account_sid, auth_token)
        lookup_result = client.lookups.v2.phone_numbers(phone_number).fetch()

        # Extract only the needed information instead of returning the whole object
        result = {
            "status": "success",
            "phone_number": lookup_result.phone_number,
            "country_code": lookup_result.country_code,
            "national_format": lookup_result.national_format,
            "valid": lookup_result.valid,
        }
        return result
    except Exception as e:
        return {"status": "error", "message": str(e), "valid": False}
