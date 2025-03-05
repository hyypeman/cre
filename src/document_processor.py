import requests
import os
import tempfile
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def extract_text_from_pdf(pdf_url: str) -> Dict[str, Any]:
    """
    Download and extract text from a PDF document.

    Args:
        pdf_url (str): The URL of the PDF document to process

    Returns:
        Dict[str, Any]: A dictionary containing the extracted text and metadata
    """
    print(f"Processing PDF document: {pdf_url}")

    # Initialize result dictionary
    result = {"url": pdf_url, "text": "", "metadata": {}, "entities": []}

    try:
        # In a real implementation, we would:
        # 1. Download the PDF
        # 2. Use a library like PyPDF2, pdfplumber, or pytesseract to extract text
        # 3. Process the text to extract entities

        # Simulate PDF processing
        # This is a placeholder for actual PDF processing code

        # Simulate downloading the PDF
        print(f"Downloading PDF from {pdf_url}")

        # Simulate text extraction based on the URL
        if "deed" in pdf_url.lower():
            result["text"] = """
            THIS INDENTURE, made the 15th day of March, 2020
            
            BETWEEN
            
            NIKKI REALTY LLC, a New York limited liability company with an address at 
            40 East 69th Street, Suite 5B, New York, NY 10021
            party of the first part, and
            
            798 LEXINGTON AVENUE HOLDINGS LLC, a New York limited liability company with an address at
            40 East 69th Street, Suite 5B, New York, NY 10021
            party of the second part,
            
            WITNESSETH, that the party of the first part, in consideration of Ten Dollars and other valuable 
            consideration paid by the party of the second part, does hereby grant and release unto the party 
            of the second part, the heirs or successors and assigns of the party of the second part forever,
            
            ALL that certain plot, piece or parcel of land, with the buildings and improvements thereon erected, 
            situate, lying and being in the Borough of Manhattan, County of New York, City and State of New York, 
            known as 798 Lexington Avenue, New York, NY.
            
            Block: 1396
            Lot: 157
            """

            result["metadata"] = {
                "document_type": "DEED",
                "document_date": "2020-03-15",
                "recording_date": "2020-03-20",
                "document_id": "2020000123456",
            }

            result["entities"] = [
                {
                    "type": "GRANTOR",
                    "name": "NIKKI REALTY LLC",
                    "address": "40 East 69th Street, Suite 5B, New York, NY 10021",
                },
                {
                    "type": "GRANTEE",
                    "name": "798 LEXINGTON AVENUE HOLDINGS LLC",
                    "address": "40 East 69th Street, Suite 5B, New York, NY 10021",
                },
                {
                    "type": "PROPERTY",
                    "address": "798 Lexington Avenue, New York, NY",
                    "block": "1396",
                    "lot": "157",
                },
            ]

        elif "mortgage" in pdf_url.lower():
            result["text"] = """
            MORTGAGE NOTE
            
            $2,500,000.00                                                                  New York, NY
                                                                                          April 1, 2020
            
            FOR VALUE RECEIVED, 798 LEXINGTON AVENUE HOLDINGS LLC, a New York limited liability company 
            with an address at 40 East 69th Street, Suite 5B, New York, NY 10021 ("Borrower"), promises 
            to pay to the order of FIRST NATIONAL BANK ("Lender"), the principal sum of TWO MILLION FIVE 
            HUNDRED THOUSAND AND 00/100 DOLLARS ($2,500,000.00), with interest on the unpaid principal 
            balance from the date of this Note, until paid, at the rate of 4.25% per annum.
            
            Property Address: 798 Lexington Avenue, New York, NY
            Block: 1396
            Lot: 157
            """

            result["metadata"] = {
                "document_type": "MORTGAGE",
                "document_date": "2020-04-01",
                "recording_date": "2020-04-10",
                "document_id": "2020000789012",
                "loan_amount": "$2,500,000.00",
                "interest_rate": "4.25%",
            }

            result["entities"] = [
                {
                    "type": "BORROWER",
                    "name": "798 LEXINGTON AVENUE HOLDINGS LLC",
                    "address": "40 East 69th Street, Suite 5B, New York, NY 10021",
                },
                {"type": "LENDER", "name": "FIRST NATIONAL BANK", "address": "Unknown"},
                {
                    "type": "PROPERTY",
                    "address": "798 Lexington Avenue, New York, NY",
                    "block": "1396",
                    "lot": "157",
                },
            ]

        else:
            # Generic document
            result["text"] = f"This is a simulated document for {pdf_url}"
            result["metadata"] = {
                "document_type": "UNKNOWN",
                "document_date": "Unknown",
                "recording_date": "Unknown",
                "document_id": "Unknown",
            }

    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        result["error"] = str(e)

    return result


def extract_entities_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extract named entities from text.

    Args:
        text (str): The text to process

    Returns:
        List[Dict[str, str]]: A list of extracted entities
    """
    entities = []

    # Look for people or companies
    name_patterns = [
        r"([A-Z][a-z]+ [A-Z][a-z]+)",  # Person names
        r"([A-Z][A-Z\s]+(?:LLC|CORP|INC|TRUST))",  # Company names
    ]

    for pattern in name_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            entities.append(
                {
                    "type": "ORGANIZATION"
                    if any(x in match for x in ["LLC", "CORP", "INC", "TRUST"])
                    else "PERSON",
                    "name": match,
                    "context": text[
                        max(0, text.find(match) - 50) : min(
                            len(text), text.find(match) + len(match) + 50
                        )
                    ],
                }
            )

    # Look for addresses
    address_pattern = r"(\d+\s+[A-Za-z]+\s+(?:Street|Avenue|Road|Drive|Lane|Place|Blvd|Boulevard|Ave|St|Rd|Dr),\s+[A-Za-z\s]+,\s+[A-Z]{2}\s+\d{5})"
    matches = re.findall(address_pattern, text)
    for match in matches:
        entities.append(
            {
                "type": "ADDRESS",
                "value": match,
                "context": text[
                    max(0, text.find(match) - 50) : min(
                        len(text), text.find(match) + len(match) + 50
                    )
                ],
            }
        )

    # Look for dollar amounts
    money_pattern = r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"
    matches = re.findall(money_pattern, text)
    for match in matches:
        entities.append(
            {
                "type": "MONEY",
                "value": f"${match}",
                "context": text[
                    max(0, text.find(match) - 50) : min(
                        len(text), text.find(match) + len(match) + 50
                    )
                ],
            }
        )

    return entities


# Example usage
if __name__ == "__main__":
    test_url = "https://example.com/documents/deed_123456.pdf"
    document_info = extract_text_from_pdf(test_url)
    print("Document Text:")
    print(document_info["text"])
    print("\nMetadata:")
    for key, value in document_info["metadata"].items():
        print(f"{key}: {value}")
    print("\nEntities:")
    for entity in document_info["entities"]:
        print(f"{entity['type']}: {entity.get('name', entity.get('value', ''))}")
