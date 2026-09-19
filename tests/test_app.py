import pytest

from app import create_app
from services.web_scraper_service import WebScraperService


@pytest.fixture
def client():
    app = create_app("development")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200


def test_intelligence_route_reads_json_store(client):
    response = client.get("/intelligence?severity=Critical")

    assert response.status_code == 200
    assert b"Credential stuffing campaign" in response.data
    assert b"Unusual PowerShell execution" not in response.data


def test_intelligence_route_supports_text_filter(client):
    response = client.get("/intelligence?q=cloud")

    assert response.status_code == 200
    assert b"Exposed S3 bucket detected" in response.data
    assert b"Credential stuffing campaign" not in response.data


def test_domain_lookup_route_renders_page(client):
    response = client.get("/domain-lookup?domain=example.com")

    assert response.status_code == 200
    assert b"Domain infrastructure lookup" in response.data
    assert b"example.com" in response.data


def test_intelligence_route_includes_richer_threat_feed(client):
    response = client.get("/intelligence")

    assert response.status_code == 200
    assert b"Botnet C2 beaconing" in response.data
    assert b"Public source" in response.data


def test_web_scraper_risk_score_uses_external_evidence():
    threat = {"severity": "Medium", "indicators": "example-ip"}
    score = WebScraperService._risk_score(
        threat,
        "Credential phishing campaign",
        "Malware attack targeting exposed credentials",
    )

    assert score > 45
    assert WebScraperService._risk_label(score) in {"Moderate", "High", "Critical"}


def test_web_scraper_enrichment_preserves_feed_order(monkeypatch):
    service = WebScraperService(max_workers=2)
    monkeypatch.setattr(
        service,
        "scrape_threat",
        lambda threat: {"summary": threat["title"], "reference_url": "https://example.com"},
    )

    enriched = service.enrich_threats([{"title": "first"}, {"title": "second"}])

    assert [threat["title"] for threat in enriched] == ["first", "second"]


def test_web_scraper_parses_bing_result_markup(monkeypatch):
    class Response:
        text = (
            '<li class="b_algo"><h2><a href="https://example.com/report">'
            'Test threat external report</a></h2><div class="b_caption"><p>'
            'Independent context for this threat.</p></div></li>'
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr("services.web_scraper_service.requests.get", lambda *args, **kwargs: Response())
    result = WebScraperService().scrape_threat({"title": "Test threat", "severity": "High"})

    assert result["reference_url"] == "https://example.com/report"
    assert result["summary"] == "Independent context for this threat."


def test_web_scraper_decodes_bing_link_entities(monkeypatch):
    class Response:
        text = (
            '<li class="b_algo"><h2><a href="https://www.bing.com/ck?a=1&amp;b=2">'
            'Test threat external report</a></h2><div class="b_caption"><p>Context.</p></div></li>'
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr("services.web_scraper_service.requests.get", lambda *args, **kwargs: Response())
    result = WebScraperService().scrape_threat({"title": "Test threat"})

    assert result["reference_url"] == "https://www.bing.com/ck?a=1&b=2"
