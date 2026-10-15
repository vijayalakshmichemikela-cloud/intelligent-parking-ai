"""
Smart Parking Management System
Main Flask Application — Entry Point

Configuration is loaded from config.py (which reads the .env file).
config.py is kept as a separate file to avoid circular imports with database.py.
"""

import os
import datetime
from flask import Flask, render_template
from config import Config


# ─── Application Factory ──────────────────────────────────────────────────────
def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Import Blueprints (done inside factory to avoid circular imports)
    from routes.auth         import auth_bp
    from routes.dashboard    import dashboard_bp
    from routes.parking      import parking_bp
    from routes.reservations import reservations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(parking_bp)
    app.register_blueprint(reservations_bp)

    # ── Template Context: variables available in every HTML template ──────────
    from database import get_db_info
    @app.context_processor
    def inject_global_data():
        return {
            'db_info':      get_db_info(),
            'current_year': datetime.datetime.now().year,
            'now':          datetime.datetime.now()
        }

    # ── Custom Jinja Filters ──────────────────────────────────────────────────
    @app.template_filter('datetime_format')
    def format_datetime(value, format="%b %d, %Y %I:%M %p"):
        if not value:
            return "-"
        if isinstance(value, str):
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    value = datetime.datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
        if isinstance(value, datetime.datetime):
            return value.strftime(format)
        return str(value)

    @app.template_filter('currency')
    def format_currency(value):
        try:
            return f"${float(value or 0.0):,.2f}"
        except (ValueError, TypeError):
            return "$0.00"

    # ── Error Pages ───────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html',
                               error_code=404,
                               error_title="Page Not Found",
                               error_message="The parking page or record you are looking for does not exist or has been moved."), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('error.html',
                               error_code=500,
                               error_title="Internal System Error",
                               error_message="A server error occurred. Please try again or check the system logs."), 500

    return app


# ─── Entry Point ─────────────────────────────────────────────────────────────
app = create_app()

if __name__ == '__main__':
    port = Config.PORT
    print("=" * 60)
    print("SMART PARKING MANAGEMENT SYSTEM")
    print(f"Server starting on http://127.0.0.1:{port}")
    print("Admin Default Login: admin / Admin@12345")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
