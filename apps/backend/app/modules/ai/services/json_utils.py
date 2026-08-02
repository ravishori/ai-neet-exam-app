import json
import re


def parse_json_response(text: str) -> dict:
    """Models sometimes wrap JSON in markdown fences despite instructions not to — strip them.

    Models also occasionally emit one complete, valid JSON value and then
    keep talking (a trailing aside despite "nothing else" instructions) —
    raw_decode() takes only that first complete value and ignores
    anything after it, rather than failing the whole response over
    trailing text that was never meant to be parsed. It does NOT recover
    truncated or malformed JSON — that still raises, correctly, since
    there's no complete valid value to extract."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    value, _end_index = json.JSONDecoder().raw_decode(cleaned)
    return value
