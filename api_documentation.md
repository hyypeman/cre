# Property Research API Documentation

This document provides comprehensive documentation for the Property Research API, a RESTful service for researching property ownership information.

## Base URL

```
http://localhost:8000
```

## Authentication

The API currently does not require authentication.

## API Endpoints

### 1. Start Property Research

Initiates the property research process for one or more addresses.

**Endpoint:** `POST /api/research`

**Status Code:** `202 Accepted`

#### Request Body

| Field | Type | Description | Constraints |
|-------|------|-------------|------------|
| `addresses` | Array of strings | List of property addresses to research | Min: 1 address, Max: 10 addresses |

Example:
```json
{
  "addresses": [
    "798 LEXINGTON AVENUE, New York, NY",
    "123 Main St, New York, NY"
  ]
}
```

#### Response Body

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | String | Unique identifier for the research job |
| `status` | String | Current status of the job (pending, processing, completed, failed) |
| `created_at` | DateTime | When the job was created |
| `updated_at` | DateTime | When the job was last updated |
| `total_addresses` | Integer | Total number of addresses in the job |
| `completed_addresses` | Integer | Number of addresses that have been processed |
| `results` | Array | Results for each address |

Example:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2023-10-15T14:30:20.123456",
  "updated_at": "2023-10-15T14:30:20.123456",
  "total_addresses": 2,
  "completed_addresses": 0,
  "results": [
    {
      "address": "798 LEXINGTON AVENUE, New York, NY",
      "owner_name": null,
      "owner_type": null,
      "contact_number": null,
      "confidence": null,
      "errors": [],
      "completed": false
    },
    {
      "address": "123 Main St, New York, NY",
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

#### Error Responses

**400 Bad Request**
```json
{
  "detail": "All addresses must be non-empty strings"
}
```

**422 Unprocessable Entity**
```json
{
  "detail": [
    {
      "loc": ["body", "addresses"],
      "msg": "ensure this value has at least 1 items",
      "type": "value_error.list.min_items"
    }
  ]
}
```

### 2. Get Job Status

Retrieves the current status and results of a property research job.

**Endpoint:** `GET /api/research/{job_id}`

**Status Code:** `200 OK`

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | String | The unique identifier of the job |

#### Response Body

Same as the response for the Start Property Research endpoint, but with updated status and results as the job progresses.

Example (job in progress):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "created_at": "2023-10-15T14:30:20.123456",
  "updated_at": "2023-10-15T14:32:15.654321",
  "total_addresses": 2,
  "completed_addresses": 1,
  "results": [
    {
      "address": "798 LEXINGTON AVENUE, New York, NY",
      "owner_name": "LEXINGTON HOLDINGS LLC",
      "owner_type": "llc",
      "contact_number": "(212) 555-1234",
      "confidence": "high",
      "errors": [],
      "completed": true
    },
    {
      "address": "123 Main St, New York, NY",
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

Example (job completed):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2023-10-15T14:30:20.123456",
  "updated_at": "2023-10-15T14:35:10.987654",
  "total_addresses": 2,
  "completed_addresses": 2,
  "results": [
    {
      "address": "798 LEXINGTON AVENUE, New York, NY",
      "owner_name": "LEXINGTON HOLDINGS LLC",
      "owner_type": "llc",
      "contact_number": "(212) 555-1234",
      "confidence": "high",
      "errors": [],
      "completed": true
    },
    {
      "address": "123 Main St, New York, NY",
      "owner_name": "John Doe",
      "owner_type": "individual",
      "contact_number": "(917) 555-5678",
      "confidence": "medium",
      "errors": [],
      "completed": true
    }
  ]
}
```

#### Error Responses

**404 Not Found**
```json
{
  "detail": "Job with ID 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

### 3. Health Check

Checks the health status of the API service.

**Endpoint:** `GET /api/health`

**Status Code:** `200 OK`

#### Response Body

| Field | Type | Description |
|-------|------|-------------|
| `status` | String | Health status of the service |
| `timestamp` | DateTime | Current server time |
| `mongodb_connected` | Boolean | Whether the service is connected to MongoDB |

Example:
```json
{
  "status": "healthy",
  "timestamp": "2023-10-15T14:45:30.123456",
  "mongodb_connected": true
}
```

## Data Models

### Job Status

Enum representing the possible states of a research job:

- `pending`: Job has been created but processing hasn't started
- `processing`: Job is currently being processed
- `completed`: Job has been successfully completed
- `failed`: Job processing failed

### Address Result

Structure containing the research results for a single address:

| Field | Type | Description |
|-------|------|-------------|
| `address` | String | The property address |
| `owner_name` | String | Name of the property owner |
| `owner_type` | String | Type of owner (individual, llc, corporation, unknown) |
| `contact_number` | String | Contact phone number for the owner |
| `confidence` | String | Confidence level in the ownership data (high, medium, low) |
| `errors` | Array of strings | Any errors encountered while processing this address |
| `completed` | Boolean | Whether processing for this address is complete |

## Environment Variables

The API service can be configured using the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection URL | "" |
| `ENABLE_MONGODB` | Enable MongoDB persistence | "false" |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | "*" |
| `PROCESSING_DELAY` | Delay between processing addresses (seconds) | 0.5 |
| `MAX_ADDRESSES` | Maximum number of addresses per request | 10 |

## Rate Limiting

Currently, there are no rate limits implemented. However, there is a limit of 10 addresses per request, which can be configured using the `MAX_ADDRESSES` environment variable.

## Error Handling

The API uses standard HTTP status codes to indicate the success or failure of requests:

- `200`: Successful GET request
- `202`: Request accepted for processing
- `400`: Bad request (e.g., invalid input)
- `404`: Resource not found
- `422`: Validation error
- `500`: Server error

Detailed error messages are provided in the response body when applicable.

## Workflow

1. Submit a list of addresses using the `POST /api/research` endpoint
2. Receive a job ID in the response
3. Periodically poll the `GET /api/research/{job_id}` endpoint to check the job status and retrieve results
4. When the job status is `completed`, all results are available

## Examples

### Example 1: Starting a research job

Request:
```http
POST /api/research HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "addresses": ["798 LEXINGTON AVENUE, New York, NY"]
}
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2023-10-15T14:30:20.123456",
  "updated_at": "2023-10-15T14:30:20.123456",
  "total_addresses": 1,
  "completed_addresses": 0,
  "results": [
    {
      "address": "798 LEXINGTON AVENUE, New York, NY",
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

### Example 2: Checking job status

Request:
```http
GET /api/research/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: localhost:8000
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2023-10-15T14:30:20.123456",
  "updated_at": "2023-10-15T14:35:10.987654",
  "total_addresses": 1,
  "completed_addresses": 1,
  "results": [
    {
      "address": "798 LEXINGTON AVENUE, New York, NY",
      "owner_name": "LEXINGTON HOLDINGS LLC",
      "owner_type": "llc",
      "contact_number": "(212) 555-1234",
      "confidence": "high",
      "errors": [],
      "completed": true
    }
  ]
}
```

### Example 3: Health check

Request:
```http
GET /api/health HTTP/1.1
Host: localhost:8000
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2023-10-15T14:45:30.123456",
  "mongodb_connected": true
}
``` 