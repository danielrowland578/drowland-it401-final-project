import pytest

from app import create_app
from services.web_scraper_service import WebScraperService


@pytest.fixture
def client():
    app = create_app("development")
    app.config["TESTING"] = True
    app.config.update(
        MYSQL_HOST=None,
        MYSQL_DATABASE=None,
        MYSQL_USER=None,
        MYSQL_PASSWORD=None,
        MYSQL_SSL_CA=None,
    )
    with app.test_client() as client:
        yield client


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200


def test_assets_route_shows_unconfigured_empty_inventory(client):
    response = client.get("/assets")

    assert response.status_code == 200
    assert b"Database is not configured" in response.data
    assert b"No assets have been added yet" not in response.data
    assert b"prod-api-01" not in response.data
    assert b"SAMPLE DATA" not in response.data


def test_assets_crud_routes_use_database_service(client, monkeypatch):
    class FakeAssetService:
        is_configured = True
        STATUSES = ("Active", "Maintenance", "Offline")
        ASSET_TYPES = ("Server", "Database")
        RISK_LEVELS = ("Critical", "High", "Medium", "Low")

        def __init__(self, config):
            self.created = None
            self.updated = None
            self.deleted = None

        def list_assets(self, filters):
            return []

        def get_asset_types(self):
            return []

        def get_metrics(self):
            return {"total": 0, "active": 0, "critical": 0, "unassigned": 0}

        def get_asset(self, asset_id):
            return None

        def create_asset(self, data):
            self.created = data.get("name")

        def update_asset(self, asset_id, data):
            self.updated = (asset_id, data.get("name"))
            return True

        def delete_asset(self, asset_id):
            self.deleted = asset_id
            return True

    fake_service = FakeAssetService({})
    monkeypatch.setattr("routes.main.AssetService", lambda config: fake_service)
    asset_form = {
        "name": "test-server",
        "type": "Server",
        "owner": "Test Team",
        "environment": "Test",
        "address": "192.0.2.10",
        "status": "Active",
        "risk": "Low",
    }

    assert client.post("/assets", data=asset_form).status_code == 302
    assert fake_service.created == "test-server"
    assert client.post("/assets/12/update", data=asset_form).status_code == 302
    assert fake_service.updated == (12, "test-server")
    assert client.post("/assets/12/delete").status_code == 302
    assert fake_service.deleted == 12


def test_asset_validation_rejects_unknown_status():
    from services.asset_service import AssetService

    with pytest.raises(ValueError, match="valid asset status"):
        AssetService.validate_asset(
            {
                "name": "test-server",
                "type": "Server",
                "environment": "Test",
                "status": "Unknown",
                "risk": "Low",
            }
        )


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
