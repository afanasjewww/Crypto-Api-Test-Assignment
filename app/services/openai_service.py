import json
import logging
import httpx
import asyncio
from app.core.config import settings

logger = logging.getLogger(__name__)

HEADERS = {"X-API-Key": settings.moralis_api_key}

# Mapping from our chain parameter to Coingecko platform keys
PLATFORM_MAPPING = {
    "eth": "ethereum",
    "bsc": "binance-smart-chain",
    "polygon": "polygon",
    "avalanche": "avalanche",
    "fantom": "fantom"
}


async def get_crypto_metadata(symbol: str, chain: str = "eth"):
    """
    Retrieves cryptocurrency metadata (contract address, name, symbol, etc.) from Moralis API.
    The chain parameter (e.g. "eth", "bsc", "polygon") is used to query the appropriate network.
    """
    logger.info(f"[Metadata] Requesting metadata for token '{symbol}' on chain '{chain}' via Moralis")
    # First, retrieve the contract address for the given token on the desired chain
    contract_address = await get_token_contract(symbol, chain)
    if not contract_address:
        logger.error(f"[Metadata] Contract address not found for token '{symbol}' on chain '{chain}'")
        return {"error": f"Unable to retrieve contract address for token {symbol} on chain {chain}"}

    url = f"https://deep-index.moralis.io/api/v2.2/erc20/{contract_address}/price?chain={chain}"
    logger.info(f"[Metadata] Moralis API request URL: {url}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS)

    logger.info(f"[Metadata] Moralis response for '{symbol}' on chain '{chain}': {response.text}")

    if response.status_code != 200:
        logger.error(f"[Metadata] Moralis API error for token '{symbol}' on chain '{chain}': {response.status_code}")
        return {"error": f"Moralis API error. Code: {response.status_code}", "response": response.text}

    try:
        data = response.json()
        # Moralis returns price data along with token details. You can adjust which fields you want.
        result = {
            "tokenName": data.get("tokenName"),
            "tokenSymbol": data.get("tokenSymbol"),
            "tokenLogo": data.get("tokenLogo"),
            "tokenDecimals": data.get("tokenDecimals"),
            "nativePrice": data.get("nativePrice"),
            "usdPrice": data.get("usdPrice"),
            "exchangeName": data.get("exchangeName"),
            "exchangeAddress": data.get("exchangeAddress"),
            "tokenAddress": data.get("tokenAddress")
        }
        if result["tokenAddress"]:
            logger.info(f"[Metadata] Retrieved metadata: {result}")
            return result
        else:
            logger.error("[Metadata] Contract address not found in Moralis response")
            return {"error": "Contract address not found"}
    except Exception as e:
        logger.exception("[Metadata] JSON processing error from Moralis API")
        return {"error": f"JSON processing error: {str(e)}"}


async def get_token_id(symbol: str) -> str:
    """
    Retrieves the token ID from the Coingecko API with retries on 429 errors.
    """
    logger.info(f"[TokenID] Requesting token ID for '{symbol}' via Coingecko")
    url = f"https://api.coingecko.com/api/v3/search?query={symbol.lower()}"
    retries = 3
    for attempt in range(1, retries + 1):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        if response.status_code == 429:
            logger.error(f"[TokenID] Attempt {attempt}: 429 Too Many Requests for '{symbol}'. Waiting 2 seconds.")
            await asyncio.sleep(2)
            continue
        elif response.status_code != 200:
            logger.error(f"[TokenID] Coingecko error for '{symbol}': {response.status_code}")
            return None
        data = response.json()
        coins = data.get("coins", [])
        if not coins:
            logger.error(f"[TokenID] No tokens found for '{symbol}'")
            return None
        token_id = coins[0]["id"]
        logger.info(f"[TokenID] Found token ID for '{symbol}': {token_id}")
        return token_id
    logger.error(f"[TokenID] Exceeded retry attempts for '{symbol}'")
    return None


async def _get_contract_from_coingecko(token_id: str, query: str, chain: str) -> str:
    """
    Helper function: if token_id is available, query the Coingecko API and return the contract address
    (if found) for the given query on the specified chain.
    """
    if not token_id:
        logger.info(f"[Contract] No token ID found for query '{query}'")
        return None
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}"
    logger.info(f"[Contract] Coingecko API request for '{query}': {url}")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        logger.error(f"[Contract] Error retrieving data for '{query}': {response.status_code}")
        return None
    data = response.json()
    platform_key = PLATFORM_MAPPING.get(chain, "ethereum")
    contract_address = data.get("platforms", {}).get(platform_key)
    if contract_address:
        logger.info(f"[Contract] Found address via Coingecko for '{query}' on chain '{chain}': {contract_address}")
    else:
        logger.info(f"[Contract] Address not found via Coingecko for '{query}' on chain '{chain}'")
    return contract_address


async def get_token_contract(symbol: str, chain: str = "eth") -> str:
    """
    Retrieves the contract address of the token.
    First attempts to get data via Coingecko, then – if not found – tries various wrapped version queries,
    and finally falls back to Ethplorer.
    The chain parameter is used both in Moralis and for selecting the appropriate platform key from Coingecko.
    """
    logger.info(f"[Contract] Requesting contract address for token '{symbol}' on chain '{chain}'")

    # For native Ethereum tokens, return the WETH address
    if symbol.upper() in ["ETH", "ETHEREUM"]:
        weth_address = "0xC02aaa39b223FE8D0A0E5C4F27eAD9083C756Cc2"
        logger.info(f"[Contract] Using WETH address for '{symbol}': {weth_address}")
        return weth_address

    # If token is not ERC20 on an EVM chain (e.g. SOL, XLM, etc.), return error
    if symbol.upper() in ["SOL", "SOLANA", "XLM", "STELLAR"]:
        logger.error(f"[Contract] Token '{symbol}' is not supported on EVM chains.")
        return None

    # First attempt via Coingecko
    token_id = await get_token_id(symbol)
    contract_address = await _get_contract_from_coingecko(token_id, symbol, chain)
    if contract_address:
        return contract_address

    # If unsuccessful, try several variants for the wrapped version
    wrapped_variants = [f"wrapped {symbol}", f"w{symbol.lower()}", f"wrapped-{symbol.lower()}"]
    for query in wrapped_variants:
        logger.info(f"[Contract] Trying wrapped query '{query}' on chain '{chain}'")
        wrapped_token_id = await get_token_id(query)
        contract_address = await _get_contract_from_coingecko(wrapped_token_id, query, chain)
        if contract_address:
            return contract_address

    # Fallback: Ethplorer API (note: Ethplorer supports only Ethereum)
    try:
        fallback_url = f"https://api.ethplorer.io/search?query={symbol}&apiKey=freekey"
        logger.info(f"[Contract] Fallback Ethplorer: Attempting to retrieve address for '{symbol}': {fallback_url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(fallback_url)
        if response.status_code == 200:
            data = response.json()
            tokens = data.get("tokens")
            if tokens and len(tokens) > 0:
                contract_address = tokens[0].get("address")
                if contract_address:
                    logger.info(f"[Contract] Fallback Ethplorer: Found address for '{symbol}': {contract_address}")
                    return contract_address
                else:
                    logger.error(f"[Contract] Fallback Ethplorer: No address found in results for '{symbol}'")
            else:
                logger.error(f"[Contract] Fallback Ethplorer: No results for '{symbol}'")
        else:
            logger.error(f"[Contract] Fallback Ethplorer: Error {response.status_code} for '{symbol}'")
    except Exception as e:
        logger.exception(f"[Contract] Fallback Ethplorer: Exception for '{symbol}': {str(e)}")
    return None


async def get_crypto_price(symbol: str, chain: str = "eth"):
    """
    Retrieves the latest cryptocurrency price using the Moralis API.
    Only data from Moralis is returned. The chain parameter (e.g., "eth", "bsc", "polygon") is used.
    """
    logger.info(f"[Price] Requesting price for '{symbol}' on chain '{chain}' via Moralis")
    contract_address = await get_token_contract(symbol, chain)
    if not contract_address:
        logger.error(f"[Price] Contract address not found for '{symbol}' on chain '{chain}'. Moralis data unavailable.")
        return {"error": f"Contract address not found for token {symbol} on chain {chain}. Moralis data unavailable."}

    url = f"https://deep-index.moralis.io/api/v2.2/erc20/{contract_address}/price?chain={chain}"
    logger.info(f"[Price] Moralis API request URL: {url}")
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS)

    logger.info(f"[Price] Moralis response for '{symbol}' on chain '{chain}': {response.text}")

    if response.status_code != 200:
        logger.error(f"[Price] Error retrieving price data for '{symbol}' on chain '{chain}': {response.status_code}")
        return {"error": f"Moralis API error. Code: {response.status_code}", "response": response.text}
    try:
        data = response.json()
        logger.info(f"[Price] Retrieved price data for '{symbol}' on chain '{chain}': {data}")
        return {
            "symbol": symbol,
            "current_price": data.get("usdPrice", "N/A"),
            "price_change_24h": data.get("priceChange", "N/A"),
            "price_change_percent": data.get("priceChangePercent", "N/A"),
            "high_24h": data.get("highPrice", "N/A"),
            "low_24h": data.get("lowPrice", "N/A"),
            "volume": data.get("volume", "N/A"),
            "source": "Moralis",
            "raw_response": data
        }
    except json.JSONDecodeError:
        logger.exception(f"[Price] Invalid JSON response from Moralis for '{symbol}' on chain '{chain}'")
        return {"error": "Invalid JSON response from Moralis API", "response": response.text}


# The function get_crypto_price_coingecko is left for reference, but is no longer used.
async def get_crypto_price_coingecko(symbol: str):
    logger.info(f"[Price] Requesting price for '{symbol}' via Coingecko (fallback)")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        logger.error(f"[Price] Coingecko error for '{symbol}': {response.status_code}")
        return {"error": "Unable to retrieve data from Coingecko"}
    data = response.json()
    logger.info(f"[Price] Coingecko data for '{symbol}': {data}")
    return {
        "symbol": symbol,
        "current_price": data.get(symbol.lower(), {}).get("usd", "N/A"),
        "source": "Coingecko"
    }
