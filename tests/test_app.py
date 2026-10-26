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

        def paginate_assets(self, filters, page=1, **kwargs):
            return {"items": [], "total": 0, "page": 1, "pages": 1}

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


def test_asset_filters_are_forwarded_and_preserved(client, monkeypatch):
    from services.asset_service import AssetService

    captured = {}

    def paginate_assets(self, filters, page=1, **kwargs):
        captured.update(filters)
        return {"items": [], "total": 0, "page": 1, "pages": 1}

    monkeypatch.setattr(AssetService, "is_configured", True)
    monkeypatch.setattr(AssetService, "paginate_assets", paginate_assets)
    monkeypatch.setattr(AssetService, "get_asset_types", lambda self: ["Server"])
    monkeypatch.setattr(AssetService, "get_metrics", lambda self: {"total": 3, "active": 2, "critical": 1, "unassigned": 0})
    response = client.get("/assets", query_string={
        "q": " production server ", "type": "Server", "status": "Active",
        "name": " api ", "owner": "Security", "address": "10.0", "environment": "prod", "risk": "High",
    })

    assert response.status_code == 200
    assert captured == {
        "query": "production server", "type": "Server", "status": "Active", "name": "api",
        "owner": "Security", "address": "10.0", "environment": "prod", "risk": "High",
    }
    assert b'value="Security"' in response.data
    assert b'value="10.0"' in response.data
    assert b'value="High" selected' in response.data
    assert b'open>' in response.data
    assert b'No assets match these filters.' in response.data
    assert b'>Clear</a>' in response.data


def test_asset_field_filter_shows_empty_results_and_clear(client):
    response = client.get("/assets?owner=Nobody")
    assert response.status_code == 200
    assert b'>Clear</a>' in response.data
    assert b'value="Nobody"' in response.data


@pytest.mark.parametrize("page_value, expected_page", [("2", 2), ("invalid", 1)])
def test_asset_page_links_preserve_filters(client, monkeypatch, page_value, expected_page):
    from html import unescape
    import re
    from urllib.parse import parse_qs, urlsplit
    from services.asset_service import AssetService

    def paginate(self, filters, page=1, **kwargs):
        assert page == expected_page
        assert kwargs == {"sort": "owner", "direction": "desc"}
        return {"items": [], "total": 23, "page": page, "pages": 3}

    monkeypatch.setattr(AssetService, "is_configured", True)
    monkeypatch.setattr(AssetService, "paginate_assets", paginate)
    monkeypatch.setattr(AssetService, "get_asset_types", lambda self: [])
    monkeypatch.setattr(AssetService, "get_metrics", lambda self: {"total": 36})
    filters = {"q": "demo server", "type": "Server", "status": "Active", "owner": "Demo IT",
               "name": "demo", "address": "192.0.2", "environment": "Demo", "risk": "Low"}
    response = client.get("/assets", query_string={**filters, "page": page_value, "sort": "owner", "direction": "desc"})
    assert response.status_code == 200
    markup = response.get_data(as_text=True)
    assert f"Page {expected_page} of 3" in markup
    next_link = re.search(r'href="([^"]+)">Next</a>', markup).group(1)
    assert parse_qs(urlsplit(unescape(next_link)).query) == {
        **{key: [value] for key, value in filters.items()}, "page": [str(expected_page + 1)],
        "sort": ["owner"], "direction": ["desc"]}
    assert 'aria-sort="descending"' in markup
    assert 'name="sort" value="owner"' in markup
    assert 'name="direction" value="desc"' in markup
    owner_link = re.search(r'href="([^"]+)" aria-label="Sort by Owner ascending"', markup).group(1)
    owner_args = parse_qs(urlsplit(unescape(owner_link)).query)
    assert owner_args == {**{key: [value] for key, value in filters.items()},
                          "sort": ["owner"], "direction": ["asc"]}
    type_link = re.search(r'href="([^"]+)" aria-label="Sort by Type ascending"', markup).group(1)
    assert parse_qs(urlsplit(unescape(type_link)).query)["direction"] == ["asc"]
    if expected_page == 2:
        previous_link = re.search(r'href="([^"]+)">Previous</a>', markup).group(1)
        assert parse_qs(urlsplit(unescape(previous_link)).query)["page"] == ["1"]


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
