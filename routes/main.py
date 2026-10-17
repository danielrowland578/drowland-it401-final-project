from flask import current_app, flash, redirect, render_template, request, url_for

from services.domain_lookup_service import DomainLookupService
from services.asset_service import AssetService
from services.search_service import SearchService
from services.web_scraper_service import WebScraperService


def register_routes(app):
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.get("/assets")
    def assets():
        filters = {
            "query": request.args.get("q", "").strip(),
            "type": request.args.get("type", ""),
            "status": request.args.get("status", ""),
        }
        service = AssetService(current_app.config)
        assets = []
        asset_types = []
        metrics = {"total": 0, "active": 0, "critical": 0, "unassigned": 0}
        database_error = None

        if not service.is_configured:
            database_error = "Database is not configured. Add your Aiven connection settings to the local .env file."
        else:
            try:
                assets = service.list_assets(filters)
                asset_types = service.get_asset_types()
                metrics = service.get_metrics()
            except Exception:
                current_app.logger.exception("Unable to load assets from MySQL")
                database_error = "Unable to load assets from MySQL. Check your Aiven connection settings."

        editing_asset = None
        edit_id = request.args.get("edit", type=int)
        if edit_id and service.is_configured and not database_error:
            try:
                editing_asset = service.get_asset(edit_id)
                if editing_asset is None:
                    database_error = "That asset could not be found."
            except Exception:
                current_app.logger.exception("Unable to load asset for editing")
                database_error = "Unable to load that asset from MySQL."

        return render_template(
            "assets.html",
            assets=assets,
            filters=filters,
            asset_types=asset_types,
            statuses=service.STATUSES,
            asset_kinds=service.ASSET_TYPES,
            risk_levels=service.RISK_LEVELS,
            metrics=metrics,
            database_error=database_error,
            editing_asset=editing_asset,
            database_ready=service.is_configured,
        )

    @app.post("/assets")
    def create_asset():
        service = AssetService(current_app.config)
        if not service.is_configured:
            flash("Configure your Aiven MySQL connection before adding assets.", "error")
            return redirect(url_for("assets"))

        try:
            service.create_asset(request.form)
            flash("Asset created.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
        except Exception:
            current_app.logger.exception("Unable to create asset")
            flash("Unable to create the asset in MySQL. Check the app log for details.", "error")
        return redirect(url_for("assets"))

    @app.post("/assets/<int:asset_id>/update")
    def update_asset(asset_id):
        service = AssetService(current_app.config)
        if not service.is_configured:
            flash("Configure your Aiven MySQL connection before editing assets.", "error")
            return redirect(url_for("assets"))

        try:
            if service.update_asset(asset_id, request.form):
                flash("Asset updated.", "success")
            else:
                flash("That asset could not be found.", "error")
        except ValueError as exc:
            flash(str(exc), "error")
        except Exception:
            current_app.logger.exception("Unable to update asset")
            flash("Unable to update the asset in MySQL. Check the app log for details.", "error")
        return redirect(url_for("assets"))

    @app.post("/assets/<int:asset_id>/delete")
    def delete_asset(asset_id):
        service = AssetService(current_app.config)
        if not service.is_configured:
            flash("Configure your Aiven MySQL connection before deleting assets.", "error")
            return redirect(url_for("assets"))

        try:
            if service.delete_asset(asset_id):
                flash("Asset deleted.", "success")
            else:
                flash("That asset could not be found.", "error")
        except Exception:
            current_app.logger.exception("Unable to delete asset")
            flash("Unable to delete the asset from MySQL. Check the app log for details.", "error")
        return redirect(url_for("assets"))

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
