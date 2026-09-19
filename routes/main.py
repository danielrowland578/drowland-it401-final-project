from flask import current_app, render_template, request

from services.domain_lookup_service import DomainLookupService
from services.search_service import SearchService
from services.web_scraper_service import WebScraperService


def register_routes(app):
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/intelligence")
    def intelligence():
        filters = {
            "query": request.args.get("q", ""),
            "severity": request.args.get("severity", ""),
            "status": request.args.get("status", ""),
            "source": request.args.get("source", ""),
        }
        search_service = SearchService(current_app.config["DATA_DIR"])
        threats = search_service.search(**filters)
        enriched = WebScraperService().enrich_threats(threats)
        scrape_count = sum(1 for threat in enriched if threat.get("web_summary"))
        return render_template(
            "intelligence.html",
            threats=enriched,
            filters=filters,
            scrape_count=scrape_count,
        )

    @app.route("/domain-lookup")
    def domain_lookup():
        domain = request.args.get("domain", "").strip()
        result = None
        error = None

        if domain:
            api_key = current_app.config.get("APIFREAKS_API_KEY") or current_app.config.get("API_KEY")
            if not api_key:
                error = "APIFreaks API key is not configured. Set APIFREAKS_API_KEY in your environment."
            else:
                try:
                    service = DomainLookupService(api_key)
                    result = service.lookup(domain)
                except ValueError as exc:
                    error = str(exc)
                except Exception as exc:  # pragma: no cover - network / API failure path
                    error = f"Unable to retrieve domain details for {domain}: {exc}"

        return render_template(
            "domain_lookup.html",
            domain=domain,
            result=result,
            error=error,
        )
