import asyncio
import os
import uuid
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union

import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from motor.motor_asyncio import AsyncIOMotorClient
from src.main import PropertyResearchGraph

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("property-research-api")

# Environment variables
MONGODB_URL = os.getenv("MONGODB_URL", "")
ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "false").lower() == "true"
PROCESSING_DELAY = float(os.getenv("PROCESSING_DELAY", "0.5"))  # Delay between addresses in seconds
MAX_ADDRESSES = int(os.getenv("MAX_ADDRESSES", "10"))  # Maximum number of addresses per request

# Initialize FastAPI app
app = FastAPI(
    title="Property Research API",
    description="API for researching property ownership information",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MongoDB client if enabled
mongodb_client = None
db = None

if ENABLE_MONGODB:
    try:
        mongodb_client = AsyncIOMotorClient(MONGODB_URL)
        db = mongodb_client.property_research
        logger.info("MongoDB connection established")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        logger.warning("Running without MongoDB persistence")


# Pydantic models
class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AddressRequest(BaseModel):
    addresses: List[str] = Field(..., min_items=1, max_items=MAX_ADDRESSES)

    @validator("addresses")
    def validate_addresses(cls, addresses):
        if not all(addr.strip() for addr in addresses):
            raise ValueError("All addresses must be non-empty strings")
        return [addr.strip() for addr in addresses]


class AddressResult(BaseModel):
    address: str
    owner_name: Optional[str] = None
    owner_type: Optional[str] = None
    contact_number: Optional[str] = None
    confidence: Optional[str] = None
    errors: List[str] = []
    completed: bool = False


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    total_addresses: int
    completed_addresses: int
    results: List[AddressResult] = []


# In-memory job storage
jobs: Dict[str, JobResponse] = {}

# Initialize property research graph
graph = PropertyResearchGraph()
graph.compile()  # Compile the graph once at startup


async def save_job_to_mongodb(job: JobResponse):
    """Save job to MongoDB if enabled."""
    if not ENABLE_MONGODB or not db:
        return

    try:
        await db.jobs.update_one({"job_id": job.job_id}, {"$set": job.dict()}, upsert=True)
    except Exception as e:
        logger.error(f"Failed to save job to MongoDB: {e}")


async def get_job_from_mongodb(job_id: str) -> Optional[JobResponse]:
    """Get job from MongoDB if enabled."""
    if not ENABLE_MONGODB or not db:
        return None

    try:
        job_data = await db.jobs.find_one({"job_id": job_id})
        if job_data:
            return JobResponse(**job_data)
    except Exception as e:
        logger.error(f"Failed to get job from MongoDB: {e}")

    return None


async def process_address(job_id: str, address: str, index: int):
    """Process a single address and update the job status."""
    job = jobs[job_id]

    # Update status for this address
    job.results[index].address = address
    job.status = JobStatus.PROCESSING
    job.updated_at = datetime.now()

    try:
        # Run the property research graph for this address
        logger.info(f"Processing address: {address}")
        result = graph.run(address)

        # Update the result
        job.results[index].owner_name = result.get("owner_name")
        job.results[index].owner_type = result.get("owner_type")
        job.results[index].contact_number = result.get("contact_number")
        job.results[index].confidence = result.get("confidence")
        job.results[index].errors = result.get("errors", [])
        job.results[index].completed = True
        job.completed_addresses += 1

        logger.info(f"Completed processing address: {address}")
    except Exception as e:
        logger.error(f"Error processing address {address}: {e}")
        job.results[index].errors = [f"Processing error: {str(e)}"]
        job.results[index].completed = True
        job.completed_addresses += 1

    # Update job status
    job.updated_at = datetime.now()
    if job.completed_addresses == job.total_addresses:
        job.status = JobStatus.COMPLETED

    # Save to MongoDB if enabled
    await save_job_to_mongodb(job)


async def process_addresses(job_id: str, addresses: List[str]):
    """Process multiple addresses sequentially with a delay between each."""
    try:
        for i, address in enumerate(addresses):
            await process_address(job_id, address, i)
            if i < len(addresses) - 1:  # Don't delay after the last address
                await asyncio.sleep(PROCESSING_DELAY)
    except Exception as e:
        logger.error(f"Error in background processing: {e}")
        job = jobs[job_id]
        job.status = JobStatus.FAILED
        job.updated_at = datetime.now()
        await save_job_to_mongodb(job)


@app.post("/api/research", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_research(request: AddressRequest, background_tasks: BackgroundTasks) -> JobResponse:
    """Start property research for a list of addresses."""
    job_id = str(uuid.uuid4())
    created_at = datetime.now()

    # Initialize results for each address
    results = [AddressResult(address=addr, completed=False) for addr in request.addresses]

    # Create job response
    job = JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=created_at,
        updated_at=created_at,
        total_addresses=len(request.addresses),
        completed_addresses=0,
        results=results,
    )

    # Store job in memory
    jobs[job_id] = job

    # Save to MongoDB if enabled
    await save_job_to_mongodb(job)

    # Start background processing
    background_tasks.add_task(process_addresses, job_id, request.addresses)

    return job


@app.get("/api/research/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str) -> JobResponse:
    """Get the status of a property research job."""
    # Try to get from in-memory cache first
    job = jobs.get(job_id)

    # If not in memory, try to get from MongoDB
    if not job:
        job = await get_job_from_mongodb(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with ID {job_id} not found"
        )

    return job


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mongodb_connected": ENABLE_MONGODB and db is not None,
    }


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Property Research API")
    # Additional startup tasks can be added here


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Property Research API")
    if mongodb_client:
        mongodb_client.close()


if __name__ == "__main__":
    uvicorn.run("application:app", host="0.0.0.0", port=8000, reload=True)
