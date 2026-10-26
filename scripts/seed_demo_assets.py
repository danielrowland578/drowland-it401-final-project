"""Add clearly fictional inventory records to the configured MySQL database."""
import random
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from services.asset_service import AssetService


def main():
    service = AssetService(create_app().config)
    batch = uuid4().hex[:8]
    rng = random.Random()
    records = []
    for index in range(1, 31):
        kind = rng.choice(service.ASSET_TYPES)
        records.append(service.validate_asset({
            "name": f"demo-{batch}-{kind.lower()}-{index:02}",
            "type": kind,
            "owner": rng.choice(("Demo Security Team", "Demo IT Team", "Demo Data Team", "")),
            "environment": rng.choice(("Demo Production", "Demo Staging", "Demo Development")),
            "address": f"192.0.2.{index}",
            "status": rng.choice(service.STATUSES),
            "risk": rng.choice(service.RISK_LEVELS),
        }))
    with service._connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.executemany(
                "INSERT INTO assets (name, asset_type, owner, environment, address, status, risk) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [service._values(record) for record in records],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    print(f"Added 30 fictional assets (batch: demo-{batch}). Existing assets were preserved.")


if __name__ == "__main__":
    main()
