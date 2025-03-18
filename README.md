# Property Ownership Research Tool

An automated tool for researching property ownership information using public databases and social media.

## Overview

This tool automates the process of researching property ownership by:

1. Searching NYC's ZoLa (Zoning & Land Use) database for property information
2. Searching ACRIS (Automated City Register Information System) for property documents
3. Extracting information from property documents (deeds, mortgages, etc.)
4. Searching social media and business databases for owner information
5. Analyzing all collected data to generate a comprehensive ownership report

## Features

- **ZoLa Integration**: Automatically searches ZoLa and extracts ownership information
- **ACRIS Integration**: Searches ACRIS for property documents and ownership history
- **Document Processing**: Extracts text and entities from property documents
- **Social Media Search**: Finds information about property owners on social media and business databases
- **LangGraph Workflow**: Uses LangGraph to orchestrate the research process
- **AI Analysis**: Uses GPT-4o to analyze collected data and generate comprehensive reports

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

# Credentials for propertyshark.com
PROPERTY_SHARK_EMAIL=
PROPERTY_SHARK_PASSWORD=
PROPERTY_SHARK_IMAP_PASSWORD=

# Credentials for skipgenie.com
SKIP_EMAIL=
SKIP_PASSWORD=
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
4. Search social media for owner information
5. Generate a comprehensive ownership report

## Components

- **main.py**: Main entry point and LangGraph workflow
- **zola_scraper.py**: Module for searching ZoLa
- **acris_scraper.py**: Module for searching ACRIS
- **document_processor.py**: Module for processing property documents
- **social_media_search.py**: Module for searching social media and business databases

## Example Research Scenarios

### Scenario 1: 798 Lexington Ave, Manhattan

Goal: Identify the owner of the property at 798 Lexington Ave, Manhattan.

Steps:
1. Search ZoLa to find basic ownership information
2. Search ACRIS to find deed records and ownership history
3. Process documents to extract detailed ownership information
4. Search social media to find additional information about the owner
5. Generate a comprehensive ownership report

### Scenario 2: 28 W 23rd Street, New York

Goal: Identify the owner of 28 W 23rd Street and retrieve their contact information.

Steps:
1. Search ZoLa to find that the owner is Joseph Rosen Trust
2. Search ACRIS to find that Jonathan P. Rosen is listed as Party One
3. Process documents to confirm 40 E 69th Street as his address
4. Search social media to find contact information and business associations
5. Generate a comprehensive ownership report

## License

MIT License
