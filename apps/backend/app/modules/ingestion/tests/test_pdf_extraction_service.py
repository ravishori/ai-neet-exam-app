from app.modules.ingestion.services.pdf_extraction_service import MIN_SECTION_CHARS, split_into_sections


def _padded(text: str) -> str:
    """Pads a section body past MIN_SECTION_CHARS so it isn't dropped as
    noise — flush() strips trailing whitespace, so pad with words, not
    spaces, or the padding vanishes before the length check runs."""
    filler = " filler word content"
    while len(text) < MIN_SECTION_CHARS + 1:
        text += filler
    return text


def test_splits_on_ncert_numbered_headings():
    page = "3.1  INTRODUCTION\n" + _padded("Some intro text.") + "\n3.2  ELECTRIC CURRENT\n" + _padded("Current is charge flow.")
    sections = split_into_sections([page])
    assert [s.heading for s in sections] == ["3.1 INTRODUCTION", "3.2 ELECTRIC CURRENT"]


def test_tracks_source_page_per_section():
    page1 = "3.1  INTRODUCTION\n" + _padded("Intro text on page 1.")
    page2 = "3.2  ELECTRIC CURRENT\n" + _padded("Current text on page 2.")
    sections = split_into_sections([page1, page2])
    assert sections[0].source_page == 1
    assert sections[1].source_page == 2


def test_section_spanning_multiple_pages_keeps_first_page_number():
    page1 = "3.1  INTRODUCTION\n" + _padded("Text starting on page 1.")
    page2 = "still part of section 3.1, continued onto page 2 with more text"
    sections = split_into_sections([page1, page2])
    assert len(sections) == 1
    assert sections[0].source_page == 1
    assert "continued onto page 2" in sections[0].text


def test_drops_sections_shorter_than_minimum():
    page = "3.1  INTRODUCTION\ntoo short\n3.2  ELECTRIC CURRENT\n" + _padded("This one is long enough to survive.")
    sections = split_into_sections([page])
    assert [s.heading for s in sections] == ["3.2 ELECTRIC CURRENT"]


def test_drops_text_before_the_first_heading():
    page = "Chapter Three\nCURRENT ELECTRICITY\n2024-25\n3.1  INTRODUCTION\n" + _padded("Real content.")
    sections = split_into_sections([page])
    assert len(sections) == 1
    assert "Chapter Three" not in sections[0].text


def test_normalizes_mangled_apostrophe_in_heading_and_body():
    # PyMuPDF extracts NCERT's apostrophe glyph as U+FFFD in real chapter 3
    # ("OHM�S LAW") — this must not break heading detection or leave the
    # replacement character in text handed to the AI. See ADR-0022.
    page = "3.4  OHM�S LAW\n" + _padded("Ohm�s law relates voltage and current.")
    sections = split_into_sections([page])
    assert sections[0].heading == "3.4 OHM'S LAW"
    assert "�" not in sections[0].text
    assert "Ohm's law" in sections[0].text


def test_no_headings_yields_no_sections():
    sections = split_into_sections(["Just some plain prose with no numbered headings at all."])
    assert sections == []
