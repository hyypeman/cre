# Property Research API

A FastAPI application that serves a LangGraph-based property research workflow as a REST API.

## Features

- REST API for property research
- Asynchronous processing of multiple addresses
- Job tracking with unique IDs
- Optional MongoDB persistence
- Docker and Docker Compose support
- CORS configuration
- Environment variable configuration

## Requirements

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- MongoDB (optional, for persistence)

## Installation

### Local Development

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd property-research-api
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   uvicorn application:app --reload
   ```

5. Access the API documentation at http://localhost:8000/docs

### Docker Deployment

1. Build and run using Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. Access the API documentation at http://localhost:8000/docs

## API Endpoints

### Start Property Research

```
POST /api/research
```

Request body:
```json
{
  "addresses": [
    "123 Main St, New York, NY",
    "456 Park Ave, New York, NY"
  ]
}
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2023-04-01T12:00:00.000Z",
  "updated_at": "2023-04-01T12:00:00.000Z",
  "total_addresses": 2,
  "completed_addresses": 0,
  "results": [
    {
      "address": "123 Main St, New York, NY",
      "owner_name": null,
      "owner_type": null,
      "contact_number": null,
      "confidence": null,
      "errors": [],
      "completed": false
    },
    {
      "address": "456 Park Ave, New York, NY",
      "owner_name": null,
      "owner_type": null,
      "contact_number": null,
      "confidence": null,
      "errors": [],
      "completed": false
    }
  ]
}
```

### Get Job Status

```
GET /api/research/{job_id}
```

Response: Same as above, but with updated status and results.

### Health Check

```
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2023-04-01T12:00:00.000Z",
  "mongodb_connected": true
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection URL | "" |
| `ENABLE_MONGODB` | Enable MongoDB persistence | "false" |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | "*" |
| `PROCESSING_DELAY` | Delay between processing addresses (seconds) | 0.5 |
| `MAX_ADDRESSES` | Maximum number of addresses per request | 10 |

## Development

### Project Structure

```
property-research-api/
├── application.py        # FastAPI application
├── src/                  # Property research implementation
│   ├── main.py           # LangGraph workflow
│   ├── state.py          # State definitions
│   └── nodes/            # Workflow nodes
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
└── requirements.txt      # Python dependencies
```

## License

[MIT License](LICENSE)
