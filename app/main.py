from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up: connecting to MongoDB")
    await connect_to_mongo()
    yield
    # Shutdown
    logger.info("Shutting down: closing MongoDB connection")
    await close_mongo_connection()

app = FastAPI(title="Crypto Info API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to Crypto Info API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
