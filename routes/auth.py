"""
Auth and Customers Blueprint
Handles: admin login/logout, session protection, customer directory,
         customer profile details, and vehicle histories.

All customer-related service functions live here too (no separate
customer_service.py needed — the functions are small enough to stay together).
"""

import io
import csv
import datetime
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, Response)
from werkzeug.security import check_password_hash
from database import query_db

auth_bp = Blueprint('auth', __name__)


# ═══════════════════════════════════════════════════════════════
#  LOGIN-REQUIRED DECORATOR
# ═══════════════════════════════════════════════════════════════

def login_required(f):
    """Decorator: redirects to login page if admin is not authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_id'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# ═══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════════

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page and authentication handler."""
    if session.get('admin_id'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        next_url = request.form.get('next') or url_for('dashboard.index')

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html', username=username)

        admin = query_db(
            "SELECT * FROM admins WHERE username = %s OR email = %s",
            (username, username),
            fetch_one=True
        )

        if not admin or not check_password_hash(admin['password_hash'], password):
            flash('Invalid username or password. Please try again.', 'danger')
            return render_template('login.html', username=username)

        # Successful login — save admin info in session
        session.clear()
        session['admin_id']       = admin['id']
        session['admin_username'] = admin['username']
        session['admin_name']     = admin['full_name']
        session['admin_role']     = admin['role']

        query_db(
            "UPDATE admins SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
            (admin['id'],),
            commit=True
        )

        flash(f'Welcome back, {admin["full_name"]}!', 'success')
        return redirect(next_url)

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Log out the current admin and clear the session."""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER SERVICE FUNCTIONS
#  (Formerly in services/customer_service.py)
# ═══════════════════════════════════════════════════════════════

def list_customers(search=None, limit=100):
    """List all customers with vehicle counts, reservation counts, and total spending."""
    sql = """
        SELECT c.*,
               COUNT(DISTINCT v.id)  AS vehicles_count,
               COUNT(DISTINCT r.id)  AS reservations_count,
               COALESCE(SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END), 0) AS total_spent,
               GROUP_CONCAT(DISTINCT v.plate_number) AS plates_list
        FROM customers c
        LEFT JOIN vehicles     v ON c.id = v.customer_id
        LEFT JOIN reservations r ON c.id = r.customer_id
        LEFT JOIN payments     p ON r.id = p.reservation_id
        WHERE 1=1
    """
    params = []

    if search:
        like = f"%{search.strip()}%"
        sql += """ AND (
            c.name LIKE %s OR c.email LIKE %s OR c.phone LIKE %s OR v.plate_number LIKE %s
        )"""
        params.extend([like, like, like, like])

    sql += " GROUP BY c.id ORDER BY c.created_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    return query_db(sql, params, fetch_all=True)


def get_customer_details(customer_id):
    """Return full customer profile: info, vehicles, reservations, and payments."""
    customer = query_db("SELECT * FROM customers WHERE id = %s", (customer_id,), fetch_one=True)
    if not customer:
        return None

    vehicles = query_db(
        "SELECT * FROM vehicles WHERE customer_id = %s ORDER BY created_at DESC",
        (customer_id,), fetch_all=True
    )

    reservations = query_db("""
        SELECT r.*, v.plate_number, s.slot_number, a.area_name, p.status AS payment_status
        FROM reservations r
        JOIN vehicles     v ON r.vehicle_id = v.id
        JOIN parking_slots s ON r.slot_id   = s.id
        JOIN parking_areas a ON s.area_id   = a.id
        LEFT JOIN payments p ON r.id        = p.reservation_id
        WHERE r.customer_id = %s
        ORDER BY r.created_at DESC
    """, (customer_id,), fetch_all=True)

    payments = query_db("""
        SELECT p.*, r.reservation_code
        FROM payments p
        JOIN reservations r ON p.reservation_id = r.id
        WHERE r.customer_id = %s
        ORDER BY p.payment_date DESC
    """, (customer_id,), fetch_all=True)

    return {
        'customer':     customer,
        'vehicles':     vehicles,
        'reservations': reservations,
        'payments':     payments
    }


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER ROUTES
#  (Formerly in routes/customers.py)
# ═══════════════════════════════════════════════════════════════

@auth_bp.route('/customers')
@login_required
def customers_index():
    """Customer directory with search and spending aggregates."""
    search    = request.args.get('search', '').strip()
    customers = list_customers(search=search)
    return render_template('customers.html', customers=customers, search=search)


@auth_bp.route('/customers/<int:customer_id>')
@login_required
def customer_details(customer_id):
    """Full customer profile: vehicles, reservations, and payment history."""
    data = get_customer_details(customer_id)
    if not data:
        flash('Customer profile not found.', 'danger')
        return redirect(url_for('auth.customers_index'))
    return render_template('customer_details.html', **data)
