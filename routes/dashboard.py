"""
Dashboard Blueprint
Renders administrative dashboard with live database metrics, charts,
recent activity tables, and real-time JSON API endpoints.
"""

import datetime
from flask import Blueprint, render_template, jsonify, redirect, url_for
from routes.auth import login_required
from database import query_db, get_db_info
from services.occupancy_service import get_occupancy_overview
from routes.reservations import get_payment_summary
from services.reservation_service import list_reservations
from services.parking_service import list_slots

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def root():
    """Redirect root to dashboard."""
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main administrative dashboard view."""
    occupancy = get_occupancy_overview()
    payment_stats = get_payment_summary()
    
    # Total reservations count
    total_res_row = query_db("SELECT COUNT(*) as cnt FROM reservations", fetch_one=True)
    total_reservations = total_res_row['cnt'] if total_res_row else 0

    # Recent reservations (top 6)
    recent_reservations = list_reservations(limit=6)

    # Recent payment transactions (top 6)
    recent_payments = query_db("""
        SELECT p.*, r.reservation_code, c.name as customer_name, v.plate_number
        FROM payments p
        JOIN reservations r ON p.reservation_id = r.id
        JOIN customers c ON r.customer_id = c.id
        JOIN vehicles v ON r.vehicle_id = v.id
        ORDER BY p.payment_date DESC
        LIMIT 6
    """, fetch_all=True)

    # Slots overview (for quick slot grid snapshot)
    slots_sample = list_slots()[:16]

    db_info = get_db_info()

    return render_template(
        'dashboard.html',
        occupancy=occupancy,
        payment_stats=payment_stats,
        total_reservations=total_reservations,
        recent_reservations=recent_reservations,
        recent_payments=recent_payments,
        slots_sample=slots_sample,
        db_info=db_info
    )


@dashboard_bp.route('/api/dashboard/stats')
@login_required
def stats_api():
    """Real-time JSON metrics endpoint for dashboard auto-refresh."""
    occupancy = get_occupancy_overview()
    payment_stats = get_payment_summary()
    
    total_res_row = query_db("SELECT COUNT(*) as cnt FROM reservations", fetch_one=True)
    total_reservations = total_res_row['cnt'] if total_res_row else 0

    return jsonify({
        'total_spaces': occupancy['total_capacity'],
        'available_spaces': occupancy['available'],
        'reserved_spaces': occupancy['reserved'],
        'occupied_spaces': occupancy['occupied'],
        'maintenance_spaces': occupancy['maintenance'],
        'occupancy_percentage': occupancy['occupancy_percentage'],
        'total_reservations': total_reservations,
        'total_revenue': payment_stats['total_revenue'],
        'pending_amount': payment_stats['pending_amount'],
        'db_info': get_db_info()
    })


@dashboard_bp.route('/api/dashboard/charts')
@login_required
def charts_api():
    """Chart.js dataset endpoint for occupancy doughnut, 7-day bookings, and revenue."""
    occupancy = get_occupancy_overview()
    
    # 1. Occupancy Doughnut Data
    doughnut_data = {
        'labels': ['Available', 'Reserved', 'Occupied', 'Maintenance'],
        'data': [
            occupancy['available'],
            occupancy['reserved'],
            occupancy['occupied'],
            occupancy['maintenance']
        ],
        'colors': ['#10b981', '#f59e0b', '#ef4444', '#64748b']
    }

    # 2. Last 7 Days Reservation Counts & Revenue
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    date_labels = [d.strftime('%a (%b %d)') for d in days]
    
    reservations_trend = []
    revenue_trend = []

    for d in days:
        d_start = f"{d.strftime('%Y-%m-%d')} 00:00:00"
        d_end = f"{d.strftime('%Y-%m-%d')} 23:59:59"

        # Count reservations
        res_row = query_db(
            "SELECT COUNT(*) as cnt FROM reservations WHERE created_at >= %s AND created_at <= %s",
            (d_start, d_end),
            fetch_one=True
        )
        reservations_trend.append(res_row['cnt'] if res_row else 0)

        # Sum revenue for paid payments
        rev_row = query_db(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'paid' AND payment_date >= %s AND payment_date <= %s",
            (d_start, d_end),
            fetch_one=True
        )
        revenue_trend.append(float(rev_row['total']) if rev_row else 0.0)

    return jsonify({
        'doughnut': doughnut_data,
        'trends': {
            'labels': date_labels,
            'reservations': reservations_trend,
            'revenue': revenue_trend
        }
    })
