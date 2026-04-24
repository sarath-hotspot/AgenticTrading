import os
import requests

SERPER_URL = "https://google.serper.dev/search"


def web_search(query: str, num_results: int = 5) -> list:
    """Returns list of {title, url, snippet}. Silent no-op if SERPER_API_KEY not set."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []
    try:
        response = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num_results},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("organic", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results
    except Exception as e:
        return [{"title": "Search error", "url": "", "snippet": str(e)}]


def format_search_results(results: list) -> str:
    if not results:
        return "No search results found (SERPER_API_KEY not set or no results)."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
    return "\n\n".join(lines)


# Anthropic tool definition (optional — only used if SERPER_API_KEY is available)

TOOL_WEB_SEARCH = {
    "name": "web_search",
    "description": (
        "Search the web for recent research, papers, or market analysis "
        "relevant to a trading hypothesis. Returns empty if no API key is configured."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
            },
        },
        "required": ["query"],
    },
}
