import logging
from fastapi import APIRouter
from openai import OpenAI
from app.services.openai_service import get_crypto_price, get_crypto_metadata
from app.core.config import settings
import json
from app.models.crypto import CryptoRequest
from app.services.report_generator import generate_crypto_report
from app.db.mongodb import save_report_to_db
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()
client = OpenAI(api_key=settings.openai_api_key)

class ChatRequest(BaseModel):
    """
    Represents a chat request to OpenAI.
    """
    prompt: str

@router.post("/crypto/metadata")
async def crypto_metadata(request: CryptoRequest):
    logger.info(f"[Route] /crypto/metadata called with symbol: {request.symbol}")
    data = await get_crypto_metadata(request.symbol)
    logger.info(f"[Route] Metadata result for {request.symbol}: {data}")
    return data

@router.post("/crypto/report")
async def get_crypto_report(request: CryptoRequest):
    logger.info(f"[Route] /crypto/report called with symbol: {request.symbol}")
    report = await generate_crypto_report(request.symbol)
    logger.info(f"[Route] Generated report for {request.symbol}: {report}")
    return report

@router.post("/openai/crypto")
async def openai_crypto_price(request: CryptoRequest):
    logger.info(f"[Route] /openai/crypto called with symbol: {request.symbol}")
    data = await get_crypto_price(request.symbol)
    logger.info(f"[Route] Price result for {request.symbol}: {data}")
    return data

@router.post("/openai/chat")
async def chat_with_openai(request: ChatRequest):
    logger.info(f"[Route] /openai/chat called with prompt: {request.prompt}")
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": request.prompt}],
        functions=[
            {
                "name": "get_crypto_price",
                "description": "Retrieves cryptocurrency price from Moralis API",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Cryptocurrency ticker, e.g., BTC or ETH"
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "generate_crypto_report",
                "description": "Generates an analytical report on a cryptocurrency based on real-time data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Cryptocurrency ticker, e.g., BTC or ETH"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        ],
        function_call="auto"
    )
    result = response.model_dump()
    logger.info(f"[Route] OpenAI response: {result}")

    if "function_call" in result["choices"][0]["message"]:
        function_name = result["choices"][0]["message"]["function_call"]["name"]
        function_args = json.loads(result["choices"][0]["message"]["function_call"]["arguments"])
        logger.info(f"[Route] Function call {function_name} with arguments {function_args}")
        if function_name == "get_crypto_price":
            result_data = await get_crypto_price(**function_args)
            logger.info(f"[Route] get_crypto_price result: {result_data}")
            return result_data
        elif function_name == "generate_crypto_report":
            report = await generate_crypto_report(**function_args)
            await save_report_to_db(report)
            logger.info(f"[Route] Report generated and saved: {report}")
            return report
    return result
