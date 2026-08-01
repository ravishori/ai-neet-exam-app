import json
import re


def parse_json_response(text: str) -> dict:
    """Models sometimes wrap JSON in markdown fences despite instructions not to — strip them."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)
