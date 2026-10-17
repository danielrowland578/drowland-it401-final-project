from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)

from app import create_app
from services.asset_service import AssetService

app = create_app("development")
app.config["TESTING"] = True
service = AssetService(app.config)

if not service.is_configured:
    print("BLOCKED: required MySQL settings are missing")
    raise SystemExit(2)

try:
    existing = service.list_assets({})
except Exception as error:
    print(f"BLOCKED: database connection failed ({type(error).__name__}, code={getattr(error, 'errno', 'unknown')})")
    raise SystemExit(3)

if existing:
    print(f"BLOCKED: found {len(existing)} pre-existing assets; no test records written")
    raise SystemExit(4)

prefix = "tp-crud-" + uuid4().hex[:8]
records = [
    {"name": f"{prefix}-server", "type": "Server", "owner": "CRUD Check", "environment": "Test", "address": "192.0.2.10", "status": "Active", "risk": "Low"},
    {"name": f"{prefix}-endpoint", "type": "Endpoint", "owner": "CRUD Check", "environment": "Test", "address": "192.0.2.11", "status": "Maintenance", "risk": "Medium"},
    {"name": f"{prefix}-database", "type": "Database", "owner": "CRUD Check", "environment": "Test", "address": "192.0.2.12", "status": "Active", "risk": "High"},
]

try:
    with app.test_client() as client:
        for record in records:
            response = client.post("/assets", data=record, follow_redirects=True)
            assert response.status_code == 200 and b"Asset created." in response.data

        found = service.list_assets({"query": prefix})
        assert len(found) == 3
        page = client.get("/assets", query_string={"q": prefix})
        assert all(record["name"].encode() in page.data for record in records)
        assert b"Database is not configured" not in page.data

        first = next(asset for asset in found if asset["name"].endswith("-server"))
        updated_name = f"{prefix}-server-updated"
        updated = dict(records[0], name=updated_name)
        response = client.post(f"/assets/{first['id']}/update", data=updated, follow_redirects=True)
        assert response.status_code == 200 and b"Asset updated." in response.data
        assert service.get_asset(first["id"])["name"] == updated_name

        endpoint = next(asset for asset in found if asset["name"].endswith("-endpoint"))
        response = client.post(f"/assets/{endpoint['id']}/delete", follow_redirects=True)
        assert response.status_code == 200 and b"Asset deleted." in response.data
        assert service.get_asset(endpoint["id"]) is None

    print("CRUD PASSED: created 3, read 3, updated 1, deleted 1")
finally:
    remaining = service.list_assets({"query": prefix})
    for asset in remaining:
        service.delete_asset(asset["id"])
    assert not service.list_assets({"query": prefix})
    print("CLEANUP PASSED: no temporary records remain")
