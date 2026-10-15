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
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard')
@login_required
def index():
    try:
        occupancy = get_occupancy_overview()
        payment_stats = get_payment_summary()
        total_res_row = query_db("SELECT COUNT(*) as cnt FROM reservations", fetch_one=True)
        total_reservations = total_res_row['cnt'] if total_res_row else 0
        recent_reservations = list_reservations(limit=6)
        recent_payments = query_db(""" SELECT p.*, r.reservation_code, c.name as customer_name, v.plate_number
            FROM payments p
            JOIN reservations r ON p.reservation_id = r.id
            JOIN customers c ON r.customer_id = c.id
            JOIN vehicles v ON r.vehicle_id = v.id
            ORDER BY p.payment_date DESC LIMIT 6 """, fetch_all=True)
        slots_sample = list_slots()[:16]
        db_info = get_db_info()
        return render_template('dashboard.html', occupancy=occupancy, payment_stats=payment_stats, total_reservations=total_reservations, recent_reservations=recent_reservations, recent_payments=recent_payments, slots_sample=slots_sample, db_info=db_info)
    except Exception as e:
        print(f"Dashboard index error: {e}")
        return render_template('dashboard.html', occupancy={'total_capacity':0,'occupied':0,'available':0,'reserved':0,'maintenance':0,'occupancy_percentage':0}, payment_stats={'total_revenue':0,'pending_amount':0}, total_reservations=0, recent_reservations=[], recent_payments=[], slots_sample=[], db_info={}, error_message=str(e))

@dashboard_bp.route('/api/dashboard/stats')
@login_required
def stats_api():
    try:
        occupancy = get_occupancy_overview()
        payment_stats = get_payment_summary()
        total_res_row = query_db("SELECT COUNT(*) as cnt FROM reservations", fetch_one=True)
        total_reservations = total_res_row['cnt'] if total_res_row else 0
        return jsonify({
            'total_spaces': occupancy.get('total_capacity',0),
            'available_spaces': occupancy.get('available',0),
            'reserved_spaces': occupancy.get('reserved',0),
            'occupied_spaces': occupancy.get('occupied',0),
            'maintenance_spaces': occupancy.get('maintenance',0),
            'occupancy_percentage': occupancy.get('occupancy_percentage',0),
            'total_reservations': total_reservations,
            'total_revenue': payment_stats.get('total_revenue',0),
            'pending_amount': payment_stats.get('pending_amount',0),
            'db_info': get_db_info()
        })
    except Exception as e:
        print(f"Stats API error: {e}")
        return jsonify({'total_spaces':0,'available_spaces':0,'total_reservations':0,'total_revenue':0,'error':str(e)})

@dashboard_bp.route('/api/dashboard/charts')
@login_required
def charts_api():
    try:
        occupancy = get_occupancy_overview()
        return jsonify({'occupancy': occupancy, 'bookings': [], 'revenue': []})
    except Exception as e:
        return jsonify({'occupancy': {}, 'bookings': [], 'revenue': [], 'error': str(e)})