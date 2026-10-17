from contextlib import contextmanager

from mysql import connector


class AssetService:
    ASSET_TYPES = ("Server", "Database", "Endpoint", "Network", "Storage")
    STATUSES = ("Active", "Maintenance", "Offline")
    RISK_LEVELS = ("Critical", "High", "Medium", "Low")

    CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS assets (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            name VARCHAR(120) NOT NULL,
            asset_type VARCHAR(40) NOT NULL,
            owner VARCHAR(120) NULL,
            environment VARCHAR(80) NOT NULL,
            address VARCHAR(255) NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'Active',
            risk VARCHAR(32) NOT NULL DEFAULT 'Low',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            INDEX idx_assets_name (name),
            INDEX idx_assets_type (asset_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """

    def __init__(self, config):
        self.config = config

    @property
    def is_configured(self):
        return all(
            self.config.get(key)
            for key in ("MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")
        )

    @staticmethod
    def validate_asset(data):
        asset = {
            "name": data.get("name", "").strip(),
            "type": data.get("type", "").strip(),
            "owner": data.get("owner", "").strip() or None,
            "environment": data.get("environment", "").strip(),
            "address": data.get("address", "").strip() or None,
            "status": data.get("status", "").strip(),
            "risk": data.get("risk", "").strip(),
        }
        if not asset["name"]:
            raise ValueError("Asset name is required.")
        if len(asset["name"]) > 120:
            raise ValueError("Asset name must be 120 characters or fewer.")
        if asset["type"] not in AssetService.ASSET_TYPES:
            raise ValueError("Choose a valid asset type.")
        if not asset["environment"]:
            raise ValueError("Environment is required.")
        if len(asset["environment"]) > 80:
            raise ValueError("Environment must be 80 characters or fewer.")
        if asset["owner"] and len(asset["owner"]) > 120:
            raise ValueError("Owner must be 120 characters or fewer.")
        if asset["address"] and len(asset["address"]) > 255:
            raise ValueError("Network address must be 255 characters or fewer.")
        if asset["status"] not in AssetService.STATUSES:
            raise ValueError("Choose a valid asset status.")
        if asset["risk"] not in AssetService.RISK_LEVELS:
            raise ValueError("Choose a valid risk level.")
        return asset

    def _connect(self):
        if not self.is_configured:
            raise RuntimeError("MySQL connection settings are incomplete.")
        options = {
            "host": self.config["MYSQL_HOST"],
            "port": int(self.config.get("MYSQL_PORT") or 3306),
            "database": self.config["MYSQL_DATABASE"],
            "user": self.config["MYSQL_USER"],
            "password": self.config["MYSQL_PASSWORD"],
            "connection_timeout": 8,
        }
        ssl_ca = self.config.get("MYSQL_SSL_CA")
        if ssl_ca:
            options["ssl_ca"] = ssl_ca
            options["ssl_verify_cert"] = True
            options["ssl_verify_identity"] = True
        return connector.connect(**options)

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(self.CREATE_TABLE_SQL)
            finally:
                cursor.close()
            connection.commit()
            yield connection
        finally:
            connection.close()

    def list_assets(self, filters):
        conditions = []
        parameters = []
        if filters.get("query"):
            pattern = f"%{filters['query']}%"
            conditions.append(
                "(name LIKE %s OR COALESCE(owner, '') LIKE %s "
                "OR environment LIKE %s OR COALESCE(address, '') LIKE %s)"
            )
            parameters.extend([pattern] * 4)
        if filters.get("type"):
            conditions.append("asset_type = %s")
            parameters.append(filters["type"])
        if filters.get("status"):
            conditions.append("status = %s")
            parameters.append(filters["status"])
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT id, name, asset_type AS type, owner, environment, address,
                   status, risk, updated_at
            FROM assets {where_clause}
            ORDER BY name, id
        """
        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, parameters)
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_asset_types(self):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT DISTINCT asset_type FROM assets ORDER BY asset_type")
                return [row[0] for row in cursor.fetchall()]
            finally:
                cursor.close()

    def get_metrics(self):
        query = """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(status = 'Active'), 0) AS active,
                   COALESCE(SUM(risk = 'Critical'), 0) AS critical,
                   COALESCE(SUM(owner IS NULL OR owner = ''), 0) AS unassigned
            FROM assets
        """
        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query)
                return cursor.fetchone()
            finally:
                cursor.close()

    def get_asset(self, asset_id):
        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT id, name, asset_type AS type, owner, environment, address, status, risk "
                    "FROM assets WHERE id = %s",
                    (asset_id,),
                )
                return cursor.fetchone()
            finally:
                cursor.close()

    def create_asset(self, data):
        asset = self.validate_asset(data)
        query = """
            INSERT INTO assets (name, asset_type, owner, environment, address, status, risk)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(query, self._values(asset))
                connection.commit()
                return cursor.lastrowid
            finally:
                cursor.close()

    def update_asset(self, asset_id, data):
        asset = self.validate_asset(data)
        query = """
            UPDATE assets
            SET name = %s, asset_type = %s, owner = %s, environment = %s,
                address = %s, status = %s, risk = %s
            WHERE id = %s
        """
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT id FROM assets WHERE id = %s", (asset_id,))
                if cursor.fetchone() is None:
                    return False
                cursor.execute(query, (*self._values(asset), asset_id))
                connection.commit()
                return True
            finally:
                cursor.close()

    def delete_asset(self, asset_id):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
                connection.commit()
                return cursor.rowcount > 0
            finally:
                cursor.close()

    @staticmethod
    def _values(asset):
        return (
            asset["name"], asset["type"], asset["owner"], asset["environment"],
            asset["address"], asset["status"], asset["risk"],
        )