from flask import current_app, render_template, request

from services.search_service import SearchService


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
        threats = SearchService(current_app.config["DATA_DIR"]).search(**filters)
        return render_template("intelligence.html", threats=threats, filters=filters)
