import requests
import os
import tempfile
import re
import random
import csv
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from pathlib import Path
from reducto import Reducto

# Load environment variables
load_dotenv()

REDUCTO_API_KEY = os.environ.get("REDUCTO_API_KEY")

# Schema definitions
DEED_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "description": "The type of document (e.g., Deed, Assignment of Mortgage, Bargain and Sale Deed)"
        },
        "property_address": {
            "type": "string",
            "description": "The street address of the property"
        },
        "block_lot": {
            "type": "object",
            "properties": {
                "block": {
                    "type": "string",
                    "description": "The block number of the property"
                },
                "lot": {
                    "type": "string",
                    "description": "The lot number of the property"
                }
            }
        },
        "grantor": {
            "type": "string",
            "description": "The person or entity transferring rights (seller, assignor)"
        },
        "grantee": {
            "type": "string",
            "description": "The person or entity receiving rights (buyer, assignee)"
        },
        "transaction_date": {
            "type": "string",
            "description": "The date the document was executed"
        },
        "recording_date": {
            "type": "string",
            "description": "The date the document was recorded"
        },
        "current_owner": {
            "type": "string",
            "description": "Explicitly stated current owner of the property"
        },
        "owner_address": {
            "type": "string",
            "description": "Address of the owner/party if different from property address"
        },
        "party_contact_information": {
            "type": "object",
            "properties": {
                "party_name": {
                    "type": "string",
                    "description": "Name of relevant party"
                },
                "party_address": {
                    "type": "string",
                    "description": "Contact address for party"
                }
            }
        },
        "reel_page": {
            "type": "string",
            "description": "The reel and page numbers where the document is recorded"
        }
    },
    "required": ["property_address", "document_type"]
}

MORTGAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "property_address": {
            "type": "string",
            "description": "The street address of the property"
        },
        "owner_name": {
            "type": "string",
            "description": "The name of the property owner/mortgagor"
        },
        "owner_address": {
            "type": "string",
            "description": "The mailing address of the owner"
        },
        "block": {
            "type": "string", 
            "description": "The block number of the property"
        },
        "lot": {
            "type": "string",
            "description": "The lot number of the property"
        },
        "document_type": {
            "type": "string",
            "description": "Type of document (e.g., MORTGAGE, DEED, ASSIGNMENT)"
        },
        "document_date": {
            "type": "string",
            "description": "The date of the document"
        },
        "prior_owner": {
            "type": "string",
            "description": "Previous owner in case of transfers/assignments"
        },
        "entity_type": {
            "type": "string",
            "description": "Type of entity owning property (LLC, Corp, Individual, etc.)"
        },
        "principal_name": {
            "type": "string",
            "description": "Name of principal/manager/signatory of owning entity"
        }
    },
    "required": ["property_address", "owner_name"]
}

def extract_from_deed_pdf(client: Reducto, job_id: str) -> Dict[str, Any]:
    """
    Extract structured data from a deed PDF using Reducto.
    
    Args:
        client: Reducto client instance
        job_id: The Reducto job ID for the document
        
    Returns:
        Dictionary containing extracted deed information
    """
    result = client.extract.run(
        document_url=f'jobid://{job_id}',
        schema=DEED_SCHEMA
    )
    return result.result[0]

def extract_from_mortgage_pdf(client: Reducto, job_id: str) -> Dict[str, Any]:
    """
    Extract structured data from a mortgage PDF using Reducto.
    
    Args:
        client: Reducto client instance
        job_id: The Reducto job ID for the document
        
    Returns:
        Dictionary containing extracted mortgage information
    """
    result = client.extract.run(
        document_url=f'jobid://{job_id}',
        schema=MORTGAGE_SCHEMA
    )
    return result.result[0]

def extract_text_from_pdf(files: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process multiple PDF documents and extract structured data.

    Args:
        files: A dictionary containing a list of files with document_filename and document_type

    Returns:
        List of dictionaries containing the extracted data or error information
    """
    try:
        if not isinstance(files, dict) or 'files' not in files:
            return [{"error": "Input must be a dictionary with a 'files' key"}]
        
        client = Reducto(api_key=REDUCTO_API_KEY)
        parsed_data = []
        
        for file in files['files']:
            try:
                if 'document_filename' not in file:
                    parsed_data.append({
                        "error": f"Missing document_filename in file entry",
                        "file_entry": file
                    })
                    continue
                    
                pdf_filename = file['document_filename']
                if not os.path.exists(pdf_filename):
                    parsed_data.append({
                        "error": f"File not found: {pdf_filename}",
                        "document_filename": pdf_filename
                    })
                    continue
                
                # Get document_type with a default of None
                document_type = file.get('document_type')
                
                upload = client.upload(file=Path(pdf_filename))
                result = client.parse.run(document_url=upload)
                job_id = result.job_id
        
                if document_type == 'deed':
                    extracted_data = extract_from_deed_pdf(client, job_id)
                elif document_type == 'mortgage':
                    extracted_data = extract_from_mortgage_pdf(client, job_id)
                else:
                    parsed_data.append({
                        "error": f"Unknown or missing document_type: {document_type}",
                        "document_filename": pdf_filename
                    })
                    continue
                    
                extracted_data['document_text'] = '\n'.join([r.content for r in result.result.chunks])
                extracted_data['document_filename'] = pdf_filename
                
                if 'document_info' in file:
                    extracted_data['document_info'] = file['document_info']
                
                parsed_data.append(extracted_data)
            
            except Exception as e:
                # Handle file-specific errors and continue processing other files
                parsed_data.append({
                    "error": f"Error processing file: {str(e)}",
                    "document_filename": file.get('document_filename', 'unknown')
                })
        
        return parsed_data

    except Exception as e:
        # Log the error for debugging
        print(f"Error processing files: {str(e)}")
        # Return a dictionary with error information
        return [{"error": f"Error processing files: {str(e)}"}]

# Example usage
if __name__ == "__main__":
    
    # Check if documents directory exists
    if not os.path.exists('documents'):
        print("Documents directory not found")
        exit(1)
        
    # Fetch all existing documents that were scraped from ACRIS in previous step
    all_files = [os.path.join('documents', f) for f in os.listdir('documents') 
                if os.path.isfile(os.path.join('documents', f))]
    
    if not all_files:
        print("No files found in documents directory")
        exit(1)
    
    # Pick random file and run data extraction on it
    random_file = random.choice(all_files)

    doc_type = 'deed' if 'FT_' in random_file else 'mortgage'
    
    pdf_data = extract_text_from_pdf({
        'files': [{
            'document_filename': random_file,
            'document_type': doc_type
        }]
    })
    
    if pdf_data:
        print(json.dumps(pdf_data, indent=4))
    else:
        print("No data extracted")
