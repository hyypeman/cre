import requests
import os
import random
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path
from reducto import Reducto

# Load environment variables
load_dotenv()

REDUCTO_API_KEY = os.environ.get("REDUCTO_API_KEY")

# Schema definitions
SCHEMA = {
    "type": "object",
    "properties": {
        "property_address": {
            "type": "string",
            "description": "The street address of the property"
        },
        "entity_owner": {
            "type": "string",
            "description": "The entity that owns the property (LLC, corporation, partnership, etc.)"
        },
        "individual_owners": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of individual behind the entity"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title or role of the individual (e.g., Manager, Member, President)"
                    }
                }
            },
            "description": "Individual persons behind the entity owner"
        },
        "ownership_evidence": {
            "type": "string",
            "description": "Evidence or context from the document linking individual to entity ownership"
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
        }
    },
    "required": ["property_address", "entity_owner"]
}

def extract_schema_from_pdf(client: Reducto, job_id: str) -> Dict[str, Any]:
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
        schema=SCHEMA
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
                
                # parse PDF document via Reducto API
                upload = client.upload(file=Path(pdf_filename))
                result = client.parse.run(document_url=upload)
                job_id = result.job_id
                
                # extract data points from parsed PDF document
                extracted_data = extract_schema_from_pdf(client, job_id)
                
                # add full document text and document information
                # which might be useful for debugging in later step
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
