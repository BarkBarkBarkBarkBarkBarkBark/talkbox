from src.infrastructure.seeds.agency_vector_seeder import _document_content


def test_document_content_is_stable_and_omits_empty_fields() -> None:
    agency = {
        "agency_name": "Example Resource",
        "category": "Food",
        "description": "  Meals every weekday.  ",
        "address": None,
        "insurance": "",
        "knowledge_tags": " pantry, meals ",
    }

    assert _document_content(agency) == (
        "Agency: Example Resource\n"
        "Category: Food\n"
        "Description: Meals every weekday.\n"
        "Tags: pantry, meals"
    )