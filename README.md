# Property Research System

## Overview

The Property Research System is an automated tool that aggregates property ownership information from multiple data sources. It uses a graph-based workflow to fetch, analyze, and consolidate property data, providing comprehensive ownership details for real estate properties.

## Features

- **Multi-source Data Collection**: Integrates with Zola, ACRIS, PropertyShark, and other data sources
- **Automated Document Processing**: Extracts ownership information from property documents
- **Entity Resolution**: Identifies owner types (individual vs. LLC) and resolves LLC ownership
- **REST API**: Provides endpoints for property research requests and status tracking
- **Asynchronous Processing**: Handles multiple property research requests in parallel
- **Persistent Storage**: Optionally stores results in MongoDB for future reference

## Project Structure

```
cre/
├── application.py            # FastAPI application server
├── run.py                    # Script to run the application directly
├── requirements.txt          # Python package dependencies
├── Dockerfile                # Container configuration
├── docker-compose.yml        # Multi-container deployment setup
├── api_documentation.md      # Detailed API documentation
├── .env                      # Environment variables configuration
├── .env.example              # Template for environment variables
├── src/                      # Core application code
│   ├── main.py               # Main workflow graph implementation
│   ├── state.py              # State management for the workflow
│   ├── nodes/                # Workflow nodes that perform specific tasks
│   │   ├── __init__.py       # Node exports
│   │   ├── acris_node.py     # ACRIS property records integration
│   │   ├── analyzer_node.py  # Data analysis and entity resolution
│   │   ├── document_processor_node.py  # Document text extraction
│   │   ├── initializer_node.py  # Workflow initialization
│   │   ├── opencorporates_node.py  # Company data integration
│   │   ├── property_shark_node.py  # PropertyShark integration
│   │   ├── skipgenie_node.py  # SkipGenie people search
│   │   ├── true_people_search_node.py  # TruePeopleSearch integration
│   │   └── zola_node.py      # NYC Planning Zola integration
│   ├── scrapers/             # Web scraping implementations
│   │   ├── __init__.py       # Scraper exports
│   │   ├── acris_scraper.py  # ACRIS document retrieval
│   │   ├── document_processor.py  # Document text extraction
│   │   ├── opencorporates_scraper.py  # Company data scraping
│   │   ├── property_shark_scraper.py  # PropertyShark data scraping
│   │   └── zola_scraper.py   # NYC Zola data scraping
│   └── __init__.py           # Package exports
├── documents/                # Documents storage directory
├── results/                  # Results output directory
└── workflow_diagram.png      # Visual representation of the workflow
```

## Getting Started

### Prerequisites

- Python 3.11+
- MongoDB (optional, for result persistence)
- API keys for external services (see Environment Variables section)
- Git

### Local Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cre
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory with the necessary environment variables (see the Environment Variables section below).

5. **Start the API server**
   ```bash
   uvicorn application:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Access the API documentation**
   Open your browser and navigate to [http://localhost:8000/docs](http://localhost:8000/docs)

### Using Docker

1. **Build and start the Docker containers**
   ```bash
   docker-compose up -d
   ```

2. **Access the API**
   The API will be available at [http://localhost:8000](http://localhost:8000)

## Deployment on Heroku

### Prerequisites
- Heroku CLI installed
- Heroku account
- Git

### Steps to Deploy

1. **Login to Heroku**
   ```bash
   heroku login
   ```

2. **Create a new Heroku app**
   ```bash
   heroku create your-app-name
   ```

3. **Set up MongoDB add-on**
   ```bash
   heroku addons:create mongolab:sandbox
   ```

4. **Configure environment variables**
   ```bash
   heroku config:set ENABLE_MONGODB=true
   heroku config:set PROCESSING_DELAY=0.5
   heroku config:set MAX_ADDRESSES=10
   heroku config:set CORS_ORIGINS=*
   # Add all other environment variables (see below)
   ```

5. **Deploy the application**
   ```bash
   git push heroku main
   ```

6. **Scale the dynos**
   ```bash
   heroku ps:scale web=1
   ```

7. **Open the application**
   ```bash
   heroku open
   ```

## Environment Variables

Create a `.env` file in the project root with the following variables:

### Core Configuration
```
# MongoDB Configuration (Optional)
MONGODB_URL=mongodb://localhost:27017/
ENABLE_MONGODB=false

# API Configuration
PROCESSING_DELAY=0.5  # Delay between addresses in seconds
MAX_ADDRESSES=10  # Maximum number of addresses per request
CORS_ORIGINS=*  # Comma-separated list of allowed origins for CORS
```

### API Keys for External Services
```
# LangChain and OpenAI Configuration
LANGCHAIN_API_KEY=your_langchain_api_key
LANGCHAIN_TRACING_V2=true
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
REDUCTO_API_KEY=your_reducto_api_key

# CAPTCHA Solving
CAPSOLVER_API_KEY=your_capsolver_api_key

# Browser Automation
HEADLESS=false  # Set to true to run browser in headless mode
TIMEOUT=30000   # Browser timeout in milliseconds

# PropertyShark Credentials
PROPERTY_SHARK_EMAIL=your_email
PROPERTY_SHARK_PASSWORD=your_password
PROPERTY_SHARK_IMAP_PASSWORD=your_imap_password

# OpenCorporates Credentials
OPENCORPORATES_USERNAME=your_username
OPENCORPORATES_PASSWORD=your_password
```

## API Usage

### Start Property Research

**Endpoint**: `POST /api/research`

**Request Body**:
```json
{
  "addresses": [
    "123 Main St, New York, NY 10001",
    "456 Park Ave, New York, NY 10022"
  ]
}
```

**Response**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2023-09-25T14:30:45.123Z",
  "updated_at": "2023-09-25T14:30:45.123Z",
  "total_addresses": 2,
  "completed_addresses": 0,
  "results": []
}
```

### Check Job Status

**Endpoint**: `GET /api/research/{job_id}`

**Response**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2023-09-25T14:30:45.123Z",
  "updated_at": "2023-09-25T14:35:12.456Z",
  "total_addresses": 2,
  "completed_addresses": 2,
  "results": [
    {
      "address": "123 Main St, New York, NY 10001",
      "owner_name": "John Doe",
      "owner_type": "individual",
      "contact_number": "212-555-1234",
      "confidence": "high",
      "errors": [],
      "completed": true
    },
    {
      "address": "456 Park Ave, New York, NY 10022",
      "owner_name": "Acme Properties LLC",
      "owner_type": "llc",
      "contact_number": "212-555-5678",
      "confidence": "medium",
      "errors": [],
      "completed": true
    }
  ]
}
```

### Health Check

**Endpoint**: `GET /api/health`

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2023-09-25T14:30:45.123Z"
}
```

## Workflow Customization

The property research workflow is implemented as a graph and can be customized by modifying the `PropertyResearchGraph` class in `src/main.py`.

## Troubleshooting

1. **MongoDB Connection Issues**
   - Ensure MongoDB is running and accessible
   - Check if the MongoDB URL is correctly configured

2. **API Key Errors**
   - Verify all API keys are correctly set in the `.env` file
   - Ensure API keys have the necessary permissions

3. **Browser Automation Issues**
   - Set `HEADLESS=false` to see the browser in action for debugging
   - Increase `TIMEOUT` value if operations are timing out

4. **Deployment Issues on Heroku**
   - Check Heroku logs: `heroku logs --tail`
   - Ensure all environment variables are correctly set

## Contributing

Contributions to the Property Research System are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the [MIT License](LICENSE).
