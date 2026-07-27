from src.infrastructure.seeds.agency_vector_seeder import _document_content


def test_document_content_is_stable_and_omits_empty_fields() -> None:
    resource = {
        "name": "Example Resource",
        "organization_name": "Example Organization",
        "category": "Food",
        "description": "  Meals every weekday.  ",
        "address": None,
        "city": " Sacramento ",
        "eligibility_text": "",
        "languages_text": " English, Spanish ",
        "hours_text": None,
    }

    assert _document_content(resource) == (
        "Resource: Example Resource\n"
        "Organization: Example Organization\n"
        "Category: Food\n"
        "Description: Meals every weekday.\n"
        "City: Sacramento\n"
        "Languages: English, Spanish"
    )