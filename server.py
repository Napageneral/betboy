import os
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = Anthropic()

POLYMARKET_API = "https://gamma-api.polymarket.com"


class VoiceQuery(BaseModel):
    query: str


def search_polymarket_markets(search_term: str, limit: int = 10) -> list:
    """Search Polymarket for events matching the search term."""
    try:
        with httpx.Client(timeout=10.0) as http_client:
            response = http_client.get(
                f"{POLYMARKET_API}/markets",
                params={
                    "closed": "false",
                    "limit": limit,
                    "_c": search_term,
                }
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error searching Polymarket: {e}")
        return []


def get_market_details(condition_id: str) -> dict | None:
    """Get detailed information about a specific market."""
    try:
        with httpx.Client(timeout=10.0) as http_client:
            response = http_client.get(
                f"{POLYMARKET_API}/markets/{condition_id}"
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error getting market details: {e}")
        return None


# Define tools for Claude
tools = [
    {
        "name": "search_sports_markets",
        "description": "Search Polymarket for sports betting markets. Use this to find events related to sports, games, matches, championships, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of search terms to try. Include team names, sport names, event names, player names. Try multiple variations."
                }
            },
            "required": ["search_terms"]
        }
    },
    {
        "name": "present_market_to_user",
        "description": "Present the best matching market to the user with betting information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "object",
                    "description": "The market object to present",
                    "properties": {
                        "id": {"type": "string"},
                        "question": {"type": "string"},
                        "description": {"type": "string"},
                        "outcomes": {"type": "string"},
                        "outcomePrices": {"type": "string"},
                        "volume": {"type": "string"},
                        "slug": {"type": "string"},
                        "endDate": {"type": "string"}
                    }
                },
                "explanation": {
                    "type": "string",
                    "description": "Brief explanation of why this market matches what the user asked for"
                }
            },
            "required": ["market", "explanation"]
        }
    }
]


def run_agent(user_query: str) -> dict:
    """Run the Claude agent to find matching Polymarket events."""
    messages = [
        {
            "role": "user",
            "content": f"""The user said (via voice): "{user_query}"

Find the best matching sports or event betting market on Polymarket. 
Search using relevant terms extracted from their query.
Once you find a good match, present it to the user.
If you can't find anything, explain what you searched for."""
        }
    ]

    all_markets = []
    max_iterations = 5

    for _ in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )

        # Check if we're done
        if response.stop_reason == "end_turn":
            # Extract text response
            for block in response.content:
                if hasattr(block, "text"):
                    return {
                        "status": "no_match",
                        "message": block.text,
                        "markets_searched": len(all_markets)
                    }
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "search_sports_markets":
                    search_terms = block.input.get("search_terms", [])
                    markets = []
                    for term in search_terms:
                        results = search_polymarket_markets(term, limit=5)
                        markets.extend(results)
                        all_markets.extend(results)
                    
                    # Deduplicate by condition_id
                    seen = set()
                    unique_markets = []
                    for m in markets:
                        cid = m.get("conditionId") or m.get("id")
                        if cid and cid not in seen:
                            seen.add(cid)
                            unique_markets.append({
                                "id": m.get("conditionId") or m.get("id"),
                                "question": m.get("question", ""),
                                "description": m.get("description", "")[:200] if m.get("description") else "",
                                "outcomes": m.get("outcomes", ""),
                                "outcomePrices": m.get("outcomePrices", ""),
                                "volume": m.get("volume", ""),
                                "slug": m.get("slug", ""),
                                "endDate": m.get("endDate", "")
                            })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(unique_markets[:10])
                    })

                elif block.name == "present_market_to_user":
                    market = block.input.get("market", {})
                    explanation = block.input.get("explanation", "")
                    
                    # Parse prices
                    prices = market.get("outcomePrices", "")
                    outcomes = market.get("outcomes", "")
                    
                    try:
                        if isinstance(prices, str) and prices:
                            prices = json.loads(prices)
                        if isinstance(outcomes, str) and outcomes:
                            outcomes = json.loads(outcomes)
                    except:
                        pass

                    betting_info = []
                    if isinstance(outcomes, list) and isinstance(prices, list):
                        for i, outcome in enumerate(outcomes):
                            if i < len(prices):
                                try:
                                    price = float(prices[i])
                                    cents = int(price * 100)
                                    betting_info.append({
                                        "outcome": outcome,
                                        "price_cents": cents,
                                        "implied_probability": f"{cents}%"
                                    })
                                except:
                                    pass

                    return {
                        "status": "found",
                        "market": {
                            "id": market.get("id"),
                            "question": market.get("question"),
                            "description": market.get("description"),
                            "slug": market.get("slug"),
                            "endDate": market.get("endDate"),
                            "volume": market.get("volume"),
                            "url": f"https://polymarket.com/event/{market.get('slug')}" if market.get("slug") else None
                        },
                        "betting_info": betting_info,
                        "explanation": explanation
                    }

        # Add assistant message and tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return {
        "status": "error",
        "message": "Could not find a matching market after multiple attempts"
    }


@app.post("/api/search")
async def search_markets(query: VoiceQuery):
    """Handle voice query and return matching markets."""
    if not query.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")
    
    result = run_agent(query.query)
    return result


@app.get("/api/markets/{slug}")
async def get_market(slug: str):
    """Get market details by slug."""
    try:
        with httpx.Client(timeout=10.0) as http_client:
            response = http_client.get(
                f"{POLYMARKET_API}/events",
                params={"slug": slug}
            )
            response.raise_for_status()
            events = response.json()
            if events:
                return events[0]
            raise HTTPException(status_code=404, detail="Market not found")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

