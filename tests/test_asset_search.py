"""Exercise search results with an in-memory SQL database, without changing live assets."""
from contextlib import contextmanager
import sqlite3

import pytest

from services.asset_service import AssetService


@pytest.fixture
def inventory(monkeypatch):
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.execute(
        "CREATE TABLE assets (id INTEGER, name TEXT, asset_type TEXT, owner TEXT, "
        "environment TEXT, address TEXT, status TEXT, risk TEXT, updated_at TEXT)"
    )
    database.executemany("INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)", [
        (1, "prod-api-01", "Server", "Security Team", "Production", "10.0.0.10", "Active", "High"),
        (2, "prod-db-01", "Database", "Data Team", "Production", "db.internal", "Maintenance", "Critical"),
        (3, "test_100%!-node", "Endpoint", None, "Test", None, "Offline", "Low"),
        (4, "testX100abc-node", "Network", "Network Team", "Test", "10.0.1.1", "Active", "Low"),
    ])

    class Cursor:
        def execute(self, query, parameters):
            self.rows = database.execute(query.replace("%s", "?"), parameters).fetchall()

        def fetchall(self):
            return [dict(row) for row in self.rows]

        def fetchone(self):
            return dict(self.rows[0]) if self.rows else None

        def close(self):
            pass

    class Connection:
        def cursor(self, **kwargs):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    service = AssetService({})
    monkeypatch.setattr(service, "_connection", connection)
    yield service
    database.close()


@pytest.mark.parametrize("filters, expected", [
    ({}, [1, 2, 3, 4]),
    ({"query": "SERVER production SECURITY"}, [1]),
    ({"query": "critical"}, [2]),
    ({"query": "10.0.0"}, [1]),
    ({"query": "offline"}, [3]),
    ({"query": "production", "type": "Database", "status": "Maintenance", "risk": "Critical"}, [2]),
    ({"name": "API", "owner": "security", "address": "0.10", "environment": "prod"}, [1]),
    ({"query": "production", "owner": "Network"}, []),
    ({"query": "_100%!"}, [3]),
    ({"name": "_100%!"}, [3]),
    ({"query": "' OR 1=1 --"}, []),
    ({"query": "  \t  "}, [1, 2, 3, 4]),
])
def test_asset_search_results(inventory, filters, expected):
    assert sorted(asset["id"] for asset in inventory.list_assets(filters)) == expected


def test_pagination_limits_rows_and_keeps_filters(inventory):
    with inventory._connection() as connection:
        cursor = connection.cursor()
        for index in range(23):
            cursor.execute(
                "INSERT INTO assets (id, name, asset_type, environment, status, risk) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (100 + index, f"demo-{index:02}", "Server", "Demo", "Active", "Low"),
            )
    filters = {"query": "demo", "type": "Server", "status": "Active"}
    pages = [inventory.paginate_assets(filters, page) for page in (1, 2, 3)]
    assert [len(page["items"]) for page in pages] == [10, 10, 3]
    assert all(page["total"] == 23 and page["pages"] == 3 for page in pages)
    ids = [asset["id"] for page in pages for asset in page["items"]]
    assert ids == list(range(100, 123))
    assert inventory.paginate_assets(filters, -5)["page"] == 1
    assert inventory.paginate_assets(filters, 999)["page"] == 3
    empty = inventory.paginate_assets({"query": "nonexistent"}, 9)
    assert empty == {"items": [], "total": 0, "page": 1, "pages": 1}

    descending = [inventory.paginate_assets(filters, page, "name", "desc") for page in (1, 2, 3)]
    assert [asset["id"] for page in descending for asset in page["items"]] == list(range(122, 99, -1))


@pytest.mark.parametrize("column", ["name", "type", "owner", "environment", "address", "updated_at", "status", "risk"])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_asset_sorting(inventory, column, direction):
    records = inventory.list_assets({})
    expected = sorted(records, key=lambda row: row["id"])
    expected.sort(key=lambda row: str(row[column] or ("Unassigned" if column == "owner" else "")).lower(),
                  reverse=direction == "desc")
    actual = inventory.paginate_assets({}, sort=column, direction=direction)
    assert [row["id"] for row in actual["items"]] == [row["id"] for row in expected]


def test_asset_sorting_rejects_sql_fragments(inventory):
    result = inventory.paginate_assets({}, sort="name; DROP TABLE assets", direction="DESC; --")
    assert [row["id"] for row in result["items"]] == [row["id"] for row in inventory.paginate_assets({})["items"]]
