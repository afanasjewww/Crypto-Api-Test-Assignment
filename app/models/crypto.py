import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CryptoRequest(BaseModel):
    symbol: str


class CryptoResponse(BaseModel):
    symbol: str
    info: str


class CryptoReport(BaseModel):
    symbol: str
    current_price: float
    price_change_percent: float
    high_24h: float
    low_24h: float
    volume: float
    sentiment: str
    report_summary: str

