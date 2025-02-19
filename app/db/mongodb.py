import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None

async def connect_to_mongo():
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    logger.info("Connected to MongoDB")



async def close_mongo_connection():
    if client:
        client.close()
        logger.info("Closed MongoDB connection")


async def save_report_to_db(report: dict):
    db = client.crypto
    await db.reports.insert_one(report)
    logging.info(f"Report saved to MongoDB for {report['symbol']}")
