from apps.api.integrations.apify_client import build_actor_input, normalize_domain


def test_normalize_domain_strips_scheme_www_and_path():
    assert normalize_domain("https://www.Acme.com/about") == "acme.com"
    assert normalize_domain("http://acme.com") == "acme.com"
    assert normalize_domain("acme.com") == "acme.com"
    assert normalize_domain(None) is None
    assert normalize_domain("") is None


def test_build_actor_input_maps_icp_fields():
    icp = {
        "target_company_type": "B2B SaaS",
        "industries": ["Software", "FinTech"],
        "geography": ["United States"],
        "headcount_range": "10-100",
    }

    actor_input = build_actor_input(icp, max_items=10)

    assert actor_input["mode"] == "search"
    assert actor_input["includeContacts"] is False
    assert actor_input["maxItems"] == 10
    # Only the first two words of the first industry go into searchTerm --
    # the actor's searchTerm behaves like a phrase match rather than a
    # tokenized AND, so joining multiple labels (or the long
    # `target_company_type` sentence) reliably returns zero results.
    assert actor_input["searchTerm"] == "Software"
    assert actor_input["country"] == "United States"
    assert actor_input["employeesEstimatedMin"] == 10
    assert actor_input["empMax"] == 100


def test_build_actor_input_omits_search_term_when_no_industries():
    actor_input = build_actor_input({"target_company_type": "B2B SaaS"}, max_items=5)
    assert "searchTerm" not in actor_input


def test_build_actor_input_search_term_uses_only_first_two_words_of_first_industry():
    icp = {"industries": ["Marketing/Advertising Agencies", "Digital Agencies"]}
    actor_input = build_actor_input(icp, max_items=5)
    assert actor_input["searchTerm"] == "Marketing Advertising"


def test_build_actor_input_normalizes_country_aliases_and_parentheticals():
    assert build_actor_input({"geography": ["Canada (nationwide)"]}, max_items=5)["country"] == "Canada"
    assert build_actor_input({"geography": ["USA"]}, max_items=5)["country"] == "United States"
    assert (
        build_actor_input({"geography": ["United States of America"]}, max_items=5)["country"]
        == "United States"
    )
    assert build_actor_input({"geography": ["UK"]}, max_items=5)["country"] == "United Kingdom"


def test_build_actor_input_skips_country_filter_for_multiple_geographies():
    icp = {"geography": ["United States", "Canada"]}
    actor_input = build_actor_input(icp, max_items=5)
    assert "country" not in actor_input


def test_build_actor_input_handles_missing_headcount_range():
    actor_input = build_actor_input({}, max_items=5)
    assert "employeesEstimatedMin" not in actor_input
    assert "empMax" not in actor_input


def test_build_actor_input_handles_single_number_headcount_range():
    actor_input = build_actor_input({"headcount_range": "50+"}, max_items=5)
    assert actor_input["employeesEstimatedMin"] == 50
    assert "empMax" not in actor_input
