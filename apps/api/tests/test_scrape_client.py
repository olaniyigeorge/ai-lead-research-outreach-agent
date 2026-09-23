from apps.api.integrations.scrape_client import build_homepage_url


def test_build_homepage_url_prefixes_https():
    assert build_homepage_url("acme.com") == "https://acme.com"
