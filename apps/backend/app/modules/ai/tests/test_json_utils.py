import pytest

from app.modules.ai.services.json_utils import parse_json_response


def test_parses_plain_json():
    assert parse_json_response('{"a": 1}') == {"a": 1}


def test_strips_markdown_fences():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('```\n{"a": 1}\n```') == {"a": 1}


def test_parses_json_array():
    assert parse_json_response('[{"a": 1}, {"a": 2}]') == [{"a": 1}, {"a": 2}]


def test_ignores_trailing_text_after_a_complete_json_value():
    """Real failure mode hit by the ingestion revision-sheet prompt: the
    model emits one complete, valid JSON object and then keeps talking
    despite "nothing else" instructions."""
    text = '{"formulas": ["V = IR"]}\n\nI hope this revision sheet helps with your studies!'
    assert parse_json_response(text) == {"formulas": ["V = IR"]}


def test_does_not_silently_recover_truncated_json():
    with pytest.raises(ValueError):
        parse_json_response('{"formulas": ["V = IR", "I = ne')
