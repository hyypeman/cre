# Property Ownership Research Tool

An automated tool for researching property ownership information using public databases and business registries.

## Overview

This tool automates the process of researching property ownership by:

1. Searching NYC's ZoLa (Zoning & Land Use) database for property information
2. Searching ACRIS (Automated City Register Information System) for property documents
3. Extracting information from property documents (deeds, mortgages, etc.)
4. Searching PropertyShark for additional property ownership information
5. For LLC owners, searching OpenCorporates for company information
6. Analyzing all collected data to generate a comprehensive ownership report

## Features

- **ZoLa Integration**: Automatically searches ZoLa and extracts ownership information
- **ACRIS Integration**: Searches ACRIS for property documents and ownership history
- **Document Processing**: Extracts text and entities from property documents
- **PropertyShark Integration**: Searches PropertyShark for additional ownership information
- **OpenCorporates Integration**: Searches OpenCorporates for company information when owners are LLCs
- **LangGraph Workflow**: Uses LangGraph to orchestrate the research process
- **AI Analysis**: Uses GPT-4o to analyze collected data and generate comprehensive reports

## Workflow

The tool follows this workflow:

1. **User Input**: Address is provided.
2. **Initial Scraping**:
   - ZoLa runs independently.
   - ACRIS runs first, then Document Processor (which uses ACRIS data).
3. **Conditional Check** (LLM-based):
   - If ZoLa + ACRIS (with Document Processor) find a name or LLC, proceed.
   - If not, call PropertyShark.
4. **LLC Handling**:
   - If an LLC is found, scrape OpenCorporates to extract a name.
   - Otherwise, proceed to search the name.
5. **Name Search**:
   - Look up the extracted name in SkipGenie, TruePeopleSearch, and possibly ZoomInfo (future implementation).
6. **Output**: Generate a spreadsheet with the results.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
playwright install firefox
```

4. Set up environment variables by creating a `.env` file:
```
# Capsolver API key for reCAPTCHA solving
CAPSOLVER_API_KEY=your_capsolver_api_key

# Optional settings
HEADLESS=false  # Set to true to run browser in headless mode
TIMEOUT=30000  # Timeout in milliseconds for page operations

# API keys for LangChain and OpenAI
LANGCHAIN_API_KEY=your_langchain_api_key
LANGCHAIN_TRACING_V2=true
OPENAI_API_KEY=your_openai_api_key

# Credentials for skipgenie.com
SKIP_EMAIL=your_email
SKIP_PASSWORD=your_password

# Credentials for PropertyShark
PROPERTY_SHARK_EMAIL=your_email
PROPERTY_SHARK_PASSWORD=your_password
PROPERTY_SHARK_IMAP_PASSWORD=your_imap_password

# Credentials for OpenCorporates
OPENCORPORATES_USERNAME=your_username
OPENCORPORATES_PASSWORD=your_password
```

## Usage

Run the main script and enter a property address:

```bash
python src/main.py
```

Example input:
```
Enter property address to research: 798 LEXINGTON AVENUE, New York, NY
```

The tool will:
1. Search ZoLa for property information
2. Search ACRIS for property documents
3. Process any documents found
4. Search PropertyShark for additional ownership information if needed
5. Search OpenCorporates for company information if the owner is an LLC
6. Generate a comprehensive ownership report

## Components

- **main.py**: Main entry point and LangGraph workflow
- **nodes/**: Node modules for the LangGraph workflow
  - **initializer_node.py**: Initializes the research process
  - **zola_node.py**: Searches ZoLa for property information
  - **acris_node.py**: Searches ACRIS for property documents
  - **document_processor_node.py**: Processes property documents
  - **property_shark_node.py**: Searches PropertyShark for ownership information
  - **opencorporates_node.py**: Searches OpenCorporates for company information
  - **analyzer_node.py**: Analyzes collected data and generates reports
- **scrapers/**: Modules for scraping data from various sources
  - **zola_scraper.py**: Module for searching ZoLa
  - **acris_scraper.py**: Module for searching ACRIS
  - **document_processor.py**: Module for processing property documents
  - **property_shark_scraper.py**: Module for searching PropertyShark
  - **opencorporates_scraper.py**: Module for searching OpenCorporates

## Example Research Scenarios

### Scenario 1: 798 Lexington Ave, Manhattan

Goal: Identify the owner of the property at 798 Lexington Ave, Manhattan.

Steps:
1. Search ZoLa to find basic ownership information
2. Search ACRIS to find deed records and ownership history
3. Process documents to extract detailed ownership information
4. If owner is an LLC, search OpenCorporates for company information
5. Generate a comprehensive ownership report

### Scenario 2: 28 W 23rd Street, New York

Goal: Identify the owner of 28 W 23rd Street and retrieve their contact information.

Steps:
1. Search ZoLa to find that the owner is Joseph Rosen Trust
2. Search ACRIS to find that Jonathan P. Rosen is listed as Party One
3. Process documents to confirm 40 E 69th Street as his address
4. Search PropertyShark for additional ownership information
5. Generate a comprehensive ownership report

## License

MIT License
