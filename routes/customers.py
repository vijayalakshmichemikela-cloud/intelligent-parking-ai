"""
Customers Blueprint
Handles customer profiles, vehicle registrations, and customer activity history.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from routes.auth import login_required
from services.customer_service import list_customers, get_customer_details

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/customers')
@login_required
def index():
    """Customer directory with search and spending aggregates."""
    search = request.args.get('search', '').strip()
    customers = list_customers(search=search)
    return render_template('customers.html', customers=customers, search=search)


@customers_bp.route('/customers/<int:customer_id>')
@login_required
def details(customer_id):
    """View detailed customer profile, registered vehicles, and complete history."""
    data = get_customer_details(customer_id)
    if not data:
        flash('Customer profile not found.', 'danger')
        return redirect(url_for('customers.index'))

    return render_template('customer_details.html', **data)
