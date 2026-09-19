import requests


class DomainLookupService:
    """Query the APIFreaks WHOIS Domain Lookup API for registrar and expiry metadata."""

    def __init__(self, api_key, base_url="https://api.apifreaks.com/v2.0"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def lookup(self, domain_name):
        if not domain_name:
            raise ValueError("A domain name is required.")

        response = requests.get(
            f"{self.base_url}/domain/whois/live",
            params={"domainName": domain_name},
            headers={"X-apiKey": self.api_key},
            timeout=15,
        )
        response.raise_for_status()

        payload = response.json()
        if not payload or not payload.get("status") and payload.get("status") is not False:
            return {"domain_name": domain_name, "domain_registered": "unknown"}

        registrar = payload.get("domain_registrar") or {}

        return {
            "domain_name": payload.get("domain_name") or domain_name,
            "query_time": payload.get("query_time") or "N/A",
            "domain_registered": payload.get("domain_registered", "unknown"),
            "create_date": payload.get("create_date") or "N/A",
            "expiry_date": payload.get("expiry_date") or "N/A",
            "registrar_name": registrar.get("registrar_name") or "N/A",
            "registrar_status": registrar.get("status") or "N/A",
            "registrar_iana_id": registrar.get("iana_id") or "N/A",
            "registrar_website": registrar.get("website_url") or "N/A",
            "registrar_email": registrar.get("email_address") or "N/A",
            "name_servers": payload.get("name_servers") or [],
            "domain_status": payload.get("domain_status") or [],
        }
