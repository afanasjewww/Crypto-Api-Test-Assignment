import json
from openai import OpenAI
from app.services.openai_service import get_crypto_price
from app.db.mongodb import save_report_to_db
from app.core.config import settings

client = OpenAI(api_key=settings.openai_api_key)

async def generate_crypto_report(symbol: str):
    """
    Retrieves token data, analyzes it, and generates a report using OpenAI.

    Args:
        symbol (str): The ticker symbol of the cryptocurrency.

    Returns:
        dict: A detailed report containing price, volume, and analysis.
    """
    # Retrieve cryptocurrency data
    data = await get_crypto_price(symbol)

    # Construct the prompt for OpenAI analysis
    prompt = f"""
    Generate an analytical report for the token {symbol}.
    Price: {data['current_price']} USD
    24h Change: {data['price_change_percent']}%
    Trading Volume: {data['volume']}
    Provide an investment analysis, risks, and insights.
    """

    # Send the request to OpenAI for analysis
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}]
    )

    report_summary = response.choices[0].message["content"]

    # Create the final report
    report = {
        "symbol": symbol,
        "current_price": data.get("current_price", "N/A"),
        "price_change_percent": data.get("price_change_percent", "N/A"),
        "high_24h": data.get("high_24h", "N/A"),
        "low_24h": data.get("low_24h", "N/A"),
        "volume": data.get("volume", "N/A"),
        "source": data.get("source", "Unknown"),
        "report_summary": report_summary
    }

    return report
